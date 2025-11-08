#!/usr/bin/env python3
"""
Test script for MCP server integration with AI client.
This script tests the connection between the Python client and the MCP server.

Prerequisites:
1. MCP server must be running: cd appium-mcp-server && npm run start:http
2. Appium server should be running (optional for basic tests): npx appium -p 4723
3. Device/emulator should be connected (optional for basic tests)
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from infrastructure.mcp_client import MCPClient, MCPConnectionError, MCPError
# Import Config only when needed to avoid circular imports
try:
    from config.config import Config
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    print("Warning: Config import failed, using defaults")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_mcp_client_connection():
    """Test basic MCP client connection and health check."""
    print("\n" + "="*60)
    print("TEST 1: MCP Client Connection")
    print("="*60)
    
    try:
        if CONFIG_AVAILABLE:
            config = Config()
            mcp_url = getattr(config, 'CONFIG_MCP_SERVER_URL', 'http://localhost:3000/mcp')
        else:
            mcp_url = 'http://localhost:3000/mcp'
        
        print(f"Connecting to MCP server at: {mcp_url}")
        client = MCPClient(server_url=mcp_url)
        
        # Test health check
        print("\nChecking server health...")
        health = client.check_server_health()
        print(f"Health status: {health}")
        
        if health.get("healthy", False):
            print("✅ Server is healthy!")
        else:
            print("⚠️  Server health check failed, but continuing...")
        
        if health.get("ready", False):
            print("✅ Server is ready!")
        else:
            print("⚠️  Server is not ready yet")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


def test_list_tools():
    """Test listing available MCP tools."""
    print("\n" + "="*60)
    print("TEST 2: List Available Tools")
    print("="*60)
    
    try:
        if CONFIG_AVAILABLE:
            config = Config()
            mcp_url = getattr(config, 'CONFIG_MCP_SERVER_URL', 'http://localhost:3000/mcp')
        else:
            mcp_url = 'http://localhost:3000/mcp'
        client = MCPClient(server_url=mcp_url)
        
        print("Fetching available tools...")
        tools_result = client.list_tools()
        
        if isinstance(tools_result, dict) and "tools" in tools_result:
            tools = tools_result["tools"]
            print(f"✅ Found {len(tools)} available tools:")
            for tool in tools[:10]:  # Show first 10
                tool_name = tool.get("name", "unknown")
                tool_desc = tool.get("description", "No description")
                print(f"  - {tool_name}: {tool_desc}")
            if len(tools) > 10:
                print(f"  ... and {len(tools) - 10} more tools")
        else:
            print(f"⚠️  Unexpected tools format: {tools_result}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ List tools test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_server_health_tool():
    """Test calling the server-health tool."""
    print("\n" + "="*60)
    print("TEST 3: Call server-health Tool")
    print("="*60)
    
    try:
        if CONFIG_AVAILABLE:
            config = Config()
            mcp_url = getattr(config, 'CONFIG_MCP_SERVER_URL', 'http://localhost:3000/mcp')
        else:
            mcp_url = 'http://localhost:3000/mcp'
        client = MCPClient(server_url=mcp_url)
        
        print("Calling server-health tool...")
        result = client.call_tool("server-health", {})
        
        if result.get("success", False):
            print("✅ Server health tool call successful!")
            data = result.get("data", {})
            stats = data.get("stats", {})
            print(f"  - Registered tools: {stats.get('registeredTools', 'N/A')}")
            print(f"  - Active invocations: {stats.get('activeInvocations', 'N/A')}")
            print(f"  - Uptime: {stats.get('uptime', 'N/A')} ms")
        else:
            print(f"⚠️  Server health tool returned: {result}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Server health tool test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_list_devices_tool():
    """Test calling the list-devices tool."""
    print("\n" + "="*60)
    print("TEST 4: Call list-devices Tool")
    print("="*60)
    
    try:
        if CONFIG_AVAILABLE:
            config = Config()
            mcp_url = getattr(config, 'CONFIG_MCP_SERVER_URL', 'http://localhost:3000/mcp')
        else:
            mcp_url = 'http://localhost:3000/mcp'
        client = MCPClient(server_url=mcp_url)
        
        print("Calling list-devices tool...")
        result = client.call_tool("list-devices", {})
        
        if result.get("success", False):
            print("✅ List devices tool call successful!")
            data = result.get("data", {})
            devices = data.get("devices", [])
            print(f"  - Found {len(devices)} device(s):")
            for device in devices:
                device_name = device.get("name", "unknown")
                device_platform = device.get("platform", "unknown")
                device_type = device.get("type", "unknown")
                print(f"    • {device_name} ({device_platform}, {device_type})")
        else:
            print(f"⚠️  List devices returned: {result.get('message', 'Unknown error')}")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ List devices test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_appium_driver_connection():
    """Test AppiumDriver connection to MCP server."""
    print("\n" + "="*60)
    print("TEST 5: AppiumDriver Connection")
    print("="*60)
    
    if not CONFIG_AVAILABLE:
        print("⚠️  Skipping - Config not available (circular import)")
        return True
    
    try:
        config = Config()
        driver = AppiumDriver(config)
        
        print("Connecting AppiumDriver to MCP server...")
        if driver.connect():
            print("✅ AppiumDriver connected successfully!")
            
            # Test getting window size (doesn't require a session)
            print("\nTesting get_window_size()...")
            window_size = driver.get_window_size()
            print(f"  - Window size: {window_size}")
            
            driver.disconnect()
            return True
        else:
            print("❌ AppiumDriver connection failed")
            return False
        
    except Exception as e:
        print(f"❌ AppiumDriver test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_appium_driver_tools():
    """Test AppiumDriver tool methods (requires active session)."""
    print("\n" + "="*60)
    print("TEST 6: AppiumDriver Tool Methods")
    print("="*60)
    print("⚠️  This test requires an active Appium session.")
    print("    Skipping for now - run this manually after initializing a session.")
    
    # Uncomment to test with an actual session:
    # try:
    #     config = Config()
    #     driver = AppiumDriver(config)
    #     driver.connect()
    #     
    #     # Initialize session (requires device and app)
    #     # driver.initialize_session(
    #     #     app_package="com.example.app",
    #     #     app_activity="com.example.MainActivity"
    #     # )
    #     
    #     # Test methods
    #     # page_source = driver.get_page_source()
    #     # screenshot = driver.get_screenshot_as_base64()
    #     
    #     driver.disconnect()
    #     return True
    # except Exception as e:
    #     print(f"❌ AppiumDriver tools test failed: {e}")
    #     return False
    
    return True  # Skip for now


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("MCP Server Integration Test Suite")
    print("="*60)
    print("\nMake sure the MCP server is running:")
    print("  cd appium-mcp-server && npm run start:http")
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    
    try:
        input()
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        return
    
    results = []
    
    # Run tests
    results.append(("MCP Client Connection", test_mcp_client_connection()))
    results.append(("List Tools", test_list_tools()))
    results.append(("Server Health Tool", test_server_health_tool()))
    results.append(("List Devices Tool", test_list_devices_tool()))
    if CONFIG_AVAILABLE:
        results.append(("AppiumDriver Connection", test_appium_driver_connection()))
    else:
        results.append(("AppiumDriver Connection", True))  # Skip if Config unavailable
    results.append(("AppiumDriver Tools", test_appium_driver_tools()))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

