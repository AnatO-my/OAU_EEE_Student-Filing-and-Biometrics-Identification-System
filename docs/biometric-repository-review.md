# Biometric attendance repository review

Source: https://github.com/macmizy/biometricattendance
Inspected commit: 3eb0e6b49b0b823e3d6931de637d05b1e3950d03 (main at review time).
Review date: 7 October 2026. Static source review only; no firmware compilation,
hardware execution or PHP/MySQL deployment was performed. No code was integrated.

## What it contains

- ESP8266 Arduino firmware, Adafruit fingerprint sensor library and SSD1306 OLED.
- PHP/MySQL user management, scan handling and attendance log pages.
- Sensor enrollment/deletion through polled commands from the PHP server.
- A spreadsheet download consisting of an HTML table with an .xls filename.

Sources:
https://github.com/macmizy/biometricattendance/blob/3eb0e6b49b0b823e3d6931de637d05b1e3950d03/projectBio.ino
https://github.com/macmizy/biometricattendance/blob/3eb0e6b49b0b823e3d6931de637d05b1e3950d03/getdata.php
https://github.com/macmizy/biometricattendance/blob/3eb0e6b49b0b823e3d6931de637d05b1e3950d03/install.php
https://github.com/macmizy/biometricattendance/blob/3eb0e6b49b0b823e3d6931de637d05b1e3950d03/Export_Excel.php

## Architecture mismatch with our project

Firmware captures an image, converts it to a sensor template and calls
fingerFastSearch. It POSTs the already matched FingerID, not the captured image
or template. Enrollment calls createModel/storeModel on the sensor. PHP maps the
sensor slot ID to its users table and toggles attendance time-in/time-out.
The words login/logout in the response mean attendance actions, not Django user
sessions or authenticated access to student records.

Our agreed architecture keeps identification/matching off the device. Therefore
this firmware cannot provide our server matcher with the needed reading as-is.
Before selecting an implementation, confirm the exact sensor model, image/template
export support, template format and compatible server matcher. A sensor slot ID
alone cannot support server-side matching. The repository supplies no server
matching implementation. ESP8266 is also not automatically an ESP32-compatible
firmware target; adapt and compile against the actual board and pinout.

## Useful references and concrete issues

Reusable ideas: staged enrollment prompts, status display, sensor error handling,
device/server feedback and command acknowledgement workflow. Rebuild integrations
against our Django JSON API and custom user/student models.

Observed issues in the reviewed source:
- Plain HTTP device requests; no device authentication or replay/idempotency
  checks are visible in getdata.php's request handling.
- Repeated positive scans can re-send the same finger and toggle check-in/out;
  no unique scan-event identifier establishes deduplication.
- Deletion requests remove users rows before successful sensor deletion is
  acknowledged, allowing server/device state to diverge.
- users.serialnumber and users_logs.serialnumber are double, unsuitable for
  our identifiers that must preserve leading zeros and text.
- Device confidence is present in library calls/comments but not transmitted as
  a distinct fingerprint_score; that value would not be an academic score.
- Export_Excel.php directly interpolates the submitted date into a SQL query.
- Several getdata.php enrollment INSERT bind calls have mismatched parameter
  counts; these paths need repair and tests rather than copying wholesale.
- The inspected tree has no README, automated test suite or LICENSE file.
  Establish reuse permission before copying source into our repository.

## Required project-side work

Device identity/provisioning/revocation; protected enrollment-to-student UUID
binding; reading payload/version; matcher/template compatibility; capture and
match-quality thresholds; structured diagnostic codes; server feedback; event
UUIDs and retry/deduplication; enrollment/deletion acknowledgements; device
integration tests. Define attendance separately if it is required; identification
must not silently log an attendance event or create a React/Django account session.
Our staff/student permissions and controlled profile access remain authoritative.
