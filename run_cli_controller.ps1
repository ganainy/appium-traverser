# PowerShell script to run the CLI controller
# Navigate to the traverser_ai_api directory and run the CLI controller

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$apiPath = Join-Path $scriptPath "traverser_ai_api"

Write-Host "Starting Appium Crawler CLI Controller..." -ForegroundColor Green
Write-Host "Working directory: $apiPath" -ForegroundColor Gray

# Change to the API directory
Set-Location $apiPath

# Run the CLI controller with all passed arguments
python cli_controller.py $args

# Return to original directory
Set-Location $scriptPath
