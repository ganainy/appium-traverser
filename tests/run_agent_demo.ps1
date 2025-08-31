# ==========================================================================
# PowerShell script to run the Agent Assistant demonstration
# 
# This script runs the demo_agent.py script with the provided API key and
# optional screenshot/XML inputs. It demonstrates the Agent Assistant's 
# ability to analyze UI screenshots and determine the next best action.
# ==========================================================================

param(
    [Parameter(Mandatory = $true)]
    [string]$ApiKey,
    [string]$Screenshot,
    [string]$Xml
)

# Get the current directory and project root
$scriptPath = $MyInvocation.MyCommand.Path
$testsDir = Split-Path -Parent $scriptPath
$projectRoot = Split-Path -Parent $testsDir

# Change to the project root directory
Push-Location $projectRoot

try {
    # Activate the virtual environment
    & .\.venv\Scripts\Activate.ps1

    # Build the command
    $command = "python tests\demo_agent.py --api-key `"$ApiKey`""

    if ($Screenshot) {
        $command += " --screenshot `"$Screenshot`""
    }

    if ($Xml) {
        $command += " --xml `"$Xml`""
    }

    # Run the command
    Write-Host "Running: $command"
    Invoke-Expression $command
}
finally {
    # Deactivate the virtual environment when done
    if (Test-Path Function:\deactivate) {
        deactivate
    }

    # Return to the original directory
    Pop-Location
}
