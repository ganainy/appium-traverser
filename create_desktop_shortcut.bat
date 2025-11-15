@echo off
REM Batch file to create desktop shortcut - just double-click this file!

echo Creating desktop shortcut for Appium Traverser ...
echo.

REM Run the PowerShell script
powershell.exe -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1"

if errorlevel 1 (
    echo.
    echo An error occurred. Press any key to exit...
    pause >nul
)



