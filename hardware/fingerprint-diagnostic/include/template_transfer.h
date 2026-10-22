#pragma once

// Included by main.cpp after query/readIndexPage/slotStillFree are defined.
#include <stdio.h>
#include "portable_template.h"

constexpr uint32_t TEMPLATE_TRANSFER_TIMEOUT_MS = 8000;
constexpr uint32_t TEMPLATE_CONSOLE_TIMEOUT_MS = 15000;

struct TemplateParameters {
  uint16_t capacity = 0;
  uint16_t security = 0;
  uint16_t packetBytes = 0;
  uint16_t systemId = 0;
  uint32_t address = 0;
};

bool readTemplateParameters(TemplateParameters &parameters) {
  const uint8_t command[] = {0x0F};
  const QueryResult result = query(command, sizeof(command));
  if (!checkQuery("ReadSysPara", result) || result.reply.length != 17) return false;
  const uint8_t *p = result.reply.payload;
  const uint16_t packetCode = fingerprint::read16(p + 13);
  if (packetCode > 3) {
    Serial.println("Unsupported data packet size code.");
    return false;
  }
  parameters.capacity = fingerprint::read16(p + 5);
  parameters.security = fingerprint::read16(p + 7);
  parameters.packetBytes = 32U << packetCode;
  parameters.systemId = fingerprint::read16(p + 3);
  parameters.address = fingerprint::read32(p + 9);
  return parameters.capacity != 0;
}

bool receiveTemplate(fingerprint::SensorTemplate &data,
                     const TemplateParameters &parameters) {
  data.length = 0;
  const uint8_t upload[] = {0x08, 0x01}; // UpChar: sensor -> ESP32.
  const QueryResult result = query(upload, sizeof(upload), SENSOR_OPERATION_TIMEOUT_MS);
  if (!checkOperationAck("UpChar", result)) return false;
  const uint32_t started = millis();
  while (true) {
    uint8_t frame[fingerprint::MAX_DATA_FRAME] = {};
    for (size_t i = 0; i < fingerprint::HEADER_SIZE; ++i) {
      if (!readByte(frame[i], started, TEMPLATE_TRANSFER_TIMEOUT_MS)) {
        Serial.println("Template transfer timeout or missing final packet.");
        data.length = 0;
        return false;
      }
    }
    const size_t body = fingerprint::read16(frame + 7);
    if (body < 3 || body > parameters.packetBytes + 2U) {
      Serial.println("Invalid template data packet length.");
      data.length = 0;
      return false;
    }
    for (size_t i = fingerprint::HEADER_SIZE; i < fingerprint::HEADER_SIZE + body; ++i) {
      if (!readByte(frame[i], started, TEMPLATE_TRANSFER_TIMEOUT_MS)) {
        Serial.println("Truncated template data packet.");
        data.length = 0;
        return false;
      }
    }
    fingerprint::DataPacket packet;
    const auto error = fingerprint::decodeData(frame, fingerprint::HEADER_SIZE + body,
                                               result.reply.address, packet);
    if (error != fingerprint::FrameError::None) {
      Serial.printf("Invalid template packet: %s.\n", frameErrorText(error));
      data.length = 0;
      return false;
    }
    if (data.length + packet.length > sizeof(data.bytes)) {
      Serial.println("Template exceeds the 2048-byte implementation limit.");
      data.length = 0;
      return false;
    }
    memcpy(data.bytes + data.length, packet.bytes, packet.length);
    data.length += packet.length;
    if (packet.final) return true;
  }
}

bool sendTemplate(const fingerprint::SensorTemplate &data,
                  const TemplateParameters &parameters) {
  const uint8_t download[] = {0x09, 0x01}; // DownChar: ESP32 -> sensor buffer 1.
  if (!checkOperationAck("DownChar", query(download, sizeof(download),
                                            SENSOR_OPERATION_TIMEOUT_MS))) return false;
  for (size_t offset = 0; offset < data.length; ) {
    const size_t remaining = data.length - offset;
    const size_t chunk = remaining < parameters.packetBytes ? remaining : parameters.packetBytes;
    uint8_t frame[fingerprint::MAX_DATA_FRAME] = {};
    const size_t size = fingerprint::encodeData(frame, sizeof(frame), FINGERPRINT_ADDRESS,
        data.bytes + offset, chunk, offset + chunk == data.length);
    if (!size || scanner.write(frame, size) != size) return false;
    scanner.flush();
    offset += chunk;
  }
  // The compatible protocol has no per-data-packet ACK. Read back the buffer.
  delay(100);
  return true;
}

// A bounded line reader consumes an oversized line through its newline.
bool readTemplateConsoleLine(char *line, size_t capacity, uint32_t started = millis()) {
  size_t used = 0;
  bool overflow = false;
  while (static_cast<uint32_t>(millis() - started) < TEMPLATE_CONSOLE_TIMEOUT_MS) {
    if (!Serial.available()) { delay(1); continue; }
    const int value = Serial.read();
    if (value == '\r') continue;
    if (value == '\n') {
      line[used] = '\0';
      return !overflow;
    }
    if (used + 1 < capacity) line[used++] = static_cast<char>(value);
    else overflow = true;
  }
  line[used] = '\0';
  return false;
}

void templateTransferError() {
  Serial.println("FPERROR transfer stopped; no success receipt issued");
  // Do not interpret leftover hex data as commands (it can contain 'd'/'e').
  const uint32_t started = millis();
  uint32_t quiet = started;
  while (static_cast<uint32_t>(millis() - started) < 1000 &&
         static_cast<uint32_t>(millis() - quiet) < 300) {
    while (Serial.available()) { Serial.read(); quiet = millis(); }
    delay(1);
  }
}

// A bitmap covers the protocol's complete 16-bit slot range in 8 KiB.
static uint8_t templateInventory[8192];

bool readTemplateInventory(uint16_t &capacity, uint16_t &stored) {
  Serial.println("FPSTEP Reading scanner capacity and stored count");
  if (!authenticated) {
    Serial.println("No authenticated connection. Send b to probe again.");
    return false;
  }
  if (!readLibraryStats(capacity, stored)) return false;
  memset(templateInventory, 0, sizeof(templateInventory));
  if (!stored) return true;
  uint32_t found = 0;
  for (uint32_t base = 0; base < capacity; base += 256) {
    Reply table;
    if (!readIndexPage(static_cast<uint8_t>(base / 256), table)) return false;
    for (uint16_t bit = 0; bit < 256 && base + bit < capacity; ++bit) {
      if (table.payload[1 + bit / 8] & (1U << (bit % 8))) {
        const uint32_t slot = base + bit;
        templateInventory[slot / 8] |= 1U << (slot % 8);
        ++found;
      }
    }
  }
  if (found != stored) {
    Serial.println("Stored count and occupied-slot table disagree. Retry l before exporting.");
    return false;
  }
  return true;
}

void listTemplateSlots() {
  uint16_t capacity = 0, stored = 0;
  if (!readTemplateInventory(capacity, stored)) { templateTransferError(); return; }
  Serial.printf("FPLISTBEGIN 1 %u %u\n", capacity, stored);
  for (uint32_t slot = 0; slot < capacity; ++slot) {
    if (templateInventory[slot / 8] & (1U << (slot % 8))) {
      Serial.printf("FPSLOT %u\n", static_cast<unsigned>(slot));
    }
  }
  Serial.printf("FPLISTEND %u\n", stored);
  Serial.println("List complete. Use t <ID> or t ALL; the Python menu saves exports to files.");
}

bool exportTemplateSlot(uint16_t slot) {
  Serial.printf("FPSTEP Slot %u: checking connection and occupancy\n", slot);
  if (!authenticated) {
    Serial.println("No authenticated connection. Send b to probe again.");
    templateTransferError();
    return false;
  }
  TemplateParameters parameters;
  Reply table;
  if (!readTemplateParameters(parameters) || slot >= parameters.capacity ||
      !readIndexPage(static_cast<uint8_t>(slot / 256), table) ||
      !(table.payload[1 + (slot % 256) / 8] & (1U << (slot % 8)))) {
    Serial.println("Cannot export: requested slot is empty, out of range, or unverified.");
    templateTransferError();
    return false;
  }
  const uint8_t load[] = {0x07, 0x01, static_cast<uint8_t>(slot >> 8),
                        static_cast<uint8_t>(slot)};
  static fingerprint::SensorTemplate data;
  if (!checkOperationAck("LoadChar", query(load, sizeof(load), SENSOR_OPERATION_TIMEOUT_MS))) {
    data.clear();
    templateTransferError();
    return false;
  }
  Serial.printf("FPSTEP Slot %u: loaded; receiving template bytes\n", slot);
  if (!receiveTemplate(data, parameters)) {
    data.clear();
    templateTransferError();
    return false;
  }
  Serial.printf("FPSTEP Slot %u: %u bytes received; UART packet checksums verified\n",
      slot, static_cast<unsigned>(data.length));
  Serial.printf("FPBEGIN 1 %u %u %u %u %u %08lX\n", slot, parameters.capacity,
      parameters.security, parameters.packetBytes, parameters.systemId,
      static_cast<unsigned long>(parameters.address));
  for (size_t offset = 0; offset < data.length; offset += 32) {
    Serial.print("FPDATA ");
    char hex[65] = {};
    const size_t chunk = data.length - offset < 32 ? data.length - offset : 32;
    for (size_t i = 0; i < chunk; ++i) snprintf(hex + 2 * i, 3, "%02X", data.bytes[offset + i]);
    Serial.println(hex);
  }
  Serial.printf("FPEND %u %08lX\n", static_cast<unsigned>(data.length),
      static_cast<unsigned long>(fingerprint::crc32(data.bytes, data.length)));
  data.clear();
  Serial.printf("FPSTEP Slot %u: transfer complete; companion tool must save the file\n", slot);
  return true;
}

void exportAllTemplates() {
  uint16_t capacity = 0, stored = 0;
  if (!readTemplateInventory(capacity, stored)) { templateTransferError(); return; }
  Serial.printf("FPBATCHBEGIN %u\n", stored);
  uint16_t completed = 0;
  for (uint32_t slot = 0; slot < capacity; ++slot) {
    if (!(templateInventory[slot / 8] & (1U << (slot % 8)))) continue;
    Serial.printf("FPSTEP Exporting %u of %u: slot %u\n", completed + 1, stored,
        static_cast<unsigned>(slot));
    if (!exportTemplateSlot(static_cast<uint16_t>(slot))) {
      Serial.printf("FPBATCHERROR %u %u\n", completed, stored);
      return; // A damaged transfer must not be presented as a complete backup.
    }
    ++completed;
  }
  Serial.printf("FPBATCHEND %u %u\n", completed, stored);
  Serial.println("Batch transfer finished. Serial Monitor does not create backup files.");
}

void exportTemplate() {
  char line[32];
  Serial.println("Export: enter a slot ID or ALL, then press Enter. Use l to list slots.");
  if (!readTemplateConsoleLine(line, sizeof(line))) { templateTransferError(); return; }
  const char *cursor = line;
  if (fingerprint::onlyWhitespace(cursor)) {
    listTemplateSlots();
    Serial.println("Choose ID or ALL within 15 seconds; q cancels:");
    if (!readTemplateConsoleLine(line, sizeof(line))) { templateTransferError(); return; }
  }
  // Trim leading/trailing spaces for the human console selection.
  cursor = line;
  while (*cursor == ' ' || *cursor == '\t') ++cursor;
  char *end = line + strlen(line);
  while (end > cursor && (end[-1] == ' ' || end[-1] == '\t')) *--end = '\0';
  if (!strcmp(cursor, "q") || !strcmp(cursor, "Q")) {
    Serial.println("Export cancelled."); return;
  }
  if (!strcmp(cursor, "ALL") || !strcmp(cursor, "all") || !strcmp(cursor, "All")) {
    exportAllTemplates(); return;
  }
  uint32_t slot = 0;
  if (!fingerprint::parseNumber(cursor, slot, 10) ||
      !fingerprint::onlyWhitespace(cursor) || slot > 65535) {
    Serial.println("Invalid selection. Use t <occupied ID> or t ALL and Enter.");
    templateTransferError(); return;
  }
  exportTemplateSlot(static_cast<uint16_t>(slot));
}

void importTemplate() {
  char line[80];
  uint32_t length = 0, expectedCrc = 0;
  const char *cursor = line;
  if (!readTemplateConsoleLine(line, sizeof(line)) ||
      !fingerprint::parseNumber(cursor, length, 10) ||
      !fingerprint::parseNumber(cursor, expectedCrc, 16) ||
      !fingerprint::onlyWhitespace(cursor) ||
      !length || length > fingerprint::MAX_TEMPLATE_BYTES ||
      !authenticated) {
    Serial.println("Use the portable_template.py restore command for template import.");
    templateTransferError();
    return;
  }
  uint16_t capacity = 0, stored = 0, slot = 0;
  TemplateParameters parameters;
  if (!readLibraryStats(capacity, stored) || !findFreeSlot(capacity, stored, slot) ||
      !readTemplateParameters(parameters) || capacity != parameters.capacity) {
    templateTransferError();
    return;
  }
  static fingerprint::SensorTemplate data, verified;
  data.clear();
  verified.clear();
  Serial.printf("FPREADY %u %u\n", slot, static_cast<unsigned>(length));
  const uint32_t transferStarted = millis();
  while (data.length < length) {
    if (!readTemplateConsoleLine(line, sizeof(line), transferStarted)) {
      data.clear();
      templateTransferError();
      return;
    }
    const size_t characters = strlen(line);
    if (!characters || characters % 2 || characters > 64 || data.length + characters / 2 > length) {
      data.clear();
      templateTransferError();
      return;
    }
    for (size_t i = 0; i < characters; i += 2) {
      const int high = fingerprint::hexDigit(line[i]), low = fingerprint::hexDigit(line[i + 1]);
      if (high < 0 || low < 0) {
        data.clear();
        templateTransferError();
        return;
      }
      data.bytes[data.length++] = static_cast<uint8_t>((high << 4) | low);
    }
  }
  if (fingerprint::crc32(data.bytes, data.length) != expectedCrc ||
      !sendTemplate(data, parameters) || !receiveTemplate(verified, parameters) ||
      verified.length != data.length || memcmp(verified.bytes, data.bytes, data.length) ||
      !slotStillFree(slot)) {
    Serial.println("Import validation/readback failed before flash storage.");
    data.clear();
    verified.clear();
    templateTransferError();
    return;
  }
  const uint8_t save[] = {0x06, 0x01, static_cast<uint8_t>(slot >> 8), static_cast<uint8_t>(slot)};
  const uint8_t load[] = {0x07, 0x01, static_cast<uint8_t>(slot >> 8), static_cast<uint8_t>(slot)};
  if (!checkOperationAck("Store", query(save, sizeof(save), SENSOR_OPERATION_TIMEOUT_MS)) ||
      !checkOperationAck("LoadChar", query(load, sizeof(load), SENSOR_OPERATION_TIMEOUT_MS)) ||
      !receiveTemplate(verified, parameters) || verified.length != data.length ||
      memcmp(verified.bytes, data.bytes, data.length)) {
    Serial.printf("Storage not verified. Slot %u may now be occupied; send r.\n", slot);
    data.clear();
    verified.clear();
    templateTransferError();
    return;
  }
  Serial.printf("FPSTORED %u %u %08lX\n", slot, static_cast<unsigned>(length),
      static_cast<unsigned long>(expectedCrc));
  data.clear();
  verified.clear();
}

void verifyTemplateSlot() {
  char line[32];
  uint32_t slot = 0;
  const char *cursor = line;
  if (!readTemplateConsoleLine(line, sizeof(line)) ||
      !fingerprint::parseNumber(cursor, slot, 10) ||
      !fingerprint::onlyWhitespace(cursor) || slot > 65535 || !authenticated) {
    Serial.println("Use v <occupied slot ID> and Enter after scanner authentication.");
    return;
  }
  TemplateParameters parameters;
  Reply table;
  if (!readTemplateParameters(parameters) || slot >= parameters.capacity ||
      !readIndexPage(static_cast<uint8_t>(slot / 256), table) ||
      !(table.payload[1 + (slot % 256) / 8] & (1U << (slot % 8)))) {
    Serial.println("Cannot verify: requested slot is empty, out of range, or unverified.");
    return;
  }
  Serial.printf("\n--- Finger match against slot %u only ---\n", static_cast<unsigned>(slot));
  if (!waitForFinger(true)) return;
  const uint8_t features[] = {0x02, 0x01};
  if (!checkOperationAck("Img2Tz", query(features, sizeof(features),
                                           SENSOR_OPERATION_TIMEOUT_MS))) return;
  const uint8_t search[] = {0x04, 0x01, static_cast<uint8_t>(slot >> 8),
                           static_cast<uint8_t>(slot), 0x00, 0x01};
  const QueryResult result = query(search, sizeof(search), SENSOR_OPERATION_TIMEOUT_MS);
  if (result.error == QueryError::None && result.reply.payload[0] == 0x09) {
    // Compatible scanners return either a status-only ACK or the normal
    // five-byte Search result layout even when no identity was accepted.
    if (result.reply.length != 1 && result.reply.length != 5) {
      Serial.println("Search selected slot: invalid no-match acknowledgement length.");
      return;
    }
    Serial.printf("SLOTNOMATCH %u\n", static_cast<unsigned>(slot));
    return;
  }
  if (!checkQuery("Search selected slot", result)) return;
  if (result.reply.length != 5 || fingerprint::read16(result.reply.payload + 1) != slot) {
    Serial.println("Invalid single-slot search result; no identity accepted.");
    return;
  }
  Serial.printf("SLOTMATCH %u %u (raw, unitless matching score)\n",
      static_cast<unsigned>(slot), fingerprint::read16(result.reply.payload + 3));
}
