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

        # MODIFIED: Added new instance variables for feedback and fallback logic
        self.last_action_feedback_for_ai: Optional[str] = None
        self.consecutive_no_op_failures: int = 0
        self.fallback_action_index: int = 0

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

        # Check CRAWL_MODE and apply corresponding limit
        if self.cfg.CRAWL_MODE == 'steps':
            if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS:
                logging.info(f"Termination check: Reached max steps ({self.cfg.MAX_CRAWL_STEPS}) in 'steps' mode.")
                if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_STEPS_REACHED")
                self.is_shutting_down = True
                return True
        elif self.cfg.CRAWL_MODE == 'time':
            if self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS:
                logging.info(f"Termination check: Reached max duration ({self.cfg.MAX_CRAWL_DURATION_SECONDS}s) in 'time' mode.")
                if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_DURATION_REACHED")
                self.is_shutting_down = True
                return True
        else:
            logging.warning(f"Unknown CRAWL_MODE: '{self.cfg.CRAWL_MODE}'. Checking both step and time limits as a fallback.")
            # Fallback to original behavior if mode is not 'steps' or 'time'
            if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS:
                logging.info(f"Termination check (fallback): Reached max steps ({self.cfg.MAX_CRAWL_STEPS}).")
                if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_STEPS_REACHED")
                self.is_shutting_down = True
                return True
            if self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS:
                logging.info(f"Termination check (fallback): Reached max duration ({self.cfg.MAX_CRAWL_DURATION_SECONDS}s).")
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
        # MODIFIED: Increment no-op counter and set feedback message
        self.consecutive_no_op_failures += 1
        self.last_action_feedback_for_ai = "EXECUTION FAILED: The AI failed to produce a valid action. A new action must be chosen."

    def _handle_mapping_failure(self):
        self.consecutive_map_failures += 1
        logging.warning(f"Action mapping failure. Count: {self.consecutive_map_failures}/{self.cfg.MAX_CONSECUTIVE_MAP_FAILURES}")
        # MODIFIED: Increment no-op counter and set feedback message
        self.consecutive_no_op_failures += 1
        self.last_action_feedback_for_ai = "EXECUTION FAILED: The AI's suggested action could not be mapped to a valid UI element. A new action must be chosen."

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

        if self.run_id is not None and hasattr(self, 'db_manager') and self.db_manager is not None :
            current_status_for_db = "COMPLETED_CLEANUP"
            if self.consecutive_ai_failures >= self.cfg.MAX_CONSECUTIVE_AI_FAILURES: current_status_for_db = "TERMINATED_MAX_AI_FAIL_CLEANUP"
            elif self.consecutive_map_failures >= self.cfg.MAX_CONSECUTIVE_MAP_FAILURES: current_status_for_db = "TERMINATED_MAX_MAP_FAIL_CLEANUP"
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

            if self.run_id is None: # Should be set by caller, but as a safeguard
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

            while not self._should_terminate():
                self.crawl_steps_taken += 1
                current_step_for_log = self.crawl_steps_taken
                logging.info(f"--- Crawl Step {current_step_for_log} (Run ID: {self.run_id}) ---")
                print(f"{UI_STEP_PREFIX}{current_step_for_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Checking app context...")

                if not self.app_context_manager.ensure_in_app():
                    logging.error(f"Step {current_step_for_log}: Failed to ensure app context. Failures: {self.app_context_manager.consecutive_context_failures}")
                    if self._should_terminate(): final_status_for_run = "TERMINATED_CONTEXT_FAIL"; break
                    time.sleep(1)
                    continue

                print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Getting screen state...")
                candidate_screen_repr = self.screen_state_manager.get_current_screen_representation(
                    run_id=self.run_id, step_number=current_step_for_log
                )
                if not candidate_screen_repr or not candidate_screen_repr.screenshot_bytes:
                    logging.error(f"Step {current_step_for_log}: Failed to get valid screen state candidate.")
                    self._handle_mapping_failure()
                    if self._should_terminate(): final_status_for_run = "TERMINATED_STATE_FAIL"; break
                    time.sleep(float(self.cfg.WAIT_AFTER_ACTION))
                    continue

                definitive_screen_repr, visit_info = self.screen_state_manager.process_and_record_state(
                    candidate_screen=candidate_screen_repr, run_id=self.run_id, step_number=current_step_for_log
                )
                
                if definitive_screen_repr.screenshot_path:
                    print(f"{UI_SCREENSHOT_PREFIX}{definitive_screen_repr.screenshot_path}")
                else:
                    logging.warning(f"Step {current_step_for_log}: Screenshot path is missing for screen ID {definitive_screen_repr.id}.")

                logging.info(f"Step {current_step_for_log}: State Processed. Screen ID: {definitive_screen_repr.id}, Hash: '{definitive_screen_repr.composite_hash}', Activity: '{definitive_screen_repr.activity_name}'")
                self.previous_composite_hash = definitive_screen_repr.composite_hash

                print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Deciding next action...")
                
                ai_action_suggestion = None
                ai_time_taken = None
                
                max_no_op = getattr(self.cfg, 'MAX_CONSECUTIVE_NO_OP_FAILURES', 3)
                if self.consecutive_no_op_failures >= max_no_op:
                    logging.warning(f"Reached {self.consecutive_no_op_failures} consecutive no-op/failed actions. Using fallback sequence.")
                    fallback_actions = getattr(self.cfg, 'FALLBACK_ACTIONS_SEQUENCE', [])
                    if fallback_actions:
                        action_to_try = fallback_actions[self.fallback_action_index % len(fallback_actions)]
                        ai_action_suggestion = action_to_try.copy()
                        ai_action_suggestion['reasoning'] = f"FALLBACK ACTION: Triggered after {self.consecutive_no_op_failures} consecutive failures."
                        self.fallback_action_index += 1
                        logging.info(f"Selected fallback action: {ai_action_suggestion}")
                    else:
                        logging.error("Fallback sequence triggered, but FALLBACK_ACTIONS_SEQUENCE is empty in config.")

                if ai_action_suggestion is None:
                    if self.cfg.APP_PACKAGE:
                        filtered_xml = utils.filter_xml_by_allowed_packages(
                            definitive_screen_repr.xml_content or "",
                            self.cfg.APP_PACKAGE,
                            self.cfg.ALLOWED_EXTERNAL_PACKAGES
                        )
                        simplified_xml_context = utils.simplify_xml_for_ai(filtered_xml, int(self.cfg.XML_SNIPPET_MAX_LEN))
                    else:
                        logging.error("APP_PACKAGE is not configured, cannot filter XML. Using raw XML.")
                        simplified_xml_context = utils.simplify_xml_for_ai(definitive_screen_repr.xml_content or "", int(self.cfg.XML_SNIPPET_MAX_LEN))
                    
                    if definitive_screen_repr.screenshot_bytes:
                        ai_response_tuple = self.ai_assistant.get_next_action(
                            screenshot_bytes=definitive_screen_repr.screenshot_bytes,
                            xml_context=simplified_xml_context,
                            previous_actions=visit_info.get("previous_actions_on_this_state", []),
                            current_screen_visit_count=visit_info.get("visit_count_this_run", 1),
                            current_composite_hash=definitive_screen_repr.composite_hash,
                            last_action_feedback=self.last_action_feedback_for_ai
                        )
                        if ai_response_tuple:
                            ai_full_response, ai_time_taken = ai_response_tuple
                            if ai_full_response and "action_to_perform" in ai_full_response:
                                ai_action_suggestion = ai_full_response.get("action_to_perform")
                    else:
                        logging.error("Screenshot bytes are None, cannot call AI.")

                if not ai_action_suggestion:
                    self._handle_ai_failure()
                    if self.run_id is not None:
                        self.db_manager.insert_step_log(
                            run_id=self.run_id, step_number=current_step_for_log,
                            from_screen_id=definitive_screen_repr.id, to_screen_id=None,
                            action_description="AI_NO_SUGGESTION", ai_suggestion_json=None,
                            mapped_action_json=None, execution_success=False, error_message="AI_NO_SUGGESTION",
                            ai_response_time=ai_time_taken
                        )
                    if self._should_terminate(): final_status_for_run = "TERMINATED_AI_FAIL"; break
                    continue
                
                self.consecutive_ai_failures = 0

                action_str_log = utils.generate_action_description(ai_action_suggestion.get('action'), None, ai_action_suggestion.get('input_text'), ai_action_suggestion.get('target_identifier'))
                logging.info(f"Step {current_step_for_log}: AI suggested action: {action_str_log}. Reasoning: {ai_action_suggestion.get('reasoning')}")
                print(f"{UI_ACTION_PREFIX}{action_str_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Mapping AI action...")

                action_details = self.action_mapper.map_ai_action_to_appium(
                    ai_response=ai_action_suggestion, current_xml_string=definitive_screen_repr.xml_content
                )
                if not action_details:
                    self._handle_mapping_failure()
                    if self._should_terminate(): final_status_for_run = "TERMINATED_MAP_FAIL"; break
                    continue
                
                self.consecutive_map_failures = 0

                if definitive_screen_repr.screenshot_bytes:
                    annotated_ss_path = self.screenshot_annotator.save_annotated_screenshot(
                        original_screenshot_bytes=definitive_screen_repr.screenshot_bytes,
                        step=current_step_for_log, screen_id=definitive_screen_repr.id,
                        ai_suggestion=ai_action_suggestion)
                    if annotated_ss_path: print(f"{UI_ANNOTATED_SCREENSHOT_PREFIX}{annotated_ss_path}")

                print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Executing action: {action_details.get('type')}...")
                execution_success = self.action_executor.execute_action(action_details=action_details)
                
                next_state_screen_id_for_log = None
                if execution_success:
                    time.sleep(float(self.cfg.WAIT_AFTER_ACTION) / 2)
                    next_candidate_repr = self.screen_state_manager.get_current_screen_representation(
                        run_id=self.run_id, step_number=current_step_for_log
                    )
                    if next_candidate_repr:
                        definitive_next_screen, _ = self.screen_state_manager.process_and_record_state(
                            candidate_screen=next_candidate_repr, run_id=self.run_id, step_number=current_step_for_log)
                        next_state_screen_id_for_log = definitive_next_screen.id
                        
                        if definitive_next_screen.composite_hash == self.previous_composite_hash:
                            self.last_action_feedback_for_ai = f"NO CHANGE: Your action '{ai_action_suggestion.get('action')}' was executed, but the screen did not change. You MUST suggest a different action."
                            logging.warning(self.last_action_feedback_for_ai)
                            self.consecutive_no_op_failures += 1
                        else:
                            self.last_action_feedback_for_ai = "SUCCESS: Your last action was successful."
                            self.consecutive_no_op_failures = 0
                            self.fallback_action_index = 0
                    else:
                         self.last_action_feedback_for_ai = "UNKNOWN: Action succeeded but the next state could not be determined."
                         self.consecutive_no_op_failures += 1
                else:
                    error_msg = self.action_executor.last_error_message or "Unknown execution error"
                    self.last_action_feedback_for_ai = f"EXECUTION FAILED: Your action '{ai_action_suggestion.get('action')}' failed with error: {error_msg}. You MUST suggest a different action."
                    logging.error(self.last_action_feedback_for_ai)
                    self.consecutive_no_op_failures += 1
                
                if self.run_id is not None:
                    self.db_manager.insert_step_log(
                        run_id=self.run_id, step_number=current_step_for_log,
                        from_screen_id=definitive_screen_repr.id, to_screen_id=next_state_screen_id_for_log,
                        action_description=action_str_log,
                        ai_suggestion_json=json.dumps(ai_action_suggestion),
                        mapped_action_json=json.dumps(action_details, default=lambda o: "<WebElement>" if isinstance(o, WebElement) else str(o)),
                        execution_success=execution_success,
                        error_message=self.action_executor.last_error_message if not execution_success else None,
                        ai_response_time=ai_time_taken
                    )
                self.screen_state_manager.record_action_taken_from_screen(definitive_screen_repr.composite_hash, f"{action_str_log} (Success: {execution_success})")

                if not execution_success:
                    if self._should_terminate(): final_status_for_run = "TERMINATED_EXEC_FAIL"; break
                
                time.sleep(float(self.cfg.WAIT_AFTER_ACTION))

            if not self.is_shutting_down:
                if self._should_terminate():
                    if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS: final_status_for_run = "COMPLETED_MAX_STEPS"
                    elif self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS: final_status_for_run = "COMPLETED_MAX_DURATION"
                    else: final_status_for_run = "COMPLETED_LIMITS"
                else:
                    final_status_for_run = "COMPLETED_UNEXPECTED_EXIT"
                logging.info(f"Crawl loop finished. Status: {final_status_for_run}")
                print(f"{UI_END_PREFIX}{final_status_for_run.upper()}")

        except WebDriverException as e:
            logging.critical(f"WebDriverException in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_WEBDRIVER_EXCEPTION"
            print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True
        except RuntimeError as e:
            logging.critical(f"RuntimeError in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_RUNTIME_ERROR"
            print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)[:100]}")
            self.is_shutting_down = True
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt received in run_async. Initiating shutdown...")
            final_status_for_run = "INTERRUPTED_KEYBOARD"
            print(f"{UI_END_PREFIX}{final_status_for_run}")
            self.is_shutting_down = True
        except Exception as e:
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

            if self.run_id is not None and self.db_manager is not None:
                self.db_manager.update_run_status(self.run_id, final_status_for_run, time.strftime("%Y-%m-%d %H:%M:%S"))

            self.perform_full_cleanup()
            logging.info(f"AppCrawler run_async finished for Run ID: {self.run_id}. Final DB status: {final_status_for_run}")

    def run(self):
        try:
            logging.info(f"AppCrawler run initiated for {self.cfg.APP_PACKAGE}.")
            asyncio.run(self.run_async())
            logging.info(f"AppCrawler run completed for {self.cfg.APP_PACKAGE}.")
        except SystemExit as se:
            logging.info(f"SystemExit caught by AppCrawler.run() wrapper: {se.code}")
            raise
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt caught by AppCrawler.run() wrapper. Cleanup should have been handled.")
        except Exception as e:
            logging.critical(f"Unhandled critical error in AppCrawler.run() wrapper: {e}", exc_info=True)
            if not self.is_shutting_down and not (hasattr(self, '_cleanup_called') and self._cleanup_called):
                self.perform_full_cleanup()
        finally:
            logging.info("AppCrawler.run() synchronous wrapper finished.")