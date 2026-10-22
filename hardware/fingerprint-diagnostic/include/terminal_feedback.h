#pragma once
#include <stdint.h>

namespace terminal {
enum class Feedback { Startup, Click, Progress, Enrolled, AttendanceSaved,
  CaptureSaved, Deleted, Error, Retry, Duplicate, Cancelled, ModeChanged,
  Started, Stopped, Exported, ClockSaved };
struct FeedbackPattern {
  bool green,red;
  uint16_t ledMs,beepMs,gapMs;
  uint8_t beeps,priority;
};
inline FeedbackPattern pattern(Feedback event) {
  switch(event) {
    case Feedback::Enrolled: return {true,false,700,700,0,1,2};
    case Feedback::AttendanceSaved: return {true,false,700,100,0,1,2};
    case Feedback::Deleted: return {true,false,700,100,100,2,2};
    case Feedback::Error: case Feedback::Retry: case Feedback::Duplicate:
      return {false,true,700,120,120,2,2};
    case Feedback::Click: return {false,false,0,20,0,1,0};
    case Feedback::Progress: return {false,false,0,0,0,0,0};
    default: return {false,false,0,100,0,1,1};
  }
}
// Nonblocking pulses: serial waits may service tick() without issuing scanner
// commands. A key click cannot truncate enrollment/success/error feedback.
class FeedbackPlayer {
  FeedbackPattern value_={false,false,0,0,0,0,0};
  uint32_t started_=0,elapsed_=0;
  bool active_=false;
public:
  void tick(uint32_t now) {
    elapsed_=now-started_;
    const uint32_t sound=value_.beeps?value_.beeps*value_.beepMs+(value_.beeps-1)*value_.gapMs:0;
    if (elapsed_>=value_.ledMs && elapsed_>=sound) active_=false;
  }
  void start(Feedback event,uint32_t now) {
    tick(now); const auto next=pattern(event);
    if (active_ && next.priority<value_.priority) return;
    value_=next; started_=now; elapsed_=0; active_=true; tick(now);
  }
  void stop() { active_=false; }
  bool green() const { return active_ && value_.green && elapsed_<value_.ledMs; }
  bool red() const { return active_ && value_.red && elapsed_<value_.ledMs; }
  bool buzzer() const {
    const uint32_t period=value_.beepMs+value_.gapMs;
    return active_ && value_.beeps && period && elapsed_/period<value_.beeps &&
      elapsed_%period<value_.beepMs;
  }
};
} // namespace terminal
