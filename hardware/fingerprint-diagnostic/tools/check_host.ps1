param([string]$Compiler = 'C:\Strawberry\c\bin\g++.exe')
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskOutput = Join-Path $taskRoot '.pio\host-tests'
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null
Push-Location $taskRoot
try {
    foreach ($suite in @('protocol', 'firmware', 'enrollment', 'template_transfer', 'terminal_logic', 'terminal', 'terminal_modes', 'terminal_feedback', 'terminal_screen', 'oled_pages', 'oled_integrity_patterns', 'accuracy_statistics', 'wifi_transfer_format')) {
        $taskExecutable = Join-Path $taskOutput ($suite + '_test.exe')
        & $Compiler -std=c++11 -Wall -Wextra -Werror -I tests/terminal_stubs -I tests/stubs -I include ('tests/' + $suite + '_test.cpp') -o $taskExecutable
        if ($LASTEXITCODE -ne 0) { throw "Compilation failed: $suite" }
        & $taskExecutable
        if ($LASTEXITCODE -ne 0) { throw "Test failed: $suite" }
        Write-Output "PASS $suite"
    }
    foreach ($suite in @('deferred_format','deferred_device','probe_experiment')) {
        $taskExecutable = Join-Path $taskOutput ($suite + '_test.exe')
        & $Compiler -std=c++11 -Wall -Wextra -Werror -I tests/deferred_stubs -I tests/stubs -I include ('tests/' + $suite + '_test.cpp') -o $taskExecutable
        if ($LASTEXITCODE -ne 0) { throw "Compilation failed: $suite" }
        & $taskExecutable
        if ($LASTEXITCODE -ne 0) { throw "Test failed: $suite" }
        Write-Output "PASS $suite"
    }
    $taskUnifiedExecutable = Join-Path $taskOutput 'unified_device_test.exe'
    & $Compiler -std=c++11 -Wall -Wextra -Werror -I tests/terminal_stubs -I tests/deferred_stubs -I tests/stubs -I include tests/unified_device_test.cpp -o $taskUnifiedExecutable
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed: unified device' }
    & $taskUnifiedExecutable
    if ($LASTEXITCODE -ne 0) { throw 'Test failed: unified device' }
    Write-Output 'PASS unified_device'
    $taskWifiExecutable = Join-Path $taskOutput 'wifi_transfer_test.exe'
    & $Compiler -std=c++11 -Wall -Wextra -Werror -I tests/wifi_stubs -I tests/terminal_stubs -I tests/deferred_stubs -I tests/stubs -I include tests/wifi_transfer_test.cpp -o $taskWifiExecutable
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed: wifi transfer' }
    & $taskWifiExecutable
    if ($LASTEXITCODE -ne 0) { throw 'Test failed: wifi transfer' }
    Write-Output 'PASS wifi_transfer'
    foreach ($variant in @(0, 1)) {
        $taskExecutable = Join-Path $taskOutput ('accuracy_firmware_' + $variant + '_test.exe')
        & $Compiler -std=c++11 -Wall -Wextra -Werror ("-DACCURACY_VERIFICATION=$variant") -I tests/accuracy_stubs -I tests/stubs -I include tests/accuracy_firmware_test.cpp -o $taskExecutable
        if ($LASTEXITCODE -ne 0) { throw "Compilation failed: accuracy variant $variant" }
        & $taskExecutable
        if ($LASTEXITCODE -ne 0) { throw "Test failed: accuracy variant $variant" }
    }
    $taskClockExecutable = Join-Path $taskOutput 'accuracy_clock_test.exe'
    & $Compiler -std=c++11 -Wall -Wextra -Werror -I tests/accuracy_stubs -I tests/stubs -I include tests/accuracy_clock_test.cpp -o $taskClockExecutable
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed: accuracy clock' }
    & $taskClockExecutable
    if ($LASTEXITCODE -ne 0) { throw 'Test failed: accuracy clock' }
    $taskPython = Join-Path $env:USERPROFILE '.platformio\penv\Scripts\python.exe'
    & $taskPython -m unittest discover -s tests -p 'test_*.py'
    if ($LASTEXITCODE -ne 0) { throw 'Python template/accuracy tests failed' }
} finally { Pop-Location }
