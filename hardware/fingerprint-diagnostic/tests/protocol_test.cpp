#include <assert.h>
#include <stdio.h>
#include "fingerprint_protocol.h"

int main() {
  using namespace fingerprint;
  // Fixed protocol fixtures; no actual fingerprint data.
  const uint8_t verify[] = {0x13, 0x00, 0x00, 0x00, 0x00};
  const uint8_t expectedCommand[] = {
      0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x01, 0x00, 0x07,
      0x13, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1B};
  uint8_t frame[MAX_FRAME_SIZE] = {};
  assert(encodeCommand(frame, sizeof(frame), 0xFFFFFFFFUL, verify, sizeof(verify)) ==
         sizeof(expectedCommand));
  assert(memcmp(frame, expectedCommand, sizeof(expectedCommand)) == 0);
  assert(encodeCommand(frame, 4, 0xFFFFFFFFUL, verify, sizeof(verify)) == 0);
  assert(encodeCommand(frame, sizeof(frame), 0xFFFFFFFFUL, verify, 0) == 0);
  assert(encodeCommand(frame, sizeof(frame), 0xFFFFFFFFUL, verify, MAX_PAYLOAD_SIZE + 1) == 0);

  const uint8_t parameters[] = {
      0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x13,
      0x00, 0x00, 0x00, 0x00, 0x09, 0x00, 0x64, 0x00, 0x03,
      0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x02, 0x00, 0x0C, 0x04, 0x94};
  Reply reply;
  assert(decodeAck(parameters, sizeof(parameters), 0xFFFFFFFFUL, reply) == FrameError::None);
  assert(reply.length == 17);
  assert(read16(reply.payload + 5) == 100);
  assert(read16(reply.payload + 7) == 3);
  assert(read32(reply.payload + 9) == 0xFFFFFFFFUL);
  assert((32U << read16(reply.payload + 13)) == 128);
  // Guard against the common uint16_t overflow when reporting 115200 baud.
  assert(static_cast<uint32_t>(read16(reply.payload + 15)) * 9600UL == 115200UL);

  const uint8_t count[] = {
      0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x05,
      0x00, 0x00, 0x02, 0x00, 0x0E};
  assert(decodeAck(count, sizeof(count), 0xFFFFFFFFUL, reply) == FrameError::None);
  assert(reply.length == 3 && read16(reply.payload + 1) == 2);
  const uint8_t wrongPassword[] = {
      0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03,
      0x13, 0x00, 0x1D};
  assert(decodeAck(wrongPassword, sizeof(wrongPassword), 0xFFFFFFFFUL, reply) == FrameError::None);
  assert(reply.payload[0] == 0x13);

  assert(decodeAck(parameters, sizeof(parameters) - 1, 0xFFFFFFFFUL, reply) == FrameError::Length);
  assert(reply.length == 0);
  assert(decodeAck(parameters, 2, 0xFFFFFFFFUL, reply) == FrameError::Length);
  assert(decodeAck(parameters, MAX_FRAME_SIZE + 1, 0xFFFFFFFFUL, reply) == FrameError::Length);
  assert(decodeAck(parameters, sizeof(parameters), 0x12345678UL, reply) == FrameError::Address);
  memcpy(frame, parameters, sizeof(parameters));
  frame[0] = 0;
  assert(decodeAck(frame, sizeof(parameters), 0xFFFFFFFFUL, reply) == FrameError::Header);
  memcpy(frame, parameters, sizeof(parameters));
  frame[6] = 0x02;
  assert(decodeAck(frame, sizeof(parameters), 0xFFFFFFFFUL, reply) == FrameError::PacketType);
  memcpy(frame, parameters, sizeof(parameters));
  frame[8] = 0xFF;
  assert(decodeAck(frame, sizeof(parameters), 0xFFFFFFFFUL, reply) == FrameError::Length);
  memcpy(frame, parameters, sizeof(parameters));
  frame[15] ^= 1;
  assert(decodeAck(frame, sizeof(parameters), 0xFFFFFFFFUL, reply) == FrameError::Checksum);
  assert(reply.length == 0);
  puts("Protocol fixtures passed: encoding, parameters, 115200 baud, counts, errors and bounds.");
}
