import os
import re
import math
import logging
from typing import Optional, Tuple, Dict , List
from PIL import Image, ImageDraw, ImageFont

# Configure basic logging if not already configured elsewhere
# logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def parse_filename(filename: str) -> Optional[Dict]:
    """
    Parses filename to extract step, screen ID, and optional target bbox coordinates.
    Returns a dictionary with keys 'step', 'screen', 'x1', 'y1', 'x2', 'y2' or None if no match.
    Coordinates will be None if not found in the filename.
    """
    # --- NEW: Pattern for annotated files with BBOX coordinates ---
    # Format: ..._bbox_X1_Y1_X2_Y2.png
    match_bbox_coords = re.match(r'.*step_(\d+)_screen_(\d+)_bbox_(\d+)_(\d+)_(\d+)_(\d+)\.(png|jpg|jpeg)$', filename, re.IGNORECASE)
    if match_bbox_coords:
        try:
            x1 = int(match_bbox_coords.group(3))
            y1 = int(match_bbox_coords.group(4))
            x2 = int(match_bbox_coords.group(5))
            y2 = int(match_bbox_coords.group(6))
            # Basic validation: ensure x1 <= x2 and y1 <= y2
            if x1 > x2: x1, x2 = x2, x1 # Swap if needed
            if y1 > y2: y1, y2 = y2, y1 # Swap if needed
            return {
                'step': int(match_bbox_coords.group(1)),
                'screen': int(match_bbox_coords.group(2)),
                'x1': x1,
                'y1': y1,
                'x2': x2,
                'y2': y2,
                'is_annotated': True
            }
        except (ValueError, IndexError) as e:
             logging.warning(f"Error parsing bbox coords from supposedly annotated file '{filename}': {e}")
             # Fallback to treating it as annotated but without coords
             try:
                return {
                    'step': int(match_bbox_coords.group(1)),
                    'screen': int(match_bbox_coords.group(2)),
                    'x1': None, 'y1': None, 'x2': None, 'y2': None,
                    'is_annotated': True
                }
             except (ValueError, IndexError):
                 logging.warning(f"Error parsing step/screen even after coord error in '{filename}'")
                 return None

    # Pattern for annotated files WITHOUT coordinates (fallback)
    match_ann_no_coords = re.match(r'.*step_(\d+)_screen_(\d+)\.(png|jpg|jpeg)$', filename, re.IGNORECASE)
    if match_ann_no_coords:
         try:
            return {
                'step': int(match_ann_no_coords.group(1)),
                'screen': int(match_ann_no_coords.group(2)),
                'x1': None, 'y1': None, 'x2': None, 'y2': None, # Explicitly None
                'is_annotated': True
            }
         except (ValueError, IndexError):
              logging.warning(f"Error parsing step/screen from annotated file: {filename}")
              return None

    # Pattern for original files
    match_orig = re.match(r'screen_(\d+)\.(png|jpg|jpeg)$', filename, re.IGNORECASE)
    if match_orig:
        try:
            return {
                'step': 0,
                'screen': int(match_orig.group(1)),
                'x1': None, 'y1': None, 'x2': None, 'y2': None, # Explicitly None
                'is_annotated': False
            }
        except (ValueError, IndexError):
             logging.warning(f"Error parsing screen from original file: {filename}")
             return None

    logging.debug(f"Filename did not match known patterns: {filename}")
    return None

# get_sort_key remains the same
def get_sort_key(parsed_data: Optional[Dict], filename: str) -> Tuple:
    """Generates a sort key from parsed filename data."""
    if parsed_data:
        return (parsed_data.get('step', float('inf')),
                parsed_data.get('screen', float('inf')),
                filename)
    else:
        return (float('inf'), float('inf'), filename)
def get_sort_key(parsed_data: Optional[Dict], filename: str) -> Tuple:
    """Generates a sort key from parsed filename data."""
    if parsed_data:
        return (parsed_data.get('step', float('inf')),
                parsed_data.get('screen', float('inf')),
                filename)
    else:
        return (float('inf'), float('inf'), filename)


def create_single_folder_grid(input_dir: str,
                              output_path: str,
                              draw_annotations: bool = False,
                              cols: int = 5,
                              padding: int = 20,
                              bg_color: tuple = (255, 255, 255),
                              axis_interval: int = 100) -> bool:
    """
    Creates a grid image from images in a directory.
    If draw_annotations is True, attempts to parse bbox coordinates from filenames
    (format ..._bbox_X1_Y1_X2_Y2.png) and draws the bbox and a center point.

    Args:
        input_dir: Path to the directory containing the image files.
        output_path: Path where the combined grid image will be saved.
        draw_annotations: If True, draw bbox and center point based on filename coords.
        cols: Number of images per row.
        padding: Pixel space between images and border.
        bg_color: Background color (RGB tuple).
        axis_interval: Pixel interval for drawing axis ticks (currently unused, kept for potential future).

    Returns:
        True if successful, False otherwise.
    """
    grid_type = "ANNOTATED" if draw_annotations else "ORIGINAL"
    logging.info(f"Creating {grid_type} grid for folder: '{input_dir}' -> '{output_path}'")

    # ... (rest of the initial setup: directory check, file scanning, sorting is the same) ...
    if not os.path.isdir(input_dir):
        logging.error(f"Input directory not found: {input_dir}")
        return False

    parsed_files: List[Dict] = [] # Type hint
    valid_extensions = ('.png', '.jpg', '.jpeg')

    logging.debug(f"Scanning directory: {input_dir}")
    for filename in os.listdir(input_dir):
        full_path = os.path.join(input_dir, filename)
        if os.path.isfile(full_path) and filename.lower().endswith(valid_extensions):
            parsed_data = parse_filename(filename)
            # Only include if parsing was successful OR if annotations aren't required
            # Also, if drawing annotations, only include files marked as annotated
            if parsed_data:
                 if draw_annotations and not parsed_data['is_annotated']:
                     logging.debug(f"Skipping non-annotated file '{filename}' for annotated grid.")
                     continue # Skip original files if building annotated grid
                 # Keep annotated files (with or without coords) and original files (if not drawing annotations)
                 parsed_files.append({'filename': filename, 'data': parsed_data})
                 logging.debug(f"Found image file: {filename}, Parsed: True, Data: {parsed_data}")
            else:
                 logging.debug(f"Skipping file '{filename}' due to parsing failure.")
        else:
            logging.debug(f"Skipping non-image file or directory: {filename}")

    if not parsed_files:
        logging.error(f"No valid/matching image files found in directory: {input_dir} for {grid_type} grid.")
        return False

    parsed_files.sort(key=lambda item: get_sort_key(item['data'], item['filename']))
    logging.info(f"Found {len(parsed_files)} images to include in the grid.")

    # --- Prepare grid layout (same as before) ---
    try:
        first_image_path = os.path.join(input_dir, parsed_files[0]['filename'])
        with Image.open(first_image_path) as img:
            img_width, img_height = img.size
        if img_width <= 0 or img_height <= 0: raise ValueError("First image has invalid dimensions.")

        num_images = len(parsed_files)
        actual_cols = min(cols, num_images)
        rows = math.ceil(num_images / actual_cols)

        label_space_y = padding * 2.5
        total_width = int((img_width * actual_cols) + (padding * (actual_cols + 1)))
        total_height = int((img_height * rows) + (padding * rows) + (label_space_y * rows) + padding)

        logging.info(f"Grid layout: {rows} rows x {actual_cols} columns.")
        logging.info(f"Single image size: {img_width}x{img_height}")
        logging.info(f"Total canvas size: {total_width}x{total_height}")

        canvas = Image.new('RGB', (total_width, total_height), bg_color)
        draw = ImageDraw.Draw(canvas)

        # Font loading (same as before)
        label_font = None
        coord_text_font = None
        # axis_value_font = None # Kept if needed later
        font_size_label = max(10, int(padding * 0.6))
        font_size_coord_text = max(12, int(padding * 0.75))
        # font_size_axis_value = max(8, int(padding * 0.5))
        try:
            label_font = ImageFont.truetype("arial.ttf", size=font_size_label)
            coord_text_font = ImageFont.truetype("arial.ttf", size=font_size_coord_text)
            # axis_value_font = ImageFont.truetype("arial.ttf", size=font_size_axis_value)
            logging.debug(f"Loaded Arial fonts. Label:{font_size_label}, Coord:{font_size_coord_text}")
        except IOError:
             logging.warning("Arial font not found. Trying default font.")
             try:
                 label_font = ImageFont.load_default()
                 coord_text_font = ImageFont.load_default()
                 # axis_value_font = ImageFont.load_default()
                 logging.debug("Using default PIL font for all text.")
             except IOError:
                  logging.error("Default PIL font also not found. Text cannot be added.")
                  # Fonts remain None

    except Exception as e:
        logging.error(f"Error preparing grid layout or opening first image: {e}", exc_info=True)
        return False

    # --- Constants for drawing annotations ---
    point_color = (255, 0, 0, 200) # Red for center point
    point_radius = max(6, padding // 4)
    coord_text_color = (180, 0, 0) # Dark red for coords text
    coord_text_offset_x = point_radius + 5
    coord_text_offset_y = -(point_radius + 5) # Place text slightly above the dot
    bbox_color = (0, 0, 200, 180) # Blue for bbox outline
    bbox_width = 3  # Width of bounding box line

    # --- Paste images onto the canvas ---
    current_image_index = 0
    for r in range(rows):
        for c in range(actual_cols):
            if current_image_index >= num_images: break

            item = parsed_files[current_image_index]
            filename = item['filename']
            parsed_data = item['data']
            img_path = os.path.join(input_dir, filename)

            paste_x = int(padding + c * (img_width + padding))
            paste_y = int(padding + r * (img_height + padding + label_space_y))

            try:
                with Image.open(img_path) as img_orig:
                    img = img_orig.convert('RGB')
                    if img.size != (img_width, img_height):
                        logging.warning(f"Image '{filename}' size {img.size} differs. Resizing to {img_width}x{img_height}.")
                        img = img.resize((img_width, img_height))

                    logging.debug(f"Pasting '{filename}' at ({paste_x}, {paste_y})")
                    canvas.paste(img, (paste_x, paste_y))

                    # --- Draw Annotations (using BBOX data) ---
                    # Check if we should draw AND if bbox coords are available
                    if (draw_annotations and parsed_data and
                        parsed_data.get('x1') is not None and parsed_data.get('y1') is not None and
                        parsed_data.get('x2') is not None and parsed_data.get('y2') is not None):

                        x1, y1, x2, y2 = parsed_data['x1'], parsed_data['y1'], parsed_data['x2'], parsed_data['y2']

                        # Validate coords are within image bounds
                        if (0 <= x1 < img_width and 0 <= y1 < img_height and
                            0 < x2 <= img_width and 0 < y2 <= img_height and
                            x1 < x2 and y1 < y2): # Added strict inequality for valid box

                            # 1. Calculate Bbox Center (relative to image)
                            center_x = (x1 + x2) / 2
                            center_y = (y1 + y2) / 2
                            center_x_int = int(center_x)
                            center_y_int = int(center_y)

                            # 2. Calculate Absolute coordinates on Canvas
                            bbox_abs_x1 = paste_x + x1
                            bbox_abs_y1 = paste_y + y1
                            bbox_abs_x2 = paste_x + x2
                            bbox_abs_y2 = paste_y + y2
                            center_abs_x = paste_x + center_x_int
                            center_abs_y = paste_y + center_y_int

                            # 3. Draw the Bounding Box
                            draw.rectangle(
                                [bbox_abs_x1, bbox_abs_y1, bbox_abs_x2, bbox_abs_y2],
                                outline=bbox_color,
                                width=bbox_width
                            )

                            # 4. Draw the Center Point (Red Dot)
                            draw.ellipse(
                                [ (center_abs_x - point_radius, center_abs_y - point_radius),
                                  (center_abs_x + point_radius, center_abs_y + point_radius) ],
                                fill=point_color, outline=point_color # Use same color for fill and outline
                            )

                            # 5. Draw Coordinate Text (Center Point)
                            if coord_text_font:
                                # Display center coordinates
                                coord_text = f"({center_x_int},{center_y_int})"
                                # Calculate text position relative to center dot
                                text_pos_x = center_abs_x + coord_text_offset_x
                                text_pos_y = center_abs_y + coord_text_offset_y

                                # Basic boundary check for text position within the pasted image area
                                text_w, text_h = coord_text_font.getsize(coord_text) if hasattr(coord_text_font, 'getsize') else (50, 15) # Estimate size if needed
                                text_pos_x = max(paste_x, min(text_pos_x, paste_x + img_width - text_w - 5)) # Keep within right bound
                                text_pos_y = max(paste_y, min(text_pos_y, paste_y + img_height - 5)) # Keep within bottom bound (adjusted offset places it above anyway)
                                text_pos_y = max(paste_y + 5, text_pos_y) # Keep within top bound

                                try:
                                     draw.text((text_pos_x, text_pos_y), coord_text, fill=coord_text_color, font=coord_text_font)
                                except Exception as coord_draw_err:
                                     logging.warning(f"Could not draw coord text for {filename}: {coord_draw_err}")
                        else:
                             logging.warning(f"Bbox coords ({x1},{y1},{x2},{y2}) for '{filename}' invalid or out of bounds ({img_width}x{img_height}). Skipping drawing.")
                    elif draw_annotations and parsed_data and parsed_data.get('x1') is None:
                        # Handle case where file is annotated but has no coords in filename
                        logging.debug(f"Annotated file '{filename}' has no bbox coordinates. Skipping drawing.")


                # Add filename label below the image (same as before)
                if label_font:
                    label_text = filename
                    label_y_pos = paste_y + img_height + (padding // 2)
                    try:
                        text_anchor = "lm"
                        draw.text((paste_x, label_y_pos), label_text, fill=(0,0,0), font=label_font, anchor=text_anchor)
                    except AttributeError:
                        draw.text((paste_x, label_y_pos), label_text, fill=(0,0,0), font=label_font)
                    except Exception as label_err:
                         logging.warning(f"Could not draw label for '{filename}': {label_err}")

            except FileNotFoundError:
                logging.error(f"Image file not found during pasting: {img_path}")
                placeholder_bounds = (paste_x, paste_y, paste_x + img_width, paste_y + img_height)
                draw.rectangle(placeholder_bounds, outline=(255,0,0), width=2)
                if label_font: draw.text((paste_x + 5, paste_y + 5), "Not Found", fill=(255,0,0), font=label_font)
            except Exception as e:
                logging.error(f"Error processing/pasting image '{filename}': {e}", exc_info=True)

            current_image_index += 1
        if current_image_index >= num_images: break

    # --- Save the final image (same as before) ---
    try:
        logging.info(f"Saving final grid image to: {output_path}")
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logging.info(f"Created output directory: {output_dir}")
        canvas.save(output_path)
        logging.info("Grid image saved successfully.")
        return True
    except Exception as e:
        logging.error(f"Failed to save the final grid image: {e}", exc_info=True)
        return False



# --- Example Usage ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    # === Configuration ===
    original_screenshots_dir = r"c:\Users\amrmo\PycharmProjects\appium-traverser\traverser-ai-api\screenshots\crawl_screenshots_eu.smartpatient.mytherapy"
    output_grid_original = r"c:\Users\amrmo\PycharmProjects\appium-traverser\comparison-grid\output\original_screenshots_grid.png"
    annotated_screenshots_dir = r"c:\Users\amrmo\PycharmProjects\appium-traverser\traverser-ai-api\screenshots\annotated_crawl_screenshots_eu.smartpatient.mytherapy"
    output_grid_annotated = r"c:\Users\amrmo\PycharmProjects\appium-traverser\comparison-grid\output\annotated_screenshots_grid_with_coords_axes.png" # Changed output name

    grid_cols = 4 # Reduced columns slightly to make space for annotations
    grid_padding = 25 # Increased padding significantly
    grid_bg_color = (230, 230, 230)
    axis_tick_interval = 200 # Draw axis values every 200 pixels
    # === End Configuration ===

    print("-" * 30)
    print(f"Generating grid for ORIGINAL screenshots from: {original_screenshots_dir}")
    success_orig = create_single_folder_grid(
        input_dir=original_screenshots_dir, output_path=output_grid_original,
        draw_annotations=False, cols=grid_cols, padding=grid_padding, bg_color=grid_bg_color
    )
    if success_orig: print(f"-> Original screenshots grid created at: {output_grid_original}")
    else: print("-> Failed to create original screenshots grid.")
    print("-" * 30)

    print(f"Generating grid for ANNOTATED screenshots from: {annotated_screenshots_dir}")
    success_ann = create_single_folder_grid(
        input_dir=annotated_screenshots_dir, output_path=output_grid_annotated,
        draw_annotations=True, cols=grid_cols, padding=grid_padding, bg_color=grid_bg_color,
        axis_interval=axis_tick_interval # Pass the interval
    )
    if success_ann: print(f"-> Annotated screenshots grid created at: {output_grid_annotated}")
    else: print("-> Failed to create annotated screenshots grid.")
    print("-" * 30)