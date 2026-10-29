# Run from the terminal configured with private-data/aiven/configure.ps1.
# The Python supervisor inherits secrets in memory and stops only its own children.
[CmdletBinding()]
param(
    [switch]$EmailWorker,
    [switch]$TeachingNotifications,
    [switch]$CheckOnly,
    [ValidateRange(1,65535)][int]$BackendPort = 8000,
    [ValidateRange(1,65535)][int]$FrontendPort = 5175
)

$ErrorActionPreference = "Stop"
$localProjectRoot = Split-Path -Parent $PSScriptRoot
$localPythonPath = Join-Path $localProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $localPythonPath -PathType Leaf)) {
    throw 'Install the project Python environment in .venv first. See docs/local-laptop.md.'
}
$localLaunchArguments = @((Join-Path $PSScriptRoot 'run_local.py'))
$localLaunchArguments += @('--backend-port', [string]$BackendPort, '--frontend-port', [string]$FrontendPort)
if ($EmailWorker) { $localLaunchArguments += '--email-worker' }
if ($TeachingNotifications) { $localLaunchArguments += '--teaching-notifications' }
if ($CheckOnly) { $localLaunchArguments += '--check-only' }
& $localPythonPath @localLaunchArguments
if ($LASTEXITCODE -ne 0) {
    throw "Local application stopped with exit code $LASTEXITCODE."
}
