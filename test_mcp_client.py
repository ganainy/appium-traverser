#!/usr/bin/env python3
"""
Test script to validate MCP client functionality.
"""

def test_mcp_client():
    """Test MCP client import and basic functionality."""
    try:
        from traverser_ai_api.mcp_client import MCPClient, CircuitBreakerState
        print('SUCCESS: MCP client can be imported')

        # Test client creation
        client = MCPClient('http://localhost:3000/mcp')
        print('SUCCESS: MCP client can be instantiated')
        print(f'Circuit breaker state: {client.circuit_breaker.state.value}')
        print(f'Server URL: {client.server_url}')
        print(f'Connection timeout: {client.connection_timeout}')
        print(f'Request timeout: {client.request_timeout}')
        print(f'Max retries: {client.max_retries}')

        return True

    except Exception as e:
        print(f'ERROR: MCP client test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_mcp_client()
    exit(0 if success else 1)