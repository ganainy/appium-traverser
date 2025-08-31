# Redirect script for agent tests
# This file redirects to the actual script in the tests directory

# Get the script path and construct the path to the tests directory
$scriptPath = $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptPath
$testScriptPath = Join-Path $rootDir "tests\run_agent_tests.ps1"

# Forward all arguments to the actual script
$argString = $args -join " "
$command = "& '$testScriptPath' $argString"

# Execute the command
Write-Host "Redirecting to $testScriptPath"
& $testScriptPath @args

# Remove the terminating command if it exists
Remove-Item Function:\deactivate -ErrorAction SilentlyContinue

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
    Write-Host ".\run_agent_tests.ps1 -ApiKey 'your-api-key-here'" -ForegroundColor Yellow
}

# Deactivate the virtual environment when done
deactivate
