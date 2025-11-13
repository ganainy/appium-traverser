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
            self.previous_actions: List[str] = []
            self.current_screen_visit_count = 0
            self.current_composite_hash = ""
            self.last_action_feedback: Optional[str] = None
            
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
            
            # Get next action from AI
            ai_decision_start = time.time()
            action_result = self.agent_assistant._get_next_action_langchain(
                screenshot_bytes=screen_state.get("screenshot_bytes"),
                xml_context=screen_state.get("xml_context", ""),
                previous_actions=self.previous_actions,
                current_screen_visit_count=self.current_screen_visit_count,
                current_composite_hash=self.current_composite_hash,
                last_action_feedback=self.last_action_feedback
            )
            ai_decision_time = time.time() - ai_decision_start  # Time in seconds
            
            if not action_result:
                logger.warning("AI did not return a valid action")
                self.last_action_feedback = "AI decision failed"
                return True  # Continue despite error
            
            action_data, confidence, token_count = action_result
            
            # Log the action
            action_str = f"{action_data.get('action', 'unknown')} on {action_data.get('target_identifier', 'unknown')}"
            reasoning = action_data.get('reasoning', '')
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
            print(f"ELEMENT_FIND_TIME: {element_find_time:.3f}s")
            logger.info(f"Element find and execution time: {element_find_time:.3f}s")
            
            if success:
                self.last_action_feedback = "Action executed successfully"
                self.previous_actions.append(action_str)
                # Keep only last 20 actions
                if len(self.previous_actions) > 20:
                    self.previous_actions = self.previous_actions[-20:]
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
                print("END: FAILED", flush=True)
                # Give threads time to finish before exit
                import time
                time.sleep(0.5)
                return
            
            if not init_success:
                logger.error("Failed to initialize crawler loop")
                print("STATUS: Crawler initialization failed", flush=True)
                print("END: FAILED", flush=True)
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
            
            # Cleanup
            logger.info("Crawler loop completed")
            print("STATUS: Crawler completed")
            print("END: COMPLETED")
            
        except KeyboardInterrupt:
            logger.info("Crawler interrupted by user")
            print("STATUS: Crawler interrupted", flush=True)
            print("END: INTERRUPTED", flush=True)
        except Exception as e:
            logger.error(f"Fatal error in crawler loop: {e}", exc_info=True)
            print("STATUS: Crawler error", flush=True)
            print(f"END: ERROR - {str(e)}", flush=True)
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

