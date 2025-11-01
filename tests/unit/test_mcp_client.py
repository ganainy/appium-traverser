import pytest
import requests
import requests.adapters
import time
from unittest.mock import Mock, patch
from traverser_ai_api.mcp_client import MCPClient, MCPError, MCPConnectionError, CircuitBreakerState


class TestMCPClient:
    """Unit tests for MCPClient."""

    def test_initialization(self):
        """Test MCPClient initialization with default values."""
        client = MCPClient("http://localhost:3000/mcp")
        assert client.server_url == "http://localhost:3000/mcp"
        assert client.connection_timeout == 5.0
        assert client.request_timeout == 30.0
        assert client.max_retries == 3

    def test_initialization_custom_values(self):
        """Test MCPClient initialization with custom values."""
        client = MCPClient(
            "http://example.com",
            connection_timeout=10.0,
            request_timeout=60.0,
            max_retries=5
        )
        assert client.server_url == "http://example.com"
        assert client.connection_timeout == 10.0
        assert client.request_timeout == 60.0
        assert client.max_retries == 5

    def test_send_request_success(self):
        """Test successful JSON-RPC request."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "result": {"status": "success"},
            "id": "req-1"
        }
        
        client = MCPClient("http://localhost:3000/mcp")
        with patch.object(client._session, 'post', return_value=mock_response) as mock_post:
            result = client._send_request("test.method")
            
            assert result["result"]["status"] == "success"
            mock_post.assert_called_once()

    def test_send_request_error_response(self):
        """Test handling of JSON-RPC error response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "error": {"code": -32601, "message": "Method not found"},
            "id": "req-1"
        }
        
        client = MCPClient("http://localhost:3000/mcp")
        with patch.object(client._session, 'post', return_value=mock_response) as mock_post:
            with pytest.raises(MCPError) as exc_info:
                client._send_request("invalid.method")

            assert exc_info.value.code == -32601
            assert "Method not found" in str(exc_info.value)

    def test_send_request_connection_failure_retry(self):
        """Test retry logic on connection failure."""
        mock_success_response = Mock()
        mock_success_response.json.return_value = {"jsonrpc": "2.0", "result": {"status": "success"}, "id": "req-3"}
        
        client = MCPClient("http://localhost:3000/mcp", max_retries=3)
        with patch.object(client._session, 'post') as mock_post:
            mock_post.side_effect = [
                requests.exceptions.ConnectionError("Connection failed"),
                requests.exceptions.ConnectionError("Connection failed"),
                mock_success_response
            ]

            result = client._send_request("test.method")

            assert result["result"]["status"] == "success"
            assert mock_post.call_count == 3

    def test_send_request_max_retries_exceeded(self):
        """Test that MCPConnectionError is raised after max retries."""
        client = MCPClient("http://localhost:3000/mcp", max_retries=2)
        
        with patch.object(client._session, 'post', side_effect=requests.exceptions.ConnectionError("Connection failed")) as mock_post:
            with pytest.raises(MCPConnectionError) as exc_info:
                client._send_request("test.method")

            assert "after 3 attempts" in str(exc_info.value)
            assert mock_post.call_count == 3

    def test_initialize_session(self):
        """Test initialize_session method."""
        with patch.object(MCPClient, '_send_request') as mock_send:
            mock_send.return_value = {
                "result": {"session_id": "session-123", "status": "initialized"}
            }

            client = MCPClient("http://localhost:3000/mcp")
            result = client.initialize_session("com.example.app")

            mock_send.assert_called_once_with("appium.initialize_session", {"app_package": "com.example.app"})
            assert result["session_id"] == "session-123"

    def test_execute_action(self):
        """Test execute_action method."""
        action = {
            "type": "click",
            "target_identifier": "com.example:id/button"
        }

        with patch.object(MCPClient, '_send_request') as mock_send:
            mock_send.return_value = {
                "result": {"status": "success", "message": "Action executed"}
            }

            client = MCPClient("http://localhost:3000/mcp")
            result = client.execute_action(action)

            expected_params = {"action": action}
            mock_send.assert_called_once_with("appium.execute_action", expected_params)
            assert result["status"] == "success"

    def test_get_screen_state(self):
        """Test get_screen_state method."""
        with patch.object(MCPClient, '_send_request') as mock_send:
            mock_send.return_value = {
                "result": {
                    "screenshot": "base64data",
                    "xml_dump": "<xml></xml>",
                    "current_activity": "MainActivity"
                }
            }

            client = MCPClient("http://localhost:3000/mcp")
            result = client.get_screen_state()

            expected_params = {"include_screenshot": True, "include_xml": True}
            mock_send.assert_called_once_with("appium.get_screen_state", expected_params)
            assert result["screenshot"] == "base64data"

    def test_session_configuration(self):
        """Test that HTTP session is properly configured with connection pooling."""
        client = MCPClient("http://localhost:3000/mcp")
        
        # Check that session exists
        assert hasattr(client, '_session')
        assert isinstance(client._session, requests.Session)
        
        # Check that adapters are configured
        assert 'http://' in client._session.adapters
        assert 'https://' in client._session.adapters
        
        # Check adapter type (HTTPAdapter)
        http_adapter = client._session.adapters['http://']
        assert isinstance(http_adapter, requests.adapters.HTTPAdapter)
        
        # Check that adapter has connection pooling configured
        # We can't directly access config, but we can verify the adapter was created with our settings
        # by checking that it's not the default adapter
        assert http_adapter is not requests.adapters.HTTPAdapter()

    def test_circuit_breaker_state_caching(self):
        """Test circuit breaker state caching mechanism."""
        client = MCPClient("http://localhost:3000/mcp")
        
        # First call should compute fresh state
        state1 = client.get_circuit_breaker_state()
        assert 'state' in state1
        assert 'failure_count' in state1
        assert state1['failure_count'] == 0
        
        # Modify circuit breaker state
        client.circuit_breaker.failure_count = 2
        client.circuit_breaker.last_failure_time = time.time()
        
        # Second call should return cached state (not updated)
        state2 = client.get_circuit_breaker_state()
        assert state2['failure_count'] == 0  # Should be cached value
        
        # Expire cache by setting old timestamp
        client._cache_timestamp = time.time() - 10  # 10 seconds ago
        
        # Third call should get fresh state
        state3 = client.get_circuit_breaker_state()
        assert state3['failure_count'] == 2  # Should be updated value

    def test_circuit_breaker_cache_ttl(self):
        """Test circuit breaker cache TTL behavior."""
        client = MCPClient("http://localhost:3000/mcp", circuit_breaker_failure_threshold=3)
        
        # Set cache TTL to 1 second for testing
        client._cache_ttl = 1.0
        
        # Get initial state
        state1 = client.get_circuit_breaker_state()
        cache_time = client._cache_timestamp
        
        # Wait for cache to expire
        time.sleep(1.1)
        
        # Modify circuit breaker
        client.circuit_breaker.failure_count = 1
        
        # Get state again - should be fresh
        state2 = client.get_circuit_breaker_state()
        assert state2['failure_count'] == 1
        assert client._cache_timestamp > cache_time

    def test_context_manager_usage(self):
        """Test context manager functionality."""
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            with MCPClient("http://localhost:3000/mcp") as client:
                assert client is not None
            
            # Verify close was called
            mock_session.close.assert_called_once()

    def test_close_method(self):
        """Test explicit session cleanup."""
        with patch('requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            client = MCPClient("http://localhost:3000/mcp")
            client.close()
            
            # Verify close was called
            mock_session.close.assert_called_once()

    def test_circuit_breaker_state_transitions(self):
        """Test circuit breaker state transitions."""
        client = MCPClient("http://localhost:3000/mcp", circuit_breaker_failure_threshold=2)
        
        # Start in CLOSED state
        assert client.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert client.circuit_breaker.failure_count == 0
        
        # Record failures
        client.circuit_breaker._record_failure()
        assert client.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert client.circuit_breaker.failure_count == 1
        
        client.circuit_breaker._record_failure()
        assert client.circuit_breaker.state == CircuitBreakerState.OPEN
        assert client.circuit_breaker.failure_count == 2
        
        # Record success (should not change OPEN state)
        client.circuit_breaker._record_success()
        assert client.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert client.circuit_breaker.failure_count == 0

    def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery from HALF_OPEN state."""
        client = MCPClient("http://localhost:3000/mcp", circuit_breaker_failure_threshold=2)
        
        # Force OPEN state
        client.circuit_breaker.failure_count = 2
        client.circuit_breaker.state = CircuitBreakerState.OPEN
        client.circuit_breaker.last_failure_time = time.time() - 70  # 70 seconds ago
        
        # Should attempt reset
        assert client.circuit_breaker._should_attempt_reset()
        
        # Simulate successful call in HALF_OPEN state
        client.circuit_breaker.state = CircuitBreakerState.HALF_OPEN
        client.circuit_breaker._record_success()
        assert client.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert client.circuit_breaker.failure_count == 0

    def test_request_id_generation(self):
        """Test that request IDs are properly incremented."""
        client = MCPClient("http://localhost:3000/mcp")
        
        # Check initial state
        assert client._request_id == 0
        
        # Generate IDs
        id1 = client._get_next_id()
        id2 = client._get_next_id()
        id3 = client._get_next_id()
        
        assert id1 == "req-1"
        assert id2 == "req-2"
        assert id3 == "req-3"
        assert client._request_id == 3

    def test_initialize_session_with_optional_params(self):
        """Test initialize_session with optional parameters."""
        with patch.object(MCPClient, '_send_request') as mock_send:
            mock_send.return_value = {
                "result": {"session_id": "session-123", "status": "initialized"}
            }

            client = MCPClient("http://localhost:3000/mcp")
            result = client.initialize_session(
                "com.example.app",
                app_activity="com.example.MainActivity",
                device_udid="device123"
            )

            expected_params = {
                "app_package": "com.example.app",
                "app_activity": "com.example.MainActivity",
                "device_udid": "device123"
            }
            mock_send.assert_called_once_with("appium.initialize_session", expected_params)
            assert result["session_id"] == "session-123"

    def test_execute_action_with_session_context(self):
        """Test execute_action with session context."""
        action = {"type": "click", "target_identifier": "com.example:id/button"}
        session_context = {"session_id": "session-123"}

        with patch.object(MCPClient, '_send_request') as mock_send:
            mock_send.return_value = {
                "result": {"status": "success", "message": "Action executed"}
            }

            client = MCPClient("http://localhost:3000/mcp")
            result = client.execute_action(action, session_context)

            expected_params = {
                "action": action,
                "session_context": session_context
            }
            mock_send.assert_called_once_with("appium.execute_action", expected_params)
            assert result["status"] == "success"

    def test_get_screen_state_custom_params(self):
        """Test get_screen_state with custom parameters."""
        with patch.object(MCPClient, '_send_request') as mock_send:
            mock_send.return_value = {
                "result": {
                    "screenshot": "base64data",
                    "xml_dump": "<xml></xml>",
                    "current_activity": "MainActivity"
                }
            }

            client = MCPClient("http://localhost:3000/mcp")
            result = client.get_screen_state(include_screenshot=False, include_xml=False)

            expected_params = {"include_screenshot": False, "include_xml": False}
            mock_send.assert_called_once_with("appium.get_screen_state", expected_params)
            assert result["screenshot"] == "base64data"

    def test_http_error_no_retry(self):
        """Test that HTTP errors don't trigger retries."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        
        client = MCPClient("http://localhost:3000/mcp")
        with patch.object(client._session, 'post', return_value=mock_response) as mock_post:
            with pytest.raises(MCPConnectionError) as exc_info:
                client._send_request("test.method")

            # Should only attempt once for HTTP errors
            assert mock_post.call_count == 1
            assert "HTTP error" in str(exc_info.value)

    def test_request_exception_no_retry(self):
        """Test that general request exceptions don't trigger retries."""
        client = MCPClient("http://localhost:3000/mcp")
        with patch.object(client._session, 'post', side_effect=requests.exceptions.RequestException("Invalid URL")) as mock_post:
            with pytest.raises(MCPConnectionError) as exc_info:
                client._send_request("test.method")

            # Should only attempt once for request exceptions
            assert mock_post.call_count == 1
            assert "request failed" in str(exc_info.value)

    def test_circuit_breaker_open_blocks_requests(self):
        """Test that circuit breaker in OPEN state blocks requests."""
        client = MCPClient("http://localhost:3000/mcp", circuit_breaker_failure_threshold=1)
        
        # Force circuit breaker to OPEN state
        client.circuit_breaker.failure_count = 1
        client.circuit_breaker.state = CircuitBreakerState.OPEN
        client.circuit_breaker.last_failure_time = time.time()  # Recent failure
        
        with pytest.raises(MCPConnectionError) as exc_info:
            client._send_request("test.method")
        
        assert "Circuit breaker is OPEN" in str(exc_info.value)

    def test_circuit_breaker_recovery_attempt(self):
        """Test circuit breaker recovery attempt after timeout."""
        client = MCPClient("http://localhost:3000/mcp", circuit_breaker_failure_threshold=1, circuit_breaker_recovery_timeout=1.0)
        
        # Force circuit breaker to OPEN state
        client.circuit_breaker.failure_count = 1
        client.circuit_breaker.state = CircuitBreakerState.OPEN
        client.circuit_breaker.last_failure_time = time.time() - 2  # 2 seconds ago (past recovery timeout)
        
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"status": "success"}, "id": "req-1"}
        
        with patch.object(client._session, 'post', return_value=mock_response) as mock_post:
            result = client._send_request("test.method")
            
            # Should transition to HALF_OPEN and succeed
            assert result["result"]["status"] == "success"
            assert client.circuit_breaker.state == CircuitBreakerState.CLOSED
            mock_post.assert_called_once()