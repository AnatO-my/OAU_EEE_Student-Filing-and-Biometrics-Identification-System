#include <assert.h>
#include <initializer_list>
#include "terminal_feedback.h"
using namespace terminal;
int main() {
  FeedbackPlayer player;
  for(auto event:{Feedback::Startup,Feedback::Click,Feedback::Progress,
      Feedback::CaptureSaved,Feedback::ModeChanged,Feedback::Exported,Feedback::ClockSaved}) {
    player.stop(); player.start(event,0);
    assert(!player.green() && !player.red());
  }
  player.stop(); player.start(Feedback::Enrolled,100);
  assert(player.green() && !player.red() && player.buzzer());
  player.start(Feedback::Click,150); player.tick(799);
  assert(player.green() && player.buzzer()); // Click cannot truncate the long beep.
  player.tick(800); assert(!player.green() && !player.buzzer());
  player.start(Feedback::Error,1000);
  assert(player.red() && !player.green() && player.buzzer());
  player.tick(1120); assert(player.red() && !player.buzzer());
  player.tick(1240); assert(player.buzzer());
  player.tick(1360); assert(!player.buzzer());
  player.tick(1700); assert(!player.red());
  player.start(Feedback::Deleted,2000); assert(player.green() && player.buzzer());
  player.tick(2100); assert(!player.buzzer()); player.tick(2200); assert(player.buzzer());
  player.tick(2300); assert(!player.buzzer()); player.tick(2700); assert(!player.green());
  player.start(Feedback::AttendanceSaved,0xFFFFFFF0UL);
  player.tick(0x54); assert(!player.buzzer() && player.green());
  player.tick(0x2AC); assert(!player.green());
}
