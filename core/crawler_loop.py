#!/usr/bin/env python3
"""
Main crawler loop that runs the AI-powered app crawling process.
This module implements the core decision-execution cycle.
"""

import io
import logging
import os
import sys
import time
import base64
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List

try:
    from config.app_config import Config
    from domain.agent_assistant import AgentAssistant
    from core.controller import FlagController
    from domain.app_context_manager import AppContextManager
    from utils.paths import SessionPathManager
    from domain.traffic_capture_manager import TrafficCaptureManager
    from domain.video_recording_manager import VideoRecordingManager
except ImportError as e:
    print(f"FATAL: Import error: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

logger = logging.getLogger(__name__)

# Constants for flag file paths
DEFAULT_SHUTDOWN_FLAG = 'crawler_shutdown.flag'
DEFAULT_PAUSE_FLAG = 'crawler_pause.flag'


class CrawlerLoop:
    """Main crawler loop that orchestrates AI decision-making and action execution."""
    
    def __init__(self, config: Config):
        """Initialize the crawler loop.
        
        Args:
            config: Configuration object
        """
        try:
            logger.debug("CrawlerLoop.__init__ starting...")
            self.config = config
            
            self.agent_assistant: Optional[AgentAssistant] = None
            self.app_context_manager: Optional[AppContextManager] = None
            self.traffic_capture_manager: Optional[TrafficCaptureManager] = None
            self.video_recording_manager: Optional[VideoRecordingManager] = None
            self.step_count = 0
            self.current_screen_visit_count = 0
            self.current_composite_hash = ""
            self.last_action_feedback: Optional[str] = None
            self.db_manager = None
            self.screen_state_manager = None
            self.current_run_id: Optional[int] = None
            self.current_from_screen_id: Optional[int] = None
            
            # Set up flag controller
            logger.debug("Setting up flag controller...")
            shutdown_flag_path = config.get('SHUTDOWN_FLAG_PATH') or os.path.join(
                config.BASE_DIR or '.', DEFAULT_SHUTDOWN_FLAG
            )
            pause_flag_path = config.get('PAUSE_FLAG_PATH') or os.path.join(
                config.BASE_DIR or '.', DEFAULT_PAUSE_FLAG
            )
            logger.debug(f"Flag paths: shutdown={shutdown_flag_path}, pause={pause_flag_path}")
            
            self.flag_controller = FlagController(shutdown_flag_path, pause_flag_path)
            logger.debug("Flag controller created")
            
            # Wait time between actions
            wait_after_action = config.get('WAIT_AFTER_ACTION')
            if wait_after_action is None:
                raise ValueError("WAIT_AFTER_ACTION must be set in configuration")
            self.wait_after_action = float(wait_after_action)
            logger.debug("CrawlerLoop.__init__ completed")
        except SystemExit as e:
            print(f"SystemExit in CrawlerLoop.__init__: {e}", file=sys.stderr, flush=True)
            raise
        except Exception as e:
            print(f"Exception in CrawlerLoop.__init__: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            logger.error(f"Error in CrawlerLoop.__init__: {e}", exc_info=True)
            raise
        
    def initialize(self) -> bool:
        """Initialize the agent assistant and driver connection.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            logger.debug("Initializing crawler loop...")
            
            # Initialize AgentAssistant
            logger.debug("Creating AgentAssistant...")
            self.agent_assistant = AgentAssistant(self.config)
            logger.debug("AgentAssistant created successfully")
            
            # Ensure driver is connected
            logger.debug("Connecting to MCP driver...")
            if not self.agent_assistant._ensure_driver_connected():
                error_msg = "Failed to connect driver - check MCP server is running"
                logger.error(error_msg)
                print(f"STATUS: {error_msg}", flush=True)
                return False
            
            logger.debug("Driver connected successfully")
            
            # Now that device is initialized, set up file logging if it was delayed
            # This ensures the log directory is created with the correct device name
            try:
                # Use the property which automatically resolves the template
                log_dir = self.config.LOG_DIR
            except Exception:
                # Fallback: try to resolve manually
                log_dir = self.config.get('LOG_DIR')
                if log_dir and '{' in log_dir:
                    try:
                        # Force path regeneration to get the correct path with device name
                        path_manager = self.config._path_manager
                        # Force regeneration to ensure we get the path with device name, not unknown_device
                        log_dir_path = path_manager.get_log_dir(force_regenerate=True)
                        log_dir = str(log_dir_path)
                    except Exception as e:
                        logger.warning(f"Could not resolve log directory template: {e}")
                        log_dir = None
            
            # Verify the path doesn't contain unknown_device and set up logging
            if log_dir:
                if 'unknown_device' in log_dir:
                    logger.warning(f"Log directory still contains unknown_device: {log_dir}, skipping file logging setup")
                else:
                    try:
                        os.makedirs(log_dir, exist_ok=True)
                        log_file_name = self.config.get('LOG_FILE_NAME')
                        if not log_file_name:
                            log_file_name = 'full.log'  # Use default from module constant if not set
                        log_file = os.path.join(log_dir, log_file_name)
                        
                        # Add file handler to root logger if not already present
                        root_logger = logging.getLogger()
                        has_file_handler = any(isinstance(h, logging.FileHandler) for h in root_logger.handlers)
                        if not has_file_handler:
                            file_handler = logging.FileHandler(log_file, encoding='utf-8')
                            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
                            root_logger.addHandler(file_handler)
                            logger.debug(f"File logging initialized at: {log_file}")
                    except Exception as e:
                        logger.warning(f"Could not set up delayed file logging: {e}")
            
            # Recreate AI interaction logger with correct path after device initialization
            # This ensures log files are created in the correct directory (with device name, not unknown_device)
            if self.agent_assistant and hasattr(self.agent_assistant, '_setup_ai_interaction_logger'):
                try:
                    self.agent_assistant._setup_ai_interaction_logger(force_recreate=True)
                    logger.debug("AI interaction logger recreated with updated session path")
                except Exception as e:
                    logger.warning(f"Could not recreate AI interaction logger: {e}")
            
            # Initialize AppContextManager for app context checking
            logger.debug("Initializing AppContextManager...")
            self.app_context_manager = AppContextManager(
                self.agent_assistant.tools.driver,
                self.config
            )
            logger.debug("AppContextManager initialized successfully")
            
            # Initialize TrafficCaptureManager if traffic capture is enabled
            if self.config.get('ENABLE_TRAFFIC_CAPTURE', False):
                try:
                    logger.debug("Initializing TrafficCaptureManager...")
                    self.traffic_capture_manager = TrafficCaptureManager(
                        self.agent_assistant.tools.driver,
                        self.config
                    )
                    logger.debug("TrafficCaptureManager initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize TrafficCaptureManager: {e}. Traffic capture will be disabled.")
                    self.traffic_capture_manager = None
            
            # Initialize VideoRecordingManager if video recording is enabled
            if self.config.get('ENABLE_VIDEO_RECORDING', False):
                try:
                    logger.debug("Initializing VideoRecordingManager...")
                    self.video_recording_manager = VideoRecordingManager(
                        self.agent_assistant.tools.driver,
                        self.config
                    )
                    logger.debug("VideoRecordingManager initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize VideoRecordingManager: {e}. Video recording will be disabled.")
                    self.video_recording_manager = None
            
            # Ensure we're in the correct app before starting
            logger.debug("Ensuring we're in the correct app context...")
            if not self.app_context_manager.ensure_in_app():
                logger.warning("Not in correct app context after initialization, but continuing...")
            
            # Initialize database to ensure it exists even if no screens are saved
            # This is important for post-run tasks like PDF generation
            # IMPORTANT: This must be done AFTER all managers are initialized and device name is resolved
            # to ensure the database is created in the correct session directory (not unknown_device)
            try:
                logger.debug("Initializing database and ensuring file exists...")
                from infrastructure.database import DatabaseManager
                
                # Ensure the database path is resolved (not a template string)
                # The DB_NAME property uses path_manager.get_db_path() which resolves the template
                db_path = self.config.DB_NAME
                logger.debug(f"Resolved database path: {db_path}")
                
                # Verify the path is resolved (not a template)
                if '{' in db_path or '}' in db_path:
                    logger.error(f"Database path contains unresolved template: {db_path}. Device info may not be available yet.")
                    raise ValueError(f"Database path template not resolved: {db_path}")
                
                # Verify the path doesn't contain "unknown_device" (device name should be resolved by now)
                if 'unknown_device' in db_path:
                    logger.error(f"Database path still contains 'unknown_device': {db_path}. Device info not resolved yet.")
                    raise ValueError(f"Database path contains 'unknown_device': device info must be resolved before database initialization.")
                
                db_manager = DatabaseManager(self.config)
                
                # Verify DatabaseManager got the resolved path
                if db_manager.db_path != db_path:
                    logger.warning(f"DatabaseManager path mismatch. Expected: {db_path}, Got: {db_manager.db_path}")
                
                # The connect() method should be responsible for
                # creating the database and its schema if it doesn't exist.
                # connect() will call _create_tables() automatically
                self.db_manager = db_manager
                if self.db_manager.connect():
                    logger.debug("Database connection successful, tables created.")
                    
                    # Initialize ScreenStateManager
                    from domain.screen_state_manager import ScreenStateManager
                    self.screen_state_manager = ScreenStateManager(
                        self.db_manager,
                        self.agent_assistant.tools.driver,
                        self.config
                    )
                    logger.debug("ScreenStateManager initialized successfully.")
                    
                    # Get or create run_id
                    app_package = self.config.get('APP_PACKAGE')
                    app_activity = self.config.get('APP_ACTIVITY')
                    if app_package and app_activity:
                        self.current_run_id = self.db_manager.get_or_create_run_info(app_package, app_activity)
                        if self.current_run_id:
                            # Initialize ScreenStateManager for this run
                            self.screen_state_manager.initialize_for_run(
                                self.current_run_id,
                                app_package,
                                app_activity,
                                is_continuation=False
                            )
                            logger.info(f"Initialized run ID: {self.current_run_id} for {app_package}")
                        else:
                            logger.warning("Failed to get or create run_id")
                    
                    # Keep connection open for step logging during execution
                    # Don't close it here - we'll use it during execution
                    
                    # Final verification
                    if os.path.exists(db_path):
                        logger.info(f"Database file successfully created on init: {db_path}")
                    else:
                        logger.error(f"Database file STILL missing after init: {db_path}")
                else:
                    # This is a critical failure for post-run tasks, so log as an error.
                    logger.error("Failed to initialize database. Post-run tasks will likely fail.")
            except Exception as e:
                # This is also critical.
                logger.error(f"Could not initialize database: {e}. Post-run tasks will likely fail.", exc_info=True)
            
            # Note: App launch verification is now handled by the MCP server during session initialization
            logger.debug("Crawler loop initialized successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to initialize crawler loop: {e}"
            logger.error(error_msg, exc_info=True)
            print(f"STATUS: Initialization failed - {str(e)}", flush=True)
            return False
    
    def check_shutdown_flag(self) -> bool:
        """Check if shutdown flag exists.
        
        Returns:
            True if shutdown requested, False otherwise
        """
        return self.flag_controller.is_shutdown_flag_present()
    
    def check_pause_flag(self) -> bool:
        """Check if pause flag exists.
        
        Returns:
            True if paused, False otherwise
        """
        return self.flag_controller.is_pause_flag_present()
    
    def wait_while_paused(self):
        """Wait while pause flag is present."""
        while self.check_pause_flag() and not self.check_shutdown_flag():
            time.sleep(0.5)
    
    def get_screen_state(self) -> Optional[Dict[str, Any]]:
        """Get current screen state (screenshot and XML).
        
        Returns:
            Dictionary with screenshot_bytes and xml_context, or None on error
        """
        try:
            driver = self.agent_assistant.tools.driver
            
            # Get screenshot
            screenshot_base64 = driver.get_screenshot_as_base64()
            screenshot_bytes = None
            if screenshot_base64:
                screenshot_bytes = base64.b64decode(screenshot_base64)
            
            # Get XML/page source
            xml_context_raw = driver.get_page_source()
            
            # Extract XML string if it's still a dict (fallback extraction)
            xml_context = xml_context_raw
            if isinstance(xml_context_raw, dict):
                # Handle nested MCP response structure
                if 'data' in xml_context_raw:
                    data = xml_context_raw['data']
                    if isinstance(data, dict):
                        # Check for nested data structure
                        if 'data' in data and isinstance(data['data'], dict):
                            xml_context = data['data'].get('source') or data['data'].get('xml') or str(xml_context_raw)
                        else:
                            xml_context = data.get('source') or data.get('xml') or str(xml_context_raw)
                    else:
                        xml_context = str(xml_context_raw)
                else:
                    xml_context = str(xml_context_raw)
            elif xml_context_raw is None:
                xml_context = ""
            
            # Calculate composite hash (simplified - in production would use proper hashing)
            self.current_composite_hash = str(hash(xml_context))
            
            return {
                "screenshot_bytes": screenshot_bytes,
                "xml_context": xml_context
            }
            
        except Exception as e:
            logger.error(f"Error getting screen state: {e}", exc_info=True)
            return None
    
    def run_step(self) -> bool:
        """Run a single crawler step: get screen -> decide action -> execute.
        
        Returns:
            True if step completed successfully, False if should stop
        """
        try:
            # Check for shutdown
            if self.check_shutdown_flag():
                logger.info("Shutdown flag detected, stopping crawler")
                return False
            
            # Wait if paused
            self.wait_while_paused()
            
            if self.check_shutdown_flag():
                return False
            
            # Increment step count
            self.step_count += 1
            print(f"UI_STEP:{self.step_count}", flush=True)
            print(f"STEP: {self.step_count}")
            logger.info(f"Starting step {self.step_count}")
            
            # CRITICAL: Ensure we're in the correct app BEFORE getting screen state and making AI decisions
            # This prevents the AI from analyzing the wrong app's UI
            if self.app_context_manager:
                logger.debug("Checking app context before screen state extraction...")
                if not self.app_context_manager.ensure_in_app():
                    logger.warning("Failed to ensure app context - attempting recovery and retrying...")
                    # Wait a bit for recovery to complete
                    time.sleep(2.0)
                    # Retry once
                    if not self.app_context_manager.ensure_in_app():
                        logger.error("Could not return to correct app context after retry - skipping this step")
                        self.last_action_feedback = "App context check failed - not in target app"
                        return True  # Continue to next step
                logger.debug("App context verified - proceeding with screen state extraction")
            else:
                logger.warning("AppContextManager not initialized - skipping app context check")
            
            # Get current screen state (only after we've verified we're in the correct app)
            screen_state = self.get_screen_state()
            if not screen_state:
                logger.error("Failed to get screen state")
                return True  # Continue despite error
            
            # Process current screen state to get screen ID and ensure it's recorded in database
            from_screen_id = None
            current_screen_visit_count = 0
            if self.screen_state_manager and self.current_run_id:
                try:
                    from domain.screen_state_manager import ScreenRepresentation
                    import utils.utils as utils
                    
                    # Create screen representation from current state
                    xml_str = screen_state.get("xml_context", "")
                    screenshot_bytes = screen_state.get("screenshot_bytes")
                    
                    if xml_str and screenshot_bytes:
                        xml_hash = utils.calculate_xml_hash(xml_str)
                        visual_hash = utils.calculate_visual_hash(screenshot_bytes)
                        composite_hash = f"{xml_hash}_{visual_hash}"
                        self.current_composite_hash = composite_hash
                        
                        # Get activity name from driver if available
                        activity_name = None
                        try:
                            if hasattr(self.agent_assistant, 'tools') and hasattr(self.agent_assistant.tools, 'driver'):
                                current_activity = self.agent_assistant.tools.driver.get_current_activity()
                                if current_activity:
                                    activity_name = current_activity
                        except Exception:
                            pass  # Activity name is optional
                        
                        # Create screen representation
                        candidate_screen = ScreenRepresentation(
                            screen_id=-1,  # Temporary ID, will be set by process_and_record_state
                            composite_hash=composite_hash,
                            xml_hash=xml_hash,
                            visual_hash=visual_hash,
                            screenshot_path=None,  # Will be set by process_and_record_state
                            activity_name=activity_name,
                            xml_content=xml_str,
                            screenshot_bytes=screenshot_bytes,
                            first_seen_run_id=self.current_run_id,
                            first_seen_step_number=self.step_count
                        )
                        
                        # Process and record the screen state (this ensures it's in the database)
                        # Don't increment visit count here - we'll do it after the action
                        final_screen, visit_info = self.screen_state_manager.process_and_record_state(
                            candidate_screen, self.current_run_id, self.step_count, increment_visit_count=False
                        )
                        from_screen_id = final_screen.id
                        current_screen_visit_count = visit_info.get("visit_count_this_run", 0)
                        self.current_screen_visit_count = current_screen_visit_count
                        
                        # Emit UI_SCREENSHOT for UI to display the current screenshot being analyzed
                        if final_screen.screenshot_path and os.path.exists(final_screen.screenshot_path):
                            print(f"UI_SCREENSHOT:{final_screen.screenshot_path}", flush=True)
                        
                        logger.debug(f"Processed screen state: ID={from_screen_id}, visit_count={current_screen_visit_count}")
                except Exception as e:
                    logger.warning(f"Error processing screen state: {e}", exc_info=True)
            
            # Collect structured action history and context from database
            action_history = []
            visited_screens = []
            current_screen_actions = []
            
            if self.db_manager and self.current_run_id:
                try:
                    # Get recent steps with details (last 20 steps)
                    action_history = self.db_manager.get_recent_steps_with_details(
                        self.current_run_id, limit=20
                    )
                    
                    # Get visited screens summary (filter out system dialogs)
                    all_visited_screens = self.db_manager.get_visited_screens_summary(
                        self.current_run_id
                    )
                    # Filter out system dialogs/pickers
                    visited_screens = []
                    target_package = self.config.get('APP_PACKAGE', '')
                    from config.package_constants import PackageConstants
                    for screen in all_visited_screens:
                        activity = screen.get('activity_name', '')
                        # Skip system dialogs and file pickers
                        if activity and (
                            'documentsui' in activity.lower() or
                            'picker' in activity.lower() or
                            PackageConstants.is_system_package(activity.split('.')[0] if '.' in activity else activity)
                        ):
                            continue
                        # Only include screens from target app or explicitly allowed packages
                        if activity and target_package:
                            activity_package = activity.split('.')[0] if '.' in activity else ''
                            if activity_package and activity_package != target_package:
                                # Check if it's in allowed external packages
                                allowed_packages = self.config.get('ALLOWED_EXTERNAL_PACKAGES', [])
                                if isinstance(allowed_packages, list) and activity_package not in allowed_packages:
                                    continue
                        visited_screens.append(screen)
                    
                    # Get actions already tried on current screen (if we know the screen ID)
                    if from_screen_id is not None:
                        current_screen_actions = self.db_manager.get_actions_for_screen_with_details(
                            from_screen_id, run_id=self.current_run_id
                        )
                except Exception as e:
                    logger.warning(f"Error collecting action history from database: {e}", exc_info=True)
                    # If database query fails, action_history will remain empty
                    action_history = []
            
            # Detect if stuck in a loop (same screen, multiple actions, no navigation)
            is_stuck = False
            stuck_reason = ""
            
            # First, check if the last action successfully navigated to a different screen
            # If it did, we're NOT stuck (false positive prevention)
            last_action_navigated_away = False
            if action_history and len(action_history) > 0:
                last_action = action_history[-1]
                last_from_screen = last_action.get('from_screen_id')
                last_to_screen = last_action.get('to_screen_id')
                last_success = last_action.get('execution_success', False)
                
                # If last action successfully navigated to a different screen, we're not stuck
                if last_success and last_to_screen is not None and last_from_screen is not None:
                    if last_to_screen != last_from_screen:
                        last_action_navigated_away = True
                        logger.debug(f"Last action navigated from Screen #{last_from_screen} to Screen #{last_to_screen} - not stuck")
            
            # Only check for stuck if we didn't just navigate away AND we're on a known screen
            if not last_action_navigated_away and from_screen_id is not None and current_screen_actions:
                # Count successful actions that stayed on same screen (exclude actions that navigated away)
                same_screen_actions = [a for a in current_screen_actions 
                                     if a.get('execution_success') and 
                                     (a.get('to_screen_id') == from_screen_id or a.get('to_screen_id') is None)]
                
                # Consider stuck if:
                # 1. High visit count (>5) on same screen
                # 2. Multiple successful actions that didn't navigate away (>=3)
                # 3. All recent actions (last 5) stayed on same screen
                if current_screen_visit_count > 5:
                    is_stuck = True
                    stuck_reason = f"High visit count ({current_screen_visit_count}) on same screen"
                elif len(same_screen_actions) >= 3:
                    is_stuck = True
                    stuck_reason = f"Multiple actions ({len(same_screen_actions)}) returned to same screen"
                elif len(current_screen_actions) >= 5:
                    # Check if all recent actions stayed on same screen
                    recent_actions = current_screen_actions[-5:]
                    all_stayed = all(
                        a.get('to_screen_id') == from_screen_id or a.get('to_screen_id') is None 
                        for a in recent_actions if a.get('execution_success')
                    )
                    if all_stayed:
                        is_stuck = True
                        stuck_reason = "All recent actions stayed on same screen"
            
            # Log the context being sent to AI
            logger.info("=" * 80)
            logger.info(f"AI CONTEXT - Step {self.step_count}")
            logger.info("=" * 80)
            if is_stuck:
                logger.info(f"⚠️ STUCK DETECTED: {stuck_reason}")
                logger.info("=" * 80)
            logger.info(f"Action History: {len(action_history)} entries")
            for action in action_history[-10:]:  # Show last 10
                step_num = action.get('step_number', '?')
                action_desc = action.get('action_description', 'unknown')
                success = action.get('execution_success', False)
                status = "✓" if success else "✗"
                from_screen = action.get('from_screen_id')
                to_screen = action.get('to_screen_id')
                error = action.get('error_message')
                
                # Better screen transition messaging
                if to_screen:
                    if from_screen == to_screen:
                        screen_info = " → stayed on same screen"
                    else:
                        screen_info = f" → navigated to Screen #{to_screen}"
                else:
                    screen_info = " → no navigation"
                
                error_info = f" ({error})" if error else ""
                logger.info(f"  [{status}] Step {step_num}: {action_desc}{screen_info}{error_info}")
            
            logger.info(f"Visited Screens: {len(visited_screens)} screens")
            for screen in visited_screens[:10]:  # Show top 10
                screen_id = screen.get('screen_id', '?')
                activity = screen.get('activity_name', 'UnknownActivity')
                visit_count = screen.get('visit_count', 0)
                logger.info(f"  Screen #{screen_id} ({activity}): {visit_count} visit(s)")
            
            logger.info(f"Current Screen ID: {from_screen_id}")
            logger.info(f"Current Screen Visit Count: {current_screen_visit_count}")
            logger.info(f"Current Screen Actions: {len(current_screen_actions)} actions tried")
            for action in current_screen_actions:
                action_desc = action.get('action_description', 'unknown')
                success = action.get('execution_success', False)
                status = "✓" if success else "✗"
                to_screen = action.get('to_screen_id')
                error = action.get('error_message')
                
                # Better screen transition messaging
                if to_screen:
                    if to_screen == from_screen_id:
                        screen_info = " → stayed on same screen"
                    else:
                        screen_info = f" → navigated to Screen #{to_screen}"
                else:
                    screen_info = " → no navigation"
                
                error_info = f" ({error})" if error else ""
                logger.info(f"  [{status}] {action_desc}{screen_info}{error_info}")
            logger.info("=" * 80)
            
            # Get next action from AI
            ai_decision_start = time.time()
            action_result = self.agent_assistant._get_next_action_langchain(
                screenshot_bytes=screen_state.get("screenshot_bytes"),
                xml_context=screen_state.get("xml_context", ""),
                action_history=action_history,
                visited_screens=visited_screens,
                current_screen_actions=current_screen_actions,
                current_screen_id=from_screen_id,
                current_screen_visit_count=current_screen_visit_count,
                current_composite_hash=self.current_composite_hash,
                last_action_feedback=self.last_action_feedback,
                is_stuck=is_stuck,
                stuck_reason=stuck_reason if is_stuck else None
            )
            ai_decision_time = time.time() - ai_decision_start  # Time in seconds
            
            if not action_result:
                logger.warning("AI did not return a valid action")
                self.last_action_feedback = "AI decision failed"
                # Log failed step
                if self.db_manager and self.current_run_id:
                    try:
                        import json
                        self.db_manager.insert_step_log(
                            run_id=self.current_run_id,
                            step_number=self.step_count,
                            from_screen_id=from_screen_id,
                            to_screen_id=None,
                            action_description="AI decision failed",
                            ai_suggestion_json=None,
                            mapped_action_json=None,
                            execution_success=False,
                            error_message="AI did not return a valid action",
                            ai_response_time=ai_decision_time * 1000.0,  # Convert to ms
                            total_tokens=None,
                            ai_input_prompt=None,
                            element_find_time_ms=None
                        )
                    except Exception as e:
                        logger.error(f"Error logging failed step: {e}")
                return True  # Continue despite error
            
            action_data, confidence, token_count, ai_input_prompt = action_result
            
            # Log the action
            action_str = f"{action_data.get('action', 'unknown')} on {action_data.get('target_identifier', 'unknown')}"
            reasoning = action_data.get('reasoning', '')
            # Emit UI_ACTION for UI to capture (with flush to ensure immediate display)
            print(f"UI_ACTION: {action_str}", flush=True)
            print(f"ACTION: {action_str}")
            if reasoning:
                print(f"REASONING: {reasoning}")
            print(f"AI_DECISION_TIME: {ai_decision_time:.3f}s")
            logger.info(f"AI decided: {action_str}")
            if reasoning:
                logger.info(f"AI reasoning: {reasoning}")
            logger.info(f"AI decision time: {ai_decision_time:.3f}s")
            
            # Execute the action (includes element finding)
            element_find_start = time.time()
            success = self.agent_assistant.execute_action(action_data)
            element_find_time = time.time() - element_find_start  # Time in seconds
            element_find_time_ms = element_find_time * 1000.0  # Convert to milliseconds
            print(f"ELEMENT_FIND_TIME: {element_find_time:.3f}s")
            logger.info(f"Element find and execution time: {element_find_time:.3f}s")
            
            # Get to_screen_id after action execution (process the new screen state)
            to_screen_id = None
            if success and self.screen_state_manager and self.current_run_id:
                try:
                    # Get new screen state after action
                    new_screen_state = self.get_screen_state()
                    if new_screen_state:
                        from domain.screen_state_manager import ScreenRepresentation
                        import utils.utils as utils
                        
                        xml_str = new_screen_state.get("xml_context", "")
                        screenshot_bytes = new_screen_state.get("screenshot_bytes")
                        
                        if xml_str and screenshot_bytes:
                            xml_hash = utils.calculate_xml_hash(xml_str)
                            visual_hash = utils.calculate_visual_hash(screenshot_bytes)
                            composite_hash = f"{xml_hash}_{visual_hash}"
                            
                            # Get activity name from driver if available
                            activity_name = None
                            try:
                                if hasattr(self.agent_assistant, 'tools') and hasattr(self.agent_assistant.tools, 'driver'):
                                    current_activity = self.agent_assistant.tools.driver.get_current_activity()
                                    if current_activity:
                                        activity_name = current_activity
                            except Exception:
                                pass  # Activity name is optional
                            
                            # Create screen representation and process it
                            candidate_screen = ScreenRepresentation(
                                screen_id=-1,  # Temporary ID, will be set by process_and_record_state
                                composite_hash=composite_hash,
                                xml_hash=xml_hash,
                                visual_hash=visual_hash,
                                screenshot_path=None,  # Will be set by process_and_record_state
                                activity_name=activity_name,
                                xml_content=xml_str,
                                screenshot_bytes=screenshot_bytes,
                                first_seen_run_id=self.current_run_id,
                                first_seen_step_number=self.step_count
                            )
                            
                            # Process and record the new screen state (increment visit count here)
                            final_screen, visit_info_after = self.screen_state_manager.process_and_record_state(
                                candidate_screen, self.current_run_id, self.step_count, increment_visit_count=True
                            )
                            # Emit UI_SCREENSHOT for UI to display the new screen state after action
                            if final_screen.screenshot_path and os.path.exists(final_screen.screenshot_path):
                                print(f"UI_SCREENSHOT:{final_screen.screenshot_path}", flush=True)
                            # Update current screen visit count after action
                            if visit_info_after:
                                self.current_screen_visit_count = visit_info_after.get("visit_count_this_run", 0)
                            to_screen_id = final_screen.id
                except Exception as e:
                    logger.warning(f"Error getting to_screen_id: {e}", exc_info=True)
            
            # Log step to database
            if self.db_manager and self.current_run_id:
                try:
                    import json
                    ai_suggestion_json = json.dumps(action_data) if action_data else None
                    mapped_action_json = json.dumps(action_data) if action_data else None
                    action_description = action_str
                    error_message = None if success else "Action execution failed"
                    
                    self.db_manager.insert_step_log(
                        run_id=self.current_run_id,
                        step_number=self.step_count,
                        from_screen_id=from_screen_id,
                        to_screen_id=to_screen_id,
                        action_description=action_description,
                        ai_suggestion_json=ai_suggestion_json,
                        mapped_action_json=mapped_action_json,
                        execution_success=success,
                        error_message=error_message,
                        ai_response_time=ai_decision_time * 1000.0,  # Convert to ms
                        total_tokens=token_count if token_count else None,
                        ai_input_prompt=ai_input_prompt,
                        element_find_time_ms=element_find_time_ms
                    )
                    logger.debug(f"Logged step {self.step_count} to database")
                except Exception as e:
                    logger.error(f"Error logging step to database: {e}", exc_info=True)
            
            if success:
                self.last_action_feedback = "Action executed successfully"
            else:
                self.last_action_feedback = "Action execution failed"
                logger.warning(f"Action execution failed: {action_str}")
            
            # Wait after action
            time.sleep(self.wait_after_action)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in crawler step: {e}", exc_info=True)
            self.last_action_feedback = f"Step error: {str(e)}"
            return True  # Continue despite error
    
    def run(self, max_steps: Optional[int] = None):
        """Run the main crawler loop.
        
        Args:
            max_steps: Maximum number of steps to run (None for unlimited)
        """
        try:
            
            # Initialize with better error handling
            try:
                init_success = self.initialize()
            except Exception as init_error:
                error_msg = f"Exception during initialization: {init_error}"
                logger.error(error_msg, exc_info=True)
                print(f"STATUS: {error_msg}", flush=True)
                # Give threads time to finish before exit
                import time
                time.sleep(0.5)
                return
            
            if not init_success:
                logger.error("Failed to initialize crawler loop")
                print("STATUS: Crawler initialization failed", flush=True)
                # Give threads time to finish before exit
                import time
                time.sleep(0.5)
                return
            
            
            # Start traffic capture if enabled
            if self.traffic_capture_manager:
                try:
                    logger.debug("Starting traffic capture...")
                    # Get run_id from step_count (will be 0 initially, but that's okay)
                    run_id = getattr(self, '_run_id', 0)
                    # Use asyncio.run to handle async call
                    asyncio.run(self.traffic_capture_manager.start_capture_async(
                        run_id=run_id,
                        step_num=0
                    ))
                    logger.debug("Traffic capture started successfully")
                except Exception as e:
                    logger.error(f"Failed to start traffic capture: {e}", exc_info=True)
            
            # Start video recording if enabled
            if self.video_recording_manager:
                try:
                    logger.debug("Starting video recording...")
                    run_id = getattr(self, '_run_id', 0)
                    success = self.video_recording_manager.start_recording(
                        run_id=run_id,
                        step_num=0
                    )
                    if success:
                        logger.debug("Video recording started successfully")
                    else:
                        logger.warning("Failed to start video recording")
                except Exception as e:
                    logger.error(f"Failed to start video recording: {e}", exc_info=True)
            
            # Main loop
            while True:
                # Check for shutdown
                if self.check_shutdown_flag():
                    logger.info("Shutdown requested")
                    break
                
                # Check max steps
                if max_steps and self.step_count >= max_steps:
                    logger.info(f"Reached max steps limit: {max_steps}")
                    break
                
                # Run a step
                should_continue = self.run_step()
                if not should_continue:
                    break
            
            # Update run status to COMPLETED
            if self.db_manager and self.current_run_id:
                try:
                    from datetime import datetime
                    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.db_manager.update_run_status(self.current_run_id, "COMPLETED", end_time)
                    logger.debug(f"Updated run {self.current_run_id} status to COMPLETED")
                except Exception as e:
                    logger.error(f"Error updating run status: {e}")
            
            # Close database connection
            if self.db_manager:
                try:
                    self.db_manager.close()
                    logger.debug("Database connection closed")
                except Exception as e:
                    logger.warning(f"Error closing database: {e}")
            
            # Cleanup
            logger.info("Crawler loop completed")
            print("STATUS: Crawler completed")
            
        except KeyboardInterrupt:
            logger.info("Crawler interrupted by user")
            # Update run status to INTERRUPTED
            if self.db_manager and self.current_run_id:
                try:
                    from datetime import datetime
                    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.db_manager.update_run_status(self.current_run_id, "INTERRUPTED", end_time)
                except Exception as e:
                    logger.error(f"Error updating run status: {e}")
            if self.db_manager:
                try:
                    self.db_manager.close()
                except Exception:
                    pass
            print("STATUS: Crawler interrupted", flush=True)
        except Exception as e:
            logger.error(f"Fatal error in crawler loop: {e}", exc_info=True)
            # Update run status to FAILED
            if self.db_manager and self.current_run_id:
                try:
                    from datetime import datetime
                    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.db_manager.update_run_status(self.current_run_id, "FAILED", end_time)
                except Exception as e:
                    logger.error(f"Error updating run status: {e}")
            if self.db_manager:
                try:
                    self.db_manager.close()
                except Exception:
                    pass
            print("STATUS: Crawler error", flush=True)
        finally:
            # Stop traffic capture if it was started
            if self.traffic_capture_manager and self.traffic_capture_manager.is_capturing():
                try:
                    logger.debug("Stopping traffic capture...")
                    run_id = getattr(self, '_run_id', 0)
                    pcap_path = asyncio.run(self.traffic_capture_manager.stop_capture_and_pull_async(
                        run_id=run_id,
                        step_num=self.step_count
                    ))
                    if pcap_path:
                        logger.debug(f"Traffic capture saved to: {pcap_path}")
                    else:
                        logger.warning("Traffic capture stopped but file was not saved")
                except Exception as e:
                    logger.error(f"Error stopping traffic capture: {e}", exc_info=True)
            
            # Stop video recording if it was started
            if self.video_recording_manager and self.video_recording_manager.is_recording():
                try:
                    logger.debug("Stopping video recording...")
                    video_path = self.video_recording_manager.stop_recording_and_save()
                    if video_path:
                        logger.debug(f"Video recording saved to: {video_path}")
                    else:
                        logger.warning("Video recording stopped but file was not saved")
                except Exception as e:
                    logger.error(f"Error stopping video recording: {e}", exc_info=True)
            
            # Run MobSF analysis if enabled
            mobsf_enabled = self.config.get('ENABLE_MOBSF_ANALYSIS', False)
            
            # Explicitly check for True boolean or "true" string
            if mobsf_enabled is True or str(mobsf_enabled).lower() == 'true':
                try:
                    logger.info("Starting automatic MobSF analysis...")
                    from infrastructure.mobsf_manager import MobSFManager
                    package_name = self.config.get('APP_PACKAGE')
                    if package_name:
                        mobsf_manager = MobSFManager(self.config)
                        success, result = mobsf_manager.perform_complete_scan(package_name)
                        if success:
                            logger.info("MobSF analysis completed successfully")
                            if isinstance(result, dict):
                                if result.get('pdf_report'):
                                    logger.info(f"MobSF PDF Report: {result['pdf_report']}")
                                if result.get('json_report'):
                                    logger.info(f"MobSF JSON Report: {result['json_report']}")
                        else:
                            error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else str(result)
                            logger.error(f"MobSF analysis failed: {error_msg}")
                    else:
                        logger.warning("APP_PACKAGE not configured, skipping MobSF analysis")
                except Exception as e:
                    logger.error(f"Error running MobSF analysis: {e}", exc_info=True)
            
            # Disconnect driver
            if self.agent_assistant and self.agent_assistant.tools.driver:
                try:
                    self.agent_assistant.tools.driver.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting driver: {e}")
            
            # Give any daemon threads time to finish before exit
            import time
            import threading
            time.sleep(0.5)
            
            # Force flush all streams
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except:
                pass


def run_crawler_loop(config: Optional[Config] = None):
    """Entry point for running the crawler loop.
    
    Args:
        config: Optional config object (creates new one if not provided)
    """
    try:
        if config is None:
            config = Config()
        
        logger.debug("CRAWLER_MODE detected, starting crawler loop...")
        
        # Set up logging - always log to stdout so parent process can see it
        # Also try to log to file if LOG_DIR is available
        # Wrap stdout with UTF-8 encoding to handle Unicode characters on Windows
        try:
            stdout_wrapper = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            handlers = [logging.StreamHandler(stdout_wrapper)]
        except Exception:
            # Fallback to regular stdout if wrapping fails
            handlers = [logging.StreamHandler(sys.stdout)]
        
        # Use the property which automatically resolves the template
        try:
            log_dir = config.LOG_DIR
        except Exception:
            # Fallback: try to resolve manually
            log_dir = config.get('LOG_DIR')
            if log_dir:
                # Resolve placeholders in log_dir if present
                if '{' in log_dir:
                    # Use the same SessionPathManager instance from config to ensure consistency
                    try:
                        # Use config's path manager instead of creating a new instance
                        path_manager = config._path_manager
                        log_dir_path = path_manager.get_log_dir()
                        log_dir = str(log_dir_path)
                    except Exception as e:
                        # Fallback: try to resolve placeholders manually
                        output_data_dir = config.get('OUTPUT_DATA_DIR') or 'output_data'
                        if '{OUTPUT_DATA_DIR}' in log_dir:
                            log_dir = log_dir.replace('{OUTPUT_DATA_DIR}', output_data_dir)
                        if '{session_dir}' in log_dir:
                            # Use proper sessions directory structure instead of crawler_session
                            try:
                                # Use config's path manager instead of creating a new instance
                                path_manager = config._path_manager
                                session_path = path_manager.get_session_path()
                                log_dir = log_dir.replace('{session_dir}', str(session_path))
                            except Exception:
                                # Last resort: use sessions directory with unknown_device
                                # But prefer device name if available
                                # Get device info from path_manager if available
                                if hasattr(config, '_path_manager'):
                                    path_manager = config._path_manager
                                    device_name = path_manager.get_device_name()
                                    device_udid = path_manager.get_device_udid()
                                    timestamp = path_manager.get_timestamp()
                                else:
                                    device_name = None
                                    device_udid = None
                                    timestamp = time.strftime('%Y-%m-%d_%H-%M')
                                device_id = device_name or device_udid or 'unknown_device'
                                app_package = config.get('APP_PACKAGE') or 'unknown.app'
                                app_package_safe = app_package.replace('.', '_')
                                session_dir = os.path.join(output_data_dir, 'sessions', f'{device_id}_{app_package_safe}_{timestamp}')
                                log_dir = log_dir.replace('{session_dir}', session_dir)
            
            # Only create log directory if we have a real device ID
            # This prevents creating directories with unknown_device
            # Get device info from path_manager if available
            if hasattr(config, '_path_manager'):
                path_manager = config._path_manager
                device_name = path_manager.get_device_name()
                device_udid = path_manager.get_device_udid()
            else:
                device_name = None
                device_udid = None
            has_real_device = device_name or device_udid
            
            if has_real_device or 'unknown_device' not in log_dir:
                try:
                    os.makedirs(log_dir, exist_ok=True)
                    log_file = os.path.join(log_dir, config.get('LOG_FILE_NAME', 'crawler.log'))
                    handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
                except Exception as e:
                    # If file logging fails, continue with stdout only
                    print(f"Warning: Could not set up file logging: {e}", file=sys.stderr)
            else:
                # Delay file logging until device is initialized
                # Log to stdout only for now
                print("INFO: Delaying file logging until device is initialized (to avoid unknown_device directory)", file=sys.stderr)
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=handlers,
            force=True  # Force reconfiguration in case logging was already set up
        )
        
        # Create and run crawler loop - use minimal logging to avoid daemon thread issues
        try:
            # Use direct print to stderr instead of logger to avoid threading issues
            logger.debug("About to create CrawlerLoop...")
            
            # Create crawler loop
            logger.debug("Calling CrawlerLoop(config)...")
            
            # Try to create the crawler loop with explicit error handling
            try:
                crawler = CrawlerLoop(config)
            except BaseException as be:
                # Catch ALL exceptions including SystemExit, KeyboardInterrupt, etc.
                logger.error(f"BaseException caught during CrawlerLoop creation: {type(be).__name__}: {be}", exc_info=True)
                # Don't re-raise immediately - give threads time
                import time
                time.sleep(1.0)
                raise
            
            logger.debug("CrawlerLoop created successfully")
        except SystemExit as e:
            print(f"SystemExit caught in CrawlerLoop creation: {e}", file=sys.stderr, flush=True)
            # Give threads time to finish
            import time
            time.sleep(0.5)
            raise
        except Exception as e:
            print(f"Exception in CrawlerLoop creation: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            # Give threads time to finish
            import time
            time.sleep(0.5)
            raise
        
        # Get max steps from config
        max_steps = config.get('MAX_CRAWL_STEPS')
        if max_steps:
            try:
                max_steps = int(max_steps)
            except (ValueError, TypeError):
                max_steps = None
        
        try:
            crawler.run(max_steps=max_steps)
        except SystemExit:
            # Re-raise SystemExit to allow clean exit
            raise
        except Exception as e:
            error_msg = f"Fatal error in crawler.run(): {e}"
            logger.error(error_msg, exc_info=True)
            print(f"FATAL: {error_msg}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
            # Give threads time to finish
            import time
            time.sleep(0.5)
            sys.exit(1)
        finally:
            # Final cleanup - ensure all streams are flushed
            try:
                sys.stdout.flush()
                sys.stderr.flush()
            except:
                pass
    except KeyboardInterrupt:
        print("Crawler interrupted by user", file=sys.stderr, flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"FATAL ERROR in run_crawler_loop: {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run_crawler_loop()

