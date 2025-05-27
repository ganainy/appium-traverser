@echo off
REM Batch script to run the CLI controller
REM Navigate to the traverser_ai_api directory and run the CLI controller

echo Starting Appium Crawler CLI Controller...
cd /d "%~dp0\traverser_ai_api"
echo Working directory: %CD%

python -m cli_controller %*

cd /d "%~dp0"
