import logging
import os
from io import BytesIO
from PIL import Image
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .appium_driver import AppiumDriver # To avoid circular import
    # Assuming config is an object or a dict-like structure
    # If it's a module, you might import it directly: from . import config
    # For this example, let's assume it's passed as an object/dict.
    # from .config import Config 

# It seems 'utils' is a module in your project.
from . import utils # Or specific import: from .utils import draw_indicator_on_image

class ScreenshotAnnotator:
    """Handles the annotation and saving of screenshots."""

    def __init__(self, driver: 'AppiumDriver', config_obj: Any): # config_obj can be your config module or a dict
        self.driver = driver
        self.config = config_obj 
        self.logger = logging.getLogger(__name__)

    def save_annotated_screenshot(self,
                                original_screenshot_bytes: bytes,
                                step: int,
                                screen_id: int,
                                ai_suggestion: Optional[Dict[str, Any]]):
        """
        Takes the original screenshot, draws indicator based on AI's bbox center,
        and saves it WITH absolute bbox coordinates in the filename.

        Args:
            original_screenshot_bytes: The raw PNG bytes of the screen.
            step: The current crawl step number.
            screen_id: The database ID of the current screen state.
            ai_suggestion: The dictionary returned by the AI assistant, which
            may contain 'target_bounding_box' with either normalized [0.0-1.0]
            or absolute pixel coordinates.
        """
        if not original_screenshot_bytes:
            self.logger.debug("Skipping annotated screenshot: No original image provided.")
            return
        if not ai_suggestion:
            self.logger.debug("Skipping annotated screenshot: No AI suggestion provided.")
            return

        bbox_data = ai_suggestion.get("target_bounding_box")
        action_type = ai_suggestion.get("action", "unknown")

        if not bbox_data:
            self.logger.debug(f"Skipping annotated screenshot: AI suggestion for action '{action_type}' has no 'target_bounding_box'.")
            return

        self.logger.debug(f"Attempting annotation using AI bbox: {bbox_data}")

        try:
            # Get screen dimensions first as we'll need them for both coordinate types
            img_width = img_height = None
            
            # Try to get dimensions from Appium first
            try:
                window_size = self.driver.get_window_size()
                if isinstance(window_size, dict):
                    width = window_size.get('width')
                    height = window_size.get('height')
                    if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
                        img_width = int(width)
                        img_height = int(height)
                        self.logger.debug(f"Using Appium window size for coord conversion: {img_width}x{img_height}")
                    else:
                        self.logger.debug("Invalid window dimensions from Appium")
            except Exception as e:
                self.logger.debug(f"Error getting window size from Appium: {e}")

            # If Appium dimensions are not available, try getting them from the image
            if img_width is None or img_height is None:
                self.logger.debug("Appium window size unavailable, loading image from bytes to get dimensions.")
                try:
                    with Image.open(BytesIO(original_screenshot_bytes)) as img:
                        img_width, img_height = img.size
                        if not (isinstance(img_width, int) and isinstance(img_height, int) and img_width > 0 and img_height > 0):
                            raise ValueError("Invalid image dimensions")
                    self.logger.debug(f"Using image dimensions from bytes: {img_width}x{img_height}")
                except Exception as img_err:
                    self.logger.error(f"Failed to get image dimensions from bytes: {img_err}. Cannot proceed with annotation.")
                    return

            # Ensure we have valid dimensions at this point
            if img_width is None or img_height is None or img_width <= 0 or img_height <= 0:
                self.logger.error("Failed to obtain valid image dimensions. Cannot proceed with annotation.")
                return

            # Extract coordinates
            tl_x, tl_y = bbox_data["top_left"]
            br_x, br_y = bbox_data["bottom_right"]

            # Check if coordinates are already normalized (between 0 and 1)
            coords_are_normalized = all(isinstance(coord, (int, float)) and 0.0 <= float(coord) <= 1.0 
                                    for coord in [tl_x, tl_y, br_x, br_y])

            if coords_are_normalized:
                self.logger.debug("Processing normalized coordinates")
                x1 = int(tl_x * img_width)
                y1 = int(tl_y * img_height)
                x2 = int(br_x * img_width)
                y2 = int(br_y * img_height)
            else:
                self.logger.debug("Processing absolute pixel coordinates")
                # Convert to int if they aren't already
                x1 = int(tl_x)
                y1 = int(tl_y)
                x2 = int(br_x)
                y2 = int(br_y)

            # Ensure coordinates are in correct order
            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1

            # Clip coordinates to image boundaries
            x1 = max(0, min(x1, img_width - 1))
            y1 = max(0, min(y1, img_height - 1))
            x2 = max(0, min(x2, img_width - 1))
            y2 = max(0, min(y2, img_height - 1))

            if x1 >= x2 or y1 >= y2:
                self.logger.warning(f"Bounding box collapsed after conversion/clipping ({x1},{y1},{x2},{y2}). Skipping annotation.")
                return

            filename_suffix = f"_bbox_{x1}_{y1}_{x2}_{y2}.png"
            target_log_info = f"bbox=({x1},{y1},{x2},{y2})"
            center_x = int((x1 + x2) / 2)
            center_y = int((y1 + y2) / 2)
            draw_coords = (center_x, center_y)

        except (KeyError, IndexError, TypeError, ValueError) as e:
            self.logger.error(f"Error processing AI bounding box {bbox_data}: {e}. Skipping annotation saving.")
            return
        except Exception as e:
            self.logger.error(f"Unexpected error processing coordinates/dimensions: {e}", exc_info=True)
            return

        # Draw the indicator
        try:
            self.logger.debug(f"Drawing indicator at center: {draw_coords}")
            annotated_bytes = utils.draw_indicator_on_image(original_screenshot_bytes, draw_coords)
            if not isinstance(annotated_bytes, bytes):
                raise ValueError("draw_indicator_on_image did not return valid bytes")
        except Exception as draw_err:
            self.logger.error(f"Error drawing indicator on image: {draw_err}", exc_info=True)
            return

        # Get the output directory from config
        annotated_dir_path = getattr(self.config, 'ANNOTATED_SCREENSHOTS_DIR', None)
        if not annotated_dir_path:
            self.logger.error("Configuration error: 'ANNOTATED_SCREENSHOTS_DIR' not defined or empty in config.")
            return

        # Initialize filepath to None
        filepath = None

        try:
            # Prepare the output directory and file path
            os.makedirs(annotated_dir_path, exist_ok=True)
            filename = f"annotated_step_{step}_screen_{screen_id}{filename_suffix}"
            filepath = os.path.join(annotated_dir_path, filename)

            # Save the annotated image
            with open(filepath, "wb") as f:
                f.write(annotated_bytes)
            self.logger.info(f"Saved annotated screenshot: {filepath} ({target_log_info})")
            
        except IOError as io_err:
            # Handle file I/O errors
            error_path = filepath if filepath else f"in directory {annotated_dir_path}"
            self.logger.error(f"Failed to save annotated screenshot to {error_path}: {io_err}", exc_info=True)
        except Exception as e:
            # Handle any other unexpected errors
            error_location = filepath if filepath else f"in directory {annotated_dir_path}"
            self.logger.error(f"Unexpected error saving annotated screenshot {error_location}: {e}", exc_info=True)

