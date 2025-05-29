#!/usr/bin/env python3
# crawler.py
import logging
import time
import os
import re
import json
import csv # For AI output logging
import threading # For logging thread IDs if needed
from typing import Optional, Tuple, List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor 

from config import Config 
import utils 

from ai_assistant import AIAssistant
from appium_driver import AppiumDriver
from screen_state_manager import ScreenStateManager, ScreenRepresentation 
from database import DatabaseManager 
from action_mapper import ActionMapper
from traffic_capture_manager import TrafficCaptureManager
from action_executor import ActionExecutor
from app_context_manager import AppContextManager
from screenshot_annotator import ScreenshotAnnotator

from selenium.webdriver.remote.webelement import WebElement
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import WebDriverException


UI_STATUS_PREFIX = "UI_STATUS:"
UI_STEP_PREFIX = "UI_STEP:"
UI_ACTION_PREFIX = "UI_ACTION:"
UI_SCREENSHOT_PREFIX = "UI_SCREENSHOT:"
UI_ANNOTATED_SCREENSHOT_PREFIX = "UI_ANNOTATED_SCREENSHOT:"
UI_END_PREFIX = "UI_END:"

class AppCrawler:
    def __init__(self, app_config: Config):
        self.cfg = app_config
        logging.info(f"AppCrawler initializing with App Package: {self.cfg.APP_PACKAGE}")

        required_attrs_for_crawler = [
            'APPIUM_SERVER_URL', 'NEW_COMMAND_TIMEOUT', 'APPIUM_IMPLICIT_WAIT',
            'GEMINI_API_KEY', 'DEFAULT_MODEL_TYPE', 'AI_SAFETY_SETTINGS',
            'DB_NAME', 'APP_PACKAGE', 'APP_ACTIVITY', 'SHUTDOWN_FLAG_PATH',
            'MAX_CRAWL_STEPS', 'MAX_CRAWL_DURATION_SECONDS',
            'MAX_CONSECUTIVE_AI_FAILURES', 'MAX_CONSECUTIVE_MAP_FAILURES',
            'MAX_CONSECUTIVE_EXEC_FAILURES', 'MAX_CONSECUTIVE_CONTEXT_FAILURES',
            'WAIT_AFTER_ACTION', 'ALLOWED_EXTERNAL_PACKAGES', 'ENABLE_XML_CONTEXT',
            'XML_SNIPPET_MAX_LEN', 'SCREENSHOTS_DIR', 'ANNOTATED_SCREENSHOTS_DIR',
            'ENABLE_TRAFFIC_CAPTURE', 'CONTINUE_EXISTING_RUN', 'OUTPUT_DATA_DIR'
        ]
        for attr in required_attrs_for_crawler:
            val = getattr(self.cfg, attr, None)
            if val is None: # Check for None specifically
                # Allow empty list/dict for these specific keys
                if attr == 'ALLOWED_EXTERNAL_PACKAGES' and isinstance(getattr(self.cfg, attr, None), list): continue
                if attr == 'AI_SAFETY_SETTINGS' and isinstance(getattr(self.cfg, attr, None), dict): continue
                raise ValueError(f"AppCrawler: Critical configuration '{attr}' is missing or None.")
        if not self.cfg.SHUTDOWN_FLAG_PATH: # Explicitly check SHUTDOWN_FLAG_PATH
            raise ValueError("AppCrawler: Critical configuration 'SHUTDOWN_FLAG_PATH' must be set.")


        self.driver = AppiumDriver(app_config=self.cfg)
        self.ai_assistant = AIAssistant(app_config=self.cfg)
        self.db_manager = DatabaseManager(app_config=self.cfg) 
        self.screen_state_manager = ScreenStateManager(db_manager=self.db_manager, driver=self.driver, app_config=self.cfg)
        self.element_finding_strategies: List[Tuple[str, Optional[str], str]] = [
            ('id', AppiumBy.ID, "ID"),
            ('acc_id', AppiumBy.ACCESSIBILITY_ID, "Accessibility ID"),
            ('xpath_exact', AppiumBy.XPATH, "XPath Exact Match"),
            ('xpath_contains', AppiumBy.XPATH, "XPath Contains Match")
        ]
        self.action_mapper = ActionMapper(driver=self.driver, element_finding_strategies=self.element_finding_strategies, app_config=self.cfg)
        self.traffic_capture_manager = TrafficCaptureManager(driver=self.driver, app_config=self.cfg)
        self.action_executor = ActionExecutor(driver=self.driver, app_config=self.cfg)
        self.app_context_manager = AppContextManager(driver=self.driver, app_config=self.cfg)
        self.screenshot_annotator = ScreenshotAnnotator(driver=self.driver, app_config=self.cfg)

        self.consecutive_ai_failures = 0
        self.consecutive_map_failures = 0
        self._last_action_description: str = "CRAWL_START"
        self.previous_composite_hash: Optional[str] = None
        self.run_id: Optional[int] = None
        self.crawl_steps_taken: int = 0
        self.crawl_start_time: float = 0.0
        
        self.is_shutting_down: bool = False
        self.monitor_task: Optional[asyncio.Task] = None
        self._cleanup_called: bool = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        self.db_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='DBExecutorThread')
        self.default_executor = ThreadPoolExecutor(thread_name_prefix='DefaultExecutorThread')
        
        self.ai_output_csv_path: Optional[str] = None
        self.ai_output_csv_headers = [
            "timestamp", "run_id", "step_number", "screen_id", "screen_composite_hash", 
            "ai_action_type", "ai_target_identifier", "ai_input_text", "ai_reasoning", 
            "all_ui_elements_count", "raw_ai_response_json"
        ]
        self._ai_csv_header_written = False

        logging.info("AppCrawler initialized successfully.")

    async def _monitor_shutdown_flag(self):
        logging.debug("Shutdown monitor task started.")
        try:
            while True:
                if self.is_shutting_down: # If already shutting down for another reason by main loop
                    logging.debug("Shutdown monitor sees self.is_shutting_down is true, exiting.")
                    return

                flag_path = str(self.cfg.SHUTDOWN_FLAG_PATH) # Ensure it's a string
                if os.path.exists(flag_path):
                    try:
                        # Optional: read content if specific content matters, otherwise existence is enough.
                        # with open(flag_path, 'r') as f:
                        #     content = f.read().lower()
                        #     if 'stop' in content: 
                        logging.info(f"Shutdown flag detected by monitoring task at {flag_path}. Initiating graceful shutdown.")
                        if not self.is_shutting_down: # Avoid redundant UI_END prints
                            print(f"{UI_END_PREFIX}GRACEFUL_SHUTDOWN_REQUESTED_BY_MONITOR")
                        self.is_shutting_down = True # Signal the main loop
                        return # Exit monitor task once flag is processed
                    except Exception as e:
                        logging.warning(f"Error reading shutdown flag in monitoring task ({flag_path}): {e}")
                
                await asyncio.sleep(0.5) # Check interval
        except asyncio.CancelledError:
            logging.info("Shutdown monitor task cancelled.")
        except Exception as e: # Catch any other unexpected error in the monitor
            logging.error(f"Exception in shutdown monitor task: {e}", exc_info=True)
        finally:
            logging.debug("Shutdown monitor task finished.")

    def _should_terminate(self) -> bool:
        # Direct check for self.is_shutting_down (set by monitor or other conditions)
        if self.is_shutting_down:
            # logging.info("Termination check: Shutdown already initiated (self.is_shutting_down is True).")
            # This log can be very verbose if checked frequently. Debug level might be better.
            logging.debug("Termination check: self.is_shutting_down is True.")
            return True

        flag_path = str(self.cfg.SHUTDOWN_FLAG_PATH)
        if os.path.exists(flag_path): 
            logging.info(f"Termination check (_should_terminate direct): External shutdown flag detected at {flag_path}.")
            if not self.is_shutting_down: 
                 print(f"{UI_END_PREFIX}GRACEFUL_SHUTDOWN_REQUESTED_BY_DIRECT_CHECK") 
            self.is_shutting_down = True 
            return True

        if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS: 
            logging.info(f"Termination check: Reached max steps ({self.cfg.MAX_CRAWL_STEPS}).")
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_STEPS_REACHED") 
            self.is_shutting_down = True
            return True

        if self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and \
           (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS: 
            logging.info(f"Termination check: Reached max duration ({self.cfg.MAX_CRAWL_DURATION_SECONDS}s).")
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_DURATION_REACHED") 
            self.is_shutting_down = True
            return True

        if self.consecutive_ai_failures >= self.cfg.MAX_CONSECUTIVE_AI_FAILURES: 
            logging.error(f"Termination check: Exceeded max AI failures ({self.cfg.MAX_CONSECUTIVE_AI_FAILURES}).")
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}FAILURE_MAX_AI_FAIL") 
            self.is_shutting_down = True
            return True
            
        if self.consecutive_map_failures >= self.cfg.MAX_CONSECUTIVE_MAP_FAILURES: 
            logging.error(f"Termination check: Exceeded max mapping failures ({self.cfg.MAX_CONSECUTIVE_MAP_FAILURES}).")
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}FAILURE_MAX_MAP_FAIL") 
            self.is_shutting_down = True
            return True
            
        if self.action_executor.consecutive_exec_failures >= self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES: 
            logging.error(f"Termination check: Exceeded max execution failures ({self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES}).")
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}FAILURE_MAX_EXEC_FAIL") 
            self.is_shutting_down = True
            return True
            
        if self.app_context_manager.consecutive_context_failures >= self.cfg.MAX_CONSECUTIVE_CONTEXT_FAILURES: 
            logging.error(f"Termination check: Exceeded max context failures ({self.cfg.MAX_CONSECUTIVE_CONTEXT_FAILURES}).")
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}FAILURE_MAX_CONTEXT_FAIL") 
            self.is_shutting_down = True
            return True
        return False


    def _handle_ai_failure(self):
        self.consecutive_ai_failures += 1
        logging.warning(f"AI failure. Count: {self.consecutive_ai_failures}/{self.cfg.MAX_CONSECUTIVE_AI_FAILURES}")

    def _handle_mapping_failure(self):
        self.consecutive_map_failures += 1
        logging.warning(f"Action mapping failure. Count: {self.consecutive_map_failures}/{self.cfg.MAX_CONSECUTIVE_MAP_FAILURES}")

    async def _run_sync_in_executor(self, executor: Optional[ThreadPoolExecutor], func, *args):
        # Ensure self.loop is available
        if not self.loop:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                logging.critical(f"No running event loop available for {func.__name__}. Cannot proceed.")
                # Depending on severity, could raise or handle. For now, raise.
                raise RuntimeError(f"AppCrawler event loop not set and could not be fetched for {func.__name__}.")
        
        target_executor = executor if executor else self.default_executor # Fallback to default if specific is None
        if not target_executor: # Should not happen if default_executor is initialized
             logging.critical(f"No executor available for {func.__name__}. This is a critical error.")
             raise RuntimeError(f"No executor for {func.__name__}")

        return await self.loop.run_in_executor(target_executor, func, *args)

    async def _setup_ai_output_csv(self):
        if not self.cfg.OUTPUT_DATA_DIR or not self.cfg.APP_PACKAGE:
            logging.error("Cannot setup AI output CSV: OUTPUT_DATA_DIR or APP_PACKAGE not configured.")
            return

        ai_output_dir = os.path.join(str(self.cfg.OUTPUT_DATA_DIR), "ai_outputs_csv")
        try:
            await self._run_sync_in_executor(self.default_executor, os.makedirs, ai_output_dir, True) 
            self.ai_output_csv_path = os.path.join(ai_output_dir, f"{str(self.cfg.APP_PACKAGE)}_ai_interactions.csv")
            logging.info(f"AI interaction logs will be saved to: {self.ai_output_csv_path}")

            def check_and_write_header_sync():
                # This function runs in an executor thread
                if self.ai_output_csv_path is None: return # Should not happen if called after path is set
                
                # Check if file needs header
                needs_header = not os.path.exists(self.ai_output_csv_path) or os.path.getsize(self.ai_output_csv_path) == 0
                
                if needs_header:
                    with open(self.ai_output_csv_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(self.ai_output_csv_headers)
                    self._ai_csv_header_written = True # Mark true for this instance
                else:
                    self._ai_csv_header_written = True # Assume exists if file is not empty
            
            await self._run_sync_in_executor(self.default_executor, check_and_write_header_sync)

        except IOError as e:
            logging.error(f"Failed to initialize or write AI CSV header to {self.ai_output_csv_path}: {e}")
            self.ai_output_csv_path = None 
        except Exception as e:
            logging.error(f"Unexpected error setting up AI CSV log: {e}", exc_info=True)
            self.ai_output_csv_path = None


    async def _log_ai_output_to_csv(self, run_id, step, screen_id, screen_hash, ai_response_dict):
        if not self.ai_output_csv_path: # If setup failed, skip logging
            return

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        action_to_perform = {}
        all_ui_elements_count = 0
        raw_json_str = "{}" # Default empty JSON object

        if isinstance(ai_response_dict, dict):
            action_to_perform = ai_response_dict.get("action_to_perform", {})
            all_ui_elements = ai_response_dict.get("all_ui_elements", []) # Could be list or None
            all_ui_elements_count = len(all_ui_elements) if isinstance(all_ui_elements, list) else 0
            try:
                raw_json_str = json.dumps(ai_response_dict)
            except TypeError: # Handle non-serializable content if any
                raw_json_str = json.dumps({"error": "failed to serialize full AI response", "original_type": str(type(ai_response_dict))})
        elif ai_response_dict is not None : # If it's not a dict but not None (e.g. error string)
             raw_json_str = json.dumps({"raw_response": str(ai_response_dict)})
        # If ai_response_dict is None, raw_json_str remains "{}"

        row_data = {
            "timestamp": timestamp,
            "run_id": run_id if run_id is not None else "",
            "step_number": step,
            "screen_id": screen_id if screen_id is not None else "",
            "screen_composite_hash": screen_hash if screen_hash is not None else "",
            "ai_action_type": action_to_perform.get("action"), # Will be None if action_to_perform is empty
            "ai_target_identifier": action_to_perform.get("target_identifier"),
            "ai_input_text": action_to_perform.get("input_text"),
            "ai_reasoning": action_to_perform.get("reasoning"),
            "all_ui_elements_count": all_ui_elements_count,
            "raw_ai_response_json": raw_json_str
        }
        
        def write_csv_row_sync():
            if self.ai_output_csv_path is None: return 

            try:
                # Determine if header needs to be written (again, robustly)
                # This is a bit redundant if _setup_ai_output_csv worked perfectly,
                # but good for robustness if multiple crawlers somehow run and race.
                # For a single crawler, _ai_csv_header_written should manage it.
                file_exists = os.path.exists(self.ai_output_csv_path)
                needs_header_check_in_append_mode = not file_exists or os.path.getsize(self.ai_output_csv_path) == 0
                
                with open(self.ai_output_csv_path, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.ai_output_csv_headers)
                    if needs_header_check_in_append_mode and not self._ai_csv_header_written:
                        # This is a fallback if the initial setup didn't write or was bypassed.
                        # In append mode, only write header if file was effectively empty.
                        writer.writeheader()
                        # self._ai_csv_header_written = True # Mark for this session, though setup should do it primarily
                    writer.writerow(row_data)
            except IOError as e:
                logging.error(f"Failed to write AI output to CSV {self.ai_output_csv_path}: {e}")
            except Exception as e_csv: # Catch other potential errors during CSV writing
                logging.error(f"Unexpected error writing AI CSV row to {self.ai_output_csv_path}: {e_csv}", exc_info=True)

        await self._run_sync_in_executor(self.default_executor, write_csv_row_sync)


    async def perform_full_cleanup(self):
        if self._cleanup_called: # Prevent multiple cleanup calls
            logging.debug("Cleanup already called or in progress.")
            return
        
        logging.info("Performing full cleanup for AppCrawler...")
        self.is_shutting_down = True # Ensure state reflects shutdown
        self._cleanup_called = True
        
        if self.cfg.ENABLE_TRAFFIC_CAPTURE and self.traffic_capture_manager and self.traffic_capture_manager.is_capturing():
            logging.info("Ensuring traffic capture stopped and pulled...")
            try:
                # traffic_capture_manager methods are async
                await self.traffic_capture_manager.stop_capture_and_pull_async(
                    run_id=self.run_id or 0, step_num=self.crawl_steps_taken)
            except Exception as e_traffic:
                logging.error(f"Error during traffic capture finalization in cleanup: {e_traffic}", exc_info=True)

        if self.driver: # Check if driver object exists
            try:
                logging.info("Quitting Appium driver session...")
                # driver.disconnect is sync, run in executor
                await self._run_sync_in_executor(self.default_executor, self.driver.disconnect)
            except Exception as e_driver:
                logging.error(f"Error during Appium driver quit: {e_driver}", exc_info=True)
            finally:
                self.driver = None # Clear reference after attempting to quit
        
        if self.db_manager: 
            try:
                logging.info("Closing database connection via DB executor...")
                # db_manager.close is sync
                await self._run_sync_in_executor(self.db_executor, self.db_manager.close)
            except Exception as e_db_close:
                logging.error(f"Error closing database via DB executor: {e_db_close}", exc_info=True)
            # self.db_manager instance is kept, its internal connection is closed.
            
        # Remove shutdown flag if it exists and this cleanup is part of graceful shutdown
        flag_path = str(self.cfg.SHUTDOWN_FLAG_PATH)
        if os.path.exists(flag_path):
            try:
                await self._run_sync_in_executor(self.default_executor, os.remove, flag_path)
                logging.info(f"Cleaned up shutdown flag: {flag_path}")
            except OSError as e_flag:
                logging.warning(f"Could not remove shutdown flag {flag_path}: {e_flag}")
            
        logging.info("AppCrawler full cleanup process finished (executors will be shutdown in main run() method).")

    async def _initialize_run(self) -> Tuple[bool, str]:
        if not self.db_manager: # Should be caught by __init__ but double check
            logging.critical("DatabaseManager (self.db_manager) is not initialized.")
            return False, "FAILURE_DB_NOT_INIT"
        if not self.driver:
            logging.critical("AppiumDriver (self.driver) is not initialized.")
            return False, "FAILURE_DRIVER_NOT_INIT"

        await self._setup_ai_output_csv() # Setup CSV logging for AI interactions

        # Get or create run ID using DB executor
        self.run_id = await self._run_sync_in_executor(self.db_executor,
            self.db_manager.get_or_create_run_info, str(self.cfg.APP_PACKAGE), str(self.cfg.APP_ACTIVITY)
        )
        if self.run_id is None:
            logging.critical("Failed to get or create run ID.")
            return False, "FAILURE_RUN_ID"
        
        await self._run_sync_in_executor(self.db_executor, 
            self.db_manager.update_run_status, self.run_id, "RUNNING"
        )
        logging.info(f"Starting/Continuing crawl run ID: {self.run_id} for app: {self.cfg.APP_PACKAGE}")
        print(f"{UI_STATUS_PREFIX}INITIALIZING_CRAWL_RUN_{self.run_id}")

        db_step_count = await self._run_sync_in_executor(self.db_executor, 
            self.db_manager.get_step_count_for_run, self.run_id
        )
        is_continuation_run = bool(self.cfg.CONTINUE_EXISTING_RUN and db_step_count > 0)
        
        # Initialize ScreenStateManager for the run (uses DB executor for its internal DB calls if any)
        await self._run_sync_in_executor(self.default_executor, # Or db_executor if SSM's init is heavy on DB
            self.screen_state_manager.initialize_for_run,
            self.run_id, str(self.cfg.APP_PACKAGE),
            str(self.cfg.APP_ACTIVITY), is_continuation_run
        )
        # ScreenStateManager updates its current_run_latest_step_number internally
        self.crawl_steps_taken = self.screen_state_manager.current_run_latest_step_number
        logging.info(f"Run type: {'Continuation' if is_continuation_run else 'New'}. Initial steps (from history): {self.crawl_steps_taken}.")
        self.crawl_start_time = time.time() # Start timer after setup

        # Connect to Appium (sync, use default executor)
        driver_connected = await self._run_sync_in_executor(self.default_executor, self.driver.connect)
        if not driver_connected:
            logging.critical("Failed to connect to Appium.")
            # Update run status to reflect failure before returning
            await self._run_sync_in_executor(self.db_executor, self.db_manager.update_run_status, self.run_id, "FAILED_APPIUM_CONNECT")
            return False, "FAILED_APPIUM_CONNECT"
        
        # Launch and verify app (sync, use default executor)
        app_launched = await self._run_sync_in_executor(self.default_executor, 
            self.app_context_manager.launch_and_verify_app
        )
        if not app_launched:
            logging.critical("Failed to launch/verify target app.")
            await self._run_sync_in_executor(self.db_executor, self.db_manager.update_run_status, self.run_id, "FAILED_APP_LAUNCH")
            return False, "FAILED_APP_LAUNCH"

        if self.cfg.ENABLE_TRAFFIC_CAPTURE:
            pcap_filename_template = f"{str(self.cfg.APP_PACKAGE)}_run{self.run_id}_step{{step_num}}.pcap"
            # traffic_capture_manager.start_capture_async is async
            capture_started = await self.traffic_capture_manager.start_capture_async(filename_template=pcap_filename_template)
            if not capture_started:
                logging.warning("Failed to start traffic capture. Continuing without it.")
            else:
                logging.info("Traffic capture started.")
        
        return True, "RUNNING" # Initial status if all good

    async def _handle_step_failure(self, step_num: int, from_screen_id: Optional[int], reason: str, 
                                   ai_suggestion: Optional[Dict[str, Any]] = None, 
                                   action_str_for_log: Optional[str] = None) -> str:
        # This method logs a failure for a step but does not decide termination.
        # Termination is handled by _should_terminate based on failure counts.
        logging.error(f"Step {step_num}: Failure - {reason}. Action attempted: '{action_str_for_log or 'N/A'}'")
        
        # Log the failed step to the database
        if self.db_manager and self.run_id is not None: 
            await self._run_sync_in_executor(self.db_executor,
                self.db_manager.insert_step_log,
                self.run_id, step_num,
                from_screen_id, None, # No 'to_screen_id' as action likely failed or state is uncertain
                action_str_for_log or reason, # Log the attempted action or reason for failure
                json.dumps(ai_suggestion) if ai_suggestion else None, # AI suggestion that led to this
                None, # No Appium action details if mapping/execution failed before that
                False, # Mark as not successful
                reason # Detailed reason for failure
            )
        
        # Record failed action attempt in screen state manager's run history
        if self.screen_state_manager and self.previous_composite_hash: # previous_composite_hash is of from_screen
             failed_action_desc = f"{action_str_for_log or reason} (failed: {reason})"
             await self._run_sync_in_executor(self.default_executor, 
                self.screen_state_manager.record_action_taken_from_screen, 
                self.previous_composite_hash, failed_action_desc
            )
        
        # The function returns a string indicating the type of failure,
        # which might be used by the caller for specific failure counting.
        return f"STEP_FAILED_{reason.upper().replace(' ', '_')}"


    async def _perform_crawl_step(self, current_step_for_log: int) -> Tuple[Optional[int], str, Optional[str]]:
        logging.info(f"--- Crawl Step {current_step_for_log} (Run ID: {self.run_id}) ---")
        print(f"{UI_STEP_PREFIX}{current_step_for_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Checking app context...")
        
        current_screen_id_for_log: Optional[int] = None # From screen of this step
        step_outcome_status: str = "STEP_STARTED" 
        termination_reason_for_run: Optional[str] = None # If this step causes overall termination

        # 1. Ensure App Context
        in_app = await self._run_sync_in_executor(self.default_executor, self.app_context_manager.ensure_in_app)
        if not in_app:
            self.app_context_manager.consecutive_context_failures +=1 # Increment failure, _should_terminate will check
            last_known_screen_id = None # Try to get last known screen for logging the failed step
            if self.previous_composite_hash and self.screen_state_manager:
                prev_screen = self.screen_state_manager.get_screen_by_composite_hash(self.previous_composite_hash)
                if prev_screen: last_known_screen_id = prev_screen.id
            
            await self._handle_step_failure(current_step_for_log, last_known_screen_id , "CONTEXT_ENSURE_FAIL")
            step_outcome_status = "CONTEXT_FAIL"
            # _should_terminate will be checked by main loop after this step returns
            return last_known_screen_id, step_outcome_status, None # No immediate run termination reason from here

        self.app_context_manager.reset_context_failures() # Reset if successful

        # 2. Get Current Screen State
        print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Getting screen state...")
        candidate_screen_repr = await self._run_sync_in_executor(self.default_executor,
            self.screen_state_manager.get_current_screen_representation,
            self.run_id, current_step_for_log
        )
        if not candidate_screen_repr or not candidate_screen_repr.screenshot_bytes:
            self._handle_mapping_failure() # Or a more generic state capture failure
            await self._handle_step_failure(current_step_for_log, None , "STATE_GET_FAIL")
            step_outcome_status = "STATE_FAIL"
            return None, step_outcome_status, None

        # 3. Process and Record Screen State (DB interaction)
        process_result = await self._run_sync_in_executor(self.db_executor, # db_executor due to DB writes
            self.screen_state_manager.process_and_record_state,
            candidate_screen_repr, self.run_id, current_step_for_log # step_number here is 'first_seen_step_number' for new screens
        )
        current_state_repr, visit_info = process_result
        current_screen_id_for_log = current_state_repr.id 

        if current_state_repr.screenshot_path:
            print(f"{UI_SCREENSHOT_PREFIX}{current_state_repr.screenshot_path}")
        else:
            logging.warning(f"Step {current_step_for_log}: Screenshot path is missing for screen ID {current_state_repr.id} after processing.")

        logging.info(f"Step {current_step_for_log}: State Processed. Screen ID: {current_screen_id_for_log}, Hash: '{current_state_repr.composite_hash[:12]}', Activity: '{current_state_repr.activity_name}'")
        self.previous_composite_hash = current_state_repr.composite_hash # Update for next step's context

        # 4. Get AI Action Suggestion
        print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Requesting AI action...")
        simplified_xml_context = current_state_repr.xml_content or ""
        if self.cfg.ENABLE_XML_CONTEXT and current_state_repr.xml_content:
            simplified_xml_context = await self._run_sync_in_executor(self.default_executor, 
                utils.simplify_xml_for_ai, current_state_repr.xml_content, int(self.cfg.XML_SNIPPET_MAX_LEN)
            )
        
        if current_state_repr.screenshot_bytes is None: # Should have been caught by candidate_screen_repr check
            self._handle_ai_failure()
            await self._handle_step_failure(current_step_for_log, current_screen_id_for_log, "AI_FAIL_NO_SCREENSHOT_BYTES")
            if self.run_id is not None: # Log to AI CSV even if failing
                 await self._log_ai_output_to_csv(self.run_id, current_step_for_log, current_screen_id_for_log, 
                                         current_state_repr.composite_hash, {"error": "Screenshot bytes were None for AI input"})
            step_outcome_status = "AI_FAIL"
            return current_screen_id_for_log, step_outcome_status, None

        ai_full_response = await self._run_sync_in_executor(self.default_executor, # AI call can be blocking
            self.ai_assistant.get_next_action,
            current_state_repr.screenshot_bytes,
            simplified_xml_context,
            visit_info.get("previous_actions_on_this_state", []), # Historical actions on this specific screen state
            visit_info.get("visit_count_this_run", 1),       # Visits to this screen state in current run
            current_state_repr.composite_hash                 # For AI to potentially use as context/ID
        )
        
        # Log AI output to CSV regardless of success/failure of the suggestion
        if self.run_id is not None and current_state_repr.composite_hash is not None: # Ensure IDs are available
             await self._log_ai_output_to_csv(self.run_id, current_step_for_log, current_screen_id_for_log, 
                                     current_state_repr.composite_hash, ai_full_response)

        # Early exit if termination is flagged during AI processing (e.g. by monitor)
        if self._should_terminate(): 
            # _should_terminate sets self.is_shutting_down and prints UI_END if applicable
            # The exact termination reason (flag, timeout etc.) will be determined by run_async's logic after loop.
            # Log that this step was interrupted.
            await self._handle_step_failure(current_step_for_log, current_screen_id_for_log, "INTERRUPTED_DURING_AI", ai_full_response if isinstance(ai_full_response, dict) else {"raw_response": str(ai_full_response)})
            return current_screen_id_for_log, "STEP_INTERRUPTED", "TERMINATED_DURING_AI" # Signal run termination

        ai_action_suggestion = None
        all_detected_ui_elements = [] 
        if isinstance(ai_full_response, dict):
            ai_action_suggestion = ai_full_response.get("action_to_perform")
            all_detected_ui_elements = ai_full_response.get("all_ui_elements", []) # Default to empty list
        # elif ai_full_response: # Old format, if AI returns just the action
        #     ai_action_suggestion = ai_full_response 
        #     logging.warning("AI response format seems to be an action directly, not a dict. Assuming old format.")
        
        action_str_for_log_ai = utils.generate_action_description( # Generate from AI suggestion
            ai_action_suggestion.get('action','N/A') if ai_action_suggestion else 'N/A', 
            None, # Element description not usually in AI direct output
            ai_action_suggestion.get('input_text') if ai_action_suggestion else None, 
            ai_action_suggestion.get('target_identifier') if ai_action_suggestion else None
        )

        if not ai_action_suggestion or not isinstance(ai_action_suggestion, dict) or not ai_action_suggestion.get("action"):
            self._handle_ai_failure()
            failure_detail = "AI_NO_VALID_SUGGESTION"
            if not ai_action_suggestion: failure_detail = "AI_NO_SUGGESTION_RETURNED"
            elif not isinstance(ai_action_suggestion, dict): failure_detail = "AI_SUGGESTION_NOT_DICT"
            elif not ai_action_suggestion.get("action"): failure_detail = "AI_SUGGESTION_MISSING_ACTION_KEY"
            
            await self._handle_step_failure(current_step_for_log, current_screen_id_for_log, failure_detail, 
                                            action_str_for_log=action_str_for_log_ai, 
                                            ai_suggestion=ai_full_response if isinstance(ai_full_response, dict) else {"raw_response": str(ai_full_response)})
            step_outcome_status = "AI_FAIL"
            return current_screen_id_for_log, step_outcome_status, None
        
        self.consecutive_ai_failures = 0 # Reset on successful suggestion
        logging.info(f"Step {current_step_for_log}: AI suggested: {action_str_for_log_ai}. Reasoning: {ai_action_suggestion.get('reasoning', 'N/A')}")
        print(f"{UI_ACTION_PREFIX}{action_str_for_log_ai}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Mapping AI action...")

        # Annotate master screenshot with all detected UI elements from AI
        if current_state_repr.screenshot_path and all_detected_ui_elements and isinstance(all_detected_ui_elements, list):
            await self._run_sync_in_executor(self.default_executor, 
                self.screenshot_annotator.update_master_annotation_file,
                current_state_repr.screenshot_path, all_detected_ui_elements
            )

        # 5. Map AI Action to Appium Action
        action_details = await self._run_sync_in_executor(self.default_executor, 
            self.action_mapper.map_ai_action_to_appium,
            ai_action_suggestion, current_state_repr.xml_content # Pass full XML for mapping
        )

        if not action_details:
            self._handle_mapping_failure()
            await self._handle_step_failure(current_step_for_log, current_screen_id_for_log, "ACTION_MAPPING_FAILED", 
                                            ai_action_suggestion, action_str_for_log_ai)
            step_outcome_status = "MAP_FAIL"
            return current_screen_id_for_log, step_outcome_status, None
        
        self.consecutive_map_failures = 0 # Reset on successful mapping

        # 6. Annotate screenshot with the *chosen* action
        if current_state_repr.screenshot_bytes: # Bytes should exist if we got this far
            annotated_ss_path = await self._run_sync_in_executor(self.default_executor, 
                self.screenshot_annotator.save_annotated_screenshot,
                current_state_repr.screenshot_bytes,
                current_step_for_log, current_state_repr.id, ai_action_suggestion # Pass AI suggestion for context
            )
            if annotated_ss_path: 
                print(f"{UI_ANNOTATED_SCREENSHOT_PREFIX}{annotated_ss_path}")
                # Save path to ScreenRepresentation object if needed later, e.g. in DB for the step
                current_state_repr.annotated_screenshot_path = annotated_ss_path 


        # 7. Execute Action
        print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Executing action: {action_details.get('type', 'N/A')}...")
        execution_success = await self._run_sync_in_executor(self.default_executor, 
            self.action_executor.execute_action, action_details
        )
        # action_executor updates its own consecutive_exec_failures

        # 8. Determine Next State (Optional, for logging link) and Log Step
        next_state_screen_id_for_log = None
        if execution_success:
            step_outcome_status = "STEP_EXECUTED_SUCCESS"
            self.action_executor.reset_consecutive_failures() # Reset on success
            await asyncio.sleep(float(self.cfg.WAIT_AFTER_ACTION) / 2) # Brief wait before capturing next state
            
            # Try to get a representation of the screen *after* the action
            next_candidate_repr = await self._run_sync_in_executor(self.default_executor,
                self.screen_state_manager.get_current_screen_representation,
                self.run_id, current_step_for_log # Still same step, but this is "destination" screen
            )
            if next_candidate_repr:
                # Process this "next_screen" to get its definitive ID (either existing or new)
                # This is for logging the transition link; this screen will be fully processed in the *next* step.
                next_process_result = await self._run_sync_in_executor(self.db_executor, 
                     self.screen_state_manager.process_and_record_state, # This will add to cache if new
                     next_candidate_repr, self.run_id, current_step_for_log # step_number indicates when it was first seen due to this step
                )
                definitive_next_screen, _ = next_process_result
                next_state_screen_id_for_log = definitive_next_screen.id
        else: # Execution failed
            step_outcome_status = "EXEC_FAIL"
            # action_executor already incremented its failure count. _should_terminate will check.
            logging.error(f"Step {current_step_for_log}: Failed to execute action: {action_details.get('type', 'N/A')}. Reason: {self.action_executor.last_error_message}")
        
        # Generate descriptive string for the action that was actually attempted/executed
        self._last_action_description = utils.generate_action_description(
            action_details.get('type', 'N/A'),
            action_details.get('element_info', {}).get('desc', action_details.get('scroll_direction')), # Mapped element desc
            action_details.get('input_text', action_details.get('intended_input_text_for_coord_tap')), # Mapped input text
            ai_action_suggestion.get('target_identifier') # Original AI target for reference
        )

        # Log the completed step to the database
        await self._run_sync_in_executor(self.db_executor,
            self.db_manager.insert_step_log,
            self.run_id, current_step_for_log,
            current_screen_id_for_log, # from_screen_id
            next_state_screen_id_for_log if execution_success else None, # to_screen_id (None if exec failed)
            self._last_action_description, # Detailed description of action taken
            json.dumps(ai_action_suggestion), # Original AI suggestion
            json.dumps(action_details, default=lambda o: "<WebElement>" if isinstance(o, WebElement) else str(o)), # Mapped Appium action
            execution_success,
            None if execution_success else self.action_executor.last_error_message or "EXECUTION_FAILED_UNKNOWN" # Error message if failed
        )
        
        # Record action in ScreenStateManager's current run history (even if failed, to avoid retrying exact same thing)
        action_log_for_ssm = f"{self._last_action_description} (Success: {execution_success})"
        await self._run_sync_in_executor(self.default_executor, 
            self.screen_state_manager.record_action_taken_from_screen, 
            current_state_repr.composite_hash, action_log_for_ssm
        )

        if not execution_success:
            # step_outcome_status is already EXEC_FAIL. Caller (_should_terminate) will handle consecutive failure checks.
            return current_screen_id_for_log, step_outcome_status, None 

        logging.info(f"Step {current_step_for_log}: Action '{self._last_action_description}' executed successfully.")
        await asyncio.sleep(float(self.cfg.WAIT_AFTER_ACTION)) # Wait after successful action
        
        step_outcome_status = "STEP_COMPLETED_SUCCESSFULLY"
        return current_screen_id_for_log, step_outcome_status, None


    async def run_async(self):
        self._cleanup_called = False
        self.is_shutting_down = False 
        final_status_for_run = "STARTED_ERROR" # Default status if init fails early
        
        # Attempt to get event loop early, needed by _run_sync_in_executor
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError as e:
            logging.critical(f"Failed to get running event loop at start of run_async: {e}", exc_info=True)
            # Cannot proceed without an event loop for executors.
            # No UI_END_PREFIX here as it's a catastrophic setup failure.
            # perform_full_cleanup might not work if loop isn't available for its executor calls.
            # Try a direct, non-async cleanup if possible or just exit.
            self.is_shutting_down = True # Signal intent
            # Direct cleanup attempts (best effort without loop for executors)
            if self.driver: self.driver.disconnect()
            if self.db_manager: self.db_manager.close()
            return # Exit run_async

        # Start the shutdown flag monitor task
        self.monitor_task = asyncio.create_task(self._monitor_shutdown_flag())

        try:
            initialized, initial_status = await self._initialize_run()
            final_status_for_run = initial_status # Will be "RUNNING" or a failure status from init
            
            if not initialized:
                self.is_shutting_down = True # Signal shutdown due to init failure
                if not self._cleanup_called: # Check if UI_END already printed by a more specific error
                    print(f"{UI_END_PREFIX}{final_status_for_run}")
                # Cleanup will be handled in finally block
                return

            # Main crawl loop
            while not self._should_terminate(): # _should_terminate checks self.is_shutting_down and other conditions
                self.crawl_steps_taken += 1
                
                _current_screen_id, step_status_msg, step_term_reason_for_run = await self._perform_crawl_step(self.crawl_steps_taken)

                if step_term_reason_for_run: # If _perform_crawl_step itself decided to terminate the run
                    final_status_for_run = step_term_reason_for_run
                    logging.warning(f"Crawl step {self.crawl_steps_taken} indicated run termination: {step_term_reason_for_run}. Overriding loop logic.")
                    # _should_terminate would have set self.is_shutting_down and printed UI_END if applicable for this reason
                    break 
                
                # If step completed (successfully or with a recoverable failure), loop continues,
                # _should_terminate() will check failure counts, flags, limits at start of next iteration.
                logging.debug(f"Step {self.crawl_steps_taken} finished with status: {step_status_msg}. Loop continues.")

            # After the loop finishes (either by _should_terminate or break from step_term_reason_for_run)
            # Determine the final status message.
            # If final_status_for_run is still "RUNNING" or a step success message, it means loop exited due to _should_terminate().
            if final_status_for_run == "RUNNING" or "STEP_COMPLETED_SUCCESSFULLY" in final_status_for_run or "STEP_EXECUTED_SUCCESS" in final_status_for_run :
                # Re-evaluate reason based on current state, as _should_terminate() would have set flags/printed UI_END.
                flag_path = str(self.cfg.SHUTDOWN_FLAG_PATH)
                if os.path.exists(flag_path) and self.is_shutting_down: # is_shutting_down confirmed by flag
                    final_status_for_run = "GRACEFUL_SHUTDOWN_FLAG"
                elif self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS:
                     final_status_for_run = "COMPLETED_MAX_STEPS"
                elif self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS:
                    final_status_for_run = "COMPLETED_MAX_DURATION"
                elif self.consecutive_ai_failures >= self.cfg.MAX_CONSECUTIVE_AI_FAILURES: final_status_for_run = "TERMINATED_MAX_AI_FAIL"
                elif self.consecutive_map_failures >= self.cfg.MAX_CONSECUTIVE_MAP_FAILURES: final_status_for_run = "TERMINATED_MAX_MAP_FAIL"
                elif self.action_executor.consecutive_exec_failures >= self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES: final_status_for_run = "TERMINATED_MAX_EXEC_FAIL"
                elif self.app_context_manager.consecutive_context_failures >= self.cfg.MAX_CONSECUTIVE_CONTEXT_FAILURES: final_status_for_run = "TERMINATED_MAX_CONTEXT_FAIL"
                elif self.is_shutting_down : # General shutdown state not caught by specific conditions above
                    final_status_for_run = "TERMINATED_BY_CONDITION" # E.g. monitor set flag, loop ended.
                else: # Natural end of loop if no other condition explicitly met (should be rare)
                    final_status_for_run = "COMPLETED_NORMALLY" 
                    if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}") # Should not happen if loop condition is robust

            logging.info(f"Crawl loop finished. Deduced final status for DB: {final_status_for_run}")

        except WebDriverException as e:
            logging.critical(f"WebDriverException in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_WEBDRIVER_EXCEPTION"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True # Ensure shutdown state
        except RuntimeError as e: # Catch other RuntimeErrors, e.g., from asyncio or critical logic
            logging.critical(f"RuntimeError in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_RUNTIME_ERROR"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True 
        except KeyboardInterrupt: # User interruption
            logging.warning("KeyboardInterrupt received in run_async. Initiating shutdown...")
            final_status_for_run = "INTERRUPTED_KEYBOARD"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}")
            self.is_shutting_down = True 
        except Exception as e: # Catch-all for any other unhandled exceptions
            logging.critical(f"Unhandled exception in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_UNHANDLED_EXCEPTION"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True 
        finally:
            logging.info(f"Exited crawl logic. Final run status before cleanup: {final_status_for_run}")
            
            # Ensure monitor task is properly handled
            if self.monitor_task:
                if not self.monitor_task.done():
                    self.monitor_task.cancel() # Request cancellation
                try:
                    await self.monitor_task # Wait for it to finish (either by cancellation or natural exit)
                except asyncio.CancelledError:
                    logging.info("Monitor task was cancelled during run_async finally.")
                except Exception as e_mon: # Catch any error from awaiting the task
                    logging.error(f"Error awaiting monitor task in run_async finally: {e_mon}")
            self.monitor_task = None # Clear the task reference
            
            self.is_shutting_down = True # Explicitly ensure shutdown state for cleanup

            # Log final status to console before DB update
            print(f"{UI_STATUS_PREFIX}Crawl finalized. Run {self.run_id if self.run_id else 'N/A'} processing end with status code: {final_status_for_run}...")

            # Update run status in DB if run_id was obtained
            if self.run_id is not None and self.db_manager is not None: 
                current_time_str = await self._run_sync_in_executor(self.default_executor, time.strftime, "%Y-%m-%d %H:%M:%S")
                await self._run_sync_in_executor(self.db_executor, 
                    self.db_manager.update_run_status, self.run_id, final_status_for_run, current_time_str
                )
            
            # Perform full cleanup
            await self.perform_full_cleanup() 
            logging.info(f"AppCrawler run_async finished for Run ID: {self.run_id if self.run_id else 'N/A'}. Final DB status recorded: {final_status_for_run}")


    def run(self):
        try:
            logging.info(f"AppCrawler run initiated for {self.cfg.APP_PACKAGE}.")
            # asyncio.run will create a new event loop or use the existing one if compatible.
            asyncio.run(self.run_async()) 
            logging.info(f"AppCrawler run completed for {self.cfg.APP_PACKAGE}.")
        except SystemExit as se: 
            # This might be raised by sys.exit() in main_cli if config fails early
            logging.info(f"SystemExit caught by AppCrawler.run() wrapper: {se.code}")
            raise # Re-raise to allow process to exit with the code
        except KeyboardInterrupt: 
            # run_async's finally block should handle cleanup for KeyboardInterrupt during async operations.
            # This is a fallback if KI happens directly in the sync `run` part, which is unlikely.
            logging.warning("KeyboardInterrupt caught by AppCrawler.run() synchronous wrapper. Cleanup primarily handled by async part.")
        except Exception as e: # Catch any other unexpected errors in the sync wrapper
            logging.critical(f"Unhandled critical error in AppCrawler.run() synchronous wrapper: {e}", exc_info=True)
            # Emergency cleanup if async cleanup didn't run or was bypassed
            if not self._cleanup_called and hasattr(self, 'perform_full_cleanup'):
                logging.warning("Attempting emergency cleanup from AppCrawler.run() sync wrapper.")
                try:
                    # Try to run async cleanup if an event loop can be made
                    asyncio.run(self.perform_full_cleanup())
                except RuntimeError as re_err: 
                    logging.error(f"RuntimeError during emergency cleanup from sync wrapper: {re_err}. This might indicate an issue with event loop management or prior crash.", exc_info=True)
                    # Fallback to simpler direct cleanup if async fails
                    if hasattr(self, 'driver') and self.driver: self.driver.disconnect() # Direct sync call
                    if hasattr(self, 'db_manager') and self.db_manager: self.db_manager.close() # Direct sync call
                except Exception as e_clean:
                     logging.error(f"Exception during emergency async cleanup from sync wrapper: {e_clean}", exc_info=True)
        finally:
            # Shutdown thread pool executors here, as they are managed by AppCrawler instance
            if hasattr(self, 'db_executor') and self.db_executor:
                logging.info("AppCrawler.run finally: Shutting down DB executor...")
                self.db_executor.shutdown(wait=True)
                # self.db_executor = None # Not strictly needed if instance is ending
            if hasattr(self, 'default_executor') and self.default_executor:
                logging.info("AppCrawler.run finally: Shutting down default executor...")
                self.default_executor.shutdown(wait=True)
                # self.default_executor = None
            logging.info("AppCrawler.run() synchronous wrapper finished, executors shut down.")