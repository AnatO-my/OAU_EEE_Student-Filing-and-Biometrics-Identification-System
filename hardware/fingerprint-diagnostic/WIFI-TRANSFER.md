# Wi-Fi transfer to the laptop

The normal `esp32-sh1106` build includes an opt-in Wi-Fi station client and keeps
the USB tools. It can send all three export types to `tools/wifi_transfer.py`:

| Export | Laptop result | What the receipt means |
| --- | --- | --- |
| Deferred capture batch | Validated `.jsonl` snapshot | Pending evidence saved on the laptop |
| Immediate attendance log | Exact validated `.csv` | Local check-in log saved on the laptop |
| Enrolled template, selected slot | Validated `.fpt.json` | Recoverable unassigned template backup saved on the laptop |

The ESP32 opens an outgoing TLS connection. It verifies the receiver certificate,
hostname and exact SHA-256 certificate pin before transmitting a device-specific
secret. The receiver checks that secret against its device allowlist. There is
no inbound HTTP server on the ESP32 and no wireless scanner-control API.

Wi-Fi is disabled until provisioned. Transfer is explicit, stops attendance and
retains device files and scanner references. A laptop receipt is not a website
receipt, student registration or a confirmed attendance result.

## 1. Install the prepared firmware once

Build/upload the complete project; Wi-Fi then remains available in the same build
as both attendance modes:

```powershell
Set-Location 'C:\Users\Ot\Downloads\EEE-Project'
& hardware/fingerprint-diagnostic/src/upload_script.ps1 -Port COM12 -NoMonitor
$fpPython = 'C:\Users\Ot\.platformio\penv\Scripts\python.exe'
$wifiTool = 'hardware/fingerprint-diagnostic/tools/wifi_transfer.py'
& $fpPython $wifiTool status --port COM12
```

Use the actual current COM port. Status is `FPWSTATUS 1 DEVICE_UUID CONFIGURED
CONNECTED`; copy the device UUID. A connected value of zero is normal while
idle: the radio disconnects after each transfer. Keep Serial Monitor closed when
the laptop tool owns the port. Uploading this application does not require
formatting the ESP32 filesystem or erasing scanner enrollments.

## 2. Create private laptop/device configuration

Both devices must be able to reach each other on the same 2.4 GHz Wi-Fi network,
including a suitable laptop hotspot. Router client isolation can block them.
Internet access is not required when the ESP32 has a correct TLS clock.

Use the laptop's actual reachable IPv4 address or DNS hostname; `localhost` and
`127.0.0.1` would refer to the ESP32 itself when used by the board. A stable address
avoids reprovisioning after a laptop address change. The certificate includes
this address/hostname, so changing it requires a new certificate and provisioning.
For an IPv4 address, certificate generation includes both its IP and DNS SAN
entries for compatibility with the pinned ESP32 runtime's
[Mbed TLS name verifier](https://github.com/Mbed-TLS/mbedtls/blob/v2.28.7/library/x509_crt.c#L2792).
Certificate trust, hostname checking and the exact leaf pin remain required.

```powershell
$laptopAddress = 'LAPTOP_IPV4_ADDRESS'
$deviceId = 'DEVICE_UUID_FROM_STATUS'
$scannerId = 'EXISTING_COMMISSIONED_SCANNER_UUID'
$galleryId = 'EXISTING_COMMISSIONED_GALLERY_UUID'
& $fpPython $wifiTool init --host $laptopAddress --device $deviceId `
    --scanner-id $scannerId --gallery-id $galleryId --compatibility-group as608-unit-1
```

The command prompts for the SSID and hides password entry. It generates a new
certificate/key and random per-device secret, and refuses an existing setup
folder. OpenSSL is needed only for this initialization; this laptop has
`C:\Strawberry\c\bin\openssl.exe`. If it is absent from PATH, add
`--openssl 'C:\Strawberry\c\bin\openssl.exe'`.
The current provisioning format supports printable ASCII SSIDs of 1–32
characters and WPA passwords of 8–63 characters.

Reuse the scanner/gallery/compatibility identifiers from existing commissioning
or the private USB export profile. They label the unit and reference-gallery
generation; they do not identify a student. For deferred batches the scanner
and compatibility labels must match their saved headers. Do not change an old
batch's header to make it pass.

Files default to:

```text
private-data/fingerprint-wifi/<device-uuid>/
    device.json         Wi-Fi credentials, receiver certificate/pin and secret
    receiver.json       Laptop file locations and commissioned device allowlist
    receiver-cert.pem   Certificate with a one-year validity period
    receiver-key.pem    Private server key
    openssl.cnf         Certificate-generation configuration
```

These ignored files contain credentials. Keep the private key on the laptop;
the ESP32 receives the certificate and secret, not that key. Configuration is
stored in ordinary local files/NVS; this prototype does not add encryption at
rest or replace a deployment key-management policy.

## 3. Provision once over USB

```powershell
$setupDir = Join-Path 'private-data/fingerprint-wifi' $deviceId
$deviceConfig = Join-Path $setupDir 'device.json'
$receiverConfig = Join-Path $setupDir 'receiver.json'
& $fpPython $wifiTool provision --port COM12 --config $deviceConfig
```

The tool checks the connected device UUID, sends a bounded checksum-protected
configuration, waits for a save receipt and sets the TLS system clock from the
laptop. Credentials are never command-line arguments and are not printed.
The firmware retains the configuration in NVS; transfers do not require another
firmware build. Configuration does not automatically start capture or transfer.

TLS must have a correct clock. After reboot the board can seed that clock from a
valid running DS1307, interpreting its civil time as Africa/Lagos (UTC+01:00).
`TERMINAL_UTC_OFFSET_SECONDS` configures another assembly timezone. Keep the RTC
set to the matching local time. If no valid RTC is available, SNTP is attempted
while connected; without Internet, bootstrap from USB explicitly:

```powershell
& $fpPython $wifiTool clock --port COM12
```

The pinned Arduino runtime has a 32-bit time representation. Accepted TLS time
is 2024-01-01 through 2037-12-31; upgrade/revalidate before that upper bound.
Setting the TLS clock does not set the attendance RTC or invent calendar dates
for deferred records. Certificate expiration/pin mismatch fails transfer; renew
the setup and provision the new certificate instead of disabling verification.

## 4. Run the laptop receiver

In a PowerShell window with the variables above:

```powershell
& $fpPython $wifiTool receive --config $receiverConfig --bind $laptopAddress
```

`--bind` must be the laptop's actual IPv4 interface address (use the IPv4 address
even when the provisioned host is a DNS name). Omitted `--bind` listens only on
127.0.0.1, suitable for local tests. The default configured TCP port is 9443.
The examples use IPv4 for both; if provisioning a DNS name, pass that name to
`init --host` and retain the IPv4 address for `receive --bind`.
Allow the receiver through Windows Firewall on the intended private network if
Windows prompts; router Internet port forwarding is unnecessary. Keep the
receiver running and the laptop awake during transfer. Ctrl+C stops it.

The receiver is a console program, not a browser upload screen. It requires no
Python package beyond the existing USB tool's pyserial dependency; TLS, parsing
and file handling use the standard library. It does not contact the website.

## 5. Send one of the three file types

For immediate and deferred attendance, the physical terminal Export page offers
Wi-Fi on DELETE. Read the page's selected mode/batch before pressing it. The
normal ENROLL action remains that mode's USB export/help action. A fresh MENU
press cancels a pending Wi-Fi transfer. Capture stays stopped afterward until
explicitly restarted.
Confirmed laptop save and operator cancellation both use neutral feedback (LEDs
off, one short beep). Actual connection, save or receipt failures use red/two-beep
feedback. Cancellation never claims a successful laptop or website receipt.

USB can also request delivery while the receiver runs in a second window:

```powershell
# Existing deferred batch, not the class-session UUID:
& $fpPython $wifiTool send --port COM12 --type batch --id 'EXISTING_BATCH_UUID'
# Complete immediate check-in log:
& $fpPython $wifiTool send --port COM12 --type csv
# One occupied enrolled-template slot (replace 1 as needed):
& $fpPython $wifiTool send --port COM12 --type template --id 1
```

For template backups, slot selection currently uses this USB command. There is
no Wi-Fi slot-selection control on the laptop or OLED template browser. The
template bytes still travel over TLS; USB's existing guided `ALL` backup remains
available separately. No automatic first-time student-registration upload is
implied by either backup method.

Association and clock waits are bounded. The transfer has a 120-second firmware
limit and bounded TLS/read/write waits. Failures or cancellation retain files;
check the receiver, matching network, clock, certificate and device status, then
retry. No success is shown merely because Wi-Fi connected or bytes were sent.

## Saved files, receipts and website handoff

Verified outputs are below:

```text
private-data/fingerprint-wifi/received/<device-uuid>/
    batches/<batch-uuid>-<jsonl-sha256>.jsonl
    checkins/attendance-<csv-sha256>.csv
    templates/<gallery-uuid>/slot-<slot>-<wire-sha256>.fpt.json
```

The receiver checks type/size, framing, checksums/digests and record content,
flushes the file and verifies its readback before issuing a receipt binding type,
identifier, transfer digest, saved-file digest and count. Template records remain
`student_id: null`; commissioning labels are retained without inventing a student
binding. Historical immediate CSV UUIDs are preserved: the CSV origin uses an
older separate NVS identity from the authenticated transport sender.

For deferred Wi-Fi receipts, the transfer digest is SHA-256 of the ASCII binary
stream digest, `:`, and the interrupted-write flag (`0` or `1`). This binds the
recovery state as well as committed blocks. The existing `FPBATCHEND` binary
stream digest and USB framing remain unchanged. CSV/template transfer digests
are SHA-256 of the exact exported bytes; saved-file digests cover the resulting
CSV/JSONL/portable-template JSON file respectively.

Identical retries reuse a verified saved copy and return the same receipt. A
different completed snapshot gets its own file. Changed recovery flags produce
separate JSONL snapshots even when committed probe bytes are unchanged. Existing
files are never overwritten to hide a mismatch. Failed local writes may retain
a `.partial` file for review. Device originals remain after every receipt.

For deferred JSONL, continue at website sign-in/preview/import in
[LAPTOP-DOWNLOADER.md](LAPTOP-DOWNLOADER.md). Backend authorization and CSRF still
apply. Laptop authentication does not change the backend's current
`device_authenticated=false` evidence state or implement identity/time matching.
Immediate CSV import, enrollment upload/student binding and the browser upload
interface remain unfinished. Automatic background synchronization is not added.

To disable Wi-Fi, remove only its provisioned configuration:

```powershell
& $fpPython $wifiTool forget --port COM12
```

This retains fingerprints, immediate CSV and deferred captures. A stolen device
token should also be removed from the laptop receiver allowlist and replaced
before reprovisioning.

## Validation and remaining bench work

Native tests cover configuration/receipts, firmware arbitration, export framing
and failures. Python tests use synthetic records and real 127.0.0.1 TLS to cover
all three formats, certificate trust/hostname checks, authentication, corruption,
truncation, limits, disk failure and lost-receipt retries. The default firmware
build must pass before uploading. Physical Wi-Fi/RTC/OLED operation, radio power
effects and sustained device-to-laptop transfers still need bench validation.
No real credentials, scanner flash, biometric files or database records are
changed by the tests or source preparation.
