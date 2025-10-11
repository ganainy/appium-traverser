# AI-Driven Android App Crawler

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-production-green.svg)]()

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Features](#features)
- [Agent-Based Architecture](#agent-based-architecture)
- [Complete Setup & Usage](#complete-setup--usage)
- [Architecture](#architecture)
- [Output](#output)

## Overview

This project implements an automated crawler for Android applications driven by pluggable AI model adapters (Gemini, Ollama, OpenRouter). It intelligently explores app screens by analyzing visual layout and structural information, deciding the next best action to discover new states and interactions.

**Available Interfaces:**

- **CLI Controller** - Command-line interface for automation and scripting
- **UI Controller** - Graphical user interface for interactive use

## Quick Start

```powershell
# 1. Install prerequisites
npm install -g appium
appium driver install uiautomator2

# 2. Setup project (Windows, using virtual environment)
git clone <repository-url>
cd appium-traverser-master-arbeit
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 3. Start crawling
appium --relaxed-security  # Terminal 1

# CLI Controller (Terminal 2, venv active)
python run_cli.py --scan-apps --list-apps --select-app 1 --start

# UI Controller (Terminal 2, venv active)
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

For full installation instructions, advanced configuration, service prerequisites (Appium, MobSF, PCAPdroid, Ollama), and the complete CLI command reference, please see:

- docs/INSTALLATION_AND_CLI_GUIDE.md

- Create the environment: `py -3 -m venv .venv`
- Activate in PowerShell: `\.venv\Scripts\Activate.ps1`
- Install deps: `pip install -r requirements.txt`
- Run the UI: `python run_ui.py`
- Without activation: `.\.venv\Scripts\python.exe run_ui.py`

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
- **`cli_controller.py`** - Command-line interface
- **`ui_controller.py`** - Graphical user interface
- **`screen_state_manager.py`** - Screen state and transition management

## Configuration

Environment variables (create a .env file in the project root):

```
GEMINI_API_KEY=your_gemini_api_key        # Required if using provider "gemini"
OPENROUTER_API_KEY=your_openrouter_key    # Required if using provider "openrouter"
OLLAMA_BASE_URL=http://localhost:11434    # Required if using provider "ollama"
# Optional service keys
# PCAPDROID_API_KEY=...
# MOBSF_API_KEY=...
```

Provider and model selection (user_config.json):

```json
{
  "AI_PROVIDER": "gemini",            
  "DEFAULT_MODEL_TYPE": "gemini-2.5-flash",  
  "ENABLE_IMAGE_CONTEXT": true,
  "OPENROUTER_SHOW_FREE_ONLY": false,
  "OUTPUT_DATA_DIR": "output_data"
}
```

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

- Base session directory: `traverser_ai_api/output_data/<device_id>_<app_package>_<timestamp>/`
- Screenshots: `<session_dir>/screenshots/`
- Annotated screenshots: `<session_dir>/annotated_screenshots/`
- Database: `<session_dir>/database/<app_package>_crawl_data.db`
- Traffic captures: `<session_dir>/traffic_captures/`
- Logs: `<session_dir>/logs/`
- Reports: `<session_dir>/reports/`
- Extracted APK: `<session_dir>/extracted_apk/`