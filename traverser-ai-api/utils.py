import hashlib
from typing import Tuple, Optional

import imagehash
from PIL import Image
import io
import logging
from PIL import Image, ImageDraw

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
    """ Simplifies XML, potentially removing less relevant nodes or attributes,
        and truncates it for the AI prompt."""
    if not xml_string:
        return ""

    # Basic truncation for now. More sophisticated simplification could involve
    # removing layout nodes without interactive children, removing style attributes, etc.
    # Using lxml for structured simplification would be more robust.
    if len(xml_string) > max_len:
        return xml_string[:max_len] + "\n... (truncated)"
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