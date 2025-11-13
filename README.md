# AI-Driven Android App Crawler

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-development-yellow.svg)]()

## Overview

An automated Android app testing tool powered by pluggable AI model adapters (Gemini, Ollama, OpenRouter). Intelligently explores applications by analyzing visual layouts and structural information to discover new states and interactions.

**Available Interfaces:**
- **CLI Controller** - Command-line interface for automation and scripting. See [`docs/cli-user-guide.md`](docs/cli-user-guide.md:1).
- **UI Controller** - Graphical user interface for interactive use. See [`docs/gui-user-guide.md`](docs/gui-user-guide.md:1).

## Features

- **AI-Powered Exploration** - Multiple provider support (Gemini, Ollama, OpenRouter)
- **Intelligent State Management** - Visual and structural hashing for unique screen identification
- **Loop Detection** - Prevents repetitive patterns
- **Traffic Capture** - Optional network monitoring via PCAPdroid during crawl (saves .pcap files)
- **Video Recording** - Optional screen recording of entire crawl session (saves .mp4 files)
- **MobSF Integration** - Optional automatic static security analysis after crawl completion
- **Focus Areas** - Customizable privacy-focused testing targets
- **Comprehensive Reporting** - PDF reports with crawl analysis

## AI Model Support

### Supported Providers

1. **Google Gemini** - Cloud-based multimodal model with excellent image understanding
2. **Ollama** - Local models (supports vision-capable variants like llama3.2-vision)
3. **OpenRouter** - Cloud router to top models via OpenAI-compatible API

### Configuration Example

```json
{
  "AI_PROVIDER": "ollama",
  "DEFAULT_MODEL_TYPE": "llama3.2-vision",
  "OLLAMA_BASE_URL": "http://localhost:11434"
}
```

**Vision-capable Ollama models:** `llama3.2-vision`, `llava`, `bakllava`

## Appium Integration

The system uses Appium-Python-Client for direct mobile device interaction. No external server is required beyond the standard Appium server.

### Configuration

```json
{
  "APPIUM_SERVER_URL": "http://127.0.0.1:4723"
}
```

**Note:** Ensure Appium server is running on the configured port (default: 4723).

## Architecture

### Core Components

- **`run_cli.py`** - CLI entry point
- **`run_ui.py`** - GUI entry point
- **`cli/main.py`** - CLI command orchestration
- **`core/crawler.py`** - Main crawling logic and state transitions
- **`domain/agent_assistant.py`** - AI-driven action orchestration
- **`domain/model_adapters.py`** - Unified AI provider integration
- **`domain/agent_tools.py`** - Device interaction tools
- **`infrastructure/appium_helper.py`** - Core Appium session management
- **`infrastructure/device_detection.py`** - Device/emulator detection
- **`infrastructure/capability_builder.py`** - W3C capability building
- **`domain/screen_state_manager.py`** - State tracking and transitions

### Agent-Based Workflow

1. **Observe** - Capture screenshot and XML representation
2. **Reason** - Analyze screen elements and available actions
3. **Plan** - Determine optimal next action
4. **Act** - Execute action via agent tools
5. **Observe Again** - Receive feedback and adapt

## CLI Usage

Detailed CLI usage, command reference and examples have been moved to the dedicated CLI user guide:
- [`docs/cli-user-guide.md`](docs/cli-user-guide.md:1)

For GUI usage and interactive workflows see the GUI user guide:
- [`docs/gui-user-guide.md`](docs/gui-user-guide.md:1)

## Configuration Management

Simplified two-layer configuration system:
- **Secrets (API keys)**: Environment variables only (never stored in SQLite)
- **Everything else**: SQLite only (int, str, bool, float values)

On first launch, simple type defaults are automatically populated into SQLite from module constants. Complex types (dict, list) are excluded and remain in code only.

**Environment Variables (.env):**
```env
GEMINI_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key
OLLAMA_BASE_URL=http://localhost:11434
MOBSF_API_KEY=your_mobsf_key
PCAPDROID_API_KEY=your_pcapdroid_key
```

**Note:** All non-secret configuration values are stored in SQLite (`config.db`). Secrets are read from environment variables only and never persisted to disk.

**System Variables:**
```
ANDROID_HOME=C:/Users/youruser/AppData/Local/Android/Sdk
```

## Output Structure

Session-based output per device/app run:
```
output_data/<device_id>_<app_package>_<timestamp>/
├── screenshots/
├── annotated_screenshots/
├── database/<app_package>_crawl_data.db
├── traffic_captures/        # PCAP files (if traffic capture enabled)
├── video/                   # Video recordings (if video recording enabled)
├── logs/
├── reports/
├── mobsf_scan_results/      # MobSF analysis results (if MobSF analysis enabled)
└── extracted_apk/
```

App info caches (stable, reusable):
```
output_data/app_info/<device_id>/
├── device_<device_id>_all_apps.json
└── device_<device_id>_filtered_health_apps.json
```

## Prerequisites

### Required
- Python 3.8+
- Node.js & npm (for Appium)
- Android SDK with ADB

### Optional
- MobSF (Docker or native)
- PCAPdroid (for traffic capture)
- Ollama (for local AI models)

### Device Setup
1. Enable Developer options (tap Build number 7 times)
2. Enable USB debugging
3. Connect via USB and authorize ADB

## MobSF Integration

MobSF (Mobile Security Framework) must be installed and running before enabling MobSF analysis. For installation instructions, see the [official MobSF documentation](https://github.com/MobSF/Mobile-Security-Framework-MobSF).

### Docker Setup (Recommended)
```powershell
# Basic (ephemeral)
docker run -d --name mobsf -p 8000:8000 opensecurity/mobile-security-framework-mobsf:latest

# With persistent storage (Windows)
mkdir C:\mobsf\uploads, C:\mobsf\signatures
docker run -d --name mobsf -p 8000:8000 `
  -v "C:\mobsf\uploads:/home/mobsf/Mobile-Security-Framework-MobSF/uploads" `
  -v "C:\mobsf\signatures:/home/mobsf/Mobile-Security-Framework-MobSF/signatures" `
  opensecurity/mobile-security-framework-mobsf:latest
```

**Note:** For native installation or other setup methods, refer to the [official MobSF installation guide](https://github.com/MobSF/Mobile-Security-Framework-MobSF).

### Configuration
```json
{
  "ENABLE_MOBSF_ANALYSIS": true,
  "MOBSF_API_URL": "http://localhost:8000/api/v1",
  "MOBSF_API_KEY": "YOUR_API_KEY_HERE"
}
```
