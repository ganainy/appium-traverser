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

This project implements an automated crawler for Android applications driven by a multimodal AI model (Google Gemini). It intelligently explores app screens by analyzing visual layout and structural information, deciding the next best action to discover new states and interactions.

**Available Interfaces:**

- **CLI Controller** - Command-line interface for automation and scripting
- **UI Controller** - Graphical user interface for interactive use

## Quick Start

```powershell
# 1. Install prerequisites
npm install -g appium
appium driver install uiautomator2

# 2. Setup project
git clone <repository-url>
cd appium-traverser-vertiefung
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Start crawling
appium --relaxed-security  # Terminal 1

# CLI Controller (Terminal 2)
python traverser_ai_api/cli_controller.py --scan-apps --list-apps --select-app 1 --start

# OR UI Controller (Terminal 2)
python traverser_ai_api/ui_controller.py  # Opens graphical interface
```

## Features

- **AI-Powered Exploration** - Uses Google Gemini to analyze screens and decide actions
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

2. **DeepSeek**
   - Cloud-based model with vision capabilities
   - Cost-effective alternative
   - Requires API key

3. **Ollama** (Local)
   - Run models locally on your machine
   - Supports both text-only and vision-capable models
   - No API costs, privacy-focused

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
  "AI_PROVIDER": "ollama",  // or "gemini" or "deepseek"
  "DEFAULT_MODEL_TYPE": "llama3.2-vision"
}
```

For cloud providers, make sure to set the appropriate API keys in your environment variables or `.env` file.

### How It Works

The agent-based architecture uses Google Generative AI (Gemini) for multimodal analysis of mobile app screens, making intelligent decisions about what UI actions to take next. The implementation focuses on direct API integration with the Google Generative AI SDK, providing a cleaner and more maintainable codebase.

### Key Features

- **Direct Google Generative AI Integration** - Uses the official Google Generative AI Python SDK
- **Simplified API** - Clean interface for getting next actions from the AI model
- **Image Optimization** - Automatically resizes and optimizes screenshots for the model
- **Robust Error Handling** - Comprehensive error handling and logging
- **Response Caching** - Caches responses to avoid duplicate API calls

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

The agent-based architecture is centered around the `AgentAssistant` class in `traverser_ai_api/agent_assistant.py`. This class handles:

1. **Model Initialization** - Setting up the Google Generative AI model with appropriate configuration
2. **Image Processing** - Preparing screenshots for the model
3. **Prompt Engineering** - Building effective prompts for the model
4. **Response Parsing** - Extracting structured action data from model responses
5. **Caching** - Avoiding duplicate API calls for the same state

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

📖 **[See CONSOLIDATED_SETUP_GUIDE.md](./CONSOLIDATED_SETUP_GUIDE.md)** for comprehensive setup instructions, usage examples, configuration options, and troubleshooting.

## Architecture

- **`main.py`** - Entry point and orchestration
- **`crawler.py`** - Main crawling logic and state transitions
- **`agent_assistant.py`** - Google Generative AI integration using direct API
- **`agent_tools.py`** - Tools for the agent to interact with the app
- **`cli_controller.py`** - Command-line interface
- **`ui_controller.py`** - Graphical user interface
- **`screen_state_manager.py`** - Screen state and transition management

## Output

- **Screenshots:** `traverser_ai_api/output_data/screenshots/`
- **Database:** `traverser_ai_api/output_data/database_output/`
- **Traffic Captures:** `traverser_ai_api/output_data/traffic_captures/`
