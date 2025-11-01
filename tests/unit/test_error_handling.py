import pytest
import time
from unittest.mock import Mock, patch, MagicMock
import requests
from traverser_ai_api.mcp_client import MCPClient, MCPConnectionError, MCPError


class TestMCPClientRetryLogic:
    """Test suite for MCP client retry logic and error handling."""

    def setup_method(self):
        """Set up test fixtures."""
        self.server_url = "http://localhost:3000"
        self.client = MCPClient(
            server_url=self.server_url,
            connection_timeout=1.0,
            request_timeout=2.0,
            max_retries=3
        )

    def test_successful_request_no_retry(self):
        """Test that successful requests don't trigger retries."""
        # Mock successful response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-1"}
        
        with patch.object(self.client._session, 'post', return_value=mock_response) as mock_post:
            # Make request
            result = self.client._send_request("test.method")

            # Verify only one request was made
            assert mock_post.call_count == 1
            assert result == {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-1"}

    def test_retry_on_connection_error(self):
        """Test that connection errors trigger retries with exponential backoff."""
        # Mock connection error for first two attempts, success on third
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-1"}

        with patch.object(self.client._session, 'post') as mock_post:
            mock_post.side_effect = [
                requests.exceptions.ConnectionError("Connection failed"),
                requests.exceptions.ConnectionError("Connection failed"),
                mock_response
            ]

            start_time = time.time()
            result = self.client._send_request("test.method")
            end_time = time.time()

            # Verify three attempts were made
            assert mock_post.call_count == 3
            # Verify exponential backoff (should take at least 1 + 2 = 3 seconds)
            assert end_time - start_time >= 3.0
            assert result == {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-1"}

    def test_max_retries_exceeded(self):
        """Test that max retries are respected and proper exception is raised."""
        with patch.object(self.client._session, 'post', side_effect=requests.exceptions.ConnectionError("Connection failed")) as mock_post:
            with pytest.raises(MCPConnectionError) as exc_info:
                self.client._send_request("test.method")

            # Verify max_retries + 1 attempts were made (initial + retries)
            assert mock_post.call_count == self.client.max_retries + 1
            assert f"Failed to connect to MCP server after {self.client.max_retries + 1} attempts" in str(exc_info.value)

    def test_mcp_error_response_handling(self):
        """Test that MCP error responses are properly handled."""
        # Mock response with MCP error
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
            "id": "req-1"
        }
        
        with patch.object(self.client._session, 'post', return_value=mock_response) as mock_post:
            with pytest.raises(MCPError) as exc_info:
                self.client._send_request("invalid.method")

            # Verify only one request (no retries for MCP errors)
            assert mock_post.call_count == 1
            assert exc_info.value.code == -32601
            assert "Method not found" in exc_info.value.message

    @patch('time.sleep')
    def test_exponential_backoff_timing(self, mock_sleep):
        """Test that exponential backoff uses correct timing."""
        with patch.object(self.client._session, 'post', side_effect=requests.exceptions.ConnectionError("Connection failed")) as mock_post:
            with pytest.raises(MCPConnectionError):
                self.client._send_request("test.method")

            # Verify sleep calls: base delays are 2^0 = 1, 2^1 = 2, 2^2 = 4 seconds, plus jitter
            expected_base_delays = [1, 2, 4]
            actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
            
            # Check that each actual delay is at least the base delay (base + jitter >= base)
            for actual, expected in zip(actual_delays, expected_base_delays):
                assert actual >= expected
                assert actual < expected + 1  # Jitter is < 1 second

    def test_timeout_error_retry(self):
        """Test that timeout errors trigger retries."""
        # Mock timeout error for first attempt, success on second
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-1"}

        with patch.object(self.client._session, 'post') as mock_post:
            mock_post.side_effect = [
                requests.exceptions.Timeout("Request timed out"),
                mock_response
            ]

            result = self.client._send_request("test.method")

            # Verify two attempts were made
            assert mock_post.call_count == 2
            assert result == {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-1"}

    def test_http_error_no_retry(self):
        """Test that HTTP errors (4xx, 5xx) don't trigger retries."""
        # Mock HTTP 500 error
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        
        with patch.object(self.client._session, 'post', return_value=mock_response) as mock_post:
            with pytest.raises(MCPConnectionError):
                self.client._send_request("test.method")

            # Verify only one attempt (HTTP errors shouldn't retry)
            assert mock_post.call_count == 1

    def test_custom_retry_configuration(self):
        """Test that custom retry configuration is respected."""
        client = MCPClient(
            server_url=self.server_url,
            max_retries=5,
            connection_timeout=2.0,
            request_timeout=10.0
        )

        assert client.max_retries == 5
        assert client.connection_timeout == 2.0
        assert client.request_timeout == 10.0

    def test_request_id_increment(self):
        """Test that request IDs are properly incremented."""
        # Mock successful responses
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = [
            {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-1"},
            {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-2"},
            {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-3"}
        ]
        
        with patch.object(self.client._session, 'post', return_value=mock_response) as mock_post:
            # Make multiple requests
            self.client._send_request("method1")
            self.client._send_request("method2")
            self.client._send_request("method3")

            # Verify request IDs were sent correctly
            calls = mock_post.call_args_list
            assert calls[0][1]['json']['id'] == 'req-1'
            assert calls[1][1]['json']['id'] == 'req-2'
            assert calls[2][1]['json']['id'] == 'req-3'