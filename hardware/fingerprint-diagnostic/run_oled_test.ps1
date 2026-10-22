#Requires -Version 5.1

<#
.SYNOPSIS
Build, upload and monitor the SSD1306 OLED test on the regular ESP32.

.DESCRIPTION
Run this file from any directory. PlatformIO must already be installed under
your Windows user profile. The test source is src/oled_test.cpp beside this file.

With USB disconnected, connect OLED SDA to GPIO21, SCL to GPIO22, GND to GND,
and VCC to 3V3 if the module supports a 3.3 V supply. Use 3.3 V I2C signals.
Follow the module's printed labels: connector order varies. Reconnect USB and
close other serial monitors before running this script.

The script builds esp32-oled-test, checks the board's partition table, then
uploads only the application at 57600 baud. Saved capture storage and the
fingerprint scanner's library are left untouched. The test replaces the running
ESP32 application until another firmware is uploaded.

When the serial monitor opens, press EN/RESET to see the I2C scan. A detected
SSD1306 at 0x3C or 0x3D should cycle WHITE, BLACK, CHECKERBOARD A and CHECKERBOARD B
every two seconds. Confirm all four patterns visually, including the edges.
Serial detection alone does not prove that the panel displays correctly.

If no OLED is detected, check power, common GND, SDA and SCL. Address 0x68 alone
is a clock response. If detected but blank or distorted, confirm SSD1306 128x64
compatibility; an SH1106 needs a different driver. Disconnect USB before changing
wiring, then reconnect and press EN/RESET. Ctrl+C closes the serial monitor.

.EXAMPLE
PS> .\run_oled_test.ps1

.EXAMPLE
PS> .\run_oled_test.ps1 -Port COM12 -NoMonitor

.EXAMPLE
PS> .\run_oled_test.ps1 -BuildOnly
#>
[CmdletBinding()]
param(
    [ValidatePattern('^COM[0-9]+$')]
    [string]$Port = 'COM12',
    [switch]$BuildOnly,
    [switch]$NoMonitor
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$oledProject = $PSScriptRoot
$oledPioRoot = Join-Path $env:USERPROFILE '.platformio'
$oledPioExe = Join-Path $oledPioRoot 'penv\Scripts\platformio.exe'
$oledPython = Join-Path $oledPioRoot 'penv\Scripts\python.exe'
$oledEsptool = Join-Path $oledPioRoot 'packages\tool-esptoolpy\esptool.py'
$oledBuildDir = Join-Path $oledProject '.pio\build\esp32-oled-test'

function Invoke-OledTool {
    param(
        [string]$Executable,
        [string[]]$Arguments,
        [string]$Step
    )
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed (exit code $LASTEXITCODE)."
    }
}

foreach ($oledRequiredPath in @(
    $oledPioExe,
    (Join-Path $oledProject 'platformio.ini'),
    (Join-Path $oledProject 'src\oled_test.cpp')
)) {
    if (-not (Test-Path -LiteralPath $oledRequiredPath -PathType Leaf)) {
        throw "Required file not found: $oledRequiredPath"
    }
}

Write-Host @"
SSD1306 128x64 OLED test - regular ESP32
Wiring: SDA -> GPIO21 | SCL -> GPIO22 | GND -> GND
VCC -> 3V3 only if your OLED supports a 3.3 V supply. Use 3.3 V I2C signals.
Disconnect USB before changing wiring. Close other serial monitors.
Expected: WHITE -> BLACK -> CHECKERBOARD A -> CHECKERBOARD B (2 seconds each).
No OLED at 0x3C/0x3D: check power, GND, SDA and SCL; press EN/RESET to retry.
Read all instructions with: Get-Help "$PSCommandPath" -Full
"@

Write-Host "`nBuilding esp32-oled-test..."
Invoke-OledTool -Executable $oledPioExe -Arguments @(
    'run', '--project-dir', $oledProject, '-e', 'esp32-oled-test'
) -Step 'OLED test build'

if ($BuildOnly) {
    Write-Host "Build passed. Firmware: $(Join-Path $oledBuildDir 'firmware.bin')"
    return
}

$oledFirmware = Join-Path $oledBuildDir 'firmware.bin'
$oledPartitions = Join-Path $oledBuildDir 'partitions.bin'
$oledBoardPartitions = Join-Path $oledBuildDir 'oled-test-board-partitions.bin'
foreach ($oledRequiredPath in @($oledPython, $oledEsptool, $oledFirmware, $oledPartitions)) {
    if (-not (Test-Path -LiteralPath $oledRequiredPath -PathType Leaf)) {
        throw "Required file not found: $oledRequiredPath"
    }
}

Write-Host "`nChecking the partition layout on $Port..."
Invoke-OledTool -Executable $oledPython -Arguments @(
    $oledEsptool, '--chip', 'esp32', '--port', $Port, '--baud', '57600',
    'read_flash', '0x8000', '0xC00', $oledBoardPartitions
) -Step 'Board partition read'

$oledExpectedHash = (Get-FileHash -LiteralPath $oledPartitions -Algorithm SHA256).Hash
$oledActualHash = (Get-FileHash -LiteralPath $oledBoardPartitions -Algorithm SHA256).Hash
if ($oledExpectedHash -ne $oledActualHash) {
    throw 'Partition layouts differ. Upload stopped; check the board configuration.'
}

Write-Host "`nUploading the test application to $Port at 57600 baud..."
Invoke-OledTool -Executable $oledPython -Arguments @(
    $oledEsptool, '--chip', 'esp32', '--port', $Port, '--baud', '57600',
    'write_flash', '0x10000', $oledFirmware
) -Step 'OLED test upload'

Write-Host "`nUpload complete. Confirm the four patterns on the physical display."
if (-not $NoMonitor) {
    Write-Host 'When the monitor opens, press EN/RESET to see the startup scan.'
    Write-Host 'Ctrl+C closes the monitor.'
    & $oledPioExe device monitor --port $Port --baud 115200
}
