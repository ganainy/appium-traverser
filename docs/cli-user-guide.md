# CLI User Guide

This guide explains how to use the command-line interface (CLI) for the Appium Traverser project.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installing Java](#installing-java)
- [Installing Android SDK and ADB](#installing-android-sdk-and-adb)
- [Starting Required Services](#starting-required-services)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
  - [Device Management](#device-management)
  - [App Management](#app-management)
  - [Crawler Control](#crawler-control)
  - [Configuration](#configuration)
  - [Actions](#actions)
  - [Prompts](#prompts)
  - [Focus Areas (for privacy testing)](#focus-areas-for-privacy-testing)
  - [External Packages](#external-packages)
  - [Analysis and Reporting](#analysis-and-reporting)
- [AI Model Management](#ai-model-management)
  - [Quick Commands](#quick-commands)
  - [Ollama Commands](#ollama-commands)
  - [OpenRouter Commands](#openrouter-commands)
  - [Gemini Commands](#gemini-commands)
  - [Tips](#tips)
- [Typical Workflow](#typical-workflow)
- [Troubleshooting](#troubleshooting)
  - [Service Issues](#service-issues)
  - [Device Issues](#device-issues)
  - [App/Crawler Issues](#appcrawler-issues)
  - [Configuration Issues](#configuration-issues)
  - [AI Model Issues](#ai-model-issues)
- [Tips](#tips-1)
- [Additional Resources](#additional-resources)

## Prerequisites

- Python 3.12 (use a virtual environment) - [Download](https://www.python.org/downloads/release/python-3120/)
- Java JDK 8 or later with JAVA_HOME set (see [Installing Java](#installing-java))
- Node.js & npm (for Appium)
- Appium installed with a compatible driver (e.g. uiautomator2)
- Android SDK with ADB on PATH and ANDROID_HOME set (see [Installing Android SDK and ADB](#installing-android-sdk-and-adb))
- API keys (set in environment or .env):
  - `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_BASE_URL` (for AI providers)
  - `MOBSF_API_KEY`, `PCAPDROID_API_KEY` (optional, for additional features)

### Virtual environment (required)

This project expects you to run the CLI from a Python virtual environment. Create and activate a venv from the project root. Examples:

- PowerShell (Windows):
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Installing Java

Appium requires Java to run. You need to install the Java Development Kit (JDK) and set the `JAVA_HOME` environment variable.

### Step 1: Download Java JDK

1. Download [Java JDK](https://www.oracle.com/java/technologies/downloads/#jdk25-windows) for Windows
   - Choose the **x64 Installer** for easiest installation
2. Run the installer and follow the installation wizard
3. Note the installation path (typically `C:\Program Files\Java\jdk-<version>`)

### Step 2: Set JAVA_HOME Environment Variable

To set it permanently for your user (Windows):

1. Open the **Environment Variables** window:
   - Press `Win + R`, type `sysdm.cpl`, and press Enter
   - Click the **Advanced** tab
   - Click **Environment Variables**

2. In the Environment Variables window:
   - Under **"User variables"** (for just your account), click **New**
   - For **Variable name**: enter `JAVA_HOME`
   - For **Variable value**: enter your JDK path, such as:
     ```
     C:\Program Files\Java\jdk-25
     ```
   - Click **OK** and close all dialog boxes

**Note:** Replace `jdk-25` with your actual JDK version folder name.

### Step 3: Add Java to PATH (Optional but Recommended)

To add Java's `bin` directory to your PATH for easier access:

1. Open the **Environment Variables** window (same as Step 2):
   - Press `Win + R`, type `sysdm.cpl`, and press Enter
   - Click the **Advanced** tab
   - Click **Environment Variables**

2. In the Environment Variables window:
   - Under **"User variables"**, find and select the **Path** variable
   - Click **Edit**
   - Click **New** to add a new entry
   - Enter the path to Java's `bin` directory, such as:
     ```
     C:\Program Files\Java\jdk-25\bin
     ```
   - Click **OK** on all dialog boxes to save

**Note:** Replace `jdk-25` with your actual JDK version folder name.

### Step 4: Verify Installation

1. Restart PowerShell to reload environment variables
2. Verify Java is accessible:
   ```powershell
   java -version
   javac -version
   ```
3. Verify JAVA_HOME is set:
   ```powershell
   echo $env:JAVA_HOME
   ```

## Installing Android SDK and ADB

### Step 1: Download Android Command Line Tools

1. Go to: [https://developer.android.com/studio#command-tools](https://developer.android.com/studio#command-tools)
2. Download **Command-line tools (Windows)** .zip file

### Step 2: Folder Setup

Extract the zip file to:

```
C:\Android\Sdk\cmdline-tools\latest\
```

**Important:** Inside the `latest` folder, there should be a `bin` folder. The structure should be:
```
C:\Android\Sdk\cmdline-tools\latest\bin\
```

### Step 3: Set ANDROID_HOME Environment Variable

Run in PowerShell:

```powershell
setx ANDROID_HOME "C:\Android\Sdk"
```

**Note:** You need to reopen PowerShell for the environment variable to take effect.

Then reopen PowerShell and verify:

```powershell
echo $env:ANDROID_HOME
```

### Step 4: Install SDK Components

1. Navigate to the tools folder:

```powershell
cd C:\Android\Sdk\cmdline-tools\latest\bin
```

2. Accept licenses:

```powershell
.\sdkmanager.bat --licenses
```

Press `y` to accept all licenses when prompted.

3. Install essential components:

```powershell
.\sdkmanager.bat "platform-tools" "platforms;android-34"
```

This will install:
- **platform-tools** - Contains ADB and other essential tools
- **platforms;android-34** - Android platform SDK (adjust version as needed)

### Step 5: Add to Windows PATH

Add platform-tools to your PATH so you can use `adb` from anywhere:

```powershell
setx PATH "$env:PATH;C:\Android\Sdk\platform-tools"
```

**Note:** You need to reopen PowerShell for PATH changes to take effect.

### Step 6: Verify Installation

1. **Reopen PowerShell** to reload environment variables
2. Verify ADB is accessible:
   ```powershell
   adb version
   ```
3. Verify ANDROID_HOME is set:
   ```powershell
   echo $env:ANDROID_HOME
   ```
4. Enable USB debugging on your Android device (Settings → Developer options)

✅ **Done!** Now you can use `adb`, `sdkmanager`, and all Android CLI tools anywhere.

### Step 7: Set Android SDK Path for Appium (Required)

Appium server requires `ANDROID_HOME` or `ANDROID_SDK_ROOT` to be set system-wide. Follow these steps:

#### 1. 🕵️‍♂️ Detect your Android SDK path

- **If you installed it manually** (as we just did), it should be:
  ```
  C:\Android\Sdk
  ```

- **If you installed it via Android Studio**, check:
  ```
  C:\Users\<YourUser>\AppData\Local\Android\Sdk
  ```

#### 2. ⚙️ Set the environment variables permanently

Open **PowerShell as Administrator**, then run:

```powershell
setx ANDROID_HOME "C:\Android\Sdk" /M
setx ANDROID_SDK_ROOT "C:\Android\Sdk" /M
```

**Note:** Replace `C:\Android\Sdk` with your actual SDK path if different.

The `/M` flag sets them system-wide, so Appium and Node.js can both access them.

#### 3. 🔄 Add tools to PATH

Still in PowerShell as Administrator:

```powershell
setx PATH "$env:PATH;C:\Android\Sdk\platform-tools;C:\Android\Sdk\cmdline-tools\latest\bin" /M
```

**Note:** Replace `C:\Android\Sdk` with your actual SDK path if different.

#### 4. 🔄 Restart Required

**Important:** You must restart your PC (or at least restart PowerShell and the Appium server) for these system-wide changes to take effect.

#### 5. ✅ Verify setup

Open a **new PowerShell** (after restart) and run:

```powershell
echo $env:ANDROID_HOME
echo $env:ANDROID_SDK_ROOT
adb version
```

You should see:
- Valid SDK path outputs for both `ANDROID_HOME` and `ANDROID_SDK_ROOT`
- ADB version information

If you see empty outputs, the environment variables weren't set correctly. Make sure you:
- Ran PowerShell as Administrator
- Used the `/M` flag for system-wide variables
- Restarted your PC or at least PowerShell

**Troubleshooting:** If Appium still can't find the Android SDK after setting these variables, ensure you've restarted the Appium server after setting the environment variables.

## Starting Required Services

Start these services in separate terminals before using the CLI:

### Appium Server (port 4723)
```powershell
#Run in seperate terminal and leave it running
npx appium -p 4723 --relaxed-security
```

Ensure the project's virtual environment is active before running CLI commands (see "Virtual environment" under Prerequisites).

```powershell
python run_cli.py precheck-services
```



## Quick Start

1. **Setup project:**
   ```powershell
   git clone <repository-url>
   cd appium-traverser
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Configure environment** (.env file):
   ```env
   # Required for AI providers (at least one)
   GEMINI_API_KEY=your_key
   OPENROUTER_API_KEY=your_key
   OLLAMA_BASE_URL=http://localhost:11434
   
   # Optional: For static security analysis of Android apps
   # MobSF must be installed and running. See: https://github.com/MobSF/Mobile-Security-Framework-MobSF
   MOBSF_API_KEY=your_key
   
   # Optional: For network traffic capture during app crawling
   PCAPDROID_API_KEY=your_key
   ```
   

3. **Basic workflow:**
   ```powershell
   python run_cli.py precheck-services    # Verify services
   python run_cli.py device list          # List devices
   python run_cli.py apps scan-all        # Scan apps
   python run_cli.py apps list-all        # List available apps
   python run_cli.py apps select 1        # Select app
   python run_cli.py gemini list-models   # List available models (or ollama/openrouter)
   python run_cli.py gemini select-model 1 # Select model (required for crawler start)
   python run_cli.py crawler start        # Start crawler
   ```

## CLI Commands

Note: Ensure the project's virtual environment is active before running CLI commands (see "Prerequisites → Virtual environment").

### Device Management
```powershell
python run_cli.py device list
python run_cli.py device select <device_id>
```

### App Management
```powershell
python run_cli.py apps scan-all       # Scan all installed apps (with AI health filtering)
python run_cli.py apps list-all       # List all apps from cache
python run_cli.py apps select <index_or_package> # e.g. python run_cli.py apps select 1
python run_cli.py apps show-selected  # Show currently selected app
```

### Crawler Control
```powershell
python run_cli.py crawler start [--generate-pdf]                # Start the crawler (optionally generate PDF report after completion)

# Feature flags for crawler start (all disabled by default):
python run_cli.py crawler start --enable-traffic-capture        # Enable PCAPdroid traffic capture during crawl
python run_cli.py crawler start --enable-video-recording        # Enable video recording during crawl
python run_cli.py crawler start --enable-mobsf-analysis         # Enable automatic MobSF analysis after crawl completes

# Combine multiple flags:
python run_cli.py crawler start --enable-traffic-capture --enable-video-recording --enable-mobsf-analysis
python run_cli.py crawler start --generate-pdf  # Generate PDF report after completion

python run_cli.py crawler stop                                   # Stop the crawler process
python run_cli.py crawler pause                                  # Pause the crawler process
python run_cli.py crawler resume                                 # Resume a paused crawler
python run_cli.py crawler status                                 # Show current crawler status (state, target app, output directory)
```

### Configuration
```powershell
python run_cli.py config show                    # Display current configuration (optionally filter by key name)
python run_cli.py config set MAX_CRAWL_STEPS=15  # Set configuration value (can set multiple: key1=value1 key2=value2)
python run_cli.py config set CRAWL_MODE=time     # Set crawl mode (e.g., 'time' for time-based crawling)

# With confirmation prompt
python run_cli.py config reset

# Skip confirmation
python run_cli.py config reset --yes
```

### Actions

Actions define what the crawler can do during app exploration (e.g., click, scroll, swipe). You can customize the available actions and their descriptions to guide the AI agent's decision-making.

```powershell
python run_cli.py actions list                                    # List all configured crawler actions
python run_cli.py actions add "swipe_up" --description "Swipe up to scroll"  # Add a new action
python run_cli.py actions edit 1 --description "Updated description"         # Edit an action by ID or name
python run_cli.py actions remove "swipe_up"                       # Remove an action by ID or name
```

### Prompts

Prompt templates control how the AI agent makes decisions during crawling. You can customize the prompts used for action decisions and system instructions to fine-tune the crawler's behavior.

```powershell
python run_cli.py prompts list                                                           # List all configured prompt templates
python run_cli.py prompts add "ACTION_DECISION_PROMPT" --template "Your prompt template here"  # Add a new prompt template
python run_cli.py prompts edit "ACTION_DECISION_PROMPT" --template "Updated template"          # Edit a prompt template
python run_cli.py prompts remove "ACTION_DECISION_PROMPT"                                     # Remove a prompt template
```

### Focus Areas (for privacy testing)

Focus areas help guide the crawler to prioritize exploring specific types of pages or content during crawling. This is particularly useful for privacy testing, where you want the crawler to actively seek out privacy-related pages (e.g., "Privacy Policy", "Settings", "Account Settings", "Data Usage") rather than just randomly exploring the app.

```powershell
python run_cli.py focus add "Privacy Policy" --description "Look for privacy policy pages" --priority 1  # Add a focus area
python run_cli.py focus list                                 # List all configured focus areas
python run_cli.py focus edit <id_or_name> --title "New Title" --description "Updated description"  # Edit a focus area
python run_cli.py focus remove <id_or_name>                  # Remove a focus area by ID or name
```

### External Packages
```powershell
python run_cli.py packages list                    # List all allowed external packages (apps the crawler can interact with)
python run_cli.py packages add com.example.app     # Add a package to the allowed external packages list
python run_cli.py packages remove com.example.app  # Remove a package from the allowed external packages list
```

### Analysis and Reporting
```powershell
python run_cli.py analysis list-targets                      # List all available analysis targets (crawl sessions: each target is a specific crawl of an app with stored data)
python run_cli.py analysis list-runs --target-index 1        # List all crawl runs for a specific target (by index)
python run_cli.py analysis generate-analysis-pdf --target-index 1     # Generate a PDF analysis report for a specific session (target-based)

# Session-based commands (use latest session if --session-dir not provided):
python run_cli.py analysis generate-pdf                      # Generate PDF report for latest session
python run_cli.py analysis generate-pdf --session-dir <path> # Generate PDF report for specific session
```

**Note:** A "target" is a crawl session (a specific instance of crawling an app), not just the app itself. Each crawl creates a new session directory named `{device_id}_{app_package}_{timestamp}`, so if you crawl the same app multiple times, you'll have multiple targets - one for each crawl session.

**Session-based commands:** The `generate-pdf` command can work on a specific session directory or automatically use the latest session (by modification timestamp) if `--session-dir` is not provided.

## AI Model Management

The CLI supports three AI providers: **Gemini**, **OpenRouter**, and **Ollama**. Switch providers, list models, and select models for use across the application.

### Quick Commands

**Use provider flags (one-off):**
```powershell
python run_cli.py --provider ollama --model "llama3.2-vision" apps scan-all
```
```

### Ollama Commands

Requires Ollama service running (`ollama serve`):
```powershell
python run_cli.py ollama refresh-models          # Refresh cache (use --no-wait for background)
python run_cli.py ollama list-models             # List models (use --no-refresh for cache only)
python run_cli.py ollama select-model <index_or_name>  # Select model
python run_cli.py ollama show-selection          # Show current selection
python run_cli.py ollama show-model-details      # Show detailed info (vision support, etc.)
```
```

### OpenRouter Commands

Requires `OPENROUTER_API_KEY` environment variable:
```powershell
python run_cli.py openrouter refresh-models      # Refresh cache (use --wait to wait)
python run_cli.py openrouter list-models         # List models (--free-only or --all)
python run_cli.py openrouter select-model <index_or_name>  # Select model
python run_cli.py openrouter show-selection      # Show current selection
python run_cli.py openrouter show-model-details  # Show detailed info (pricing, vision, etc.)
python run_cli.py openrouter configure-image-context --enable|--disable  # Configure vision
```
```

### Gemini Commands

Requires `GEMINI_API_KEY` environment variable:
```powershell
python run_cli.py gemini refresh-models          # Refresh cache (use --no-wait for background)
python run_cli.py gemini list-models             # List models (use --no-refresh for cache only)
python run_cli.py gemini select-model <index_or_name>  # Select model
python run_cli.py gemini show-selection          # Show current selection
python run_cli.py gemini show-model-details      # Show detailed info (vision support, token limits, etc.)
```
```

### Tips

- **Ollama:** Ensure service is running before listing/selecting models
- **OpenRouter/Gemini:** Set `OPENROUTER_API_KEY` or `GEMINI_API_KEY` environment variables
- Model selections persist across sessions; use `--provider`/`--model` flags for one-off commands
- Vision support is automatically detected using hybrid detection (metadata → CLI → patterns)

## Typical Workflow

1. **Check services and devices:**
   ```powershell
   python run_cli.py precheck-services
   python run_cli.py device list
   ```

2. **Select AI provider and model:**
   > **Note:** Model selection is **required** for `crawler start` (AI-powered crawling). It's **optional** for `apps scan-all` (works without AI, but AI filtering will be skipped). All other commands don't require a model.
   
   ```powershell
   # For Ollama
   python run_cli.py ollama list-models
   python run_cli.py ollama select-model 1
   
   # For OpenRouter
   python run_cli.py openrouter list-models
   python run_cli.py openrouter select-model 1
   
   # For Gemini
   python run_cli.py gemini list-models
   python run_cli.py gemini select-model 1
   
   # Or use flags for one-off commands with any provider
   python run_cli.py --provider ollama --model "llama3.2-vision" apps scan-all
   ```

3. **Discover and select app:**
   ```powershell
   python run_cli.py apps scan-all
   python run_cli.py apps list-all
   python run_cli.py apps select 1
   ```

4. **Start crawler:**
   ```powershell
   # Basic start
   python run_cli.py crawler start
   
   # With optional features enabled
   python run_cli.py crawler start --enable-traffic-capture --enable-video-recording --enable-mobsf-analysis
   
   # With PDF generation after completion
   python run_cli.py crawler start --generate-pdf
   ```

5. **Monitor and control:**
   ```powershell
   python run_cli.py crawler status  # Check status
   python run_cli.py crawler pause   # Pause if needed
   python run_cli.py crawler resume  # Resume
   ```

6. **View results:**
   Results are in: `output_data/<device_id>_<app_package>_<timestamp>/`
   - `screenshots/` - Captured screenshots
   - `database/` - Crawl data
   - `logs/` - Crawl logs
   - `reports/` - Analysis reports
   - `traffic_captures/` - PCAP files (if traffic capture enabled)
   - `video/` - Video recordings (if video recording enabled)
   - `mobsf_scan_results/` - MobSF analysis results (if MobSF analysis enabled)



## Troubleshooting

### Service Issues
- **Service not available:** Ensure Appium (port 4723) is running

### Device Issues
- **No device found:** Connect device via USB, enable USB debugging, run `adb devices`
- **ADB not found:** See [Installing ADB](#installing-adb) section

### App/Crawler Issues
- **No app selected:** Run `python run_cli.py apps scan-all` then `apps select <index>`
- **Crawler not starting:** Check Appium server logs, verify device connection, check status with `crawler status`

### Configuration Issues
- **AI provider not configured:** Select a model using provider-specific commands (e.g., `python run_cli.py gemini select-model 1`), which automatically sets the provider.
- **Missing API keys:** Set environment variables: `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, etc.
- **Provider validation errors:** Use `--provider` (gemini/openrouter/ollama) and `--model` if needed

### AI Model Issues
- **Ollama models not found:** Ensure Ollama service is running (`ollama serve`), then run `python run_cli.py ollama refresh-models`
- **Ollama connection failed:** Check `OLLAMA_BASE_URL` environment variable (default: `http://localhost:11434`)
- **OpenRouter models not loading:** Verify `OPENROUTER_API_KEY` is set, then run `python run_cli.py openrouter refresh-models --wait`
- **Model selection not persisting:** Check that you're using `select-model` command, not just `--model` flag (flag is for one-off commands)
- **Vision model not detected:** Run `python run_cli.py ollama show-model-details` or `python run_cli.py openrouter show-model-details` to verify vision support
- **No models available:** For Ollama, ensure models are installed (`ollama pull <model-name>`). For OpenRouter, check API key and network connection

## Tips

- Use `-v` or `--verbose` for detailed logging
- Use `python run_cli.py --help` to see all available commands
- Configuration changes persist in the database
- **Traffic Capture:** Requires PCAPdroid app installed on device and `PCAPDROID_API_KEY` set (optional but recommended)
- **Video Recording:** Uses Appium's built-in screen recording; videos are saved as MP4 files
- **MobSF Analysis:** Requires MobSF server running and `MOBSF_API_KEY` set; runs automatically after crawl completes if enabled. See [official MobSF installation guide](https://github.com/MobSF/Mobile-Security-Framework-MobSF) for setup instructions.

## Additional Resources

- GUI user guide: `docs/gui-user-guide.md`
- Main project README: `README.md`
