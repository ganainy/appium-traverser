"""
This test module verifies the behavior of the `ParsedData` entity in the core parser. It checks:
- Initialization and default values of ParsedData.
- Validation logic for valid and invalid data.
- Error handling for invalid element types, identifiers, and bounding boxes.
"""
import pytest
from core.parser import ParsedData


class TestParsedData:
    """Test ParsedData entity functionality."""

    @pytest.fixture
    def sample_data(self):
        """Sample parsed data for testing."""
        return {
            "session_id": "test-session-123",
            "element_type": "button",
            "identifier": "com.example:id/continue",
            "bounding_box": {
                "top_left": [100, 50],
                "bottom_right": [200, 100]
            },
            "properties": {"text": "Continue", "enabled": True},
            "confidence_score": 0.95
        }

    def test_init_default(self, sample_data):
        """Test ParsedData initialization with defaults."""
        data = ParsedData(**sample_data)

        assert data.element_type == "button"
        assert data.identifier == "com.example:id/continue"
        assert data.bounding_box["top_left"] == [100, 50]
        assert data.properties["text"] == "Continue"
        assert data.confidence_score == 0.95
        assert data.data_id is not None

    def test_validate_valid_data(self, sample_data):
        """Test validation of valid parsed data."""
        data = ParsedData(**sample_data)

        # Should not raise
        data.validate()

    def test_validate_invalid_element_type(self, sample_data):
        """Test validation rejects invalid element type."""
        data = ParsedData(**{**sample_data, "element_type": "invalid"})

        with pytest.raises(ValueError, match="Invalid element type"):
            data.validate()

    def test_validate_empty_identifier(self, sample_data):
        """Test validation rejects empty identifier."""
        data = ParsedData(**{**sample_data, "identifier": ""})

        with pytest.raises(ValueError, match="Identifier cannot be empty"):
            data.validate()

    def test_validate_invalid_bounding_box(self, sample_data):
        """Test validation rejects invalid bounding box."""
        # Missing key
        invalid_data = ParsedData(**{**sample_data, "bounding_box": {"top_left": [100, 50]}})

        with pytest.raises(ValueError, match="Bounding box missing bottom_right"):
            invalid_data.validate()

    def test_validate_negative_coordinates(self, sample_data):
        """Test validation rejects negative coordinates."""
        data = ParsedData(**{
            **sample_data,
            "bounding_box": {"top_left": [-10, 50], "bottom_right": [200, 100]}
        })

        with pytest.raises(ValueError, match="coordinates must be non-negative"):
            data.validate()

    def test_validate_invalid_geometry(self, sample_data):
        """Test validation rejects invalid bounding box geometry."""
        # top_left below bottom_right
        data = ParsedData(**{
            **sample_data,
            "bounding_box": {"top_left": [200, 100], "bottom_right": [100, 50]}
        })

        with pytest.raises(ValueError, match="top_left must be above and left of bottom_right"):
            data.validate()

    def test_validate_invalid_confidence(self, sample_data):
        """Test validation rejects invalid confidence score."""
        data = ParsedData(**{**sample_data, "confidence_score": 1.5})

        with pytest.raises(ValueError, match="Confidence score must be between"):
            data.validate()