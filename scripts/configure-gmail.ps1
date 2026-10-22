# Configure this PowerShell process and programs launched from it. No file writes.
param([string]$Sender = "")

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($Sender)) {
    $Sender = Read-Host "Gmail / Google Workspace address chosen by the HOD"
}
try {
    $gmailSenderAddress = [System.Net.Mail.MailAddress]::new($Sender.Trim()).Address
} catch {
    throw "Enter a valid sending email address."
}

$gmailAppSecret = Read-Host "Google App Password (hidden; not the normal Gmail password)" -AsSecureString
try {
    $env:DJANGO_EMAIL_HOST_PASSWORD = ([System.Net.NetworkCredential]::new("", $gmailAppSecret)).Password.Replace(" ", "")
} finally {
    $gmailAppSecret.Dispose()
}
if ([string]::IsNullOrWhiteSpace($env:DJANGO_EMAIL_HOST_PASSWORD)) {
    throw "An App Password is required."
}

$env:DJANGO_EMAIL_BACKEND = "academics.email_backend.EmailBackend"
$env:DJANGO_EMAIL_HOST = "smtp.gmail.com"
$env:DJANGO_EMAIL_PORT = "587"
$env:DJANGO_EMAIL_USE_TLS = "true"
$env:DJANGO_EMAIL_AUTH_METHOD = "LOGIN"
$env:DJANGO_EMAIL_HOST_USER = $gmailSenderAddress
$env:DJANGO_DEFAULT_FROM_EMAIL = "EEE Department <$gmailSenderAddress>"

Write-Host "Gmail SMTP configured for this terminal. No email has been sent."
Write-Host "Run the mock email command from this same terminal. Restart running server/worker processes to use these settings."
Write-Host "No credentials were written to disk; deployment must supply them through its private secret configuration."
