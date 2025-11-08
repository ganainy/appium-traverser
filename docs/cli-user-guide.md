# CLI User Guide

This guide explains how to use the command-line interface (CLI) for the Appium Traverser project.

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
   GEMINI_API_KEY=your_key
   OPENROUTER_API_KEY=your_key
   OLLAMA_BASE_URL=http://localhost:11434
   ```

3. **Basic workflow:**
   ```powershell
   python run_cli.py precheck-services    # Verify services
   python run_cli.py device list          # List devices
   python run_cli.py apps scan-all        # Scan apps
   python run_cli.py apps list-all        # List available apps
   python run_cli.py apps select 1        # Select app
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
python run_cli.py crawler start [--annotate-offline-after-run]
python run_cli.py crawler stop
python run_cli.py crawler pause
python run_cli.py crawler resume
python run_cli.py crawler status
```

### Configuration
```powershell
python run_cli.py config show
python run_cli.py config set MAX_CRAWL_STEPS=15
python run_cli.py config set CRAWL_MODE=time
```

### Focus Areas (for privacy testing)
```powershell
python run_cli.py focus add "Privacy Policy" --priority 1
python run_cli.py focus list
python run_cli.py focus remove <id>
```

### External Packages
```powershell
python run_cli.py packages list
python run_cli.py packages add com.example.app
python run_cli.py packages remove com.example.app
```

### Analysis and Reporting
```powershell
python run_cli.py analysis list-targets
python run_cli.py analysis list-runs --target-index 1
python run_cli.py analysis generate-pdf --target-index 1
```

## Choosing an AI Provider

Specify provider via CLI flags or environment variables:
```powershell
python run_cli.py --provider ollama --model "llama3.2-vision" apps scan-all
```

Providers: `gemini`, `openrouter`, `ollama`. If not specified, CLI reads from environment variables or `user_config.json`.

## Typical Workflow

1. **Check services and devices:**
   ```powershell
   python run_cli.py precheck-services
   python run_cli.py device list
   ```

2. **Discover and select app:**
   ```powershell
   python run_cli.py apps scan-all
   python run_cli.py apps list-all
   python run_cli.py apps select 1
   ```

3. **Start crawler:**
   ```powershell
   python run_cli.py crawler start --annotate-offline-after-run
   ```

4. **Monitor and control:**
   ```powershell
   python run_cli.py crawler status  # Check status
   python run_cli.py crawler pause   # Pause if needed
   python run_cli.py crawler resume  # Resume
   ```

5. **View results:**
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
- **Port 3000 in use (Linux/Mac):** `lsof -i :3000` then `kill -9 <PID>`
- **MCP build errors:** `cd appium-mcp-server && npm run clean && npm install && npm run build`
- **MCP won't start:** Check `appium-mcp-server/mcp-server.log`, verify Node.js >= 18.0.0

### Device Issues
- **No device found:** Connect device via USB, enable USB debugging, run `adb devices`
- **ADB not found:** See [Installing ADB](#installing-adb) section

### App/Crawler Issues
- **No app selected:** Run `python run_cli.py apps scan-all` then `apps select <index>`
- **Crawler not starting:** Check Appium/MCP server logs, verify device connection, check status with `crawler status`

### Configuration Issues
- **AI provider not configured:** Set `$env:AI_PROVIDER="gemini"` or use `--provider` flag
- **Missing API keys:** Set environment variables: `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, etc.
- **Provider validation errors:** Use `--provider` (gemini/openrouter/ollama) and `--model` if needed

## Tips

- Use `-v` or `--verbose` for detailed logging
- Use `python run_cli.py --help` to see all available commands
- Configuration changes persist in the database
- Crawler can be paused/resumed during execution

## Additional Resources

- GUI user guide: `docs/gui-user-guide.md`
- Main project README: `README.md`
