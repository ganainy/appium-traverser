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





