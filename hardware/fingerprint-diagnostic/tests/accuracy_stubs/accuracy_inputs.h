#pragma once
#include "terminal_logic.h"
namespace accuracy {
class Inputs {
  terminal::Button keys_[3]; bool ready_=false;
public:
  bool buttons[3]={};
  void begin() { ready_=true; poll(); }
  void poll() { if (ready_) for (unsigned i=0;i<3;++i) keys_[i].sample(buttons[i],millis()); }
  bool take(unsigned i) { return keys_[i].take(); }
  void suppress() { for (auto &key:keys_) key.suppress(); poll(); }
  uint32_t bootNonce() { return 0x12345678; }
};
} // namespace accuracy
