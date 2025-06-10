#!/usr/bin/env python3
import logging
import time
import sys
import os
import io
import json
from config import Config
import shutil
from typing import Tuple, Optional, Any, cast, List, Dict, Set

import hashlib
import imagehash
from PIL import Image, ImageDraw
from lxml import etree
import re

# --- Global Script Start Time (for ElapsedTimeFormatter) ---
SCRIPT_START_TIME = time.time()

# --- Custom Log Formatter and Handler Manager (Moved from main.py) ---
class ElapsedTimeFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        elapsed_seconds = record.created - SCRIPT_START_TIME
        h = int(elapsed_seconds // 3600)
        m = int((elapsed_seconds % 3600) // 60)
        s = int(elapsed_seconds % 60)
        ms = int((elapsed_seconds - (h * 3600 + m * 60 + s)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

class LoggerManager:
    def __init__(self):
        self.handlers: List[logging.Handler] = []
        self.stdout_wrapper: Optional[io.TextIOWrapper] = None

    def setup_logging(self, log_level_str: str, log_file: Optional[str] = None) -> logging.Logger:
        numeric_level = getattr(logging, log_level_str.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level string: {log_level_str}")

        logger = logging.getLogger()
        logger.setLevel(numeric_level)

        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            if isinstance(handler, logging.FileHandler):
                try:
                    handler.close()
                except Exception:
                    pass
        self.handlers.clear()

        log_formatter = ElapsedTimeFormatter(
            "[%(levelname)s] (%(asctime)s) %(filename)s:%(lineno)d - %(message)s"
        )

        try:
            if not self.stdout_wrapper:
                self.stdout_wrapper = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            console_handler = logging.StreamHandler(self.stdout_wrapper)
        except Exception:
            console_handler = logging.StreamHandler(sys.stdout)

        console_handler.setFormatter(log_formatter)
        logger.addHandler(console_handler)
        self.handlers.append(console_handler)

        if log_file:
            try:
                log_file_dir = os.path.dirname(os.path.abspath(log_file))
                if log_file_dir:
                    os.makedirs(log_file_dir, exist_ok=True)

                file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
                file_handler.setFormatter(log_formatter)
                logger.addHandler(file_handler)
                self.handlers.append(file_handler)
            except Exception as e:
                print(f"Error setting up file logger for {log_file}: {e}", file=sys.stderr)

        if numeric_level > logging.DEBUG:
            for lib_name in ["appium.webdriver.webdriver", "urllib3.connectionpool", "selenium.webdriver.remote.remote_connection"]:
                logging.getLogger(lib_name).setLevel(logging.WARNING)

        return logger

# --- Constants for XML Simplification ---
KEEP_ATTRS = {
    'class', 'resource-id', 'text', 'content-desc', 'hint',
    'clickable', 'focusable', 'enabled', 'checkable', 'checked',
    'selected', 'editable', 'long-clickable', 'password',
    'bounds'
}
BOOLEAN_ATTRS_TRUE_ONLY = {
    'clickable', 'focusable', 'enabled', 'checkable',
    'selected', 'editable', 'long-clickable', 'password'
}

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
        return 1000

    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except Exception as e:
        logging.error(f"Error calculating hash distance between {hash1} and {hash2}: {e}")
        return 1000

def simplify_xml_for_ai(xml_string: str, max_len: int) -> str:
    """
    Simplifies XML by removing non-essential attributes and potentially empty nodes,
    aiming to stay under max_len without arbitrary truncation.
    """
    if not xml_string:
        return ""

    original_len = len(xml_string)
    if original_len > 200:
        logging.debug(f"Original XML length: {original_len}")

    try:
        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        root = etree.fromstring(xml_string.encode('utf-8'), parser=parser)
        if root is None:
            raise ValueError("Failed to parse XML root.")

        for element in root.iter('*'):
            current_attrs = list(element.attrib.keys())
            for attr_name in current_attrs:
                if attr_name not in KEEP_ATTRS:
                    del element.attrib[attr_name]
                    continue
                if attr_name in BOOLEAN_ATTRS_TRUE_ONLY:
                    attr_value = element.attrib[attr_name]
                    if isinstance(attr_value, str) and attr_value.lower() == 'false':
                        del element.attrib[attr_name]
                        continue

        xml_bytes = etree.tostring(root)
        simplified_xml = xml_bytes.decode('utf-8')

        if len(simplified_xml) > max_len:
            logging.warning(f"Simplified XML still exceeds max_len ({len(simplified_xml)} > {max_len}). Performing final smart truncation.")
            trunc_point = simplified_xml.rfind('</', 0, max_len)
            if trunc_point != -1:
                end_tag_point = simplified_xml.find('>', trunc_point, max_len + 30)
                if end_tag_point != -1:
                    simplified_xml = simplified_xml[:end_tag_point+1] + "\n... (truncated)"
                else:
                    simplified_xml = simplified_xml[:max_len] + "... (truncated)"
            else:
                simplified_xml = simplified_xml[:max_len] + "... (truncated)"

        simplified_xml = re.sub(r'>\s+<', '><', simplified_xml).strip()

        final_len = len(simplified_xml)
        if original_len > 200:
            logging.debug(f"Simplified XML length: {final_len} (from {original_len})")
        return simplified_xml

    except (etree.XMLSyntaxError, ValueError, TypeError) as e:
        logging.error(f"Failed to parse or simplify XML: {e}. Falling back to basic truncation.")
        return xml_string[:max_len] + "\n... (fallback truncation)" if len(xml_string) > max_len else xml_string
    except Exception as e:
        logging.error(f"Unexpected error during XML simplification: {e}. Falling back.", exc_info=True)
        return xml_string[:max_len] + "\n... (fallback truncation)" if len(xml_string) > max_len else xml_string

def filter_xml_by_allowed_packages(xml_string: str, target_package: str, allowed_packages: List[str]) -> str:
    """
    Filters an XML string, removing elements not belonging to the target or allowed packages.
    System UI packages (e.g., 'com.android.systemui') are implicitly allowed to keep essential navigation.
    """
    if not xml_string:
        return ""
    try:
        parser = etree.XMLParser(recover=True, remove_blank_text=True)
        root = etree.fromstring(xml_string.encode('utf-8'), parser=parser)
        if root is None:
            raise ValueError("Failed to parse XML root.")

        allowed_set: Set[str] = set(allowed_packages)
        allowed_set.add(target_package)
        allowed_set.add('com.android.systemui')

        # Using a list comprehension with a recursive check is cleaner
        # The parent map is needed to remove elements from their parent
        parent_map = {c: p for p in root.iter() for c in p}
        nodes_to_remove = []
        for elem in root.iter('*'):
            pkg = elem.get('package')
            if pkg and pkg not in allowed_set:
                nodes_to_remove.append(elem)

        for elem in nodes_to_remove:
            parent = parent_map.get(elem)
            if parent is not None:
                logging.debug(f"Filtering out XML element with package: '{elem.get('package')}'")
                parent.remove(elem)

        xml_bytes = etree.tostring(root)
        return xml_bytes.decode('utf-8')

    except (etree.XMLSyntaxError, ValueError, TypeError) as e:
        logging.error(f"XML ParseError during package filtering: {e}. Returning original XML.")
        return xml_string
    except Exception as e:
        logging.error(f"Unexpected error during XML filtering: {e}", exc_info=True)
        return xml_string


def draw_indicator_on_image(image_bytes: bytes, coordinates: Tuple[int, int], color="red", radius=15) -> Optional[bytes]:
    """Draws a circle indicator at the given coordinates on an image."""
    if not image_bytes or not coordinates:
        return None
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)
        x, y = coordinates
        left_up_point = (x - radius, y - radius)
        right_down_point = (x + radius, y + radius)
        draw.ellipse([left_up_point, right_down_point], fill=color, outline=color)
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="PNG")
        return output_buffer.getvalue()
    except Exception as e:
        logging.error(f"Error drawing indicator at {coordinates}: {e}")
        return None

def generate_action_description(action_type: str, target_obj: Optional[Any], input_text: Optional[str], ai_target_identifier: Optional[str]) -> str:
    """Generates a human-readable description of an action."""
    description = f"{action_type.upper()}"
    if ai_target_identifier:
        description += f" on '{ai_target_identifier}'"
    elif isinstance(target_obj, str):
        description += f" {target_obj}"
    if input_text:
        description += f" with text '{input_text}'"
    return description

def draw_rectangle_on_image(
    image_bytes: bytes,
    box_coords: Tuple[int, int, int, int],
    primary_color: str = "red",
    border_color: str = "black",
    line_thickness: int = 1,
    border_size: int = 1
) -> Optional[bytes]:
    """Draws a rectangle (bounding box) with a contrasting border on an image."""
    if not image_bytes or not box_coords:
        logging.warning("draw_rectangle_on_image: Missing image_bytes or box_coords.")
        return None
    if line_thickness <= 0:
        logging.warning("draw_rectangle_on_image: line_thickness must be positive.")
        return image_bytes
    if border_size < 0:
        logging.warning("draw_rectangle_on_image: border_size cannot be negative.")
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)
        x1, y1, x2, y2 = box_coords

        if not (0 <= x1 < img.width and 0 <= y1 < img.height and \
                x1 < x2 <= img.width and y1 < y2 <= img.height):
            logging.warning(
                f"draw_rectangle_on_image: Invalid or out-of-bounds box_coords ({x1},{y1},{x2},{y2}) "
                f"for image size ({img.width}x{img.height}). Skipping drawing."
            )
            return image_bytes

        border_rect_line_width = line_thickness + (2 * border_size)
        if border_size > 0 and border_rect_line_width > 0:
            draw.rectangle([x1, y1, x2, y2], outline=border_color, width=border_rect_line_width)

        if line_thickness > 0 :
            draw.rectangle([x1, y1, x2, y2], outline=primary_color, width=line_thickness)

        output_buffer = io.BytesIO()
        img.save(output_buffer, format="PNG")
        return output_buffer.getvalue()
    except Exception as e:
        logging.error(f"Error in draw_rectangle_on_image with box {box_coords}: {e}", exc_info=True)
        return None

def are_visual_hashes_valid(hash1: Optional[str], hash2: Optional[str]) -> bool:
    """
    Checks if two visual hash strings are valid for comparison (i.e., not error strings).
    """
    if not hash1 or not hash2:
        return False
    error_strings = ["no_image", "hash_error"]
    if hash1 in error_strings or hash2 in error_strings:
        return False
    return True

if __name__ == '__main__':
    # Example usage or tests for utils can go here
    print(f"Utils module loaded. SCRIPT_START_TIME: {SCRIPT_START_TIME}")

    # Basic test for LoggerManager
    test_logger_manager = LoggerManager()
    test_logger = test_logger_manager.setup_logging(log_level_str='DEBUG', log_file='test_utils.log')
    test_logger.info("This is an info message from utils.py test.")
    test_logger.debug("This is a debug message from utils.py test.")
    print("Check test_utils.log for output.")

    # Clean up test log file
    if os.path.exists('test_utils.log'):
        try:
            # Close handlers if any are still open by the root logger for this file
            for handler in test_logger.handlers:
                if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath('test_utils.log'):
                    handler.close()
            os.remove('test_utils.log')
            print("Cleaned up test_utils.log.")
        except Exception as e:
            print(f"Could not remove test_utils.log: {e}")