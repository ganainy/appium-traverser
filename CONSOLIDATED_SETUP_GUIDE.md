# AI-Driven Android App Crawler - Complete Setup & Usage Guide

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-development-yellow.svg)]()

## Overview

This project implements an automated crawler for Android applications driven by a multimodal AI model (Google Gemini). It intelligently explores app screens by analyzing visual layout and structural information, deciding the next best action to discover new states and interactions.

**Available Interfaces:**
- **GUI Controller** - Traditional graphical interface with visual controls
- **CLI Controller** - Command-line interface for automation and scripting

## Quick Start

### 1. Prerequisites Installation

**Required Software:**
- **Python 3.8+** - [Download here](https://www.python.org/) (ensure it's added to PATH)
- **Node.js & npm** - [Download here](https://nodejs.org/) (for Appium)
- **Android SDK** - Usually comes with Android Studio
- **Java 8+** - For Android tools

**Environment Variables:**
- `ANDROID_HOME` or `ANDROID_SDK_ROOT` pointing to your Android SDK directory
- `GEMINI_API_KEY` in `.env` file for AI features

### 2. Quick Installation

```powershell
# 1. Install Appium and drivers
npm install -g appium
appium driver install uiautomator2

# 2. Clone and setup project
git clone <repository-url>
cd appium-traverser-vertiefung

# 3. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt

# 5. Verify setup
appium --version
adb devices
```

### 3. Start Crawling (CLI Method)

```powershell
# Terminal 1: Start Appium
appium --relaxed-security

# Terminal 2: Use CLI Controller
.\run_cli_controller.ps1 --scan-apps
.\run_cli_controller.ps1 --list-apps
.\run_cli_controller.ps1 --select-app 1
.\run_cli_controller.ps1 --start
```

## Detailed Setup Instructions

### Prerequisites Setup

1. **Python Installation:**
   - Download from [python.org](https://www.python.org/)
   - **Critical:** Check "Add Python to PATH" during installation
   - Verify: `python --version`

2. **Node.js & Appium:**
   ```powershell
   # Install Node.js from nodejs.org, then:
   npm install -g appium
   appium driver install uiautomator2
   appium driver install xcuitest  # Optional for iOS
   
   # Verify installation
   appium --version
   appium driver list --installed
   ```

3. **Android SDK Setup:**
   - Install Android Studio or standalone SDK
   - Set environment variable: `ANDROID_HOME=C:\Users\YourUser\AppData\Local\Android\Sdk`
   - Add to PATH: `%ANDROID_HOME%\platform-tools`
   - Verify: `adb devices`

4. **Device/Emulator:**
   - Enable Developer Options and USB Debugging on device
   - Or start Android emulator
   - Verify connection: `adb devices`

### Project Setup

1. **Clone Repository:**
   ```powershell
   git clone <repository-url>
   cd appium-traverser-vertiefung
   ```

2. **Virtual Environment:**
   ```powershell
   # Create environment
   python -m venv .venv
   
   # Activate (Windows PowerShell)
   .\.venv\Scripts\Activate.ps1
   
   # If execution policy error, run once:
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

4. **Environment Configuration:**
   Create `.env` file in project root:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage Guide

### CLI Controller (Recommended for Automation)

**Execution Methods:**
```powershell
# Method 1: PowerShell wrapper (easiest)
.\run_cli_controller.ps1 --help

# Method 2: Batch wrapper
.\run_cli_controller.bat --help

# Method 3: Direct execution
cd traverser_ai_api
python cli_controller.py --help

# Method 4: Python wrapper
cd traverser_ai_api
python run_cli.py --help
```

**Complete Workflow:**
```powershell
# 1. Start Appium (Terminal 1)
appium --relaxed-security --address 0.0.0.0 --port 4723

# 2. Setup and crawl (Terminal 2)
cd "path\to\appium-traverser-vertiefung"

# Scan for health apps
.\run_cli_controller.ps1 --scan-apps

# List found apps
.\run_cli_controller.ps1 --list-apps

# Select app by index or name
.\run_cli_controller.ps1 --select-app 1
.\run_cli_controller.ps1 --select-app "MyFitnessPal"

# Configure crawler
.\run_cli_controller.ps1 --show-config
.\run_cli_controller.ps1 --set-config MAX_CRAWL_STEPS=50
.\run_cli_controller.ps1 --set-config CRAWL_MODE=steps
.\run_cli_controller.ps1 --save-config

# Start crawling
.\run_cli_controller.ps1 --start

# 3. Monitor/control (Terminal 3 - optional)
.\run_cli_controller.ps1 --status
.\run_cli_controller.ps1 --stop
```

**Available Commands:**
```powershell
# App Management
--scan-apps                    # Scan device for health apps
--list-apps                    # List available apps
--select-app NAME_OR_INDEX     # Select app by name or index

# Crawler Control
--start                        # Start the crawler
--stop                         # Stop the crawler
--status                       # Show current status

# Configuration
--show-config [FILTER]         # Show configuration
--set-config KEY=VALUE         # Set configuration value
--save-config                  # Save configuration

# Options
--force-rescan                 # Force app rescan
--verbose                      # Enable verbose logging
```

### GUI Controller (Traditional Interface)

```powershell
# Ensure virtual environment is activated
.\.venv\Scripts\Activate.ps1

# Start GUI
.\run_ui_controller.ps1
```

## Configuration Management

### Common Configuration Options

**Device Settings:**
```powershell
.\run_cli_controller.ps1 --set-config TARGET_DEVICE_UDID=emulator-5554
.\run_cli_controller.ps1 --set-config APPIUM_SERVER_URL=http://localhost:4723/wd/hub
```

**Crawler Behavior:**
```powershell
# Steps-based crawling
.\run_cli_controller.ps1 --set-config CRAWL_MODE=steps
.\run_cli_controller.ps1 --set-config MAX_CRAWL_STEPS=30

# Time-based crawling
.\run_cli_controller.ps1 --set-config CRAWL_MODE=time
.\run_cli_controller.ps1 --set-config MAX_CRAWL_DURATION_SECONDS=300

# Additional options
.\run_cli_controller.ps1 --set-config ENABLE_TRAFFIC_CAPTURE=true
.\run_cli_controller.ps1 --set-config CONTINUE_EXISTING_RUN=true
```

**Configuration Files:**
- Main config: `traverser_ai_api/user_config.json`
- Default values: `traverser_ai_api/config.py`

## Project Architecture

### Core Components

- **`main.py`** - Entry point and orchestration
- **`crawler.py`** - Main crawling logic and state transitions
- **`appium_driver.py`** - Appium WebDriver wrapper
- **`ai_assistant.py`** - Google Gemini AI integration
- **`state_manager.py`** - Screen state and transition management
- **`cli_controller.py`** - Command-line interface
- **`ui_controller.py`** - Graphical user interface

### Key Features

- **AI-Powered Exploration** - Uses Google Gemini to analyze screens and decide actions
- **State Management** - Tracks unique screens using visual and structural hashing
- **Loop Detection** - Prevents getting stuck in repetitive patterns
- **Traffic Capture** - Optional network traffic monitoring
- **Multi-Interface** - Both CLI and GUI available
- **Automation-Ready** - Scriptable for CI/CD integration

### Output Locations

- **Screenshots:** `traverser_ai_api/output_data/screenshots/`
- **Database:** `traverser_ai_api/output_data/database_output/`
- **Traffic Captures:** `traverser_ai_api/output_data/traffic_captures/`
- **App Info Cache:** `traverser_ai_api/output_data/app_info/`

## Troubleshooting

### Appium Issues
```powershell
# Check if Appium is running
netstat -an | findstr :4723

# Kill existing processes
taskkill /F /IM node.exe

# Reset Appium session
appium --session-override
```

### Device Connection Issues
```powershell
# Restart ADB
adb kill-server
adb start-server

# Check device properties
adb shell getprop

# List connected devices
adb devices
```

### Python/Environment Issues
```powershell
# Check Python installation
python --version

# Verify virtual environment
where python  # Should point to .venv directory

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Common Error Solutions

**"Could not connect to Appium server"**
- Ensure Appium is running: `appium --relaxed-security`
- Check server URL in configuration
- Verify port 4723 is not blocked

**"No devices found"**
- Run `adb devices` to verify connection
- Try restarting ADB: `adb kill-server && adb start-server`
- Check USB debugging is enabled

**"App not found"**
- Run app scan first: `--scan-apps`
- Ensure app is installed on device
- Check device is unlocked and accessible

**"Permission denied" errors**
- Ensure Appium runs with `--relaxed-security`
- Check file permissions in output directories
- Verify Android SDK environment variables

**PowerShell execution policy errors**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Advanced Usage

### Automation Scripts
```powershell
# Create batch crawling script
.\run_cli_controller.ps1 --scan-apps
$apps = @("MyFitnessPal", "Strava", "Fitbit")
foreach ($app in $apps) {
    .\run_cli_controller.ps1 --select-app $app
    .\run_cli_controller.ps1 --set-config MAX_CRAWL_STEPS=25
    .\run_cli_controller.ps1 --save-config
    .\run_cli_controller.ps1 --start
    # Wait for completion or implement monitoring
}
```

### Multiple Device Setup
```powershell
# Configure different devices
.\run_cli_controller.ps1 --set-config TARGET_DEVICE_UDID=device1
.\run_cli_controller.ps1 --save-config

# Save device-specific configs
Copy-Item "traverser_ai_api\user_config.json" "config_device1.json"
```

### CI/CD Integration
```yaml
# Example GitHub Actions workflow
- name: Run Appium Crawler
  run: |
    appium --relaxed-security &
    sleep 10
    .\run_cli_controller.ps1 --scan-apps
    .\run_cli_controller.ps1 --select-app 1
    .\run_cli_controller.ps1 --start
```

## Migration from GUI to CLI

The CLI controller maintains full compatibility with existing GUI configurations:
- Same `user_config.json` format
- Same output directory structure
- Same feature set and capabilities
- Easy transition without data loss

**Benefits of CLI:**
- Automation and scripting support
- Lower resource usage
- Remote execution capability
- Better CI/CD integration
- Faster startup times

## UI Element Annotation Tool

The project includes a standalone tool for batch processing screenshots to identify UI elements:

```powershell
# Process all screenshots in a directory
python -m tools.ui_element_annotator --input-dir "output_data/screenshots/crawl_screenshots_com.example" --output-file "output_data/annotations.json"

# View help and options
python -m tools.ui_element_annotator --help
```

This tool uses Google's Gemini Vision AI to analyze screenshots and create detailed annotations of UI elements, saving their locations and properties in a JSON file. Useful for:
- Post-crawl analysis
- Training data generation
- UI testing verification
- Accessibility testing

---

**Need Help?** Check the troubleshooting section above or create an issue in the project repository.
