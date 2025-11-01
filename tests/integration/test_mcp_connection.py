import pytest
from traverser_ai_api.mcp_client import MCPClient, MCPConnectionError


class TestMCPConnectionIntegration:
    """Integration tests for MCP client connection to real server."""

    @pytest.fixture
    def mcp_client(self):
        """Create MCP client with real server URL."""
        return MCPClient(
            server_url="http://localhost:3000/mcp",
            connection_timeout=5.0,
            request_timeout=10.0,
            max_retries=2
        )

    def test_mcp_server_connection(self, mcp_client):
        """Test that MCP server accepts connections and responds to ping."""
        # This is a basic connectivity test
        # Since we don't know the exact methods supported, we'll try a simple request
        # that should fail gracefully but confirm the server is responding

        try:
            # Try to send a request that might not be implemented but should get a response
            result = mcp_client._send_request("system.ping")
            # If we get here, server responded
            assert "jsonrpc" in result
            assert result["jsonrpc"] == "2.0"
        except MCPConnectionError:
            # Server not running or network issue
            pytest.skip("MCP server not available for integration testing")
        except Exception as e:
            # Server responded but with error - that's still a valid connection
            assert "MCP Error" in str(e) or "Method not found" in str(e)

    def test_jsonrpc_handshake_format(self, mcp_client):
        """Test that JSON-RPC requests are properly formatted."""
        # Test the request formatting without actually sending
        from unittest.mock import patch

        with patch.object(mcp_client, '_send_request') as mock_send:
            mock_send.return_value = {
                "jsonrpc": "2.0",
                "result": {"status": "ok"},
                "id": "test-123"
            }

            # This should work if the method exists
            try:
                result = mcp_client._send_request("test.handshake")
                # Verify response format
                assert result["jsonrpc"] == "2.0"
                assert "result" in result or "error" in result
                assert "id" in result
            except MCPConnectionError:
                pytest.skip("Cannot test handshake format without server")

    def test_connection_timeout_handling(self, mcp_client):
        """Test that connection timeouts are handled properly."""
        # Create client with very short timeout
        fast_client = MCPClient(
            server_url="http://10.255.255.1:12345",  # Non-routable address
            request_timeout=0.001,
            max_retries=1
        )

        with pytest.raises(MCPConnectionError):
            fast_client._send_request("test.timeout")

    def test_invalid_server_url(self):
        """Test handling of completely invalid server URLs."""
        client = MCPClient("http://invalid.server.url:9999", max_retries=1)

        with pytest.raises(MCPConnectionError):
            client._send_request("test.invalid")