# Wi-Fi transfer implementation validation — 21 October 2026

The normal `esp32-sh1106` build includes the opt-in Wi-Fi station and outgoing
TLS client. It supports committed deferred batches, the existing local attendance
CSV and a selected enrolled-template backup. USB transfer remains available.
No board upload, actual Wi-Fi association, real biometric transfer or database
write was performed for this implementation.

## Firmware and native verification

Final PlatformIO `run -e esp32-sh1106` completed successfully with no compiler
warnings: 94,784 bytes static RAM (28.9%) and 1,035,437 bytes program flash (79.0%
of the existing 1,310,720-byte application partition). Partition layout and
filesystem formatting behavior were not changed.

Both new native suites passed under C++11 with `-Wall -Wextra -Werror`:

- `wifi_transfer_format_test.cpp`: exact bounded provisioning layout, malformed
  and truncated inputs, receipt type/identifier/digest/count binding, RTC civil
  time conversion, leap days, UTC+1 offset and the pinned core's 2037 ceiling.
- `wifi_transfer_test.cpp`: the actual unified firmware and controller with
  simulated Wi-Fi/TLS/filesystem/scanner adapters; all three transfer types;
  per-snapshot pending/recovery receipt binding; config save/readback and forgetting;
  changed certificate pin, wrong receipt, connection/short-write failure,
  association timeout and physical MENU cancellation before association and
  during frame transmission; neutral cancellation feedback; retained files and no
  competing capture or scanner Store/Delete/Empty operation. The Export page's
  DELETE action queues transfer instead of fingerprint deletion.

Native TLS and SHA adapters are test doubles. They verify control flow and the
exact input to the recovery-binding hash; they do not establish the ESP32's
cryptographic behavior or physical radio reliability. The real pinned libraries
are included in the successful ESP32 build. Laptop Python tests separately use
real hashing, file flush/readback and TLS sockets; see the operator guide and
the combined `tools/check_host.ps1` run for their results.

The host-check runner now includes both suites alongside the existing checks.
The combined suite requires permission for synthetic local loopback sockets;
no shared development database or scanner is used.

The combined check passed all 19 native suite/variant executions. After the
final neutral-cancellation and generic export-screen wording adjustment, the
Wi-Fi/unified-device native suites were rerun successfully and the normal
SH1106 firmware was rebuilt successfully. The final Python discovery passed all
81 tests, including real TLS loopback transfers of all three file types,
certificate/hostname/plaintext rejection, authentication, bounded/corrupt input,
file flush/readback failure, retry after a lost receipt and immediate cancellation
handling. These are synthetic local tests, not an ESP32 radio bench result.

## Important reviewed boundaries

- Provisioning and transfer are explicit. Normal boot leaves Wi-Fi off and
  attendance stopped. A transfer pauses acquisition and owns the transport until
  completion/failure; the scanner UART is never shared with live capture.
- The client verifies the configured CA, hostname and exact leaf-certificate
  SHA-256 before sending its device token or any export. There is no insecure
  fallback or inbound wireless command server. The local pinned Mbed TLS 2.28.7
  hostname behavior requires the certificate compatibility described in
  [WIFI-TRANSFER.md](WIFI-TRANSFER.md).
- A valid configured DS1307 can seed the TLS clock using Africa/Lagos local time
  (`TERMINAL_UTC_OFFSET_SECONDS=3600`). Otherwise SNTP or explicit USB clock
  provisioning is needed. This does not assign wall-clock times to unidentified
  deferred captures.
- A receiver receipt confirms a validated laptop copy only. No receipt erases
  files or establishes student identity, attendance marking or website import.
- Historical CSV-origin UUIDs are preserved separately from the Wi-Fi sender's
  commissioned device identity. Unassigned enrollment backups remain unassigned.
- Wi-Fi credentials and the per-device token are stored in private laptop files
  and ordinary ESP32 NVS; flash encryption, secure boot and deployment-level key
  management are outside this prototype.

Physical tests still needed: real AP/hotspot association; ESP32 CA/hostname/pin
verification and clock bootstrap; all three file transfers with the actual
scanner; radio/power stability; interrupt/retry and reboot behavior; OLED/LED/
buzzer feedback and bounded cancellation during the real TLS handshake.
