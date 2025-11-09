# appium_driver.py - MCP Client version (moved to infrastructure)
import base64
import logging
from typing import Any, Dict, Optional, Tuple

from config.config import Config
from infrastructure.mcp_client import MCPClient, MCPConnectionError, MCPError

logger = logging.getLogger(__name__)


class AppiumDriver:
    def __init__(self, app_config: Config):
        self.cfg = app_config
        self.mcp_client: Optional[MCPClient] = None
        self._session_initialized = False
        self._session_info: Optional[Dict[str, Any]] = None
        logger.debug("AppiumDriver (MCP client) initialized.")

    def connect(self) -> bool:
        """Initialize MCP client connection."""
        try:
            # Get MCP server URL - use config.get() to follow precedence
            mcp_url = self.cfg.get('CONFIG_MCP_SERVER_URL') or self.cfg.get('MCP_SERVER_URL', 'http://localhost:3000/mcp')
            # Get timeout values
            connection_timeout = self.cfg.get('MCP_CONNECTION_TIMEOUT', 5.0)
            request_timeout = self.cfg.get('MCP_REQUEST_TIMEOUT', 30.0)
            
            self.mcp_client = MCPClient(
                server_url=mcp_url,
                connection_timeout=connection_timeout,
                request_timeout=request_timeout
            )
            
            # Check server health
            health = self.mcp_client.check_server_health()
            if not health.get("healthy", False):
                logger.warning(f"MCP server health check failed: {health}")
                # Continue anyway - server might be starting up
            
            logger.debug("MCP client connection established.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect MCP client: {e}")
            return False

    def disconnect(self):
        """Disconnect MCP client and close session."""
        if self.mcp_client:
            try:
                # Close any active session
                if self._session_initialized:
                    try:
                        self.mcp_client.call_tool("close-appium", {})
                    except Exception as e:
                        logger.warning(f"Error closing Appium session: {e}")
                    finally:
                        self._session_initialized = False
                        self._session_info = None
                self.mcp_client.close()
            except Exception as e:
                logger.warning(f"Error during MCP client disconnect: {e}")
            finally:
                self.mcp_client = None
        logger.debug("MCP client disconnected.")

    def _ensure_mcp_client(self) -> bool:
        """Ensure MCP client is initialized."""
        if not self.mcp_client:
            if not self.connect():
                logger.error("Failed to initialize MCP client")
                return False
        return True

    def initialize_session(self, app_package: Optional[str] = None, app_activity: Optional[str] = None,
                          device_udid: Optional[str] = None, platform_name: str = "Android") -> bool:
        """Initialize Appium session via MCP.
        
        Args:
            app_package: Android app package name
            app_activity: Android app activity name
            device_udid: Device UDID (optional, will auto-detect if not provided)
            platform_name: Platform name ("Android" or "iOS")
            
        Returns:
            True if session initialized successfully, False otherwise
        """
        if not self._ensure_mcp_client():
            return False
        
        try:
            # Build initialization parameters
            init_params = {
                "platformName": platform_name
            }
            
            if app_package:
                init_params["appPackage"] = app_package
            if app_activity:
                init_params["appActivity"] = app_activity
            if device_udid:
                init_params["udid"] = device_udid
            
            result = self.mcp_client.call_tool("initialize-appium", init_params)
            
            if result.get("success", False):
                self._session_initialized = True
                self._session_info = result.get("data", {})
                logger.info(f"Appium session initialized: {self._session_info.get('sessionId', 'unknown')}")
                return True
            else:
                logger.error(f"Failed to initialize session: {result.get('message', 'Unknown error')}")
                return False
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error initializing session: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error initializing session: {e}")
            return False

    def validate_session(self) -> bool:
        """Validate that the current session is still active."""
        if not self._ensure_mcp_client():
            return False
        
        try:
            result = self.mcp_client.call_tool("validate-session", {})
            is_valid = result.get("success", False)
            if not is_valid:
                self._session_initialized = False
                self._session_info = None
            return is_valid
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error validating session: {e}")
            self._session_initialized = False
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating session: {e}")
            return False

    def get_page_source(self) -> Optional[str]:
        """Get page source via MCP."""
        if not self._ensure_mcp_client():
            return None
        
        try:
            result = self.mcp_client.call_tool("get-page-source", {})
            if result.get("success", False):
                data = result.get("data", {})
                # Page source might be in data.xml or data directly
                return data.get("xml") or data.get("pageSource") or str(data)
            else:
                logger.error(f"Failed to get page source: {result.get('message', 'Unknown error')}")
                return None
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error getting page source: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting page source: {e}")
            return None

    def get_screenshot_as_base64(self) -> Optional[str]:
        """Get screenshot via MCP."""
        if not self._ensure_mcp_client():
            return None
        
        try:
            result = self.mcp_client.call_tool("take-screenshot", {})
            if result.get("success", False):
                data = result.get("data", {})
                # Screenshot might be in data.screenshot, data.base64, or data directly
                screenshot = data.get("screenshot") or data.get("base64") or data.get("image")
                if screenshot:
                    # If it's already base64, return as-is; otherwise encode
                    if isinstance(screenshot, str):
                        # Remove data URL prefix if present
                        if screenshot.startswith("data:image"):
                            screenshot = screenshot.split(",", 1)[1]
                        return screenshot
                    elif isinstance(screenshot, bytes):
                        return base64.b64encode(screenshot).decode('utf-8')
            else:
                logger.error(f"Failed to get screenshot: {result.get('message', 'Unknown error')}")
                return None
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error getting screenshot: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting screenshot: {e}")
            return None

    def tap(self, target_identifier: Optional[str], bbox: Optional[Dict[str, Any]] = None) -> bool:
        """Tap via MCP. Can tap by element identifier or coordinates (bbox)."""
        if not self._ensure_mcp_client():
            return False
        
        try:
            if target_identifier:
                # Tap by element identifier
                result = self.mcp_client.call_tool("tap-element", {
                    "selector": target_identifier,
                    "strategy": "id"  # Default strategy, could be enhanced
                })
            elif bbox:
                # Tap by coordinates - extract center from bbox
                top_left = bbox.get("top_left", [0, 0])
                bottom_right = bbox.get("bottom_right", [0, 0])
                x = (top_left[1] + bottom_right[1]) // 2
                y = (top_left[0] + bottom_right[0]) // 2
                
                # Use swipe with very short duration for tap
                result = self.mcp_client.call_tool("swipe", {
                    "startX": x,
                    "startY": y,
                    "endX": x,
                    "endY": y,
                    "duration": 100  # Very short duration = tap
                })
            else:
                logger.error("tap() called without target_identifier or bbox")
                return False
            
            success = result.get("success", False)
            if not success:
                logger.warning(f"Tap failed: {result.get('message', 'Unknown error')}")
            return success
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error during tap: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during tap: {e}")
            return False

    def input_text(self, target_identifier: str, text: str) -> bool:
        """Input text via MCP."""
        if not self._ensure_mcp_client():
            return False
        
        try:
            result = self.mcp_client.call_tool("send-keys", {
                "selector": target_identifier,
                "text": text,
                "strategy": "id"  # Default strategy
            })
            success = result.get("success", False)
            if not success:
                logger.warning(f"Input text failed: {result.get('message', 'Unknown error')}")
            return success
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error during input_text: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during input_text: {e}")
            return False

    def scroll(self, target_identifier: Optional[str], direction: str) -> bool:
        """Scroll via MCP."""
        if not self._ensure_mcp_client():
            return False
        
        try:
            # Map direction to scroll parameters
            scroll_params = {
                "direction": direction.lower(),
                "distance": 500,  # Default scroll distance
                "duration": 500   # Default duration
            }
            
            result = self.mcp_client.call_tool("scroll", scroll_params)
            success = result.get("success", False)
            if not success:
                logger.warning(f"Scroll failed: {result.get('message', 'Unknown error')}")
            return success
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error during scroll: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during scroll: {e}")
            return False

    def long_press(self, target_identifier: str, duration: int) -> bool:
        """Long press via MCP using swipe with longer duration."""
        if not self._ensure_mcp_client():
            return False
        
        try:
            # For long press, we can use swipe with same start/end coordinates and longer duration
            # First, try to find element to get its coordinates
            find_result = self.mcp_client.call_tool("find-element", {
                "selector": target_identifier,
                "strategy": "id"
            })
            
            if find_result.get("success", False):
                element_data = find_result.get("data", {})
                # Extract coordinates from element if available
                # Otherwise, use a coordinate-based approach
                # For now, use tap-element which might support long press
                # Or use swipe with coordinates
                logger.warning("Long press via element coordinates not fully implemented - using tap")
                result = self.mcp_client.call_tool("tap-element", {
                    "selector": target_identifier,
                    "strategy": "id"
                })
            else:
                logger.error(f"Could not find element for long press: {target_identifier}")
                return False
            
            success = result.get("success", False)
            if not success:
                logger.warning(f"Long press failed: {result.get('message', 'Unknown error')}")
            return success
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error during long_press: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during long_press: {e}")
            return False

    def press_back(self) -> bool:
        """Press back via MCP. Note: MCP server may not have direct back button support."""
        if not self._ensure_mcp_client():
            return False
        
        try:
            # MCP server doesn't have a direct back button tool
            # We could use ADB command or Appium key press, but for now log a warning
            logger.warning("press_back() not directly supported by MCP server - may need custom tool")
            # Try to use swipe from edge as a workaround (Android back gesture)
            # This is a workaround - ideally MCP server should have a back button tool
            result = self.mcp_client.call_tool("swipe", {
                "startX": 50,   # Left edge
                "startY": 960,  # Middle of screen
                "endX": 200,    # Swipe right
                "endY": 960,
                "duration": 300
            })
            success = result.get("success", False)
            if not success:
                logger.warning(f"Back press (swipe workaround) failed: {result.get('message', 'Unknown error')}")
            return success
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error during press_back: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during press_back: {e}")
            return False

    def press_home(self) -> bool:
        """Press home via MCP. Note: MCP server may not have direct home button support."""
        if not self._ensure_mcp_client():
            return False
        
        try:
            # MCP server doesn't have a direct home button tool
            logger.warning("press_home() not directly supported by MCP server - may need custom tool")
            # Similar workaround as back button
            return False  # Not implemented yet
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error during press_home: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during press_home: {e}")
            return False

    def wait_for_toast_to_dismiss(self, timeout_ms: int = 1200):
        """Wait for toast to dismiss."""
        # TODO: Implement toast dismissal waiting logic
        pass

    def get_window_size(self):
        """Get window size."""
        if not self._ensure_mcp_client():
            return {"width": 1080, "height": 1920}  # Default fallback
        
        try:
            result = self.mcp_client.call_tool("get-window-size", {})
            if result.get("success", False):
                data = result.get("data", {})
                # Extract width and height from response
                width = data.get("width") or data.get("windowWidth")
                height = data.get("height") or data.get("windowHeight")
                if width and height:
                    return {"width": int(width), "height": int(height)}
            # Fallback to default
            logger.warning("Could not get window size from MCP, using default")
            return {"width": 1080, "height": 1920}
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error getting window size: {e}")
            return {"width": 1080, "height": 1920}
        except Exception as e:
            logger.error(f"Unexpected error getting window size: {e}")
            return {"width": 1080, "height": 1920}

    def start_video_recording(self):
        """Start video recording."""
        # TODO: Implement video recording start functionality
        pass

    def stop_video_recording(self):
        """Stop video recording."""
        # TODO: Implement video recording stop functionality
        return None

    def save_video_recording(self, data, path):
        """Save video recording."""
        # TODO: Implement video recording save functionality
        pass

    def get_current_package(self) -> Optional[str]:
        """Get current package via MCP session info."""
        if not self._ensure_mcp_client():
            return None
        
        try:
            result = self.mcp_client.call_tool("get-session-info", {})
            if result.get("success", False):
                data = result.get("data", {})
                # Extract package from session info
                package = data.get("package") or data.get("appPackage") or data.get("currentPackage")
                if package:
                    return str(package)
            return None
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error getting current package: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting current package: {e}")
            return None

    def get_current_activity(self) -> Optional[str]:
        """Get current activity via MCP session info."""
        if not self._ensure_mcp_client():
            return None
        
        try:
            result = self.mcp_client.call_tool("get-session-info", {})
            if result.get("success", False):
                data = result.get("data", {})
                # Extract activity from session info
                activity = data.get("activity") or data.get("appActivity") or data.get("currentActivity")
                if activity:
                    return str(activity)
            return None
        except (MCPConnectionError, MCPError) as e:
            logger.error(f"MCP error getting current activity: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting current activity: {e}")
            return None

    def get_current_app_context(self) -> Optional[Tuple[Optional[str], Optional[str]]]:
        """Get current app context via MCP."""
        package = self.get_current_package()
        activity = self.get_current_activity()
        return package, activity

    def terminate_app(self, package_name: str) -> bool:
        """Terminate app via MCP. Note: May not be directly supported."""
        if not self._ensure_mcp_client():
            return False
        
        logger.warning(f"terminate_app({package_name}) not directly supported by MCP server")
        # Could potentially use close-appium and reinitialize, but that's not ideal
        return False  # Not implemented yet

    def launch_app(self) -> bool:
        """Launch app via MCP. Note: App should be launched via initialize-appium."""
        if not self._ensure_mcp_client():
            return False
        
        logger.warning("launch_app() - app should be launched via initialize-appium tool")
        # App is launched when session is initialized
        return self._session_initialized

    def press_back_button(self) -> bool:
        """Press back button via MCP."""
        return self.press_back()