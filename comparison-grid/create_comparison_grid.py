import os
import re
import math
import logging
from PIL import Image, ImageDraw, ImageFont

# Configure basic logging if not already configured elsewhere
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def try_extract_sort_key(filename):
    """
    Attempts to extract numerical sorting keys (like step, screen ID)
    from filenames for more logical grid ordering.
    Falls back to alphabetical sort if patterns don't match.
    """
    # Try annotated pattern first
    match_ann = re.match(r'.*step_(\d+)_screen_(\d+)\.(png|jpg|jpeg)$', filename, re.IGNORECASE)
    if match_ann:
        try:
            step = int(match_ann.group(1))
            screen = int(match_ann.group(2))
            return (step, screen) # Sort by step, then screen
        except ValueError:
            pass # Fall through if conversion fails

    # Try original screen pattern
    match_orig = re.match(r'screen_(\d+)\.(png|jpg|jpeg)$', filename, re.IGNORECASE)
    if match_orig:
        try:
            screen = int(match_orig.group(1))
            return (0, screen) # Use 0 for step to group originals if mixed, sort by screen
        except ValueError:
            pass # Fall through

    # Fallback to alphabetical sort
    return (float('inf'), filename) # Put non-matching last, sort alphabetically


def create_single_folder_grid(input_dir: str,
                              output_path: str,
                              cols: int = 5,
                              padding: int = 10,
                              bg_color: tuple = (255, 255, 255)) -> bool:
    """
    Creates a grid image from all valid image files within a single directory.

    Args:
        input_dir: Path to the directory containing the image files.
        output_path: Path where the combined grid image will be saved.
        cols: Number of images to display per row in the grid.
        padding: Pixel space between images and around the border.
        bg_color: Background color for the grid canvas (RGB tuple).

    Returns:
        True if the grid image was created successfully, False otherwise.
    """
    logging.info(f"Creating grid for folder: '{input_dir}' -> '{output_path}'")

    if not os.path.isdir(input_dir):
        logging.error(f"Input directory not found: {input_dir}")
        return False

    image_paths = []
    valid_extensions = ('.png', '.jpg', '.jpeg')

    # --- Find all valid image files ---
    logging.debug(f"Scanning directory: {input_dir}")
    for filename in os.listdir(input_dir):
        full_path = os.path.join(input_dir, filename)
        if os.path.isfile(full_path) and filename.lower().endswith(valid_extensions):
            image_paths.append(filename) # Store filename for sorting
            logging.debug(f"Found image file: {filename}")
        else:
            logging.debug(f"Skipping non-image file or directory: {filename}")

    if not image_paths:
        logging.error(f"No valid image files found in directory: {input_dir}")
        return False

    # --- Sort images (attempt numerical sort based on expected patterns) ---
    image_paths.sort(key=try_extract_sort_key)
    logging.info(f"Found {len(image_paths)} images. Will arrange in grid.")
    logging.debug(f"Sorted image order: {image_paths}") # Log the sorted order

    # --- Prepare grid layout ---
    try:
        # Get dimensions from the first image (assume consistency)
        first_image_path = os.path.join(input_dir, image_paths[0])
        with Image.open(first_image_path) as img:
            img_width, img_height = img.size
        if img_width <= 0 or img_height <= 0:
             raise ValueError("First image has invalid dimensions.")

        # Calculate grid dimensions
        num_images = len(image_paths)
        actual_cols = min(cols, num_images) # Don't make more columns than images
        rows = math.ceil(num_images / actual_cols)

        # Calculate total canvas size
        total_width = (img_width * actual_cols) + (padding * (actual_cols + 1))
        total_height = (img_height * rows) + (padding * (rows + 1)) + (rows * padding) # Extra padding for labels

        logging.info(f"Grid layout: {rows} rows x {actual_cols} columns.")
        logging.info(f"Single image size: {img_width}x{img_height}")
        logging.info(f"Total canvas size: {total_width}x{total_height}")

        # Create the blank canvas
        canvas = Image.new('RGB', (total_width, total_height), bg_color)
        draw = ImageDraw.Draw(canvas) # Get draw object for optional labels
        # Attempt to load a font
        label_font = None
        try:
            label_font = ImageFont.truetype("arial.ttf", size=int(padding*0.8))
        except IOError:
             logging.warning("Arial font not found. Labels will not be added.")
             try:
                 label_font = ImageFont.load_default()
             except IOError:
                  logging.error("Default PIL font also not found. Cannot add labels.")

    except Exception as e:
        logging.error(f"Error preparing grid layout or opening first image: {e}", exc_info=True)
        return False

    # --- Paste images onto the canvas ---
    current_image_index = 0
    for r in range(rows):
        for c in range(actual_cols):
            if current_image_index >= num_images:
                break # Stop if we run out of images

            filename = image_paths[current_image_index]
            img_path = os.path.join(input_dir, filename)

            # Calculate top-left corner for this image cell
            paste_x = padding + c * (img_width + padding)
            paste_y = padding + r * (img_height + padding + padding) # Extra padding for labels

            try:
                # Open and paste image
                with Image.open(img_path) as img:
                    # Ensure image is RGB if canvas is RGB
                    if img.mode != 'RGB': img = img.convert('RGB')
                    # Resize if necessary?
                    if img.size != (img_width, img_height):
                        logging.warning(f"Image '{filename}' size {img.size} differs from first image. Resizing.")
                        img = img.resize((img_width, img_height))
                    logging.debug(f"Pasting '{filename}' at ({paste_x}, {paste_y})")
                    canvas.paste(img, (paste_x, paste_y))

                # Add filename label below the image if font is available
                if label_font:
                    label_text = filename
                    label_y = paste_y + img_height + (padding // 4) # Position below image
                    try: # Use text anchor if available
                        text_anchor = "lm" # Left-Middle anchor
                        draw.text((paste_x, label_y), label_text, fill=(0,0,0), font=label_font, anchor=text_anchor)
                    except AttributeError: # Fallback for older Pillow
                        draw.text((paste_x, label_y), label_text, fill=(0,0,0), font=label_font)
                    except Exception as label_err:
                         logging.warning(f"Could not draw label for '{filename}': {label_err}")

            except FileNotFoundError:
                logging.error(f"Image file not found during pasting: {img_path}")
                # Draw placeholder
                placeholder_bounds = (paste_x, paste_y, paste_x + img_width, paste_y + img_height)
                draw.rectangle(placeholder_bounds, outline=(255,0,0), width=2)
                if label_font:
                    draw.text((paste_x + 5, paste_y + 5), "Not Found", fill=(255,0,0), font=label_font)
            except Exception as e:
                logging.error(f"Error processing/pasting image '{filename}': {e}", exc_info=True)
                # Draw placeholder

            current_image_index += 1
        if current_image_index >= num_images:
            break # Exit outer loop too

    # --- Save the final image ---
    try:
        logging.info(f"Saving final grid image to: {output_path}")
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir): # Create output directory if it doesn't exist
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
    # Configure logging for the example execution
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    # === Configuration ===
    # Directory containing the ORIGINAL (non-annotated) screenshots
    original_screenshots_dir = r"C:\Users\amrmo\PycharmProjects\appium-traverser\crawl_screenshots_eu.smartpatient.mytherapy"
    # Output path for the grid of original screenshots
    output_grid_original = r"C:\Users\amrmo\PycharmProjects\appium-traverser\original_screenshots_grid.png"

    # Directory containing the ANNOTATED screenshots
    annotated_screenshots_dir = r"C:\Users\amrmo\PycharmProjects\appium-traverser\annotated_crawl_screenshots_eu.smartpatient.mytherapy"
    # Output path for the grid of annotated screenshots
    output_grid_annotated = r"C:\Users\amrmo\PycharmProjects\appium-traverser\annotated_screenshots_grid.png"

    # Grid appearance settings (can be customized for each grid if needed)
    grid_cols = 5
    grid_padding = 15
    grid_bg_color = (220, 220, 220)
    # === End Configuration ===


    # --- Generate Grid for Original Screenshots ---
    print("-" * 30)
    print(f"Generating grid for ORIGINAL screenshots from: {original_screenshots_dir}")
    success_orig = create_single_folder_grid(
        input_dir=original_screenshots_dir,
        output_path=output_grid_original,
        cols=grid_cols,
        padding=grid_padding,
        bg_color=grid_bg_color
    )
    if success_orig:
        print(f"-> Original screenshots grid created at: {output_grid_original}")
    else:
        print("-> Failed to create original screenshots grid.")
    print("-" * 30)


    # --- Generate Grid for Annotated Screenshots ---
    print(f"Generating grid for ANNOTATED screenshots from: {annotated_screenshots_dir}")
    success_ann = create_single_folder_grid(
        input_dir=annotated_screenshots_dir,
        output_path=output_grid_annotated,
        cols=grid_cols,
        padding=grid_padding,
        bg_color=grid_bg_color
    )
    if success_ann:
        print(f"-> Annotated screenshots grid created at: {output_grid_annotated}")
    else:
        print("-> Failed to create annotated screenshots grid.")
    print("-" * 30)