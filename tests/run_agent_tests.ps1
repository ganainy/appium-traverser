# ==========================================================================
# PowerShell script to run the Agent Assistant tests
# 
# This script runs the test suite for the Agent Assistant implementation.
# It supports running all tests or specific test methods with configurable
# verbosity. An API key is required for the full integration tests.
# ==========================================================================

param(
    [string]$ApiKey,
    [string]$Test,
    [switch]$Verbose
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
    $command = "python tests\run_agent_tests.py"

    if ($ApiKey) {
        $command += " --api-key `"$ApiKey`""
    }

    if ($Test) {
        $command += " --test $Test"
    }

    if ($Verbose) {
        $command += " -vv"
    }
    else {
        $command += " -v"
    }

    # Run the command
    Write-Host "Running: $command"
    Invoke-Expression $command

    # Display message about skipping tests
    if (-not $ApiKey) {
        Write-Host "`nNOTE: No API key provided. Some tests will be skipped.`n" -ForegroundColor Yellow
        Write-Host "To run all tests including integration tests, use:" -ForegroundColor Yellow
        Write-Host ".\tests\run_agent_tests.ps1 -ApiKey 'your-api-key-here'" -ForegroundColor Yellow
    }
}
finally {
    # Deactivate the virtual environment when done
    if (Test-Path Function:\deactivate) {
        deactivate
    }

    # Return to the original directory
    Pop-Location
}
