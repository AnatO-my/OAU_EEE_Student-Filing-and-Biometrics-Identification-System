# Laptop download and website import walkthrough

The laptop receives saved files over USB serial; the ESP32 does not appear as a
USB disk. Download and website import are separate operations. Connecting the
cable does not perform either automatically.

## Which file is needed?

| Operation | Laptop file | Current website handling |
| --- | --- | --- |
| Deferred attendance | One `.jsonl` snapshot per capture batch | Authorized backend preview/import exists; evidence remains pending matching and timing review |
| Enrollment backup | `.fpt.json` per enrolled template, plus bulk-export manifest | Student enrollment upload/binding is not implemented |
| Immediate local check-in | CSV streamed from ESP32 `/attendance.csv`; Wi-Fi receiver can save it | Website importer is not implemented; USB serial export has no dedicated laptop file recorder |

The deferred downloader below is `tools/deferred_batches.py`. Do not convert its
JSONL into CSV: CSV check-ins do not contain the unidentified fingerprint probes
needed for deferred matching. Enrollment templates and single-capture attendance
probes are also different records.

## 1. Open PowerShell and prepare the tool

The normal `esp32-sh1106` firmware includes both attendance modes. No rebuild is
needed to download an existing batch. Connect the powered ESP32 to the laptop,
and close PlatformIO Serial Monitor or any other program using the COM port.

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
$fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'
$batchTool = 'hardware/fingerprint-diagnostic/tools/deferred_batches.py'
& $fpPython -m serial.tools.list_ports
```

COM12 was the recorded working port. Use the port actually listed for this
board if Windows assigns a different number. The tool configures 115,200 baud
itself. Internet access is unnecessary for the USB download.

```powershell
$devicePort = 'COM12'
& $fpPython $batchTool list --port $devicePort
```

The output lists batch UUIDs, saved-capture counts and interrupted-write flags.
Opening the tool pauses the physical terminal/capture so scanner commands do not
compete. A batch UUID identifies the saved capture collection; it is different
from the backend class-session UUID to which that collection is bound.

## 2. Download an existing attendance batch

Copy the intended existing batch UUID from the list. Do not generate a new UUID
when trying to retrieve an existing collection.

```powershell
$batch = 'PASTE_EXISTING_BATCH_UUID_HERE'
& $fpPython $batchTool stop --port $devicePort
& $fpPython $batchTool download --port $devicePort --batch $batch
```

The downloader prints `Saved N pending captures:` and the exact saved path. Its
default destination is:

```text
C:\Users\Ot\Downloads\EEE-Project\private-data\fingerprint-probes\batches\<batch-uuid>-<random-suffix>.jsonl
```

Each download uses a fresh filename. The device retains the original files.
Downloading again creates another snapshot; an explicit `--out` destination
that already exists is refused. An empty batch is valid and contains zero scans.

The tool checks the requested batch identity, stored-block CRC32, probe lengths,
event UUID uniqueness, elapsed-time ordering within each boot, record count and
complete transfer SHA-256. It builds the JSONL header/events/trailer, validates
them, flushes a temporary file to disk and verifies its bytes by readback before
publishing the final filename without overwriting an existing file.

## 3. Validate the downloaded file

Use the path printed by the download, without opening or editing its probe data:

```powershell
$batchFile = 'PASTE_FULL_SAVED_JSONL_PATH_HERE'
& $fpPython $batchTool validate $batchFile
```

Expected result: `Valid pending batch: N captures.` A valid download proves a
complete local snapshot; it does not prove identity, class eligibility or website
receipt. Current deferred records contain boot UUID/elapsed milliseconds and
null calendar capture time, so timing still requires review.

If validation or transfer fails, preserve device files and any `.partial` file.
Retry into a fresh destination after resolving the reported problem. A damaged
committed event blocks export rather than being silently omitted. An interrupted
uncommitted tail can be reported on an otherwise valid committed snapshot; it
requires recovery review and must not be cleared by formatting the device.

## 4. Preview on the website backend

The following is the current API workflow, not a finished browser upload screen.
Use the intended backend with its attendance routes/schema available and an
authorized staff account with course access and the dedicated
`attendance.import_pending_captures` permission. These routes have been tested
locally; that does not establish they are deployed on a particular website.

First sign in from this PowerShell session. Browser sign-in cookies are not
automatically shared with PowerShell. Replace the website placeholder; use its
actual HTTPS origin, or the explicit localhost origin for local development.

```powershell
$apiBase = 'https://YOUR-WEBSITE'
$loginCredential = Get-Credential -Message 'Website staff account'
$csrf = Invoke-RestMethod -Uri "$apiBase/api/auth/csrf/" -SessionVariable webSession
$loginBody = @{
    username = $loginCredential.UserName
    password = $loginCredential.GetNetworkCredential().Password
} | ConvertTo-Json
$null = Invoke-RestMethod -Method Post -Uri "$apiBase/api/auth/login/" `
    -WebSession $webSession -Headers @{ 'X-CSRFToken' = $csrf.csrfToken } `
    -ContentType 'application/json' -Body ([Text.Encoding]::UTF8.GetBytes($loginBody))
$loginBody = $null
$loginCredential = $null
# Django rotates the CSRF token on login.
$csrf = Invoke-RestMethod -Uri "$apiBase/api/auth/csrf/" -WebSession $webSession
```

Read the class identifier from the validated file header so the request targets
the class already bound to this batch. Changing that identifier is not a way to
move captures to another class.

```powershell
$batchHeader = Get-Content -LiteralPath $batchFile -TotalCount 1 | ConvertFrom-Json
$classSession = $batchHeader.class_session_uuid
$pendingUrl = "$apiBase/api/attendance/sessions/$classSession/pending-batches/"
$captureHeaders = @{ 'X-CSRFToken' = $csrf.csrfToken }
$preview = Invoke-RestMethod -Method Post -Uri ($pendingUrl + 'preview/') `
    -WebSession $webSession -Headers $captureHeaders `
    -ContentType 'application/x-ndjson' -InFile $batchFile
$preview
```

Preview checks the complete file, authorization, class binding and conflicts,
without saving captures. Review its counts and recovery/timing flags. The API
takes the original file bytes, not a multipart form or a JSON wrapper.

## 5. Import the reviewed file and retain the receipt

After reviewing the preview, send the same unchanged file with its preview hash:

```powershell
$captureHeaders['X-Capture-SHA256'] = $preview.file_sha256
$receipt = Invoke-RestMethod -Method Post -Uri $pendingUrl `
    -WebSession $webSession -Headers $captureHeaders `
    -ContentType 'application/x-ndjson' -InFile $batchFile
$receipt
```

The response includes a receipt ID, whole-file digest, receipt time and new/
existing-event counts. The receipt means the backend committed pending evidence;
it does not mean students were matched or marked present. An exact retry is
idempotent and returns the original receipt. If a response is lost, retry the
same bytes rather than changing event identifiers.

Keep both the laptop download and device files. Current receipts do not authorize
deletion, and the device has no ordinary batch-deletion command. Enrollment
binding, identity/timing reconciliation and the browser upload interface remain
separate integration work. See [the backend contract](../../docs/attendance-pending-batches.md).

## Preparing a new class rather than downloading an old one

Use a real backend-created class-session UUID and the commissioned scanner UUID:

```powershell
$batch = [guid]::NewGuid().ToString()
$classSession = 'BACKEND_CLASS_SESSION_UUID'
$scannerId = 'COMMISSIONED_SCANNER_UUID'
& $fpPython $batchTool begin --port $devicePort --batch $batch `
    --class-session $classSession --scanner-id $scannerId --compatibility-group as608-unit-1
```

Then select the intended batch and Deferred mode on the device and explicitly
start it. Alternatively, `arm --port $devicePort --batch $batch --watch` provides
laptop progress and Ctrl+C stops capture. See [unified controls](UNIFIED-ATTENDANCE.md).
No student enrollment needs deleting to start another attendance batch.

## Enrollment backups and Wi-Fi

For the existing enrolled-template backup tool, run:

```powershell
& $fpPython hardware/fingerprint-diagnostic/tools/portable_template.py menu --port $devicePort
```

Select listed slots or `ALL`. Verified files and a manifest are saved below
`private-data/fingerprint-templates/export-<timestamp>-<suffix>/`. This is a
backup/export operation, not automatic website enrollment. See [EXPORTING.md](EXPORTING.md).

The opt-in Wi-Fi transport uses the laptop receiver described in
[WIFI-TRANSFER.md](WIFI-TRANSFER.md). It delivers all three file types to the
laptop. Deferred JSONL still uses the same website preview/import steps afterward;
the CSV and enrollment website integrations remain unfinished.
