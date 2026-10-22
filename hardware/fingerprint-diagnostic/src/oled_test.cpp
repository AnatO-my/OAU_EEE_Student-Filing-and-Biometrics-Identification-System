// Standalone SSD1306 128x64 test. No extra libraries or other peripherals needed.
#include <Arduino.h>

#include <Wire.h>

constexpr int SDA_PIN = 21, SCL_PIN = 22; // Original regular ESP32 wiring.
uint8_t address = 0;
#define OLED_RESET -1;
bool ready = false;

bool send(uint8_t control, const uint8_t *bytes, size_t size) {
  Wire.beginTransmission(address);
  const bool queued = Wire.write(control) == 1 && Wire.write(bytes, size) == size;
  return Wire.endTransmission() == 0 && queued;
}

bool drawPattern(unsigned pattern) {
  const uint8_t window[] = {0x21, 0, 127, 0x22, 0, 7};
  if (!send(0x00, window, sizeof(window))) return false;
  for (unsigned page = 0; page < 8; ++page) {
    for (unsigned x = 0; x < 128; x += 16) {
      uint8_t data[16];
      for (unsigned i = 0; i < sizeof(data); ++i) {
        if (pattern < 2) data[i] = pattern == 0 ? 0xFF : 0x00;
        else data[i] = ((page + (x + i) / 8 + pattern) & 1) ? 0xFF : 0x00;
      }
      if (!send(0x40, data, sizeof(data))) return false;
    }
  }
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\nOLED-only test: SSD1306 128x64, SDA=21 SCL=22");
  if (!Wire.begin(SDA_PIN, SCL_PIN, 100000)) {
    Serial.println("FAIL: could not start I2C.");
    return;
  }
  Wire.setTimeOut(50);
  delay(100);
  for (uint8_t candidate = 1; candidate < 127; ++candidate) {
    Wire.beginTransmission(candidate);
    if (Wire.endTransmission() != 0) continue;
    Serial.printf("I2C device at 0x%02X\n", candidate);
    if (candidate == 0x3C || (candidate == 0x3D && address == 0)) address = candidate;
  }
  if (address == 0) {
    Serial.println("FAIL: no OLED at 0x3C/0x3D. Check power, GND, SDA and SCL.");
    return;
  }
  // Same SSD1306 initialization as the supplied MicroPython code; stop scrolling.
  const uint8_t init[] = {
    0xAE, 0x2E, 0x20, 0x00, 0x40, 0xA1, 0xA8, 63, 0xC8,
    0xD3, 0x00, 0xDA, 0x12, 0xD5, 0x80, 0xD9, 0xF1,
    0xDB, 0x30, 0x81, 0xFF, 0xA4, 0xA6, 0x8D, 0x14
  };
  const uint8_t on[] = {0xAF};
  ready = send(0x00, init, sizeof(init)) && drawPattern(1) && send(0x00, on, sizeof(on));
  if (!ready) {
    Serial.println("FAIL: OLED initialization/write failed.");
    return;
  }
  Serial.printf("Using OLED address 0x%02X. Watch the screen for all four patterns.\n", address);
}

void loop() {
  if (!ready) { delay(100); return; }
  static unsigned pattern = 0;
  const char *names[] = {"WHITE", "BLACK", "CHECKERBOARD A", "CHECKERBOARD B"};
  if (!drawPattern(pattern)) {
    Serial.println("FAIL: OLED write failed. Check connections; press RESET to retry.");
    ready = false;
    return;
  }
  Serial.println(names[pattern]);
  pattern = (pattern + 1) % 4;
  delay(2000);
}
