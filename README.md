# AI-Driven Android App Crawler

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-development-blue.svg)]()

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Features](#features)
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
.\run_cli_controller.ps1 --scan-apps --list-apps --select-app 1 --start

# OR UI Controller (Terminal 2)
.\run_ui_controller.ps1  # Opens graphical interface
```

## Features

- **AI-Powered Exploration** - Uses Google Gemini to analyze screens and decide actions
- **Intelligent State Management** - Visual and structural hashing to identify unique screens
- **Loop Detection** - Prevents getting stuck in repetitive patterns
- **Traffic Capture** - Optional network monitoring
- **Automation Ready** - Perfect for CI/CD and scripting workflows

## Complete Setup & Usage

📖 **[See CONSOLIDATED_SETUP_GUIDE.md](./CONSOLIDATED_SETUP_GUIDE.md)** for comprehensive setup instructions, usage examples, configuration options, and troubleshooting.

## Architecture

- **`main.py`** - Entry point and orchestration
- **`crawler.py`** - Main crawling logic and state transitions
- **`cli_controller.py`** - Command-line interface
- **`ui_controller.py`** - Graphical user interface
- **`ai_assistant.py`** - Google Gemini integration
- **`state_manager.py`** - Screen state and transition management

## Output

- **Screenshots:** `traverser_ai_api/output_data/screenshots/`
- **Database:** `traverser_ai_api/output_data/database_output/`
- **Traffic Captures:** `traverser_ai_api/output_data/traffic_captures/`


