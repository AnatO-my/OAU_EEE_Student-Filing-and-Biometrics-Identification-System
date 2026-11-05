# Displays only synthetic demonstration logins on this Windows account.
$ErrorActionPreference = 'Stop'
$demoAccountFile = Join-Path $PSScriptRoot '..\private-data\vercel-demo\accounts.dpapi'
$demoAccountSecret = (Get-Content -Raw -LiteralPath $demoAccountFile).Trim() | ConvertTo-SecureString
try {
    $demoAccounts = ([System.Net.NetworkCredential]::new('', $demoAccountSecret)).Password | ConvertFrom-Json
    $demoAccounts | Select-Object role,username,password | Format-Table -AutoSize
    Write-Host 'These accounts access synthetic demo data only. Keep their passwords private.'
} finally {
    $demoAccountSecret.Dispose()
    Remove-Variable demoAccounts -ErrorAction SilentlyContinue
}
