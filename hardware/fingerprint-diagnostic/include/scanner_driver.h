#pragma once

#include <Arduino.h>
#include "config.h"
#include "fingerprint_protocol.h"

// Each sketch provides an input-only service hook and its own report output.
void serviceTerminalInputs();
void printReport();

using fingerprint::Reply;
// UART1 is available on both the original ESP32 and ESP32-S3. UART0 remains
// available for the board's USB-to-UART console. Pins are assigned explicitly.
HardwareSerial scanner(1);
uint32_t connectedBaud = 0;
bool authenticated = false;

enum class QueryError { None, Timeout, InvalidFrame };
struct QueryResult {
  QueryError error = QueryError::None;
  fingerprint::FrameError frameError = fingerprint::FrameError::None;
  Reply reply;
};

bool readByte(uint8_t &value, uint32_t started, uint32_t timeoutMs) {
  while (static_cast<uint32_t>(millis() - started) < timeoutMs) {
    serviceTerminalInputs();
    if (scanner.available()) {
      value = static_cast<uint8_t>(scanner.read());
      return true;
    }
    delay(1);
  }
  return false;
}

QueryResult query(const uint8_t *command, size_t length,
                  uint32_t timeoutMs = REPLY_TIMEOUT_MS) {
  QueryResult result;
  uint8_t frame[fingerprint::MAX_FRAME_SIZE] = {};
  const size_t requestSize = fingerprint::encodeCommand(
      frame, sizeof(frame), FINGERPRINT_ADDRESS, command, length);
  if (!requestSize) {
    result.error = QueryError::InvalidFrame;
    result.frameError = fingerprint::FrameError::Length;
    return result;
  }
  // Drain a snapshot, so continuous noise cannot make this step unbounded.
  const int pending=scanner.available();
  for (int i=0;i<pending;++i) {
    scanner.read();
  }
  scanner.write(frame, requestSize);
  scanner.flush();
  const uint32_t started = millis();

  // Ignore startup noise until an EF01 header is found, with one total timeout.
  bool haveEF = false;
  uint8_t byte = 0;
  while (true) {
    if (!readByte(byte, started, timeoutMs)) {
      result.error = QueryError::Timeout;
      return result;
    }
    if (haveEF && byte == 0x01) {
      frame[0] = 0xEF;
      frame[1] = 0x01;
      break;
    }
    haveEF = (byte == 0xEF);
  }
  for (size_t i = 2; i < fingerprint::HEADER_SIZE; ++i) {
    if (!readByte(frame[i], started, timeoutMs)) {
      result.error = QueryError::Timeout;
      return result;
    }
  }
  const size_t bodySize = fingerprint::read16(frame + 7);
  if (bodySize < 3 || bodySize > sizeof(frame) - fingerprint::HEADER_SIZE) {
    result.error = QueryError::InvalidFrame;
    result.frameError = fingerprint::FrameError::Length;
    return result;
  }
  const size_t frameSize = fingerprint::HEADER_SIZE + bodySize;
  for (size_t i = fingerprint::HEADER_SIZE; i < frameSize; ++i) {
    if (!readByte(frame[i], started, timeoutMs)) {
      result.error = QueryError::Timeout;
      return result;
    }
  }
  result.frameError = fingerprint::decodeAck(
      frame, frameSize, FINGERPRINT_ADDRESS, result.reply);
  if (result.frameError != fingerprint::FrameError::None) {
    result.error = QueryError::InvalidFrame;
  }
  return result;
}

const char *frameErrorText(fingerprint::FrameError error) {
  switch (error) {
  case fingerprint::FrameError::Length: return "invalid packet length";
  case fingerprint::FrameError::Header: return "invalid packet header";
  case fingerprint::FrameError::Address: return "unexpected device address";
  case fingerprint::FrameError::PacketType: return "expected an ACK packet";
  case fingerprint::FrameError::Checksum: return "checksum mismatch";
  default: return "OK";
  }
}

bool checkQuery(const char *name, const QueryResult &result) {
  if (result.error == QueryError::Timeout) {
    Serial.printf("%s: timeout (no complete EF01 response).\n", name);
    return false;
  }
  if (result.error == QueryError::InvalidFrame) {
    Serial.printf("%s: %s.\n", name, frameErrorText(result.frameError));
    return false;
  }
  if (result.reply.payload[0] != 0x00) {
    Serial.printf("%s: scanner confirmation code 0x%02X", name,
                  result.reply.payload[0]);
    if (result.reply.payload[0] == 0x13) {
      Serial.print(" (incorrect password)");
    } else if (result.reply.payload[0] == 0x01) {
      Serial.print(" (scanner reports a received-packet error)");
    } else if (result.reply.payload[0] == 0x03) {
      Serial.print(" (image capture failed; reposition the finger)");
    } else if (result.reply.payload[0] == 0x06) {
      Serial.print(" (image too messy; clean and reposition the finger)");
    } else if (result.reply.payload[0] == 0x07) {
      Serial.print(" (too few usable fingerprint features)");
    } else if (result.reply.payload[0] == 0x15) {
      Serial.print(" (no usable fingerprint image)");
    } else if (result.reply.payload[0] == 0x0A) {
      Serial.print(" (the two enrollment scans did not agree; use the same finger)");
    } else if (result.reply.payload[0] == 0x18) {
      Serial.print(" (scanner flash-write error)");
    }
    Serial.println(".");
    return false;
  }
  return true;
}

bool checkOperationAck(const char *name, const QueryResult &result) {
  if (!checkQuery(name, result)) {
    return false;
  }
  if (result.reply.length != 1) {
    Serial.printf("%s: unexpected acknowledgement length.\n", name);
    return false;
  }
  return true;
}

bool readLibraryStats(uint16_t &capacity, uint16_t &stored) {
  const uint8_t command[] = {0x0F};
  const QueryResult result = query(command, sizeof(command));
  if (!checkQuery("ReadSysPara", result)) {
    return false;
  }
  if (result.reply.length != 17) {
    Serial.println("Cannot search: unexpected parameter payload.");
    return false;
  }
  capacity = fingerprint::read16(result.reply.payload + 5);
  if (capacity == 0) {
    Serial.println("Cannot search: scanner reports zero template capacity.");
    return false;
  }
  const uint8_t countCommand[] = {0x1D};
  const QueryResult count = query(countCommand, sizeof(countCommand));
  if (!checkQuery("TemplateNum", count)) {
    return false;
  }
  if (count.reply.length != 3) {
    Serial.println("Cannot search: unexpected template-count payload.");
    return false;
  }
  stored = fingerprint::read16(count.reply.payload + 1);
  Serial.printf("Stored templates: %u; search capacity: %u\n", stored, capacity);
  if (stored > capacity) {
    Serial.println("Cannot search: stored count exceeds reported capacity.");
    return false;
  }
  return true;
}


bool readIndexPage(uint8_t page, Reply &reply) {
  const uint8_t command[] = {0x1F, page}; // ReadIndexTable: 256 occupancy bits.
  const QueryResult result = query(command, sizeof(command));
  if (!checkQuery("ReadIndexTable", result)) {
    return false;
  }
  if (result.reply.length != 33) {
    Serial.println("ReadIndexTable: unexpected occupancy-table length.");
    return false;
  }
  reply = result.reply;
  return true;
}


void probeScanner() {
  // 57600 first for AS608; all standard 9600 multiples, then common extensions.
  const uint32_t baudRates[] = {
      57600, 115200, 9600, 19200, 38400, 28800, 48000,
      67200, 76800, 86400, 96000, 105600, 230400, 460800};
  authenticated = false;
  connectedBaud = 0;
  uint8_t verifyCommand[5] = {0x13}; // VfyPwd; does not change the password.
  fingerprint::write32(verifyCommand + 1, FINGERPRINT_PASSWORD);
  Serial.println("\nProbing AS608-compatible scanners...");
  for (uint32_t baud : baudRates) {
    scanner.end();
    scanner.begin(baud, SERIAL_8N1, FINGERPRINT_RX_PIN, FINGERPRINT_TX_PIN);
    delay(80);
    Serial.printf("Trying %lu baud... ", static_cast<unsigned long>(baud));
    QueryResult result = query(verifyCommand, sizeof(verifyCommand));
    if (result.error == QueryError::Timeout) {
      // Retry once in case the module was still starting or an ACK was lost.
      result = query(verifyCommand, sizeof(verifyCommand));
    }
    if (result.error == QueryError::None) {
      connectedBaud = baud;
      if (!checkQuery("VfyPwd", result)) {
        Serial.println("A scanner responded. Check password/protocol; probing stopped.");
        return;
      }
      authenticated = true;
      Serial.println("authenticated.");
      printReport();
      return;
    }
    checkQuery("VfyPwd", result);
  }
  Serial.println("No compatible scanner found. Check power, common ground, TX/RX,");
  Serial.println("configured address/password and the scanner's actual protocol.");
  Serial.println("Unknown UART scanners using a different protocol need another driver.");
}

