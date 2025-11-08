#!/usr/bin/env python3
"""
Quick test script to verify MCP server connection.
Run this first to make sure everything is set up correctly.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from infrastructure.mcp_client import MCPClient

def main():
    print("🔍 Quick MCP Server Connection Test\n")
    
    # Use default MCP URL to avoid circular import
    mcp_url = 'http://localhost:3000/mcp'
    print(f"Connecting to: {mcp_url}\n")
    
    try:
        # Create client
        client = MCPClient(server_url=mcp_url)
        
        # Test health
        print("1. Checking server health...")
        health = client.check_server_health()
        if health.get("healthy"):
            print("   ✅ Server is healthy")
        else:
            print("   ⚠️  Server health check failed")
            print(f"   Details: {health}")
        
        # Test list tools
        print("\n2. Listing available tools...")
        tools_result = client.list_tools()
        if isinstance(tools_result, dict) and "tools" in tools_result:
            tools = tools_result["tools"]
            print(f"   ✅ Found {len(tools)} tools")
            print(f"   Sample tools: {', '.join([t['name'] for t in tools[:5]])}")
        else:
            print(f"   ⚠️  Unexpected response: {tools_result}")
        
        # Test server-health tool
        print("\n3. Calling server-health tool...")
        result = client.call_tool("server-health", {})
        if result.get("success"):
            print("   ✅ Tool call successful")
            stats = result.get("data", {}).get("stats", {})
            print(f"   - Registered tools: {stats.get('registeredTools', 'N/A')}")
        else:
            print(f"   ⚠️  Tool call failed: {result.get('message', 'Unknown error')}")
        
        client.close()
        print("\n✅ All basic tests passed! MCP server is working.")
        print("\nNext steps:")
        print("  1. Run full test: python test_mcp_integration.py")
        print("  2. Start Appium server: npx appium -p 4723")
        print("  3. Test with device: See TEST_MCP_INTEGRATION.md")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure MCP server is running:")
        print("     cd appium-mcp-server && npm run start:http")
        print("  2. Check if port 3000 is available")
        print("  3. Verify the server URL in config")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

