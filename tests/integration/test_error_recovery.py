import pytest
import time
from unittest.mock import Mock, patch
import requests
from traverser_ai_api.mcp_client import MCPClient, MCPConnectionError, CircuitBreaker, CircuitBreakerState


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.server_url = "http://localhost:3000"
        self.client = MCPClient(
            server_url=self.server_url,
            max_retries=0,  # Disable retries for cleaner circuit breaker testing
            circuit_breaker_failure_threshold=3,
            circuit_breaker_recovery_timeout=2.0  # Short timeout for testing
        )

    @patch('requests.post')
    def test_circuit_breaker_closes_after_failures(self, mock_post):
        """Test that circuit breaker opens after failure threshold is exceeded."""
        # Mock persistent connection failures
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        # Make requests that should fail and trigger circuit breaker
        for i in range(3):
            with pytest.raises(MCPConnectionError):
                self.client._send_request("test.method")

        # Circuit breaker should now be open
        assert self.client.circuit_breaker.state == CircuitBreakerState.OPEN

        # Next request should fail fast without making HTTP call
        with pytest.raises(MCPConnectionError) as exc_info:
            self.client._send_request("test.method")

        assert "Circuit breaker is OPEN" in str(exc_info.value)
        # Should not have made another HTTP request
        assert mock_post.call_count == 3

    @patch('requests.post')
    def test_circuit_breaker_half_open_recovery(self, mock_post):
        """Test circuit breaker recovery through half-open state."""
        # First, force circuit breaker to open
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        for i in range(3):
            with pytest.raises(MCPConnectionError):
                self.client._send_request("test.method")

        assert self.client.circuit_breaker.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(2.1)

        # Mock successful response for recovery attempt
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-4"}
        mock_post.side_effect = None  # Clear side_effect
        mock_post.return_value = mock_response  # Set return_value

        # Next request should attempt recovery (half-open state)
        result = self.client._send_request("test.method")

        # Should have made the HTTP request and succeeded
        assert mock_post.call_count == 4  # 3 failures + 1 recovery attempt
        assert result == {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-4"}
        assert self.client.circuit_breaker.state == CircuitBreakerState.CLOSED

    @patch('requests.post')
    def test_circuit_breaker_failure_during_recovery(self, mock_post):
        """Test circuit breaker re-opens if recovery attempt fails."""
        # First, force circuit breaker to open
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        for i in range(3):
            with pytest.raises(MCPConnectionError):
                self.client._send_request("test.method")

        assert self.client.circuit_breaker.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(2.1)

        # Mock failure during recovery attempt
        mock_post.side_effect = requests.exceptions.ConnectionError("Still failing")

        # Recovery attempt should fail and circuit breaker should re-open
        with pytest.raises(MCPConnectionError):
            self.client._send_request("test.method")

        assert self.client.circuit_breaker.state == CircuitBreakerState.OPEN
        assert mock_post.call_count == 4  # 3 failures + 1 failed recovery

    @patch('requests.post')
    def test_circuit_breaker_allows_requests_when_closed(self, mock_post):
        """Test that circuit breaker allows normal operation when closed."""
        # Mock successful responses
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = [
            {"jsonrpc": "2.0", "result": {"status": "ok1"}, "id": "req-1"},
            {"jsonrpc": "2.0", "result": {"status": "ok2"}, "id": "req-2"},
            {"jsonrpc": "2.0", "result": {"status": "ok3"}, "id": "req-3"}
        ]
        mock_post.return_value = mock_response

        # Make multiple successful requests
        result1 = self.client._send_request("method1")
        result2 = self.client._send_request("method2")
        result3 = self.client._send_request("method3")

        # All should succeed and circuit breaker should remain closed
        assert result1["result"]["status"] == "ok1"
        assert result2["result"]["status"] == "ok2"
        assert result3["result"]["status"] == "ok3"
        assert self.client.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert self.client.circuit_breaker.failure_count == 0
        assert mock_post.call_count == 3

    @patch('requests.post')
    def test_circuit_breaker_resets_failure_count_on_success(self, mock_post):
        """Test that failure count resets to zero after successful requests."""
        # Mock alternating failures and successes
        mock_response_success = Mock()
        mock_response_success.raise_for_status.return_value = None
        mock_response_success.json.return_value = {"jsonrpc": "2.0", "result": {"status": "ok"}, "id": "req-3"}

        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Fail 1"),
            requests.exceptions.ConnectionError("Fail 2"),
            mock_response_success,  # Success resets counter
            requests.exceptions.ConnectionError("Fail 3"),  # Counter starts over
            requests.exceptions.ConnectionError("Fail 4"),
            requests.exceptions.ConnectionError("Fail 5"),  # Should open circuit
        ]

        # Two failures
        with pytest.raises(MCPConnectionError):
            self.client._send_request("fail1")
        with pytest.raises(MCPConnectionError):
            self.client._send_request("fail2")

        assert self.client.circuit_breaker.failure_count == 2
        assert self.client.circuit_breaker.state == CircuitBreakerState.CLOSED

        # Success resets counter
        result = self.client._send_request("success")
        assert result["result"]["status"] == "ok"
        assert self.client.circuit_breaker.failure_count == 0  # Should be reset

        # Two more failures
        with pytest.raises(MCPConnectionError):
            self.client._send_request("fail3")
        with pytest.raises(MCPConnectionError):
            self.client._send_request("fail4")

        assert self.client.circuit_breaker.failure_count == 2

        # Third failure should open circuit
        with pytest.raises(MCPConnectionError):
            self.client._send_request("fail5")

        assert self.client.circuit_breaker.state == CircuitBreakerState.OPEN

    def test_circuit_breaker_custom_configuration(self):
        """Test circuit breaker with custom configuration."""
        client = MCPClient(
            server_url=self.server_url,
            circuit_breaker_failure_threshold=10,
            circuit_breaker_recovery_timeout=120.0
        )

        assert client.circuit_breaker.failure_threshold == 10
        assert client.circuit_breaker.recovery_timeout == 120.0
        assert client.circuit_breaker.state == CircuitBreakerState.CLOSED
        assert client.circuit_breaker.failure_count == 0

    def test_circuit_breaker_no_fast_fail_during_half_open(self):
        """Test that circuit breaker doesn't fast-fail during half-open state."""
        # Create circuit breaker and force it to open
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        # Record failures to open circuit
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("test")))  # Always fails
        except:
            pass
        try:
            cb.call(lambda: (_ for _ in ()).throw(Exception("test")))  # Always fails
        except:
            pass

        assert cb.state == CircuitBreakerState.OPEN

        # Wait for recovery timeout
        time.sleep(0.2)

        # Mock a function that succeeds
        call_count = 0
        def succeeding_func():
            nonlocal call_count
            call_count += 1
            return "success"

        # Should allow the call and succeed
        result = cb.call(succeeding_func)
        assert result == "success"
        assert call_count == 1
        assert cb.state == CircuitBreakerState.CLOSED