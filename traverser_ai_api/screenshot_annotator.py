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
                           may contain 'target_bounding_box'.
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
            tl_x_norm, tl_y_norm = bbox_data["top_left"]
            br_x_norm, br_y_norm = bbox_data["bottom_right"]

            if not all(isinstance(coord, (int, float)) and 0.0 <= coord <= 1.0 for coord in [tl_x_norm, tl_y_norm, br_x_norm, br_y_norm]):
                 raise ValueError(f"Normalized coordinates invalid or out of range [0.0, 1.0]: {bbox_data}")

            window_size = self.driver.get_window_size()
            if window_size and window_size.get('width') > 0 and window_size.get('height') > 0:
                 img_width = window_size['width']
                 img_height = window_size['height']
                 self.logger.debug(f"Using Appium window size for coord conversion: {img_width}x{img_height}")
            else:
                 self.logger.debug("Appium window size unavailable or invalid, loading image from bytes to get dimensions.")
                 try:
                     with Image.open(BytesIO(original_screenshot_bytes)) as img:
                         img_width, img_height = img.size
                     if img_width <= 0 or img_height <= 0:
                          raise ValueError("Image dimensions from bytes are invalid.")
                     self.logger.debug(f"Using image dimensions from bytes: {img_width}x{img_height}")
                 except Exception as img_err:
                     self.logger.error(f"Failed to get image dimensions from bytes: {img_err}. Cannot proceed with annotation.")
                     return

            x1 = int(tl_x_norm * img_width)
            y1 = int(tl_y_norm * img_height)
            x2 = int(br_x_norm * img_width)
            y2 = int(br_y_norm * img_height)

            if x1 > x2: x1, x2 = x2, x1
            if y1 > y2: y1, y2 = y2, y1

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

        annotated_bytes = None
        try:
            self.logger.debug(f"Drawing indicator at center: {draw_coords}")
            annotated_bytes = utils.draw_indicator_on_image(
                original_screenshot_bytes,
                draw_coords
            )
            if not annotated_bytes:
                 raise ValueError("draw_indicator_on_image returned None")
        except Exception as draw_err:
             self.logger.error(f"Error drawing indicator on image: {draw_err}", exc_info=True)

        if annotated_bytes:
            try:
                # Assuming ANNOTATED_SCREENSHOTS_DIR is an attribute of the config object
                annotated_dir_path = getattr(self.config, 'ANNOTATED_SCREENSHOTS_DIR', None)
                if not annotated_dir_path:
                    self.logger.error("Configuration error: 'ANNOTATED_SCREENSHOTS_DIR' not defined or empty in config.")
                    return

                os.makedirs(annotated_dir_path, exist_ok=True)
                filename = f"annotated_step_{step}_screen_{screen_id}{filename_suffix}"
                filepath = os.path.join(annotated_dir_path, filename)

                with open(filepath, "wb") as f:
                    f.write(annotated_bytes)
                self.logger.info(f"Saved annotated screenshot: {filepath} ({target_log_info})")

            except IOError as io_err:
                 self.logger.error(f"Failed to save annotated screenshot to {filepath}: {io_err}", exc_info=True)
            except Exception as e:
                 filepath_str = filepath if 'filepath' in locals() else f"in {str(annotated_dir_path)}"
                 self.logger.error(f"Unexpected error saving annotated screenshot {filepath_str}: {e}", exc_info=True)
        else:
            self.logger.warning("Skipping saving annotated screenshot because indicator drawing failed.")

