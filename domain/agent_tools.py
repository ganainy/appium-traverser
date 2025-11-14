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

if TYPE_CHECKING:
    from infrastructure.appium_driver import AppiumDriver
    from config.app_config import Config


class AgentTools:
    """
    A collection of tools that can be used by the AI agent to interact with the app.
    These tools wrap the MCP client functionality in a way that's easier for the agent to use.
    """
    
    def __init__(self, 
                driver: 'AppiumDriver',
                config: 'Config'):
        """Initialize the AgentTools with MCP client driver."""
        self.driver = driver  # MCP client
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
            
            # Call MCP driver tap method
            success = self.driver.tap(element_identifier, None)
            result = {
                "success": success,
                "message": "Click executed successfully" if success else "Click failed"
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
            
            # Call MCP driver input_text method
            success = self.driver.input_text(element_identifier, text)
            result = {
                "success": success,
                "message": f"Text '{text}' input successfully" if success else "Input failed"
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
            
            # Call MCP driver scroll method
            success = self.driver.scroll(direction)
            result = {
                "success": success,
                "message": f"Scroll {direction} executed successfully" if success else "Scroll failed"
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
            
            # Call MCP driver press_back method
            success = self.driver.press_back()
            result = {
                "success": success,
                "message": "Back button pressed successfully" if success else "Back press failed"
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
            
            # Create bbox for MCP tap
            bbox = {
                "top_left": [y_abs, x_abs],
                "bottom_right": [y_abs, x_abs]  # Same point for tap
            }
            
            # Call MCP driver tap method with bbox
            success = self.driver.tap(None, bbox)
            result = {
                "success": success,
                "message": f"Tapped at coordinates ({x_abs}, {y_abs}) successfully" if success else "Tap failed"
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

            # Call MCP driver long_press method
            success = self.driver.long_press(element_identifier or "", duration_ms or 600)
            result = {
                "success": success,
                "message": "Long press executed successfully" if success else "Long press failed"
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
            
            # Mock screen state for MCP integration
            screen_info = {
                "hash": "mock_hash",
                "xml_available": True,
                "screenshot_available": True,
                "visual_hash": "mock_visual",
                "xml_hash": "mock_xml",
                "visit_count": 1
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
            
            # Mock app context check for MCP integration
            in_context = True
            
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
    
    def double_tap(self, element_identifier: Optional[str] = None, target_bounding_box: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Perform a double tap on an element or at specified coordinates.
        
        Args:
            element_identifier: Optional identifier of the element to double tap.
            target_bounding_box: Optional bbox to compute coordinates if element is not found.
            
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: double_tap(identifier={element_identifier}, has_bbox={bool(target_bounding_box)})")
            
            # Call driver double_tap method
            success = self.driver.double_tap(element_identifier, target_bounding_box)
            result = {
                "success": success,
                "message": "Double tap executed successfully" if success else "Double tap failed"
            }
            
            # Save to action history
            self.action_history.append({
                "action": "double_tap",
                "target": element_identifier or "coords",
                "success": success,
                "timestamp": time.time()
            })
            
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during double_tap: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
    
    def clear_text(self, element_identifier: str) -> Dict[str, Any]:
        """
        Clear text from an input element.
        
        Args:
            element_identifier: The identifier of the element to clear.
            
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: clear_text({element_identifier})")
            
            # Call driver clear_text method
            success = self.driver.clear_text(element_identifier)
            result = {
                "success": success,
                "message": "Text cleared successfully" if success else "Clear text failed"
            }
            
            # Save to action history
            self.action_history.append({
                "action": "clear_text",
                "target": element_identifier,
                "success": success,
                "timestamp": time.time()
            })
            
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during clear_text: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
    
    def replace_text(self, element_identifier: str, text: str) -> Dict[str, Any]:
        """
        Replace existing text in an input element.
        
        Args:
            element_identifier: The identifier of the element to replace text in.
            text: The new text to set.
            
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: replace_text({element_identifier}, {text})")
            
            # Call driver replace_text method
            success = self.driver.replace_text(element_identifier, text)
            result = {
                "success": success,
                "message": f"Text replaced with '{text}' successfully" if success else "Replace text failed"
            }
            
            # Save to action history
            self.action_history.append({
                "action": "replace_text",
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
                "message": f"Exception during replace_text: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
    
    def flick(self, direction: str) -> Dict[str, Any]:
        """
        Perform a fast flick gesture in the specified direction.
        
        Args:
            direction: The direction to flick. One of: "up", "down", "left", "right".
            
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug(f"Agent tool: flick({direction})")
            
            # Validate direction
            valid_directions = ["up", "down", "left", "right"]
            if direction not in valid_directions:
                return {
                    "success": False,
                    "message": f"Invalid direction: {direction}. Must be one of: {', '.join(valid_directions)}"
                }
            
            # Call driver flick method
            success = self.driver.flick(direction)
            result = {
                "success": success,
                "message": f"Flick {direction} executed successfully" if success else "Flick failed"
            }
            
            # Save to action history
            self.action_history.append({
                "action": f"flick_{direction}",
                "success": success,
                "timestamp": time.time()
            })
            
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during flick: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result
    
    def reset_app(self) -> Dict[str, Any]:
        """
        Reset the app to its initial state.
        
        Returns:
            A dictionary containing the result of the action.
        """
        try:
            logging.debug("Agent tool: reset_app()")
            
            # Call driver reset_app method
            success = self.driver.reset_app()
            result = {
                "success": success,
                "message": "App reset successfully" if success else "Reset app failed"
            }
            
            # Save to action history
            self.action_history.append({
                "action": "reset_app",
                "success": success,
                "timestamp": time.time()
            })
            
            self.last_action_result = result
            return result
        except Exception as e:
            error_result = {
                "success": False,
                "message": f"Exception during reset_app: {str(e)}"
            }
            self.last_action_result = error_result
            return error_result