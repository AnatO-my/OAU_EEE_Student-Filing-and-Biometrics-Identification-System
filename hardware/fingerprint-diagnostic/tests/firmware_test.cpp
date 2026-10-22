#include <assert.h>
#include "../src/main.cpp"

uint32_t fakeMillis = 0;
HardwareSerial Serial(0);

const std::vector<uint8_t> OK = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x00, 0x00, 0x0A};
const std::vector<uint8_t> PARAMETERS = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x13,
    0x00, 0x00, 0x00, 0x00, 0x09, 0x00, 0x64, 0x00, 0x03,
    0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x02, 0x00, 0x0C, 0x04, 0x94};
const std::vector<uint8_t> COUNT = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x05,
    0x00, 0x00, 0x02, 0x00, 0x0E};
const std::vector<uint8_t> WRONG_PASSWORD = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x13, 0x00, 0x1D};
const std::vector<uint8_t> PARAMETERS_150 = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x13,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x96, 0x00, 0x03,
    0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x02, 0x00, 0x06, 0x04, 0xB7};
const std::vector<uint8_t> COUNT_9 = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x05,
    0x00, 0x00, 0x09, 0x00, 0x15};
const std::vector<uint8_t> NO_FINGER = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x02, 0x00, 0x0C};
const std::vector<uint8_t> MATCH_ID_7 = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x07,
    0x00, 0x00, 0x07, 0x00, 0xC8, 0x00, 0xDD};
const std::vector<uint8_t> NO_MATCH = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x09, 0x00, 0x13};
const std::vector<uint8_t> MESSY_IMAGE = {
    0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x03, 0x06, 0x00, 0x10};

std::vector<uint8_t> matchFixture(uint32_t, const uint8_t *request, size_t size) {
  switch (request[9]) {
  case 0x0F: return PARAMETERS_150;
  case 0x1D: return COUNT_9;
  case 0x01: return OK;
  case 0x02:
    assert(size == 13 && request[10] == 1);
    return OK;
  case 0x04: {
    // Search the entire 150-slot library, even though only nine are occupied.
    const uint8_t expected[] = {0x04, 0x01, 0x00, 0x00, 0x00, 0x96};
    assert(size == 17 && memcmp(request + 9, expected, sizeof(expected)) == 0);
    return MATCH_ID_7;
  }
  default:
    // No store/delete/enrolment/export commands are allowed by this fixture.
    assert(false);
    return {};
  }
}

int main() {
  std::vector<uint8_t> commands;
  // Emulate an unknown compatible module at 115200, including startup noise.
  scanner.onWrite = [&](uint32_t baud, const uint8_t *request, size_t size) {
    assert(size >= 12);
    const uint8_t command = request[9];
    assert(command == 0x13 || command == 0x0F || command == 0x1D);
    commands.push_back(command);
    if (baud != 115200) return std::vector<uint8_t>{};
    auto response = command == 0x13 ? OK : command == 0x0F ? PARAMETERS : COUNT;
    response.insert(response.begin(), {0x55, 0xEF, 0xEF});
    return response;
  };
  setup();
  assert(authenticated && connectedBaud == 115200);
  assert(scanner.rxPin == 16 && scanner.txPin == 17);
  assert(Serial.output.find("Reported UART rate: 115200 baud") != std::string::npos);
  assert(Serial.output.find("Template capacity: 100") != std::string::npos);
  assert(Serial.output.find("Stored templates: 2") != std::string::npos);
  assert(Serial.output.find("Free template slots: 98") != std::string::npos);

  // A later bad parameter ACK must not display previous values, while the
  // independent count query can still complete successfully.
  Serial.output.clear();
  scanner.onWrite = [](uint32_t, const uint8_t *request, size_t) {
    auto response = request[9] == 0x0F ? PARAMETERS : COUNT;
    if (request[9] == 0x0F) response.back() ^= 1;
    return response;
  };
  Serial.incoming.push_back('r');
  loop();
  assert(Serial.output.find("checksum mismatch") != std::string::npos);
  assert(Serial.output.find("Template capacity:") == std::string::npos);
  assert(Serial.output.find("Stored templates: 2") != std::string::npos);
  assert(Serial.output.find("Free template slots:") == std::string::npos);

  Serial.output.clear();
  unsigned requests = 0;
  scanner.onWrite = [&](uint32_t, const uint8_t *request, size_t) {
    assert(request[9] == 0x13);
    ++requests;
    return WRONG_PASSWORD;
  };
  probeScanner();
  assert(requests == 1 && !authenticated);
  assert(Serial.output.find("incorrect password") != std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t, const uint8_t *, size_t) {
    return std::vector<uint8_t>{};
  };
  const uint32_t started = fakeMillis;
  probeScanner();
  assert(!authenticated && connectedBaud == 0);
  assert(fakeMillis - started < 25000);
  assert(Serial.output.find("No compatible scanner found") != std::string::npos);

  authenticated = true;
  connectedBaud = 57600;
  Serial.output.clear();
  scanner.onWrite = matchFixture;
  Serial.incoming.push_back('m');
  loop();
  assert(Serial.output.find("Image capture: PASS") != std::string::npos);
  assert(Serial.output.find("Feature extraction: PASS") != std::string::npos);
  assert(Serial.output.find("MATCH: template ID=7; confidence score=200") != std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t baud, const uint8_t *request, size_t size) {
    return request[9] == 0x04 ? NO_MATCH : matchFixture(baud, request, size);
  };
  captureTest(true);
  assert(Serial.output.find("NO MATCH:") != std::string::npos);
  assert(Serial.output.find("MATCH: template ID=") == std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t baud, const uint8_t *request, size_t size) {
    return request[9] == 0x02 ? MESSY_IMAGE : matchFixture(baud, request, size);
  };
  captureTest(true);
  assert(Serial.output.find("image too messy") != std::string::npos);
  assert(Serial.output.find("MATCH: template ID=") == std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t baud, const uint8_t *request, size_t size) {
    auto response = matchFixture(baud, request, size);
    if (request[9] == 0x04) response.back() ^= 1;
    return response;
  };
  captureTest(true);
  assert(Serial.output.find("Search: checksum mismatch") != std::string::npos);
  assert(Serial.output.find("MATCH: template ID=") == std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t baud, const uint8_t *request, size_t size) {
    return request[9] == 0x04 ? OK : matchFixture(baud, request, size);
  };
  captureTest(true);
  assert(Serial.output.find("unexpected result payload") != std::string::npos);
  assert(Serial.output.find("MATCH: template ID=") == std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t baud, const uint8_t *request, size_t size) {
    if (request[9] == 0x04) {
      // Semantically invalid success: ID 150 is outside the 0..149 search.
      return std::vector<uint8_t>{
          0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x07,
          0x00, 0x00, 0x96, 0x00, 0xC8, 0x01, 0x6C};
    }
    return matchFixture(baud, request, size);
  };
  captureTest(true);
  assert(Serial.output.find("outside the requested slot range") != std::string::npos);
  assert(Serial.output.find("MATCH: template ID=") == std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t, const uint8_t *request, size_t) {
    assert(request[9] == 0x01);
    return std::vector<uint8_t>{};
  };
  const uint32_t operationStarted = fakeMillis;
  captureTest(false);
  assert(fakeMillis - operationStarted == SENSOR_OPERATION_TIMEOUT_MS);
  assert(Serial.output.find("GenImg: timeout") != std::string::npos);
  assert(Serial.output.find("wait expired") == std::string::npos);

  // Capture-only mode waits through two no-finger ACKs, with no feature/search.
  Serial.output.clear();
  unsigned imageRequests = 0;
  scanner.onWrite = [&](uint32_t, const uint8_t *request, size_t) {
    assert(request[9] == 0x01);
    return ++imageRequests < 3 ? NO_FINGER : OK;
  };
  Serial.incoming.push_back('c');
  loop();
  assert(imageRequests == 3);
  assert(Serial.output.find("Image capture: PASS") != std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t, const uint8_t *request, size_t) {
    assert(request[9] == 0x01);
    return NO_FINGER;
  };
  const uint32_t waitStarted = fakeMillis;
  captureTest(false);
  assert(fakeMillis - waitStarted == FINGER_WAIT_TIMEOUT_MS);
  assert(Serial.output.find("wait expired") != std::string::npos);

  Serial.output.clear();
  Serial.incoming.push_back('x');
  imageRequests = 0;
  scanner.onWrite = [&](uint32_t, const uint8_t *, size_t) {
    ++imageRequests;
    return OK;
  };
  captureTest(false);
  assert(imageRequests == 0 && Serial.output.find("Capture cancelled") != std::string::npos);

  Serial.output.clear();
  scanner.onWrite = [](uint32_t, const uint8_t *request, size_t) {
    assert(request[9] == 0x0F || request[9] == 0x1D);
    if (request[9] == 0x0F) return PARAMETERS_150;
    return std::vector<uint8_t>{
        0xEF, 0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x07, 0x00, 0x05,
        0x00, 0x00, 0x00, 0x00, 0x0C};
  };
  captureTest(true);
  assert(Serial.output.find("no enrolled templates") != std::string::npos);
  puts("Firmware simulations passed: diagnostics, capture, match/no-match, search range, corrupt ACK, image quality, cancel and timeouts.");
}
