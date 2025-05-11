# Start Appium in a new window
Write-Host "Starting Appium server in a new window..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "appium --allow-insecure adb_shell"

# Activate the virtual environment
Write-Host "Activating virtual environment..."
.\.venv\Scripts\Activate.ps1

# Change to the script directory
Write-Host "Changing directory to traverser_ai_api..."
cd traverser_ai_api

# Run the UI controller
Write-Host "Starting UI controller..."
python -m ui_controller

# Optional: Pause at the end if the script closes too quickly
# Read-Host "Press Enter to close this window..."
