"""
Integration tests for LangChain orchestration flow with MCP client.

These tests verify the complete orchestration flow from AI decision making
through MCP server communication to action execution.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

from domain.agent_assistant import AgentAssistant
from infrastructure.mcp_client import MCPClient



class TestLangChainOrchestrationIntegration:
    """Integration tests for complete LangChain orchestration flow with MCP client."""

    @pytest.fixture
    def real_config(self):
        """Create a real config object for integration testing."""
        from config.config import Config
        config = Mock(spec=Config)
        config.AI_PROVIDER = "gemini"
        config.GEMINI_API_KEY = "test_key"
        config.MCP_SERVER_URL = "http://localhost:3000/mcp"
        config.MCP_CONNECTION_TIMEOUT = 5.0
        config.MCP_REQUEST_TIMEOUT = 10.0
        config.MCP_MAX_RETRIES = 2
        config.DEFAULT_MODEL_TYPE = "gemini-2.5-flash-image"
        config.LONG_PRESS_MIN_DURATION_MS = 600
        config.FOCUS_AREAS = []
        config.ENABLE_IMAGE_CONTEXT = False  # Disable for integration testing
        config.AVAILABLE_ACTIONS = ["click", "input", "scroll_down", "scroll_up", "back"]
        return config

    @pytest.fixture
    def mock_mcp_client(self):
        """Create a mock MCP client that simulates real server responses."""
        client = Mock(spec=MCPClient)

        # Simulate successful session initialization
        client.initialize_session.return_value = {
            "session_id": "integration-test-session-123",
            "capabilities": ["execute_action", "get_screen_state"]
        }

        # Simulate successful action execution
        client.execute_action.return_value = {
            "status": "success",
            "action_result": "clicked",
            "execution_time_ms": 150
        }

        # Simulate screen state retrieval
        client.get_screen_state.return_value = {
            "screen": "home",
            "elements": [
                {"id": "com.example:id/button1", "text": "Continue"},
                {"id": "com.example:id/input1", "type": "input"}
            ],
            "timestamp": "2025-10-31T12:00:00Z"
        }

        return client

    @pytest.fixture
    def mock_model_adapter(self):
        """Create a mock model adapter that returns realistic AI responses."""
        adapter = Mock()

        # Return different responses based on context
        def generate_response_side_effect(prompt, **kwargs):
            if "Continue" in prompt and "button" in prompt:
                return (
                    '{"action": "click", "target_identifier": "com.example:id/button1", "reasoning": "Primary CTA visible"}',
                    {"processing_time": 1.2, "token_count": {"total": 150}}
                )
            elif "input" in prompt and "type=\"email\"" in prompt:
                return (
                    '{"action": "input", "target_identifier": "com.example:id/input1", "input_text": "test@example.com", "reasoning": "Email input field detected"}',
                    {"processing_time": 1.0, "token_count": {"total": 120}}
                )
            elif "scrollable" in prompt:
                return (
                    '{"action": "scroll_down", "reasoning": "Scrollable content detected, need to see more"}',
                    {"processing_time": 0.8, "token_count": {"total": 100}}
                )
            else:
                return (
                    '{"action": "click", "target_identifier": "default_target", "reasoning": "Default action"}',
                    {"processing_time": 1.0, "token_count": {"total": 100}}
                )

        adapter.generate_response.side_effect = generate_response_side_effect
        return adapter

    @pytest.fixture
    def agent_with_mcp(self, real_config, mock_mcp_client, mock_model_adapter):
        """Create an AgentAssistant with MCP client integration."""
        with patch('domain.agent_assistant.create_model_adapter', return_value=mock_model_adapter):
            # Create mock agent tools
            mock_tools = Mock()
            mock_tools.driver = Mock()
            mock_tools.driver.tap.return_value = True
            mock_tools.driver.input_text.return_value = True
            mock_tools.driver.scroll.return_value = True
            mock_tools.driver.press_back.return_value = True

            agent = AgentAssistant(
                app_config=real_config,
                mcp_client=mock_mcp_client,
                model_alias_override="integration-test-model",
                agent_tools=mock_tools
            )

            return agent

    def test_complete_orchestration_flow_click_action(self, agent_with_mcp, mock_mcp_client, mock_model_adapter):
        """Test complete orchestration flow for a click action."""
        # Test the full orchestration flow
        result = agent_with_mcp.get_next_action(
            screenshot_bytes=None,
            xml_context='<xml><button id="com.example:id/button1">Continue</button></xml>',
            previous_actions=[],
            current_screen_visit_count=1,
            current_composite_hash="hash123",
            last_action_feedback=None
        )

        # Verify orchestration completed successfully
        assert result is not None
        action_data, elapsed_time, token_count = result

        assert "action_to_perform" in action_data
        assert action_data["action_to_perform"]["action"] == "click"
        assert action_data["action_to_perform"]["target_identifier"] == "com.example:id/button1"
        assert elapsed_time > 0
        assert token_count > 0

        # Verify model adapter was called with correct prompt
        mock_model_adapter.generate_response.assert_called_once()
        call_args = mock_model_adapter.generate_response.call_args
        prompt = call_args[1]['prompt']  # Access keyword argument
        assert "Continue" in prompt
        assert "XML CONTEXT" in prompt

    def test_orchestration_flow_with_previous_actions(self, agent_with_mcp, mock_mcp_client, mock_model_adapter):
        """Test orchestration flow considers previous actions in context."""
        previous_actions = [
            "Clicked continue button",
            "Scrolled down to see more content"
        ]

        result = agent_with_mcp.get_next_action(
            screenshot_bytes=None,
            xml_context='<xml><input id="com.example:id/input1" type="email"/></xml>',
            previous_actions=previous_actions,
            current_screen_visit_count=2,
            current_composite_hash="hash456",
            last_action_feedback="Good progress"
        )

        assert result is not None
        action_data, elapsed_time, token_count = result

        # Verify previous actions are included in the prompt
        mock_model_adapter.generate_response.assert_called_once()
        call_args = mock_model_adapter.generate_response.call_args
        prompt = call_args[1]['prompt']  # Access keyword argument

        assert "Clicked continue button" in prompt
        assert "Scrolled down to see more content" in prompt
        assert "Good progress" in prompt

    def test_orchestration_flow_input_action(self, agent_with_mcp, mock_mcp_client, mock_model_adapter):
        """Test orchestration flow for input actions."""
        result = agent_with_mcp.get_next_action(
            screenshot_bytes=None,
            xml_context='<xml><input id="com.example:id/input1" type="email" hint="Enter email"/></xml>',
            previous_actions=[],
            current_screen_visit_count=1,
            current_composite_hash="hash789",
            last_action_feedback=None
        )

        assert result is not None
        action_data, elapsed_time, token_count = result

        action = action_data["action_to_perform"]
        assert action["action"] == "input"
        assert action["target_identifier"] == "com.example:id/input1"
        assert action["input_text"] == "test@example.com"

    def test_orchestration_flow_scroll_action(self, agent_with_mcp, mock_mcp_client, mock_model_adapter):
        """Test orchestration flow for scroll actions."""
        result = agent_with_mcp.get_next_action(
            screenshot_bytes=None,
            xml_context='<xml><scrollable><item>Item 1</item><item>Item 2</item></scrollable></xml>',
            previous_actions=[],
            current_screen_visit_count=1,
            current_composite_hash="hash999",
            last_action_feedback=None
        )

        assert result is not None
        action_data, elapsed_time, token_count = result

        action = action_data["action_to_perform"]
        assert action["action"] == "scroll_down"
        assert "reasoning" in action

    def test_mcp_client_integration_in_orchestration(self, agent_with_mcp, mock_mcp_client):
        """Test that MCP client is properly integrated into orchestration flow."""
        # Verify MCP client is accessible
        assert agent_with_mcp.mcp_client is mock_mcp_client

        # Test MCP connection status checking
        status = agent_with_mcp.check_mcp_connection_status()
        assert status["connected"] is True
        assert status.get("response_time_ms") is not None
        assert status.get("error_details") is None

    def test_orchestration_with_mcp_error_handling(self, real_config, mock_mcp_client, mock_model_adapter):
        """Test orchestration handles MCP client errors gracefully."""
        # Configure MCP client to fail
        mock_mcp_client.initialize_session.side_effect = Exception("MCP server unavailable")

        with patch('domain.agent_assistant.create_model_adapter', return_value=mock_model_adapter):
            mock_tools = Mock()
            agent = AgentAssistant(
                app_config=real_config,
                mcp_client=mock_mcp_client,
                model_alias_override="error-test-model",
                agent_tools=mock_tools
            )

            # Test that agent can still function even with MCP issues
            # (MCP errors shouldn't break the basic orchestration)
            result = agent.get_next_action(
                screenshot_bytes=None,
                xml_context='<xml><button>Continue</button></xml>',
                previous_actions=[],
                current_screen_visit_count=1,
                current_composite_hash="error_hash",
                last_action_feedback=None
            )

            # Should still return a result (MCP errors are handled gracefully)
            assert result is not None

    def test_orchestration_context_maintenance(self, agent_with_mcp, mock_model_adapter):
        """Test that orchestration maintains context across multiple calls."""
        # First call
        result1 = agent_with_mcp.get_next_action(
            screenshot_bytes=None,
            xml_context='<xml><button id="btn1">Continue</button></xml>',
            previous_actions=[],
            current_screen_visit_count=1,
            current_composite_hash="ctx1",
            last_action_feedback=None
        )

        # Second call with different context
        result2 = agent_with_mcp.get_next_action(
            screenshot_bytes=None,
            xml_context='<xml><input id="input1">Enter text</input></xml>',
            previous_actions=["Clicked continue button"],
            current_screen_visit_count=2,
            current_composite_hash="ctx2",
            last_action_feedback="Success"
        )

        # Third call
        result3 = agent_with_mcp.get_next_action(
            screenshot_bytes=None,
            xml_context='<xml><scrollable>Content</scrollable></xml>',
            previous_actions=["Clicked continue button", "Entered text"],
            current_screen_visit_count=3,
            current_composite_hash="ctx3",
            last_action_feedback=None
        )

        # Verify all calls succeeded
        assert result1 is not None
        assert result2 is not None
        assert result3 is not None

        # Verify different actions were generated based on context
        actions = [
            result1[0]["action_to_perform"]["action"],
            result2[0]["action_to_perform"]["action"],
            result3[0]["action_to_perform"]["action"]
        ]

        # Should have variety in actions based on context
        assert len(set(actions)) >= 2  # At least 2 different action types

    def test_orchestration_performance_metrics(self, agent_with_mcp, mock_model_adapter):
        """Test that orchestration provides performance metrics."""
        import time

        start_time = time.time()
        result = agent_with_mcp.get_next_action(
            screenshot_bytes=None,
            xml_context='<xml><button>Continue</button></xml>',
            previous_actions=[],
            current_screen_visit_count=1,
            current_composite_hash="perf_test",
            last_action_feedback=None
        )
        end_time = time.time()

        assert result is not None
        action_data, elapsed_time, token_count = result

        # Verify timing is reasonable
        assert elapsed_time > 0
        assert elapsed_time < 10  # Should complete within 10 seconds
        assert token_count > 0

        # Verify token count is reasonable
        assert isinstance(token_count, int)
        assert token_count < 1000  # Shouldn't use excessive tokens

    @pytest.mark.parametrize("action_type", [
        "click",
        "input",
        "scroll_down",
        "scroll_up",
        "back"
    ])
    def test_orchestration_action_execution_routing(self, agent_with_mcp, mock_mcp_client, action_type):
        """Test that different action types are routed to correct MCP methods."""
        # Create action data directly for testing execution routing
        action_data = {
            "action": action_type,
            "target_identifier": "test_target" if action_type in ["click", "input"] else None,
            "input_text": "test text" if action_type == "input" else None
        }

        # Execute the action to test routing
        success = agent_with_mcp.execute_action(action_data)

        # Verify the action was executed (mock returns True)
        assert success is True

        # Verify the correct driver method was called
        if action_type == "click":
            agent_with_mcp.tools.driver.tap.assert_called()
        elif action_type == "input":
            agent_with_mcp.tools.driver.input_text.assert_called()
        elif action_type in ["scroll_down", "scroll_up"]:
            agent_with_mcp.tools.driver.scroll.assert_called()