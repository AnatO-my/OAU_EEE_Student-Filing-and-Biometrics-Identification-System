// Adafruit version of the OLED test: welcome text, counter and USB text input.
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

constexpr int SCREEN_WIDTH = 128, SCREEN_HEIGHT = 64;
constexpr int SDA_PIN = 21, SCL_PIN = 22, OLED_RESET = -1;
// Wire uses 7-bit addresses: module labels 0x78/0x7A mean 0x3C/0x3D here.
constexpr uint8_t SCREEN_ADDRESS = 0x3C; // Fallback if neither address ACKs.
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET, 100000, 100000);
uint8_t screenAddress = SCREEN_ADDRESS;
bool ready = false;
String message = "OLED Ready!";

bool acknowledges(uint8_t address) {
  Wire.beginTransmission(address);
  return Wire.endTransmission() == 0;
}

void showText() {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(F("ADAFRUIT OLED TEST"));
  display.print(F("I2C: 0x")); display.println(screenAddress, HEX);
  display.print(F("Seconds: ")); display.println(millis() / 1000);
  display.setCursor(0, 32);
  display.setTextSize(message.length() <= 20 ? 2 : 1);
  display.println(message);
  display.display();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println(F("\nAdafruit OLED test: 128x64, SDA=21 SCL=22, I2C=100kHz"));
  if (!Wire.begin(SDA_PIN, SCL_PIN, 100000)) {
    Serial.println(F("FAIL: could not start I2C."));
    return;
  }
  Wire.setTimeOut(50);
  delay(100);
  const bool found3C = acknowledges(0x3C), found3D = acknowledges(0x3D);
  Serial.printf("0x3C (label 0x78): %s\n", found3C ? "ACK" : "NO ACK");
  Serial.printf("0x3D (label 0x7A): %s\n", found3D ? "ACK" : "NO ACK");
  if (found3C) screenAddress = 0x3C;
  else if (found3D) screenAddress = 0x3D;
  else Serial.println(F("No OLED ACK. Trying the driver anyway; check wiring/power."));

  // Keep the explicit Wire pins; begin() success alone does not prove a panel ACK.
  if (!display.begin(SSD1306_SWITCHCAPVCC, screenAddress, true, false)) {
    Serial.println(F("FAIL: SSD1306 framebuffer allocation failed."));
    return;
  }
  ready = true;
  showText();
  Serial.printf("Driver ready at 0x%02X. Check for OLED Ready! and a changing counter.\n", screenAddress);
  Serial.println(F("Type up to 80 characters and press Enter to show them on the OLED."));
  Serial.println(F("After changing wiring, press RESET to initialize the OLED again."));
}

void loop() {
  if (!ready) { delay(100); return; }
  static uint32_t lastRefresh = 0;
  static String incoming;
  bool changed = false;
  // Collect characters until Enter, keeping the counter running while typing.
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\r' || c == '\n') {
      incoming.trim();
      if (incoming.length() > 0) {
        message = incoming;
        Serial.print(F("Text sent: ")); Serial.println(message);
        changed = true;
      }
      incoming = "";
    } else if (c == '\b' || c == 127) {
      if (incoming.length() > 0) incoming.remove(incoming.length() - 1);
    } else if (c >= 32 && c <= 126 && incoming.length() < 80) {
      incoming += c;
    }
  }
  if (changed || millis() - lastRefresh >= 1000) {
    lastRefresh = millis();
    Serial.printf("OLED ACK=%s, seconds=%lu\n",
                  acknowledges(screenAddress) ? "YES" : "NO", millis() / 1000);
    showText();
  }
  delay(10);
}
