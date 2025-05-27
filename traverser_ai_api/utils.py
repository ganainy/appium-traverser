import hashlib
from typing import Tuple, Optional, Any, cast

import imagehash
from PIL import Image
import io
import logging
from PIL import Image, ImageDraw
from lxml import etree 
import re

# --- Constants for XML Simplification ---

# Attributes considered essential for identification or interaction state
# We keep 'class' as it helps identify the type of widget (Button, EditText, etc.)
KEEP_ATTRS = {
    'class', 'resource-id', 'text', 'content-desc', 'hint', # Identification
    'clickable', 'focusable', 'enabled', 'checkable', 'checked', # Interaction state
    'selected', 'editable', 'long-clickable', 'password', # Other important states
    'bounds'  #BOUNDING BOX ATTRIBUTE
}

# Boolean attributes where we only care if they are "true"
# We can remove them if they are "false" to save space
BOOLEAN_ATTRS_TRUE_ONLY = {
    'clickable', 'focusable', 'enabled', 'checkable', # Keep 'checked' always
    'selected', 'editable', 'long-clickable', 'password'
}

# --- Loop Detection ---
LOOP_DETECTION_VISIT_THRESHOLD = 1 #  Max visits before AI is told to prioritize breaking loops.


def calculate_xml_hash(xml_string: str) -> str:
    """Calculates SHA256 hash of the XML string."""
    if not xml_string:
        return "no_xml"
    return hashlib.sha256(xml_string.encode('utf-8')).hexdigest()

def calculate_visual_hash(screenshot_bytes: bytes) -> str:
    """Calculates perceptual hash (pHash) of the screenshot."""
    if not screenshot_bytes:
        return "no_image"
    try:
        img = Image.open(io.BytesIO(screenshot_bytes))
        # Use average hash (aHash) or perceptual hash (pHash)
        # pHash is generally better for similarity
        # dHash (difference hash) is also an option
        v_hash = str(imagehash.phash(img))
        return v_hash
    except Exception as e:
        logging.error(f"Error calculating visual hash: {e}")
        return "hash_error"

def visual_hash_distance(hash1: str, hash2: str) -> int:
    """Calculates the Hamming distance between two visual hashes."""
    if hash1 == hash2:
        return 0
    if "no_image" in [hash1, hash2] or "hash_error" in [hash1, hash2]:
        return 1000 # Indicate invalid comparison

    try:
        # Imagehash library allows comparing hash objects directly,
        # need to convert hex strings back if stored
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2 # Hamming distance
    except Exception as e:
        logging.error(f"Error calculating hash distance between {hash1} and {hash2}: {e}")
        return 1000 # Indicate invalid comparison

def simplify_xml_for_ai(xml_string: str, max_len: int) -> str:
    """
    Simplifies XML by removing non-essential attributes and potentially empty nodes,
    aiming to stay under max_len without arbitrary truncation.

    Args:
        xml_string: The raw XML string from Appium.
        max_len: The target maximum length for the simplified XML.

    Returns:
        A simplified XML string, hopefully under max_len. If processing fails
        or it's still too long after simplification, it might perform
        a final smart truncation.
    """
    if not xml_string:
        return ""

    logging.info(f"Original XML length: {len(xml_string)}")

    try:
        # Parse the XML string. Requires bytes. Handle potential encoding issues.
        parser = etree.XMLParser(recover=True, remove_blank_text=True) # recover helps with slightly malformed XML
        root = etree.fromstring(xml_string.encode('utf-8'), parser=parser)
        if root is None: # Parsing failed completely despite recovery
            raise ValueError("Failed to parse XML root.")

        elements_processed = 0
        # Iterate through all elements in the tree
        for element in root.iter('*'): # '*' iterates over all tags
            elements_processed += 1
            current_attrs = list(element.attrib.keys()) # Get keys before modifying

            for attr_name in current_attrs:
                # 1. Remove attributes not in our essential list
                if attr_name not in KEEP_ATTRS:
                    del element.attrib[attr_name]
                    continue # Go to next attribute

                # 2. Remove boolean attributes that are "false" (unless always kept like 'checked')
                if attr_name in BOOLEAN_ATTRS_TRUE_ONLY:
                    attr_value = element.attrib[attr_name]
                    if isinstance(attr_value, str) and attr_value.lower() == 'false':
                        del element.attrib[attr_name]
                        continue

                # 3. Optional: Shorten potentially long 'resource-id' (keep only last part)
                # if attr_name == 'resource-id':
                #     parts = element.attrib[attr_name].split('/')
                #     if len(parts) > 1:
                #         element.attrib[attr_name] = parts[-1]

            # 4. Optional: Remove elements that become completely empty *after* attribute pruning
            # (Be careful with this - might remove structure. Let's skip for now unless necessary)
            # if not element.attrib and not element.text and not len(element):
            #    parent = element.getparent()
            #    if parent is not None:
            #        parent.remove(element)

        # Convert the modified tree back to a string, with minimal parameters for type checking
        xml_bytes = etree.tostring(root)  
        simplified_xml = xml_bytes.decode('utf-8')

        # Final Check: If still too long, perform a slightly smarter truncation
        if len(simplified_xml) > max_len:
            logging.warning(f"Simplified XML still exceeds max_len ({len(simplified_xml)} > {max_len}). Performing final smart truncation.")
            # Try to truncate at the end of the last complete tag
            trunc_point = simplified_xml.rfind('</', 0, max_len)
            if trunc_point != -1:
                # Find the closing '>' for that tag
                end_tag_point = simplified_xml.find('>', trunc_point, max_len + 20) # Search a bit beyond max_len
                if end_tag_point != -1:
                    simplified_xml = simplified_xml[:end_tag_point+1] + "\n... (truncated)"
                else: # Couldn't find closing '>', just truncate hard
                    simplified_xml = simplified_xml[:max_len] + "... (truncated)"
            else: # No closing tag found before max_len, hard truncate
                simplified_xml = simplified_xml[:max_len] + "... (truncated)"

        # Optional: Final regex cleanup for extra whitespace if needed
        simplified_xml = re.sub(r'>\s+<', '><', simplified_xml)
        simplified_xml = simplified_xml.strip()

        logging.info(f"Simplified XML length: {len(simplified_xml)}")


        return simplified_xml

    except (etree.XMLSyntaxError, ValueError, TypeError) as e:
        logging.error(f"Failed to parse or simplify XML: {e}. Falling back to basic truncation.")
        # Fallback to original basic truncation if parsing/simplification fails
        if len(xml_string) > max_len:
            return xml_string[:max_len] + "\n... (fallback truncation)"
        return xml_string
    except Exception as e:
        logging.error(f"Unexpected error during XML simplification: {e}. Falling back to basic truncation.", exc_info=True)
        if len(xml_string) > max_len:
            return xml_string[:max_len] + "\n... (fallback truncation)"
        return xml_string

def draw_indicator_on_image(image_bytes: bytes, coordinates: Tuple[int, int], color="red", radius=15) -> Optional[bytes]:
    """Draws a circle indicator at the given coordinates on an image."""
    if not image_bytes or not coordinates:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB") # Ensure RGB for color drawing
        draw = ImageDraw.Draw(img)

        # Calculate bounding box for the circle
        x, y = coordinates
        left_up_point = (x - radius, y - radius)
        right_down_point = (x + radius, y + radius)

        # Draw a filled red circle
        draw.ellipse([left_up_point, right_down_point], fill=color, outline=color)

        # Save the modified image back to bytes
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="PNG")
        return output_buffer.getvalue()

    except Exception as e:
        logging.error(f"Error drawing indicator at {coordinates}: {e}")
        return None # Return None if drawing fails

def generate_action_description(action_type: str, target_obj: Optional[Any], input_text: Optional[str], ai_target_identifier: Optional[str]) -> str:

    """Generates a human-readable description of an action."""
    description = f"{action_type.upper()}"

    if ai_target_identifier:
        description += f" on '{ai_target_identifier}'"
    elif isinstance(target_obj, str): # e.g., for scroll direction
        description += f" {target_obj}"
    # Add more specific details if target_obj is a WebElement, but be careful with stale elements
    # For now, ai_target_identifier is preferred for UI display if available.

    if input_text:
        description += f" with text '{input_text}'"
    
    return description

def draw_rectangle_on_image(
    image_bytes: bytes,
    box_coords: Tuple[int, int, int, int],  # (x1, y1, x2, y2)
    primary_color: str = "red",            # The main color of the line
    border_color: str = "black",           # Contrasting border color
    line_thickness: int = 1,               # Thickness of the primary_color line
    border_size: int = 1                   # Thickness of the border_color on each side of the primary line
) -> Optional[bytes]:
    """
    Draws a rectangle (bounding box) with a contrasting border on an image
    for better visibility.

    Args:
        image_bytes: The raw bytes of the image.
        box_coords: A tuple (x1, y1, x2, y2) representing the top-left
                    and bottom-right coordinates of the rectangle.
        primary_color: The main color for the rectangle's center line.
        border_color: The color for the border around the primary line.
        line_thickness: The thickness of the primary color line.
        border_size: The thickness of the border on each side of the primary line.
                    The total visual thickness of the border color part will be
                     line_thickness + 2 * border_size.

    Returns:
        Bytes of the annotated image, or None if an error occurs.
    """
    if not image_bytes or not box_coords:
        logging.warning("draw_rectangle_on_image: Missing image_bytes or box_coords.")
        return None
    if line_thickness <= 0:
        logging.warning("draw_rectangle_on_image: line_thickness must be positive.")
        return image_bytes # Or None if error
    if border_size < 0: # border_size can be 0 for no border
        logging.warning("draw_rectangle_on_image: border_size cannot be negative.")
        return image_bytes # Or None

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")  # Ensure RGB for color drawing
        draw = ImageDraw.Draw(img)

        x1, y1, x2, y2 = box_coords

        # Basic validation (already done more thoroughly in ScreenshotAnnotator before calling)
        if not (0 <= x1 < img.width and 0 <= y1 < img.height and \
                x1 < x2 <= img.width and y1 < y2 <= img.height):
            logging.warning(
                f"draw_rectangle_on_image: Invalid or out-of-bounds box_coords ({x1},{y1},{x2},{y2}) "
                f"for image size ({img.width}x{img.height}). Skipping drawing."
            )
            return image_bytes # Return original image if coords are bad

        # Calculate the total width for the border rectangle
        # This is the width of the line drawn by PIL, centered on the coordinates.
        border_rect_line_width = line_thickness + (2 * border_size)

        if border_size > 0 and border_rect_line_width > 0:
            # Draw the thicker border rectangle first
            draw.rectangle([x1, y1, x2, y2], outline=border_color, width=border_rect_line_width)
        
        # Draw the thinner primary color rectangle on top
        # If border_size is 0, border_rect_line_width will equal line_thickness,
        # so the first draw (if border_size > 0 was false) would be skipped,
        # and this one will draw the primary line with its specified thickness.
        # If border_size > 0, this will draw the primary line centered within the border.
        if line_thickness > 0 : # Ensure we draw something if border_size was 0
            draw.rectangle([x1, y1, x2, y2], outline=primary_color, width=line_thickness)


        output_buffer = io.BytesIO()
        img.save(output_buffer, format="PNG")
        return output_buffer.getvalue()

    except Exception as e:
        logging.error(f"Error in draw_rectangle_on_image with box {box_coords}: {e}", exc_info=True)
        return None