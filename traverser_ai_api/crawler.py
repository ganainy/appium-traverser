import logging
import time
import os
import re # Not used directly in this version of AppCrawler, but often useful with utils
import json
from typing import Optional, Tuple, List, Dict, Any
import asyncio # For running async methods like traffic capture

# --- Assuming your project structure allows these imports ---
# --- Adjust them based on your actual package structure ---

from config import Config
import utils # For utils.simplify_xml_for_ai, utils.generate_action_description etc.

from ai_assistant import AIAssistant
from appium_driver import AppiumDriver
from screen_state_manager import ScreenStateManager, ScreenRepresentation
from database import DatabaseManager
from action_mapper import ActionMapper
from traffic_capture_manager import TrafficCaptureManager
from action_executor import ActionExecutor
from app_context_manager import AppContextManager
from screenshot_annotator import ScreenshotAnnotator

from selenium.webdriver.remote.webelement import WebElement # For type checking if needed
from appium.webdriver.common.appiumby import AppiumBy # Used by AppCrawler for strategies
from selenium.common.exceptions import WebDriverException


# --- UI Communication Prefixes ---
UI_STATUS_PREFIX = "UI_STATUS:"
UI_STEP_PREFIX = "UI_STEP:"
UI_ACTION_PREFIX = "UI_ACTION:"
UI_SCREENSHOT_PREFIX = "UI_SCREENSHOT:"
UI_ANNOTATED_SCREENSHOT_PREFIX = "UI_ANNOTATED_SCREENSHOT:"
UI_END_PREFIX = "UI_END:"

class AppCrawler:
    """Orchestrates the AI-driven app crawling process using a centralized Config object."""

    def __init__(self, app_config: Config):
        """Initialize the AppCrawler with the main application Config object.

        Args:
            app_config (Config): The main application Config object instance.
        """
        self.cfg = app_config
        logging.info(f"AppCrawler initializing with App Package: {self.cfg.APP_PACKAGE}")

        # --- Validate required configurations directly from self.cfg ---
        # These checks ensure critical config values are present before proceeding.
        required_attrs_for_crawler = [
            'APPIUM_SERVER_URL', 'NEW_COMMAND_TIMEOUT', 'APPIUM_IMPLICIT_WAIT',
            'GEMINI_API_KEY', 'DEFAULT_MODEL_TYPE', 'AI_SAFETY_SETTINGS',
            'DB_NAME', 'APP_PACKAGE', 'APP_ACTIVITY', 'SHUTDOWN_FLAG_PATH',
            'MAX_CRAWL_STEPS', 'MAX_CRAWL_DURATION_SECONDS',
            'MAX_CONSECUTIVE_AI_FAILURES', 'MAX_CONSECUTIVE_MAP_FAILURES',
            'MAX_CONSECUTIVE_EXEC_FAILURES', 'MAX_CONSECUTIVE_CONTEXT_FAILURES',
            'WAIT_AFTER_ACTION', 'ALLOWED_EXTERNAL_PACKAGES', 'ENABLE_XML_CONTEXT',
            'XML_SNIPPET_MAX_LEN', 'SCREENSHOTS_DIR', 'ANNOTATED_SCREENSHOTS_DIR',
            'ENABLE_TRAFFIC_CAPTURE', 'CONTINUE_EXISTING_RUN'
        ]
        for attr in required_attrs_for_crawler:
            if not hasattr(self.cfg, attr) or getattr(self.cfg, attr) is None:
                # Specific allowances for None or empty if meaningful (e.g., empty list for ALLOWED_EXTERNAL_PACKAGES)
                if attr == 'ALLOWED_EXTERNAL_PACKAGES' and isinstance(getattr(self.cfg, attr, None), list):
                    continue
                if attr == 'AI_SAFETY_SETTINGS' and isinstance(getattr(self.cfg, attr, None), dict): # Empty dict is fine
                    continue
                raise ValueError(f"AppCrawler: Critical configuration '{attr}' is missing or None in Config object.")

        # --- Initialize components, passing self.cfg ---
        self.driver = AppiumDriver(app_config=self.cfg)
        self.ai_assistant = AIAssistant(app_config=self.cfg)
        self.db_manager = DatabaseManager(app_config=self.cfg) # DatabaseManager now takes app_config

        self.screen_state_manager = ScreenStateManager(
            db_manager=self.db_manager,
            driver=self.driver,
            app_config=self.cfg
        )

        self.element_finding_strategies: List[Tuple[str, Optional[str], str]] = [
            ('id', AppiumBy.ID, "ID"), # AppiumBy members are strings like "id"
            ('acc_id', AppiumBy.ACCESSIBILITY_ID, "Accessibility ID"),
            ('xpath_exact', AppiumBy.XPATH, "XPath Exact Match"), # Use AppiumBy.XPATH for clarity
            ('xpath_contains', AppiumBy.XPATH, "XPath Contains Match")
        ]
        logging.debug(f"Element finding strategies: {[s[2] for s in self.element_finding_strategies]}")

        self.action_mapper = ActionMapper(
            driver=self.driver,
            element_finding_strategies=self.element_finding_strategies,
            app_config=self.cfg
        )

        self.traffic_capture_manager = TrafficCaptureManager(
            driver=self.driver,
            app_config=self.cfg
        )

        self.action_executor = ActionExecutor(
            driver=self.driver,
            app_config=self.cfg
        )
        self.app_context_manager = AppContextManager(
            driver=self.driver,
            app_config=self.cfg
        )
        self.screenshot_annotator = ScreenshotAnnotator(
            driver=self.driver,
            app_config=self.cfg
        )

        # --- State Tracking ---
        self.consecutive_ai_failures = 0
        self.consecutive_map_failures = 0
        # consecutive_exec_failures is managed by ActionExecutor
        # consecutive_context_failures is managed by AppContextManager

        self._last_action_description: str = "CRAWL_START"
        self.previous_composite_hash: Optional[str] = None

        # --- Run Loop Control ---
        self.run_id: Optional[int] = None
        self.crawl_steps_taken: int = 0
        self.crawl_start_time: float = 0.0
        self.is_shutting_down: bool = False

        logging.info("AppCrawler initialized successfully.")

    def _should_terminate(self) -> bool:
        """Checks if the crawler should terminate based on configured limits or shutdown flag."""
        if self.is_shutting_down:
            logging.info("Termination check: Shutdown already initiated by internal logic.")
            return True

        if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            logging.info(f"Termination check: External shutdown flag found at {self.cfg.SHUTDOWN_FLAG_PATH}.")
            self.is_shutting_down = True # Set internal flag
            print(f"{UI_END_PREFIX}SHUTDOWN_FLAG_DETECTED")
            return True

        max_steps = self.cfg.MAX_CRAWL_STEPS
        if max_steps is not None and self.crawl_steps_taken >= max_steps:
            logging.info(f"Termination check: Reached maximum crawl steps ({max_steps}).")
            print(f"{UI_END_PREFIX}MAX_STEPS_REACHED")
            return True

        max_duration = self.cfg.MAX_CRAWL_DURATION_SECONDS
        if max_duration is not None and (time.time() - self.crawl_start_time) >= max_duration:
            logging.info(f"Termination check: Reached maximum crawl duration ({max_duration}s).")
            print(f"{UI_END_PREFIX}MAX_DURATION_REACHED")
            return True

        if self.consecutive_ai_failures >= self.cfg.MAX_CONSECUTIVE_AI_FAILURES:
            logging.error(f"Termination check: Exceeded max consecutive AI failures ({self.cfg.MAX_CONSECUTIVE_AI_FAILURES}).")
            print(f"{UI_END_PREFIX}FAILURE_MAX_AI_FAIL")
            return True
        if self.consecutive_map_failures >= self.cfg.MAX_CONSECUTIVE_MAP_FAILURES:
            logging.error(f"Termination check: Exceeded max consecutive mapping failures ({self.cfg.MAX_CONSECUTIVE_MAP_FAILURES}).")
            print(f"{UI_END_PREFIX}FAILURE_MAX_MAP_FAIL")
            return True
        if self.action_executor.consecutive_exec_failures >= self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES:
            logging.error(f"Termination check: Exceeded max consecutive execution failures ({self.cfg.MAX_CONSECUTIVE_EXEC_FAILURES}).")
            print(f"{UI_END_PREFIX}FAILURE_MAX_EXEC_FAIL")
            return True
        if self.app_context_manager.consecutive_context_failures >= self.cfg.MAX_CONSECUTIVE_CONTEXT_FAILURES:
            logging.error(f"Termination check: Exceeded max consecutive app context failures ({self.cfg.MAX_CONSECUTIVE_CONTEXT_FAILURES}).")
            print(f"{UI_END_PREFIX}FAILURE_MAX_CONTEXT_FAIL")
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
            logging.debug("Cleanup already called and completed.")
            return

        logging.info("Performing full cleanup for AppCrawler...")
        self.is_shutting_down = True # Ensure this is set
        self._cleanup_called = True # Mark that cleanup has been initiated

        if self.cfg.ENABLE_TRAFFIC_CAPTURE and self.traffic_capture_manager and self.traffic_capture_manager.is_capturing():
            logging.info("Ensuring traffic capture is stopped and data pulled during full cleanup...")
            try:
                # This should ideally be awaited if called from an async context,
                # but cleanup might be called from sync context too.
                # For now, assume stop_capture_and_pull_async handles its own async nature if needed or has a sync wrapper.
                # The main call is in run_async's finally. This is a fallback.
                if hasattr(asyncio, 'get_running_loop'): # Check if an event loop is running
                    try:
                        loop = asyncio.get_running_loop()
                        if loop.is_running():
                            asyncio.ensure_future(self.traffic_capture_manager.stop_capture_and_pull_async(
                                run_id=self.run_id or 0, step_num=self.crawl_steps_taken
                            )) # type: ignore
                        else: # Loop exists but not running
                            asyncio.run(self.traffic_capture_manager.stop_capture_and_pull_async(
                                run_id=self.run_id or 0, step_num=self.crawl_steps_taken
                            )) # type: ignore
                    except RuntimeError: # No event loop
                        asyncio.run(self.traffic_capture_manager.stop_capture_and_pull_async(
                            run_id=self.run_id or 0, step_num=self.crawl_steps_taken
                        )) # type: ignore
                else: # Fallback for older Python or if get_running_loop is not suitable
                    asyncio.run(self.traffic_capture_manager.stop_capture_and_pull_async(
                        run_id=self.run_id or 0, step_num=self.crawl_steps_taken
                    )) # type: ignore

            except Exception as e_traffic:
                logging.error(f"Error during traffic capture finalization in cleanup: {e_traffic}", exc_info=True)

        if self.driver:
            try:
                logging.info("Quitting Appium driver session...")
                self.driver.disconnect() # AppiumDriver.disconnect() calls driver.quit()
            except Exception as e_driver:
                logging.error(f"Error during Appium driver quit in cleanup: {e_driver}", exc_info=True)
            finally:
                self.driver = None # type: ignore

        if self.db_manager:
            try:
                logging.info("Closing database connection...")
                self.db_manager.close()
            except Exception as e_db:
                logging.error(f"Error closing database in cleanup: {e_db}", exc_info=True)
            finally:
                self.db_manager = None # type: ignore

        if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            try:
                os.remove(self.cfg.SHUTDOWN_FLAG_PATH)
                logging.info(f"Cleaned up shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH}")
            except OSError as e_flag:
                logging.warning(f"Could not remove shutdown flag during cleanup: {e_flag}")

        if self.run_id is not None and self.db_manager is not None: # Check db_manager again as it might be None
            self.db_manager.update_run_status(self.run_id, "COMPLETED_CLEANUP" if not self._should_terminate() else "TERMINATED_CLEANUP", time.strftime("%Y-%m-%d %H:%M:%S"))


        logging.info("AppCrawler full cleanup process finished.")
        self._cleanup_called = True


    async def run_async(self):
        self._cleanup_called = False
        final_status_for_run = "STARTED_ERROR" # Default if exits early

        try:
            if not self.db_manager:
                logging.critical("DatabaseManager not available. Cannot run.")
                print(f"{UI_END_PREFIX}FAILURE_DB_NOT_INIT")
                return

            self.run_id = self.db_manager.get_or_create_run_info(str(self.cfg.APP_PACKAGE), str(self.cfg.APP_ACTIVITY))
            if self.run_id is None:
                logging.critical("Failed to get or create run ID. Cannot proceed.")
                print(f"{UI_END_PREFIX}FAILURE_RUN_ID")
                return
            final_status_for_run = "RUNNING" # Set after successful run_id
            self.db_manager.update_run_status(self.run_id, "RUNNING")


            logging.info(f"Starting/Continuing crawl run ID: {self.run_id} for app: {self.cfg.APP_PACKAGE}")
            print(f"{UI_STATUS_PREFIX}INITIALIZING_CRAWL_RUN_{self.run_id}")

            is_continuation_run = bool(self.cfg.CONTINUE_EXISTING_RUN and self.db_manager.get_step_count_for_run(self.run_id) > 0)
            self.screen_state_manager.initialize_for_run(
                run_id=self.run_id, app_package=str(self.cfg.APP_PACKAGE),
                start_activity=str(self.cfg.APP_ACTIVITY), is_continuation=is_continuation_run
            )
            # Correctly set AppCrawler's step counter based on ScreenStateManager's initialized value
            self.crawl_steps_taken = self.screen_state_manager.current_run_latest_step_number # MODIFIED HERE
            if is_continuation_run:
                logging.info(f"Continuing run. Initial step count for AppCrawler set to {self.crawl_steps_taken} (next step will be {self.crawl_steps_taken + 1}).")
            else:
                logging.info(f"Starting new run. Initial step count for AppCrawler set to 0.")


            self.crawl_start_time = time.time()
            self.is_shutting_down = False

            if not self.driver or not self.driver.connect():
                logging.critical("Failed to connect to Appium. Aborting crawl.")
                final_status_for_run = "FAILED_APPIUM_CONNECT"
                print(f"{UI_END_PREFIX}{final_status_for_run}")
                return

            if not self.app_context_manager.launch_and_verify_app():
                logging.critical("Failed to launch/verify target app. Aborting crawl.")
                final_status_for_run = "FAILED_APP_LAUNCH"
                print(f"{UI_END_PREFIX}{final_status_for_run}")
                return

            if self.cfg.ENABLE_TRAFFIC_CAPTURE:
                pcap_filename_template = f"{self.cfg.APP_PACKAGE}_run{self.run_id}_step{{step_num}}.pcap"
                if not await self.traffic_capture_manager.start_capture_async(filename_template=pcap_filename_template):
                    logging.warning("Failed to start traffic capture. Continuing without it.")
                else: logging.info("Traffic capture started.")

            current_state_repr: Optional[ScreenRepresentation] = None

            while not self._should_terminate():
                self.crawl_steps_taken += 1 # Current step being processed
                current_step_for_log = self.crawl_steps_taken
                logging.info(f"--- Crawl Step {current_step_for_log} (Run ID: {self.run_id}) ---")
                print(f"{UI_STEP_PREFIX}{current_step_for_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Checking app context...")

                if not self.app_context_manager.ensure_in_app():
                    logging.error(f"Step {current_step_for_log}: Failed to ensure app context. Failures: {self.app_context_manager.consecutive_context_failures}")
                    if self._should_terminate(): final_status_for_run = "TERMINATED_CONTEXT_FAIL"; break
                    time.sleep(1)
                    # continue # Potentially skip step if context is lost and unrecoverable for this iteration

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
                current_state_repr = definitive_screen_repr

                if current_state_repr.screenshot_path:
                    print(f"{UI_SCREENSHOT_PREFIX}{current_state_repr.screenshot_path}")
                logging.info(f"Step {current_step_for_log}: State Processed. Screen ID: {current_state_repr.id}, Hash: '{current_state_repr.composite_hash}', Activity: '{current_state_repr.activity_name}'")
                self.previous_composite_hash = current_state_repr.composite_hash

                print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Requesting AI action...")
                simplified_xml_context = current_state_repr.xml_content or ""
                if self.cfg.ENABLE_XML_CONTEXT and current_state_repr.xml_content:
                    simplified_xml_context = utils.simplify_xml_for_ai(current_state_repr.xml_content, int(self.cfg.XML_SNIPPET_MAX_LEN))

                ai_suggestion = self.ai_assistant.get_next_action(
                    screenshot_bytes=current_state_repr.screenshot_bytes, # type: ignore
                    xml_context=simplified_xml_context,
                    previous_actions=visit_info.get("previous_actions_on_this_state", []),
                    current_screen_visit_count=visit_info.get("visit_count_this_run", 1),
                    current_composite_hash=current_state_repr.composite_hash
                )

                if self._should_terminate(): final_status_for_run = "TERMINATED_DURING_AI"; break

                if not ai_suggestion:
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
                    ai_suggestion.get('action','N/A'), None, ai_suggestion.get('input_text'), ai_suggestion.get('target_identifier')
                )
                logging.info(f"Step {current_step_for_log}: AI suggested: {action_str_log}. Reasoning: {ai_suggestion.get('reasoning')}")
                print(f"{UI_ACTION_PREFIX}{action_str_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Mapping AI action...")

                action_details = self.action_mapper.map_ai_action_to_appium(
                    ai_response=ai_suggestion, current_xml_string=current_state_repr.xml_content
                )

                if not action_details:
                    logging.error(f"Step {current_step_for_log}: Failed to map AI action: {ai_suggestion.get('action')} on '{ai_suggestion.get('target_identifier', 'N/A')}'")
                    self._handle_mapping_failure()
                    if self._should_terminate(): final_status_for_run = "TERMINATED_MAP_FAIL"; break
                    self.db_manager.insert_step_log(
                        run_id=self.run_id, step_number=current_step_for_log,
                        from_screen_id=current_state_repr.id, to_screen_id=None,
                        action_description=action_str_log, ai_suggestion_json=json.dumps(ai_suggestion),
                        mapped_action_json=None, execution_success=False, error_message="ACTION_MAPPING_FAILED"
                    )
                    self.screen_state_manager.record_action_taken_from_screen(current_state_repr.composite_hash, f"{action_str_log} (mapping_failed)")
                    time.sleep(1)
                    continue

                self.consecutive_map_failures = 0

                annotated_ss_path = self.screenshot_annotator.save_annotated_screenshot(
                    original_screenshot_bytes=current_state_repr.screenshot_bytes, # type: ignore
                    step=current_step_for_log, screen_id=current_state_repr.id,
                    ai_suggestion=ai_suggestion
                )
                if annotated_ss_path: print(f"{UI_ANNOTATED_SCREENSHOT_PREFIX}{annotated_ss_path}")

                print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Executing action: {action_details.get('type')}...")
                execution_success = self.action_executor.execute_action(action_details=action_details)

                next_state_screen_id_for_log = None
                if execution_success:
                    time.sleep(float(self.cfg.WAIT_AFTER_ACTION) / 2)
                    next_candidate_repr = self.screen_state_manager.get_current_screen_representation(
                        run_id=self.run_id, step_number=current_step_for_log # Log as part of same logical step
                    )
                    if next_candidate_repr:
                        definitive_next_screen, _ = self.screen_state_manager.process_and_record_state(
                            candidate_screen=next_candidate_repr, run_id=self.run_id, step_number=current_step_for_log
                        )
                        next_state_screen_id_for_log = definitive_next_screen.id

                self._last_action_description = utils.generate_action_description( # Use for DB log
                    action_details.get('type', 'N/A'),
                    action_details.get('element_info', {}).get('desc', action_details.get('scroll_direction')),
                    action_details.get('input_text', action_details.get('intended_input_text_for_coord_tap')),
                    ai_suggestion.get('target_identifier')
                )

                self.db_manager.insert_step_log(
                    run_id=self.run_id, step_number=current_step_for_log,
                    from_screen_id=current_state_repr.id, to_screen_id=next_state_screen_id_for_log,
                    action_description=self._last_action_description,
                    ai_suggestion_json=json.dumps(ai_suggestion),
                    mapped_action_json=json.dumps(action_details, default=lambda o: "<WebElement>" if isinstance(o, WebElement) else str(o)), # Handle WebElement for JSON
                    execution_success=execution_success,
                    error_message=None if execution_success else "EXECUTION_FAILED"
                )
                self.screen_state_manager.record_action_taken_from_screen(current_state_repr.composite_hash, f"{self._last_action_description} (Success: {execution_success})")

                if not execution_success:
                    logging.error(f"Step {current_step_for_log}: Failed to execute action: {action_details.get('type')}")
                    if self._should_terminate(): final_status_for_run = "TERMINATED_EXEC_FAIL"; break
                else: logging.info(f"Step {current_step_for_log}: Action executed successfully.")

                time.sleep(float(self.cfg.WAIT_AFTER_ACTION)) # Wait after action execution and logging

            # End of while loop
            if not self.is_shutting_down : # If loop exited due to limits, not error/interrupt
                final_status_for_run = "COMPLETED_LIMITS" if self._should_terminate() else "COMPLETED_NORMALLY" # Should be caught by _should_terminate for limits
                if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS: final_status_for_run = "COMPLETED_MAX_STEPS"
                elif self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and (time.time() - self.crawl_start_time) >= self.cfg.MAX_CRAWL_DURATION_SECONDS: final_status_for_run = "COMPLETED_MAX_DURATION"
                else: final_status_for_run = "COMPLETED_UNKNOWN_REASON" # Should ideally not happen
                logging.info(f"Crawl loop finished based on limits or other condition. Status: {final_status_for_run}")
                print(f"{UI_END_PREFIX}{final_status_for_run.upper()}")


        except WebDriverException as e:
            logging.critical(f"WebDriverException in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_WEBDRIVER_EXCEPTION"
            print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)}")
            self.is_shutting_down = True
        except RuntimeError as e:
            logging.critical(f"RuntimeError in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_RUNTIME_ERROR"
            print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)}")
            self.is_shutting_down = True
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt received in run_async. Initiating shutdown...")
            final_status_for_run = "INTERRUPTED_KEYBOARD"
            print(f"{UI_END_PREFIX}{final_status_for_run}")
            self.is_shutting_down = True
        except Exception as e:
            logging.critical(f"Unhandled exception in run_async: {e}", exc_info=True)
            final_status_for_run = "CRASH_UNHANDLED_EXCEPTION"
            print(f"{UI_END_PREFIX}{final_status_for_run}: {str(e)}")
            self.is_shutting_down = True
        finally:
            logging.info(f"Exited crawl loop or encountered critical error. Final run status before cleanup: {final_status_for_run}")
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
        """Synchronous public method to start the Appium App Crawler."""
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
            if not self.is_shutting_down and not (hasattr(self, '_cleanup_called') and self._cleanup_called):
                self.perform_full_cleanup() # Attempt cleanup if not already done
        finally:
            logging.info("AppCrawler.run() synchronous wrapper finished.")