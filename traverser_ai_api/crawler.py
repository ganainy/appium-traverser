#!/usr/bin/env python3
# crawler.py
import asyncio
import csv  # For AI output logging
import json
import logging
import os
import re
import threading  # For logging thread IDs if needed
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    from traverser_ai_api.config import Config
except ImportError:
    from traverser_ai_api.config import Config
try:
    from traverser_ai_api import utils
except ImportError:
    import utils

try:
    from traverser_ai_api.agent_assistant import AgentAssistant
except ImportError:
    from agent_assistant import AgentAssistant
try:
    from traverser_ai_api.appium_driver import AppiumDriver
except ImportError:
    from appium_driver import AppiumDriver
try:
    from traverser_ai_api.screen_state_manager import ScreenRepresentation, ScreenStateManager
except ImportError:
    from screen_state_manager import ScreenRepresentation, ScreenStateManager
try:
    from traverser_ai_api.database import DatabaseManager
except ImportError:
    from database import DatabaseManager
try:
    from traverser_ai_api.action_mapper import ActionMapper
except ImportError:
    from action_mapper import ActionMapper
try:
    from traverser_ai_api.traffic_capture_manager import TrafficCaptureManager
except ImportError:
    from traffic_capture_manager import TrafficCaptureManager
try:
    from traverser_ai_api.action_executor import ActionExecutor
except ImportError:
    from action_executor import ActionExecutor
try:
    from traverser_ai_api.app_context_manager import AppContextManager
except ImportError:
    from app_context_manager import AppContextManager
try:
    from traverser_ai_api.screenshot_annotator import ScreenshotAnnotator
except ImportError:
    from screenshot_annotator import ScreenshotAnnotator

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webelement import WebElement

UI_STATUS_PREFIX = "UI_STATUS:"
UI_STEP_PREFIX = "UI_STEP:"
UI_ACTION_PREFIX = "UI_ACTION:"
UI_SCREENSHOT_PREFIX = "UI_SCREENSHOT:"
UI_ANNOTATED_SCREENSHOT_PREFIX = "UI_ANNOTATED_SCREENSHOT:"
UI_FOCUS_PREFIX = "UI_FOCUS:"
UI_END_PREFIX = "UI_END:"

class AppCrawler:
    def __init__(self, app_config: Config):
        self.cfg = app_config
        logging.debug(f"AppCrawler initializing with App Package: {self.cfg.APP_PACKAGE}")

        required_attrs_for_crawler = [
            'MCP_SERVER_URL', 'NEW_COMMAND_TIMEOUT', 'APPIUM_IMPLICIT_WAIT',
            'GEMINI_API_KEY', 'DEFAULT_MODEL_TYPE', 'AI_SAFETY_SETTINGS',
            'DB_NAME', 'APP_PACKAGE', 'APP_ACTIVITY', 'SHUTDOWN_FLAG_PATH',
            'PAUSE_FLAG_PATH',
            'MAX_CRAWL_STEPS', 'MAX_CRAWL_DURATION_SECONDS',
            'MAX_CONSECUTIVE_AI_FAILURES', 'MAX_CONSECUTIVE_MAP_FAILURES',
            'MAX_CONSECUTIVE_EXEC_FAILURES', 'MAX_CONSECUTIVE_CONTEXT_FAILURES',
            'WAIT_AFTER_ACTION', 'ALLOWED_EXTERNAL_PACKAGES', 'XML_SNIPPET_MAX_LEN', 'SCREENSHOTS_DIR', 'ANNOTATED_SCREENSHOTS_DIR',
            'ENABLE_TRAFFIC_CAPTURE', 'CONTINUE_EXISTING_RUN', 'OUTPUT_DATA_DIR'
        ]
        for attr in required_attrs_for_crawler:
            val = getattr(self.cfg, attr, None)
            if val is None:
                if attr == 'ALLOWED_EXTERNAL_PACKAGES' and isinstance(getattr(self.cfg, attr, None), list): continue
                if attr == 'AI_SAFETY_SETTINGS' and isinstance(getattr(self.cfg, attr, None), dict): continue
                raise ValueError(f"AppCrawler: Critical configuration '{attr}' is missing or None.")
        if not self.cfg.SHUTDOWN_FLAG_PATH:
            raise ValueError("AppCrawler: Critical configuration 'SHUTDOWN_FLAG_PATH' must be set.")
        if not self.cfg.PAUSE_FLAG_PATH:
            raise ValueError("AppCrawler: Critical configuration 'PAUSE_FLAG_PATH' must be set.")


        self.driver = AppiumDriver(app_config=self.cfg)
        self.db_manager = DatabaseManager(app_config=self.cfg)
        self.screen_state_manager = ScreenStateManager(db_manager=self.db_manager, driver=self.driver, app_config=self.cfg)
        # Strategy ordering tuned for speed and reliability:
        # 1) Full resource-id (ID)
        # 2) Accessibility ID
        # 3) Text (case-insensitive contains)
        # 4) Class contains (allowed even when DISABLE_EXPENSIVE_XPATH is True)
        # Heavier XPath heuristics (xpath contains, flexible) remain gated by DISABLE_EXPENSIVE_XPATH.
        self.element_finding_strategies: List[Tuple[str, Optional[str], str]] = [
            ('id', 'ID', "ID"),
            ('acc_id', 'ACCESSIBILITY_ID', "Accessibility ID"),
            ('text_case_insensitive', 'XPATH', "Text Case Insensitive"),
            ('content_desc_case_insensitive', 'XPATH', "Content-Desc Case Insensitive"),
            ('class_contains', 'XPATH', "Class Contains Match"),
        ]
        # Add heavier XPath heuristics only if not disabled
        if not getattr(self.cfg, 'DISABLE_EXPENSIVE_XPATH', False):
            self.element_finding_strategies.extend([
                ('xpath_contains', 'XPATH', "XPath Contains Match"),
                ('xpath_flexible', 'XPATH', "XPath Flexible Match")
            ])
        self.action_mapper = ActionMapper(driver=self.driver, element_finding_strategies=self.element_finding_strategies, app_config=self.cfg)
        self.traffic_capture_manager = TrafficCaptureManager(driver=self.driver, app_config=self.cfg)
        self.action_executor = ActionExecutor(driver=self.driver, app_config=self.cfg)
        self.app_context_manager = AppContextManager(driver=self.driver, app_config=self.cfg)
        self.screenshot_annotator = ScreenshotAnnotator(driver=self.driver, app_config=self.cfg)
        
        # Create the agent tools
        from .agent_tools import AgentTools
        self.agent_tools = AgentTools(
            driver=self.driver,
            config=self.cfg
        )
        
        # Initialize the AI assistant with agent tools
        self.ai_assistant = AgentAssistant(app_config=self.cfg, agent_tools=self.agent_tools)

        self.consecutive_ai_failures = 0
        self.consecutive_map_failures = 0
        self._last_action_description: str = "CRAWL_START"
        self.previous_composite_hash: Optional[str] = None
        self.run_id: Optional[int] = None
        self.crawl_steps_taken: int = 0
        self.crawl_start_time: float = 0.0
        self.total_paused_time: float = 0.0
        self._is_video_recording: bool = False

        self.last_action_feedback_for_ai: Optional[str] = None
        self.consecutive_no_op_failures: int = 0
        self.fallback_action_index: int = 0
        self.force_image_context_next_step: bool = False

        # Cache for simplified XML to avoid repeated heavy processing when the screen hash is unchanged
        self.simplified_xml_cache: Dict[str, str] = {}
        self.max_xml_cache_entries: int = 200

        # Track how many times the same action has been attempted per screen to prevent loops
        self.action_repeat_counts: Dict[str, Dict[str, int]] = {}
        self.max_repeat_tracking_screens: int = 200

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

        logging.debug("AppCrawler initialized successfully.")

    def _should_terminate(self) -> bool:
        if self.is_shutting_down:
            logging.debug("Termination check: Shutdown already initiated.")
            return True
        if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            logging.debug(f"Termination check: External shutdown flag found: {self.cfg.SHUTDOWN_FLAG_PATH}.")
            self.is_shutting_down = True
            print(f"{UI_END_PREFIX}SHUTDOWN_FLAG_DETECTED")
            return True

        if self.cfg.CRAWL_MODE == 'steps':
            if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS:
                logging.debug(f"Termination check: Reached max steps ({self.cfg.MAX_CRAWL_STEPS}) in 'steps' mode.")
                if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_STEPS_REACHED")
                self.is_shutting_down = True
                return True
        elif self.cfg.CRAWL_MODE == 'time':
            # Adjust elapsed time calculation to account for pause time
            effective_elapsed_time = (time.time() - self.crawl_start_time) - self.total_paused_time
            if self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and effective_elapsed_time >= self.cfg.MAX_CRAWL_DURATION_SECONDS:
                logging.debug(f"Termination check: Reached max duration ({self.cfg.MAX_CRAWL_DURATION_SECONDS}s) in 'time' mode. Effective elapsed time: {effective_elapsed_time:.2f}s")
                if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_DURATION_REACHED")
                self.is_shutting_down = True
                return True
        else:
            logging.warning(f"Unknown CRAWL_MODE: '{self.cfg.CRAWL_MODE}'. Checking both step and time limits as a fallback.")
            if self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS:
                logging.debug(f"Termination check (fallback): Reached max steps ({self.cfg.MAX_CRAWL_STEPS}).")
                if not self.is_shutting_down: print(f"{UI_END_PREFIX}MAX_STEPS_REACHED")
                self.is_shutting_down = True
                return True
            effective_elapsed_time = (time.time() - self.crawl_start_time) - self.total_paused_time
            if self.cfg.MAX_CRAWL_DURATION_SECONDS is not None and effective_elapsed_time >= self.cfg.MAX_CRAWL_DURATION_SECONDS:
                logging.debug(f"Termination check (fallback): Reached max duration ({self.cfg.MAX_CRAWL_DURATION_SECONDS}s).")
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

        logging.debug("Performing full cleanup for AppCrawler...")
        self.is_shutting_down = True
        self._cleanup_called = True

        if self.cfg.ENABLE_TRAFFIC_CAPTURE and self.traffic_capture_manager and self.traffic_capture_manager.is_capturing():
            logging.debug("Ensuring traffic capture stopped and pulled...")
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
                logging.debug("Quitting Appium driver session...")
                self.driver.disconnect()
            except Exception as e_driver:
                logging.error(f"Error during Appium driver quit: {e_driver}", exc_info=True)
            finally:
                self.driver = None
        if self.db_manager:
            try:
                logging.debug("Closing database connection...")
                self.db_manager.close()
            except Exception as e_db:
                logging.error(f"Error closing database: {e_db}", exc_info=True)
            finally:
                self.db_manager = None
        if self.cfg.SHUTDOWN_FLAG_PATH and os.path.exists(self.cfg.SHUTDOWN_FLAG_PATH):
            try:
                os.remove(self.cfg.SHUTDOWN_FLAG_PATH)
                logging.debug(f"Cleaned up shutdown flag: {self.cfg.SHUTDOWN_FLAG_PATH}")
            except OSError as e_flag:
                logging.warning(f"Could not remove shutdown flag: {e_flag}")

        if self.run_id is not None and hasattr(self, 'db_manager') and self.db_manager is not None :
            current_status_for_db = "COMPLETED_CLEANUP"
            if self.consecutive_ai_failures >= self.cfg.MAX_CONSECUTIVE_AI_FAILURES: current_status_for_db = "TERMINATED_MAX_AI_FAIL_CLEANUP"
            elif self.consecutive_map_failures >= self.cfg.MAX_CONSECUTIVE_MAP_FAILURES: current_status_for_db = "TERMINATED_MAX_MAP_FAIL_CLEANUP"
            self.db_manager.update_run_status(self.run_id, current_status_for_db, time.strftime("%Y-%m-%d %H:%M:%S"))

        logging.debug("AppCrawler full cleanup process finished.")


    async def _initialize_run(self) -> bool:
        """Handles the setup and initialization for a crawl run. Returns True on success."""
        if not self.db_manager:
            logging.critical("DatabaseManager not available.")
            print(f"{UI_END_PREFIX}FAILURE_DB_NOT_INIT")
            return False

        if self.run_id is None:
            self.run_id = self.db_manager.get_or_create_run_info(str(self.cfg.APP_PACKAGE), str(self.cfg.APP_ACTIVITY))
        
        if self.run_id is None:
            logging.critical("Failed to get or create run ID.")
            print(f"{UI_END_PREFIX}FAILURE_RUN_ID")
            return False
            
        self.db_manager.update_run_status(self.run_id, "INITIALIZING")
        logging.debug(f"Starting/Continuing crawl run ID: {self.run_id} for app: {self.cfg.APP_PACKAGE}")
        print(f"{UI_STATUS_PREFIX}INITIALIZING_CRAWL_RUN_{self.run_id}")

        is_continuation_run = bool(self.cfg.CONTINUE_EXISTING_RUN and self.db_manager.get_step_count_for_run(self.run_id) > 0)
        self.screen_state_manager.initialize_for_run(
            run_id=self.run_id, app_package=str(self.cfg.APP_PACKAGE),
            start_activity=str(self.cfg.APP_ACTIVITY), is_continuation=is_continuation_run
        )
        self.crawl_steps_taken = self.screen_state_manager.current_run_latest_step_number
        logging.debug(f"Crawl start step count set to {self.crawl_steps_taken}.")

        self.crawl_start_time = time.time()
        self.is_shutting_down = False

        if not self.driver or not self.driver.connect():
            logging.critical("Failed to connect to Appium.")
            return False
        if not self.app_context_manager.launch_and_verify_app():
            logging.critical("Failed to launch/verify target app.")
            return False

        if self.cfg.ENABLE_VIDEO_RECORDING:
            try:
                self.driver.start_video_recording()
                self._is_video_recording = True
            except Exception as e:
                logging.error(f"Failed to start video recording: {e}")
                self._is_video_recording = False

        if self.cfg.ENABLE_TRAFFIC_CAPTURE:
            pcap_filename_template = f"{self.cfg.APP_PACKAGE}_run{self.run_id}_step{{step_num}}.pcap"
            if not await self.traffic_capture_manager.start_capture_async(filename_template=pcap_filename_template):
                logging.warning("Failed to start traffic capture.")
            else:
                logging.debug("Traffic capture started.")
        
        self.db_manager.update_run_status(self.run_id, "RUNNING")
        return True

    async def _handle_pause_if_requested(self):
        """Checks for the pause flag and holds execution while it exists."""
        if self.cfg.PAUSE_FLAG_PATH and os.path.exists(self.cfg.PAUSE_FLAG_PATH):
            pause_start_time = time.time()
            logging.debug("Pause flag detected. Pausing execution...")
            print(f"{UI_STATUS_PREFIX}PAUSED")
            while os.path.exists(self.cfg.PAUSE_FLAG_PATH):
                if self.driver:
                    logging.debug("Sending heartbeat to Appium server to keep session alive...")
                    self.driver.get_window_size()
                await asyncio.sleep(60)
            
            pause_duration = time.time() - pause_start_time
            self.total_paused_time += pause_duration
            logging.debug(f"Resume signal received. Paused for {pause_duration:.2f}s. Total paused time: {self.total_paused_time:.2f}s. Resuming execution...")
            print(f"{UI_STATUS_PREFIX}RESUMING")

    async def _get_next_action(self, definitive_screen_repr: ScreenRepresentation, visit_info: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[float], Optional[int]]:
        """Decides whether to use a fallback action or query the AI using the agent-based approach."""
        ai_action_suggestion = None
        ai_time_taken = None
        total_tokens = None

        max_no_op = getattr(self.cfg, 'MAX_CONSECUTIVE_NO_OP_FAILURES', 3)
        if self.consecutive_no_op_failures >= max_no_op:
            logging.warning(f"Reached {self.consecutive_no_op_failures} consecutive no-op/failed actions. Using fallback sequence.")
            fallback_actions = getattr(self.cfg, 'FALLBACK_ACTIONS_SEQUENCE', [])
            if fallback_actions:
                action_to_try = fallback_actions[self.fallback_action_index % len(fallback_actions)]
                ai_action_suggestion = action_to_try.copy()
                ai_action_suggestion['reasoning'] = f"FALLBACK ACTION: Triggered after {self.consecutive_no_op_failures} consecutive failures."
                self.fallback_action_index += 1
                logging.debug(f"Selected fallback action: {ai_action_suggestion}")
            else:
                logging.error("Fallback sequence triggered, but FALLBACK_ACTIONS_SEQUENCE is empty in config.")
        
        if ai_action_suggestion is None:
            xml_content = definitive_screen_repr.xml_content or ""
            filtered_xml = utils.filter_xml_by_allowed_packages(xml_content, str(self.cfg.APP_PACKAGE), self.cfg.ALLOWED_EXTERNAL_PACKAGES)
            # Use cache for simplified XML based on screen hash, provider, and max snippet length
            cache_key = f"{definitive_screen_repr.composite_hash}:{self.cfg.AI_PROVIDER}:{int(self.cfg.XML_SNIPPET_MAX_LEN)}"
            simplified_xml = self.simplified_xml_cache.get(cache_key)
            if simplified_xml is None:
                simplified_xml = utils.simplify_xml_for_ai(filtered_xml, int(self.cfg.XML_SNIPPET_MAX_LEN), self.cfg.AI_PROVIDER)
                # Maintain a simple cap on cache size
                if len(self.simplified_xml_cache) >= getattr(self, 'max_xml_cache_entries', 200):
                    try:
                        self.simplified_xml_cache.pop(next(iter(self.simplified_xml_cache)))
                    except StopIteration:
                        pass
                self.simplified_xml_cache[cache_key] = simplified_xml
            
            # Check if image context is enabled, or forced for a single step
            enable_image_context = (getattr(self.cfg, 'ENABLE_IMAGE_CONTEXT', True) or self.force_image_context_next_step)
            
            if enable_image_context and definitive_screen_repr.screenshot_bytes and self.loop:
                try:
                    # Use the agent-based approach
                    agent_result = None
                    if definitive_screen_repr.screenshot_bytes is not None:  # Ensure screenshot is not None
                        agent_result = await self.loop.run_in_executor(
                            self.default_executor,
                            lambda: self.ai_assistant.plan_and_execute(
                                definitive_screen_repr.screenshot_bytes,
                                simplified_xml,
                                visit_info.get("previous_actions_on_this_state", []),
                                visit_info.get("visit_count_this_run", 1),
                                definitive_screen_repr.composite_hash,
                                self.last_action_feedback_for_ai
                            )
                        )
                    
                    if agent_result:
                        action_data, time_taken, token_count, success = agent_result
                        ai_time_taken = time_taken
                        total_tokens = token_count
                        
                        # If the action was already executed by the agent, record the result
                        if success:
                            ai_action_suggestion = action_data
                            action_str = utils.generate_action_description(
                                action_data.get('action', 'unknown'),
                                None,
                                action_data.get('input_text'),
                                action_data.get('target_identifier')
                            )
                            self.screen_state_manager.record_action_taken_from_screen(
                                definitive_screen_repr.composite_hash, 
                                f"{action_str} (Success: {success}) [Agent Executed]"
                            )
                            # Reset the failure counters since the agent successfully executed an action
                            self.consecutive_ai_failures = 0
                            self.consecutive_map_failures = 0
                            self.action_executor.reset_consecutive_failures()
                        else:
                            # If execution failed but we have a valid action, return it for standard execution
                            ai_action_suggestion = action_data
                            
                except Exception as e:
                    logging.error(f"Error in agent-based execution: {e}", exc_info=True)
                finally:
                    # Reset forced image context after a single attempt
                    if self.force_image_context_next_step:
                        self.force_image_context_next_step = False
            elif not enable_image_context:
                # Use text-only analysis without image
                if self.loop:
                    try:
                        agent_result = await self.loop.run_in_executor(
                            self.default_executor,
                            lambda: self.ai_assistant.plan_and_execute(
                                None,  # No screenshot bytes
                                simplified_xml,
                                visit_info.get("previous_actions_on_this_state", []),
                                visit_info.get("visit_count_this_run", 1),
                                definitive_screen_repr.composite_hash,
                                self.last_action_feedback_for_ai
                            )
                        )
                        
                        if agent_result:
                            action_data, time_taken, token_count, success = agent_result
                            ai_time_taken = time_taken
                            total_tokens = token_count
                            
                            # If the action was already executed by the agent, record the result
                            if success:
                                ai_action_suggestion = action_data
                                action_str = utils.generate_action_description(
                                    action_data.get('action', 'unknown'),
                                    None,
                                    action_data.get('input_text'),
                                    action_data.get('target_identifier')
                                )
                                self.screen_state_manager.record_action_taken_from_screen(
                                    definitive_screen_repr.composite_hash, 
                                    f"{action_str} (Success: {success}) [Agent Executed - Text Only]"
                                )
                                # Reset the failure counters since the agent successfully executed an action
                                self.consecutive_ai_failures = 0
                                self.consecutive_map_failures = 0
                                self.action_executor.reset_consecutive_failures()
                            else:
                                # If execution failed but we have a valid action, return it for standard execution
                                ai_action_suggestion = action_data
                                
                    except Exception as e:
                        logging.error(f"Error in agent-based execution (text-only): {e}", exc_info=True)
                else:
                    logging.error("Event loop not available, cannot call AI for text-only analysis.")
            elif not definitive_screen_repr.screenshot_bytes:
                logging.error("Screenshot bytes are None, cannot call AI.")
            elif not self.loop:
                 logging.error("Event loop not available, cannot call AI.")
        
        return ai_action_suggestion, ai_time_taken, total_tokens

    async def _process_action_result(self, execution_success: bool, definitive_screen_repr: ScreenRepresentation, ai_suggestion: Dict[str, Any], action_details: Dict[str, Any], ai_time_taken: Optional[float], total_tokens: Optional[int]):
        """Handles the outcome of an action, updates feedback, and logs the step."""
        if not self.run_id:
            logging.error("Cannot process action result without a valid run_id.")
            return

        next_state_screen_id_for_log = None
        if execution_success:
            await asyncio.sleep(float(self.cfg.WAIT_AFTER_ACTION) / 2)
            next_candidate_repr = self.screen_state_manager.get_current_screen_representation(self.run_id, self.crawl_steps_taken)
            if next_candidate_repr:
                definitive_next_screen, _ = self.screen_state_manager.process_and_record_state(next_candidate_repr, self.run_id, self.crawl_steps_taken)
                next_state_screen_id_for_log = definitive_next_screen.id
                
                if definitive_next_screen.composite_hash == self.previous_composite_hash:
                    self.last_action_feedback_for_ai = f"NO CHANGE: Your action '{ai_suggestion.get('action')}' was executed, but the screen did not change. You MUST suggest a different action."
                    logging.warning(self.last_action_feedback_for_ai)
                    self.consecutive_no_op_failures += 1
                    # Force image context on next step to help break no-change loops
                    self.force_image_context_next_step = True
                else:
                    self.last_action_feedback_for_ai = "SUCCESS: Your last action was successful."
                    self.consecutive_no_op_failures = 0
                    self.fallback_action_index = 0
                    # Clear forced image context after progression
                    if self.force_image_context_next_step:
                        self.force_image_context_next_step = False
            else:
                 self.last_action_feedback_for_ai = "UNKNOWN: Action succeeded but the next state could not be determined."
                 self.consecutive_no_op_failures += 1
                 self.force_image_context_next_step = True
        else:
            error_msg = self.action_executor.last_error_message or "Unknown execution error"
            self.last_action_feedback_for_ai = f"EXECUTION FAILED: Your action '{ai_suggestion.get('action')}' failed with error: {error_msg}. You MUST suggest a different action."
            logging.error(self.last_action_feedback_for_ai)
            self.consecutive_no_op_failures += 1
            # Optionally force image context to assist recovery
            self.force_image_context_next_step = True
        
        action_str_log = utils.generate_action_description(ai_suggestion.get('action', 'unknown'), None, ai_suggestion.get('input_text'), ai_suggestion.get('target_identifier'))
        
        if self.db_manager:
            self.db_manager.insert_step_log(
                run_id=self.run_id, step_number=self.crawl_steps_taken,
                from_screen_id=definitive_screen_repr.id, to_screen_id=next_state_screen_id_for_log,
                action_description=action_str_log,
                ai_suggestion_json=json.dumps(ai_suggestion),
                mapped_action_json=json.dumps(action_details, default=lambda o: "<WebElement>" if isinstance(o, WebElement) else str(o)),
                execution_success=execution_success,
                error_message=self.action_executor.last_error_message if not execution_success else None,
                ai_response_time=(ai_time_taken * 1000 if ai_time_taken is not None else None),
                total_tokens=total_tokens
            )
        self.screen_state_manager.record_action_taken_from_screen(definitive_screen_repr.composite_hash, f"{action_str_log} (Success: {execution_success})")

    async def _perform_one_crawl_step(self) -> Tuple[str, Optional[str]]:
        """Executes a single step of the crawl, from state capture to action execution."""
        self.crawl_steps_taken += 1
        current_step_for_log = self.crawl_steps_taken
        logging.debug(f"--- Crawl Step {current_step_for_log} (Run ID: {self.run_id}) ---")
        print(f"{UI_STEP_PREFIX}{current_step_for_log}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Checking app context...")

        if not self.run_id:
            return "BREAK", "CRITICAL_ERROR_NO_RUN_ID"

        if not self.app_context_manager.ensure_in_app():
            logging.error(f"Step {current_step_for_log}: Failed to ensure app context. Failures: {self.app_context_manager.consecutive_context_failures}")
            if self._should_terminate(): return "BREAK", "TERMINATED_CONTEXT_FAIL"
            await asyncio.sleep(1)
            return "CONTINUE", None

        print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Getting screen state...")
        screen = self.screen_state_manager.get_current_screen_representation(self.run_id, current_step_for_log)
        if not screen or not screen.screenshot_bytes:
            self._handle_mapping_failure() # Treat as a mapping failure
            # Force image context on next step to assist mapping on tough screens
            self.force_image_context_next_step = True
            if self.db_manager:
                self.db_manager.insert_step_log(self.run_id, current_step_for_log, None, None, "GET_SCREEN_STATE", None, None, False, "Failed to get valid screen state", None, None)
            if self._should_terminate(): return "BREAK", "TERMINATED_STATE_FAIL"
            await asyncio.sleep(float(self.cfg.WAIT_AFTER_ACTION))
            return "CONTINUE", None

        screen, visit_info = self.screen_state_manager.process_and_record_state(screen, self.run_id, current_step_for_log)
        if screen.screenshot_path: print(f"{UI_SCREENSHOT_PREFIX}{screen.screenshot_path}")
        self.previous_composite_hash = screen.composite_hash
        logging.debug(f"Step {current_step_for_log}: State Processed. Screen ID: {screen.id}, Hash: '{screen.composite_hash}'")
        
        print(f"{UI_STATUS_PREFIX}Step {current_step_for_log}: Deciding next action...")
        ai_suggestion, ai_time, tokens = await self._get_next_action(screen, visit_info)

        if not ai_suggestion:
            self._handle_ai_failure()
            if self.db_manager:
                self.db_manager.insert_step_log(self.run_id, current_step_for_log, screen.id, None, "AI_ACTION_DECISION", None, None, False, "AI failed to return a suggestion", ai_time, tokens)
            if self._should_terminate(): return "BREAK", "TERMINATED_AI_FAIL"
            return "CONTINUE", None
        self.consecutive_ai_failures = 0
        
        # Enforce repeated action cap per screen to reduce loops
        repeat_cap = getattr(self.cfg, 'MAX_SAME_ACTION_REPEAT', 3)
        if ai_suggestion:
            current_hash = screen.composite_hash
            suggested_action = ai_suggestion.get('action', 'unknown')
            prev_counts = self.action_repeat_counts.get(current_hash, {})
            if prev_counts.get(suggested_action, 0) >= repeat_cap:
                logging.warning(f"Repeat cap reached for action '{suggested_action}' on screen {current_hash}. Selecting fallback action.")
                fallback_actions = getattr(self.cfg, 'FALLBACK_ACTIONS_SEQUENCE', [])
                if fallback_actions:
                    action_to_try = fallback_actions[self.fallback_action_index % len(fallback_actions)]
                    ai_suggestion = action_to_try.copy()
                    ai_suggestion['reasoning'] = f"FALLBACK ACTION: Repeat limit reached for '{suggested_action}'."
                    self.fallback_action_index += 1
                    # Force image context on the next step to help break loops when repeat cap triggers
                    self.force_image_context_next_step = True

        action_str = utils.generate_action_description(ai_suggestion.get('action', 'unknown'), None, ai_suggestion.get('input_text'), ai_suggestion.get('target_identifier'))
        logging.debug(f"Step {current_step_for_log}: AI suggested: {action_str}. Reasoning: {ai_suggestion.get('reasoning')}")
        print(f"{UI_ACTION_PREFIX}{action_str}\n{UI_STATUS_PREFIX}Step {current_step_for_log}: Mapping and executing...")

        # Increment repeat counter for the attempted action on this screen
        try:
            if screen.composite_hash:
                # Prune tracking size if needed
                if len(self.action_repeat_counts) >= getattr(self, 'max_repeat_tracking_screens', 200):
                    try:
                        self.action_repeat_counts.pop(next(iter(self.action_repeat_counts)))
                    except StopIteration:
                        pass
                counts = self.action_repeat_counts.setdefault(screen.composite_hash, {})
                action_name_for_count = ai_suggestion.get('action', 'unknown')
                counts[action_name_for_count] = counts.get(action_name_for_count, 0) + 1
        except Exception:
            pass

        action_details = self.action_mapper.map_ai_action_to_appium(ai_suggestion, screen.xml_content)
        if not action_details:
            self._handle_mapping_failure()
            # Force image context on next step to assist mapping
            self.force_image_context_next_step = True
            if self.db_manager:
                 self.db_manager.insert_step_log(self.run_id, current_step_for_log, screen.id, None, action_str, json.dumps(ai_suggestion), None, False, "Failed to map AI action to element", ai_time, tokens)
            if self._should_terminate(): return "BREAK", "TERMINATED_MAP_FAIL"
            return "CONTINUE", None
        self.consecutive_map_failures = 0

        if screen.screenshot_bytes:
            annotated_path = self.screenshot_annotator.save_annotated_screenshot(screen.screenshot_bytes, current_step_for_log, screen.id, ai_suggestion)
            if annotated_path: print(f"{UI_ANNOTATED_SCREENSHOT_PREFIX}{annotated_path}")

        success = self.action_executor.execute_action(action_details)
        await self._process_action_result(success, screen, ai_suggestion, action_details, ai_time, tokens)

        if not success and self._should_terminate():
            return "BREAK", "TERMINATED_EXEC_FAIL"
        
        await asyncio.sleep(float(self.cfg.WAIT_AFTER_ACTION))
        return "CONTINUE", None

    async def _finalize_run(self, status: str):
        """Wraps up the crawl run by stopping services and updating status."""
        logging.debug(f"Finalizing run. Status: {status}")
        print(f"{UI_STATUS_PREFIX}Crawl loop ended. Finalizing run {self.run_id} with status {status}...")

        if self._is_video_recording:
            logging.info("Stopping video recording...")
            try:
                video_data = self.driver.stop_video_recording()
                if video_data:
                    video_filename = f"crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                    if self.cfg.VIDEO_RECORDING_DIR:
                        video_path = os.path.join(self.cfg.VIDEO_RECORDING_DIR, video_filename)
                        self.driver.save_video_recording(video_data, video_path)
                        logging.info(f"Video saved to {video_path}")
                    else:
                        logging.error("VIDEO_RECORDING_DIR not set, cannot save video.")
                else:
                    logging.warning("Video recording data was empty.")
            except Exception as e:
                logging.error(f"Error stopping or saving video recording: {e}")

        if self.cfg.ENABLE_TRAFFIC_CAPTURE and self.traffic_capture_manager.is_capturing():
            logging.debug("Stopping and pulling final traffic capture...")
            pcap_file = await self.traffic_capture_manager.stop_capture_and_pull_async(self.run_id or 0, self.crawl_steps_taken)
            if pcap_file: logging.debug(f"Final traffic capture saved to: {pcap_file}")
            else: logging.warning("Failed to save final traffic capture.")
            
            # MobSF Integration - Run static analysis at the end of the crawl if enabled
        if hasattr(self.cfg, 'ENABLE_MOBSF_ANALYSIS') and self.cfg.ENABLE_MOBSF_ANALYSIS:
            logging.debug("MobSF static analysis enabled. Starting analysis...")
            print(f"{UI_STATUS_PREFIX}Starting MobSF static analysis...")
            
            try:
                # Import here to avoid circular imports
                from mobsf_manager import MobSFManager

                # Create MobSF manager and run analysis
                mobsf_manager = MobSFManager(self.cfg)
                
                # Since perform_complete_scan isn't async, use run_in_executor
                if self.loop:
                    try:
                        # Execute in thread pool to avoid blocking
                        success, result = await self.loop.run_in_executor(
                            self.default_executor, 
                            lambda: mobsf_manager.perform_complete_scan(str(self.cfg.APP_PACKAGE))
                        )
                    except Exception as e:
                        logging.error(f"Error running MobSF analysis in executor: {e}", exc_info=True)
                        success, result = False, {"error": f"Analysis execution error: {str(e)}"}
                else:
                    # Fallback to direct execution if no event loop
                    success, result = mobsf_manager.perform_complete_scan(str(self.cfg.APP_PACKAGE))
                
                if success:
                    logging.debug(f"MobSF analysis completed successfully. PDF report: {result.get('pdf_report')}")
                    print(f"{UI_STATUS_PREFIX}MobSF analysis completed successfully.")
                    
                    # Update the run status with MobSF results if we have a database connection
                    if self.run_id and self.db_manager:
                        try:
                            # Store the file paths in the run_meta table
                            meta_data = {
                                "mobsf_pdf_report": result.get('pdf_report', ''),
                                "mobsf_json_report": result.get('json_report', ''),
                                "mobsf_file_hash": result.get('file_hash', '')
                            }
                            
                            # Try to extract and store the security score
                            if 'security_score' in result and result['security_score'] != "Unknown":
                                security_score = result['security_score']
                                if isinstance(security_score, dict):
                                    for category, score in security_score.items():
                                        if isinstance(score, dict) and 'value' in score:
                                            meta_data[f"mobsf_score_{category}"] = score['value']
                            
                            # Save meta data to database
                            self.db_manager.update_run_meta(self.run_id, json.dumps(meta_data))
                            logging.debug("MobSF analysis results saved to database.")
                        except Exception as e:
                            logging.error(f"Error saving MobSF results to database: {e}")
                else:
                    logging.error(f"MobSF analysis failed: {result.get('error', 'Unknown error')}")
                    print(f"{UI_STATUS_PREFIX}MobSF analysis failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                logging.error(f"Error during MobSF analysis: {e}", exc_info=True)
                print(f"{UI_STATUS_PREFIX}Error during MobSF analysis: {str(e)}")

        if self.run_id and self.db_manager:
            self.db_manager.update_run_status(self.run_id, status, time.strftime("%Y-%m-%d %H:%M:%S"))
        
        self.perform_full_cleanup()
        logging.debug(f"AppCrawler run_async finished for Run ID: {self.run_id}. Final DB status: {status}")

    def _determine_completion_status(self) -> str:
        """Determines the final status string if the loop completes without a failure-based termination."""
        if self.cfg.CRAWL_MODE == 'steps' and self.cfg.MAX_CRAWL_STEPS is not None and self.crawl_steps_taken >= self.cfg.MAX_CRAWL_STEPS:
            return "COMPLETED_MAX_STEPS"
        elif self.cfg.CRAWL_MODE == 'time' and self.cfg.MAX_CRAWL_DURATION_SECONDS is not None:
             return "COMPLETED_MAX_DURATION"
        return "COMPLETED_UNEXPECTED_EXIT"

    def _handle_critical_exception(self, e: Exception) -> str:
        """Logs critical exceptions and determines the appropriate final status."""
        if isinstance(e, WebDriverException):
            logging.critical(f"WebDriverException in run_async: {e}", exc_info=True)
            status = "CRASH_WEBDRIVER_EXCEPTION"
        elif isinstance(e, RuntimeError):
            logging.critical(f"RuntimeError in run_async: {e}", exc_info=True)
            status = "CRASH_RUNTIME_ERROR"
        elif isinstance(e, KeyboardInterrupt):
            logging.warning("KeyboardInterrupt received in run_async. Initiating shutdown...")
            status = "INTERRUPTED_KEYBOARD"
        else:
            logging.critical(f"Unhandled exception in run_async: {e}", exc_info=True)
            status = "CRASH_UNHANDLED_EXCEPTION"
        
        if not self.is_shutting_down:
            print(f"{UI_END_PREFIX}{status}: {str(e)[:100]}")
        self.is_shutting_down = True
        return status
        
    async def run_async(self):
        """Main asynchronous entry point for the crawler's execution logic."""
        self._cleanup_called = False
        final_status = "STARTED_ERROR"
        self.loop = asyncio.get_running_loop() # Get loop for executor calls

        try:
            if await self._initialize_run():
                final_status = "RUNNING"
                while not self._should_terminate():
                    await self._handle_pause_if_requested()
                    result, status_update = await self._perform_one_crawl_step()
                    if result == "BREAK":
                        if status_update:
                            final_status = status_update
                        break
                
                if not self.is_shutting_down:
                    final_status = self._determine_completion_status()
            else:
                final_status = "FAILED_INITIALIZATION"
        
        except Exception as e:
            final_status = self._handle_critical_exception(e)
        finally:
            await self._finalize_run(final_status)


    def run(self):
        """Public synchronous entry point to start the crawler."""
        try:
            logging.debug(f"AppCrawler run initiated for {self.cfg.APP_PACKAGE}.")
            asyncio.run(self.run_async())
            logging.debug(f"AppCrawler run completed for {self.cfg.APP_PACKAGE}.")
        except SystemExit as se:
            logging.debug(f"SystemExit caught by AppCrawler.run() wrapper: {se.code}")
            raise
        except KeyboardInterrupt:
            logging.warning("KeyboardInterrupt caught by AppCrawler.run() wrapper. Cleanup should have been handled.")
        except Exception as e:
            logging.critical(f"Unhandled critical error in AppCrawler.run() wrapper: {e}", exc_info=True)
            if not self.is_shutting_down and not (hasattr(self, '_cleanup_called') and self._cleanup_called):
                self.perform_full_cleanup()
        finally:
            logging.debug("AppCrawler.run() synchronous wrapper finished.")
