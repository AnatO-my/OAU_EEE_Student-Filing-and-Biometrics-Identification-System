#pragma once

#ifndef TERMINAL_ENABLED
#define TERMINAL_ENABLED 0
#endif

#include <stdarg.h>
#include <stdio.h>
#include <stdint.h>
#include <deque>
#include <functional>
#include <string>
#include <vector>

constexpr uint32_t SERIAL_8N1 = 0;
extern uint32_t fakeMillis;
inline uint32_t millis() { return fakeMillis; }
inline void delay(uint32_t duration) { fakeMillis += duration; }

class HardwareSerial {
public:
  explicit HardwareSerial(int) {}
  uint32_t baud = 0;
  int rxPin = -1;
  int txPin = -1;
  std::string output;
  std::deque<uint8_t> incoming;
  std::function<std::vector<uint8_t>(uint32_t, const uint8_t *, size_t)> onWrite;
  void begin(uint32_t rate, uint32_t = SERIAL_8N1, int rx = -1, int tx = -1) {
    baud = rate;
    rxPin = rx;
    txPin = tx;
  }
  void end() { incoming.clear(); }
  int available() { return static_cast<int>(incoming.size()); }
  int read() {
    if (incoming.empty()) return -1;
    const uint8_t value = incoming.front();
    incoming.pop_front();
    return value;
  }
  size_t write(const uint8_t *data, size_t size) {
    if (onWrite) {
      const auto response = onWrite(baud, data, size);
      incoming.insert(incoming.end(), response.begin(), response.end());
    }
    return size;
  }
  void flush() {}
  void print(const char *text) { output += text; }
  void println(const char *text) { output += std::string(text) + "\n"; }
  void printf(const char *format, ...) {
    char text[512];
    va_list arguments;
    va_start(arguments, format);
    vsnprintf(text, sizeof(text), format, arguments);
    va_end(arguments);
    output += text;
  }
};

extern HardwareSerial Serial;
