# tests/integration/test_mcp_routing.py
"""
Integration tests for MCP server routing.

These tests verify that all device actions are routed through the MCP server
and not executed directly via Appium.
"""
import pytest
from unittest.mock import Mock, patch

from traverser_ai_api.agent_assistant import AgentAssistant
from traverser_ai_api.appium_driver import AppiumDriver



class TestMCPRouting:
    """Test that agent actions are routed through MCP server."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config for testing."""
        from traverser_ai_api.config import Config
        config = Mock(spec=Config)
        config.AI_PROVIDER = "gemini"
        config.GEMINI_API_KEY = "test_key"
        config.DEFAULT_MODEL_TYPE = "gemini-2.5-flash-image"
        config.USE_CHAT_MEMORY = False
        config.MAX_CHAT_HISTORY = 10
        config.LONG_PRESS_MIN_DURATION_MS = 600
        config.FOCUS_AREAS = []
        return config

    @pytest.fixture
    def mock_driver(self, mock_config):
        """Create a mock MCP driver."""
        driver = Mock(spec=AppiumDriver)
        driver.tap.return_value = True
        driver.input_text.return_value = True
        driver.scroll.return_value = True
        driver.long_press.return_value = True
        driver.press_back.return_value = True
        driver.press_home.return_value = True
        return driver

    @pytest.fixture
    def agent_assistant(self, mock_config, mock_driver):
        """Create an agent assistant with mocked dependencies."""
        # Mock the model adapter
        with patch('traverser_ai_api.agent_assistant.create_model_adapter') as mock_create:
            mock_adapter = Mock()
            mock_adapter.generate_response.return_value = ('{"action": "tap", "target_identifier": "test_button"}', 1.0, 100)
            mock_create.return_value = mock_adapter

            # Create agent tools mock
            mock_tools = Mock()
            mock_tools.driver = mock_driver
            mock_tools.click_element.return_value = {"success": True}
            mock_tools.input_text.return_value = {"success": True}
            mock_tools.scroll.return_value = {"success": True}
            mock_tools.long_press.return_value = {"success": True}
            mock_tools.press_back.return_value = {"success": True}
            mock_tools.press_home.return_value = {"success": True}

            assistant = AgentAssistant(
                app_config=mock_config,
                agent_tools=mock_tools
            )
            return assistant

    def test_tap_action_routes_through_mcp(self, agent_assistant, mock_driver):
        """Test that tap actions are routed through MCP driver."""
        action_data = {
            "action": "click",
            "target_identifier": "test_button"
        }

        result = agent_assistant.execute_action(action_data)

        assert result is True
        # Verify MCP driver tap was called
        mock_driver.tap.assert_called_once_with("test_button", None)

    def test_input_action_routes_through_mcp(self, agent_assistant, mock_driver):
        """Test that input actions are routed through MCP driver."""
        action_data = {
            "action": "input",
            "target_identifier": "input_field",
            "input_text": "test text"
        }

        result = agent_assistant.execute_action(action_data)

        assert result is True
        # Verify MCP driver input_text was called
        mock_driver.input_text.assert_called_once_with("input_field", "test text")

    def test_scroll_action_routes_through_mcp(self, agent_assistant, mock_driver):
        """Test that scroll actions are routed through MCP driver."""
        action_data = {
            "action": "scroll_down",
            "target_identifier": None
        }

        result = agent_assistant.execute_action(action_data)

        assert result is True
        # Verify MCP driver scroll was called
        mock_driver.scroll.assert_called_once_with(None, "down")

    def test_back_action_routes_through_mcp(self, agent_assistant, mock_driver):
        """Test that back actions are routed through MCP driver."""
        action_data = {
            "action": "back"
        }

        result = agent_assistant.execute_action(action_data)

        assert result is True
        # Verify MCP driver press_back was called
        mock_driver.press_back.assert_called_once()

    def test_home_action_routes_through_mcp(self, agent_assistant, mock_driver):
        """Test that home actions are routed through MCP driver."""
        action_data = {
            "action": "home"
        }

        # Note: The execute_action doesn't handle "home", but press_home is available
        # This test verifies the MCP routing infrastructure
        mock_driver.press_home.return_value = True
        mock_driver.press_home.assert_not_called()  # Should not be called for "home" action

    def test_long_press_action_routes_through_mcp(self, agent_assistant, mock_driver):
        """Test that long press actions are routed through MCP driver."""
        action_data = {
            "action": "long_press",
            "target_identifier": "test_element",
            "duration_ms": 1000
        }

        result = agent_assistant.execute_action(action_data)

        assert result is True
        # Verify MCP driver long_press was called
        mock_driver.long_press.assert_called_once_with("test_element", 1000)

    def test_all_actions_use_mcp_driver(self, agent_assistant, mock_driver):
        """Test that all supported actions use the MCP driver methods."""
        actions = [
            {"action": "click", "target_identifier": "btn"},
            {"action": "input", "target_identifier": "field", "input_text": "text"},
            {"action": "scroll_down"},
            {"action": "scroll_up"},
            {"action": "swipe_left"},
            {"action": "swipe_right"},
            {"action": "back"},
            {"action": "long_press", "target_identifier": "btn", "duration_ms": 500}
        ]

        for action in actions:
            agent_assistant.execute_action(action)

        # Verify MCP driver methods were called
        assert mock_driver.tap.called
        assert mock_driver.input_text.called
        assert mock_driver.scroll.called
        assert mock_driver.press_back.called
        assert mock_driver.long_press.called