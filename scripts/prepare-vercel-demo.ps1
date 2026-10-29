# Run in a separate PowerShell process. The Aiven administrator password is never saved.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$demoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $demoRoot
$demoPrivateDirectory = Join-Path $demoRoot 'private-data\vercel-demo'
$demoBundlePath = Join-Path $demoPrivateDirectory 'environment.dpapi'
if (Test-Path -LiteralPath $demoBundlePath) {
    throw 'A demo credential bundle already exists. Have Codex inspect its status before preparing another database.'
}
$demoLink = Get-Content -Raw -LiteralPath (Join-Path $demoRoot '.vercel\project.json') | ConvertFrom-Json
if ($demoLink.projectName -ne 'oau-eee-demo' -or -not $demoLink.projectId -or -not $demoLink.orgId) {
    throw 'Link and verify the oau-eee-demo Vercel project first.'
}
. (Join-Path $demoRoot 'private-data\aiven\configure.ps1') -UseExistingPassword:([bool]$env:POSTGRES_PASSWORD)
$demoPython = Join-Path $demoRoot '.venv\Scripts\python.exe'
$demoHelper = Join-Path $PSScriptRoot 'prepare_vercel_demo.py'
$demoBundle = & $demoPython $demoHelper plan
if ($LASTEXITCODE -ne 0) { throw 'Demo preparation failed before database creation.' }
New-Item -ItemType Directory -Path $demoPrivateDirectory -Force | Out-Null
try {
    $demoSecure = ConvertTo-SecureString -String $demoBundle -AsPlainText -Force
    $demoSecure | ConvertFrom-SecureString | Set-Content -LiteralPath $demoBundlePath -Encoding ascii
    $demoBundle | & $demoPython $demoHelper create
    if ($LASTEXITCODE -ne 0) { throw 'Demo creation did not complete. The encrypted bundle is retained for diagnosis; do not rerun blindly.' }
    'created' | Set-Content -LiteralPath (Join-Path $demoPrivateDirectory 'database-status.txt') -Encoding ascii
    Write-Host 'Isolated demo database and application role created. Tell Codex: demo database ready.'
    Write-Host 'Only demo credentials were saved, encrypted for your Windows account. No administrator password was saved.'
} finally {
    if ($null -ne $demoSecure) { $demoSecure.Dispose() }
    Remove-Variable demoBundle -ErrorAction SilentlyContinue
    Remove-Item Env:POSTGRES_PASSWORD -ErrorAction SilentlyContinue
}
