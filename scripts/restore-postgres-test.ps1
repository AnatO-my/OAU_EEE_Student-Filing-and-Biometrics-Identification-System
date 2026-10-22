param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [string]$RuntimeDirectory
)
$ErrorActionPreference = "Stop"
$projectDirectory = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectDirectory ".venv\Scripts\python.exe"
if (-not $RuntimeDirectory) {
    $RuntimeDirectory = Join-Path $projectDirectory "private-data\postgres18\bin"
}
$archivePath = (Resolve-Path -LiteralPath $Archive).Path
& $python (Join-Path $projectDirectory "tools\run_attendance_postgres_tests.py") `
    --pg-bin $RuntimeDirectory --skip-tests --restore-archive $archivePath
if ($LASTEXITCODE -ne 0) { throw "Isolated PostgreSQL restore verification failed; inspect the retained synthetic cluster logs." }
