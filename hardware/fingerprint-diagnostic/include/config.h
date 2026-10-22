#pragma once

#include <stdint.h>

// Optional private overrides, for example a previously changed sensor password.
#if __has_include("../local_config.h")
#include "../local_config.h"
#endif

// ESP32 perspective: scanner TXD -> ESP32 RX; scanner RXD -> ESP32 TX.
#ifndef FINGERPRINT_RX_PIN
#define FINGERPRINT_RX_PIN 16
#endif
#ifndef FINGERPRINT_TX_PIN
#define FINGERPRINT_TX_PIN 17
#endif
#ifndef FINGERPRINT_PASSWORD
#define FINGERPRINT_PASSWORD 0x00000000UL
#endif
#ifndef FINGERPRINT_ADDRESS
#define FINGERPRINT_ADDRESS 0xFFFFFFFFUL
#endif

constexpr uint32_t CONSOLE_BAUD = 115200;
constexpr uint32_t REPLY_TIMEOUT_MS = 800;
constexpr uint32_t SENSOR_OPERATION_TIMEOUT_MS = 2000;
constexpr uint32_t FINGER_WAIT_TIMEOUT_MS = 60000;
constexpr uint32_t ERASE_CONFIRM_TIMEOUT_MS = 15000;
