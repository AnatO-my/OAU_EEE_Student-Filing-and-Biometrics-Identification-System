#pragma once
#include <Arduino.h>
#include <esp_system.h>
#include "terminal_config.h"
#include "terminal_logic.h"

namespace accuracy {
class Inputs {
  terminal::Button keys_[3];
  bool initialized_=false;
public:
  void begin() {
    pinMode(TERMINAL_ENROLL_PIN,INPUT_PULLUP); pinMode(TERMINAL_DELETE_PIN,INPUT_PULLUP);
    pinMode(TERMINAL_MENU_PIN,INPUT_PULLUP); initialized_=true; poll();
  }
  void poll() {
    if (!initialized_) return;
    const int pins[]={TERMINAL_ENROLL_PIN,TERMINAL_DELETE_PIN,TERMINAL_MENU_PIN};
    for (unsigned i=0;i<3;++i) keys_[i].sample(digitalRead(pins[i])==LOW,millis());
  }
  bool take(unsigned i) { return keys_[i].take(); }
  void suppress() { for (auto &key:keys_) key.suppress(); poll(); }
  uint32_t bootNonce() { return esp_random(); } // Session label, not an authentication secret.
};
} // namespace accuracy
