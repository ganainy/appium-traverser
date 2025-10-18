"""
Agent tools module for the Android App Crawler.

This module provides a set of tools that can be used by the AI agent to interact
with the Android app under test. Each tool is implemented as a function that performs
a specific action and returns a result.
"""
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.remote.webelement import WebElement

if TYPE_CHECKING:
    from action_executor import ActionExecutor
    from action_mapper import ActionMapper
    from app_context_manager import AppContextManager
    from appium_driver import AppiumDriver
    from config import Config
    from screen_state_manager import ScreenStateManager


class AgentTools:
    """
    A collection of tools that can be used by the AI agent to interact with the app.
    These tools wrap the existing functionality in a way that's easier for the agent to use.
    """
    
    def __init__(self, 
                driver: 'AppiumDriver',
                action_executor: 'ActionExecutor',
                action_mapper: 'ActionMapper',
                screen_state_manager: 'ScreenStateManager',
                app_context_manager: 'AppContextManager',
                config: 'Config'):
        """Initialize the AgentTools with required components."""
        self.driver = driver
        self.action_executor = action_executor
        self.action_mapper = action_mapper
        self.screen_state_manager = screen_state_manager
        self.app_context_manager = app_context_manager
        self.cfg = config
        self.last_action_result = None
        self.action_history = []
        
    def click_element(self, element_identifier: str) -> Dict[str, Any]:
        """
        Click on an element identified by the given identifier.
        
        Args:
            element_identifier: The identifier of the element to click.
            
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: click_element({element_identifier})")
            
            # Create an action request for the mapper
            action_request = {
                "action": "click",
                "target_identifier": element_identifier
            }
            
            # Map the action to an Appium action
            mapped_action = self.action_mapper.map_ai_action_to_appium(action_request)
            if not mapped_action:
                result = {
                    "success": False,
                    "message": f"Failed to find element with identifier: {element_identifier}"
                }
            else:
                # Execute the action
                success = self.action_executor.execute_action(mapped_action)
                result = {
                    "success": success,
                    "message": "Click executed successfully" if success else f"Click failed: {self.action_executor.last_error_message}"
                }
                
                # Save to action history
                self.action_history.append({
                    "action": "click",
                    "target": element_identifier,
                    "success": success,
                    "timestamp": time.time()
                })
                
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during click: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
            
    def input_text(self, element_identifier: str, text: str) -> Dict[str, Any]:
        """
        Input text into an element identified by the given identifier.
        
        Args:
            element_identifier: The identifier of the element to input text into.
            text: The text to input.
            
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: input_text({element_identifier}, {text})")
            
            # Create an action request for the mapper
            action_request = {
                "action": "input",
                "target_identifier": element_identifier,
                "input_text": text
            }
            
            # Map the action to an Appium action
            mapped_action = self.action_mapper.map_ai_action_to_appium(action_request)
            if not mapped_action:
                result = {
                    "success": False,
                    "message": f"Failed to find element with identifier: {element_identifier}"
                }
            else:
                # Execute the action
                success = self.action_executor.execute_action(mapped_action)
                result = {
                    "success": success,
                    "message": f"Text '{text}' input successfully" if success else f"Input failed: {self.action_executor.last_error_message}"
                }
                
                # Save to action history
                self.action_history.append({
                    "action": "input",
                    "target": element_identifier,
                    "text": text,
                    "success": success,
                    "timestamp": time.time()
                })
                
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during input: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
    
    def scroll(self, direction: str) -> Dict[str, Any]:
        """
        Scroll the screen in the specified direction.
        
        Args:
            direction: The direction to scroll. One of: "up", "down", "left", "right".
            
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: scroll({direction})")
            
            # Validate direction
            valid_directions = ["up", "down", "left", "right"]
            if direction not in valid_directions:
                return {
                    "success": False,
                    "message": f"Invalid direction: {direction}. Must be one of: {', '.join(valid_directions)}"
                }
            
            # Create an action request for the mapper
            action_type = f"scroll_{direction}" if direction in ["up", "down"] else f"swipe_{direction}"
            action_request = {
                "action": action_type
            }
            
            # Map the action to an Appium action
            mapped_action = self.action_mapper.map_ai_action_to_appium(action_request)
            if not mapped_action:
                result = {
                    "success": False,
                    "message": f"Failed to map scroll action for direction: {direction}"
                }
            else:
                # Execute the action
                success = self.action_executor.execute_action(mapped_action)
                result = {
                    "success": success,
                    "message": f"Scroll {direction} executed successfully" if success else f"Scroll failed: {self.action_executor.last_error_message}"
                }
                
                # Save to action history
                self.action_history.append({
                    "action": f"scroll_{direction}",
                    "success": success,
                    "timestamp": time.time()
                })
                
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during scroll: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
    
    def press_back(self) -> Dict[str, Any]:
        """
        Press the back button.
        
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug("Agent tool: press_back()")
            
            # Create an action request for the mapper
            action_request = {
                "action": "back"
            }
            
            # Map the action to an Appium action
            mapped_action = self.action_mapper.map_ai_action_to_appium(action_request)
            if not mapped_action:
                result = {
                    "success": False,
                    "message": "Failed to map back action"
                }
            else:
                # Execute the action
                success = self.action_executor.execute_action(mapped_action)
                result = {
                    "success": success,
                    "message": "Back button pressed successfully" if success else f"Back press failed: {self.action_executor.last_error_message}"
                }
                
                # Save to action history
                self.action_history.append({
                    "action": "back",
                    "success": success,
                    "timestamp": time.time()
                })
                
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during back press: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
    
    def tap_coordinates(self, x: float, y: float, normalized: bool = True, duration_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Tap on the screen at the given coordinates.
        
        Args:
            x: The x coordinate to tap.
            y: The y coordinate to tap.
            normalized: Whether the coordinates are normalized (0-1) or absolute pixels.
            
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: tap_coordinates({x}, {y}, normalized={normalized}, duration_ms={duration_ms})")
            
            # Convert normalized coordinates to absolute if needed
            if normalized:
                window_size = self.driver.get_window_size()
                if not window_size:
                    return {
                        "success": False,
                        "message": "Failed to get window size for coordinate calculation"
                    }
                
                x_abs = int(x * window_size['width'])
                y_abs = int(y * window_size['height'])
            else:
                x_abs = int(x)
                y_abs = int(y)
            
            # Create an action for the executor
            action_details = {
                "type": "tap_coords",
                "coordinates": (x_abs, y_abs)
            }
            if isinstance(duration_ms, (int, float)):
                try:
                    action_details["duration_ms"] = int(duration_ms)
                except Exception:
                    pass
            
            # Execute the action
            success = self.action_executor.execute_action(action_details)
            result = {
                "success": success,
                "message": f"Tapped at coordinates ({x_abs}, {y_abs}) successfully" if success else f"Tap failed: {self.action_executor.last_error_message}"
            }
            
            # Save to action history
            self.action_history.append({
                "action": "tap_coordinates",
                "x": x_abs,
                "y": y_abs,
                "success": success,
                "timestamp": time.time()
            })
            
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during coordinate tap: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result

    def long_press(self, element_identifier: Optional[str] = None, target_bounding_box: Optional[Dict[str, Any]] = None, duration_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Perform a long press on an element or at specified coordinates.

        Args:
            element_identifier: Optional identifier of the element to long press.
            target_bounding_box: Optional bbox to compute coordinates if element is not found.
            duration_ms: Optional override duration in milliseconds.

        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: long_press(identifier={element_identifier}, has_bbox={bool(target_bounding_box)}, duration_ms={duration_ms})")

            action_request: Dict[str, Any] = {"action": "long_press"}
            if element_identifier:
                action_request["target_identifier"] = element_identifier
            if isinstance(target_bounding_box, dict):
                action_request["target_bounding_box"] = target_bounding_box

            mapped_action = self.action_mapper.map_ai_action_to_appium(action_request)
            if not mapped_action:
                result = {
                    "success": False,
                    "message": "Failed to map long_press action"
                }
            else:
                # If duration provided, pass through for coordinate taps
                if isinstance(duration_ms, (int, float)) and mapped_action.get("type") == "tap_coords":
                    try:
                        mapped_action["duration_ms"] = int(duration_ms)
                    except Exception:
                        pass
                success = self.action_executor.execute_action(mapped_action)
                result = {
                    "success": success,
                    "message": "Long press executed successfully" if success else f"Long press failed: {self.action_executor.last_error_message}"
                }

                # Save to action history
                self.action_history.append({
                    "action": "long_press",
                    "target": element_identifier or "coords",
                    "success": success,
                    "timestamp": time.time()
                })

            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during long_press: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
    
    def get_screen_state(self) -> Dict[str, Any]:
        """
        Get information about the current screen state.
        
        Returns:
            A dictionary containing information about the current screen.
        """
        try:
            logging.debug("Agent tool: get_screen_state()")
            
            screen = self.screen_state_manager.get_current_screen_representation(run_id=0, step_number=0)
            if not screen or not screen.screenshot_bytes:
                return {
                    "success": False,
                    "message": "Failed to get current screen state"
                }
            
            # Process the state but don't record it in the database yet
            screen_info = {
                "hash": screen.composite_hash,
                "xml_available": screen.xml_content is not None and len(screen.xml_content) > 0,
                "screenshot_available": screen.screenshot_bytes is not None and len(screen.screenshot_bytes) > 0,
                "visual_hash": screen.visual_hash,
                "xml_hash": screen.xml_hash,
                "visit_count": self.screen_state_manager.get_visit_count(screen.composite_hash)
            }
            
            return {
                "success": True,
                "screen_info": screen_info,
                "message": "Screen state retrieved successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Exception while getting screen state: {str(e)}"
            }
    
    def get_action_history(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get the history of actions performed by the agent.
        
        Args:
            limit: The maximum number of actions to return.
            
        Returns:
            A dictionary containing the action history.
        """
        try:
            logging.debug(f"Agent tool: get_action_history(limit={limit})")
            
            # Get the most recent actions up to the limit
            recent_actions = self.action_history[-limit:] if self.action_history else []
            
            return {
                "success": True,
                "actions": recent_actions,
                "message": f"Retrieved {len(recent_actions)} recent actions"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Exception while getting action history: {str(e)}"
            }
    
    def check_app_context(self) -> Dict[str, Any]:
        """
        Check if the app is still in the foreground and try to restore it if not.
        
        Returns:
            A dictionary indicating whether the app is in the foreground.
        """
        try:
            logging.debug("Agent tool: check_app_context()")
            
            in_context = self.app_context_manager.ensure_in_app()
            
            return {
                "success": True,
                "in_app_context": in_context,
                "message": "App is in foreground" if in_context else "App is not in foreground, attempted to restore"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Exception checking app context: {str(e)}"
            }
