// PIN_BTN_ENROL, PIN_BTN_DELETE, PIN_BTN_MENU = 25, 26, 27
// PIN_LED_GREEN, PIN_LED_RED, PIN_BUZZER = 18, 19, 23
// PIN_I2C_SDA, PIN_I2C_SCL = 21, 22
// PIN_FP_TX, PIN_FP_RX, FP_UART_ID = 17, 16, 2

/*
 * Main firmware for the regular ESP32; build the complete PlatformIO project.
 * The GPIO defaults above are configured in include/config.h and
 * include/terminal_config.h. Scanner TX -> GPIO16; scanner RX <- GPIO17.
 * Scanner UART probes 57600 baud first, 8N1. PC console: 115200 baud.
 * OLED and DS1307 share SDA21/SCL22 at 100 kHz; addresses 0x3C and 0x68.
 *
 * esp32-sh1106 (default): immediate and deferred attendance in one runtime UI.
 * esp32: the same terminal with the alternative SSD1306 OLED adapter.
 * esp32-deferred: legacy capture-only development profile; no reflash is needed
 * to switch modes on the normal unified build. MENU selects mode and start/stop.
 *
 * Immediate: lift then present an enrolled finger. A successful match is saved
 * to /attendance.csv only with a valid RTC and writable local storage.
 * Deferred: prepare/select a class batch, confirm the mode, then capture probes
 * to ESP32 storage as PENDING MATCH. No enrolled slot is consumed by attendance.
 * ENROLL uses three presentations; DELETE requires a fresh confirmation; MENU
 * selects statistics, CSV export, clock setting, status or fingerprint erasure.
 * Serial a starts/resumes attendance. Diagnostic/backup commands pause it.
 * Recorded events are local; this firmware does not submit attendance to Django.
 * Normal application uploads preserve existing storage; do not erase/format it
 * just to update the firmware. See TERMINAL.md for wiring and operating steps.
 */

#include <Arduino.h>
#include "config.h"
#include "fingerprint_protocol.h"
#include "terminal_config.h"
#ifndef WIFI_TRANSFER_ENABLED
#define WIFI_TRANSFER_ENABLED 0
#endif

void serviceTerminalInputs();

#include "scanner_driver.h"

void printReport()
{
  if (!authenticated)
  {
    Serial.println("No authenticated connection. Send b to probe again.");
    return;
  }
  Serial.println("\n--- Scanner parameter report ---");
  Serial.println("Protocol: EF01 UART (AS608-compatible)");
  Serial.println("Model: not identified by these commands; AS608 is user supplied.");
  Serial.printf("ESP32 RX: GPIO%d; TX: GPIO%d; UART: 8N1\n",
                FINGERPRINT_RX_PIN, FINGERPRINT_TX_PIN);
  Serial.printf("Detected communication rate: %lu baud\n",
                static_cast<unsigned long>(connectedBaud));

  const uint8_t parametersCommand[] = {0x0F}; // ReadSysPara.
  const QueryResult parameters = query(parametersCommand, sizeof(parametersCommand));
  bool haveCapacity = false;
  uint16_t capacity = 0;
  if (checkQuery("ReadSysPara", parameters))
  {
    if (parameters.reply.length != 17)
    {
      Serial.printf("Unexpected parameter payload: %u bytes; expected 17.\n",
                    static_cast<unsigned>(parameters.reply.length));
    }
    else
    {
      const uint8_t *p = parameters.reply.payload;
      capacity = fingerprint::read16(p + 5);
      haveCapacity = true;
      const uint16_t packetCode = fingerprint::read16(p + 13);
      const uint16_t baudMultiplier = fingerprint::read16(p + 15);
      const uint32_t reportedBaud = static_cast<uint32_t>(baudMultiplier) * 9600UL;
      Serial.printf("Status register: 0x%04X\n", fingerprint::read16(p + 1));
      Serial.printf("System ID: 0x%04X (protocol ID, not a unique serial number)\n",
                    fingerprint::read16(p + 3));
      Serial.printf("Template capacity: %u\n", capacity);
      Serial.printf("Security level: %u\n", fingerprint::read16(p + 7));
      Serial.printf("Device address: 0x%08lX\n",
                    static_cast<unsigned long>(fingerprint::read32(p + 9)));
      if (packetCode <= 3)
      {
        Serial.printf("Data packet size: %u bytes (code %u)\n",
                      static_cast<unsigned>(32U << packetCode), packetCode);
      }
      else
      {
        Serial.printf("Data packet size code: %u (unknown encoding)\n", packetCode);
      }
      Serial.printf("Reported UART rate: %lu baud (multiplier %u)\n",
                    static_cast<unsigned long>(reportedBaud), baudMultiplier);
      if (reportedBaud != connectedBaud)
      {
        Serial.println("Reported rate differs from the working rate; check the module manual.");
      }
    }
  }

  const uint8_t countCommand[] = {0x1D}; // TemplateNum.
  const QueryResult count = query(countCommand, sizeof(countCommand));
  if (checkQuery("TemplateNum", count))
  {
    if (count.reply.length != 3)
    {
      Serial.println("Unexpected template-count payload; count unavailable.");
    }
    else
    {
      const uint16_t stored = fingerprint::read16(count.reply.payload + 1);
      Serial.printf("Stored templates: %u\n", stored);
      if (haveCapacity && stored <= capacity)
      {
        Serial.printf("Free template slots: %u\n", capacity - stored);
      }
      else if (haveCapacity)
      {
        Serial.println("Stored count exceeds reported capacity; check the module manual.");
      }
    }
  }
  Serial.println("Voltage, current, DPI, image dimensions, firmware version and");
  Serial.println("template byte size are not reported by these commands.");
}

bool readSearchCapacity(uint16_t &capacity)
{
  uint16_t stored = 0;
  if (!readLibraryStats(capacity, stored))
  {
    return false;
  }
  if (stored == 0)
  {
    Serial.println("The scanner has no enrolled templates. Send e to enrol, or c to test capture.");
    return false;
  }
  return true;
}

bool waitForFinger(bool present)
{
  Serial.printf("%s Waiting up to %lu seconds; x cancels.\n",
                present ? "Place a finger on the scanner." : "Lift your finger completely.",
                static_cast<unsigned long>(FINGER_WAIT_TIMEOUT_MS / 1000));
  const uint32_t started = millis();
  const uint8_t imageCommand[] = {0x01}; // GenImg: scanner's volatile image buffer.
  while (true)
  {
    while (Serial.available())
    {
      const int key = Serial.read();
      if (key == 'x' || key == 'X')
      {
        Serial.println("Capture cancelled.");
        return false;
      }
    }
    if (static_cast<uint32_t>(millis() - started) >= FINGER_WAIT_TIMEOUT_MS)
    {
      Serial.println(present ? "No finger detected before the wait expired. Retry the command."
                             : "Finger-removal wait expired. Lift your finger and retry e.");
      return false;
    }
    const QueryResult image = query(imageCommand, sizeof(imageCommand),
                                    SENSOR_OPERATION_TIMEOUT_MS);
    if (image.error == QueryError::None && image.reply.payload[0] == 0x02)
    {
      if (image.reply.length != 1)
      {
        Serial.println("GenImg: unexpected no-finger acknowledgement length.");
        return false;
      }
      if (!present)
      {
        Serial.println("Finger removed.");
        return true;
      }
      delay(100); // No finger yet; avoid flooding the scanner or console.
      continue;
    }
    if (!checkOperationAck("GenImg", image))
    {
      return false;
    }
    if (present)
    {
      Serial.println("Image capture: PASS.");
      return true;
    }
    delay(100); // Finger is still present; wait for a separate second scan.
  }
}

void captureTest(bool matchExisting)
{
  if (!authenticated)
  {
    Serial.println("No authenticated connection. Send b to probe again.");
    return;
  }
  Serial.println(matchExisting ? "\n--- Capture and match test ---"
                               : "\n--- Image capture test ---");
  uint16_t capacity = 0;
  if (matchExisting && !readSearchCapacity(capacity))
  {
    return;
  }
  if (!waitForFinger(true))
  {
    return;
  }
  if (!matchExisting)
  {
    Serial.println("Lift your finger. Send c to repeat, or m to capture and match.");
    return;
  }

  const uint8_t featureCommand[] = {0x02, 0x01}; // Img2Tz: character buffer 1.
  const QueryResult features = query(featureCommand, sizeof(featureCommand),
                                     SENSOR_OPERATION_TIMEOUT_MS);
  if (!checkOperationAck("Img2Tz", features))
  {
    return;
  }
  Serial.println("Feature extraction: PASS.");
  // Search all reported slots. The count is capacity, not the occupied count,
  // because enrolled templates can be sparse (e.g. IDs 7, 42 and 149).
  const uint8_t searchCommand[] = {
      0x04, 0x01, 0x00, 0x00,
      static_cast<uint8_t>(capacity >> 8), static_cast<uint8_t>(capacity)};
  const QueryResult match = query(searchCommand, sizeof(searchCommand),
                                  SENSOR_OPERATION_TIMEOUT_MS);
  if (match.error == QueryError::None && match.reply.payload[0] == 0x09)
  {
    Serial.println("NO MATCH: this capture did not match an enrolled template.");
  }
  else if (checkQuery("Search", match))
  {
    if (match.reply.length != 5)
    {
      Serial.println("Search: unexpected result payload; no match ID reported.");
      return;
    }
    const uint16_t id = fingerprint::read16(match.reply.payload + 1);
    const uint16_t score = fingerprint::read16(match.reply.payload + 3);
    if (id >= capacity)
    {
      Serial.println("Search: returned ID is outside the requested slot range.");
      return;
    }
    Serial.printf("MATCH: template ID=%u; confidence score=%u (raw sensor value).\n",
                  static_cast<unsigned>(id), static_cast<unsigned>(score));
  }
  Serial.println("Lift your finger. Send m to repeat with another finger.");
}

bool findFreeSlot(uint16_t capacity, uint16_t stored, uint16_t &id)
{
  if (stored == 0)
  {
    id = capacity > 1 ? 1 : 0;
    return true;
  }
  if (stored == capacity)
  {
    Serial.println("Template library is full. No enrolment slot is available.");
    return false;
  }
  bool zeroFree = false;
  for (uint32_t base = 0; base < capacity; base += 256)
  {
    Reply table;
    if (!readIndexPage(static_cast<uint8_t>(base / 256), table))
    {
      Serial.println("Cannot prove a slot is free. Enrolment stopped; d can clear the library.");
      return false;
    }
    for (uint16_t bit = 0; bit < 256 && base + bit < capacity; ++bit)
    {
      if ((table.payload[1 + bit / 8] & (1U << (bit % 8))) == 0)
      {
        if (base + bit == 0)
        {
          zeroFree = true; // Prefer IDs starting at 1 when possible.
        }
        else
        {
          id = static_cast<uint16_t>(base + bit);
          return true;
        }
      }
    }
  }
  if (zeroFree)
  {
    id = 0;
    return true;
  }
  Serial.println("No free slot found in the occupancy table.");
  return false;
}

bool slotStillFree(uint16_t id)
{
  const uint8_t command[] = {0x1D};
  const QueryResult count = query(command, sizeof(command));
  if (!checkQuery("TemplateNum", count) || count.reply.length != 3)
  {
    Serial.println("Cannot verify the slot before saving. Enrolment stopped.");
    return false;
  }
  if (fingerprint::read16(count.reply.payload + 1) == 0)
  {
    return true;
  }
  Reply table;
  if (!readIndexPage(static_cast<uint8_t>(id / 256), table))
  {
    return false;
  }
  const uint16_t bit = id % 256;
  if (table.payload[1 + bit / 8] & (1U << (bit % 8)))
  {
    Serial.println("Selected slot is now occupied. Enrolment stopped before saving.");
    return false;
  }
  return true;
}

void enrolFinger()
{
  if (!authenticated)
  {
    Serial.println("No authenticated connection. Send b to probe again.");
    return;
  }
  uint16_t capacity = 0, stored = 0, id = 0;
  if (!readLibraryStats(capacity, stored) || !findFreeSlot(capacity, stored, id))
  {
    return;
  }
  Serial.printf("\n--- Enrol your finger in free slot %u ---\n", id);
  Serial.println("Scan 1 of 2: use the finger you want to register.");
  if (!waitForFinger(true))
  {
    return;
  }
  const uint8_t firstFeatures[] = {0x02, 0x01};
  if (!checkOperationAck("Img2Tz buffer 1", query(firstFeatures, sizeof(firstFeatures),
                                                  SENSOR_OPERATION_TIMEOUT_MS)))
  {
    return;
  }
  if (!waitForFinger(false))
  {
    return;
  }
  Serial.println("Scan 2 of 2: place the SAME finger again.");
  if (!waitForFinger(true))
  {
    return;
  }
  const uint8_t secondFeatures[] = {0x02, 0x02};
  if (!checkOperationAck("Img2Tz buffer 2", query(secondFeatures, sizeof(secondFeatures),
                                                  SENSOR_OPERATION_TIMEOUT_MS)))
  {
    return;
  }
  const uint8_t combine[] = {0x05}; // RegModel: merge the two character buffers.
  if (!checkOperationAck("RegModel", query(combine, sizeof(combine),
                                           SENSOR_OPERATION_TIMEOUT_MS)))
  {
    return;
  }
  if (!slotStillFree(id))
  {
    return;
  }
  const uint8_t save[] = {0x06, 0x01, static_cast<uint8_t>(id >> 8),
                          static_cast<uint8_t>(id)};
  const QueryResult saved = query(save, sizeof(save), SENSOR_OPERATION_TIMEOUT_MS);
  if (!checkOperationAck("Store", saved))
  {
    Serial.println("Save not confirmed. Send r to check the library before retrying e.");
    return;
  }
  Serial.printf("ENROLLED: template ID=%u. Lift your finger, then send m to test it.\n", id);
  printReport();
}

bool confirmErase()
{
  Serial.println("This permanently deletes ALL stored fingerprints. Type ERASE then Enter within 15 seconds; x cancels.");
  char text[16] = {};
  size_t length = 0;
  bool tooLong = false;
  const uint32_t started = millis();
  while (static_cast<uint32_t>(millis() - started) < ERASE_CONFIRM_TIMEOUT_MS)
  {
    if (!Serial.available())
    {
      delay(1);
      continue;
    }
    const int key = Serial.read();
    if (length == 0 && (key == 'x' || key == 'X'))
    {
      Serial.println("Erase cancelled.");
      return false;
    }
    if (key == '\r' || key == '\n')
    {
      if (length == 0 && !tooLong)
        continue; // Ignore Enter after the d command.
      Serial.println("");
      if (!tooLong && strcmp(text, "ERASE") == 0)
        return true;
      Serial.println("Erase cancelled: confirmation did not match ERASE.");
      return false;
    }
    if ((key == 8 || key == 127) && length > 0 && !tooLong)
    {
      text[--length] = '\0';
      Serial.print("\b \b");
    }
    else if (key >= 32 && key <= 126)
    {
      Serial.printf("%c", key);
      if (length < sizeof(text) - 1)
        text[length++] = static_cast<char>(key);
      else
        tooLong = true;
    }
  }
  Serial.println("\nErase cancelled: confirmation timed out.");
  return false;
}

void eraseLibrary()
{
  if (!authenticated)
  {
    Serial.println("No authenticated connection. Send b to probe again.");
    return;
  }
  uint16_t capacity = 0, stored = 0;
  if (!readLibraryStats(capacity, stored))
    return;
  if (stored == 0)
  {
    Serial.println("The template library is already empty. Send e to enrol your finger.");
    return;
  }
  Serial.printf("\nErase request: %u stored templates.\n", stored);
  if (!confirmErase())
    return;
  const uint8_t erase[] = {0x0D}; // Empty: delete all templates in sensor flash.
  if (!checkOperationAck("Empty", query(erase, sizeof(erase),
                                        SENSOR_OPERATION_TIMEOUT_MS)))
  {
    Serial.println("Erase not confirmed. Send r to check the library.");
    return;
  }
  const uint8_t countCommand[] = {0x1D};
  const QueryResult count = query(countCommand, sizeof(countCommand));
  if (!checkQuery("TemplateNum", count) || count.reply.length != 3)
  {
    Serial.println("Erase acknowledged, but count verification failed. Send r.");
    return;
  }
  if (fingerprint::read16(count.reply.payload + 1) != 0)
  {
    Serial.println("Erase acknowledged, but the scanner still reports stored templates. Send r.");
    return;
  }
  Serial.println("ERASED: stored templates=0. Send e to enrol your own finger.");
}

#include "template_transfer.h"
#include "probe_experiment.h"
#if DEFERRED_ENABLED
#include "deferred_device.h"
#endif

void printHelp()
{
  Serial.println("\nr = read parameters/count again; b = repeat baud probe; h = help");
  Serial.println("c = capture image; m = capture and match existing templates; x = cancel finger wait");
  Serial.println("e = enrol your finger in a free slot; d = erase ALL templates after typing ERASE");
  Serial.println("l = list occupied slots; t <ID> or t ALL = export; u = import via Python tool");
  Serial.println("t <ID> = export enrolled template; Python menu saves files and shows progress");
  Serial.println("v <ID> = capture and search only that occupied slot");
  Serial.println("q = export one fresh probe; j = search saved probe; k = direct buffer comparison");
#if DEFERRED_ENABLED
  Serial.println("z = prepare/manage deferred class batches: begin/arm/stop/list/export; saves remain PENDING MATCH");
#endif
#if WIFI_TRANSFER_ENABLED && DEFERRED_ENABLED
  Serial.println("w = private Wi-Fi setup/status/clock/send; TLS laptop receipt is not website upload");
#endif
  Serial.println("Console is 115200 baud. Place/lift your finger when the active test prompts you.");
#if TERMINAL_ENABLED
  Serial.println("a = start/resume attendance; p = pause attendance; 1/2/3 = ENROL/DELETE/MENU keys");
  Serial.println("f = format local check-in storage after typing FORMAT (deletes local files)");
#endif
}

#if TERMINAL_ENABLED
#include "attendance_terminal.h"
terminal::TerminalHardware terminalHardware;
#if DEFERRED_ENABLED
terminal::AttendanceTerminal<terminal::TerminalHardware> attendanceTerminal(terminalHardware,&deferredDevice);
#else
terminal::AttendanceTerminal<terminal::TerminalHardware> attendanceTerminal(terminalHardware);
#endif
void serviceTerminalInputs() { attendanceTerminal.pollInputs(); }
#else
void serviceTerminalInputs() {}
#endif

#if WIFI_TRANSFER_ENABLED && DEFERRED_ENABLED
#include "wifi_transfer.h"
wireless::Transfer wifiTransfer(deferredDevice);
bool queueWireless(const char *type,const char *id) { return wifiTransfer.queue(type,id); }
bool cancelWireless() {
#if TERMINAL_ENABLED
  return digitalRead(TERMINAL_MENU_PIN)==LOW;
#else
  return false;
#endif
}
bool seedWirelessClock() {
#if TERMINAL_ENABLED
  terminal::DateTime local; int64_t epoch=0;
  if(!terminalHardware.readClock(local) || !terminal::valid(local) ||
      !wireless::civilEpoch(local.year,local.month,local.day,local.hour,local.minute,local.second,
        TERMINAL_UTC_OFFSET_SECONDS,epoch)) return false;
  timeval now={}; now.tv_sec=static_cast<decltype(now.tv_sec)>(epoch);
  return settimeofday(&now,nullptr)==0;
#else
  return false;
#endif
}
#endif

void setup()
{
  Serial.begin(CONSOLE_BAUD);
  delay(1500); // Allow the scanner and USB console to start.
#if TERMINAL_ENABLED
  Serial.println("\nESP32 fingerprint attendance terminal");
#else
  Serial.println("\nESP32 fingerprint scanner diagnostic");
#endif
  printHelp();
#if DEFERRED_ENABLED
  deferredDevice.begin();
#endif
#if TERMINAL_ENABLED
  attendanceTerminal.begin();
#endif
#if WIFI_TRANSFER_ENABLED && DEFERRED_ENABLED
  wifiTransfer.begin(cancelWireless,seedWirelessClock); deferredDevice.setWireless(queueWireless);
#endif
  probeScanner();
#if TERMINAL_ENABLED
  attendanceTerminal.bootReady();
#endif
}

void loop()
{
#if WIFI_TRANSFER_ENABLED && DEFERRED_ENABLED
  // A queued transfer owns file/scanner access until completion/cancellation.
  // Input sampling still services feedback, but no UI/serial actions execute.
  if(wifiTransfer.busy()) { wifiTransfer.tick(); delay(10); return; }
#endif
  if (Serial.available())
  {
    const int command = Serial.read();
#if DEFERRED_ENABLED
    if (command != '\r' && command != '\n')
      deferredDevice.stop();
#endif
#if TERMINAL_ENABLED
    // A persistent maintenance pause protects multi-command Python sessions as
    // well as individual transfers. UART waits only sample buttons; they never
    // execute UI actions or print unsolicited progress into an export stream.
    const char *maintenance = "rRbBcCmMeEdDtTlLuUvVqQjJkKzZwWhH?fFpP";
    if (command > 0 && strchr(maintenance, command))
      attendanceTerminal.pause();
#endif
    switch (command)
    {
    case 'r':
    case 'R':
      printReport();
      break;
    case 'b':
    case 'B':
      probeScanner();
      break;
    case 'c':
    case 'C':
      captureTest(false);
      break;
    case 'm':
    case 'M':
      captureTest(true);
      break;
    case 'e':
    case 'E':
      enrolFinger();
      break;
    case 'd':
    case 'D':
      eraseLibrary();
      break;
    case 't':
    case 'T':
      exportTemplate();
      break;
    case 'l':
    case 'L':
      listTemplateSlots();
      break;
    case 'u':
    case 'U':
      importTemplate();
      break;
    case 'v':
    case 'V':
      verifyTemplateSlot();
      break;
    case 'q':
    case 'Q':
      captureProbe();
      break;
    case 'j':
    case 'J':
      compareSavedProbe();
      break;
    case 'k':
    case 'K':
      compareSavedProbe(true);
      break;
#if DEFERRED_ENABLED
    case 'z':
    case 'Z':
      deferredDevice.command();
      break;
#endif
#if WIFI_TRANSFER_ENABLED && DEFERRED_ENABLED
    case 'w':
    case 'W':
      wifiTransfer.command();
      break;
#endif
    case 'h':
    case 'H':
    case '?':
      printHelp();
      break;
#if TERMINAL_ENABLED
    case 'a':
    case 'A':
      attendanceTerminal.resume();
      break;
    case 'p':
    case 'P':
      Serial.println("UI paused. Send a to resume.");
      break;
    case '1':
    case '2':
    case '3':
      attendanceTerminal.key(command - '1');
      break;
    case 'x':
    case 'X':
      attendanceTerminal.cancel();
      break;
    case 'f':
    case 'F':
      attendanceTerminal.formatStorage();
      break;
#endif
    default:
      break;
    }
  }
#if TERMINAL_ENABLED
  attendanceTerminal.tick();
#endif
#if DEFERRED_ENABLED && !TERMINAL_ENABLED
  deferredDevice.tick();
#endif
  delay(10);
}
