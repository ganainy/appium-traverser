<!-- filepath: e:\Vertiefung\appium-traverser-vertiefung\CONSOLIDATED_SETUP_GUIDE.md -->
# AI-Driven Android App Crawler - Complete Setup & Usage Guide

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
- [Usage Guide](#usage-guide)
  - [CLI Controller](#cli-controller-recommended-for-automation)
  - [Configuration Management](#configuration-management)
- [MobSF Setup](#mobsf-setup)
- [Project Architecture](#project-architecture)
  - [Core Components](#core-components)
  - [Key Features](#key-features)
  - [Output Locations](#output-locations-relative-to-traverser_ai_api)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)
- [UI Element Annotation Tool](#ui-element-annotation-tool)

## Overview

This project implements an automated crawler for Android applications driven by a multimodal AI model (Google Gemini). It intelligently explores app screens by analyzing visual layout and structural information, deciding the next best action to discover new states and interactions.

Available Interfaces:
*   CLI Controller - Command-line interface for automation and scripting
*   UI Controller - Graphical user interface for interactive use

## Quick Start

### 1. Prerequisites Installation

Required Software:
*   Python 3.8+ - Download here (ensure it's added to PATH)
*   Node.js & npm - Download here (for Appium)
*   Android SDK - Usually comes with Android Studio
*   Java 8+ - For Android tools

Environment Variables:
*   `ANDROID_HOME` or `ANDROID_SDK_ROOT` pointing to your Android SDK directory
*   `GEMINI_API_KEY` in `.env` file for AI features
*   `PCAPDROID_API_KEY` in `.env` file for traffic capture functionality

### 2. Quick Installation

**1. Install Appium and drivers**
```bash
npm install -g appium
appium driver install uiautomator2
```

**2. Clone and setup project**
```bash
git clone <repository-url>
cd appium-traverser-vertiefung
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

#### Terminal 1: Start Appium

```bash
appium --relaxed-security
```

#### Terminal 2: Use CLI Controller (ensure .venv is active)

```powershell
python traverser_ai_api/cli_controller.py --scan-apps
python traverser_ai_api/cli_controller.py --list-apps
python traverser_ai_api/cli_controller.py --select-app 1 # Or by name
python traverser_ai_api/cli_controller.py --start
```

### 4. Start Crawling (UI Method)

#### Terminal 1: Start Appium (same as CLI method)

```bash
appium --relaxed-security
```

#### Terminal 2: Launch UI Controller (ensure .venv is active)

```powershell
python traverser_ai_api/ui_controller.py
```

**Using the UI Controller:**

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
*   Download from python.org
*   Critical: Check "Add Python to PATH" during installation.
*   Verify: `python --version`

**Node.js & Appium:**
Install Node.js from nodejs.org, then:
```bash
npm install -g appium
appium driver install uiautomator2
# appium driver install xcuitest  # Optional for iOS
```
Verify installation:
```bash
appium --version
appium driver list --installed
```

**Android SDK Setup:**
*   Install Android Studio or standalone SDK tools.
*   Set environment variable `ANDROID_HOME` (or `ANDROID_SDK_ROOT`) to your SDK path (e.g., `C:\Users\YourUser\AppData\Local\Android\Sdk`).
*   Add SDK `platform-tools` to your system PATH (e.g., `%ANDROID_HOME%\platform-tools`).
*   Verify: `adb devices` (should show connected devices/emulators after setup).

**Device/Emulator:**
*   Enable Developer Options and USB Debugging on your physical Android device.
*   Or, set up and start an Android emulator via Android Studio.
*   Verify connection: `adb devices` should list your device/emulator.

### Project Setup

**Clone Repository:**
```bash
git clone <repository-url> # Replace <repository-url> with the actual URL
cd appium-traverser-vertiefung
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
If you encounter an execution policy error in PowerShell when trying to activate the virtual environment, run the following command once in PowerShell:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

**Install Dependencies:**
Ensure your virtual environment is active:
```bash
pip install -r requirements.txt
```

**Environment Configuration (`.env` file):**
Create a file named `.env` in the project root directory (NOT in the traverser_ai_api subdirectory).
Add your Google Gemini API key and optionally PCAPdroid API key to it:
```env
# Required for AI functionality
GEMINI_API_KEY=your_api_key_here

# Optional keys
# PCAPDROID_API_KEY=your_pcapdroid_key_here
# MOBSF_API_KEY=your_mobsf_key_here
```

IMPORTANT: Only use ONE .env file in the project root. The application is configured to look for it there.

This file contains sensitive information and should NOT be committed to version control.

## Usage Guide

### CLI Controller (Recommended for Automation)

#### Execution:
Navigate to the `traverser_ai_api` directory or use relative paths. Ensure your virtual environment is active.

Example:
```powershell
cd traverser_ai_api
python cli_controller.py --help
```
Or from the project root:
```powershell
python traverser_ai_api/cli_controller.py --help
```

#### Typical Workflow:

**1. Start Appium Server (in a separate terminal):**
```bash
appium --relaxed-security --address 0.0.0.0 --port 4723
```
(The `--relaxed-security` flag is often needed for certain Appium actions like installing APKs or managing files.)

**2. Interact with the CLI Controller (in another terminal, project root directory):**
Activate virtual environment if not already active:
```powershell
# .\.venv\Scripts\Activate.ps1
```
Scan for installed (health-related) apps on the connected device/emulator:
```powershell
python traverser_ai_api/cli_controller.py --scan-apps
```
List the apps found by the scan:
```powershell
python traverser_ai_api/cli_controller.py --list-apps
```
Select an app to target for crawling (use its index number from the list or package name):
```powershell
python traverser_ai_api/cli_controller.py --select-app 1
# OR
python traverser_ai_api/cli_controller.py --select-app "com.example.healthapp"
```
View current crawler configuration:
```powershell
python traverser_ai_api/cli_controller.py --show-config
```
Modify configuration if needed (e.g., set max crawl steps):
```powershell
python traverser_ai_api/cli_controller.py --set-config MAX_CRAWL_STEPS=50
python traverser_ai_api/cli_controller.py --save-config # Persists changes to user_config.json
```
Start the crawling process for the selected app:
```powershell
python traverser_ai_api/cli_controller.py --start
```
Check crawler status (can be run while crawler is active or stopped):
```powershell
python traverser_ai_api/cli_controller.py --status
```

Pause a running crawler:
```powershell
python traverser_ai_api/cli_controller.py --pause
```

Resume a paused crawler:
```powershell
python traverser_ai_api/cli_controller.py --resume
```

Stop a running crawler gracefully:
```powershell
python traverser_ai_api/cli_controller.py --stop
```

#### Available Commands:

##### App Management:
*   `--scan-apps`: Scans the connected device/emulator for health-related applications and updates a local cache.
*   `--list-apps`: Lists applications found by the `--scan-apps` command.
*   `--select-app <APP_NAME_OR_INDEX>`: Selects an application (by its 1-based index from `--list-apps` or by its package name) to be the target for crawling.

##### Crawler Control:
*   `--start`: Starts the crawling process on the currently selected application.
*   `--stop`: Signals a running crawler to stop gracefully.
*   `--pause`: Temporarily halts crawler execution after completing current action.
*   `--resume`: Continues execution of a paused crawler.
*   `--status`: Shows the current status of the crawler (running, stopped, paused, selected app, etc.).

##### Configuration:
*   `--show-config [FILTER_KEY]`: Displays the current configuration. Optionally filters by a key string.
*   `--set-config <KEY=VALUE>`: Sets a specific configuration value (e.g., `MAX_CRAWL_STEPS=100`). Multiple can be provided.
*   `--save-config`: Saves the current in-memory configuration to `user_config.json`.

##### Analysis & Reporting (Simplified Workflow):
*   `--list-analysis-targets`: Scans the output directory for databases and lists available app packages (targets) for analysis with an index number.
*   `--list-runs-for-target`: Lists all recorded runs for a specific analysis target.
    *   Requires either `--target-index <NUMBER>` (from `--list-analysis-targets`) OR `--target-app-package <PACKAGE_NAME>`.
*   `--generate-analysis-pdf`: Generates a PDF report for an analysis target.
    *   Requires either `--target-index <NUMBER>` OR `--target-app-package <PACKAGE_NAME>`.
    *   The PDF is generated for the latest run if multiple exist for the target, or the only run if just one. The specific run ID used is determined automatically.
    *   Optionally takes `--pdf-output-name <FILENAME.pdf>` to customize the suffix of the PDF filename. If omitted, a default name (`analysis.pdf`) is used as the suffix. The PDF is always prefixed with the app package.

##### Options:
*   `--force-rescan`: Forces the `--scan-apps` command to re-scan even if a cached app list exists.
*   `--verbose` or `-v`: Enables verbose (DEBUG level) logging for the CLI session.

#### Analysis Examples (Simplified Workflow):

**1. List all apps that have crawl data (databases)**
```powershell
python traverser_ai_api/cli_controller.py --list-analysis-targets
# Example output might show:
#   1. App Package: com.example.app1, DB File: com.example.app1_crawl_data.db
#   2. App Package: com.another.app, DB File: com.another.app_crawl_data.db
```

**2. (Optional) List runs for a specific app to see what run IDs are available**
```powershell
python traverser_ai_api/cli_controller.py --list-runs-for-target --target-index 1
```

**3. Generate PDF for the automatically selected run (latest/only) of 'com.example.app1' (using index)**
```powershell
python traverser_ai_api/cli_controller.py --generate-analysis-pdf --target-index 1
```

**4. Generate PDF for the automatically selected run of 'com.another.app' (using package name)**
```powershell
python traverser_ai_api/cli_controller.py --generate-analysis-pdf --target-app-package com.another.app
```

**5. Generate PDF for the automatically selected run of 'com.another.app' with a custom output name**
```powershell
python traverser_ai_api/cli_controller.py --generate-analysis-pdf --target-app-package com.another.app --pdf-output-name "my_custom_report.pdf"
# This would create a file like: com.another.app_run_<AUTO_SELECTED_ID>_my_custom_report.pdf
```


## Configuration Management

### Common Configuration Options (via CLI)

#### Device Settings:
```powershell
python traverser_ai_api/cli_controller.py --set-config TARGET_DEVICE_UDID=emulator-5554
python traverser_ai_api/cli_controller.py --set-config APPIUM_SERVER_URL="http://127.0.0.1:4723" # Ensure quotes if URL has special chars
```

#### Crawler Behavior:
Steps-based crawling:
```powershell
python traverser_ai_api/cli_controller.py --set-config CRAWL_MODE=steps
python traverser_ai_api/cli_controller.py --set-config MAX_CRAWL_STEPS=30
```
Time-based crawling:
```powershell
python traverser_ai_api/cli_controller.py --set-config CRAWL_MODE=time
python traverser_ai_api/cli_controller.py --set-config MAX_CRAWL_DURATION_SECONDS=300
```
Other options:
```powershell
python traverser_ai_api/cli_controller.py --set-config ENABLE_TRAFFIC_CAPTURE=true # or false
python traverser_ai_api/cli_controller.py --set-config CONTINUE_EXISTING_RUN=true # or false
```
Remember to use `--save-config` after setting values if you want them to persist for future sessions.

### Configuration Files:
*   User-specific settings: `traverser_ai_api/user_config.json` (created/updated by saving config via UI or CLI).
*   Default values: Defined within `traverser_ai_api/config.py`.

## Project Architecture

### Core Components
*   `main.py`: Main entry point for the crawler, orchestrates the crawling process.
*   `crawler.py`: Contains the core crawling logic, state transitions, and interaction with other components.
*   `appium_driver.py`: A wrapper around the Appium WebDriver for interacting with the Android device/emulator.
*   `ai_assistant.py`: Handles communication with the Google Gemini AI model for action decisions and reasoning.
*   `state_manager.py`: Manages screen states, detects unique screens using hashing, and identifies loops.
*   `config.py`: Defines the configuration structure and loads default/user settings.
*   `cli_controller.py`: Implements the command-line interface.
*   `analysis_viewer.py`: Provides functionalities to analyze crawl data and generate reports.

### Key Features
*   AI-Powered Exploration: Leverages Google Gemini for intelligent action selection based on screen context.
*   State Management & Hashing: Identifies unique screens by hashing their XML structure and visual features (optional).
*   Loop Detection: Prevents the crawler from getting stuck in repetitive navigation cycles.
*   Traffic Capture: Optionally captures network traffic during the crawl using PCAPdroid.
*   CLI Interface: Offers a command-line interface for automation and scripting.
*   Configurable: Extensive options to customize crawler behavior, AI parameters, and device settings.
*   Data Persistence: Stores crawl data, including screens, steps, and AI interactions, in an SQLite database.
*   Reporting: Capable of generating PDF reports summarizing crawl sessions (via CLI).

### Output Locations (relative to `traverser_ai_api/`)
*   Screenshots: `output_data/screenshots/crawl_screenshots_{package_name}/`
*   Annotated Screenshots: `output_data/screenshots/annotated_crawl_screenshots_{package_name}/`
*   Databases: `output_data/database_output/{package_name}/{package_name}_crawl_data.db`
*   Traffic Captures: `output_data/traffic_captures/{package_name}/`
*   App Info Cache: `output_data/app_info/` (shared, contains scanned app lists)
*   Analysis Reports (PDFs): `output_data/analysis_reports/`
*   Logs: `output_data/logs/{package_name}/` (for crawler logs) and `output_data/logs/cli/` (for CLI logs)

## Troubleshooting

### Appium Issues
Check if Appium is running on the default port (4723):
*Windows:*
```powershell
netstat -an | findstr ":4723"
```
*macOS/Linux:*
```bash
lsof -i :4723
```
If Appium is stuck or misbehaving, kill Node.js processes:
*Windows:*
```powershell
taskkill /F /IM node.exe
```
*macOS/Linux (be cautious with pkill):*
```bash
pkill -f appium
```
Consider resetting Appium's session handling if issues persist:
```bash
appium --session-override # Start Appium with this flag
```

### Device Connection Issues (adb)
Restart ADB server:
```powershell
adb kill-server
adb start-server
```
List connected devices/emulators:
```powershell
adb devices # Ensure your target device is listed and 'device' or 'emulator' state
```
*   If device shows 'unauthorized', re-authorize on the device.
*   Check device properties (useful for `TARGET_DEVICE_UDID`): `adb shell getprop`

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

### Common Error Solutions
*   **"Could not connect to Appium server"**
    *   Ensure Appium is running: `appium --relaxed-security`.
    *   Verify the `APPIUM_SERVER_URL` in your configuration matches where Appium is listening.
    *   Check firewall settings; ensure port 4723 (or your configured port) is not blocked.
*   **"No devices/emulators found" by ADB or Appium**
    *   Run `adb devices` to confirm ADB sees your device.
    *   Ensure USB debugging is enabled on the physical device and authorized.
    *   If using an emulator, ensure it's fully booted.
    *   Try a different USB cable or port.
*   **"App not found" or "Activity not found" when starting crawl**
    *   Run `--scan-apps` and `--select-app` first via CLI, or ensure correct package/activity in GUI.
    *   Verify the app is actually installed on the target device/emulator.
    *   Ensure the device is unlocked and on the home screen (or any neutral state) before starting.
*   **Permission denied errors (file access, etc.)**
    *   If Appium needs to install APKs or access certain device features, running it with `--relaxed-security` is often necessary.
    *   Check file/folder permissions for your project directory and `output_data` subdirectories.
    *   Ensure Android SDK environment variables (`ANDROID_HOME`) are correctly set and pointing to a valid SDK installation.

### PowerShell execution policy errors when activating `.venv`
Run this once in PowerShell:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
```

## Advanced Usage

### Automation Scripts (Example PowerShell)
Ensure virtual environment is active first: `.\.venv\Scripts\Activate.ps1`

Example: Batch crawl a list of apps
```powershell
$appsToCrawl = @(
    "com.example.app1",
    "com.example.app2",
    "com.example.anotherapp"
)

foreach ($appPackage in $appsToCrawl) {
    Write-Host "Selecting app: $appPackage"
    python traverser_ai_api/cli_controller.py --select-app $appPackage
    
    Write-Host "Setting crawl parameters for $appPackage..."
    python traverser_ai_api/cli_controller.py --set-config MAX_CRAWL_STEPS=20
    python traverser_ai_api/cli_controller.py --save-config
    
    Write-Host "Starting crawl for $appPackage..."
    python traverser_ai_api/cli_controller.py --start
    
    # Add logic here to wait for completion if needed, e.g., by monitoring status or logs
    Write-Host "Crawl presumably finished for $appPackage (or stop manually)."
    Start-Sleep -Seconds 10 # Brief pause
}
Write-Host "Batch crawling finished."
```

### Multiple Device Setup
You can run multiple Appium servers on different ports and target different devices by setting `APPIUM_SERVER_URL` and `TARGET_DEVICE_UDID` in your configuration.

It's often easier to manage separate `user_config.json` files or use environment variables to switch between device configurations if running multiple instances of the crawler system.


## MobSF Setup

The AppTransverser supports integration with MobSF (Mobile Security Framework) for static analysis of Android applications. To use this feature:

1. Install MobSF
   - Follow the official installation guide at [https://github.com/MobSF/Mobile-Security-Framework-MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF)
   - Basic installation steps:

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
   - Start MobSF and access the web interface (typically at [http://localhost:8000](http://localhost:8000))
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
   - Check that the connection succeeds without errors

5. Usage
   - When starting a crawl with MobSF analysis enabled, the system will:
     - Extract the APK from the connected device
     - Upload it to MobSF for analysis
     - Process the results and save reports in the output directory

## UI Element Annotation Tool

The project includes a standalone tool for batch processing screenshots to identify and annotate UI elements using Google's Gemini Vision AI.

### Usage

Ensure virtual environment is active.
Run from the project root directory (`appium-traverser-vertiefung`).

Example: Process all screenshots in a specific crawl output directory

```powershell
python -m traverser_ai_api.tools.ui_element_annotator --input-dir "traverser_ai_api/output_data/screenshots/crawl_screenshots_com.example.app1" --output-file "traverser_ai_api/output_data/annotations/app1_annotations.json"
```

View help for all options:

```powershell
python -m traverser_ai_api.tools.ui_element_annotator --help
```

This tool analyzes screenshots to:

- Detect various UI elements (buttons, text fields, images, etc.)
- Determine their bounding box coordinates
- Extract text content if present
- Save this information in a structured JSON output file

This can be useful for:

- Detailed post-crawl analysis of UI components
- Generating datasets for training custom UI understanding models
- Verifying UI elements for automated testing or analysis
