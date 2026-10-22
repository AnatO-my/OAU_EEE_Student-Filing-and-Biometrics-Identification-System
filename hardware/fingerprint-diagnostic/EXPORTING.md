# Select and export fingerprint templates

Use the normal unified SH1106 firmware for this board. For the complete laptop
download/website handoff see [LAPTOP-DOWNLOADER.md](LAPTOP-DOWNLOADER.md); optional
encrypted wireless delivery is described in [WIFI-TRANSFER.md](WIFI-TRANSFER.md).

Close Serial Monitor with **Ctrl+C** before uploading or starting the export menu.
The menu needs exclusive access to COM12. No Adafruit library is required.
Export reads saved templates; no finger needs to be on the scanner.
The physical terminal UI pauses automatically when the tool connects. After
closing the tool and reopening Serial Monitor, send `a` to resume the UI and
automatic Home scanning. See [terminal controls](TERMINAL.md).

## 1. Upload the updated firmware once

Run these in PowerShell:

```powershell
cd C:\Users\Ot\Downloads\EEE-Project\hardware\fingerprint-diagnostic
$pio = 'C:\Users\Ot\.platformio\penv\Scripts\platformio.exe'
& $pio run -e esp32-sh1106 -t upload --upload-port COM12
```

Expect `[SUCCESS]`. The updated firmware adds the occupied-slot list and export
progress messages. This command updates the ESP32 program; it does not erase
the scanner's template library. Leave Serial Monitor closed for the next step.

## 2. Start the guided file-export menu

```powershell
$fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'
& $fpPython tools/portable_template.py menu --port COM12
```

The tool opens the console and reads the scanner's occupied-slot table. At
`Choose ID(s), ALL, R to refresh, or Q to quit:`, enter:

| Input | Action |
| --- | --- |
| `12` | Export occupied slot 12 (substitute a listed ID) |
| `10,12` | Export those two occupied slots |
| `ALL` | Export every slot in the displayed occupied-slot snapshot |
| `R` | Refresh the slot list |
| `Q` | Close the menu and release the port |

An ID not in the occupied-slot list is rejected before transfer. Each operation
uses a new output folder, so earlier backups are retained. For each template,
the feedback confirms occupancy, loading, received bytes/packet checksums,
transfer CRC, JSON save and file-readback/SHA-256 validation. `[SAVED]` shows the
absolute file location; `[SUMMARY]` gives verified/failed/unattempted counts.

## 3. Find the files

By default, files are saved below:

```text
C:\Users\Ot\Downloads\EEE-Project\private-data\fingerprint-templates\export-<timestamp>-<suffix>\
    slot-00012.fpt.json
    manifest.json
```

`manifest.json` records each verified file, byte count, UUID and checksum. If a
transfer fails, the batch stops and the manifest identifies the failed slot and
unattempted slots. Earlier verified files remain usable. Retry after addressing
the printed error; a new batch gets a new folder.

Backups contain actual biometric template bytes. Keep this ignored directory
private. The terminal displays status and paths, not the biometric payload.

## Direct commands instead of the menu

```powershell
& $fpPython tools/portable_template.py list --port COM12
& $fpPython tools/portable_template.py export --port COM12 --slot 12
& $fpPython tools/portable_template.py export --port COM12 --all
```

Use `--out-dir PATH` to choose another private destination. A single export can
also specify `--out PATH` for a new filename. Existing explicit scanner/gallery,
student, finger and template UUID options remain supported for a single slot.

## Student identity and repeated backups

New unassigned backups use record schema **2**, with `student_id: null` and an
unknown finger label. Exporting all slots does not mean they belong to the same
person. Existing explicitly bound identities in the export profile are retained
for identical bytes. Version-1 records remain readable/restorable.

The private `export-profile.json` retains commissioning IDs and template UUIDs
for exact byte duplicates in that gallery. Repeated backups through this profile
retain the template UUID. After fully erasing/rebuilding the scanner library,
start a new gallery using `menu --port COM12 --new-gallery`. This updates the
local export namespace; it does not erase the scanner.

Unassigned backups can be restored for testing, but cannot identify a student
until an authorized enrollment process binds them to the correct student UUID.
No database upload or student binding is performed by this menu.

## Using Serial Monitor itself

The firmware supports `l` to list occupied IDs, `t 12` followed by Enter to stream
one template, and `t ALL` followed by Enter to stream all. Sending `t` and Enter
opens a slot-selection prompt. These commands **stream data only**: Serial
Monitor does not create the verified JSON files. Use the Python menu for backups.

Use `e` for enrollment, `v <ID>` for a live check against one slot, and `h` for
help. Never paste template payload lines into the report or shared source.

## If export does not start

- Port busy/access denied: close Serial Monitor and other programs using COM12.
- No slot list: upload the updated firmware above; the new menu requires `l`.
- Scanner timeout: use `b` in Serial Monitor to check authentication and wiring,
  close the monitor, then retry the menu.
- Empty library: enroll successfully with `e` before exporting.
- CRC or file-readback failure: the file is not reported as verified. Inspect
  the error/manifest and retry; the tool does not invent missing template bytes.

See [README.md](README.md) for wiring and [the storage design](../../docs/fingerprint-template-storage.md)
for format compatibility and restoration.
