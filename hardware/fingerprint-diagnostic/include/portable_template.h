#pragma once

#include "fingerprint_protocol.h"

namespace fingerprint {
// Implementation limits, not claims about every AS608-compatible module.
constexpr size_t MAX_TEMPLATE_BYTES = 2048;
constexpr size_t MAX_DATA_BYTES = 256;
constexpr size_t MAX_DATA_FRAME = HEADER_SIZE + MAX_DATA_BYTES + 2;

struct SensorTemplate {
  uint8_t bytes[MAX_TEMPLATE_BYTES] = {};
  size_t length = 0;
  void clear() { memset(bytes, 0, sizeof(bytes)); length = 0; }
};

struct DataPacket {
  uint8_t bytes[MAX_DATA_BYTES] = {};
  size_t length = 0;
  bool final = false;
};

inline uint32_t crc32(const uint8_t *bytes, size_t length) {
  uint32_t crc = 0xFFFFFFFFUL;
  for (size_t i = 0; i < length; ++i) {
    crc ^= bytes[i];
    for (unsigned bit = 0; bit < 8; ++bit) {
      crc = (crc >> 1) ^ ((crc & 1) ? 0xEDB88320UL : 0);
    }
  }
  return crc ^ 0xFFFFFFFFUL;
}

inline size_t encodeData(uint8_t *frame, size_t capacity, uint32_t address,
                         const uint8_t *bytes, size_t length, bool final) {
  const size_t total = HEADER_SIZE + length + 2;
  if (!length || length > MAX_DATA_BYTES || capacity < total) return 0;
  frame[0] = 0xEF;
  frame[1] = 0x01;
  write32(frame + 2, address);
  frame[6] = final ? 0x08 : 0x02;
  frame[7] = static_cast<uint8_t>((length + 2) >> 8);
  frame[8] = static_cast<uint8_t>(length + 2);
  memcpy(frame + HEADER_SIZE, bytes, length);
  uint16_t checksum = 0;
  for (size_t i = 6; i < total - 2; ++i) checksum += frame[i];
  frame[total - 2] = static_cast<uint8_t>(checksum >> 8);
  frame[total - 1] = static_cast<uint8_t>(checksum);
  return total;
}

inline FrameError decodeData(const uint8_t *frame, size_t size,
                             uint32_t expectedAddress, DataPacket &packet) {
  packet = DataPacket{};
  if (size < HEADER_SIZE + 3 || size > MAX_DATA_FRAME) return FrameError::Length;
  if (frame[0] != 0xEF || frame[1] != 0x01) return FrameError::Header;
  const size_t wireLength = read16(frame + 7);
  if (wireLength < 3 || size != HEADER_SIZE + wireLength) return FrameError::Length;
  // Transfer packets must agree with the address in the initiating ACK.
  if (read32(frame + 2) != expectedAddress) return FrameError::Address;
  if (frame[6] != 0x02 && frame[6] != 0x08) return FrameError::PacketType;
  uint16_t checksum = 0;
  for (size_t i = 6; i < size - 2; ++i) checksum += frame[i];
  if (checksum != read16(frame + size - 2)) return FrameError::Checksum;
  packet.length = wireLength - 2;
  packet.final = frame[6] == 0x08;
  memcpy(packet.bytes, frame + HEADER_SIZE, packet.length);
  return FrameError::None;
}

inline int hexDigit(char digit) {
  if (digit >= '0' && digit <= '9') return digit - '0';
  if (digit >= 'a' && digit <= 'f') return digit - 'a' + 10;
  if (digit >= 'A' && digit <= 'F') return digit - 'A' + 10;
  return -1;
}

inline bool parseNumber(const char *&text, uint32_t &value, unsigned base) {
  while (*text == ' ' || *text == '\t') ++text;
  value = 0;
  bool haveDigit = false;
  while (*text && *text != ' ' && *text != '\t') {
    const int digit = hexDigit(*text++);
    if (digit < 0 || static_cast<unsigned>(digit) >= base ||
        value > (0xFFFFFFFFUL - static_cast<unsigned>(digit)) / base) return false;
    value = value * base + static_cast<unsigned>(digit);
    haveDigit = true;
  }
  return haveDigit;
}

inline bool onlyWhitespace(const char *text) {
  while (*text == ' ' || *text == '\t') ++text;
  return *text == '\0';
}
} // namespace fingerprint
