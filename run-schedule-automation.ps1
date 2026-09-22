# Wrapper invoked by Windows Task Scheduler every Monday at 10:00 AM.
# Closes any running Edge windows first: launching Edge with a persistent
# user profile fails if that same profile is already open elsewhere, and an
# unattended scheduled task has no way to prompt you to close it yourself.
# Set CLOSE_EXISTING_EDGE=false as an environment variable on the scheduled
# task if you'd rather the run fail than have your open Edge windows closed.

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if ($env:CLOSE_EXISTING_EDGE -ne 'false') {
    $edgeProcesses = Get-Process msedge -ErrorAction SilentlyContinue
    if ($edgeProcesses) {
        Write-Output "Closing existing Edge windows so the automation can reuse your profile..."
        Stop-Process -Name msedge -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 3
    }
}

$logDir = Join-Path $scriptDir 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "run-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"

node schedule-automation.js *>> $logFile
exit $LASTEXITCODE
