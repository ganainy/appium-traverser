"""
This test module verifies the behavior of the core `CrawlerSession` entity. It checks:
- Initialization of CrawlerSession with default and custom configurations.
- Validation logic for session status and progress values.
- Error handling for invalid session states.
- Session lifecycle methods such as start and end.
"""
import pytest
from datetime import datetime
from core.config import Configuration
from core.crawler import CrawlerSession


class TestCrawlerSession:
    """Test CrawlerSession entity functionality."""

    @pytest.fixture
    def sample_config(self):
        """Sample configuration for testing."""
        return Configuration(
            name="test_config",
            settings={"max_depth": 3, "timeout": 60, "platform": "android"}
        )

    def test_init_default(self, sample_config):
        """Test CrawlerSession initialization with defaults."""
        session = CrawlerSession(sample_config)

        assert session.status == "pending"
        assert session.progress == 0.0
        assert session.start_time is None
        assert session.end_time is None
        assert session.results == []
        assert session.error_message is None
        assert session.session_id is not None

    def test_validate_valid_session(self, sample_config):
        """Test validation of valid session."""
        session = CrawlerSession(sample_config)

        # Should not raise
        session.validate()

    def test_validate_invalid_status(self, sample_config):
        """Test validation rejects invalid status."""
        session = CrawlerSession(sample_config)
        session.status = "invalid"

        with pytest.raises(ValueError, match="Invalid status"):
            session.validate()

    def test_validate_invalid_progress(self, sample_config):
        """Test validation rejects invalid progress."""
        session = CrawlerSession(sample_config)
        session.progress = 1.5

        with pytest.raises(ValueError, match="Progress must be between"):
            session.validate()

    def test_start_session(self, sample_config):
        """Test starting a session."""
        session = CrawlerSession(sample_config)

        session.start()

        assert session.status == "running"
        assert session.start_time is not None
        assert isinstance(session.start_time, datetime)

    def test_start_already_started_fails(self, sample_config):
        """Test starting an already started session fails."""
        session = CrawlerSession(sample_config)
        session.start()

        with pytest.raises(ValueError, match="Can only start pending sessions"):
            session.start()

    def test_complete_session(self, sample_config):
        """Test completing a session."""
        session = CrawlerSession(sample_config)
        session.start()

        session.complete()

        assert session.status == "completed"
        assert session.progress == 1.0
        assert session.end_time is not None

    def test_complete_not_running_fails(self, sample_config):
        """Test completing a non-running session fails."""
        session = CrawlerSession(sample_config)

        with pytest.raises(ValueError, match="Can only complete running sessions"):
            session.complete()

    def test_fail_session(self, sample_config):
        """Test failing a session."""
        session = CrawlerSession(sample_config)
        session.start()

        session.fail("Test error")

        assert session.status == "failed"
        assert session.error_message == "Test error"
        assert session.end_time is not None

    def test_stop_session(self, sample_config):
        """Test stopping a session."""
        session = CrawlerSession(sample_config)
        session.start()

        session.stop()

        assert session.status == "stopped"
        assert session.end_time is not None

    def test_stop_not_running_fails(self, sample_config):
        """Test stopping a completed session fails."""
        session = CrawlerSession(sample_config)
        session.start()
        session.complete()

        with pytest.raises(ValueError, match="Can only stop running or pending sessions"):
            session.stop()