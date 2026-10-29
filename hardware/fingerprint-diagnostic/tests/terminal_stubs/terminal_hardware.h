#pragma once
#include "terminal_logic.h"
#include "terminal_feedback.h"
#include "terminal_screen.h"
#include <string>
#include <vector>

namespace terminal {
class TerminalHardware {
public:
  bool oledOK=false,rtcOK=false,fsOK=false,clockPresent=false,setOK=false;
  bool buttons[3]={};
  DateTime clock;
  Screen last;
  uint8_t pixels[OLED_FRAME_BYTES]={};
  LogResult nextRecord=LogResult::Saved;
  unsigned writes=0,formats=0,exports=0,clockWrites=0;
  int feedback=0;
  Feedback lastFeedback=Feedback::Progress;
  void begin() {}
  bool button(unsigned i) const { return buttons[i]; }
  void tick() {}
  void off() {}
  void notify(Feedback event) {
    lastFeedback=event; const auto p=pattern(event); feedback=p.green?1:p.red?-1:0;
  }
  bool readClock(DateTime &t) { if (!clockPresent) return false; t=clock; return true; }
  bool setClock(const DateTime &t) { ++clockWrites; if (!setOK) return false; clock=t; return true; }
  bool todayCount(const DateTime &,uint32_t &count) { count=writes; return fsOK; }
  bool hashTemplate(const uint8_t *,size_t,char *out) { memset(out,'a',64); out[64]=0; return true; }
  LogResult record(const DateTime &,uint16_t,uint16_t,const char *) { ++writes; return nextRecord; }
  bool exportLog() { ++exports; return fsOK; }
  bool formatStorage() { ++formats; return fsOK=true; }
  void contrast(bool) {}
  void show(const Screen &screen) { last=screen; renderScreen(screen,pixels); }
};
} // namespace terminal
