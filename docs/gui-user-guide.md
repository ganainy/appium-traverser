# GUI User Guide

This guide explains how to use the Graphical User Interface (GUI) for the Appium Traverser project. The GUI is intended for general users who prefer an interactive experience.

## Prerequisites

- Python 3.12 (use a virtual environment) - Download from [Python 3.12.0 release page](https://www.python.org/downloads/release/python-3120/)
- Node.js & npm (required to install and run Appium and drivers)
- PySide6 or PyQt6 (GUI runtime)
- Appium installed and a compatible driver (e.g. uiautomator2)
- Android SDK with ADB available on PATH (see [Installing ADB](#installing-adb) below)
- Optional services depending on features:
  - Ollama (for using local AI models)
  - MobSF (for static analysis of APKs)
  - PCAPdroid (for traffic capture on device)
- API keys / environment variables (set these in your environment or a .env file as needed):
  - GEMINI_API_KEY (for Gemini provider)
  - OPENROUTER_API_KEY (for OpenRouter provider)
  - OLLAMA_BASE_URL (for Ollama; e.g. http://localhost:11434)
  - MOBSF_API_KEY (if MobSF analysis is enabled)
  - PCAPDROID_API_KEY (if PCAPdroid traffic capture is enabled)

## Installing ADB

ADB (Android Debug Bridge) is required to communicate with Android devices.

1. **Download and extract:** Get [Android SDK Platform Tools](https://developer.android.com/tools/releases/platform-tools) and extract to `C:\platform-tools\`

2. **Add to PATH (PowerShell as Administrator):**
   ```powershell
   $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
   [Environment]::SetEnvironmentVariable("Path", "$currentPath;C:\platform-tools", "User")
   $env:Path += ";C:\platform-tools"
   ```

3. **Verify:** Restart PowerShell and run `adb version`

4. **Enable USB debugging on your Android device:**
   - On your Android device, go to Settings → About phone
   - Tap "Build number" 7 times to enable Developer options
   - Go back to Settings → Developer options
   - Enable "USB debugging"
   - Connect your device via USB and authorize the computer when prompted
   - Verify connection: `adb devices` should show your device

## Quick start (Windows PowerShell example)

1. Clone and set up project:
```powershell
git clone <repository-url>
cd appium-traverser-master-arbeit
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

2. Configure environment (.env) with required API keys if applicable.

3. **Start required services:**
   - **Appium Server** (in a separate terminal):
     ```powershell
     npx appium -p 4723 --relaxed-security
     ```

4. Launch the UI:
```powershell
python run_ui.py
```

## Key UI areas

- Main window
  - Status bar: shows crawler status and last messages
  - Action history: chronological list of actions executed by the crawler
  - Screenshot pane: displays current screenshot captured during crawl
  - Progress bar: indicates crawl progress (steps or time)
  - Controls: Start, Stop, Pause, Resume crawler buttons

- Configuration panel
  - Configure AI provider, model, crawl mode (steps/time), and other runtime settings
  - Save and auto-save settings to SQLite-backed user config store

- Health App Scanner
  - Scan installed apps and filter for health-related targets
  - Select an app to use as the crawl target

- Reports & Analysis
  - Generate PDF reports for completed crawls
  - View analysis runs and target summaries

- Allowed External Packages
  - Manage external packages that the crawler can interact with outside the main target app
  - Add, remove, edit, and clear packages with validation
  - Packages are persisted in the configuration and shared between GUI and CLI

## Validation & Pre-crawl checks

Before starting a crawl, the UI performs validation checks:
- Appium server reachable (/status)
- Required API keys present (Gemini/OpenRouter/MobSF/PCAPdroid as configured)
- Ollama availability (HTTP API check and subprocess fallback)
- Target app selected

If checks fail, the UI shows blocking issues (❌) or warnings (⚠️). You can still force-start the crawler but stability may be affected.

## Starting and controlling a crawl

- Use the Start button to launch the crawler. The UI will:
  - Validate dependencies (AI provider tools)
  - Prepare output session directories
  - Launch the crawler process as a separate Python process and stream its output
  - Display step updates, actions, screenshots, and status in real-time

- Use Stop to request graceful shutdown (writes a shutdown flag file). A timer will force-kill the process if it doesn't exit.

- Use Pause/Resume where supported by the orchestrator.


## Tips

- Use the pre-crawl validation button to diagnose missing services before starting a crawl.
- Use the GUI to visually inspect action history and screenshots for faster debugging and analysis.
- Configuration changes are saved to a SQLite-backed store; keep settings consistent across UI and CLI.

## Where to find more

- CLI user guide: docs/cli-user-guide.md
- Main project README: README.md
