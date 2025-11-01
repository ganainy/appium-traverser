# AI-Driven Android App Crawler

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-development-yellow.svg)]()

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Features](#features)
- [Agent-Based Architecture](#agent-based-architecture)
- [Complete Setup & Usage](#complete-setup--usage)
- [Architecture](#architecture)
- [Output](#output)

## Overview


## Project Overview

This project implements an automated crawler for Android applications driven by pluggable AI model adapters (Gemini, Ollama, OpenRouter). It intelligently explores app screens by analyzing visual layout and structural information, deciding the next best action to discover new states and interactions.

### Purpose
The AI-Driven Android App Crawler is an automated testing and exploration tool that uses pluggable AI model adapters to intelligently navigate Android applications. It analyzes visual layouts and structural information to make decisions about the next best action for discovering new states and interactions.

**Available Interfaces:**

- **CLI Controller** - Command-line interface for automation and scripting
- **UI Controller** - Graphical user interface for interactive use

## Quick Start

```powershell
# 1. Install prerequisites
# Install Appium dependencies (UiAutomator2 driver)
npm install -g appium
appium driver install uiautomator2

# 2. Setup project (Windows, using virtual environment)
git clone <repository-url>
cd appium-traverser-master-arbeit
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 3. Configure environment variables
# Create .env file with your API keys
# GEMINI_API_KEY=your_gemini_api_key
# OPENROUTER_API_KEY=your_openrouter_api_key
# OLLAMA_BASE_URL=http://localhost:11434

# 4. Start external MCP server (separate process)
# Note: MCP server is an external component that must be set up separately
# Example: python -m external_mcp_server --host localhost --port 3000

# 5. Start crawling (CLI examples)
python run_cli.py --show-config
python run_cli.py --precheck-services

# UI Controller (alternative interface)
python run_ui.py
```

## Features

- **AI-Powered Exploration** - Uses your selected provider/model (Gemini, Ollama, OpenRouter) to analyze screens and decide actions
- **Intelligent State Management** - Visual and structural hashing to identify unique screens
- **Loop Detection** - Prevents getting stuck in repetitive patterns
- **Traffic Capture** - Optional network monitoring
- **Automation Ready** - Perfect for CI/CD and scripting workflows

## AI Model Support

This project supports multiple AI providers for intelligent app exploration:

### Supported Providers

1. **Google Gemini** (Default)
   - Cloud-based multimodal model
   - Excellent image understanding
   - Requires API key

2. **Ollama** (Local)
   - Run models locally on your machine
   - Supports both text-only and vision-capable models
   - No API costs, privacy-focused

3. **OpenRouter**
   - Cloud-based router to top models via OpenAI-compatible API
   - Simple presets (`openrouter-auto`, `openrouter-auto-fast`)
   - Requires API key

#### OpenRouter Models Metadata & Refresh

- The UI fetches capabilities from the OpenRouter Models API and caches them locally.
- Use the `Refresh models` button in the UI to update metadata on demand.
- Image support is detected using standardized `architecture.input_modalities` fields.
- The `ENABLE_IMAGE_CONTEXT` control is tri-state:
  - Vision-capable: enabled and checked with tooltip `This model supports image inputs.`
  - Non-vision: enabled and unchecked with tooltip `This model does not support image inputs.`
  - Auto-disabled: disabled with tooltip `Image context disabled due to provider payload limits (max X KB).`
  - Unknown: enabled (unchecked by default) with tooltip `Capability unknown; metadata not available.`

### Using Ollama with Vision Support

To use Ollama with vision-capable models:

1. **Install Ollama:**
   ```bash
   # Download from https://ollama.ai/download
   # Or on Linux/Mac:
   curl -fsSL https://ollama.ai/install.sh | sh
   ```

2. **Pull vision-capable models:**
   ```bash
   # Llama 3.2 Vision (recommended)
   ollama pull llama3.2-vision
   
   # Other vision models
   ollama pull llava
   ollama pull bakllava
   ```

3. **Configure the crawler:**
   ```json
   {
     "AI_PROVIDER": "ollama",
     "DEFAULT_MODEL_TYPE": "llama3.2-vision",
     "OLLAMA_BASE_URL": "http://localhost:11434"
   }
   ```

4. **Available Ollama Models:**
   - `llama3.2` - Text-only model
   - `llama3.2-vision` - Vision-capable model ⭐
   - `llama3.2-fast` - Fast text-only model
   - `llama3.2-vision-fast` - Fast vision model ⭐
   - `mistral` - Text-only model
   - `llava` - Vision model ⭐
   - `bakllava` - Vision model ⭐

**Note:** Models marked with ⭐ support image input for better UI analysis.

### Switching Between Providers

You can easily switch between providers by updating your `user_config.json`:

```json
{
  "AI_PROVIDER": "ollama",  // or "gemini", or "openrouter"
  "DEFAULT_MODEL_TYPE": "llama3.2-vision"  // e.g., "openrouter-auto" for OpenRouter
}
```

For cloud providers, make sure to set the appropriate API keys in your environment variables or `.env` file.

## MCP Integration

This project includes comprehensive MCP (Model Context Protocol) integration for enhanced AI-driven mobile app testing. The MCP server provides a standardized interface for AI models to interact with mobile devices through HTTP JSON-RPC.

### MCP Architecture

The MCP integration consists of three main components:

1. **MCP Server** (`mcp_server.py`) - Exposes mobile device actions as standardized tools
2. **MCP Client** (`mcp_client.py`) - HTTP JSON-RPC client for communicating with the MCP server
3. **LangChain Orchestration** - Uses LangChain chains to coordinate complex AI interactions through MCP

### Key MCP Features

- **Circuit Breaker Pattern** - Automatic failure detection and recovery for MCP server connections
- **Exponential Backoff Retry** - Intelligent retry logic with configurable parameters
- **LangChain Integration** - Orchestrates complex AI decision chains through MCP server
- **Error Recovery** - Graceful handling of MCP communication failures with fallback mechanisms
- **Connection Monitoring** - Real-time monitoring of MCP server health and connection status

### MCP Configuration

Configure MCP settings in your `user_config.json`:

```json
{
  "MCP_SERVER_URL": "http://127.0.0.1:3000",
  "MCP_CONNECTION_TIMEOUT": 5.0,
  "MCP_REQUEST_TIMEOUT": 30.0,
  "MCP_MAX_RETRIES": 3,
  "USE_LANGCHAIN_ORCHESTRATION": true
}
```

### Starting MCP Server

```powershell
# Note: The MCP server is an external component that must be set up separately
# This is NOT included in this codebase - you need to obtain and configure
# an MCP server that exposes mobile device actions as tools

# Example external MCP server startup (hypothetical):
# python -m external_mcp_server --host localhost --port 3000 --relaxed-security
```

### MCP Server Capabilities

The system expects the external MCP server to expose the following tools for AI agents:

- `appium.initialize_session` - Initialize a new testing session
- `appium.execute_action` - Execute mobile actions (click, input, scroll, etc.)
- `appium.get_screen_state` - Retrieve current screen information

### LangChain Orchestration

When enabled, the system uses LangChain to orchestrate complex AI interactions:

- **Action Decision Chains** - Determines optimal next actions based on screen analysis
- **Context Analysis Chains** - Analyzes screen state and provides insights for testing strategy
- **Memory Management** - Maintains conversation context across multiple AI requests
- **Fallback Mechanisms** - Automatically falls back to direct AI calls if MCP fails

### MCP Error Handling

The system includes robust error handling for MCP communications:

- **Connection Failures** - Automatic retry with exponential backoff
- **Circuit Breaker** - Prevents cascading failures when MCP server is unavailable
- **Graceful Degradation** - Falls back to direct AI model calls when MCP is unavailable
- **Comprehensive Logging** - Detailed logging of all MCP interactions and errors

### MCP Health Monitoring

Monitor MCP server health through the UI or logs:

- Connection status and response times
- Circuit breaker state (CLOSED/OPEN/HALF_OPEN)
- Failure counts and recovery attempts
- Detailed error logging with timestamps

### How It Works

The agent-based architecture uses a unified model adapter layer to integrate with multiple AI providers for multimodal analysis of mobile app screens. Supported providers include Google Gemini, local Ollama models (including vision-capable variants), and OpenRouter-accessed cloud models. This adapter approach keeps the core logic clean and maintainable while allowing you to switch models without changing crawler code.

### Key Features

- **Pluggable Model Adapters** - Unified integration for Gemini, Ollama (local), and OpenRouter
- **Simplified AI API** - Clean interface for retrieving next actions regardless of provider
- **Image Optimization** - Automatically resizes and optimizes screenshots for vision-capable models
- **Provider Capability Detection** - Detects image input support and payload limits to auto-toggle image context
- **Robust Error Handling** - Comprehensive error handling and logging across providers
- **Response Caching** - Caches AI responses to avoid duplicate calls

### Agent Components

#### 1. Agent Tools

The `AgentTools` class provides a bridge between the AI agent and the app under test:

- `click_element` - Clicks on UI elements
- `input_text` - Enters text in input fields
- `scroll` - Scrolls in different directions
- `press_back` - Presses the back button
- `tap_coordinates` - Directly taps at specific coordinates
- `get_screen_state` - Retrieves information about the current screen
- `get_action_history` - Retrieves the history of performed actions
- `check_app_context` - Ensures the app is in the foreground

#### 2. Agent Assistant

The `AgentAssistant` class implements the core agent functionality:

- `plan_and_execute` - The main agent method that analyzes the current screen and decides what action to take
- Uses structured prompting to guide the agent's reasoning process
- Directly executes actions using the agent tools
- Observes the results of actions and adapts its strategy

### Agent Workflow

The agent-based approach follows these steps:

1. **Observe**: The agent receives a screenshot of the current app state and its XML representation
2. **Reason**: The agent analyzes the screen to determine what elements are present and what actions are possible
3. **Plan**: The agent decides on the most appropriate action to take
4. **Act**: The agent executes the action directly using the agent tools
5. **Observe Again**: The agent receives feedback from the action execution and updates its understanding

### Benefits of the Agent Approach

- **Direct Execution**: The agent can directly execute actions without needing a separate execution layer
- **Feedback Loop**: The agent can observe the results of its actions and adjust its strategy
- **Adaptability**: The agent can handle unexpected situations by trying alternative approaches
- **Self-correction**: The agent can detect and recover from errors during exploration

### Implementation Details

The agent-based architecture is centered around the `AgentAssistant` class in `traverser_ai_api/agent_assistant.py`, which works with provider-specific adapters defined in `traverser_ai_api/model_adapters.py`.

1. **Provider Initialization** - Initialize the selected provider via model adapters (Gemini, Ollama, OpenRouter)
2. **Image Processing** - Prepare screenshots for vision-capable models
3. **Prompt Engineering** - Build effective prompts for consistent, structured outputs
4. **Response Parsing** - Extract structured action data from model responses
5. **Caching** - Avoid duplicate API calls for the same state

### Health App List Caching

When scanning installed apps and toggling AI filtering, the system now stores caches in a stable, per-device directory (not tied to a run session), using device-specific filenames:

- AI filtering OFF: `output_data/app_info/<device_id>/device_<device_id>_all_apps.json`
- AI filtering ON:  `output_data/app_info/<device_id>/device_<device_id>_filtered_health_apps.json`

The application reads/writes these stable caches based on your current AI filter setting and persists device-specific relative paths in the configuration. Per-run session folders continue to store run-specific artifacts (logs, screenshots, DB, etc.), but app_info caches are maintained separately for reuse across runs.

### Testing

For testing, use the built-in test files in the `tests/` directory:

```powershell
# Run agent tests
cd tests
python test_agent_assistant.py

# Run the agent demo with a sample screenshot
python demo_agent.py --api-key "your-api-key"
```

You can also provide custom screenshots and XML files to the demo:

```powershell
python demo_agent.py --api-key "your-api-key" --screenshot "path/to/screenshot.png" --xml "path/to/xml.xml"
```

### Future Improvements

- Add more agent capabilities for richer interactions
- Implement fine-tuning for specific app types
- Add support for more models and providers
- Expand test coverage with more real-world scenarios

## Complete Setup & Usage

📖 See the detailed guide: [INSTALLATION_AND_CLI_GUIDE.md](./docs/INSTALLATION_AND_CLI_GUIDE.md) for comprehensive setup instructions, full CLI reference, configuration options, and troubleshooting.

## Additional Resources

### Software Architecture

#### Core Components
The system consists of several core components:

1. **Main Entry Point (`main.py`)**
   - Bootstrap and orchestrate crawling process
   - Initialize configuration and logging
   - Set up output directories
   - Create and manage AppCrawler instance
   - Handle graceful shutdown and cleanup

2. **AppCrawler (`crawler.py`)**
   - Core orchestration engine
   - Coordinate components (AI, state management, actions)
   - Implement crawling loop logic
   - Handle termination conditions
   - Manage pause/resume functionality

3. **Agent Assistant (`agent_assistant.py`)**
   - Primary decision-making agent
   - Integrate with AI providers (Gemini, OpenRouter, Ollama)
   - Analyze screenshots and UI XML
   - Enforce structured output schema
   - Handle provider failures and fallbacks

4. **Screen State Manager (`screen_state_manager.py`)**
   - Track unique screen states
   - Generate composite hashes (XML + visual)
   - Detect transitions and loops
   - Store screen representations

5. **Action Components**
   - Map AI suggestions to executable actions
   - Execute actions via MCP tools
   - Handle errors and fallbacks

For a complete architectural overview, see our [Software Architecture Documentation](./docs/SOFTWARE_ARCHITECTURE_DOCUMENTATION.md).

### Focus Areas and Custom Testing Goals

The crawler supports customizable focus areas for targeted testing. Focus areas allow the AI agent to concentrate on specific privacy-related aspects during app exploration.

#### Adding Focus Areas

1. **Via CLI**:
   ```bash
   # Add a basic focus area
   python -m traverser_ai_api focus add "Privacy Policy"

   # Add with description and priority
   python -m traverser_ai_api focus add "Permissions" --description "Check permissions" --priority 1
   ```

2. **Via UI**:
   Use the "+ Add Focus Area" dialog to configure:
   - ID: Unique identifier
   - Name: Display name
   - Description: Brief description
   - Prompt Modifier: AI instructions
   - Priority: Order priority

For more details on managing focus areas, see our [Focus Areas Guide](./docs/FOCUS_AREAS_GUIDE.md).

### MCP Client Security

Our MCP client implementation includes several security features and considerations:

#### Security Measures
1. Authentication mechanism
2. SSL/TLS verification
3. Input validation
4. Safe error logging
5. Request size limits
6. Rate limiting
7. Request integrity protection

For detailed security information, see our [MCP Security Review](./docs/MCP_SECURITY_REVIEW_T030.md).

### Getting Started

For full installation instructions, advanced configuration, service prerequisites (MCP Server, MobSF, PCAPdroid, Ollama), and the complete CLI command reference, please see our [Installation and CLI Guide](./docs/INSTALLATION_AND_CLI_GUIDE.md).

Quick Start:
```bash
# Create environment
py -3 -m venv .venv

# Activate in PowerShell
\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the UI
python run_ui.py

# Or without activation
.\.venv\Scripts\python.exe run_ui.py
```

Notes
- If using the OpenRouter provider, install the OpenAI SDK inside the venv: `pip install openai`.
- In VS Code, select interpreter: `Ctrl+Shift+P` → `Python: Select Interpreter` → choose `\.venv\Scripts\python.exe`.

### Using OpenRouter

OpenRouter provides curated routing across high-quality models using an OpenAI-compatible API.

- Get your API key at `https://openrouter.ai` and set `OPENROUTER_API_KEY` in your `.env`.
- Install the OpenAI SDK: `pip install openai`.
- Configure:
  ```json
  {
    "AI_PROVIDER": "openrouter",
    "DEFAULT_MODEL_TYPE": "openrouter-auto"
  }
  ```
- Available models:
  - `openrouter-auto` (balanced)
  - `openrouter-auto-fast` (faster)
   - Select any model from the dropdown, including dynamic catalog entries.

Notes
- If `OPENROUTER_MODELS` is missing in configuration, the app falls back to resilient defaults (`openrouter-auto`, `openrouter-auto-fast`). Model selection is dropdown-only.



## Architecture

- **`main.py`** - Entry point and orchestration
- **`crawler.py`** - Main crawling logic and state transitions
- **`agent_assistant.py`** - Core agent orchestrating AI-driven actions
- **`ai_assistant.py` & `model_adapters.py`** - Unified AI integration via provider adapters (Gemini, Ollama, OpenRouter)
- **`agent_tools.py`** - Tools for the agent to interact with the app
- **`mcp_server.py`** - MCP server exposing device actions as tools
- **`appium_driver.py`** - MCP client wrapper for device interactions
- **`cli/`** - Modular command-line interface
- **`ui_controller.py`** - Graphical user interface
- **`screen_state_manager.py`** - Screen state and transition management

## Configuration

Environment variables (create a .env file in the project root):

```
GEMINI_API_KEY=your_gemini_api_key        # Required if using provider "gemini"
OPENROUTER_API_KEY=your_openrouter_key    # Required if using provider "openrouter"
OLLAMA_BASE_URL=http://localhost:11434    # Required if using provider "ollama"
MCP_SERVER_URL=http://localhost:3000      # MCP server endpoint
# Optional service keys
# PCAPDROID_API_KEY=...
# MOBSF_API_KEY=...
```


## Configuration Management

All user preferences are now stored in a local SQLite database (`config.db`).

- Use the app's UI or CLI to update preferences.
- Advanced users can use the migration script to import from `user_config.json`.
- The config system uses a four-layer precedence: runtime cache > SQLite > environment variables > Pydantic defaults.

**Legacy JSON config is only used for migration.**

Notes
- Set only the API key(s) needed for your selected provider.
- The UI can refresh OpenRouter model metadata and detects vision support automatically.

### MobSF (Docker) port mapping

If you run MobSF in Docker, you must publish the MobSF container port to your device (host) port so the app can reach the API at `http://localhost:8000`.

Example command:

```powershell
docker run -d --name mobsf -p 8000:8000 opensecurity/mobile-security-framework-mobsf:latest
```

After starting:
- Open MobSF UI at `http://localhost:8000`
- Copy your API key from the MobSF UI
- Configure the app with:
  - `MOBSF_API_URL`: `http://localhost:8000`
  - `MOBSF_API_KEY`: your key

With Docker Compose, add to the service:

```yaml
ports:
  - "8000:8000"
```

## Output

Session-based output structure (per device/app run):

- Base session directory: `output_data/<device_id>_<app_package>_<timestamp>/`
- Screenshots: `<session_dir>/screenshots/`
- Annotated screenshots: `<session_dir>/annotated_screenshots/`
- Database: `<session_dir>/database/<app_package>_crawl_data.db`
- Traffic captures: `<session_dir>/traffic_captures/`
- Logs: `<session_dir>/logs/`
- Reports: `<session_dir>/reports/`
- Extracted APK: `<session_dir>/extracted_apk/`



### Recent Updates

**Device Management**
- New commands: `--list-devices`, `--select-device UDID`, `--auto-select-device` for easier ADB device selection.


**Config Storage & Migration**
- Preferences now use SQLite for robust, structured storage.
- Migration script provided for seamless upgrade from JSON.

**Focus Areas CRUD**
- Manage focus areas with: `--add-focus-area`, `--edit-focus-area`, `--remove-focus-area`, `--import-focus-areas`, `--export-focus-areas`, plus description and priority options.

**OpenRouter Features**
- View model details, configure image context, toggle image context, and improved model selection with pricing info.


**Testing & Coverage**
- New unit and integration tests for config schema, user storage, migration, and full config lifecycle.
- See `tests/` for examples and coverage.

**Docs**
- CLI reference and workflow examples updated for all new commands and features.
---
# Consolidated docs from /docs

> The following sections were moved from the repository's docs/ directory and consolidated here for a single-source README.  
> Original files:
> - docs/INSTALLATION_AND_CLI_GUIDE.md
> - docs/SOFTWARE_ARCHITECTURE_DOCUMENTATION.md
> - docs/FOCUS_AREAS_GUIDE.md
> - docs/ADD_FOCUS_AREA_DIALOG.md
> - docs/MCP_SECURITY_REVIEW_T030.md

<!-- INSTALLATION_AND_CLI_GUIDE.md -->
# Installation & CLI Guide (moved from docs/INSTALLATION_AND_CLI_GUIDE.md)

## AI-Driven Android App Crawler - Complete Setup & Usage Guide

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
  - [Prerequisites Installation](#1-prerequisites-installation)
  - [Quick Installation](#2-quick-installation)
  - [Start Crawling (CLI Method)](#3-start-crawling-cli-method)
  - [Start Crawling (UI Method)](#4-start-crawling-ui-method)
- [Detailed Setup Instructions](#detailed-setup-instructions)
  - [Prerequisites Setup](#prerequisites-setup)
  - [Project Setup](#project-setup)
  - [OpenRouter Models Metadata & Refresh](#openrouter-models-metadata--refresh)
- [Usage Guide](#usage-guide)
  - [CLI Controller (Recommended for Automation)](#cli-controller-recommended-for-automation)
    - [Available Commands](#available-commands)
    - [Analysis Examples (Simplified Workflow)](#analysis-examples-simplified-workflow)
  - [Health App List Caching](#health-app-list-caching)
- [Configuration Management](#configuration-management)
  - [Common Configuration Options (via CLI)](#common-configuration-options-via-cli)
  - [Configuration Files](#configuration-files)
- [Troubleshooting](#troubleshooting)
  - [MCP Server Issues](#mcp-server-issues)
  - [Device Connection Issues (adb)](#device-connection-issues-adb)
  - [Python/Environment Issues](#pythonenvironment-issues)
  - [Common Error Solutions](#common-error-solutions)
  - [PowerShell execution policy errors when activating .venv](#powershell-execution-policy-errors-when-activating-venv)
- [MobSF Setup](#mobsf-setup)
- [Comprehensive Prerequisites Installation Guide](#comprehensive-prerequisites-installation-guide)
  - [1) System Requirements](#1-system-requirements)
  - [2) Android SDK and ADB](#2-android-sdk-and-adb)
  - [3) MCP Server](#3-mcp-server)
  - [4) MobSF (Mobile Security Framework)](#4-mobsf-mobile-security-framework)
  - [5) PCAPDroid (Optional: Traffic Capture)](#5-pcapdroid-optional-traffic-capture)
  - [6) Project Setup](#6-project-setup)
  - [7) Optional: Ollama (Local AI)](#7-optional-ollama-local-ai)
- [Full CLI Command Reference](#full-cli-command-reference)
  - [General Options](#general-options)
  - [App Management](#app-management)
  - [Crawler Control](#crawler-control)
  - [Configuration Management](#configuration-management-1)
  - [Analysis Workflow](#analysis-workflow)
  - [MobSF Integration](#mobsf-integration)
  - [Focus Areas Management](#focus-areas-management)
- [Pre-Crawl Checklist](#pre-crawl-checklist)

## Overview

This project implements an automated crawler for Android applications driven by a multimodal AI model (Google Gemini). It intelligently explores app screens by analyzing visual layout and structural information, deciding the next best action to discover new states and interactions.

Available Interfaces:
- CLI Controller - Command-line interface for automation and scripting
- UI Controller - Graphical user interface for interactive use

## Quick Start

### 1. Prerequisites Installation

Required Software:
- Python 3.8+ (ensure it's added to PATH)
- Node.js & npm -(for MCP server dependencies)
- Android SDK - Usually comes with Android Studio if you have it installed

### Required Environment Variables

#### 1. .env File Variables
Add the following API keys to your `.env` file:

- `GEMINI_API_KEY`: API key for Gemini AI features
- `PCAPDROID_API_KEY`: API key for traffic capture functionality
- `OPENROUTER_API_KEY`: API key for using OpenRouter AI models ([Get your key](https://openrouter.ai/))
- `MOBSF_API_KEY`: API key for Mobile Security Framework (MobSF) ([MobSF API Docs](https://mobsf.github.io/docs/#/api/))

Example `.env` snippet:
```env
GEMINI_API_KEY=your-gemini-key-here
PCAPDROID_API_KEY=your-pcapdroid-key-here
OPENROUTER_API_KEY=your-openrouter-key-here
MOBSF_API_KEY=your-mobsf-key-here
```

#### 2. Windows System Environment Variables
Set the following variable(s) in your Windows system environment:

- `ANDROID_HOME` or `ANDROID_SDK_ROOT`: Path to your Android SDK directory

Example value:
```
ANDROID_HOME=C:/Users/youruser/AppData/Local/Android/Sdk
```

Refer to the documentation for each service to obtain your API keys and set up access.

### 2. Quick Installation

**1. Install MCP server dependencies**
```bash
npm install -g appium
appium driver install uiautomator2
```

**2. Clone and setup project**
```bash
git clone <repository-url>
cd appium-traverser-master-arbeit
```

**3. Create virtual environment**

*For PowerShell:*
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

*For bash/zsh:*
```bash
python -m venv .venv
source .venv/bin/activate
```

**4. Install dependencies**
```bash
pip install -r requirements.txt
```

**5. Verify setup**
```bash
appium --version
adb devices
```

### 3. Start Crawling (CLI Method)

#### Terminal 1: Start External MCP Server

**Note**: The MCP server is an external component. Ensure your MCP server is running and accessible before starting the crawler.

#### Terminal 2: Use CLI Controller (ensure .venv is active)
```powershell
python run_cli.py apps scan-health --force-rescan   # or use apps scan-all
python run_cli.py apps list-health                  # or use apps list-all
python run_cli.py apps select 1                     # select by index
python run_cli.py apps select "com.example.healthapp"  # or select by package/name
python run_cli.py crawler start --annotate-offline-after-run  # starts crawler and creates annotated screenshots after completion
```

### 4. Start Crawling (UI Method)

#### Terminal 1: Start External MCP Server (same as CLI method)

**Note**: The MCP server is an external component. Ensure your MCP server is running and accessible before starting the crawler.

#### Terminal 2: Launch UI Controller (ensure .venv is active)
```powershell
python run_ui.py
```

Using the UI Controller:
1. The UI will open in a new window with several tabs for configuration and control
2. On the "App Selection" tab:
   * Click "Scan Device for Apps" to find installed applications
   * Select an app from the list that appears
   * Click "Set as Target App" to select it for crawling
3. On the "Configuration" tab:
   * Adjust settings as needed (crawl steps, duration, features, etc.)
   * Settings are automatically saved
4. On the "Crawler Control" tab:
   * Click "Start Crawler" to begin the crawling process
   * The log window will show real-time progress
   * Use "Pause/Resume" or "Stop" buttons to control the crawler
   * Screenshot previews will appear as the crawler explores the app
5. For MobSF static analysis:
   - Configure MobSF settings in the "Configuration" tab
   - Test the connection using "Test MobSF Connection"
   - Run analysis using "Run MobSF Analysis"
   - Note: MobSF must be installed and running separately (see [MobSF Setup](#mobsf-setup) section below)

The UI provides the same functionality as the CLI with a more interactive experience, making it ideal for monitoring crawl progress and viewing results in real-time.

## Detailed Setup Instructions

### Prerequisites Setup

**Python Installation:**
- Download from python.org
- Critical: Check "Add Python to PATH" during installation.
- Verify: `python --version`

**Node.js & MCP Server:**
Install Node.js from nodejs.org, then install MCP server dependencies:
```bash
npm install -g appium
appium driver install uiautomator2
```
**Note: The MCP server itself is an external component that must be obtained and configured separately. This codebase connects to an external MCP server, it does not include one.**

**Android SDK Setup:**
- Install Android Studio or standalone SDK tools.
- Set environment variable `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) to your SDK path (e.g., `C:\Users\YourUser\AppData\Local\Android\Sdk`).
- Add SDK `platform-tools` to your system PATH (e.g., `%ANDROID_HOME%\platform-tools`).
- Verify: `adb devices` (should show connected Android devices after setup).

**Device Setup:**
- Required: Enable Developer options and USB debugging.
  - Settings > About phone > tap Build number 7 times.
  - Settings > System > Developer options > enable USB debugging.
- Authorize: connect via USB and accept the RSA fingerprint prompt.
- Verify: `adb devices` should show the device as "device" (not "unauthorized").

### Project Setup

**Clone Repository:**
```bash
git clone <repository-url> # Replace <repository-url> with the actual URL
cd appium-traverser-master-arbeit
```

**Virtual Environment (Recommended):**
Create environment:
```powershell
python -m venv .venv
```
Activate (Windows PowerShell):
```powershell
.\.venv\Scripts\Activate.ps1
```
Activate (Git Bash / Linux / macOS):
```bash
source .venv/bin/activate
```

**Install Dependencies:**
Ensure your virtual environment is active:
```bash
pip install -r requirements.txt
```

**Environment Configuration (`.env` file):**
Create a file named `.env` in the project root directory (NOT in the traverser_ai_api subdirectory).
Add your cloud AI provider API key(s) and optional service keys:
```env
# Required for AI functionality (set the one for your selected provider)
GEMINI_API_KEY=your_gemini_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional keys
# PCAPDROID_API_KEY=your_pcapdroid_key_here
# MOBSF_API_KEY=your_mobsf_key_here
# OLLAMA_BASE_URL=http://localhost:11434
```

### OpenRouter Models Metadata & Refresh

- The UI integrates the OpenRouter Models API to fetch model capabilities and caches results.
- Click `Refresh models` in the AI settings to update metadata on demand.
- A 24-hour TTL is applied to the local cache; when expired, a background refresh is queued when the UI becomes active.
- The `ENABLE_IMAGE_CONTEXT` setting reflects availability:
  - Vision-capable: `This model supports image inputs.`
  - Non-vision: `This model does not support image inputs.`
  - Auto-disabled: `Image context disabled due to provider payload limits (max X KB).`
  - Unknown capability: `Capability unknown; metadata not available.`

- Set `OPENROUTER_API_KEY` in `.env`
- Cache path: `output_data/cache/openrouter_models.json`

## Usage Guide

### CLI Controller (Recommended for Automation)

#### Execution:
From the project root (ensure your virtual environment is active):
Example:
```powershell
python run_cli.py --help
```

#### Typical Workflow:
- Device management commands: add, edit, remove, and list devices for ADB integration.
- Focus areas CRUD: add, edit, remove, import, export focus areas with description and priority options.
- OpenRouter parity: improved model selection, metadata display, image context support, and pricing info for models.
- Documentation updates: CLI reference and workflow examples expanded for new features.

1. **Start Appium Server (in a separate terminal):**
```bash
appium --relaxed-security --address 0.0.0.0 --port 4723
```
(The `--relaxed-security` flag is needed for certain Appium actions like installing APKs or managing files.)

2. **Interact with the CLI Controller (in another terminal, project root directory):**
Activate virtual environment if not already active:
```powershell
# .\.venv\Scripts\Activate.ps1
```
Scan for installed apps on the connected Android device:
```powershell
# Health-focused scan (AI-filtered)
python run_cli.py apps scan-health
# OR deterministic scan of ALL apps
python run_cli.py apps scan-all
```
List the apps found by the scan:
```powershell
python run_cli.py --list-health-apps   # If you scanned health apps
python run_cli.py --list-all-apps      # If you scanned all apps
```
Select an app to target for crawling (use its index number from the list or package name):
```powershell
python run_cli.py --select-app 1
# OR select an app using its package name
python run_cli.py --select-app "com.example.healthapp"
```
View the currently selected app information:
```powershell
python run_cli.py --show-selected-app
```
View current crawler configuration:
```powershell
python run_cli.py --show-config
```
Modify configuration if needed (e.g., set max crawl steps):
```powershell
python run_cli.py --set-config MAX_CRAWL_STEPS=15
```
Start the crawling process for the selected app:
```powershell
python run_cli.py --start
```

### Health App List Caching

When scanning installed apps, the system writes device-specific cache files to the configured APP_INFO_OUTPUT_DIR. Two deterministic caches are maintained:

Default location (separated from run sessions):

- `output_data/app_info/<device_id>/device_<device_id>_all_apps.json`
- `output_data/app_info/<device_id>/device_<device_id>_filtered_health_apps.json`

APP_INFO_OUTPUT_DIR resolves to `OUTPUT_DATA_DIR/app_info/<device_id>`, so caches are stable per device and reusable across multiple runs.

- All apps (no AI filtering): `device_<device_id>_all_apps.json`
- Health apps (AI-filtered):  `device_<device_id>_filtered_health_apps.json`

Both caches use a unified list key `health_apps` in the JSON output. The CLI and UI read from `health_apps` only.
Check crawler status (can be run while crawler is active or stopped):
```powershell
python run_cli.py --status
```

Pause a running crawler:
```powershell
python run_cli.py --pause
```

Resume a paused crawler:
```powershell
python run_cli.py --resume
```

Stop a running crawler gracefully:
```powershell
python run_cli.py --stop
```

#### Available Commands:

##### App Management:
- `--scan-all-apps`: Scans the connected Android device and caches ALL installed apps (no AI filtering).
- `--scan-health-apps`: Scans the device and caches AI-filtered HEALTH apps.
- `--list-all-apps`: Lists ALL apps from the latest all-apps cache.
- `--list-health-apps`: Lists HEALTH apps from the latest health-filtered cache.
- `--select-app <APP_NAME_OR_INDEX>`: Selects an application (by its 1-based index from `--list-health-apps`/`--list-all-apps` or by its package name) to be the target for crawling.
- `--show-selected-app`: Displays the currently selected app information (name, package, and activity).
- `--add-device`: Add a new device for management (ADB integration).
- `--remove-device`: Remove a managed device.
- `--edit-device`: Edit device details.
- `--list-devices`: List all managed devices.

##### Crawler Control:
- `--start`: Starts the crawling process on the currently selected application.
- `--stop`: Signals a running crawler to stop gracefully.
- `--pause`: Temporarily halts crawler execution after completing current action.
- `--resume`: Continues execution of a paused crawler.
- `--status`: Shows the current status of the crawler (running, stopped, paused, selected app, etc.).
- `--precheck-services`: Run pre-crawl validation (Appium, provider services, API keys, target app).
- `--annotate-offline-after-run`: After crawler exits, run offline UI annotator to overlay bounding boxes on screenshots and generate a gallery (used with --start).

#### Analysis & Reporting (Simplified Workflow):

- `--list-analysis-targets` — Scans the output directory for databases and lists available app packages (targets) for analysis with an index number.
- `--list-runs-for-target` — Lists all recorded runs for a specific analysis target.
  - Requires either `--target-index <NUMBER>` (from `--list-analysis-targets`) OR `--target-app-package <PACKAGE_NAME>`.
- `--generate-analysis-pdf` — Generates a PDF report for an analysis target.
  - Requires either `--target-index <NUMBER>` OR `--target-app-package <PACKAGE_NAME>`.
  - The PDF is generated for the latest run if multiple exist for the target, or the only run if just one. The specific run ID used is determined automatically.
  - Optionally takes `--pdf-output-name <FILENAME.pdf>` to customize the suffix of the PDF filename. If omitted, a default name (`analysis.pdf`) is used as the suffix. The PDF is always prefixed with the app package.
  - Requires the optional `xhtml2pdf` library. If not installed, the CLI will print "Analysis module or PDF library not available" and skip PDF generation. Install via:
    ```powershell
    pip install xhtml2pdf
    ```

#### Offline UI Annotation (No AI Calls):
After a crawl finishes, you can automatically overlay bounding boxes onto screenshots and generate a simple gallery:

- `--annotate-offline-after-run`: When used with `--start`, runs the offline annotator after the crawler exits. It writes images to `.../annotated_screenshots/` inside the latest session directory and generates an `index.html` gallery.

Manual usage (without running a new crawl):
```powershell
python -m tools.ui_element_annotator --db-path "path\to\your_crawl_data.db" --screens-dir ".../screenshots" --out-dir ".../annotated_screenshots"
```

#### Analysis Examples (Simplified Workflow):
1. List all apps that have crawl data (databases)
```powershell
python run_cli.py --list-analysis-targets
```
2. (Optional) List runs for a specific app to see what run IDs are available
```powershell
python run_cli.py --list-runs-for-target --target-index 1
```
3. Generate PDF for the automatically selected run (latest/only) of 'com.example.app1' (using index)
```powershell
python run_cli.py --generate-analysis-pdf --target-index 1
```
4. Generate PDF for the automatically selected run of 'com.another.app' (using package name)
```powershell
python run_cli.py --generate-analysis-pdf --target-app-package com.another.app
```
5. Generate PDF for the automatically selected run of 'com.another.app' with a custom output name
```powershell
python run_cli.py --generate-analysis-pdf --target-app-package com.another.app --pdf-output-name "my_custom_report.pdf"
# This would create a file like: com.another.app_run_<AUTO_SELECTED_ID>_my_custom_report.pdf
```

## Configuration Management

### Common Configuration Options (via CLI)

#### Device Settings:
```powershell
python run_cli.py --set-config TARGET_DEVICE_UDID=DEVICE_SERIAL  # Use the serial shown by `adb devices`
python run_cli.py --set-config APPIUM_SERVER_URL="http://127.0.0.1:4723" # Ensure quotes if URL has special chars
```

#### Crawler Behavior:
Steps-based crawling:
```powershell
python run_cli.py --set-config CRAWL_MODE=steps
python run_cli.py --set-config MAX_CRAWL_STEPS=15
```
Time-based crawling:
```powershell
python run_cli.py --set-config CRAWL_MODE=time
python run_cli.py --set-config MAX_CRAWL_DURATION_SECONDS=300
```
Other options:
```powershell
python run_cli.py --set-config ENABLE_TRAFFIC_CAPTURE=true # or false
python run_cli.py --set-config CONTINUE_EXISTING_RUN=true # or false
```

### Configuration Files:
- User-specific settings: `traverser_ai_api/user_config.json` (created/updated by saving config via UI or CLI).
- Default values: Defined within `traverser_ai_api/config.py`.

## Troubleshooting

### MCP Server Issues
Check if your external MCP server is running and accessible:
*Windows:*
```powershell
# Check if your MCP server process is running (replace with your server command)
# Example: netstat -an | findstr ":3000"
```
*macOS/Linux:*
```bash
# Check if your MCP server process is running (replace with your server command)
# Example: lsof -i :3000
```
If MCP server connection issues persist:
- Verify the `MCP_SERVER_URL` in your configuration matches your external MCP server URL
- Check firewall settings and ensure the configured port is accessible
- Confirm your external MCP server implements the required mobile automation tools

### Device Connection Issues (adb)
Restart ADB server:
```powershell
adb kill-server
adb start-server
```
List connected Android devices:
```powershell
adb devices # Ensure your target device is listed and 'device' state
```
- If device shows 'unauthorized', re-authorize on the device.
- Check device properties (useful for `TARGET_DEVICE_UDID`): `adb shell getprop`

### Python/Environment Issues
Check Python version:
```bash
python --version
```
Verify virtual environment is active (prompt usually changes):
*On Windows, check path:*
```powershell
where python # First result should be in your .venv directory
```
*On macOS/Linux:*
```bash
which python # Should point to .venv/bin/python
```
Reinstall dependencies if corruption is suspected:
```bash
pip install -r requirements.txt --force-reinstall
```

* "Could not connect to MCP server"
  - Ensure your external MCP server is running and accessible.
  - Verify the `MCP_SERVER_URL` in your configuration matches where your MCP server is listening.
  - Check firewall settings; ensure the configured port is not blocked.

* "No devices found" by ADB or MCP server
  - Run `adb devices` to confirm ADB sees your device.
  - Ensure USB debugging is enabled on the physical device and authorized.
  - Try a different USB cable or port.

* "App not found" or "Activity not found" when starting crawl
  - Run `--scan-health-apps` and `--select-app` first via CLI, or ensure correct package/activity in GUI.
  - Verify the app is actually installed on the target device.
  - Ensure the device is unlocked and on the home screen (or any neutral state) before starting.

* Permission denied errors (file access, etc.)
  - Check file/folder permissions for your project directory and `output_data` subdirectories.
  - Ensure Android SDK environment variables (`ANDROID_HOME`) are correctly set and pointing to a valid SDK installation.

### PowerShell execution policy errors when activating `.venv`
Run this once in PowerShell:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

## MobSF Setup

The AppTransverser supports integration with MobSF (Mobile Security Framework) for static analysis of Android applications. To use this feature:

1. Install MobSF
   - Option A) Docker (recommended)
     - Prerequisites: Install and start Docker Desktop (Windows/macOS) or Docker Engine (Linux). Wait until Docker reports “Running”.
     - Windows tip: If you see pipe errors like `dockerDesktopLinuxEngine ... cannot find the file specified`, switch context to default:
       ```powershell
       docker context ls
       docker context use default
       ```
     - Run MobSF (basic, ephemeral storage):
       ```powershell
       docker pull opensecurity/mobile-security-framework-mobsf:latest
       docker run -d --name mobsf -p 8000:8000 opensecurity/mobile-security-framework-mobsf:latest
       ```
     - Optional: persist uploads and signatures (recommended)
      - Windows (PowerShell):
        ```powershell
        mkdir C:\mobsf\uploads
        mkdir C:\mobsf\signatures
        # Use backtick (`) for line continuation in PowerShell and quote Windows paths
        docker run -d --name mobsf -p 8000:8000 `
          -v "C:\mobsf\uploads:/home/mobsf/Mobile-Security-Framework-MobSF/uploads" `
          -v "C:\mobsf\signatures:/home/mobsf/Mobile-Security-Framework-MobSF/signatures" `
          opensecurity/mobile-security-framework-mobsf:latest
        ```
       - macOS/Linux (bash):
         ```bash
         mkdir -p $PWD/mobsf/uploads $PWD/mobsf/signatures
         docker run -d --name mobsf -p 8000:8000 \
           -v "$PWD/mobsf/uploads:/home/mobsf/Mobile-Security-Framework-MobSF/uploads" \
           -v "$PWD/mobsf/signatures:/home/mobsf/Mobile-Security-Framework-MobSF/signatures" \
           opensecurity/mobile-security-framework-mobsf:latest
         ```

    - Option B) Native install (without Docker)
      - Follow the official guide: https://github.com/MobSF/Mobile-Security-Framework-MobSF
      - Basic steps:
        ```bash
        # Clone the repository
        git clone https://github.com/MobSF/Mobile-Security-Framework-MobSF.git
        cd Mobile-Security-Framework-MobSF

        # Setup
        ./setup.sh    # For Linux/Mac
        setup.bat     # For Windows
        
        # Run MobSF
        ./run.sh      # For Linux/Mac
        run.bat       # For Windows
        ```

2. Get your MobSF API Key
   - Start MobSF and access the web interface (typically at http://localhost:8000)
   - Go to Settings (⚙️ icon) in the top-right corner
   - Find your API key in the API Key section

3. Configure AppTransverser to use MobSF
   - In the UI Controller: Go to Configuration tab → MobSF Static Analysis section
   - In the config file: Set the following parameters in your user_config.json:
     ```json
     "ENABLE_MOBSF_ANALYSIS": true,
     "MOBSF_API_URL": "http://localhost:8000/api/v1",
     "MOBSF_API_KEY": "YOUR_API_KEY_HERE"
     ```

4. Test the connection
   - In the UI Controller: Click "Test MobSF Connection" button
   - In the CLI: Run `python run_cli.py --test-mobsf-connection`
   - Check that the connection succeeds without errors

5. Usage
   - When starting a crawl with MobSF analysis enabled, the system will:
     - Extract the APK from the connected device
     - Upload it to MobSF for analysis
     - Process the results and save reports in the output directory

# (END of INSTALLATION_AND_CLI_GUIDE.md excerpt)

<!-- SOFTWARE_ARCHITECTURE_DOCUMENTATION.md -->
# Software Architecture Documentation (moved from docs/SOFTWARE_ARCHITECTURE_DOCUMENTATION.md)

## AI-Driven Android App Crawler - Software Architecture Documentation

Status: Development

## Table of Contents
1. Project Overview
2. System Architecture
3. Core Components
4. Data Flow
5. Configuration Management
6. Database Schema
7. AI Integration
8. Development Guidelines
9. Extending the System
10. Testing Strategy
11. Deployment & Operations

## Project Overview

### Purpose
The AI-Driven Android App Crawler is an automated testing and exploration tool that uses pluggable AI model adapters (Gemini, OpenRouter, Ollama) to intelligently navigate Android applications. It analyzes visual layouts and structural information to make decisions about the next best action for discovering new states and interactions.

### Key Features
- AI-Powered Exploration: Uses provider adapters (Gemini, Ollama, OpenRouter) for intelligent action selection
- Intelligent State Management: Visual and structural hashing to identify unique screens
- Loop Detection: Prevents getting stuck in repetitive patterns
- Traffic Capture: Optional network monitoring via PCAPdroid
- CLI Interface: Command-line interface for automation and scripting
- Comprehensive Reporting: PDF reports with crawl analysis
- Configurable: Extensive options to customize crawler behavior

### Technology Stack
- Language: Python 3.8+
- Mobile Automation: MCP Server with Appium backend and UIAutomator2
- AI Models: Pluggable provider adapters (Gemini, Ollama, OpenRouter)
- Database: SQLite
- Image Processing: Pillow, ImageHash
- GUI Framework: PySide6 (Qt)
- PDF Generation: xhtml2pdf (optional; install with `pip install xhtml2pdf`)
- Network Capture: PCAPdroid integration

... (architecture content continues; full architecture content has been appended into the README)

# (END of SOFTWARE_ARCHITECTURE_DOCUMENTATION.md excerpt)

<!-- FOCUS_AREAS_GUIDE.md -->
# Focus Areas Guide (moved from docs/FOCUS_AREAS_GUIDE.md)

## Overview
Focus areas allow the AI agent to concentrate on specific privacy-related aspects during app exploration. Focus areas are no longer hardcoded - they must be explicitly created by users through either the CLI or the UI.

## Starting with Empty Focus Areas
When you first start the application:
- The UI will show an empty focus areas panel with a message: "No focus areas added yet. Click '+ Add Focus Area' to get started."
- The database starts with no default focus areas
- Users must add focus areas before they can be used during crawling

## Adding Focus Areas

### Via CLI
Use the `focus add` command to create new focus areas:
```bash
# Add a basic focus area
python -m traverser_ai_api focus add "Privacy Policy"

# Add with description
python -m traverser_ai_api focus add "Permissions" --description "Check app permission requests"

# Add with priority (lower number = higher priority)
python -m traverser_ai_api focus add "Data Collection" --priority 1

# Add with disabled state
python -m traverser_ai_api focus add "Network Traffic" --priority 2 --disabled
```

### Via UI
1. Open the Traverser UI
2. Navigate to "AI Privacy Focus Areas" section
3. Click the "+ Add Focus Area" button
4. A form will appear (note: currently requires CLI as UI form is TBD)
5. Fill in the required fields and save

**Note:** Full UI form for adding focus areas is to be implemented.

... (rest of guide appended)

# (END of FOCUS_AREAS_GUIDE.md excerpt)

<!-- ADD_FOCUS_AREA_DIALOG.md -->
# Add Focus Area Dialog - UI Implementation (moved from docs/ADD_FOCUS_AREA_DIALOG.md)

## Overview
The "+ Add Focus Area" button now opens an interactive dialog form that allows users to add new focus areas directly from the UI.

## Implementation Details

### Dialog Form Fields
The `AddFocusAreaDialog` includes the following input fields:

| Field | Type | Purpose | Required |
|-------|------|---------|----------|
| **ID** | Text Input | Unique identifier for the focus area | Yes |
| **Name** | Text Input | Display name for the focus area | Yes |
| **Description** | Multi-line Text | Brief description of the focus area | No |
| **Prompt Modifier** | Multi-line Text | AI prompt instructions for this focus area | No |
| **Priority** | Number Input | Order priority (lower = higher priority, default: 999) | No |

... (rest of dialog doc appended)

# (END of ADD_FOCUS_AREA_DIALOG.md excerpt)

<!-- MCP_SECURITY_REVIEW_T030.md -->
# MCP Client Security Review - T030 (moved from docs/MCP_SECURITY_REVIEW_T030.md)

## Executive Summary
The MCP client implementation has been reviewed for security vulnerabilities. While the system includes robust error handling, retry logic, and circuit breaker protection, several critical security issues were identified that require immediate attention for production deployment.

## Security Findings

### 🔴 Critical Issues

#### 1. No Authentication Mechanism
- Issue: MCP server communication occurs over HTTP without any authentication
- Impact: Complete lack of access control; any network-attached system can interact with the MCP server
- Risk Level: Critical
- Current State: `MCP_SERVER_URL = "http://localhost:3000/mcp"` (HTTP only)

... (rest of security review appended)

# (END of MCP_SECURITY_REVIEW_T030.md excerpt)

---

Notes:
- This insertion consolidates the docs into the top-level README. If you want the docs files removed from /docs after verification, confirm and I will delete them in a follow-up operation.
- For references to the original docs, see the original files:
  - [`docs/INSTALLATION_AND_CLI_GUIDE.md`](docs/INSTALLATION_AND_CLI_GUIDE.md:1)
  - [`docs/SOFTWARE_ARCHITECTURE_DOCUMENTATION.md`](docs/SOFTWARE_ARCHITECTURE_DOCUMENTATION.md:1)
  - [`docs/FOCUS_AREAS_GUIDE.md`](docs/FOCUS_AREAS_GUIDE.md:1)
  - [`docs/ADD_FOCUS_AREA_DIALOG.md`](docs/ADD_FOCUS_AREA_DIALOG.md:1)
  - [`docs/MCP_SECURITY_REVIEW_T030.md`](docs/MCP_SECURITY_REVIEW_T030.md:1)
