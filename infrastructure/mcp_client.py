import json
import logging
import re
import time
from typing import Any, Dict, Optional
from enum import Enum

import requests
import requests.adapters

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreaker:
    """Simple circuit breaker implementation."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0, expected_exception=None):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception or Exception

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _record_success(self):
        """Record a successful operation."""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        logger.debug("Circuit breaker: Success recorded, state -> CLOSED")

    def _record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker: Failure threshold ({self.failure_threshold}) exceeded, state -> OPEN")
        else:
            logger.debug(f"Circuit breaker: Failure recorded ({self.failure_count}/{self.failure_threshold})")

    def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker."""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker: Recovery timeout elapsed, state -> HALF_OPEN")
            else:
                raise MCPCircuitOpenError("Circuit breaker is OPEN - MCP server unavailable")

        try:
            result = func(*args, **kwargs)
            # Record success for both HALF_OPEN (recovery) and CLOSED (normal operation) states
            if self.state == CircuitBreakerState.HALF_OPEN:
                self._record_success()
            elif self.state == CircuitBreakerState.CLOSED:
                # Reset failure count on successful operation even in closed state
                self.failure_count = 0
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise


class MCPClient:
    """HTTP JSON-RPC client for communicating with FastMCP server."""

    def __init__(self, server_url: str, connection_timeout: float = 5.0, request_timeout: float = 30.0, max_retries: int = 3,
                 circuit_breaker_failure_threshold: int = 5, circuit_breaker_recovery_timeout: float = 60.0):
        self.server_url = server_url.rstrip('/')
        self.connection_timeout = connection_timeout
        self.request_timeout = request_timeout
        self.max_retries = max_retries

        # Circuit breaker for handling persistent failures
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_failure_threshold,
            recovery_timeout=circuit_breaker_recovery_timeout,
            expected_exception=MCPConnectionError
        )

        # HTTP session for connection pooling and reuse
        self._session = requests.Session()

        # Configure connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,  # Number of connection pools
            pool_maxsize=20,      # Max connections per pool
            max_retries=0,        # Disable urllib3 retries, we handle our own
            pool_block=False      # Don't block when pool is full
        )
        self._session.mount('http://', adapter)
        self._session.mount('https://', adapter)

        # Cache for frequently accessed data
        self._circuit_breaker_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 5.0  # Cache circuit breaker state for 5 seconds

        self._request_id = 0

    def _get_next_id(self) -> str:
        """Generate next JSON-RPC request ID."""
        self._request_id += 1
        return f"req-{self._request_id}"

    def _send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send JSON-RPC request with retry logic and circuit breaker protection."""
        def _make_request() -> Dict[str, Any]:
            """Inner function that makes the actual HTTP request with retries."""
            request_data = {
                "jsonrpc": "2.0",
                "method": method,
                "id": self._get_next_id()
            }
            if params:
                request_data["params"] = params

            last_exception = None
            for attempt in range(self.max_retries + 1):  # +1 for initial attempt
                try:
                    logger.debug(f"Sending MCP request: {method} (attempt {attempt + 1})")
                    response = self._session.post(
                        self.server_url,
                        json=request_data,
                        headers={
                            'Content-Type': 'application/json',
                            'Accept': 'application/json'
                        },
                        timeout=(self.connection_timeout, self.request_timeout)
                    )
                    response.raise_for_status()

                    result = response.json()
                    if "error" in result:
                        logger.error(f"MCP error response: {result['error']}")
                        raise MCPError(result["error"])

                    logger.debug(f"MCP response received for {method}")
                    return result

                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    # Retry on transient network errors
                    last_exception = e
                    logger.warning(f"MCP request failed (attempt {attempt + 1}): {e}")
                    if attempt < self.max_retries:
                        # Improved exponential backoff with jitter and reasonable maximum
                        base_delay = min(2 ** attempt, 10)  # Cap at 10 seconds
                        jitter = time.time() % 1  # Add small random jitter
                        delay = base_delay + jitter
                        logger.debug(f"Retrying in {delay:.2f} seconds")
                        time.sleep(delay)
                    else:
                        raise MCPConnectionError(f"Failed to connect to MCP server after {self.max_retries + 1} attempts: {e}")
                except requests.exceptions.HTTPError as e:
                    # Don't retry on HTTP errors (4xx, 5xx) - they're not transient
                    logger.error(f"MCP HTTP error (no retry): {e}")
                    raise MCPConnectionError(f"MCP server returned HTTP error: {e}")
                except requests.exceptions.RequestException as e:
                    # Other request exceptions (like invalid URL, etc.) - don't retry
                    logger.error(f"MCP request error (no retry): {e}")
                    raise MCPConnectionError(f"MCP request failed: {e}")

            # This should never be reached, but just in case
            raise MCPConnectionError(f"Failed to connect to MCP server after {self.max_retries + 1} attempts: {last_exception}")

        # Use circuit breaker to protect against persistent failures
        return self.circuit_breaker.call(_make_request)

    def get_circuit_breaker_state(self) -> Dict[str, Any]:
        """Get the current state of the circuit breaker.
        
        Returns:
            Dictionary containing circuit breaker state information
        """
        # Check cache first
        current_time = time.time()
        if (self._circuit_breaker_cache and 
            current_time - self._cache_timestamp < self._cache_ttl):
            return self._circuit_breaker_cache
        
        # Compute fresh state
        recovery_time = None
        if self.circuit_breaker.last_failure_time and self.circuit_breaker.recovery_timeout:
            recovery_time = self.circuit_breaker.last_failure_time + self.circuit_breaker.recovery_timeout
        
        state = {
            "state": self.circuit_breaker.state.value,
            "failure_count": self.circuit_breaker.failure_count,
            "failure_threshold": self.circuit_breaker.failure_threshold,
            "recovery_timeout": self.circuit_breaker.recovery_timeout,
            "last_failure_time": self.circuit_breaker.last_failure_time,
            "recovery_time": recovery_time,
            "can_attempt_reset": self.circuit_breaker._should_attempt_reset() if self.circuit_breaker.state == CircuitBreakerState.OPEN else False
        }
        
        # Cache the result
        self._circuit_breaker_cache = state
        self._cache_timestamp = current_time
        
        return state

    def check_server_health(self) -> Dict[str, Any]:
        """Check MCP server health using HTTP endpoints.
        
        Returns:
            Dictionary with 'healthy' (bool), 'ready' (bool), and 'details' (dict)
        """
        result = {
            "healthy": False,
            "ready": False,
            "details": {}
        }
        
        try:
            # Check /health endpoint (liveness)
            health_url = f"{self.server_url.replace('/mcp', '')}/health"
            health_response = self._session.get(health_url, timeout=self.connection_timeout)
            if health_response.status_code == 200:
                result["healthy"] = True
                result["details"]["health"] = health_response.json()
                logger.debug(f"Server health check passed: {result['details']['health']}")
            else:
                logger.warning(f"Server health check returned HTTP {health_response.status_code}")
        except Exception as e:
            logger.warning(f"Server health check failed: {e}")
            result["details"]["health_error"] = str(e)
        
        try:
            # Check /ready endpoint (readiness)
            ready_url = f"{self.server_url.replace('/mcp', '')}/ready"
            ready_response = self._session.get(ready_url, timeout=self.connection_timeout)
            if ready_response.status_code == 200:
                result["ready"] = True
                result["details"]["ready"] = ready_response.json()
                logger.debug(f"Server readiness check passed: {result['details']['ready']}")
            elif ready_response.status_code == 503:
                logger.debug("Server is initializing (503 Service Unavailable)")
                result["details"]["ready_status"] = "initializing"
            else:
                logger.warning(f"Server readiness check returned HTTP {ready_response.status_code}")
        except Exception as e:
            logger.warning(f"Server readiness check failed: {e}")
            result["details"]["ready_error"] = str(e)
        
        return result

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Call an MCP tool by name with the provided arguments.
        
        Args:
            tool_name: Name of the MCP tool to call
            arguments: Optional dictionary of tool arguments
            
        Returns:
            Dictionary containing the tool result with 'success', 'message', 'data' fields
        """
        params = {
            "name": tool_name,
            "arguments": arguments or {}
        }
        
        response = self._send_request("tools/call", params)
        result = response.get("result", {})
        
        # Handle MCP response format - may have content array with text
        if isinstance(result, dict) and "content" in result:
            # Extract text from content array if present
            content = result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                text_content = content[0].get("text", "")
                # Try to parse JSON from text if it contains JSON
                if text_content and text_content.strip().startswith("{"):
                    try:
                        # Find JSON object in text
                        json_match = re.search(r'\{[\s\S]*\}', text_content)
                        if json_match:
                            parsed = json.loads(json_match.group(0))
                            return parsed
                    except (json.JSONDecodeError, AttributeError):
                        pass
                # If not JSON, return the text as message
                if not isinstance(result, dict) or "message" not in result:
                    return {
                        "success": True,
                        "message": text_content,
                        "data": result
                    }
        
        # Return result as-is if it's already in expected format
        return result

    def list_tools(self) -> Dict[str, Any]:
        """List all available MCP tools.
        
        Returns:
            Dictionary containing list of available tools
        """
        response = self._send_request("tools/list", {})
        return response.get("result", {})

    def close(self) -> None:
        """Close the HTTP session and clean up resources."""
        if hasattr(self, '_session'):
            self._session.close()
            logger.debug("MCP client session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit."""
        self.close()


class MCPError(Exception):
    """Base exception for MCP-related errors."""
    def __init__(self, error_data: Dict[str, Any]):
        self.code = error_data.get("code")
        self.message = error_data.get("message", "Unknown MCP error")
        self.data = error_data.get("data")
        super().__init__(f"MCP Error {self.code}: {self.message}")


class MCPConnectionError(Exception):
    """Raised when there is a connection issue with the MCP server."""
    pass

class MCPCircuitOpenError(Exception):
    """Raised when the MCP circuit breaker is open."""
    pass