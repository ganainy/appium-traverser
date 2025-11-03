"""
Data parsing and ParsedData entity management.
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ParsedData:
    """
    Represents structured data extracted during crawling.
    """
    
    # Schema Definition
    VALID_ELEMENT_TYPES = ["button", "text", "input", "image", "container"]
    # Bounding Box Schema
    BBOX_TOP_LEFT_KEY = "top_left"
    BBOX_BOTTOM_RIGHT_KEY = "bottom_right"
    BBOX_REQUIRED_KEYS = [BBOX_TOP_LEFT_KEY, BBOX_BOTTOM_RIGHT_KEY]
    BBOX_COORD_LENGTH = 2
    MIN_COORD_VALUE = 0
    # Validation Rules
    MIN_CONFIDENCE = 0.0
    MAX_CONFIDENCE = 1.0

    def __init__(
        self,
        session_id: str,
        element_type: str,
        identifier: str,
        bounding_box: Dict[str, List[int]],
        properties: Optional[Dict[str, Any]] = None,
        confidence_score: float = 1.0,
        data_id: Optional[str] = None
    ):
        self.data_id = data_id or str(uuid.uuid4())
        self.session_id = session_id
        self.element_type = element_type
        self.identifier = identifier
        self.bounding_box = bounding_box
        self.properties = properties or {}
        self.confidence_score = confidence_score
        self.timestamp = datetime.now()

    def validate(self) -> None:
        """
        Validate parsed data.
        """
        logger.debug(f"Validating ParsedData: {self.data_id}")
        if self.element_type not in self.VALID_ELEMENT_TYPES:
            logger.error(f"Invalid element type: {self.element_type}")
            raise ValueError(f"Invalid element type: {self.element_type}")

        if not self.identifier:
            logger.error("Identifier cannot be empty")
            raise ValueError("Identifier cannot be empty")

        if not isinstance(self.bounding_box, dict):
            logger.error("Bounding box must be a dictionary")
            raise ValueError("Bounding box must be a dictionary")

        for key in self.BBOX_REQUIRED_KEYS:
            if key not in self.bounding_box:
                logger.error(f"Bounding box missing {key}")
                raise ValueError(f"Bounding box missing {key}")

            if not isinstance(self.bounding_box[key], list) or len(self.bounding_box[key]) != self.BBOX_COORD_LENGTH:
                logger.error(f"{key} must be a list of 2 integers")
                raise ValueError(f"{key} must be a list of 2 integers")

            if not all(isinstance(coord, int) and coord >= self.MIN_COORD_VALUE for coord in self.bounding_box[key]):
                logger.error(f"{key} coordinates must be non-negative integers")
                raise ValueError(f"{key} coordinates must be non-negative integers")

        # Validate bounding box geometry
        tl = self.bounding_box[self.BBOX_TOP_LEFT_KEY]
        br = self.bounding_box[self.BBOX_BOTTOM_RIGHT_KEY]
        if tl[0] >= br[0] or tl[1] >= br[1]:
            logger.error("Invalid bounding box: top_left must be above and left of bottom_right")
            raise ValueError("Invalid bounding box: top_left must be above and left of bottom_right")

        if not (self.MIN_CONFIDENCE <= self.confidence_score <= self.MAX_CONFIDENCE):
            logger.error("Confidence score must be between 0.0 and 1.0")
            raise ValueError("Confidence score must be between 0.0 and 1.0")

        logger.debug(f"ParsedData validation successful: {self.data_id}")


def parse_raw_data(raw_data: Dict[str, Any]) -> List[ParsedData]:
    """
    Parse raw crawling data into structured ParsedData objects.

    Args:
        raw_data: Raw data from crawling source

    Returns:
        List of ParsedData objects
    """
    logger.debug("Parsing raw data")
    try:
        # This is a placeholder implementation
        # In full implementation, this would parse XML, screenshots, etc.
        # For now, return empty list
        parsed_items = []
        logger.info(f"Parsed {len(parsed_items)} items from raw data")
        return parsed_items
    except Exception as e:
        logger.error(f"Failed to parse raw data: {e}")
        raise