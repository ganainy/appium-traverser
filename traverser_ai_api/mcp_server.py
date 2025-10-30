import asyncio
import logging
from typing import Dict, List, Optional

from fastmcp import FastMCP

# Import the AppiumDriver from removed code
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'removed_appium_code'))
from appium_driver import AppiumDriver

from traverser_ai_api.config import Config

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPAutomationServer:
    def __init__(self):
        self.app = FastMCP("Android Automation Server")
        self.driver: Optional[AppiumDriver] = None
        self.config: Optional[Config] = None
        self._setup_tools()

    def _setup_tools(self):
        @self.app.tool()
        async def initialize_session(app_package: str, app_activity: str, device_udid: Optional[str] = None) -> str:
            """Initialize the Appium session for the specified app."""
            try:
                if self.driver:
                    self.driver.disconnect()
                
                # Create config with the provided parameters
                defaults_path = os.path.join(os.path.dirname(__file__), 'config.py')
                user_config_path = os.path.join(os.path.dirname(__file__), 'user_config.json')
                self.config = Config(defaults_path, user_config_path)
                self.config.APP_PACKAGE = app_package
                self.config.APP_ACTIVITY = app_activity
                if device_udid:
                    self.config.TARGET_DEVICE_UDID = device_udid
                
                self.driver = AppiumDriver(self.config)
                success = self.driver.connect()
                
                if success:
                    logger.info("MCP Automation Server: Session initialized successfully")
                    return "Session initialized successfully"
                else:
                    return "Failed to initialize session"
            except Exception as e:
                logger.error(f"Failed to initialize session: {e}")
                return f"Error initializing session: {str(e)}"

        @self.app.tool()
        async def tap(target_identifier: str, target_bounding_box: Dict, reasoning: str, focus_influence: List[str]) -> str:
            """Perform a tap action on the specified element or coordinates."""
            try:
                if not self.driver:
                    return "No active session. Call initialize_session first."
                
                # Try to find element by identifier first
                element = None
                if target_identifier:
                    try:
                        if target_identifier.startswith("com.") or ":" in target_identifier:
                            # Resource ID
                            element = self.driver.find_element_by_id(target_identifier)
                        else:
                            # Text or content-desc
                            element = self.driver.find_element_by_text(target_identifier)
                    except:
                        pass
                
                if element:
                    # Tap the element
                    result = self.driver.tap_element(element)
                else:
                    # Use coordinates from bounding box
                    bbox = target_bounding_box
                    if bbox and "top_left" in bbox and "bottom_right" in bbox:
                        y1, x1 = bbox["top_left"]
                        y2, x2 = bbox["bottom_right"]
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        result = self.driver.tap_coordinates(center_x, center_y, normalized=False)
                    else:
                        return "Invalid target: no element found and no valid bounding box provided"
                
                if result.get("success"):
                    logger.info(f"Tap action successful: {reasoning}")
                    return "Tap successful"
                else:
                    return f"Tap failed: {result.get('error', 'Unknown error')}"
                    
            except Exception as e:
                logger.error(f"Tap action failed: {e}")
                return f"Tap error: {str(e)}"

        @self.app.tool()
        async def input_text(target_identifier: str, input_text: str, reasoning: str, focus_influence: List[str]) -> str:
            """Input text into the specified element."""
            try:
                if not self.driver:
                    return "No active session. Call initialize_session first."
                
                element = None
                if target_identifier:
                    try:
                        if target_identifier.startswith("com.") or ":" in target_identifier:
                            element = self.driver.find_element_by_id(target_identifier)
                        else:
                            element = self.driver.find_element_by_text(target_identifier)
                    except:
                        pass
                
                if element:
                    result = self.driver.input_text_into_element(element, input_text)
                    if result.get("success"):
                        logger.info(f"Input action successful: {reasoning}")
                        return "Input successful"
                    else:
                        return f"Input failed: {result.get('error', 'Unknown error')}"
                else:
                    return "Input target element not found"
                    
            except Exception as e:
                logger.error(f"Input action failed: {e}")
                return f"Input error: {str(e)}"

        @self.app.tool()
        async def scroll(direction: str, reasoning: str, focus_influence: List[str]) -> str:
            """Scroll in the specified direction (up, down, left, right)."""
            try:
                if not self.driver:
                    return "No active session. Call initialize_session first."
                
                if direction.lower() == "down":
                    result = self.driver.scroll_down()
                elif direction.lower() == "up":
                    result = self.driver.scroll_up()
                elif direction.lower() == "left":
                    result = self.driver.swipe_left()
                elif direction.lower() == "right":
                    result = self.driver.swipe_right()
                else:
                    return f"Invalid scroll direction: {direction}"
                
                if result.get("success"):
                    logger.info(f"Scroll {direction} successful: {reasoning}")
                    return f"Scroll {direction} successful"
                else:
                    return f"Scroll {direction} failed: {result.get('error', 'Unknown error')}"
                    
            except Exception as e:
                logger.error(f"Scroll action failed: {e}")
                return f"Scroll error: {str(e)}"

        @self.app.tool()
        async def long_press(target_identifier: str, target_bounding_box: Dict, duration_ms: int, reasoning: str, focus_influence: List[str]) -> str:
            """Perform a long press on the specified element or coordinates."""
            try:
                if not self.driver:
                    return "No active session. Call initialize_session first."
                
                element = None
                if target_identifier:
                    try:
                        if target_identifier.startswith("com.") or ":" in target_identifier:
                            element = self.driver.find_element_by_id(target_identifier)
                        else:
                            element = self.driver.find_element_by_text(target_identifier)
                    except:
                        pass
                
                if element:
                    result = self.driver.long_press_element(element, duration_ms)
                else:
                    # Use coordinates
                    bbox = target_bounding_box
                    if bbox and "top_left" in bbox and "bottom_right" in bbox:
                        y1, x1 = bbox["top_left"]
                        y2, x2 = bbox["bottom_right"]
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        result = self.driver.tap_coordinates(center_x, center_y, normalized=False, duration_ms=duration_ms)
                    else:
                        return "Invalid target: no element found and no valid bounding box provided"
                
                if result.get("success"):
                    logger.info(f"Long press successful: {reasoning}")
                    return "Long press successful"
                else:
                    return f"Long press failed: {result.get('error', 'Unknown error')}"
                    
            except Exception as e:
                logger.error(f"Long press failed: {e}")
                return f"Long press error: {str(e)}"

        @self.app.tool()
        async def press_back(reasoning: str, focus_influence: List[str]) -> str:
            """Press the back button."""
            try:
                if not self.driver:
                    return "No active session. Call initialize_session first."
                
                result = self.driver.press_back()
                if result.get("success"):
                    logger.info(f"Back press successful: {reasoning}")
                    return "Back press successful"
                else:
                    return f"Back press failed: {result.get('error', 'Unknown error')}"
                    
            except Exception as e:
                logger.error(f"Back press failed: {e}")
                return f"Back press error: {str(e)}"

        @self.app.tool()
        async def press_home(reasoning: str, focus_influence: List[str]) -> str:
            """Press the home button."""
            try:
                if not self.driver:
                    return "No active session. Call initialize_session first."
                
                result = self.driver.press_home()
                if result.get("success"):
                    logger.info(f"Home press successful: {reasoning}")
                    return "Home press successful"
                else:
                    return f"Home press failed: {result.get('error', 'Unknown error')}"
                    
            except Exception as e:
                logger.error(f"Home press failed: {e}")
                return f"Home press error: {str(e)}"

        @self.app.tool()
        async def get_screen_info() -> Dict:
            """Get current screen information including XML and screenshot."""
            try:
                if not self.driver:
                    return {"error": "No active session"}
                
                # Get page source (XML)
                xml = self.driver.get_page_source()
                
                # Get screenshot
                screenshot = self.driver.get_screenshot_as_base64()
                
                return {
                    "xml": xml,
                    "screenshot_base64": screenshot
                }
                
            except Exception as e:
                logger.error(f"Failed to get screen info: {e}")
                return {"error": str(e)}

    def run(self):
        """Run the MCP server."""
        import uvicorn
        uvicorn.run(self.app, host="127.0.0.1", port=8000)

if __name__ == "__main__":
    server = MCPAutomationServer()
    server.run()
