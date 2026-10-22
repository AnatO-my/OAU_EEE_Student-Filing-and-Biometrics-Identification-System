param(
    [string]$OutputPath,
    [string]$ClientDirectory,
    [switch]$VerifyRestore
)
$ErrorActionPreference = "Stop"
$projectDirectory = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectDirectory ".venv\Scripts\python.exe"
if (-not $OutputPath) {
    $OutputPath = Join-Path $projectDirectory ("backups\aiven-" + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffffffZ') + ".dump")
}
if (-not $ClientDirectory) {
    $ClientDirectory = Join-Path $projectDirectory "private-data\postgres18-aiven-client\bin"
}
if (-not (Test-Path -LiteralPath (Join-Path $ClientDirectory "pg_dump.exe"))) {
    throw "Prepare backup utilities first: .\.venv\Scripts\python.exe tools\prepare_postgres_runtime.py --aiven-client"
}
$backupArguments = @((Join-Path $projectDirectory "tools\postgres_backup.py"), "--pg-bin", $ClientDirectory, "backup")
if ($OutputPath) { $backupArguments += @("--output", $OutputPath) }
& $python @backupArguments
if ($LASTEXITCODE -ne 0) { throw "PostgreSQL backup failed; no completed backup was accepted." }
if ($VerifyRestore) {
    & (Join-Path $PSScriptRoot "restore-postgres-test.ps1") -Archive $OutputPath
}
