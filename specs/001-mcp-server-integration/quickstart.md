# Quickstart: MCP Server Integration

## Prerequisites
- Python 3.8+
- Node.js 18+
- Appium MCP Server (FASTMCP)
- Android device or emulator
- All dependencies from requirements.txt

## Setup
1. Clone the repository and check out the `001-mcp-server-integration` branch.
2. Install Python and Node.js dependencies:
   ```sh
   pip install -r requirements.txt
   # (Install Node.js dependencies for MCP server as needed)
   ```
3. Start the MCP server (see MCP server README for details).
4. Configure the crawler to use the MCP server as the automation backend.

## Running a Crawl
1. Launch the crawler using the CLI or UI entrypoint.
2. The AI agent will decide actions and send them to the MCP server.
3. All device interactions will be routed through the MCP server; no direct Appium calls are made by the crawler.

## Migrating Existing Appium Code
- All removed direct Appium code is available in a git-ignored folder for reference if MCP server improvements are needed.

## Testing
- Run `pytest` to execute all unit and integration tests.
- Contract tests for MCP protocol compliance are included in the test suite.

## Documentation
- See the project README and architecture docs for more details on the MCP-first, agent-driven approach.
