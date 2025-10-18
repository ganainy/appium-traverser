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
  - [Appium Issues](#appium-issues)
  - [Device Connection Issues (adb)](#device-connection-issues-adb)
  - [Python/Environment Issues](#pythonenvironment-issues)
  - [Common Error Solutions](#common-error-solutions)
  - [PowerShell execution policy errors when activating .venv](#powershell-execution-policy-errors-when-activating-venv)
- [MobSF Setup](#mobsf-setup)
- [Comprehensive Prerequisites Installation Guide](#comprehensive-prerequisites-installation-guide)
  - [1) System Requirements](#1-system-requirements)
  - [2) Android SDK and ADB](#2-android-sdk-and-adb)
  - [3) Appium Server](#3-appium-server)
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

#### Terminal 1: Start Appium

```bash
appium --relaxed-security
```

#### Terminal 2: Use CLI Controller (ensure .venv is active)

```powershell
python run_cli.py --scan-health-apps --force-rescan   # or use --scan-all-apps
python run_cli.py --list-health-apps                  # or use --list-all-apps
python run_cli.py --select-app 1                      # select by index
python run_cli.py --select-app "com.example.healthapp"  # or select by package/name
python run_cli.py --start --annotate-offline-after-run  # starts crawler and creates annotated screenshots after completion
```

### 4. Start Crawling (UI Method)

#### Terminal 1: Start Appium (same as CLI method)

```bash
appium --relaxed-security
```

#### Terminal 2: Launch UI Controller (ensure .venv is active)

```powershell
python run_ui.py
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
*   Verify: `adb devices` (should show connected Android devices after setup).

**Device Setup:**

*   Required: Enable Developer options and USB debugging.
    * Settings > About phone > tap Build number 7 times.
    * Settings > System > Developer options > enable USB debugging.
*   Authorize: connect via USB and accept the RSA fingerprint prompt.
*   Verify: `adb devices` should show the device as "device" (not "unauthorized").

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

CLI refresh (same logic as UI, runs in background):

```powershell
python run_cli.py --refresh-openrouter-models
```

Requirements:
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

**1. Start Appium Server (in a separate terminal):**
```bash
appium --relaxed-security --address 0.0.0.0 --port 4723
```
(The `--relaxed-security` flag is needed for certain Appium actions like installing APKs or managing files.)

**2. Interact with the CLI Controller (in another terminal, project root directory):**
Activate virtual environment if not already active:
```powershell
# .\.venv\Scripts\Activate.ps1
```
Scan for installed apps on the connected Android device:
```powershell
# Health-focused scan (AI-filtered)
python run_cli.py --scan-health-apps
# OR deterministic scan of ALL apps
python run_cli.py --scan-all-apps
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
*   `--scan-all-apps`: Scans the connected Android device and caches ALL installed apps (no AI filtering).
*   `--scan-health-apps`: Scans the device and caches AI-filtered health apps (requires AI provider configured).
*   `--list-all-apps`: Lists ALL apps from the latest all-apps cache.
*   `--list-health-apps`: Lists HEALTH apps from the latest health-filtered cache.
*   `--select-app <APP_NAME_OR_INDEX>`: Selects an application (by its 1-based index from `--list-health-apps`/`--list-all-apps` or by its package name) to be the target for crawling.
*   `--show-selected-app`: Displays the currently selected app information (name, package, and activity).

##### Crawler Control:
*   `--start`: Starts the crawling process on the currently selected application.
*   `--stop`: Signals a running crawler to stop gracefully.
*   `--pause`: Temporarily halts crawler execution after completing current action.
*   `--resume`: Continues execution of a paused crawler.
*   `--status`: Shows the current status of the crawler (running, stopped, paused, selected app, etc.).

##### Configuration:
*   `--show-config [FILTER_KEY]`: Displays the current configuration. Optionally filters by a key string.
*   `--set-config <KEY=VALUE>`: Sets a specific configuration value (e.g., `MAX_CRAWL_STEPS=100`). Multiple can be provided.

##### Analysis & Reporting (Simplified Workflow):
*   `--list-analysis-targets`: Scans the output directory for databases and lists available app packages (targets) for analysis with an index number.
*   `--list-runs-for-target`: Lists all recorded runs for a specific analysis target.
    *   Requires either `--target-index <NUMBER>` (from `--list-analysis-targets`) OR `--target-app-package <PACKAGE_NAME>`.
*   `--generate-analysis-pdf`: Generates a PDF report for an analysis target.
    *   Requires either `--target-index <NUMBER>` OR `--target-app-package <PACKAGE_NAME>`.
    *   The PDF is generated for the latest run if multiple exist for the target, or the only run if just one. The specific run ID used is determined automatically.
    *   Optionally takes `--pdf-output-name <FILENAME.pdf>` to customize the suffix of the PDF filename. If omitted, a default name (`analysis.pdf`) is used as the suffix. The PDF is always prefixed with the app package.
    *   Requires the optional `xhtml2pdf` library. If not installed, the CLI will print "Analysis module or PDF library not available" and skip PDF generation. Install via:
        ```powershell
        pip install xhtml2pdf
        ```

##### Options:
*   `--force-rescan`: Forces the scan commands to re-scan even if a cached app list exists.
*   `--verbose` or `-v`: Enables verbose (DEBUG level) logging for the CLI session.

##### Offline UI Annotation (No AI Calls):
After a crawl finishes, you can automatically overlay bounding boxes onto screenshots and generate a simple gallery:

*   `--annotate-offline-after-run`: When used with `--start`, runs the offline annotator after the crawler exits. It writes images to `.../annotated_screenshots/` inside the latest session directory and generates an `index.html` gallery.

Manual usage (without running a new crawl):
```powershell
python -m tools.ui_element_annotator --db-path "path\to\your_crawl_data.db" --screens-dir ".../screenshots" --out-dir ".../annotated_screenshots"
```

#### Analysis Examples (Simplified Workflow):

**1. List all apps that have crawl data (databases)**
```powershell
python run_cli.py --list-analysis-targets
# Example output might show:
#   1. App Package: com.example.app1, DB File: com.example.app1_crawl_data.db
#   2. App Package: com.another.app, DB File: com.another.app_crawl_data.db
```

**2. (Optional) List runs for a specific app to see what run IDs are available**
```powershell
python run_cli.py --list-runs-for-target --target-index 1
```

**3. Generate PDF for the automatically selected run (latest/only) of 'com.example.app1' (using index)**
```powershell
python run_cli.py --generate-analysis-pdf --target-index 1
```

**4. Generate PDF for the automatically selected run of 'com.another.app' (using package name)**
```powershell
python run_cli.py --generate-analysis-pdf --target-app-package com.another.app
```

**5. Generate PDF for the automatically selected run of 'com.another.app' with a custom output name**
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
*   User-specific settings: `traverser_ai_api/user_config.json` (created/updated by saving config via UI or CLI).
*   Default values: Defined within `traverser_ai_api/config.py`.

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
List connected Android devices:
```powershell
adb devices # Ensure your target device is listed and 'device' state
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
*   **"No devices found" by ADB or Appium**
    *   Run `adb devices` to confirm ADB sees your device.
    *   Ensure USB debugging is enabled on the physical device and authorized.
    *   Try a different USB cable or port.
*   **"App not found" or "Activity not found" when starting crawl**
    *   Run `--scan-health-apps` and `--select-app` first via CLI, or ensure correct package/activity in GUI.
    *   Verify the app is actually installed on the target device.
    *   Ensure the device is unlocked and on the home screen (or any neutral state) before starting.
*   **Permission denied errors (file access, etc.)**
    *   If Appium needs to install APKs or access certain device features, make sure you are running it with `--relaxed-security` flag.
    *   Check file/folder permissions for your project directory and `output_data` subdirectories.
    *   Ensure Android SDK environment variables (`ANDROID_HOME`) are correctly set and pointing to a valid SDK installation.

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
     - Common Docker commands:
       ```powershell
       docker ps --filter name=mobsf       # see status
       docker start mobsf                  # start existing container
       docker stop mobsf                   # stop
       docker rm -f mobsf                  # remove (then re-run docker run)
       ```
   - Option B) Native install (without Docker)
     - Follow the official guide: [https://github.com/MobSF/Mobile-Security-Framework-MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF)
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
- In the CLI: Run `python run_cli.py --test-mobsf-connection`
   - Check that the connection succeeds without errors

5. Usage
   - When starting a crawl with MobSF analysis enabled, the system will:
     - Extract the APK from the connected device
     - Upload it to MobSF for analysis
     - Process the results and save reports in the output directory

# Comprehensive Prerequisites Installation Guide

This section consolidates installing and configuring the required services and tools: Appium, Android SDK/ADB, MobSF, and PCAPDroid. Optional local AI via Ollama is also covered.

## 1) System Requirements
- Windows 10/11 (PowerShell) or macOS/Linux
- Python 3.8+ (recommend 3.10+)
- Node.js 18+ (for Appium)
- Docker (optional, recommended for MobSF)

## 2) Android SDK and ADB
1. Install Android Platform Tools:
   - Download: https://developer.android.com/studio/releases/platform-tools
   - Extract and add the folder to PATH (contains `adb`).
2. Enable Developer Options and USB Debugging on your device.
3. Verify connection:
   ```powershell
   adb devices
   ```
   Your device should appear as “device”.

## 3) Appium Server
1. Install Node.js: https://nodejs.org/
2. Install Appium and Android driver:
   ```powershell
   npm install -g appium
   appium driver install uiautomator2
   ```
3. Start Appium server:
   ```powershell
   appium --relaxed-security
   ```
4. Optional: Set APPIUM_SERVER_URL in your `.env` or `user_config.json` (default is `http://127.0.0.1:4723`).

## 4) MobSF (Mobile Security Framework)
Recommended via Docker.

1. Ensure Docker is running
   - Windows/macOS: Start Docker Desktop and wait until it shows “Running”.
   - Windows tip: If you get pipe errors referring to `dockerDesktopLinuxEngine`, switch context to default:
     ```powershell
     docker context ls
     docker context use default
     ```

2. Pull the image
   ```powershell
   docker pull opensecurity/mobile-security-framework-mobsf:latest
   ```

3. Run MobSF
   - Quick start (no persistent volumes):
     ```powershell
     docker run -d --name mobsf -p 8000:8000 opensecurity/mobile-security-framework-mobsf:latest
     ```
   - With persistence (recommended):
    - Windows (PowerShell):
      ```powershell
      mkdir C:\mobsf\uploads
      mkdir C:\mobsf\signatures
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

4. Verify and manage
   ```powershell
   docker ps --filter name=mobsf    # should show mobsf with port 8000
   docker start mobsf               # start existing container
   docker stop mobsf                # stop
   docker rm -f mobsf               # remove
   ```

5. Open MobSF UI and configure
   - Open the UI: http://localhost:8000
   - Copy your API Key from Settings.
   - AppTransverser configuration:
     - `MOBSF_API_URL`: `http://localhost:8000`
     - `MOBSF_API_KEY`: your key

6. Test and run analysis
```powershell
python run_cli.py --test-mobsf-connection
python run_cli.py --run-mobsf-analysis
```

## 5) PCAPDroid (Optional: Traffic Capture)
PCAPDroid captures device network traffic. Install on your Android device (F-Droid or official sources).

- Steps:
  1. Install PCAPDroid on the device and open the app.
  2. Enable “Remote control” / REST API in PCAPDroid and generate an API key.
  3. Set `PCAPDROID_API_KEY` in `.env`.
  4. In app config, enable traffic capture:
     - `ENABLE_TRAFFIC_CAPTURE`: true

- Notes:
  - PCAPDroid may use a local VPN method if the device is not rooted.
  - Ensure the device is connected and accessible via ADB for capture coordination.

## 6) Project Setup
```powershell
# Clone and create venv
git clone <repository-url>
cd appium-traverser-master-arbeit
py -3 -m venv .venv
\.venv\Scripts\Activate.ps1

# Install Python dependencies
pip install -r requirements.txt

# Create .env and set any provider/service keys
Copy-Item .env.example .env
# Edit .env to add GEMINI_API_KEY / OPENROUTER_API_KEY / OLLAMA_BASE_URL / PCAPDROID_API_KEY / MOBSF_API_KEY

# Start Appium in another terminal
appium --relaxed-security
```

## 7) Optional: Ollama (Local AI)
Install Ollama for local models (including vision-capable ones). See the “Using Ollama with Vision Support” section in the main README for details.

---

# Full CLI Command Reference

Run commands from the project root with venv activated:
```powershell
python run_cli.py <options>
```

## General Options
- `-v, --verbose` — Enable DEBUG logging.
- `--force-rescan` — Force app rescan when scanning.

## App Management
- `--scan-all-apps` — Scan device and cache ALL installed apps (no AI filtering).
- `--scan-health-apps` — Scan device and cache AI-filtered HEALTH apps.
- `--list-all-apps` — List all apps from the latest all-apps cache.
- `--list-health-apps` — List health apps from the latest health-filtered cache.
- `--select-app ID_OR_NAME` — Select app by 1-based index or name/package substring.
- `--show-selected-app` — Display the currently selected app information (name, package, and activity).

## Crawler Control
- `--start` — Start the crawler.
- `--stop` — Signal the crawler to stop.
- `--pause` — Signal the running crawler to pause.
- `--resume` — Signal a paused crawler to resume.
- `--status` — Show crawler status.
- `--precheck-services` — Run pre-crawl validation (Appium, provider services, API keys, target app).
- `--annotate-offline-after-run` — After crawler exits, run offline UI annotator to overlay bounding boxes on screenshots and generate a gallery (used with --start).

## Configuration Management
- `--show-config [FILTER]` — Show configuration (optionally filter by key substring).
- `--set-config K=V` — Set configuration values; can be repeated. Examples:
  - Set a boolean: `--set-config CONTINUE_EXISTING_RUN=true`
  - Set an integer: `--set-config MAX_CRAWL_STEPS=50`
  - Set a list via JSON: `--set-config ALLOWED_EXTERNAL_PACKAGES="[\"requests\",\"pandas\"]"`
  - Set focus areas via JSON: `--set-config FOCUS_AREAS="[{\"title\":\"Location\",\"enabled\":true}]"`

## Analysis Workflow
- `--list-analysis-targets` — List app packages with available crawl databases.
- `--list-runs-for-target --target-index N` — List runs by target index.
- `--list-runs-for-target --target-app-package PKG` — List runs by package.
- `--generate-analysis-pdf --target-index N [--pdf-output-name NAME.pdf]` — Generate PDF for latest run.
- `--generate-analysis-pdf --target-app-package PKG [--pdf-output-name NAME.pdf]` — Generate PDF.
- `--print-analysis-summary --target-index N` — Print summary metrics for latest run.
- `--print-analysis-summary --target-app-package PKG` — Print summary.

## MobSF Integration
- `--test-mobsf-connection` — Test MobSF connectivity using `MOBSF_API_URL` and `MOBSF_API_KEY`.
- `--run-mobsf-analysis` — Run full MobSF workflow for the currently selected app.

## Focus Areas Management
- `--list-focus-areas` — Display configured privacy focus areas.
- `--enable-focus-area ID_OR_NAME` — Enable by index or name substring.
- `--disable-focus-area ID_OR_NAME` — Disable by index or name substring.
- `--move-focus-area --from-index N --to-index M` — Reorder areas (1-based indices).

---

## AI Providers

- `--refresh-openrouter-models` — Fetch latest OpenRouter models and refresh the local cache (background). Requires `OPENROUTER_API_KEY` in `.env`. Writes to `output_data/cache/openrouter_models.json`.
- `--list-openrouter-models` — List available OpenRouter models from the local cache.
- `--list-openrouter-models --free-only` — List only free models (overrides OPENROUTER_SHOW_FREE_ONLY config).
- `--list-openrouter-models --all` — List all models (overrides OPENROUTER_SHOW_FREE_ONLY config).
- `--select-openrouter-model ID_OR_NAME` — Select an OpenRouter model by 1-based index or name/ID fragment. Automatically sets AI_PROVIDER to "openrouter".
- `--show-openrouter-selection` — Show the currently selected OpenRouter model details.

### OpenRouter Model Management Workflow

1. First, refresh the model cache (requires `OPENROUTER_API_KEY` in `.env`):
   ```powershell
   python run_cli.py --refresh-openrouter-models
   ```

2. List available models:
   ```powershell
   # List all models (respects OPENROUTER_SHOW_FREE_ONLY config)
   python run_cli.py --list-openrouter-models
   
   # List only free models (overrides config)
   python run_cli.py --list-openrouter-models --free-only
   
   # List all models regardless of config (overrides config)
   python run_cli.py --list-openrouter-models --all
   ```

3. Select a model by index or name:
   ```powershell
   # Select by index (1-based)
   python run_cli.py --select-openrouter-model 1
   
   # Or select by name/ID fragment
   python run_cli.py --select-openrouter-model "gpt-4"
   ```

4. Verify your selection:
   ```powershell
   python run_cli.py --show-openrouter-selection
   ```

### Model Pricing and Warnings

- Free models are marked with `[FREE]` in the listing
- Paid models will show a warning when selected if `OPENROUTER_NON_FREE_WARNING` is enabled
- To disable paid model warnings: `python run_cli.py --set-config OPENROUTER_NON_FREE_WARNING=false`
- To show only free models by default: `python run_cli.py --set-config OPENROUTER_SHOW_FREE_ONLY=true`

# Pre-Crawl Checklist

Use the CLI to validate setup before starting:
```powershell
python run_cli.py --precheck-services
```
You should see green checks for Appium, provider services (e.g., Ollama), required API keys, and a selected target app.
