#Requires -Version 5.1

<#
.SYNOPSIS
Build, upload and monitor an OLED integrity test on the regular ESP32.

.DESCRIPTION
Run this file from any directory. PlatformIO must already be installed under
your Windows user profile. The default Integrity test uses src/oled_integrity.cpp
and the same SH1106 driver as the working terminal. -Test Basic selects the
original SSD1306 four-pattern test in src/oled_test.cpp instead.

With USB disconnected, connect OLED SDA to GPIO21, SCL to GPIO22, GND to GND,
and VCC to 3V3 if the module supports a 3.3 V supply. Use 3.3 V I2C signals.
Follow the module's printed labels: connector order varies. Reconnect USB and
close other serial monitors before running this script.

The script builds the selected test, checks the board's partition table, then
uploads only the application at 57600 baud. Saved capture storage and the
fingerprint scanner's library are left untouched. The test replaces the running
ESP32 application until another firmware is uploaded.

When the serial monitor opens, press EN/RESET to see the address probes and
test sequence. Integrity cycles for approximately one minute: numbered text
rows 1-8, white/black, horizontal/vertical stripes and their inverses,
checkerboards, top-only/lower-only fills, each eight-pixel band and each pixel
row. Top text rows 1-2 correspond to pixel y=0..15; rows 3-8 use y=16..63.
Watch for missing, stuck or noisy pixels. Compare the top with the lower rows.
Type p then Enter to pause/resume, n to advance, t to hold the text grid,
r to restart the cycle or h for help. Ctrl+C closes the serial monitor.
Serial success alone does not prove that the panel displays correctly.

Basic cycles WHITE, BLACK, CHECKERBOARD A and CHECKERBOARD B every two seconds;
it does not accept the Integrity controls. Restore the terminal afterwards with
the existing src/upload_script.ps1 (default esp32-sh1106). Following the reported
faulty pixel lines 2,4,6,8,10,12, the terminal reserves y=0..15 and fits its content
into six text rows below that band. This diagnostic still tests the whole panel.

If no OLED is detected, check power, common GND, SDA and SCL. Address 0x68 alone
is a clock response. The controller selection must match your panel; the I2C
address alone does not identify it. Disconnect USB before changing wiring,
then reconnect and press EN/RESET.

.EXAMPLE
PS> .\run_oled_test.ps1

.EXAMPLE
PS> .\run_oled_test.ps1 -Port COM12 -NoMonitor

.EXAMPLE
PS> .\run_oled_test.ps1 -BuildOnly

.EXAMPLE
PS> .\run_oled_test.ps1 -Test Basic
#>
[CmdletBinding()]
param(
    [ValidatePattern('^COM[0-9]+$')]
    [string]$Port = 'COM12',
    [ValidateSet('Integrity', 'Basic')]
    [string]$Test = 'Integrity',
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
$oledEnvironment = 'esp32-oled-integrity'
$oledSource = 'src\oled_integrity.cpp'
if ($Test -eq 'Basic') {
    $oledEnvironment = 'esp32-oled-test'
    $oledSource = 'src\oled_test.cpp'
}
$oledBuildDir = Join-Path $oledProject ('.pio\build\' + $oledEnvironment)

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
    (Join-Path $oledProject $oledSource)
)) {
    if (-not (Test-Path -LiteralPath $oledRequiredPath -PathType Leaf)) {
        throw "Required file not found: $oledRequiredPath"
    }
}

Write-Host @"
OLED $Test test - regular ESP32, environment $oledEnvironment
Wiring: SDA -> GPIO21 | SCL -> GPIO22 | GND -> GND
VCC -> 3V3 only if your OLED supports a 3.3 V supply. Use 3.3 V I2C signals.
Disconnect USB before changing wiring. Close other serial monitors.
No OLED at 0x3C/0x3D: check power, GND, SDA and SCL; press EN/RESET to retry.
Read all instructions with: Get-Help "$PSCommandPath" -Full
"@
if ($Test -eq 'Integrity') {
    Write-Host 'SH1106 test: compare text rows 1-2 (pixel y=0..15) with rows 3-8.'
    Write-Host 'Sequence: text, fills, stripes, checkerboards, top/lower fills, bands, pixel-row sweep.'
    Write-Host 'Controls: p=pause/resume, n=next, t=hold text grid, r=restart, h=help. Press Enter to send.'
    Write-Host 'Watch a full cycle (about one minute); note affected rows and pattern names.'
} else {
    Write-Host 'SSD1306 basic test: WHITE -> BLACK -> CHECKERBOARD A -> CHECKERBOARD B (2 seconds each).'
}

Write-Host "`nBuilding $oledEnvironment..."
Invoke-OledTool -Executable $oledPioExe -Arguments @(
    'run', '--project-dir', $oledProject, '-e', $oledEnvironment
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

Write-Host "`nUpload complete. Inspect the patterns on the physical display."
if (-not $NoMonitor) {
    Write-Host 'When the monitor opens, press EN/RESET to see the startup scan.'
    Write-Host 'Ctrl+C closes the monitor.'
    & $oledPioExe device monitor --port $Port --baud 115200
}
