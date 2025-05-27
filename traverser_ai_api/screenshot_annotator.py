import logging
import os
from io import BytesIO
from PIL import Image # Keep this import if you still use Image directly anywhere else, though not strictly needed for the changes below if utils handles all PIL.
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .appium_driver import AppiumDriver
    # from .config import Config 

# Import the new drawing utility (and any other needed utils)
from . import utils # This assumes utils.py is in the same directory

class ScreenshotAnnotator:
    """Handles the annotation and saving of screenshots."""

    def __init__(self, driver: 'AppiumDriver', config_obj: Any):
        self.driver = driver
        self.config = config_obj 
        self.logger = logging.getLogger(__name__)

    def save_annotated_screenshot(self,
                                original_screenshot_bytes: bytes,
                                step: int,
                                screen_id: int,
                                ai_suggestion: Optional[Dict[str, Any]]):
        """
        Takes the original screenshot, draws the AI's suggested bounding box,
        and saves it with absolute bbox coordinates in the filename.
        """
        if not original_screenshot_bytes:
            self.logger.debug("Skipping annotated screenshot: No original image provided.")
            return
        if not ai_suggestion:
            self.logger.debug("Skipping annotated screenshot: No AI suggestion provided.")
            return

        bbox_data = ai_suggestion.get("target_bounding_box")
        action_type = ai_suggestion.get("action", "unknown")

        # Only try to draw a box if it's relevant (e.g., for click, input)
        # and if bbox_data is present.
        if not bbox_data or action_type not in ["click", "input"]:
            self.logger.debug(
                f"Skipping bounding box annotation: AI suggestion for action '{action_type}' "
                f"has no 'target_bounding_box' or action type does not require it."
            )
            # If you still want to save the original unannotated image or handle it differently,
            # you can add that logic here. For now, we just return.
            return

        self.logger.debug(f"Attempting annotation using AI bbox: {bbox_data}")

        img_width: Optional[int] = None
        img_height: Optional[int] = None
        
        try:
            # Try to get dimensions from Appium first
            try:
                window_size = self.driver.get_window_size()
                if isinstance(window_size, dict):
                    width = window_size.get('width')
                    height = window_size.get('height')
                    if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
                        img_width = int(width)
                        img_height = int(height)
                        self.logger.debug(f"Using Appium window size for coord reference: {img_width}x{img_height}")
            except Exception as e:
                self.logger.debug(f"Error getting window size from Appium, will use image dimensions: {e}")

            # If Appium dimensions are not available, try getting them from the image
            if img_width is None or img_height is None:
                self.logger.debug("Appium window size unavailable, loading image from bytes to get dimensions.")
                try:
                    with Image.open(BytesIO(original_screenshot_bytes)) as img_for_size:
                        img_width, img_height = img_for_size.size
                    if not (isinstance(img_width, int) and isinstance(img_height, int) and img_width > 0 and img_height > 0):
                        raise ValueError("Invalid image dimensions from image bytes")
                    self.logger.debug(f"Using image dimensions from bytes: {img_width}x{img_height}")
                except Exception as img_err:
                    self.logger.error(f"Failed to get image dimensions from bytes: {img_err}. Cannot proceed with annotation.")
                    return

            if not (img_width and img_height and img_width > 0 and img_height > 0):
                 self.logger.error("Failed to obtain valid image dimensions. Cannot proceed with annotation.")
                 return

            # AI provides coordinates as [Y, X]
            # top_left: [y1, x1], bottom_right: [y2, x2]
            raw_y1, raw_x1 = bbox_data["top_left"]
            raw_y2, raw_x2 = bbox_data["bottom_right"]

            # Check if coordinates are normalized (all between 0.0 and 1.0 inclusive)
            # A simple heuristic: if any coordinate is > 1.0, assume absolute.
            # More robust: check if *all* are <= 1.0 (and >= 0).
            # The AI prompt specifies Y,X order for coordinates in the JSON.
            coords_are_normalized = all(0.0 <= float(c) <= 1.0 for c in [raw_y1, raw_x1, raw_y2, raw_x2])

            if coords_are_normalized:
                self.logger.debug(f"Processing normalized coordinates: y1={raw_y1}, x1={raw_x1}, y2={raw_y2}, x2={raw_x2}")
                # Denormalize: AI gives [Y,X], so map y to height, x to width
                x1 = int(float(raw_x1) * img_width)
                y1 = int(float(raw_y1) * img_height)
                x2 = int(float(raw_x2) * img_width)
                y2 = int(float(raw_y2) * img_height)
            else:
                self.logger.debug(f"Processing absolute pixel coordinates: y1={raw_y1}, x1={raw_x1}, y2={raw_y2}, x2={raw_x2}")
                # AI provides [Y,X], assign directly after ensuring they are int
                x1 = int(float(raw_x1))
                y1 = int(float(raw_y1))
                x2 = int(float(raw_x2))
                y2 = int(float(raw_y2))
            
            self.logger.debug(f"Converted/Raw box: x1={x1}, y1={y1}, x2={x2}, y2={y2}")

            # Ensure coordinates are in top-left to bottom-right order
            # (x1 should be less than x2, y1 should be less than y2)
            abs_x1 = min(x1, x2)
            abs_y1 = min(y1, y2)
            abs_x2 = max(x1, x2)
            abs_y2 = max(y1, y2)

            # Clip coordinates to image boundaries
            # Image.crop and ImageDraw.rectangle handle coordinates slightly differently with edges.
            # For ImageDraw.rectangle, coordinates can extend to width/height.
            clipped_x1 = max(0, abs_x1)
            clipped_y1 = max(0, abs_y1)
            clipped_x2 = min(img_width, abs_x2)  # Can be equal to img_width
            clipped_y2 = min(img_height, abs_y2) # Can be equal to img_height
            
            self.logger.debug(f"Clipped box: x1={clipped_x1}, y1={clipped_y1}, x2={clipped_x2}, y2={clipped_y2}")


            # If the box is collapsed (e.g., x1 == x2 or y1 == y2) or invalid, skip drawing
            if clipped_x1 >= clipped_x2 or clipped_y1 >= clipped_y2:
                self.logger.warning(
                    f"Bounding box is zero-size or invalid after conversion/clipping "
                    f"({clipped_x1},{clipped_y1},{clipped_x2},{clipped_y2}). Skipping drawing."
                )
                # Save the original image if desired, or just return
                # For now, we'll just use the original bytes if drawing is skipped.
                annotated_bytes_to_save = original_screenshot_bytes
                filename_suffix = "_no_bbox.png" # Indicate no box was drawn
                target_log_info = "no_bbox"
            else:
                # Prepare for drawing the rectangle
                # The draw_rectangle_on_image function expects (x1, y1, x2, y2)
                draw_box_coords = (clipped_x1, clipped_y1, clipped_x2, clipped_y2)
                filename_suffix = f"_bbox_{clipped_x1}_{clipped_y1}_{clipped_x2}_{clipped_y2}.png"
                target_log_info = f"bbox=({draw_box_coords})"
                
                # Draw the bounding box
                self.logger.debug(f"Drawing bounding box: {draw_box_coords}")
                # Use the new utility function
                annotated_bytes_from_util = utils.draw_rectangle_on_image(original_screenshot_bytes, draw_box_coords)
                
                if not isinstance(annotated_bytes_from_util, bytes):
                    # Log error and fall back to original image if drawing failed
                    self.logger.error("utils.draw_rectangle_on_image did not return valid bytes. Using original screenshot.")
                    annotated_bytes_to_save = original_screenshot_bytes
                    filename_suffix = "_draw_error.png"
                    target_log_info += "_draw_error"
                else:
                    annotated_bytes_to_save = annotated_bytes_from_util

        except (KeyError, IndexError, TypeError, ValueError) as e:
            self.logger.error(f"Error processing AI bounding box data {bbox_data}: {e}. Saving original screenshot.")
            annotated_bytes_to_save = original_screenshot_bytes
            filename_suffix = "_bbox_error.png"
            target_log_info = "bbox_error"
        except Exception as e:
            self.logger.error(f"Unexpected error during coordinate processing or drawing: {e}", exc_info=True)
            annotated_bytes_to_save = original_screenshot_bytes
            filename_suffix = "_unexpected_error.png"
            target_log_info = "unexpected_error"


        # --- Saving logic (mostly unchanged) ---
        annotated_dir_path = getattr(self.config, 'ANNOTATED_SCREENSHOTS_DIR', None)
        if not annotated_dir_path:
            self.logger.error("Configuration error: 'ANNOTATED_SCREENSHOTS_DIR' not defined or empty in config.")
            return

        filepath = None
        try:
            os.makedirs(annotated_dir_path, exist_ok=True)
            # Ensure filename_suffix and target_log_info are defined in all paths above
            filename = f"annotated_step_{step}_screen_{screen_id}{filename_suffix}"
            filepath = os.path.join(annotated_dir_path, filename)

            with open(filepath, "wb") as f:
                f.write(annotated_bytes_to_save) # Use the potentially annotated or original bytes
            self.logger.info(f"Saved screenshot: {filepath} ({target_log_info})")
            
        except IOError as io_err:
            error_path = filepath if filepath else f"in directory {annotated_dir_path}"
            self.logger.error(f"Failed to save screenshot to {error_path}: {io_err}", exc_info=True)
        except Exception as e:
            error_location = filepath if filepath else f"in directory {annotated_dir_path}"
            self.logger.error(f"Unexpected error saving screenshot {error_location}: {e}", exc_info=True)
