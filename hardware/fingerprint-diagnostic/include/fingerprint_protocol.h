#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

// AS608 and compatible EF01 UART protocol. Short command/ACK codec;
// portable_template.h handles larger template data packets separately.
namespace fingerprint {
constexpr size_t HEADER_SIZE = 9;
constexpr size_t MAX_FRAME_SIZE = 64;
constexpr size_t MAX_PAYLOAD_SIZE = MAX_FRAME_SIZE - HEADER_SIZE - 2;

inline uint16_t read16(const uint8_t *p) {
  return (static_cast<uint16_t>(p[0]) << 8) | p[1];
}

inline uint32_t read32(const uint8_t *p) {
  return (static_cast<uint32_t>(p[0]) << 24) |
         (static_cast<uint32_t>(p[1]) << 16) |
         (static_cast<uint32_t>(p[2]) << 8) | p[3];
}

inline void write32(uint8_t *p, uint32_t value) {
  p[0] = static_cast<uint8_t>(value >> 24);
  p[1] = static_cast<uint8_t>(value >> 16);
  p[2] = static_cast<uint8_t>(value >> 8);
  p[3] = static_cast<uint8_t>(value);
}

enum class FrameError {
  None,
  Length,
  Header,
  Address,
  PacketType,
  Checksum,
};

struct Reply {
  uint8_t payload[MAX_PAYLOAD_SIZE] = {};
  size_t length = 0; // Includes the confirmation code; excludes the checksum.
  uint32_t address = 0;
};

inline size_t encodeCommand(uint8_t *frame, size_t capacity, uint32_t address,
                            const uint8_t *payload, size_t length) {
  const size_t total = HEADER_SIZE + length + 2;
  if (length == 0 || length > MAX_PAYLOAD_SIZE || capacity < total) {
    return 0;
  }
  frame[0] = 0xEF;
  frame[1] = 0x01;
  write32(frame + 2, address);
  frame[6] = 0x01; // Command packet.
  const uint16_t wireLength = static_cast<uint16_t>(length + 2);
  frame[7] = static_cast<uint8_t>(wireLength >> 8);
  frame[8] = static_cast<uint8_t>(wireLength);
  memcpy(frame + HEADER_SIZE, payload, length);
  uint16_t checksum = 0;
  for (size_t i = 6; i < total - 2; ++i) {
    checksum = static_cast<uint16_t>(checksum + frame[i]);
  }
  frame[total - 2] = static_cast<uint8_t>(checksum >> 8);
  frame[total - 1] = static_cast<uint8_t>(checksum);
  return total;
}

inline FrameError decodeAck(const uint8_t *frame, size_t size,
                            uint32_t expectedAddress, Reply &reply) {
  reply = Reply{}; // Never expose stale parameters after a failed query.
  if (size < HEADER_SIZE + 3 || size > MAX_FRAME_SIZE) {
    return FrameError::Length;
  }
  if (frame[0] != 0xEF || frame[1] != 0x01) {
    return FrameError::Header;
  }
  const size_t wireLength = read16(frame + 7);
  if (wireLength < 3 || size != HEADER_SIZE + wireLength) {
    return FrameError::Length;
  }
  // The factory address is used for the initial probe. Some compatible modules
  // return their own address. A manually configured address is checked exactly.
  if (expectedAddress != 0xFFFFFFFFUL && read32(frame + 2) != expectedAddress) {
    return FrameError::Address;
  }
  if (frame[6] != 0x07) {
    return FrameError::PacketType;
  }
  uint16_t checksum = 0;
  for (size_t i = 6; i < size - 2; ++i) {
    checksum = static_cast<uint16_t>(checksum + frame[i]);
  }
  if (checksum != read16(frame + size - 2)) {
    return FrameError::Checksum;
  }
  reply.address = read32(frame + 2);
  reply.length = wireLength - 2;
  memcpy(reply.payload, frame + HEADER_SIZE, reply.length);
  return FrameError::None;
}
} // namespace fingerprint
