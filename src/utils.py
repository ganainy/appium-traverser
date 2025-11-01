#!/usr/bin/env python3
import io
import json
import logging
import os
import sys
import time

try:
    # Import Config only when needed to avoid circular import
    from traverser_ai_api.config import Config
except ImportError:
    # Import Config only when needed to avoid circular import
    from traverser_ai_api.config import Config

import hashlib
import shutil
import xml.etree.ElementTree as std_etree
from typing import Any, Dict, List, Optional, Set, Tuple, cast

import imagehash
from PIL import Image, ImageDraw

try:
    import lxml.etree as lxml_etree
    USING_LXML = True
except ImportError as e:
    lxml_etree = None
    USING_LXML = False
    logging.warning(f"⚠️ lxml not available, falling back to xml.etree.ElementTree. Error: {e}")
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

class UIColoredLogHandler(logging.Handler):
    """Custom logging handler that routes log messages to the UI with emoji indicators for better visibility."""

    def __init__(self, ui_controller):
        super().__init__()
        self.ui_controller = ui_controller

    def emit(self, record):
        """Emit a log record to the UI with emoji indicators based on log level and content."""
        try:
            message = self.format(record)
            message_lower = message.lower()
            color = 'white'  # Default color
            
            # Check if the message already has an emoji prefix
            has_emoji = any(emoji in message[:4] for emoji in ["🔴", "⚠️", "ℹ️", "✅", "🔧", "📌", "🚀", "🔍", "🟢", "🔒", "📍", "👁️", "🔐", "👆", "⌨️", "📜", "👈", "⬅️", "⚡"])
            
            # Add emoji indicators based on log level and message content
            if record.levelno >= logging.CRITICAL:
                if not has_emoji:
                    message = f"🔴 CRITICAL: {message}"  # Critical errors
                color = 'red'
            elif record.levelno >= logging.ERROR:
                if not has_emoji:
                    message = f"🔴 {message}"  # Regular errors
                color = 'red'
            elif record.levelno >= logging.WARNING:
                if not has_emoji:
                    message = f"⚠️ {message}"  # Warnings
                color = 'orange'
            elif record.levelno >= logging.INFO:
                if not has_emoji:
                    # Add specific indicators based on message content
                    if 'success' in message_lower or 'completed' in message_lower:
                        message = f"✅ {message}"
                        color = 'green'
                    elif 'connected' in message_lower or 'ready' in message_lower:
                        message = f"🟢 {message}"
                        color = 'green'
                    elif 'important' in message_lower:
                        message = f"📌 {message}"
                        color = 'magenta'
                    elif 'privacy' in message_lower:
                        message = f"🔒 {message}"
                        color = 'blue'
                    elif 'detecting' in message_lower or 'checking' in message_lower:
                        message = f"🔍 {message}"
                        color = 'cyan'
                    elif 'starting' in message_lower or 'initializing' in message_lower:
                        message = f"🚀 {message}"
                        color = 'blue'
                    elif 'failure' in message_lower or 'fail' in message_lower:
                        message = f"🔴 {message}"  # Failures need red indicator
                        color = 'red'
                    elif 'termination' in message_lower or 'terminated' in message_lower:
                        message = f"🔴 {message}"  # Termination messages need red indicator
                        color = 'red'
                    else:
                        message = f"ℹ️ {message}"  # Default info indicator
                        color = 'blue'
            elif record.levelno >= logging.DEBUG:
                if not has_emoji:
                    message = f"🔧 {message}"  # Debug messages
                color = 'gray'

            # Send to UI controller if available
            if self.ui_controller and hasattr(self.ui_controller, 'log_message'):
                self.ui_controller.log_message(message, color=color)
        except Exception:
            # Don't let logging errors crash the application
            pass
class LoggerManager:
    def __init__(self):
        self.handlers: List[logging.Handler] = []
        self.stdout_wrapper: Optional[io.TextIOWrapper] = None
        self.stderr_wrapper: Optional[io.TextIOWrapper] = None
        self.ui_controller = None  # Reference to UI controller for colored logging

    def set_ui_controller(self, ui_controller):
        """Set the UI controller reference for routing colored log messages."""
        self.ui_controller = ui_controller
        
        # If logging is already set up, add the UI handler now
        if self.handlers:  # Check if setup_logging has been called
            logger = logging.getLogger()
            
            # Check if UI handler is already added
            has_ui_handler = any(isinstance(handler, UIColoredLogHandler) for handler in logger.handlers)
            
            if not has_ui_handler and self.ui_controller:
                # Get the current log level from the logger
                current_level = logger.level
                
                # Create and add UI handler
                ui_handler = UIColoredLogHandler(self.ui_controller)
                ui_handler.setLevel(current_level)
                
                # Use the same formatter as other handlers
                for handler in logger.handlers:
                    if hasattr(handler, 'formatter') and handler.formatter:
                        ui_handler.setFormatter(handler.formatter)
                        break
                
                logger.addHandler(ui_handler)
                self.handlers.append(ui_handler)
                logging.debug("UIColoredLogHandler added to existing logger configuration")

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
            # Prepare stderr wrapper as well for any direct error prints
            if not self.stderr_wrapper:
                self.stderr_wrapper = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
            console_handler = logging.StreamHandler(self.stdout_wrapper)
        except Exception:
            console_handler = logging.StreamHandler(sys.stdout)

        console_handler.setFormatter(log_formatter)
        logger.addHandler(console_handler)
        self.handlers.append(console_handler)

        # Add UI handler for colored logging if UI controller is available
        if self.ui_controller:
            ui_handler = UIColoredLogHandler(self.ui_controller)
            ui_handler.setLevel(numeric_level)
            ui_handler.setFormatter(log_formatter)
            logger.addHandler(ui_handler)
            self.handlers.append(ui_handler)

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
                try:
                    if self.stderr_wrapper:
                        print(f"Error setting up file logger for {log_file}: {e}", file=self.stderr_wrapper)
                    else:
                        print(f"Error setting up file logger for {log_file}: {e}", file=sys.stderr)
                except Exception:
                    # Last resort if printing fails
                    pass

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
CONTAINER_CLASSES = {
    # Common Android container/layout classes (suffixes; we strip package prefixes)
    'FrameLayout', 'LinearLayout', 'RelativeLayout', 'ConstraintLayout',
    'RecyclerView', 'ListView', 'ScrollView', 'NestedScrollView',
    'ViewPager', 'CoordinatorLayout', 'AppBarLayout'
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
        logging.error(f"🔴 Error calculating visual hash: {e}")
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
        logging.error(f"🔴 Error calculating hash distance between {hash1} and {hash2}: {e}")
        return 1000

def simplify_xml_for_ai(xml_string: str, max_len: int, provider: str = "gemini", prune_noninteractive: bool = True) -> str:
    """
    Simplifies XML by removing non-essential attributes and potentially empty nodes,
    aiming to stay under max_len without arbitrary truncation.
    
    Args:
        xml_string: The XML string to simplify
        max_len: Maximum length in characters
        provider: AI provider ("gemini", etc.) for provider-specific optimizations
    """
    if not xml_string:
        return ""

    original_len = len(xml_string)
    if original_len > 200:
        logging.debug(f"Original XML length: {original_len} (provider: {provider})")

    # Get provider capabilities from config
    try:
        from config import AI_PROVIDER_CAPABILITIES
    except ImportError:
        from config import AI_PROVIDER_CAPABILITIES
    
    capabilities = AI_PROVIDER_CAPABILITIES.get(provider.lower(), AI_PROVIDER_CAPABILITIES.get('gemini', {}))
    provider_xml_limit = capabilities.get('xml_max_len', max_len)
    
    # Use the more restrictive limit between configured max_len and provider capability
    effective_max_len = min(max_len, provider_xml_limit)
    # Tight mode for small provider limits or explicitly small max_len
    tight_mode = effective_max_len <= 50000 or provider.lower() in {"openrouter", "ollama"}
    
    if effective_max_len != max_len:
        logging.debug(f"Applied {provider}-specific XML limit: {effective_max_len} (from configured {max_len})")

    possible_parse_errors = (std_etree.ParseError,)
    if USING_LXML and lxml_etree:
        possible_parse_errors += (lxml_etree.ParseError, lxml_etree.XMLSyntaxError)

    try:
        if USING_LXML and lxml_etree:
            parser = lxml_etree.XMLParser(recover=True, remove_blank_text=True)
            root = lxml_etree.fromstring(xml_string.encode('utf-8'), parser=parser)
        else:
            root = std_etree.fromstring(xml_string.encode('utf-8'))

        if root is None:
            raise ValueError("Failed to parse XML root.")

        # First pass: keep only whitelisted attrs and drop false booleans
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
            # Provider-aware attribute prioritization and compression
            # - In tight_mode, drop non-critical boolean attrs except 'clickable'
            if tight_mode:
                for maybe_drop in ('focusable', 'enabled', 'checkable', 'checked', 'selected', 'editable', 'long-clickable', 'password', 'hint'):
                    element.attrib.pop(maybe_drop, None)
            # Compress 'class' to suffix without package prefix (e.g., android.widget.FrameLayout -> FrameLayout)
            if 'class' in element.attrib and isinstance(element.attrib['class'], str):
                cls = element.attrib['class']
                if '.' in cls:
                    element.attrib['class'] = cls.split('.')[-1]
            # In tight_mode, for non-interactive nodes later, we may drop 'class'

        # Second pass: interactive-node-centric text handling
        # Interactive criteria: any of clickable, focusable, checkable, long-clickable == 'true'
        interactive_flags: Dict[Any, bool] = {}
        MAX_TEXT_FIELD_LEN = 80 if tight_mode else 120
        for element in root.iter('*'):
            try:
                is_interactive = any(
                    element.attrib.get(attr, '').lower() == 'true'
                    for attr in ['clickable', 'focusable', 'checkable', 'long-clickable']
                )
            except Exception:
                is_interactive = False
            interactive_flags[element] = is_interactive

            if is_interactive:
                # Truncate long text fields to reduce token usage
                for field in ('text', 'content-desc'):
                    if field in element.attrib and isinstance(element.attrib[field], str):
                        val = element.attrib[field]
                        if len(val) > MAX_TEXT_FIELD_LEN:
                            element.attrib[field] = val[:MAX_TEXT_FIELD_LEN]
            else:
                # Remove non-essential text for non-interactive nodes
                element.attrib.pop('text', None)
                element.attrib.pop('content-desc', None)
                if tight_mode:
                    # Bounds of non-interactive containers rarely help; drop to save tokens
                    element.attrib.pop('bounds', None)
                if tight_mode:
                    # Drop class for purely structural, non-interactive nodes to save tokens
                    element.attrib.pop('class', None)

        # Third pass (optional, when lxml is available): prune non-interactive containers
        # that have no resource-id and no interactive descendants (controlled by prune_noninteractive)
        if prune_noninteractive and USING_LXML and lxml_etree:
            try:
                nodes_to_remove: List[Any] = []
                for element in root.iter('*'):
                    # Skip the root element
                    if element.getparent() is None:
                        continue
                    has_resource_id = bool(element.attrib.get('resource-id', ''))
                    is_interactive = bool(interactive_flags.get(element, False))
                    if is_interactive or has_resource_id:
                        continue
                    # Check if any descendant is interactive or has a resource-id
                    descendant_has_interactive = False
                    descendant_has_id = False
                    for desc in element.iterdescendants():
                        if interactive_flags.get(desc, False):
                            descendant_has_interactive = True
                            break
                        if bool(desc.attrib.get('resource-id', '')):
                            descendant_has_id = True
                            # do not break; prefer detecting interactive first
                    # Additional pruning for large structural containers in tight_mode
                    if tight_mode:
                        cls = element.attrib.get('class', '')
                        cls_suffix = cls.split('.')[-1] if '.' in cls else cls
                        many_children = len(element) >= 4
                        is_structural = cls_suffix in CONTAINER_CLASSES or (not cls_suffix and many_children)
                        if is_structural and not descendant_has_interactive and not descendant_has_id:
                            nodes_to_remove.append(element)
                    else:
                        if not descendant_has_interactive:
                            nodes_to_remove.append(element)

                # Remove after collection to avoid mutating while iterating
                for node in nodes_to_remove:
                    parent = node.getparent()
                    try:
                        parent.remove(node)
                    except Exception:
                        # If removal fails, skip silently
                        pass
            except Exception as e:
                logging.debug(f"XML pruning skipped due to error: {e}")

        if USING_LXML and lxml_etree:
            xml_bytes = lxml_etree.tostring(root)
        else:
            xml_bytes = std_etree.tostring(root)
        simplified_xml = xml_bytes.decode('utf-8')

        if len(simplified_xml) > effective_max_len:
            logging.warning(f"⚠️ Simplified XML still exceeds max_len ({len(simplified_xml)} > {effective_max_len}) for {provider}. Performing final smart truncation.")
            trunc_point = simplified_xml.rfind('</', 0, effective_max_len)
            if trunc_point != -1:
                end_tag_point = simplified_xml.find('>', trunc_point, effective_max_len + 30)
                if end_tag_point != -1:
                    simplified_xml = simplified_xml[:end_tag_point+1] + "\n... (truncated)"
                else:
                    simplified_xml = simplified_xml[:effective_max_len] + "... (truncated)"
            else:
                simplified_xml = simplified_xml[:effective_max_len] + "... (truncated)"

        simplified_xml = re.sub(r'>\s+<', '><', simplified_xml).strip()

        final_len = len(simplified_xml)
        if original_len > 200:
            logging.debug(f"Simplified XML length: {final_len} (from {original_len}) for {provider}")
        return simplified_xml

    except possible_parse_errors + (ValueError, TypeError) as e:
        logging.error(f"🔴 Failed to parse or simplify XML for {provider}: {e}. Falling back to basic truncation.")
        return xml_string[:effective_max_len] + "\n... (fallback truncation)" if len(xml_string) > effective_max_len else xml_string
    except Exception as e:
        logging.error(f"🔴 Unexpected error during XML simplification for {provider}: {e}. Falling back.", exc_info=True)
        return xml_string[:effective_max_len] + "\n... (fallback truncation)" if len(xml_string) > effective_max_len else xml_string

def filter_xml_by_allowed_packages(xml_string: str, target_package: str, allowed_packages: List[str]) -> str:
    """
    Filters an XML string, removing elements not belonging to the target or allowed packages.
    System UI packages (e.g., 'com.android.systemui') are implicitly allowed to keep essential navigation.
    """
    if not xml_string:
        return ""

    possible_parse_errors = (std_etree.ParseError,)
    if USING_LXML and lxml_etree:
        possible_parse_errors += (lxml_etree.ParseError, lxml_etree.XMLSyntaxError)

    try:
        if USING_LXML and lxml_etree:
            parser = lxml_etree.XMLParser(recover=True, remove_blank_text=True)
            root = lxml_etree.fromstring(xml_string.encode('utf-8'), parser=parser)
        else:
            root = std_etree.fromstring(xml_string.encode('utf-8'))
        if root is None:
            raise ValueError("Failed to parse XML root.")

        allowed_set: Set[str] = set(allowed_packages)
        allowed_set.add(target_package)
        allowed_set.add('com.android.systemui')

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

        if USING_LXML and lxml_etree:
            xml_bytes = lxml_etree.tostring(root)
        else:
            xml_bytes = std_etree.tostring(root)
        return xml_bytes.decode('utf-8')

    except possible_parse_errors + (ValueError, TypeError) as e:
        logging.error(f"🔴 XML ParseError during package filtering: {e}. Returning original XML.")
        return xml_string
    except Exception as e:
        logging.error(f"🔴 Unexpected error during XML filtering: {e}", exc_info=True)
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
        logging.error(f"🔴 Error drawing indicator at {coordinates}: {e}")
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
        logging.warning("⚠️ draw_rectangle_on_image: Missing image_bytes or box_coords.")
        return None
    if line_thickness <= 0:
        logging.warning("⚠️ draw_rectangle_on_image: line_thickness must be positive.")
        return image_bytes
    if border_size < 0:
        logging.warning("⚠️ draw_rectangle_on_image: border_size cannot be negative.")
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)
        x1, y1, x2, y2 = box_coords

        if not (0 <= x1 < img.width and 0 <= y1 < img.height and \
                x1 < x2 <= img.width and y1 < y2 <= img.height):
            logging.warning(
                f"⚠️ draw_rectangle_on_image: Invalid or out-of-bounds box_coords ({x1},{y1},{x2},{y2}) "
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
        logging.error(f"🔴 Error in draw_rectangle_on_image with box {box_coords}: {e}", exc_info=True)
        return None

def create_jsonrpc_request(method: str, params: Optional[Dict[str, Any]] = None, request_id: Optional[str] = None) -> Dict[str, Any]:
    """Create a JSON-RPC 2.0 request dictionary."""
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": request_id or str(int(time.time() * 1000))
    }
    if params:
        request["params"] = params
    return request


def validate_jsonrpc_response(response: Dict[str, Any]) -> bool:
    """Validate that a response conforms to JSON-RPC 2.0 format."""
    if not isinstance(response, dict):
        return False
    if response.get("jsonrpc") != "2.0":
        return False
    if "id" not in response:
        return False
    # Either result or error must be present, but not both
    has_result = "result" in response
    has_error = "error" in response
    return (has_result or has_error) and not (has_result and has_error)

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
