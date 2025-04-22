import os
import logging
from PIL import Image, ImageDraw, ImageFont

def create_screenshot_grid(input_dir: str,
                         output_path: str,
                         cols: int = 5,
                         padding: int = 20,
                         bg_color: tuple = (255, 255, 255)) -> bool:
    """
    Creates a simple grid image from screenshots in a directory.
    """
    logging.info(f"Creating screenshot grid from: '{input_dir}' -> '{output_path}'")

    if not os.path.isdir(input_dir):
        logging.error(f"Input directory not found: {input_dir}")
        return False

    # Get all image files
    valid_extensions = ('.png', '.jpg', '.jpeg')
    image_files = [f for f in os.listdir(input_dir) 
                  if f.lower().endswith(valid_extensions)]

    if not image_files:
        logging.error(f"No image files found in directory: {input_dir}")
        return False

    # Sort files by name
    image_files.sort()
    logging.info(f"Found {len(image_files)} images to include in the grid.")

    try:
        # Get dimensions from first image
        first_image_path = os.path.join(input_dir, image_files[0])
        with Image.open(first_image_path) as img:
            img_width, img_height = img.size

        # Calculate grid layout
        num_images = len(image_files)
        actual_cols = min(cols, num_images)
        rows = (num_images + actual_cols - 1) // actual_cols

        # Calculate canvas size with space for labels
        label_space_y = padding * 2
        total_width = (img_width * actual_cols) + (padding * (actual_cols + 1))
        total_height = (img_height * rows) + (padding * rows) + (label_space_y * rows) + padding

        # Create canvas
        canvas = Image.new('RGB', (total_width, total_height), bg_color)
        draw = ImageDraw.Draw(canvas)

        # Try to load font
        try:
            label_font = ImageFont.truetype("arial.ttf", size=max(10, int(padding * 0.6)))
        except:
            label_font = ImageFont.load_default()

        # Place images in grid
        for idx, filename in enumerate(image_files):
            if idx >= num_images:
                break

            row = idx // actual_cols
            col = idx % actual_cols

            paste_x = padding + col * (img_width + padding)
            paste_y = padding + row * (img_height + padding + label_space_y)

            try:
                img_path = os.path.join(input_dir, filename)
                with Image.open(img_path) as img:
                    if img.size != (img_width, img_height):
                        img = img.resize((img_width, img_height))
                    canvas.paste(img, (paste_x, paste_y))

                # Add filename label
                label_y = paste_y + img_height + (padding // 2)
                draw.text((paste_x, label_y), filename, fill=(0,0,0), font=label_font)

            except Exception as e:
                logging.error(f"Error processing image '{filename}': {e}")
                # Draw placeholder for failed image
                placeholder_bounds = (paste_x, paste_y, paste_x + img_width, paste_y + img_height)
                draw.rectangle(placeholder_bounds, outline=(255,0,0), width=2)
                draw.text((paste_x + 5, paste_y + 5), "Error", fill=(255,0,0), font=label_font)

        # Save final image
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        canvas.save(output_path)
        logging.info("Grid image saved successfully.")
        return True

    except Exception as e:
        logging.error(f"Error creating grid: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    screenshots_dir = r"c:\Users\amrmo\PycharmProjects\appium-traverser\traverser-ai-api\screenshots\crawl_screenshots_eu.smartpatient.mytherapy"
    output_grid = r"c:\Users\amrmo\PycharmProjects\appium-traverser\comparison-grid\output\screenshots_grid.png"

    success = create_screenshot_grid(
        input_dir=screenshots_dir,
        output_path=output_grid,
        cols=4,
        padding=25,
        bg_color=(230, 230, 230)
    )

    if success:
        print(f"Screenshot grid created at: {output_grid}")
    else:
        print("Failed to create screenshot grid.")