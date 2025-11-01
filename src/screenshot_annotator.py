import json  # For annotations.json
import logging
import os
from io import BytesIO
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PIL import Image, ImageDraw  # Added ImageDraw

if TYPE_CHECKING:
    from appium_driver import AppiumDriver
try:
    from traverser_ai_api.config import Config
except ImportError:
    from traverser_ai_api.config import Config
try:
    from traverser_ai_api import utils
except ImportError:
    import utils

class ScreenshotAnnotator:
    def __init__(self, driver: 'AppiumDriver', app_config: Config):
        self.driver = driver
        self.cfg = app_config
        self.logger = logging.getLogger(__name__)

        if not hasattr(self.cfg, 'ANNOTATED_SCREENSHOTS_DIR') or not self.cfg.ANNOTATED_SCREENSHOTS_DIR:
            raise ValueError("ScreenshotAnnotator: ANNOTATED_SCREENSHOTS_DIR is required.")
        # SCREENSHOTS_DIR is for the raw screenshots where annotations.json will live
        if not hasattr(self.cfg, 'SCREENSHOTS_DIR') or not self.cfg.SCREENSHOTS_DIR:
            raise ValueError("ScreenshotAnnotator: SCREENSHOTS_DIR is required for master annotation file.")
        
        # Ensure the directory for SCREENSHOTS_DIR (raw screenshots) exists before resolving master_annotation_file_path
        # Config class should have already created this, but an extra check is fine.
        if self.cfg.SCREENSHOTS_DIR: # Check if the path is not None or empty
             os.makedirs(str(self.cfg.SCREENSHOTS_DIR), exist_ok=True)
             self.master_annotation_file_path = os.path.join(str(self.cfg.SCREENSHOTS_DIR), "annotations.json")
        else: # Should not happen if config is correctly loaded and SCREENSHOTS_DIR is mandatory
            self.logger.critical("SCREENSHOTS_DIR is not configured properly. Master annotation file path cannot be set.")
            # Potentially raise an error or set a flag indicating this annotator is partially non-functional
            self.master_annotation_file_path = None # Or some other indicator of a problem

        if not self.master_annotation_file_path:
            logging.error("Master annotation file path could not be determined due to missing SCREENSHOTS_DIR config.")

    # ... (rest of the save_annotated_screenshot and update_master_annotation_file methods from previous response) ...
    # (The save_annotated_screenshot method provided in the user's prompt context is suitable to be kept)
    # (The update_master_annotation_file method from my previous response is the one for the new JSON file)

    def save_annotated_screenshot(self,
                                  original_screenshot_bytes: bytes,
                                  step: int,
                                  screen_id: int,
                                  ai_suggestion: Optional[Dict[str, Any]],
                                  ) -> Optional[str]:
        if not original_screenshot_bytes:
            self.logger.debug("Skipping annotated screenshot: No original image bytes provided.")
            return None
        
        annotated_bytes_to_save = original_screenshot_bytes
        filename_suffix = "_original.png" 
        target_log_info = "original"

        bbox_data = None
        action_type = "unknown"

        if ai_suggestion:
            bbox_data = ai_suggestion.get("target_bounding_box") 
            action_type = ai_suggestion.get("action", "unknown")
        else: 
            self.logger.debug("No AI suggestion provided. Saving original image for annotated screenshot.")
            # Fall through to save the original image under ANNOTATED_SCREENSHOTS_DIR with a generic name
            # Or, if ai_suggestion is None and you don't want to save anything in this case:
            # return None 


        if bbox_data and isinstance(bbox_data, dict) and action_type in ["click", "input"]:
            self.logger.debug(f"Attempting annotation for action '{action_type}' using AI bbox: {bbox_data}")
            
            img_width: Optional[int] = None
            img_height: Optional[int] = None
            
            try:
                window_size = self.driver.get_window_size()
                if window_size and isinstance(window_size.get('width'), int) and isinstance(window_size.get('height'), int):
                    img_width = window_size['width']
                    img_height = window_size['height']
                    self.logger.debug(f"Using Appium window size for coordinate reference: {img_width}x{img_height}")
                
                if not (img_width and img_height and img_width > 0 and img_height > 0):
                    self.logger.debug("Appium window size unavailable/invalid, loading image from bytes to get dimensions.")
                    try:
                        with Image.open(BytesIO(original_screenshot_bytes)) as img_for_size:
                            img_width, img_height = img_for_size.size
                        if not (isinstance(img_width, int) and isinstance(img_height, int) and img_width > 0 and img_height > 0):
                            raise ValueError("Invalid image dimensions from image bytes")
                        self.logger.debug(f"Using image dimensions from bytes: {img_width}x{img_height}")
                    except Exception as img_err:
                        self.logger.error(f"Failed to get image dimensions from bytes: {img_err}. Cannot proceed with annotation drawing.")

                if not (img_width and img_height and img_width > 0 and img_height > 0):
                    self.logger.error("Failed to obtain valid image/screen dimensions. Cannot draw bounding box for action target.")
                else:
                    raw_y1, raw_x1 = bbox_data.get("top_left", [0,0])
                    raw_y2, raw_x2 = bbox_data.get("bottom_right", [0,0])

                    coords_are_normalized = all(0.0 <= float(c) <= 1.0 for c in [raw_y1, raw_x1, raw_y2, raw_x2] if isinstance(c, (int,float,str)))

                    if coords_are_normalized:
                        x1 = int(float(raw_x1) * img_width)
                        y1 = int(float(raw_y1) * img_height)
                        x2 = int(float(raw_x2) * img_width)
                        y2 = int(float(raw_y2) * img_height)
                    else: 
                        x1, y1, x2, y2 = int(float(raw_x1)), int(float(raw_y1)), int(float(raw_x2)), int(float(raw_y2))
                    
                    self.logger.debug(f"Processed AI BBox for action target (x1,y1,x2,y2): ({x1},{y1},{x2},{y2}) from raw: {bbox_data}")

                    abs_x1, abs_y1 = min(x1, x2), min(y1, y2)
                    abs_x2, abs_y2 = max(x1, x2), max(y1, y2)
                    
                    clipped_x1, clipped_y1 = max(0, abs_x1), max(0, abs_y1)
                    clipped_x2, clipped_y2 = min(img_width, abs_x2), min(img_height, abs_y2)
                    
                    if clipped_x1 >= clipped_x2 or clipped_y1 >= clipped_y2:
                        # Retry using actual image dimensions as a fallback if we used window size
                        try:
                            with Image.open(BytesIO(original_screenshot_bytes)) as img_for_retry:
                                img_w_retry, img_h_retry = img_for_retry.size
                            rx1, ry1, rx2, ry2 = x1, y1, x2, y2
                            # Re-clip against image size
                            rx1, ry1 = max(0, min(rx1, img_w_retry)), max(0, min(ry1, img_h_retry))
                            rx2, ry2 = max(0, min(rx2, img_w_retry)), max(0, min(ry2, img_h_retry))
                            if rx1 < rx2 and ry1 < ry2:
                                draw_box_coords = (rx1, ry1, rx2, ry2)
                                filename_suffix = f"_action_{action_type}_target_bbox_{'_'.join(map(str, draw_box_coords))}.png"
                                target_log_info = f"action_{action_type}_target_bbox=({draw_box_coords})_retry_imgdims"
                                self.logger.debug(f"Retrying draw with image dims; coords: {draw_box_coords}")
                                drawn_bytes = utils.draw_rectangle_on_image(original_screenshot_bytes, draw_box_coords)
                                if isinstance(drawn_bytes, bytes):
                                    annotated_bytes_to_save = drawn_bytes
                                else:
                                    self.logger.error("utils.draw_rectangle_on_image failed on retry. Using original.")
                                    filename_suffix = f"_action_{action_type}_target_draw_error.png"
                                    target_log_info += "_draw_error"
                            else:
                                # Final fallback: assume input order was [x,y] instead of [y,x]
                                alt_x1_raw, alt_y1_raw = bbox_data.get("top_left", [0, 0])
                                alt_x2_raw, alt_y2_raw = bbox_data.get("bottom_right", [0, 0])
                                # Interpret directly as pixel coordinates
                                ax1, ay1 = int(float(alt_x1_raw)), int(float(alt_y1_raw))
                                ax2, ay2 = int(float(alt_x2_raw)), int(float(alt_y2_raw))
                                ax1, ay1 = min(ax1, ax2), min(ay1, ay2)
                                ax2, ay2 = max(ax1, ax2), max(ay1, ay2)
                                ax1, ay1 = max(0, min(ax1, img_w_retry)), max(0, min(ay1, img_h_retry))
                                ax2, ay2 = max(0, min(ax2, img_w_retry)), max(0, min(ay2, img_h_retry))
                                if ax1 < ax2 and ay1 < ay2:
                                    draw_box_coords = (ax1, ay1, ax2, ay2)
                                    filename_suffix = f"_action_{action_type}_target_bbox_{'_'.join(map(str, draw_box_coords))}.png"
                                    target_log_info = f"action_{action_type}_target_bbox=({draw_box_coords})_fallback_swapped"
                                    self.logger.debug(f"Fallback swapped x/y draw; coords: {draw_box_coords}")
                                    drawn_bytes = utils.draw_rectangle_on_image(original_screenshot_bytes, draw_box_coords)
                                    if isinstance(drawn_bytes, bytes):
                                        annotated_bytes_to_save = drawn_bytes
                                    else:
                                        self.logger.error("utils.draw_rectangle_on_image failed on swapped fallback. Using original.")
                                        filename_suffix = f"_action_{action_type}_target_draw_error.png"
                                        target_log_info += "_draw_error"
                                else:
                                    self.logger.warning("BBox still invalid after swapped-coords fallback. Will not draw.")
                                    filename_suffix = f"_action_{action_type}_no_target_bbox.png"
                                    target_log_info = f"action_{action_type}_no_target_bbox"
                        except Exception as retry_err:
                            self.logger.debug(f"BBox retry using image dimensions failed: {retry_err}")
                            self.logger.warning(f"Action target BBox is zero-size or invalid. Original: {bbox_data}, Clipped: ({clipped_x1},{clipped_y1},{clipped_x2},{clipped_y2}). Will not draw.")
                            filename_suffix = f"_action_{action_type}_no_target_bbox.png"
                            target_log_info = f"action_{action_type}_no_target_bbox"
                    else:
                        draw_box_coords = (clipped_x1, clipped_y1, clipped_x2, clipped_y2)
                        filename_suffix = f"_action_{action_type}_target_bbox_{'_'.join(map(str, draw_box_coords))}.png"
                        target_log_info = f"action_{action_type}_target_bbox=({draw_box_coords})"
                        
                        self.logger.debug(f"Drawing action target bounding box: {draw_box_coords}")
                        drawn_bytes = utils.draw_rectangle_on_image(original_screenshot_bytes, draw_box_coords)
                        if isinstance(drawn_bytes, bytes):
                            annotated_bytes_to_save = drawn_bytes
                        else:
                            self.logger.error("utils.draw_rectangle_on_image failed to return bytes. Using original for annotated image.")
                            filename_suffix = f"_action_{action_type}_target_draw_error.png"
                            target_log_info += "_draw_error"
            
            except (KeyError, IndexError, TypeError, ValueError) as e_bbox:
                self.logger.error(f"Error processing AI target bounding box data {bbox_data} for action '{action_type}': {e_bbox}. Saving original for annotated image.")
                filename_suffix = f"_action_{action_type}_target_bbox_error.png"
                target_log_info = f"action_{action_type}_target_bbox_error"
            except Exception as e_draw:
                self.logger.error(f"Unexpected error during target annotation drawing for action '{action_type}': {e_draw}", exc_info=True)
                filename_suffix = f"_action_{action_type}_target_draw_unexpected_error.png"
                target_log_info = f"action_{action_type}_target_draw_unexpected_error"
        elif not ai_suggestion: # If ai_suggestion was None to begin with
             filename_suffix = "_no_ai_suggestion.png"
             target_log_info = "no_ai_suggestion"
        else: # ai_suggestion exists, but no bbox_data for target or action type not requiring a drawn box
            self.logger.debug(f"No specific target bounding box to draw for action '{action_type}' or bbox_data missing/invalid. Annotated image will be original.")
            filename_suffix = f"_action_{action_type}_no_specific_target_annotation.png"
            target_log_info = f"action_{action_type}_no_specific_target_annotation"

        annotated_dir = str(self.cfg.ANNOTATED_SCREENSHOTS_DIR)
        os.makedirs(annotated_dir, exist_ok=True)
        
        filename = f"annotated_s{screen_id}_step{step}{filename_suffix}"
        filepath = os.path.join(annotated_dir, filename)

        try:
            with open(filepath, "wb") as f:
                f.write(annotated_bytes_to_save)
            self.logger.info(f"Saved annotated screenshot ({target_log_info}): {filepath}")
            return filepath
        except IOError as io_err:
            self.logger.error(f"Failed to save annotated screenshot to {filepath}: {io_err}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error saving annotated screenshot {filepath}: {e}", exc_info=True)
            return None

    def update_master_annotation_file(self,
                                      original_screenshot_filename: str, 
                                      all_ui_elements_data: List[Dict[str, Any]]):
        if not self.master_annotation_file_path:
            self.logger.error("Master annotation file path is not set. Cannot update.")
            return
            
        if not all_ui_elements_data:
            self.logger.debug(f"No UI elements data provided for {original_screenshot_filename}. Skipping update to master annotation file.")
            return

        master_annotations = {}
        try:
            if os.path.exists(self.master_annotation_file_path):
                with open(self.master_annotation_file_path, 'r', encoding='utf-8') as f:
                    master_annotations = json.load(f)
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding existing master annotation file: {self.master_annotation_file_path}. Will overwrite with new data for this screenshot.", exc_info=True)
            master_annotations = {}
        except Exception as e:
            self.logger.error(f"Error loading master annotation file {self.master_annotation_file_path}: {e}. Proceeding with new/overwritten data.", exc_info=True)
            master_annotations = {}

        master_annotations[os.path.basename(original_screenshot_filename)] = all_ui_elements_data
        
        try:
            # SCREENSHOTS_DIR (raw) existence is checked/created in __init__ or by Config class
            with open(self.master_annotation_file_path, 'w', encoding='utf-8') as f:
                json.dump(master_annotations, f, indent=4, ensure_ascii=False)
            self.logger.info(f"Updated master annotation file with {len(all_ui_elements_data)} elements for {original_screenshot_filename}: {self.master_annotation_file_path}")
        except IOError as e:
            self.logger.error(f"Failed to write master annotation file {self.master_annotation_file_path}: {e}", exc_info=True)
        except Exception as e: # Catch any other unexpected error
            self.logger.error(f"Unexpected error writing master annotation file {self.master_annotation_file_path}: {e}", exc_info=True)
