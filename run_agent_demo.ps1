# Redirect script for agent demo
# This file redirects to the actual script in the tests directory

# Get the script path and construct the path to the tests directory
$scriptPath = $MyInvocation.MyCommand.Path
$rootDir = Split-Path -Parent $scriptPath
$testScriptPath = Join-Path $rootDir "tests\run_agent_demo.ps1"

# Forward all arguments to the actual script
$argString = $args -join " "
$command = "& '$testScriptPath' $argString"

# Execute the command
Write-Host "Redirecting to $testScriptPath"
& $testScriptPath @args

# Remove the terminating command if it exists
Remove-Item Function:\deactivate -ErrorAction SilentlyContinue

if ($Screenshot) {
    $command += " --screenshot `"$Screenshot`""
}

if ($Xml) {
    $command += " --xml `"$Xml`""
}

# Run the command
Write-Host "Running: $command"
Invoke-Expression $command

# Deactivate the virtual environment when done
deactivate
