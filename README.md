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

## Agent-Based Architecture

This branch implements a new agent-based architecture for the Android app crawler, replacing the previous LLM implementation with a more flexible and extensible agent model using Google Generative AI (Gemini).

### Agent Architecture

The agent-based architecture uses Google Generative AI (Gemini) for multimodal analysis of mobile app screens, making intelligent decisions about what UI actions to take next. The implementation focuses on direct API integration with the Google Generative AI SDK, providing a cleaner and more maintainable codebase.

### Key Features

- **Direct Google Generative AI Integration** - Uses the official Google Generative AI Python SDK
- **Simplified API** - Clean interface for getting next actions from the AI model
- **Image Optimization** - Automatically resizes and optimizes screenshots for the model
- **Robust Error Handling** - Comprehensive error handling and logging
- **Response Caching** - Caches responses to avoid duplicate API calls
- **Extensive Test Suite** - Comprehensive test coverage with mocks and integration tests

### Implementation Details

The agent-based architecture is centered around the `AgentAssistant` class in `traverser_ai_api/agent_assistant.py`. This class handles:

1. **Model Initialization** - Setting up the Google Generative AI model with appropriate configuration
2. **Image Processing** - Preparing screenshots for the model
3. **Prompt Engineering** - Building effective prompts for the model
4. **Response Parsing** - Extracting structured action data from model responses
5. **Caching** - Avoiding duplicate API calls for the same state

#### Key Components

- **Model Configuration** - Uses environment variables for API keys and configuration objects for model settings
- **Action Extraction** - Parses JSON from model responses to extract structured action data
- **Loop Detection** - Analyzes action history to detect and break out of loops
- **Image Optimization** - Resizes images to optimal dimensions for the model

### Getting Started with the Agent

#### Prerequisites

- Python 3.8+
- Google Generative AI API key (from [Google AI Studio](https://ai.google.dev/))
- Appium setup (as described in the Quick Start section)

#### Installation

1. Install the additional requirements:

   ```powershell
   pip install -r agent-requirements.txt
   ```

2. Set your Google API key:

   ```powershell
   $env:GOOGLE_API_KEY="your-api-key-here"
   ```

#### Testing and Demo

1. Run the test suite to verify the implementation:

   ```powershell
   .\run_agent_tests.ps1 -ApiKey "your-api-key-here"
   ```

   Or run specific tests:

   ```powershell
   .\run_agent_tests.ps1 -ApiKey "your-api-key-here" -Test "test_full_integration"
   ```

2. Try the demo with sample data:

   ```powershell
   .\run_agent_demo.ps1 -ApiKey "your-api-key-here"
   ```

   You can also provide custom screenshots and XML data:

   ```powershell
   .\run_agent_demo.ps1 -ApiKey "your-api-key-here" -Screenshot "path/to/screenshot.png" -Xml "path/to/xml.xml"
   ```

   Note: All test and demo files are located in the `tests/` directory. The root directory scripts automatically redirect to the actual implementation in the tests directory.

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
- **`cli_controller.py`** - Command-line interface
- **`ui_controller.py`** - Graphical user interface
- **`state_manager.py`** - Screen state and transition management

## Output

- **Screenshots:** `traverser_ai_api/output_data/screenshots/`
- **Database:** `traverser_ai_api/output_data/database_output/`
- **Traffic Captures:** `traverser_ai_api/output_data/traffic_captures/`
