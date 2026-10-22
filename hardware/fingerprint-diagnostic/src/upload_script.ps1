param(
    [ValidateSet('esp32', 'esp32-sh1106')]
    [string]$AttendanceEnvironment = 'esp32-sh1106',
    [ValidatePattern('^COM[0-9]+$')]
    [string]$Port = 'COM12',
    [switch]$BuildOnly,
    [switch]$NoMonitor
)

$project = 'C:\Users\Ot\Downloads\EEE-Project\hardware\fingerprint-diagnostic'
$pio = 'C:\Users\Ot\.platformio\penv\Scripts\platformio.exe'

# Find the connected ESP32's port.
& $pio device list

# COM12 was your previous port; update this if it changes.
$boardPort = $Port

Write-Host "Attendance firmware: $AttendanceEnvironment | port: $boardPort"
Write-Host 'One installed build: MENU > ATTENDANCE MODE selects IMMEDIATE or DEFERRED; confirm with ENROLL.'
Write-Host 'Boot starts stopped. Prepare a class batch over USB for deferred mode. SH1106 is the default.'
Write-Host 'Serial a starts/resumes the selected attendance type after diagnostics.'

if ($BuildOnly) {
    & $pio run -d $project -e $AttendanceEnvironment
    if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
    return
}

# Compile the project and upload it.
& $pio run -d $project -e $AttendanceEnvironment -t upload --upload-port $boardPort
if ($LASTEXITCODE -ne 0) { throw 'Build or upload failed' }

# Open the USB console.
if (-not $NoMonitor) {
    & $pio device monitor -p $boardPort -b 115200
}
