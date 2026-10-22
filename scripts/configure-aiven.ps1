# Dot-source from the repository root to configure this terminal's child processes.
# Credentials remain in process environment variables; no secrets are saved to disk.
[CmdletBinding()]
param(
    [string]$DatabaseHost = "",
    [int]$DatabasePort = 0,
    [string]$DatabaseName = "defaultdb",
    [string]$DatabaseUser = "avnadmin",
    [string]$RootCertificate = "",
    [string]$ClientLibraryDirectory = "",
    [switch]$UseExistingPassword
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DatabaseHost)) {
    $DatabaseHost = Read-Host "Aiven PostgreSQL host (hostname only)"
}
$DatabaseHost = $DatabaseHost.Trim()
if ($DatabaseHost -notmatch '^[a-zA-Z0-9.-]+\.aivencloud\.com$') {
    throw "Use the PostgreSQL hostname shown in Aiven, ending in .aivencloud.com. Do not paste a service URI."
}
if ($DatabasePort -eq 0) {
    $aivenPortText = Read-Host "Aiven PostgreSQL port (copy from the service overview)"
    if (-not [int]::TryParse($aivenPortText, [ref]$DatabasePort)) {
        throw "Enter the numeric port from Aiven."
    }
}
if ($DatabasePort -lt 1 -or $DatabasePort -gt 65535) {
    throw "The PostgreSQL port must be between 1 and 65535."
}
if ([string]::IsNullOrWhiteSpace($DatabaseName) -or [string]::IsNullOrWhiteSpace($DatabaseUser)) {
    throw "Database name and user must not be empty."
}
if ([string]::IsNullOrWhiteSpace($RootCertificate)) {
    $RootCertificate = Join-Path $PSScriptRoot '..\private-data\aiven\ca.pem'
}
if (-not (Test-Path -LiteralPath $RootCertificate -PathType Leaf)) {
    throw "Download the service CA certificate to private-data/aiven/ca.pem, or pass -RootCertificate with its full path."
}
$aivenCertificatePath = (Resolve-Path -LiteralPath $RootCertificate).ProviderPath
if (-not [string]::IsNullOrWhiteSpace($ClientLibraryDirectory)) {
    if (-not (Test-Path -LiteralPath (Join-Path $ClientLibraryDirectory 'libpq.dll') -PathType Leaf)) {
        throw "ClientLibraryDirectory must contain the trusted PostgreSQL libpq.dll. See docs/aiven-free-postgresql.md."
    }
    $aivenClientDirectory = (Resolve-Path -LiteralPath $ClientLibraryDirectory).ProviderPath
}

$aivenPasswordSecure = $null
try {
    if ($UseExistingPassword) {
        $aivenPasswordValue = $env:POSTGRES_PASSWORD
    } else {
        $aivenPasswordSecure = Read-Host "Aiven PostgreSQL password (hidden)" -AsSecureString
        $aivenPasswordValue = ([System.Net.NetworkCredential]::new("", $aivenPasswordSecure)).Password
    }
    if ([string]::IsNullOrEmpty($aivenPasswordValue)) {
        throw "A database password is required. Run the setup without -UseExistingPassword to enter it privately."
    }

    $env:POSTGRES_HOST = $DatabaseHost
    $env:POSTGRES_PORT = [string]$DatabasePort
    $env:POSTGRES_DB = $DatabaseName.Trim()
    $env:POSTGRES_USER = $DatabaseUser.Trim()
    $env:POSTGRES_PASSWORD = $aivenPasswordValue
    $env:POSTGRES_SSLMODE = "verify-full"
    $env:POSTGRES_SSLROOTCERT = $aivenCertificatePath
    $env:POSTGRES_CONNECT_TIMEOUT = "10"
    $env:DJANGO_SETTINGS_MODULE = "config.postgres_settings"
    if (-not [string]::IsNullOrWhiteSpace($ClientLibraryDirectory)) {
        # Use psycopg's documented Python implementation with the compatible
        # native client. The binary wheel otherwise loads its own libpq.
        $env:PSYCOPG_IMPL = "python"
        if (($env:PATH -split [System.IO.Path]::PathSeparator)[0] -ne $aivenClientDirectory) {
            $env:PATH = $aivenClientDirectory + [System.IO.Path]::PathSeparator + $env:PATH
        }
        # Aiven uses password authentication over TLS, not Kerberos encryption.
        $env:PGGSSENCMODE = "disable"
    }
} finally {
    if ($null -ne $aivenPasswordSecure) {
        $aivenPasswordSecure.Dispose()
    }
    Remove-Variable aivenPasswordValue -ErrorAction SilentlyContinue
}

Write-Host "Aiven PostgreSQL configured for this terminal with certificate and hostname verification."
Write-Host "No connection, migration, import or secret-file write has been performed."
Write-Host 'Next: .\.venv\Scripts\python.exe manage.py check_database_connection'
Write-Host "Restart servers and workers from this configured terminal when ready."
