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

    def _should_terminate(self) -> bool:
        # Direct check for self.is_shutting_down (set by monitor or other conditions)
        if self.is_shutting_down:
            logging.info("Termination check: Shutdown already initiated.")
            return True
        if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            logging.info(f"Termination check: External shutdown flag found: {self.cfg.SHUTDOWN_FLAG_PATH}.")
            self.is_shutting_down = True
            print(f"{UI_END_PREFIX}SHUTDOWN_FLAG_DETECTED")
            return True
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

    def perform_full_cleanup(self):
        if self.is_shutting_down and hasattr(self, '_cleanup_called') and self._cleanup_called:
            logging.debug("Cleanup already called.")
            return
        
        logging.info("Performing full cleanup for AppCrawler...")
        self.is_shutting_down = True
        self._cleanup_called = True
        
        if self.cfg.ENABLE_TRAFFIC_CAPTURE and self.traffic_capture_manager and self.traffic_capture_manager.is_capturing():
            logging.info("Ensuring traffic capture stopped and pulled...")
            try:
                loop_exists = False
                try:
                    loop = asyncio.get_running_loop()
                    loop_exists = loop.is_running()
                except RuntimeError: # No running loop
                    loop_exists = False

                if loop_exists:
                    asyncio.ensure_future(self.traffic_capture_manager.stop_capture_and_pull_async(
                        run_id=self.run_id or 0, step_num=self.crawl_steps_taken))
                else:
                    asyncio.run(self.traffic_capture_manager.stop_capture_and_pull_async(
                        run_id=self.run_id or 0, step_num=self.crawl_steps_taken))
            except Exception as e_traffic:
                logging.error(f"Error during traffic capture finalization in cleanup: {e_traffic}", exc_info=True)

        if self.driver: # Check if driver object exists
            try:
                logging.info("Quitting Appium driver session...")
                self.driver.disconnect()
            except Exception as e_driver:
                logging.error(f"Error during Appium driver quit: {e_driver}", exc_info=True)
            finally:
                self.driver = None
        if self.db_manager:
            try:
                logging.info("Closing database connection...")
                self.db_manager.close()
            except Exception as e_db:
                logging.error(f"Error closing database: {e_db}", exc_info=True)
            finally:
                self.db_manager = None
        if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            try:
                os.remove(self.cfg.SHUTDOWN_FLAG_PATH)
                logging.info(f"Cleaned up shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH}")
            except OSError as e_flag:
                logging.warning(f"Could not remove shutdown flag: {e_flag}")
        # self.db_manager might be None here if an early exception occurred
        if self.run_id is not None and hasattr(self, 'db_manager') and self.db_manager is not None :
            current_status_for_db = "COMPLETED_CLEANUP"
            # Check if termination was due to a failure condition caught by _should_terminate
            # This logic might need refinement based on how final_status_for_run is set before cleanup
            if self.consecutive_ai_failures >= self.cfg.MAX_CONSECUTIVE_AI_FAILURES: current_status_for_db = "TERMINATED_MAX_AI_FAIL_CLEANUP"
            elif self.consecutive_map_failures >= self.cfg.MAX_CONSECUTIVE_MAP_FAILURES: current_status_for_db = "TERMINATED_MAX_MAP_FAIL_CLEANUP"
            # Add other failure checks if needed
            
            self.db_manager.update_run_status(self.run_id, current_status_for_db, time.strftime("%Y-%m-%d %H:%M:%S"))

        logging.info("AppCrawler full cleanup process finished.")


    async def run_async(self):
        self._cleanup_called = False
        final_status_for_run = "STARTED_ERROR"

        try:
            if not self.db_manager:
                logging.critical("DatabaseManager not available.")
                print(f"{UI_END_PREFIX}FAILURE_DB_NOT_INIT")
                return

            self.run_id = self.db_manager.get_or_create_run_info(str(self.cfg.APP_PACKAGE), str(self.cfg.APP_ACTIVITY))
            if self.run_id is None:
                logging.critical("Failed to get or create run ID.")
                print(f"{UI_END_PREFIX}FAILURE_RUN_ID")
                return
            final_status_for_run = "RUNNING"
            self.db_manager.update_run_status(self.run_id, "RUNNING")

            logging.info(f"Starting/Continuing crawl run ID: {self.run_id} for app: {self.cfg.APP_PACKAGE}")
            print(f"{UI_STATUS_PREFIX}INITIALIZING_CRAWL_RUN_{self.run_id}")

            is_continuation_run = bool(self.cfg.CONTINUE_EXISTING_RUN and self.db_manager.get_step_count_for_run(self.run_id) > 0)
            self.screen_state_manager.initialize_for_run(
                run_id=self.run_id, app_package=str(self.cfg.APP_PACKAGE),
                start_activity=str(self.cfg.APP_ACTIVITY), is_continuation=is_continuation_run
            )
            self.crawl_steps_taken = self.screen_state_manager.current_run_latest_step_number
            if is_continuation_run:
                logging.info(f"Continuing run. Initial step count for AppCrawler set to {self.crawl_steps_taken}.")
            else:
                logging.info(f"Starting new run. Initial step count for AppCrawler set to 0.")

            self.crawl_start_time = time.time()
            self.is_shutting_down = False

            if not self.driver or not self.driver.connect():
                logging.critical("Failed to connect to Appium.")
                final_status_for_run = "FAILED_APPIUM_CONNECT"
                print(f"{UI_END_PREFIX}{final_status_for_run}")
                return
            if not self.app_context_manager.launch_and_verify_app():
                logging.critical("Failed to launch/verify target app.")
                final_status_for_run = "FAILED_APP_LAUNCH"
                print(f"{UI_END_PREFIX}{final_status_for_run}")
                return

            if self.cfg.ENABLE_TRAFFIC_CAPTURE:
                pcap_filename_template = f"{self.cfg.APP_PACKAGE}_run{self.run_id}_step{{step_num}}.pcap"
                if not await self.traffic_capture_manager.start_capture_async(filename_template=pcap_filename_template):
                    logging.warning("Failed to start traffic capture.")
                else: logging.info("Traffic capture started.")

            current_state_repr: Optional[ScreenRepresentation] = None

            while not self._should_terminate():
                self.crawl_steps_taken += 1
                current_step_for_log = self.crawl_steps_taken
                logging.info(f"--- Crawl Step {current_step_for_log} (Run ID: {self.run_id}) ---")
                print(f"{UI_STEP_PREFIX}{current_step_for_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Checking app context...")

                if not self.app_context_manager.ensure_in_app():
                    logging.error(f"Step {current_step_for_log}: Failed to ensure app context. Failures: {self.app_context_manager.consecutive_context_failures}")
                    if self._should_terminate(): final_status_for_run = "TERMINATED_CONTEXT_FAIL"; break
                    time.sleep(1) # Small pause before retrying or next step
                    continue 

                print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Getting screen state...")
                candidate_screen_repr = self.screen_state_manager.get_current_screen_representation(
                    run_id=self.run_id, step_number=current_step_for_log
                )
                if not candidate_screen_repr or not candidate_screen_repr.screenshot_bytes:
                    logging.error(f"Step {current_step_for_log}: Failed to get valid screen state candidate.")
                    self._handle_mapping_failure() # Or a new context failure counter
                    if self._should_terminate(): final_status_for_run = "TERMINATED_STATE_FAIL"; break
                    time.sleep(float(self.cfg.WAIT_AFTER_ACTION))
                    continue

                definitive_screen_repr, visit_info = self.screen_state_manager.process_and_record_state(
                    candidate_screen=candidate_screen_repr, run_id=self.run_id, step_number=current_step_for_log
                )
                current_state_repr = definitive_screen_repr

                # Ensure screenshot_path is valid before using it
                if current_state_repr.screenshot_path:
                    print(f"{UI_SCREENSHOT_PREFIX}{current_state_repr.screenshot_path}")
                    # Update master annotation file for the *original* screenshot
                    # This part assumes ai_assistant.get_next_action will be modified
                    # to return all_ui_elements. For now, we'll prepare for it.
                else:
                    logging.warning(f"Step {current_step_for_log}: Screenshot path is missing for screen ID {current_state_repr.id}. Cannot update master annotation for this screen.")


                logging.info(f"Step {current_step_for_log}: State Processed. Screen ID: {current_state_repr.id}, Hash: '{current_state_repr.composite_hash}', Activity: '{current_state_repr.activity_name}'")
                self.previous_composite_hash = current_state_repr.composite_hash

                print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Requesting AI action...")
                simplified_xml_context = current_state_repr.xml_content or ""
                if self.cfg.ENABLE_XML_CONTEXT and current_state_repr.xml_content:
                    simplified_xml_context = utils.simplify_xml_for_ai(current_state_repr.xml_content, int(self.cfg.XML_SNIPPET_MAX_LEN))

                # *** MODIFICATION POINT FOR AI RESPONSE ***
                # ai_full_response would ideally be:
                # {
                #     "action_to_perform": { ... original suggestion ... },
                #     "all_ui_elements": [ { "type": "button", "bbox": ... }, ... ]
                # }
                if current_state_repr.screenshot_bytes is None:
                    logging.error("Screenshot bytes are None, cannot proceed with AI analysis")
                    self._handle_ai_failure()
                    continue

                ai_full_response = self.ai_assistant.get_next_action( # This method needs to be updated
                    screenshot_bytes=current_state_repr.screenshot_bytes,
                    xml_context=simplified_xml_context,
                    previous_actions=visit_info.get("previous_actions_on_this_state", []),
                    current_screen_visit_count=visit_info.get("visit_count_this_run", 1),
                    current_composite_hash=current_state_repr.composite_hash
                )
                
                ai_action_suggestion = None
                all_detected_ui_elements = [] # For the new annotation file

                if isinstance(ai_full_response, dict):
                    ai_action_suggestion = ai_full_response.get("action_to_perform")
                    all_detected_ui_elements = ai_full_response.get("all_ui_elements", [])
                elif ai_full_response: # Backwards compatibility if it only returns the action
                    ai_action_suggestion = ai_full_response 
                    logging.warning("AI response format is old (expected dict with 'action_to_perform' and 'all_ui_elements'). Proceeding with action only.")


                if self._should_terminate(): final_status_for_run = "TERMINATED_DURING_AI"; break

                if not ai_action_suggestion:
                    logging.error(f"Step {current_step_for_log}: AI Assistant failed to suggest an action.")
                    self._handle_ai_failure()
                    if self._should_terminate(): final_status_for_run = "TERMINATED_AI_FAIL"; break
                    self.db_manager.insert_step_log(
                        run_id=self.run_id, step_number=current_step_for_log,
                        from_screen_id=current_state_repr.id, to_screen_id=None,
                        action_description="AI_NO_SUGGESTION", ai_suggestion_json=None,
                        mapped_action_json=None, execution_success=False, error_message="AI_NO_SUGGESTION"
                    )
                    self.screen_state_manager.record_action_taken_from_screen(current_state_repr.composite_hash, "AI_NO_SUGGESTION (failed)")
                    time.sleep(1)
                    continue
                
                self.consecutive_ai_failures = 0
                action_str_log = utils.generate_action_description(
                    ai_action_suggestion.get('action','N/A'), None, ai_action_suggestion.get('input_text'), ai_action_suggestion.get('target_identifier')
                )
                logging.info(f"Step {current_step_for_log}: AI suggested action: {action_str_log}. Reasoning: {ai_action_suggestion.get('reasoning')}")
                print(f"{UI_ACTION_PREFIX}{action_str_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Mapping AI action...")

                # Update master annotation file with all detected elements if available
                if current_state_repr.screenshot_path and all_detected_ui_elements:
                    self.screenshot_annotator.update_master_annotation_file(
                        original_screenshot_filename=current_state_repr.screenshot_path, # Pass the full path here
                        all_ui_elements_data=all_detected_ui_elements
                    )
                elif current_state_repr.screenshot_path and not all_detected_ui_elements:
                    # Using self.logger from AppCrawler if it exists, or just logging
                    logging.debug(f"No 'all_ui_elements' data from AI for {current_state_repr.screenshot_path} to update master annotation file.")


                action_details = self.action_mapper.map_ai_action_to_appium(
                    ai_response=ai_action_suggestion, current_xml_string=current_state_repr.xml_content
                )
                action_details = self.action_mapper.map_ai_action_to_appium(
                    ai_response=ai_action_suggestion, current_xml_string=current_state_repr.xml_content
                )

                if not action_details:
                    logging.error(f"Step {current_step_for_log}: Failed to map AI action: {ai_action_suggestion.get('action')} on '{ai_action_suggestion.get('target_identifier', 'N/A')}'")
                    self._handle_mapping_failure()
                    if self._should_terminate(): final_status_for_run = "TERMINATED_MAP_FAIL"; break
                    self.db_manager.insert_step_log(
                        run_id=self.run_id, step_number=current_step_for_log,
                        from_screen_id=current_state_repr.id, to_screen_id=None,
                        action_description=action_str_log, ai_suggestion_json=json.dumps(ai_action_suggestion),
                        mapped_action_json=None, execution_success=False, error_message="ACTION_MAPPING_FAILED"
                    )
                    self.screen_state_manager.record_action_taken_from_screen(current_state_repr.composite_hash, f"{action_str_log} (mapping_failed)")
                    time.sleep(1)
                    continue
                
                self.consecutive_map_failures = 0

                # Save the annotated screenshot (with a box around the *target* element)
                if current_state_repr.screenshot_bytes: # Ensure bytes are available
                    annotated_ss_path = self.screenshot_annotator.save_annotated_screenshot(
                        original_screenshot_bytes=current_state_repr.screenshot_bytes,
                        step=current_step_for_log, screen_id=current_state_repr.id,
                        ai_suggestion=ai_action_suggestion # Pass the action suggestion here
                    )
                    if annotated_ss_path: print(f"{UI_ANNOTATED_SCREENSHOT_PREFIX}{annotated_ss_path}")
                else:
                    logging.warning(f"Cannot save annotated screenshot for step {current_step_for_log}, screen ID {current_state_repr.id}: original_screenshot_bytes is missing.")

                print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Executing action: {action_details.get('type')}...")
                execution_success = self.action_executor.execute_action(action_details=action_details) # This calls the updated ActionExecutor

                next_state_screen_id_for_log = None
                if execution_success:
                    time.sleep(float(self.cfg.WAIT_AFTER_ACTION) / 2) # Wait briefly before getting next state
                    next_candidate_repr = self.screen_state_manager.get_current_screen_representation(
                        run_id=self.run_id, step_number=current_step_for_log # Still part of the same logical step
                    )
                    if next_candidate_repr:
                        # Process and record this new state. It might be a new screen or a revisit.
                        definitive_next_screen, _ = self.screen_state_manager.process_and_record_state(
                            candidate_screen=next_candidate_repr, run_id=self.run_id, step_number=current_step_for_log
                        )
                        next_state_screen_id_for_log = definitive_next_screen.id
                
                self._last_action_description = utils.generate_action_description(
                    action_details.get('type', 'N/A'),
                    action_details.get('element_info', {}).get('desc', action_details.get('scroll_direction')),
                    action_details.get('input_text', action_details.get('intended_input_text_for_coord_tap')),
                    ai_action_suggestion.get('target_identifier') # Use the AI's identifier
                )

                self.db_manager.insert_step_log(
                    run_id=self.run_id, step_number=current_step_for_log,
                    from_screen_id=current_state_repr.id, to_screen_id=next_state_screen_id_for_log,
                    action_description=self._last_action_description,
                    ai_suggestion_json=json.dumps(ai_action_suggestion), 
                    mapped_action_json=json.dumps(action_details, default=lambda o: "<WebElement>" if isinstance(o, WebElement) else str(o)),
                    execution_success=execution_success,
                    error_message=None if execution_success else self.action_executor.last_error_message or "EXECUTION_FAILED" # Use last_error_message
                )
                self.screen_state_manager.record_action_taken_from_screen(current_state_repr.composite_hash, f"{self._last_action_description} (Success: {execution_success})")

                if not execution_success:
                    logging.error(f"Step {current_step_for_log}: Failed to execute action: {action_details.get('type')}")
                    # ActionExecutor now tracks its own failures. _should_terminate will check action_executor.consecutive_exec_failures.
                    if self._should_terminate(): final_status_for_run = "TERMINATED_EXEC_FAIL"; break
                else:
                    logging.info(f"Step {current_step_for_log}: Action executed successfully.")
                    # self.action_executor.reset_consecutive_failures() # This is now called inside ActionExecutor on success

                time.sleep(float(self.cfg.WAIT_AFTER_ACTION)) 

            # End of while loop
            if not self.is_shutting_down:
                if self._should_terminate(): # Check conditions that might have been met on the last iteration
                    # Determine the specific reason _should_terminate is true
                    if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS: final_status_for_run = "COMPLETED_MAX_STEPS"
                    elif self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS: final_status_for_run = "COMPLETED_MAX_DURATION"
                    elif self.consecutive_ai_failures >= self.cfg.MAX_CONSECUTIVE_AI_FAILURES: final_status_for_run = "TERMINATED_MAX_AI_FAIL"
                    # ... other specific _should_terminate conditions
                    else: final_status_for_run = "COMPLETED_LIMITS" # Generic if specific not matched
                else: # Should not happen if loop exited normally without _should_terminate being true
                    final_status_for_run = "COMPLETED_UNEXPECTED_EXIT"
                logging.info(f"Crawl loop finished. Status: {final_status_for_run}")
                print(f"{UI_END_PREFIX}{final_status_for_run.upper()}")


        except WebDriverException as e:
            logging.critical(f"WebDriverException in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_WEBDRIVER_EXCEPTION"
            print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}") # Limit error message length for UI
            self.is_shutting_down = True
        except RuntimeError as e: # Catch specific runtime errors if needed
            logging.critical(f"RuntimeError in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_RUNTIME_ERROR"
            print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True # Signal shutdown
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt received in run_async. Initiating shutdown...")
            final_status_for_run = "INTERRUPTED_KEYBOARD"
            print(f"{UI_END_PREFIX}{final_status_for_run}")
            self.is_shutting_down = True # Signal shutdown
        except Exception as e: # Catch-all for any other unhandled exceptions
            logging.critical(f"Unhandled exception in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_UNHANDLED_EXCEPTION"
            if not self.is_shutting_down: print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True 
        finally:
            logging.info(f"Exited crawl loop or error. Final run status before cleanup: {final_status_for_run}")
            print(f"{UI_STATUS_PREFIX}Crawl loop ended. Finalizing run {self.run_id} with status {final_status_for_run}...")

            if self.cfg.ENABLE_TRAFFIC_CAPTURE and self.traffic_capture_manager.is_capturing():
                logging.info("Stopping and pulling final traffic capture...")
                pcap_file = await self.traffic_capture_manager.stop_capture_and_pull_async(
                    run_id=self.run_id or 0, step_num=self.crawl_steps_taken
                )
                if pcap_file: logging.info(f"Final traffic capture saved to: {pcap_file}")
                else: logging.warning("Failed to save final traffic capture.")

            if self.run_id is not None and self.db_manager is not None: # Check db_manager again
                self.db_manager.update_run_status(self.run_id, final_status_for_run, time.strftime("%Y-%m-%d %H:%M:%S"))

            self.perform_full_cleanup()
            logging.info(f"AppCrawler run_async finished for Run ID: {self.run_id}. Final DB status: {final_status_for_run}")

    def run(self):
        try:
            logging.info(f"AppCrawler run initiated for {self.cfg.APP_PACKAGE}.")
            asyncio.run(self.run_async()) # Manages its own event loop
            logging.info(f"AppCrawler run completed for {self.cfg.APP_PACKAGE}.")
        except SystemExit as se: # Propagate SystemExit if used for controlled shutdown
            logging.info(f"SystemExit caught by AppCrawler.run() wrapper: {se.code}")
            raise
        except KeyboardInterrupt: # Should be handled by run_async's finally
            logging.warning("KeyboardInterrupt caught by AppCrawler.run() wrapper. Cleanup should have been handled.")
        except Exception as e:
            logging.critical(f"Unhandled critical error in AppCrawler.run() wrapper: {e}", exc_info=True)
            # Ensure cleanup is attempted if not already done by run_async
            if not self.is_shutting_down and not (hasattr(self, '_cleanup_called') and self._cleanup_called):
                self.perform_full_cleanup()
        finally:
            logging.info("AppCrawler.run() synchronous wrapper finished.")