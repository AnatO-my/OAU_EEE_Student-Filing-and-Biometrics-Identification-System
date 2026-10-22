# Apply reviewed local application migrations from the private Aiven terminal.
# Stop existing local servers/workers first. No student data is imported here.
[CmdletBinding()]
param([switch]$EmailWorker)

$ErrorActionPreference = 'Stop'
$registrationProjectRoot = Split-Path -Parent $PSScriptRoot
$registrationPython = Join-Path $registrationProjectRoot '.venv\Scripts\python.exe'
if ($env:DJANGO_SETTINGS_MODULE -ne 'config.postgres_settings' -or
    $env:POSTGRES_SSLMODE -ne 'verify-full' -or
    [string]::IsNullOrEmpty($env:POSTGRES_PASSWORD)) {
    throw 'Use the PowerShell terminal configured with private-data/aiven/configure.ps1 first. Keep the password private.'
}

Push-Location -LiteralPath $registrationProjectRoot
try {
    & $registrationPython -c "import socket,sys; ports=[p for p in (8000,5175) if socket.socket().connect_ex(('127.0.0.1',p))==0]; print('Stop the existing local servers with Ctrl+C before updating.' if ports else 'Local server ports are clear.'); sys.exit(bool(ports))"
    if ($LASTEXITCODE -ne 0) { throw 'The existing local application is still running. Stop its startup terminal, then retry.' }
    & $registrationPython manage.py check_database_connection
    if ($LASTEXITCODE -ne 0) { throw 'Database connection check failed; no migration was attempted.' }
    & $registrationPython manage.py migrate --plan
    if ($LASTEXITCODE -ne 0) { throw 'Migration planning failed; no migration was attempted.' }

    Write-Host 'Creating a new private backup and verifying restoration before the schema update...'
    & (Join-Path $PSScriptRoot 'backup-postgres.ps1') -VerifyRestore

    & $registrationPython manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) { throw 'Migration did not complete. Keep the backup and share the error; do not reset or delete migrations.' }
    & $registrationPython manage.py migrate --check
    if ($LASTEXITCODE -ne 0) { throw 'Migration verification failed.' }
    & $registrationPython manage.py check --database default
    if ($LASTEXITCODE -ne 0) { throw 'Database system checks failed.' }
    & $registrationPython manage.py check_database_connection
    if ($LASTEXITCODE -ne 0) { throw 'Final connection check failed.' }

    Write-Host 'Application schema is ready. Starting the local application; no student imports or account/role changes were performed.'
    if ($EmailWorker) {
        & (Join-Path $PSScriptRoot 'start-local.ps1') -EmailWorker
    } else {
        & (Join-Path $PSScriptRoot 'start-local.ps1')
    }
} finally {
    Pop-Location
}
