import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from domain.agent_assistant import AgentAssistant


class TestAgentAssistantErrorRecovery:
    """Unit tests for AgentAssistant error recovery functionality."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration object."""
        config = Mock()
        config.AI_PROVIDER = 'openrouter'
        config.OPENROUTER_API_KEY = 'test-key'
        config.OLLAMA_BASE_URL = 'http://localhost:11434'
        config.DEFAULT_MODEL_TYPE = 'gpt-3.5-turbo'
        config.ENABLE_IMAGE_CONTEXT = True
        config.MCP_SERVER_URL = 'http://localhost:3000/mcp'
        config.FOCUS_AREAS = []
        config.FOCUS_MAX_ACTIVE = 5
        config.USE_LANGCHAIN_ORCHESTRATION = True
        config.LANGCHAIN_MEMORY_K = 10  # Fix for LangChain initialization
        return config

    @pytest.fixture
    def mock_mcp_client(self):
        """Create a mock MCP client."""
        client = Mock()
        client.get_circuit_breaker_state.return_value = {
            "state": "closed",
            "failure_count": 0,
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
            "last_failure_time": None,
            "recovery_time": None,
            "can_attempt_reset": False
        }
        return client

    @pytest.fixture
    def agent_assistant(self, mock_config, mock_mcp_client):
        """Create an AgentAssistant instance with mocked dependencies."""
        with patch('domain.agent_assistant.create_model_adapter') as mock_adapter, \
             patch('domain.agent_assistant.Session') as mock_session, \
             patch.object(AgentAssistant, '_init_langchain_components') as mock_init_langchain:

            # Mock the model adapter
            mock_model_adapter = Mock()
            mock_adapter.return_value = mock_model_adapter

            # Mock the session
            mock_session_instance = Mock()
            mock_session.return_value = mock_session_instance

            # Create agent assistant - LangChain init will be mocked
            assistant = AgentAssistant(
                app_config=mock_config,
                mcp_client=mock_mcp_client
            )

            # Mock the LangChain components to avoid initialization issues
            assistant.action_decision_chain = Mock()
            assistant.context_analysis_chain = Mock()
            assistant.langchain_llm = Mock()
            assistant.langchain_memory = Mock()

            return assistant

    def test_check_mcp_connection_status_healthy(self, agent_assistant, mock_mcp_client):
        """Test MCP connection status check when healthy."""
        mock_mcp_client.get_screen_state.return_value = {"status": "healthy"}

        status = agent_assistant.check_mcp_connection_status()

        assert status["connected"] is True
        assert "response_time_ms" in status
        assert status["circuit_breaker"]["state"] == "closed"

    def test_check_mcp_connection_status_circuit_breaker_open(self, agent_assistant, mock_mcp_client):
        """Test MCP connection status when circuit breaker is open."""
        mock_mcp_client.get_circuit_breaker_state.return_value = {
            "state": "open",
            "failure_count": 5,
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
            "last_failure_time": 1234567890,
            "recovery_time": 1234567950,
            "can_attempt_reset": False
        }

        status = agent_assistant.check_mcp_connection_status()

        assert status["connected"] is False
        assert "Circuit breaker is OPEN" in status["reason"]
        assert status["circuit_breaker"]["state"] == "open"

    def test_check_mcp_connection_status_connection_failed(self, agent_assistant, mock_mcp_client):
        """Test MCP connection status when connection fails."""
        mock_mcp_client.get_screen_state.side_effect = Exception("Connection refused")

        status = agent_assistant.check_mcp_connection_status()

        assert status["connected"] is False
        assert "Connection failed" in status["reason"]
        assert "error_details" in status

    def test_get_next_action_langchain_mcp_unavailable_fallback(self, agent_assistant, mock_mcp_client):
        """Test that LangChain method falls back when MCP is unavailable."""
        # Mock MCP as unavailable
        mock_mcp_client.get_circuit_breaker_state.return_value = {
            "state": "open",
            "failure_count": 5,
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
            "last_failure_time": 1234567890,
            "recovery_time": 1234567950,
            "can_attempt_reset": False
        }

        # Mock the direct method to return a result
        with patch.object(agent_assistant, '_get_next_action_direct') as mock_direct:
            mock_direct.return_value = ({"action_to_perform": {"action": "click"}}, 1.0, 100)

            result = agent_assistant._get_next_action_langchain(
                None, "<xml></xml>", [], 1, "hash123"
            )

            # Should have called the direct fallback
            mock_direct.assert_called_once()
            assert result is not None

    def test_get_next_action_direct_mcp_unavailable_returns_none(self, agent_assistant, mock_mcp_client):
        """Test that direct method returns None when MCP is unavailable."""
        # Mock MCP as unavailable
        mock_mcp_client.get_circuit_breaker_state.return_value = {
            "state": "open",
            "failure_count": 5,
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
            "last_failure_time": 1234567890,
            "recovery_time": 1234567950,
            "can_attempt_reset": False
        }

        result = agent_assistant._get_next_action_direct(
            None, "<xml></xml>", [], 1, "hash123"
        )

        assert result is None

    def test_get_next_action_langchain_mcp_error_during_execution_fallback(self, agent_assistant, mock_mcp_client):
        """Test that LangChain method falls back when MCP error occurs during execution."""
        # Mock MCP as initially healthy
        mock_mcp_client.get_circuit_breaker_state.return_value = {
            "state": "closed",
            "failure_count": 0,
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
            "last_failure_time": None,
            "recovery_time": None,
            "can_attempt_reset": False
        }
        # Mock the health check to succeed
        mock_mcp_client.get_screen_state.return_value = {"status": "healthy"}

        # Disable image context to avoid image processing
        agent_assistant.cfg.ENABLE_IMAGE_CONTEXT = False

        # Mock the chain to raise an MCP-related error
        agent_assistant.action_decision_chain.invoke.side_effect = Exception("Circuit breaker is OPEN")

        # Mock the direct method to return a result
        with patch.object(agent_assistant, '_get_next_action_direct') as mock_direct:
            mock_direct.return_value = ({"action_to_perform": {"action": "click"}}, 1.0, 100)

            result = agent_assistant._get_next_action_langchain(
                None, "<xml></xml>", [], 1, "hash123"
            )

            # Check that invoke was called
            agent_assistant.action_decision_chain.invoke.assert_called_once()
            
            # Should have called the direct fallback
            mock_direct.assert_called_once()
            assert result is not None

    def test_log_error_recovery_event_mcp_fallback(self, agent_assistant):
        """Test logging of MCP fallback recovery events."""
        with patch('domain.agent_assistant.logging') as mock_logging:
            agent_assistant.log_error_recovery_event("mcp_fallback", {
                "fallback_from": "langchain_orchestration",
                "fallback_to": "direct_model",
                "reason": "Circuit breaker open"
            })

            # Verify warning log was called
            mock_logging.warning.assert_called_once()
            warning_call = mock_logging.warning.call_args[0][0]
            assert "Error recovery: Falling back due to MCP unavailability" in warning_call

            # Verify structured log was called
            mock_logging.info.assert_called()
            info_calls = [call for call in mock_logging.info.call_args_list if "ERROR_RECOVERY:" in str(call)]
            assert len(info_calls) > 0

    def test_log_error_recovery_event_mcp_unavailable(self, agent_assistant):
        """Test logging of MCP unavailable events."""
        with patch('domain.agent_assistant.logging') as mock_logging:
            agent_assistant.log_error_recovery_event("mcp_unavailable", {
                "context": "direct_model_call",
                "reason": "Server down",
                "recovery_possible": False
            })

            # Verify info log was called (since mcp_unavailable is not a special case)
            mock_logging.info.assert_called()
            info_calls = mock_logging.info.call_args_list
            assert any("Error recovery event: mcp_unavailable" in str(call) for call in info_calls)

    def test_log_mcp_connection_status_with_circuit_breaker_details(self, agent_assistant, mock_mcp_client):
        """Test that connection status logging includes circuit breaker details."""
        mock_mcp_client.get_circuit_breaker_state.return_value = {
            "state": "half_open",
            "failure_count": 3,
            "failure_threshold": 5,
            "recovery_timeout": 60.0,
            "last_failure_time": 1234567890,
            "recovery_time": 1234567950,
            "can_attempt_reset": True
        }
        mock_mcp_client.get_screen_state.return_value = {"status": "healthy"}

        with patch('domain.agent_assistant.logging') as mock_logging:
            agent_assistant.log_mcp_connection_status()

            # Verify structured logging includes circuit breaker info
            mock_logging.info.assert_called()
            info_calls = [call for call in mock_logging.info.call_args_list if "MCP_STATUS:" in str(call)]
            assert len(info_calls) > 0

            # Parse the JSON log entry
            status_call = info_calls[0]
            log_json = status_call[0][0].replace("MCP_STATUS: ", "")
            log_data = json.loads(log_json)

            assert "circuit_breaker" in log_data["mcp_connection"]
            cb_info = log_data["mcp_connection"]["circuit_breaker"]
            assert cb_info["state"] == "half_open"
            assert cb_info["failure_count"] == 3
            assert cb_info["can_attempt_reset"] is True