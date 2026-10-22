#include <assert.h>
#include "../src/main.cpp"

uint32_t fakeMillis = 0;
HardwareSerial Serial(0);
const std::vector<uint8_t> ACK_OK = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x00, 0x00, 0x0A};
const std::vector<uint8_t> ACK_NO_FINGER = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x02, 0x00, 0x0C};
const std::vector<uint8_t> ACK_MISMATCH = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x0A, 0x00, 0x14};
const std::vector<uint8_t> ACK_FLASH_ERROR = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x18, 0x00, 0x22};
const std::vector<uint8_t> PARAMS = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x13,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x96, 0x00, 0x03,
    0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x02, 0x00, 0x06, 0x04, 0xB7};

unsigned stored = 0, images = 0, indexReads = 0, stores = 0, erases = 0;
uint16_t savedId = 0;
bool mismatched = false, flashError = false, slotChanged = false;
bool badIndex = false, fingerNeverLifted = false;
std::vector<uint8_t> featureSlots;

std::vector<uint8_t> countFixture() {
  switch (stored) {
  case 0: return {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x05,
                  0x00, 0x00, 0x00, 0x00, 0x0C};
  case 1: return {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x05,
                  0x00, 0x00, 0x01, 0x00, 0x0D};
  case 9: return {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x05,
                  0x00, 0x00, 0x09, 0x00, 0x15};
  case 10: return {0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x05,
                   0x00, 0x00, 0x0A, 0x00, 0x16};
  default: assert(false); return {};
  }
}

void resetFixture(unsigned initialCount) {
  fakeMillis = 0;
  authenticated = true;
  connectedBaud = 57600;
  Serial.output.clear();
  Serial.incoming.clear();
  scanner.incoming.clear();
  stored = initialCount;
  images = indexReads = stores = erases = 0;
  savedId = 0;
  mismatched = flashError = slotChanged = badIndex = fingerNeverLifted = false;
  featureSlots.clear();
  scanner.onWrite = [](uint32_t, const uint8_t *request, size_t size) {
    const uint8_t command = request[9];
    switch (command) {
    case 0x0F: return PARAMS;
    case 0x1D: return countFixture();
    case 0x1F: {
      assert(size == 13 && request[10] == 0);
      ++indexReads;
      // Fixed occupancy fixture: slots 1..9 occupied, slot 0 and 10 free.
      std::vector<uint8_t> table = {
          0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x23, 0x00};
      table.resize(42, 0);
      table[10] = 0xFE;
      table[11] = slotChanged && indexReads > 1 ? 0x07 : 0x03;
      table.push_back(0x01);
      table.push_back(table[11] == 0x07 ? 0x2F : 0x2B);
      if (badIndex) table.back() ^= 1;
      return table;
    }
    case 0x01:
      ++images;
      return images == 3 && !fingerNeverLifted ? ACK_NO_FINGER : ACK_OK;
    case 0x02:
      assert(size == 13);
      featureSlots.push_back(request[10]);
      return ACK_OK;
    case 0x05:
      assert(images == 4 && featureSlots == std::vector<uint8_t>({1, 2}));
      return mismatched ? ACK_MISMATCH : ACK_OK;
    case 0x06:
      assert(size == 15 && request[10] == 1 && featureSlots.size() == 2);
      ++stores;
      savedId = fingerprint::read16(request + 11);
      assert((stored == 0 && savedId == 1) || (stored == 9 && savedId == 10));
      if (flashError) return ACK_FLASH_ERROR;
      ++stored;
      return ACK_OK;
    case 0x0D:
      assert(size == 12);
      ++erases;
      stored = 0;
      return ACK_OK;
    default: assert(false); return std::vector<uint8_t>{};
    }
  };
}

void sendText(const char *text) {
  for (const char *p = text; *p; ++p) Serial.incoming.push_back(*p);
}

int main() {
  resetFixture(9);
  sendText("dERASE\n");
  loop();
  assert(erases == 1 && stored == 0);
  assert(Serial.output.find("ERASED: stored templates=0") != std::string::npos);
  Serial.output.clear();
  sendText("e");
  loop();
  assert(stores == 1 && stored == 1 && savedId == 1 && indexReads == 0);
  assert(Serial.output.find("Finger removed") != std::string::npos);
  assert(Serial.output.find("ENROLLED: template ID=1") != std::string::npos);
  assert(Serial.output.find("Stored templates: 1") != std::string::npos);

  resetFixture(9);
  enrolFinger();
  assert(erases == 0 && stored == 10 && savedId == 10 && indexReads == 2);
  assert(Serial.output.find("ENROLLED: template ID=10") != std::string::npos);

  resetFixture(9);
  slotChanged = true;
  enrolFinger();
  assert(stores == 0 && Serial.output.find("now occupied") != std::string::npos);

  resetFixture(9);
  badIndex = true;
  enrolFinger();
  assert(stores == 0 && images == 0);
  assert(Serial.output.find("Cannot prove a slot is free") != std::string::npos);

  resetFixture(0);
  mismatched = true;
  enrolFinger();
  assert(stores == 0 && stored == 0);
  assert(Serial.output.find("two enrollment scans did not agree") != std::string::npos);

  resetFixture(0);
  flashError = true;
  enrolFinger();
  assert(stores == 1 && stored == 0);
  assert(Serial.output.find("Save not confirmed") != std::string::npos);
  assert(Serial.output.find("ENROLLED:") == std::string::npos);

  resetFixture(0);
  fingerNeverLifted = true;
  enrolFinger();
  assert(stores == 0 && featureSlots == std::vector<uint8_t>({1}));
  assert(Serial.output.find("Finger-removal wait expired") != std::string::npos);

  resetFixture(0);
  sendText("x");
  enrolFinger();
  assert(stores == 0 && images == 0);

  resetFixture(9);
  sendText("erase\n");
  eraseLibrary();
  assert(erases == 0 && stored == 9);
  resetFixture(9);
  sendText("ERASE-and-more-than-fifteen-characters\n");
  eraseLibrary();
  assert(erases == 0 && stored == 9);
  resetFixture(9);
  sendText("x");
  eraseLibrary();
  assert(erases == 0 && stored == 9);
  resetFixture(9);
  eraseLibrary();
  assert(erases == 0 && stored == 9 && fakeMillis == ERASE_CONFIRM_TIMEOUT_MS);

  resetFixture(0);
  eraseLibrary();
  assert(erases == 0 && Serial.output.find("already empty") != std::string::npos);
  puts("Enrollment simulations passed: confirmed erase, two scans, free slots, occupied-slot guard, mismatch, save failure, lift wait and cancellation.");
}
