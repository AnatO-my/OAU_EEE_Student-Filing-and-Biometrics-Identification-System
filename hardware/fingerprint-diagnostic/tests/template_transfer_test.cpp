#include <assert.h>
#include "../src/main.cpp"

uint32_t fakeMillis = 0;
HardwareSerial Serial(0);

const std::vector<uint8_t> ACK_OK = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x00, 0x00, 0x0A};
const std::vector<uint8_t> PARAMS = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x13,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x96, 0x00, 0x03,
    0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x02, 0x00, 0x06, 0x04, 0xB7};

std::vector<uint8_t> buffer, flash, received;
unsigned stores = 0, downloads = 0, uploads = 0, indexReads = 0;
unsigned packetCode = 2;
uint16_t reportedCapacity = 150;
std::vector<uint16_t> occupiedSlots;
unsigned searches = 0;
bool rejectFinger = false, wrongMatchId = false, extendedNoMatch = false;
bool wrongStoredCount = false;
bool corrupt = false, noFinal = false, truncated = false, wrongAddress = false;
bool wrongType = false, changedBuffer = false, changedSlot = false, failedStore = false;
bool badFlashRead = false, oversized = false;

// Independent fixture writer: no calls to the codec being tested.
std::vector<uint8_t> packet(uint8_t type, const std::vector<uint8_t> &payload) {
  const unsigned length = static_cast<unsigned>(payload.size()) + 2;
  std::vector<uint8_t> result = {0xEF, 1, 0xFF, 0xFF, 0xFF, 0xFF, type,
      static_cast<uint8_t>(length >> 8), static_cast<uint8_t>(length)};
  result.insert(result.end(), payload.begin(), payload.end());
  unsigned sum = 0;
  for (size_t i = 6; i < result.size(); ++i) sum += result[i];
  result.push_back(static_cast<uint8_t>(sum >> 8));
  result.push_back(static_cast<uint8_t>(sum));
  return result;
}

void sendText(const std::string &text) {
  Serial.incoming.insert(Serial.incoming.end(), text.begin(), text.end());
}

void resetFixture() {
  fakeMillis = 0;
  authenticated = true;
  Serial.incoming.clear();
  Serial.output.clear();
  scanner.incoming.clear();
  stores = downloads = uploads = indexReads = 0;
  packetCode = 2;
  reportedCapacity = 150;
  occupiedSlots = {1};
  searches = 0;
  rejectFinger = wrongMatchId = extendedNoMatch = false;
  wrongStoredCount = false;
  corrupt = noFinal = truncated = wrongAddress = wrongType = false;
  changedBuffer = changedSlot = failedStore = badFlashRead = oversized = false;
  buffer.clear(); flash.clear(); received.clear();
  // Synthetic 300-byte template exercises 128+128+44 packet boundaries.
  for (unsigned i = 0; i < 300; ++i) flash.push_back(static_cast<uint8_t>(i));
  scanner.onWrite = [](uint32_t, const uint8_t *frame, size_t size) {
    if (frame[6] == 0x02 || frame[6] == 0x08) {
      assert(downloads == 1);
      assert(fingerprint::read16(frame + 7) == size - 9);
      const size_t bytes = size - 11;
      assert(bytes <= (32U << packetCode));
      unsigned sum = 0;
      for (size_t i = 6; i < size - 2; ++i) sum += frame[i];
      assert((sum & 65535) == fingerprint::read16(frame + size - 2));
      received.insert(received.end(), frame + 9, frame + size - 2);
      if (frame[6] == 0x08) buffer = received;
      return std::vector<uint8_t>{};
    }
    assert(frame[6] == 1);
    switch (frame[9]) {
    case 0x01: return ACK_OK;
    case 0x02: return ACK_OK;
    case 0x04:
      ++searches;
      assert(size == 17 && frame[10] == 1);
      assert(fingerprint::read16(frame + 11) == 1);
      assert(fingerprint::read16(frame + 13) == 1); // Exactly one target slot.
      if (rejectFinger) return extendedNoMatch ? packet(7, {0x09, 0, 0, 0, 0}) : packet(7, {0x09});
      return packet(7, {0, 0, static_cast<uint8_t>(wrongMatchId ? 2 : 1), 0, 124});
    case 0x0F: {
      auto payload = std::vector<uint8_t>(PARAMS.begin() + 9, PARAMS.end() - 2);
      payload[14] = static_cast<uint8_t>(packetCode);
      payload[5] = static_cast<uint8_t>(reportedCapacity >> 8);
      payload[6] = static_cast<uint8_t>(reportedCapacity);
      return packet(7, payload);
    }
    case 0x1D: {
      const size_t count = occupiedSlots.size() + (wrongStoredCount ? 1 : 0);
      return packet(7, {0, static_cast<uint8_t>(count >> 8), static_cast<uint8_t>(count)});
    }
    case 0x1F: {
      ++indexReads;
      std::vector<uint8_t> bits(33, 0);
      for (uint16_t slot : occupiedSlots) {
        if (slot / 256 == frame[10]) bits[1 + (slot % 256) / 8] |= 1U << (slot % 8);
      }
      if (changedSlot && indexReads > 1 && frame[10] == 0) bits[1] |= 0x04;
      return packet(7, bits);
    }
    case 0x07:
      assert(size == 15 && frame[10] == 1);
      {
        const uint16_t slot = fingerprint::read16(frame + 11);
        bool occupied = false;
        for (uint16_t candidate : occupiedSlots) occupied |= slot == candidate;
        assert(occupied);
      }
      buffer = flash;
      if (badFlashRead && stores) buffer[0] ^= 1;
      return ACK_OK;
    case 0x08: {
      ++uploads;
      std::vector<uint8_t> stream = ACK_OK;
      std::vector<uint8_t> data = buffer;
      if (changedBuffer) data[0] ^= 1;
      if (oversized) data.resize(2049, 0xA5);
      const size_t chunk = 32U << packetCode;
      for (size_t offset = 0; offset < data.size(); offset += chunk) {
        const size_t end = offset + chunk < data.size() ? offset + chunk : data.size();
        auto part = packet(end == data.size() && !noFinal ? 8 : 2,
            std::vector<uint8_t>(data.begin() + offset, data.begin() + end));
        if (offset == 0) {
          if (corrupt) part.back() ^= 1;
          if (wrongAddress) part[2] = 0;
          if (wrongType) part[6] = 7;
        }
        stream.insert(stream.end(), part.begin(), part.end());
      }
      if (truncated) stream.pop_back();
      return stream;
    }
    case 0x09:
      ++downloads;
      received.clear();
      return ACK_OK;
    case 0x06:
      ++stores;
      assert(fingerprint::read16(frame + 11) == 2);
      assert(uploads == 1 && buffer == received);
      if (failedStore) return packet(7, {0x18});
      flash = buffer;
      occupiedSlots.push_back(2);
      return ACK_OK;
    default: assert(false); return std::vector<uint8_t>{};
    }
  };
}

std::string importText(const std::vector<uint8_t> &data, bool badCrc = false) {
  char line[80];
  snprintf(line, sizeof(line), "u %u %08lX\n", static_cast<unsigned>(data.size()),
      static_cast<unsigned long>(fingerprint::crc32(data.data(), data.size()) ^ (badCrc ? 1 : 0)));
  std::string text(line);
  for (size_t offset = 0; offset < data.size(); offset += 32) {
    const size_t end = offset + 32 < data.size() ? offset + 32 : data.size();
    for (size_t i = offset; i < end; ++i) {
      snprintf(line, sizeof(line), "%02X", data[i]);
      text += line;
    }
    text += '\n';
  }
  return text;
}

int main() {
  const uint8_t crcText[] = {'1','2','3','4','5','6','7','8','9'};
  assert(fingerprint::crc32(crcText, sizeof(crcText)) == 0xCBF43926UL);
  // Fixed EF01 final-data fixture: payload 10 20 30, checksum 006D.
  const uint8_t finalFixture[] = {0xEF,1,0xFF,0xFF,0xFF,0xFF,8,0,5,0x10,0x20,0x30,0,0x6D};
  fingerprint::DataPacket decoded;
  assert(fingerprint::decodeData(finalFixture, sizeof(finalFixture), 0xFFFFFFFFUL, decoded)
      == fingerprint::FrameError::None);
  assert(decoded.final && decoded.length == 3 && decoded.bytes[2] == 0x30);
  uint8_t encoded[sizeof(finalFixture)];
  assert(fingerprint::encodeData(encoded, sizeof(encoded), 0xFFFFFFFFUL,
      finalFixture + 9, 3, true) == sizeof(finalFixture));
  assert(memcmp(encoded, finalFixture, sizeof(encoded)) == 0);

  resetFixture();
  sendText("t 1\n"); loop();
  assert(stores == 0 && downloads == 0);
  assert(Serial.output.find("FPBEGIN 1 1 150 3 128 0 FFFFFFFF") != std::string::npos);
  assert(Serial.output.find("FPDATA 000102030405") != std::string::npos);
  assert(Serial.output.find("FPEND 300 ") != std::string::npos);

  resetFixture(); sendText("t 2\n"); loop();
  assert(uploads == 0 && Serial.output.find("FPERROR") != std::string::npos);
  for (const char *bad : {"t -4294967295\n", "t 4294967297\n", "t 1 extra\n",
                         "t 150\n", "u 0 00000000\n", "u 2049 00000000\n"}) {
    resetFixture(); sendText(bad); loop();
    assert(uploads == 0 && downloads == 0 && stores == 0);
    assert(Serial.output.find("FPERROR") != std::string::npos);
  }

  for (unsigned failure = 0; failure < 7; ++failure) {
    resetFixture();
    corrupt = failure == 0; noFinal = failure == 1; truncated = failure == 2;
    wrongAddress = failure == 3; wrongType = failure == 4; oversized = failure == 5;
    if (failure == 6) authenticated = false;
    sendText("t 1\n"); loop();
    assert(Serial.output.find("FPEND") == std::string::npos);
    assert(Serial.output.find("FPERROR") != std::string::npos);
    assert(stores == 0);
  }

  resetFixture();
  const auto original = flash;
  sendText(importText(original)); loop();
  assert(stores == 1 && downloads == 1 && uploads == 2);
  assert(flash == original && received == original);
  assert(Serial.output.find("FPSTORED 2 300 ") != std::string::npos);

  for (unsigned code = 0; code < 4; ++code) {
    resetFixture(); packetCode = code;
    sendText("t 1\n"); loop();
    assert(Serial.output.find("FPEND 300 ") != std::string::npos);
    resetFixture(); packetCode = code;
    sendText(importText(flash)); loop();
    assert(stores == 1 && uploads == 2 && Serial.output.find("FPSTORED 2 300 ") != std::string::npos);
  }
  resetFixture(); packetCode = 4; sendText("t 1\n"); loop();
  assert(uploads == 0 && Serial.output.find("FPERROR") != std::string::npos);

  resetFixture();
  flash.resize(2048, 0x5A);
  sendText(importText(flash)); loop();
  assert(stores == 1 && Serial.output.find("FPSTORED 2 2048 ") != std::string::npos);

  resetFixture(); sendText(importText(flash, true)); loop();
  assert(stores == 0 && downloads == 0);
  resetFixture(); changedBuffer = true; sendText(importText(flash)); loop();
  assert(stores == 0 && downloads == 1);
  resetFixture(); changedSlot = true; sendText(importText(flash)); loop();
  assert(stores == 0 && Serial.output.find("now occupied") != std::string::npos);
  resetFixture(); failedStore = true; sendText(importText(flash)); loop();
  assert(stores == 1 && Serial.output.find("FPSTORED") == std::string::npos);
  resetFixture(); badFlashRead = true; sendText(importText(flash)); loop();
  assert(stores == 1 && Serial.output.find("Storage not verified") != std::string::npos);
  resetFixture(); sendText("u 3 00000000\nGG\ndERASE\n"); loop();
  assert(stores == 0 && downloads == 0 && Serial.incoming.empty());
  resetFixture(); sendText("u 3 00000000\n"); loop();
  assert(stores == 0 && downloads == 0 && fakeMillis >= TEMPLATE_CONSOLE_TIMEOUT_MS);

  resetFixture(); sendText("v 1\n"); loop();
  assert(searches == 1 && stores == 0 && downloads == 0);
  assert(Serial.output.find("SLOTMATCH 1 124") != std::string::npos);
  resetFixture(); rejectFinger = true; sendText("v 1\n"); loop();
  assert(searches == 1 && Serial.output.find("SLOTNOMATCH 1") != std::string::npos);
  resetFixture(); wrongMatchId = true; sendText("v 1\n"); loop();
  assert(searches == 1 && Serial.output.find("SLOTMATCH") == std::string::npos);
  resetFixture(); sendText("v 2\n"); loop();
  assert(searches == 0 && stores == 0);
  resetFixture(); rejectFinger = extendedNoMatch = true; sendText("v 1\n"); loop();
  assert(searches == 1 && Serial.output.find("SLOTNOMATCH 1") != std::string::npos);

  resetFixture(); sendText("l\n"); loop();
  assert(Serial.output.find("FPLISTBEGIN 1 150 1\nFPSLOT 1\nFPLISTEND 1") != std::string::npos);
  assert(stores == 0 && downloads == 0 && uploads == 0);
  resetFixture(); occupiedSlots.clear(); sendText("l\n"); loop();
  assert(Serial.output.find("FPLISTBEGIN 1 150 0\nFPLISTEND 0") != std::string::npos);
  resetFixture(); reportedCapacity = 600; occupiedSlots = {1, 257, 599};
  sendText("l\n"); loop();
  assert(indexReads == 3);
  assert(Serial.output.find("FPSLOT 1\nFPSLOT 257\nFPSLOT 599\nFPLISTEND 3") != std::string::npos);
  resetFixture(); reportedCapacity = 600; occupiedSlots = {1, 257, 599};
  sendText("t ALL\n"); loop();
  assert(uploads == 3 && stores == 0 && downloads == 0);
  assert(Serial.output.find("FPBATCHEND 3 3") != std::string::npos);
  assert(Serial.output.find("FPSTEP Slot 599: 300 bytes received") != std::string::npos);
  resetFixture(); corrupt = true; sendText("t ALL\n"); loop();
  assert(uploads == 1 && Serial.output.find("FPBATCHERROR 0 1") != std::string::npos);
  assert(Serial.output.find("FPBATCHEND") == std::string::npos);
  resetFixture(); sendText("t\n1\n"); loop();
  assert(uploads == 1 && Serial.output.find("FPEND 300") != std::string::npos);
  resetFixture(); wrongStoredCount = true; sendText("l\n"); loop();
  assert(Serial.output.find("disagree") != std::string::npos);
  assert(Serial.output.find("FPLISTBEGIN") == std::string::npos);
  assert(Serial.output.find("FPERROR") != std::string::npos);

  printf("Template packet/export/restore tests passed (synthetic data only).\n");
  return 0;
}
