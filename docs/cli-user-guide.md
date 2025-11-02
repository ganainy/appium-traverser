# CLI User Guide

This guide explains how to use the command-line interface (CLI) for the Appium Traverser project. The CLI is intended for general users who prefer scripting or terminal-based workflows.

## Prerequisites

- Python 3.8+ (use a virtual environment)
- Node.js & npm (required to install and run Appium and drivers)
- Appium installed and a compatible driver (e.g. uiautomator2)
- Android SDK with ADB available on PATH
- Optional services depending on features:
  - Ollama (local models)
  - MobSF (binary analysis)
  - PCAPdroid (traffic capture on device)
- API keys / environment variables (set these in your environment or a .env file as needed):
  - GEMINI_API_KEY (for Gemini provider)
  - OPENROUTER_API_KEY (for OpenRouter provider)
  - OLLAMA_BASE_URL (for Ollama; e.g. http://localhost:11434)
  - MOBSF_API_KEY (if MobSF analysis is enabled)
  - PCAPDROID_API_KEY (if PCAPdroid traffic capture is enabled)

## Quick start (Windows PowerShell example)

1. Clone and set up project:
```powershell
git clone <repository-url>
cd appium-traverser-master-arbeit
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure environment (example .env entries):
```env
GEMINI_API_KEY=your_key
OPENROUTER_API_KEY=your_key
OLLAMA_BASE_URL=http://localhost:11434
```

3. Run the CLI:
```powershell
python run_cli.py apps scan-health
python run_cli.py apps select 1
python run_cli.py crawler start
```

Or if installed as a console script (optional):
```bash
traverser-cli apps scan-health
traverser-cli crawler start
```

## Choosing an AI provider

When launching the CLI you can specify an AI provider and (optionally) a model:

- CLI flags:
  - --provider (gemini, openrouter, ollama)
  - --model (provider-specific model alias)

If not provided, the CLI will read:
1. runtime options
2. environment variables (e.g., AI_PROVIDER)
3. a local user_config.json (created under the package directory)

Example:
```powershell
python run_cli.py --provider ollama --model "llama3.2-vision" apps scan-health
```

## Primary CLI workflows

### App management
Scan and list installed apps:
```powershell
python run_cli.py apps scan-health    # AI-filtered health apps
python run_cli.py apps scan-all       # All installed apps
python run_cli.py apps list-health
python run_cli.py apps select 1
python run_cli.py apps select "com.example.app"
```

### Crawler control
Start/stop/pause/resume the crawler:
```powershell
python run_cli.py crawler start [--annotate-offline-after-run]
python run_cli.py crawler stop
python run_cli.py crawler pause
python run_cli.py crawler resume
python run_cli.py crawler status
```

### Configuration
View and change runtime configuration:
```powershell
python run_cli.py config show
python run_cli.py config set MAX_CRAWL_STEPS=15
python run_cli.py config set CRAWL_MODE=time
```

### Focus areas
Manage focus/target areas for private-data scanning:
```powershell
python run_cli.py focus add "Privacy Policy" --priority 1
python run_cli.py focus list
python run_cli.py focus remove <id>
```

### Analysis and reporting
Generate reports and inspect analysis data:
```powershell
python run_cli.py analysis list-targets
python run_cli.py analysis list-runs --target-index 1
python run_cli.py analysis generate-pdf --target-index 1
```

## Common workflows (example)

1. Discover health apps:
```powershell
python run_cli.py apps scan-health
python run_cli.py apps list-health
```
2. Select target app:
```powershell
python run_cli.py apps select 1
```
3. Start crawler:
```powershell
python run_cli.py crawler start
```
4. After crawl, generate a PDF report:
```powershell
python run_cli.py analysis generate-pdf --target-index 1
```

## Troubleshooting

- Appium not reachable:
  - Ensure Appium is running: `appium` or use `appium --allow-insecure chromedriver_autodownload` as appropriate
  - Verify APPIUM_SERVER_URL in config or .env

- Device not listed:
  - Ensure adb is available and device is authorized: `adb devices`

- Missing API keys:
  - Set environment variables or update the local config store:
    - GEMINI_API_KEY, OPENROUTER_API_KEY, MOBSF_API_KEY, PCAPDROID_API_KEY

- Provider validation errors:
  - Check `--provider` value (must be one of gemini, openrouter, ollama)
  - Use `--model` to specify a compatible model when needed

- Permission or path issues on Windows:
  - Run PowerShell as Administrator for device and network access if required
  - Use the project virtual environment's python executable

## Tips

- Use `-v` or `--verbose` to enable more detailed CLI logging.
- Use `python run_cli.py --help` or `traverser-cli --help` to see available subcommands and flags.
- The CLI stores user preference in a local user_config.json under the package; passing flags overrides stored settings for the session.

## Where to find more

- GUI user guide: docs/gui-user-guide.md
- Main project README: README.md
