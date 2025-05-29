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
            if not hasattr(self.cfg, attr) or getattr(self.cfg, attr) is None:
                if attr == 'ALLOWED_EXTERNAL_PACKAGES' and isinstance(getattr(self.cfg, attr, None), list): continue
                if attr == 'AI_SAFETY_SETTINGS' and isinstance(getattr(self.cfg, attr, None), dict): continue
                raise ValueError(f"AppCrawler: Critical configuration '{attr}' is missing or None.")

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
                if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
                    try:
                        with open(self.cfg.SHUTDOWN_FLAG_PATH, 'r') as f:
                            content = f.read().lower()
                            if 'stop' in content:
                                logging.info("Shutdown flag detected by monitoring task. Setting self.is_shutting_down = True.")
                                if not self.is_shutting_down:
                                    print(f"{UI_END_PREFIX}GRACEFUL_SHUTDOWN_REQUESTED_BY_MONITOR")
                                self.is_shutting_down = True
                                return 
                    except Exception as e:
                        logging.warning(f"Error reading shutdown flag in monitoring task: {e}")
                
                if self.is_shutting_down:
                    logging.debug("Shutdown monitor sees self.is_shutting_down is true, exiting.")
                    return
                
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logging.info("Shutdown monitor task cancelled.")
        except Exception as e:
            logging.error(f"Exception in shutdown monitor task: {e}", exc_info=True)
        finally:
            logging.debug("Shutdown monitor task finished.")

    def _should_terminate(self) -> bool:
        if self.is_shutting_down:
            logging.info("Termination check: Shutdown already initiated (self.is_shutting_down is True).")
            return True

        if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH): 
            try:
                with open(self.cfg.SHUTDOWN_FLAG_PATH, 'r') as f: 
                    if 'stop' in f.read().lower(): 
                        logging.info("Termination check (_should_terminate direct): External shutdown flag detected.")
                        if not self.is_shutting_down:
                            print(f"{UI_END_PREFIX}GRACEFUL_SHUTDOWN_REQUESTED_BY_DIRECT_CHECK") 
                        self.is_shutting_down = True 
                        return True
            except Exception as e:
                logging.warning(f"Error reading shutdown flag file in _should_terminate: {e}")

        if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS: 
            logging.info(f"Termination check: Reached max steps ({self.cfg.MAX_CRAWL_STEPS}).")
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_STEPS_REACHED") 
            self.is_shutting_down = True
            return True

        if self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS: 
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
        if not self.loop:
            logging.critical(f"Event loop not initialized in AppCrawler for {func.__name__}. Trying to get current loop.")
            try:
                current_event_loop = asyncio.get_running_loop()
            except RuntimeError:
                logging.critical(f"No running event loop available to execute {func.__name__}. This is a critical error.")
                raise 
            return await current_event_loop.run_in_executor(executor, func, *args)
        return await self.loop.run_in_executor(executor, func, *args)

    async def _setup_ai_output_csv(self):
        if not self.cfg.OUTPUT_DATA_DIR or not self.cfg.APP_PACKAGE:
            logging.error("Cannot setup AI output CSV: OUTPUT_DATA_DIR or APP_PACKAGE not configured.")
            return

        ai_output_dir = os.path.join(self.cfg.OUTPUT_DATA_DIR, "ai_outputs_csv")
        try:
            # Use executor for os.makedirs as it's file I/O
            await self._run_sync_in_executor(self.default_executor, os.makedirs, ai_output_dir, True) # exist_ok=True
            self.ai_output_csv_path = os.path.join(ai_output_dir, f"{self.cfg.APP_PACKAGE}_ai_interactions.csv")
            logging.info(f"AI interaction logs will be saved to: {self.ai_output_csv_path}")

            def check_and_write_header():
                if not os.path.exists(self.ai_output_csv_path) or os.path.getsize(self.ai_output_csv_path) == 0: # type: ignore
                    with open(self.ai_output_csv_path, 'w', newline='', encoding='utf-8') as f: # type: ignore
                        writer = csv.writer(f)
                        writer.writerow(self.ai_output_csv_headers)
                    self._ai_csv_header_written = True
                else:
                    self._ai_csv_header_written = True # Assume header exists
            
            await self._run_sync_in_executor(self.default_executor, check_and_write_header)

        except IOError as e:
            logging.error(f"Failed to initialize or write AI CSV header to {self.ai_output_csv_path}: {e}")
            self.ai_output_csv_path = None 
        except Exception as e:
            logging.error(f"Unexpected error setting up AI CSV log: {e}", exc_info=True)
            self.ai_output_csv_path = None


    async def _log_ai_output_to_csv(self, run_id, step, screen_id, screen_hash, ai_response_dict):
        if not self.ai_output_csv_path:
            return

        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        action_to_perform = {}
        all_ui_elements_count = 0
        raw_json_str = "{}"

        if isinstance(ai_response_dict, dict):
            action_to_perform = ai_response_dict.get("action_to_perform", {})
            all_ui_elements = ai_response_dict.get("all_ui_elements", [])
            all_ui_elements_count = len(all_ui_elements) if isinstance(all_ui_elements, list) else 0
            try:
                raw_json_str = json.dumps(ai_response_dict)
            except TypeError: 
                raw_json_str = json.dumps({"error": "failed to serialize full AI response"})
        elif ai_response_dict is not None :
             raw_json_str = json.dumps({"raw_response": str(ai_response_dict)})

        row_data = {
            "timestamp": timestamp,
            "run_id": run_id if run_id is not None else "",
            "step_number": step,
            "screen_id": screen_id if screen_id is not None else "",
            "screen_composite_hash": screen_hash if screen_hash is not None else "",
            "ai_action_type": action_to_perform.get("action"),
            "ai_target_identifier": action_to_perform.get("target_identifier"),
            "ai_input_text": action_to_perform.get("input_text"),
            "ai_reasoning": action_to_perform.get("reasoning"),
            "all_ui_elements_count": all_ui_elements_count,
            "raw_ai_response_json": raw_json_str
        }
        
        def write_csv_row_sync():
            try:
                file_exists_and_not_empty = os.path.exists(self.ai_output_csv_path) and os.path.getsize(self.ai_output_csv_path) > 0 # type: ignore
                
                with open(self.ai_output_csv_path, 'a', newline='', encoding='utf-8') as f: # type: ignore
                    writer = csv.DictWriter(f, fieldnames=self.ai_output_csv_headers)
                    if not file_exists_and_not_empty and not self._ai_csv_header_written:
                        # This condition should ideally be met only once if _setup_ai_output_csv worked.
                        # If multiple AppCrawler instances run for the same app package *simultaneously* (not typical for this script)
                        # this could lead to multiple headers or race conditions.
                        # For sequential runs or single instance, it's fine.
                        writer.writeheader()
                        self._ai_csv_header_written = True # Mark it as written for this session
                    writer.writerow(row_data)
            except IOError as e:
                logging.error(f"Failed to write AI output to CSV {self.ai_output_csv_path}: {e}")
            except Exception as e_csv:
                logging.error(f"Unexpected error writing AI CSV row: {e_csv}", exc_info=True)

        await self._run_sync_in_executor(self.default_executor, write_csv_row_sync)


    async def perform_full_cleanup(self):
        if self.is_shutting_down and self._cleanup_called:
            logging.debug("Cleanup already called.")
            return
        logging.info("Performing full cleanup for AppCrawler...")
        self.is_shutting_down = True 
        self._cleanup_called = True
        
        if self.cfg.ENABLE_TRAFFIC_CAPTURE and self.traffic_capture_manager and self.traffic_capture_manager.is_capturing():
            logging.info("Ensuring traffic capture stopped and pulled...")
            try:
                await self.traffic_capture_manager.stop_capture_and_pull_async(
                    run_id=self.run_id or 0, step_num=self.crawl_steps_taken)
            except Exception as e_traffic:
                logging.error(f"Error during traffic capture finalization in cleanup: {e_traffic}", exc_info=True)

        if self.driver:
            try:
                logging.info("Quitting Appium driver session...")
                await self._run_sync_in_executor(self.default_executor, self.driver.disconnect)
            except Exception as e_driver:
                logging.error(f"Error during Appium driver quit: {e_driver}", exc_info=True)
            finally:
                self.driver = None 
        
        if self.db_manager: 
            try:
                logging.info("Closing database connection via DB executor...")
                await self._run_sync_in_executor(self.db_executor, self.db_manager.close)
            except Exception as e_db_close:
                logging.error(f"Error closing database via DB executor: {e_db_close}", exc_info=True)
            # self.db_manager instance is kept, its internal connection is closed by db_manager.close()
            
        if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            try:
                await self._run_sync_in_executor(self.default_executor, os.remove, self.cfg.SHUTDOWN_FLAG_PATH)
                logging.info(f"Cleaned up shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH}")
            except OSError as e_flag:
                logging.warning(f"Could not remove shutdown flag: {e_flag}")
            
        logging.info("AppCrawler partial cleanup process finished (executors shutdown in main run() method).")

    async def _initialize_run(self) -> Tuple[bool, str]:
        if not self.db_manager:
            logging.critical("DatabaseManager (self.db_manager) is not initialized.")
            return False, "FAILURE_DB_NOT_INIT"
        if not self.driver:
            logging.critical("AppiumDriver (self.driver) is not initialized.")
            return False, "FAILURE_DRIVER_NOT_INIT"

        await self._setup_ai_output_csv()

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
        
        await self._run_sync_in_executor(self.db_executor, 
            self.screen_state_manager.initialize_for_run,
            self.run_id, str(self.cfg.APP_PACKAGE),
            str(self.cfg.APP_ACTIVITY), is_continuation_run
        )
        self.crawl_steps_taken = self.screen_state_manager.current_run_latest_step_number
        logging.info(f"Run type: {'Continuation' if is_continuation_run else 'New'}. Initial steps: {self.crawl_steps_taken}.")
        self.crawl_start_time = time.time()

        driver_connected = await self._run_sync_in_executor(self.default_executor, self.driver.connect)
        if not driver_connected:
            logging.critical("Failed to connect to Appium.")
            return False, "FAILED_APPIUM_CONNECT"
        
        app_launched = await self._run_sync_in_executor(self.default_executor, 
            self.app_context_manager.launch_and_verify_app
        )
        if not app_launched:
            logging.critical("Failed to launch/verify target app.")
            return False, "FAILED_APP_LAUNCH"

        if self.cfg.ENABLE_TRAFFIC_CAPTURE:
            pcap_filename_template = f"{self.cfg.APP_PACKAGE}_run{self.run_id}_step{{step_num}}.pcap"
            capture_started = await self.traffic_capture_manager.start_capture_async(filename_template=pcap_filename_template)
            if not capture_started:
                logging.warning("Failed to start traffic capture.")
            else:
                logging.info("Traffic capture started.")
        
        return True, "RUNNING"

    async def _handle_step_failure(self, step_num: int, from_screen_id: Optional[int], reason: str, 
                                   ai_suggestion: Optional[Dict[str, Any]] = None, 
                                   action_str_for_log: Optional[str] = None) -> str:
        logging.error(f"Step {step_num}: {reason}")
        final_status = f"TERMINATED_{reason.upper().replace(' ', '_')}"
        
        if self.db_manager and self.run_id: # run_id could be None if _initialize_run failed
            await self._run_sync_in_executor(self.db_executor,
                self.db_manager.insert_step_log,
                self.run_id, step_num,
                from_screen_id, None, 
                action_str_for_log or reason, 
                json.dumps(ai_suggestion) if ai_suggestion else None,
                None, False, reason
            )
        if self.screen_state_manager and self.previous_composite_hash:
             await self._run_sync_in_executor(self.default_executor, 
                self.screen_state_manager.record_action_taken_from_screen, 
                self.previous_composite_hash, f"{action_str_for_log or reason} (failed)"
            )
        return final_status


    async def _perform_crawl_step(self, current_step_for_log: int) -> Tuple[Optional[int], str, Optional[str]]:
        logging.info(f"--- Crawl Step {current_step_for_log} (Run ID: {self.run_id}) ---")
        print(f"{UI_STEP_PREFIX}{current_step_for_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Checking app context...")
        
        current_screen_id_for_log: Optional[int] = None 

        in_app = await self._run_sync_in_executor(self.default_executor, self.app_context_manager.ensure_in_app)
        if not in_app:
            last_known_screen_id = None
            if self.previous_composite_hash and self.db_manager:
                screen_data = await self._run_sync_in_executor(self.db_executor, self.db_manager.get_screen_by_composite_hash, self.previous_composite_hash)
                if screen_data: last_known_screen_id = screen_data[0]
            failure_reason = await self._handle_step_failure(current_step_for_log, last_known_screen_id , "CONTEXT_ENSURE_FAIL")
            return last_known_screen_id, failure_reason, "TERMINATED_CONTEXT_FAIL"
        
        print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Getting screen state...")
        candidate_screen_repr = await self._run_sync_in_executor(self.default_executor,
            self.screen_state_manager.get_current_screen_representation,
            self.run_id, current_step_for_log
        )
        if not candidate_screen_repr or not candidate_screen_repr.screenshot_bytes:
            self._handle_mapping_failure() 
            failure_reason = await self._handle_step_failure(current_step_for_log, None , "STATE_GET_FAIL")
            return None, failure_reason, "TERMINATED_STATE_FAIL"

        process_result = await self._run_sync_in_executor(self.db_executor, 
            self.screen_state_manager.process_and_record_state, # Uses DB
            candidate_screen_repr, self.run_id, current_step_for_log
        )
        current_state_repr, visit_info = process_result
        current_screen_id_for_log = current_state_repr.id 

        if current_state_repr.screenshot_path:
            print(f"{UI_SCREENSHOT_PREFIX}{current_state_repr.screenshot_path}")
        else:
            logging.warning(f"Step {current_step_for_log}: Screenshot path is missing for screen ID {current_state_repr.id}.")

        logging.info(f"Step {current_step_for_log}: State Processed. Screen ID: {current_screen_id_for_log}, Hash: '{current_state_repr.composite_hash}', Activity: '{current_state_repr.activity_name}'")
        self.previous_composite_hash = current_state_repr.composite_hash 

        print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Requesting AI action...")
        simplified_xml_context = current_state_repr.xml_content or ""
        if self.cfg.ENABLE_XML_CONTEXT and current_state_repr.xml_content:
            simplified_xml_context = await self._run_sync_in_executor(self.default_executor, 
                utils.simplify_xml_for_ai, current_state_repr.xml_content, int(self.cfg.XML_SNIPPET_MAX_LEN)
            )
        
        if current_state_repr.screenshot_bytes is None:
            self._handle_ai_failure()
            failure_reason = await self._handle_step_failure(current_step_for_log, current_screen_id_for_log, "AI_FAIL_NO_SS")
            # Log AI output as failure to CSV
            if self.run_id is not None and current_screen_id_for_log is not None :
                await self._log_ai_output_to_csv(self.run_id, current_step_for_log, current_screen_id_for_log, 
                                         current_state_repr.composite_hash, {"error": "Screenshot bytes were None for AI input"})
            return current_screen_id_for_log, failure_reason, "TERMINATED_AI_FAIL_NO_SS"

        ai_full_response = await self._run_sync_in_executor(self.default_executor, 
            self.ai_assistant.get_next_action,
            current_state_repr.screenshot_bytes,
            simplified_xml_context,
            visit_info.get("previous_actions_on_this_state", []),
            visit_info.get("visit_count_this_run", 1),
            current_state_repr.composite_hash
        )
        
        if self.run_id is not None and current_screen_id_for_log is not None and current_state_repr.composite_hash is not None:
             await self._log_ai_output_to_csv(self.run_id, current_step_for_log, current_screen_id_for_log, 
                                     current_state_repr.composite_hash, ai_full_response)

        if self._should_terminate(): return current_screen_id_for_log, "TERMINATED_DURING_AI_PROCESSING", "TERMINATED_DURING_AI"

        ai_action_suggestion = None
        all_detected_ui_elements = [] 
        if isinstance(ai_full_response, dict):
            ai_action_suggestion = ai_full_response.get("action_to_perform")
            all_detected_ui_elements = ai_full_response.get("all_ui_elements", [])
        elif ai_full_response: 
            ai_action_suggestion = ai_full_response 
            logging.warning("AI response format is old. Proceeding with action only.")

        action_str_log = utils.generate_action_description(
            ai_action_suggestion.get('action','N/A') if ai_action_suggestion else 'N/A', None, 
            ai_action_suggestion.get('input_text') if ai_action_suggestion else None, 
            ai_action_suggestion.get('target_identifier') if ai_action_suggestion else None
        )

        if not ai_action_suggestion:
            self._handle_ai_failure()
            failure_reason = await self._handle_step_failure(current_step_for_log, current_screen_id_for_log, "AI_NO_SUGGESTION", action_str_for_log=action_str_log, ai_suggestion=ai_full_response if isinstance(ai_full_response, dict) else {"raw_response": str(ai_full_response)})
            return current_screen_id_for_log, failure_reason, "TERMINATED_AI_FAIL"
        
        self.consecutive_ai_failures = 0
        logging.info(f"Step {current_step_for_log}: AI suggested: {action_str_log}. Reasoning: {ai_action_suggestion.get('reasoning')}")
        print(f"{UI_ACTION_PREFIX}{action_str_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Mapping AI action...")

        if current_state_repr.screenshot_path and all_detected_ui_elements:
            await self._run_sync_in_executor(self.default_executor, 
                self.screenshot_annotator.update_master_annotation_file,
                current_state_repr.screenshot_path, all_detected_ui_elements
            )

        action_details = await self._run_sync_in_executor(self.default_executor, 
            self.action_mapper.map_ai_action_to_appium,
            ai_action_suggestion, current_state_repr.xml_content
        )

        if not action_details:
            self._handle_mapping_failure()
            failure_reason = await self._handle_step_failure(current_step_for_log, current_screen_id_for_log, "ACTION_MAPPING_FAILED", ai_action_suggestion, action_str_log)
            return current_screen_id_for_log, failure_reason, "TERMINATED_MAP_FAIL"
        
        self.consecutive_map_failures = 0

        if current_state_repr.screenshot_bytes:
            annotated_ss_path = await self._run_sync_in_executor(self.default_executor, 
                self.screenshot_annotator.save_annotated_screenshot,
                current_state_repr.screenshot_bytes,
                current_step_for_log, current_state_repr.id, ai_action_suggestion
            )
            if annotated_ss_path: print(f"{UI_ANNOTATED_SCREENSHOT_PREFIX}{annotated_ss_path}")

        print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Executing action: {action_details.get('type')}...")
        execution_success = await self._run_sync_in_executor(self.default_executor, 
            self.action_executor.execute_action, action_details
        )

        next_state_screen_id_for_log = None
        if execution_success:
            await asyncio.sleep(float(self.cfg.WAIT_AFTER_ACTION) / 2) 
            next_candidate_repr = await self._run_sync_in_executor(self.default_executor,
                self.screen_state_manager.get_current_screen_representation,
                self.run_id, current_step_for_log 
            )
            if next_candidate_repr:
                next_process_result = await self._run_sync_in_executor(self.db_executor, 
                     self.screen_state_manager.process_and_record_state,
                     next_candidate_repr, self.run_id, current_step_for_log 
                )
                definitive_next_screen, _ = next_process_result
                next_state_screen_id_for_log = definitive_next_screen.id
        
        self._last_action_description = utils.generate_action_description(
            action_details.get('type', 'N/A'),
            action_details.get('element_info', {}).get('desc', action_details.get('scroll_direction')),
            action_details.get('input_text', action_details.get('intended_input_text_for_coord_tap')),
            ai_action_suggestion.get('target_identifier') 
        )

        await self._run_sync_in_executor(self.db_executor,
            self.db_manager.insert_step_log,
            self.run_id, current_step_for_log,
            current_screen_id_for_log, next_state_screen_id_for_log,
            self._last_action_description,
            json.dumps(ai_action_suggestion), 
            json.dumps(action_details, default=lambda o: "<WebElement>" if isinstance(o, WebElement) else str(o)),
            execution_success,
            None if execution_success else self.action_executor.last_error_message or "EXECUTION_FAILED"
        )
        await self._run_sync_in_executor(self.default_executor, 
            self.screen_state_manager.record_action_taken_from_screen, 
            current_state_repr.composite_hash, f"{self._last_action_description} (Success: {execution_success})"
        )

        if not execution_success:
            logging.error(f"Step {current_step_for_log}: Failed to execute action: {action_details.get('type')}")
            return current_screen_id_for_log, "TERMINATED_EXEC_FAIL_IN_STEP", "TERMINATED_EXEC_FAIL"
        
        logging.info(f"Step {current_step_for_log}: Action executed successfully.")
        await asyncio.sleep(float(self.cfg.WAIT_AFTER_ACTION)) 
        return current_screen_id_for_log, "STEP_SUCCESSFUL", None


    async def run_async(self):
        self._cleanup_called = False
        self.is_shutting_down = False 
        final_status_for_run = "STARTED_ERROR"
        self.loop = asyncio.get_running_loop()

        self.monitor_task = asyncio.create_task(self._monitor_shutdown_flag())

        try:
            initialized, initial_status = await self._initialize_run()
            final_status_for_run = initial_status
            if not initialized:
                self.is_shutting_down = True 
                if not self.is_shutting_down: # Check if already shutting down to avoid double print
                    print(f"{UI_END_PREFIX}{final_status_for_run}")
                return

            while not self._should_terminate():
                self.crawl_steps_taken += 1
                
                _current_screen_id, _step_status_msg, step_term_reason = await self._perform_crawl_step(self.crawl_steps_taken)

                if step_term_reason:
                    final_status_for_run = step_term_reason
                    logging.warning(f"Crawl step {self.crawl_steps_taken} indicated termination: {step_term_reason}")
                    break 

                if self._should_terminate(): 
                    # Determine current reason for termination, _should_terminate already prints UI_END_PREFIX
                    if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
                         final_status_for_run = "GRACEFUL_SHUTDOWN_FLAG"
                    elif self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS: final_status_for_run = "COMPLETED_MAX_STEPS"
                    elif self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS: final_status_for_run = "COMPLETED_MAX_DURATION"
                    elif self.consecutive_ai_failures >= self.cfg.MAX_CONSECUTIVE_AI_FAILURES: final_status_for_run = "TERMINATED_MAX_AI_FAIL"
                    elif self.consecutive_map_failures >= self.cfg.MAX_CONSECUTIVE_MAP_FAILURES: final_status_for_run = "TERMINATED_MAX_MAP_FAIL"
                    elif self.action_executor.consecutive_exec_failures >= self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES: final_status_for_run = "TERMINATED_MAX_EXEC_FAIL"
                    elif self.app_context_manager.consecutive_context_failures >= self.cfg.MAX_CONSECUTIVE_CONTEXT_FAILURES: final_status_for_run = "TERMINATED_MAX_CONTEXT_FAIL"
                    else: final_status_for_run = "TERMINATED_BY_CONDITION_LOOP_END" 
                    logging.info(f"Termination condition met after step {self.crawl_steps_taken}. Status: {final_status_for_run}")
                    break
            
            # If loop finished without break, or broke due to _should_terminate setting a status.
            # If final_status_for_run is still "RUNNING" or "STEP_SUCCESSFUL", it means loop ended by condition not error.
            if final_status_for_run == "RUNNING" or final_status_for_run == "STEP_SUCCESSFUL": 
                if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS:
                     final_status_for_run = "COMPLETED_MAX_STEPS" # _should_terminate would have printed UI_END
                elif self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS: 
                    final_status_for_run = "COMPLETED_MAX_DURATION" # _should_terminate would have printed UI_END
                else: # Loop finished, but not due to max steps/duration specifically, e.g. _should_terminate became true for other reasons
                    final_status_for_run = "COMPLETED_NORMALLY" 
                    # If _should_terminate set self.is_shutting_down due to flag, it would have printed.
                    # If it's a natural completion not caught by specific UI_END prints above, this is a fallback.
                    if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}")


            logging.info(f"Crawl loop finished. Final status for DB: {final_status_for_run}")

        except WebDriverException as e:
            logging.critical(f"WebDriverException in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_WEBDRIVER_EXCEPTION"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True
        except RuntimeError as e: 
            logging.critical(f"RuntimeError in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_RUNTIME_ERROR"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True 
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt received in run_async. Initiating shutdown...")
            final_status_for_run = "INTERRUPTED_KEYBOARD"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}")
            self.is_shutting_down = True 
        except Exception as e: 
            logging.critical(f"Unhandled exception in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_UNHANDLED_EXCEPTION"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True 
        finally:
            logging.info(f"Exited crawl logic. Final run status before cleanup: {final_status_for_run}")
            
            if self.monitor_task:
                if not self.monitor_task.done():
                    self.monitor_task.cancel()
                try:
                    await self.monitor_task 
                except asyncio.CancelledError:
                    logging.info("Monitor task was cancelled during run_async finally.")
                except Exception as e_mon:
                    logging.error(f"Error awaiting monitor task in run_async finally: {e_mon}")
            self.monitor_task = None 
            
            self.is_shutting_down = True # Ensure cleanup knows it's shutting down

            print(f"{UI_STATUS_PREFIX}Crawl finalized. Run {self.run_id} status {final_status_for_run}...")

            if self.run_id is not None and self.db_manager is not None: 
                await self._run_sync_in_executor(self.db_executor, 
                    self.db_manager.update_run_status, self.run_id, final_status_for_run, time.strftime("%Y-%m-%d %H:%M:%S")
                )
            await self.perform_full_cleanup() 
            logging.info(f"AppCrawler run_async finished for Run ID: {self.run_id}. Final DB status recorded: {final_status_for_run}")


    def run(self):
        try:
            logging.info(f"AppCrawler run initiated for {self.cfg.APP_PACKAGE}.")
            asyncio.run(self.run_async()) 
            logging.info(f"AppCrawler run completed for {self.cfg.APP_PACKAGE}.")
        except SystemExit as se: 
            logging.info(f"SystemExit caught by AppCrawler.run() wrapper: {se.code}")
            raise 
        except KeyboardInterrupt: 
            logging.warning("KeyboardInterrupt caught by AppCrawler.run() wrapper. Cleanup should have been handled by run_async.")
        except Exception as e:
            logging.critical(f"Unhandled critical error in AppCrawler.run() wrapper: {e}", exc_info=True)
            if not (hasattr(self, '_cleanup_called') and self._cleanup_called) and hasattr(self, 'perform_full_cleanup'):
                logging.warning("Attempting emergency cleanup from AppCrawler.run() wrapper.")
                try:
                    asyncio.run(self.perform_full_cleanup())
                except RuntimeError as re_err: 
                    logging.error(f"RuntimeError during emergency cleanup: {re_err}. This might indicate an issue with event loop management.", exc_info=True)
                except Exception as e_clean:
                     logging.error(f"Exception during emergency cleanup: {e_clean}", exc_info=True)
        finally:
            if hasattr(self, 'db_executor') and self.db_executor:
                logging.info("AppCrawler.run finally: Shutting down DB executor...")
                self.db_executor.shutdown(wait=True)
                self.db_executor = None
            if hasattr(self, 'default_executor') and self.default_executor:
                logging.info("AppCrawler.run finally: Shutting down default executor...")
                self.default_executor.shutdown(wait=True)
                self.default_executor = None
            logging.info("AppCrawler.run() synchronous wrapper finished.")