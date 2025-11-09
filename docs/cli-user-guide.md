# CLI User Guide

This guide explains how to use the command-line interface (CLI) for the Appium Traverser project.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installing ADB](#installing-adb)
- [Starting Required Services](#starting-required-services)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
  - [Device Management](#device-management)
  - [App Management](#app-management)
  - [Crawler Control](#crawler-control)
  - [Configuration](#configuration)
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
- Node.js & npm (for Appium and MCP server)
- Appium installed with a compatible driver (e.g. uiautomator2)
- Android SDK with ADB on PATH (see [Installing ADB](#installing-adb))
- API keys (set in environment or .env):
  - `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_BASE_URL` (for AI providers)
  - `MOBSF_API_KEY`, `PCAPDROID_API_KEY` (optional, for additional features)

## Installing ADB

1. Download [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools) and extract to `C:\platform-tools\`
2. Add to PATH (PowerShell as Administrator):
   ```powershell
   $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
   [Environment]::SetEnvironmentVariable("Path", "$currentPath;C:\platform-tools", "User")
   $env:Path += ";C:\platform-tools"
   ```
3. Verify: Restart PowerShell and run `adb version`
4. Enable USB debugging on your Android device (Settings → Developer options)

## Starting Required Services

Start these services in separate terminals before using the CLI:

### Appium Server (port 4723)
```powershell
npx appium -p 4723
```

### MCP Server (port 3000)
```powershell
cd appium-mcp-server
npm install          # First time only
npm run build        # First time or after changes
npm run start:http   # Start server
# Or use: npm run dev  # For development with auto-reload
```

Verify services: `python run_cli.py precheck-services`

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
   MOBSF_API_KEY=your_key
   
   # Optional: For network traffic capture during app crawling
   PCAPDROID_API_KEY=your_key
   ```
   
   **Optional API Keys:**
   - **MOBSF_API_KEY**: Required if you want to perform static security analysis of Android applications using MobSF (Mobile Security Framework). This enables security scanning of APK files during analysis.
   - **PCAPDROID_API_KEY**: Required if you want to capture network traffic during app crawling. PCAPdroid is an Android app that captures network packets, useful for privacy and security testing.

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
python run_cli.py crawler start [--annotate-offline-after-run]  # Start the crawler (optionally run offline UI annotation after completion)
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
```

### Focus Areas (for privacy testing)
```powershell
python run_cli.py focus add "Look for Privacy Policies" --priority 1  # Add a focus area that the crawler should focus on exploring related pages of (e.g., "Privacy Policy", "Settings")
python run_cli.py focus list                                 # List all configured focus areas
python run_cli.py focus remove <id>                          # Remove a focus area by ID or name
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
python run_cli.py analysis generate-pdf --target-index 1     # Generate a PDF analysis report for a specific session 
```

**Note:** A "target" is a crawl session (a specific instance of crawling an app), not just the app itself. Each crawl creates a new session directory named `{device_id}_{app_package}_{timestamp}`, so if you crawl the same app multiple times, you'll have multiple targets - one for each crawl session.

## AI Model Management

The CLI supports three AI providers: **Gemini**, **OpenRouter**, and **Ollama**. Switch providers, list models, and select models for use across the application.

### Quick Commands

**Use provider flags (one-off):**
```powershell
python run_cli.py --provider ollama --model "llama3.2-vision" apps scan-all
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

### Gemini Commands

Requires `GEMINI_API_KEY` environment variable:
```powershell
python run_cli.py gemini refresh-models          # Refresh cache (use --no-wait for background)
python run_cli.py gemini list-models             # List models (use --no-refresh for cache only)
python run_cli.py gemini select-model <index_or_name>  # Select model
python run_cli.py gemini show-selection          # Show current selection
python run_cli.py gemini show-model-details      # Show detailed info (vision support, token limits, etc.)
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
   python run_cli.py crawler start --annotate-offline-after-run
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
   - `annotated_screenshots/` - AI-annotated (if enabled)
   - `database/` - Crawl data
   - `logs/` - Crawl logs
   - `reports/` - Analysis reports

6. **Generate report:**
   ```powershell
   python run_cli.py analysis generate-pdf --target-index 1
   ```

## Troubleshooting

### Service Issues
- **Service not available:** Ensure Appium (port 4723) and MCP server (port 3000) are running
- **Port 3000 in use (Windows):** `netstat -ano | findstr :3000` then `taskkill /PID <PID> /F`
- **MCP build errors:** `cd appium-mcp-server && npm run clean && npm install && npm run build`
- **MCP won't start:** Check `appium-mcp-server/mcp-server.log`, verify Node.js >= 18.0.0

### Device Issues
- **No device found:** Connect device via USB, enable USB debugging, run `adb devices`
- **ADB not found:** See [Installing ADB](#installing-adb) section

### App/Crawler Issues
- **No app selected:** Run `python run_cli.py apps scan-all` then `apps select <index>`
- **Crawler not starting:** Check Appium/MCP server logs, verify device connection, check status with `crawler status`

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
- Crawler can be paused/resumed during execution

## Additional Resources

- GUI user guide: `docs/gui-user-guide.md`
- Main project README: `README.md`
