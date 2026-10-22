#pragma once
#include "config.h"

#ifndef TERMINAL_ENABLED
#define TERMINAL_ENABLED 1
#endif
#ifndef TERMINAL_OLED_ENABLED
#define TERMINAL_OLED_ENABLED 1
#endif
// Address 0x3C alone cannot identify the controller. Use esp32-sh1106, or set
// this override to 1, for a confirmed SH1106 128x64 panel (two-column offset).
#ifndef TERMINAL_OLED_SH1106
#define TERMINAL_OLED_SH1106 0
#endif
#ifndef TERMINAL_BUZZER_ACTIVE_HIGH
#define TERMINAL_BUZZER_ACTIVE_HIGH 1
#endif
// The DS1307 UI stores local civil time. This project operates in Africa/Lagos.
// Set a different fixed UTC offset explicitly when commissioning elsewhere.
#ifndef TERMINAL_UTC_OFFSET_SECONDS
#define TERMINAL_UTC_OFFSET_SECONDS 3600
#endif

// Button/output/I2C defaults follow the proposal. Scanner pins continue to
// come from config.h: RX16/TX17 on BOTH boards until wiring is verified.
#ifndef TERMINAL_ENROLL_PIN
#if CONFIG_IDF_TARGET_ESP32S3
#define TERMINAL_ENROLL_PIN 13
#else
#define TERMINAL_ENROLL_PIN 25
#endif
#endif
#ifndef TERMINAL_DELETE_PIN
#if CONFIG_IDF_TARGET_ESP32S3
#define TERMINAL_DELETE_PIN 14
#else
#define TERMINAL_DELETE_PIN 26
#endif
#endif
#ifndef TERMINAL_MENU_PIN
#if CONFIG_IDF_TARGET_ESP32S3
#define TERMINAL_MENU_PIN 15
#else
#define TERMINAL_MENU_PIN 27
#endif
#endif
#ifndef TERMINAL_GREEN_PIN
#if CONFIG_IDF_TARGET_ESP32S3
#define TERMINAL_GREEN_PIN 10
#else
#define TERMINAL_GREEN_PIN 18
#endif
#endif
#ifndef TERMINAL_RED_PIN
#if CONFIG_IDF_TARGET_ESP32S3
#define TERMINAL_RED_PIN 11
#else
#define TERMINAL_RED_PIN 19
#endif
#endif
#ifndef TERMINAL_BUZZER_PIN
#if CONFIG_IDF_TARGET_ESP32S3
#define TERMINAL_BUZZER_PIN 12
#else
#define TERMINAL_BUZZER_PIN 23
#endif
#endif
#ifndef TERMINAL_SDA_PIN
#if CONFIG_IDF_TARGET_ESP32S3
#define TERMINAL_SDA_PIN 8
#else
#define TERMINAL_SDA_PIN 21
#endif
#endif
#ifndef TERMINAL_SCL_PIN
#if CONFIG_IDF_TARGET_ESP32S3
#define TERMINAL_SCL_PIN 9
#else
#define TERMINAL_SCL_PIN 22
#endif
#endif
#ifndef TERMINAL_OLED_ADDRESS
#define TERMINAL_OLED_ADDRESS 0x3C
#endif

namespace terminal {
constexpr uint8_t OLED_ADDRESS = TERMINAL_OLED_ADDRESS;
constexpr uint8_t RTC_ADDRESS = 0x68;
constexpr uint32_t I2C_RATE = 100000;
constexpr uint32_t MAX_LOG_BYTES = 256 * 1024;
constexpr uint32_t ACTION_TIMEOUT = 20000;
constexpr uint32_t CLEAR_HOLD = 3000;
constexpr uint32_t PAGE_TIMEOUT = 20000;
constexpr uint32_t DIM_AFTER = 60000;
#if TERMINAL_ENABLED
constexpr int PINS[]={TERMINAL_ENROLL_PIN,TERMINAL_DELETE_PIN,TERMINAL_MENU_PIN,
  TERMINAL_GREEN_PIN,TERMINAL_RED_PIN,TERMINAL_BUZZER_PIN,TERMINAL_SDA_PIN,
  TERMINAL_SCL_PIN,FINGERPRINT_RX_PIN,FINGERPRINT_TX_PIN};
constexpr bool distinctPins(unsigned i=0,unsigned j=1) {
  return i>=9 ? true : j>=10 ? distinctPins(i+1,i+2) :
    PINS[i]!=PINS[j] && distinctPins(i,j+1);
}
static_assert(distinctPins(),"Terminal/scanner GPIO assignments overlap; check local_config.h");
#endif
} // namespace terminal
