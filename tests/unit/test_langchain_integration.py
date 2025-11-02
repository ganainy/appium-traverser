"""
This test module verifies the integration of LangChain with the agent assistant. It checks:
- Creation of LangChain chains for workflow testing.
- Mocking of configuration, MCP client, and model adapter.
- Agent interaction with mocked dependencies and response generation.
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from typing import Dict, Any, Optional

from domain.agent_assistant import AgentAssistant


class TestLangChainIntegration:
    '''Test suite for LangChain integration functionality.'''

    @pytest.fixture
    def mock_config(self):
        '''Create a mock configuration object.'''
        config = MagicMock()

        config.AI_PROVIDER = 'gemini'
        config.MCP_SERVER_URL = 'http://localhost:3000/mcp'
        config.MCP_CONNECTION_TIMEOUT = 5.0
        config.MCP_REQUEST_TIMEOUT = 10.0
        config.MCP_MAX_RETRIES = 3
        config.LOG_DIR = '/tmp/logs'
        config.ENABLE_IMAGE_CONTEXT = False  # Disable image context for testing

        return config

    @pytest.fixture
    def mock_mcp_client(self):
        '''Create a mock MCP client.'''
        client = MagicMock()

        client.initialize_session.return_value = {'session_id': 'test-session-123'}
        client.execute_action.return_value = {'status': 'success', 'action_result': 'clicked'}
        client.get_screen_state.return_value = {'screen': 'home', 'elements': []}

        return client

    @pytest.fixture
    def mock_model_adapter(self):
        '''Create a mock model adapter.'''
        adapter = MagicMock()

        adapter.generate_response.return_value = (
            '{"action": "click", "target_identifier": "test-button"}',
            {'processing_time': 1.0, 'token_count': {'total': 100}}
        )

        return adapter

    def test_langchain_chain_creation(self, mock_config, mock_mcp_client, mock_model_adapter):
        '''Test that LangChain chains can be created for testing workflows.'''
        with patch('domain.agent_assistant.create_model_adapter', return_value=mock_model_adapter), \
             patch('domain.agent_tools.AgentTools') as mock_tools_class:

            mock_tools = MagicMock()
            mock_tools_class.return_value = mock_tools

            # Create agent with MCP client
            agent = AgentAssistant(
                app_config=mock_config,
                mcp_client=mock_mcp_client,
                model_alias_override='test-model',
                agent_tools=mock_tools
            )

            # Verify that the agent was initialized with LangChain components
            assert agent.mcp_client is mock_mcp_client
            assert agent.model_adapter is mock_model_adapter

            # Test that we can create a basic chain structure
            assert hasattr(agent, 'model_adapter')
            assert hasattr(agent, 'mcp_client')

    def test_langchain_orchestration_flow(self, mock_config, mock_mcp_client, mock_model_adapter):
        '''Test the orchestration flow through LangChain chains.'''
        with patch('domain.agent_assistant.create_model_adapter', return_value=mock_model_adapter), \
             patch('domain.agent_tools.AgentTools') as mock_tools_class:

            mock_tools = MagicMock()
            mock_tools_class.return_value = mock_tools

            agent = AgentAssistant(
                app_config=mock_config,
                mcp_client=mock_mcp_client,
                model_alias_override='test-model',
                agent_tools=mock_tools
            )

            # Mock the _build_system_prompt method
            with patch.object(agent, '_build_system_prompt', return_value='Test prompt'):
                # Test get_next_action which should orchestrate through LangChain
                result = agent.get_next_action(
                    screenshot_bytes=None,
                    xml_context='<xml>test</xml>',
                    previous_actions=[],
                    current_screen_visit_count=1,
                    current_composite_hash='hash123',
                    last_action_feedback=None
                )

                # Verify the orchestration flow
                assert result is not None
                action_data, elapsed_time, token_count = result
                assert 'action_to_perform' in action_data
                assert elapsed_time >= 0
                assert token_count > 0

                # Verify model adapter was called
                mock_model_adapter.generate_response.assert_called_once()

    def test_langchain_error_handling(self, mock_config, mock_mcp_client, mock_model_adapter):
        '''Test error handling in LangChain orchestration.'''
        with patch('domain.agent_assistant.create_model_adapter', return_value=mock_model_adapter), \
             patch('domain.agent_tools.AgentTools') as mock_tools_class:

            mock_tools = MagicMock()
            mock_tools_class.return_value = mock_tools

            agent = AgentAssistant(
                app_config=mock_config,
                mcp_client=mock_mcp_client,
                model_alias_override='test-model',
                agent_tools=mock_tools
            )

            # Test error in model adapter
            mock_model_adapter.generate_response.side_effect = Exception('Model error')

            result = agent.get_next_action(
                screenshot_bytes=None,
                xml_context='<xml>test</xml>',
                previous_actions=[],
                current_screen_visit_count=1,
                current_composite_hash='hash123',
                last_action_feedback=None
            )

            # Should handle error gracefully
            assert result is None
