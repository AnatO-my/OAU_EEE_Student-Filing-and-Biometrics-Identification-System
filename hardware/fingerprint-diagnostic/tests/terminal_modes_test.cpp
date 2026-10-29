#define main originalTerminalTests
#include "terminal_test.cpp"
#undef main

struct CaptureFixture : terminal::CaptureControl {
  bool ready=false,active=false;
  unsigned scans=0,stops=0,count=0;
  terminal::CaptureEvent event=terminal::CaptureEvent::None;
  bool prepared() const override { return ready; }
  bool armed() const override { return active; }
  unsigned savedCount() const override { return count; }
  const char *batchId() const override { return "00000000-0000-4000-8000-000000000002"; }
  const char *classId() const override { return "00000000-0000-4000-8000-000000000003"; }
  const char *message() const override { return "Prepare class via USB"; }
  terminal::CaptureEvent takeEvent() override { auto old=event; event=terminal::CaptureEvent::None; return old; }
  bool startSelected() override { active=ready; return active; }
  bool nextBatch() override { active=false; return ready; }
  void stop() override { ++stops; active=false; }
  void tick() override { assert(active); ++scans; }
};
void modeMenu() { for(unsigned i=0;i<6;++i) attendanceTerminal.key(2); assert(attendanceTerminal.page()==6); }
void combined(CaptureFixture &capture) {
  reset(); new (&attendanceTerminal) UI(terminalHardware,&capture); attendanceTerminal.begin();
}
int main() {
  CaptureFixture capture; combined(capture);
  assert(!attendanceTerminal.running());
  const unsigned initial=images; advance(1000); assert(images==initial);
  modeMenu(); attendanceTerminal.key(1);
  assert(attendanceTerminal.state()==State::ModeConfirm);
  advance(500); assert(images==initial && capture.scans==0); // Confirmation never captures.
  attendanceTerminal.key(2); assert(attendanceTerminal.mode()==terminal::AttendanceMode::Immediate);

  modeMenu(); attendanceTerminal.key(1); attendanceTerminal.key(0);
  assert(!attendanceTerminal.running() && !capture.active && terminalHardware.feedback<0);
  assert(Serial.output.find("CAPTURE NOT STARTED")!=std::string::npos);

  capture.ready=true; combined(capture); modeMenu(); attendanceTerminal.key(1); attendanceTerminal.key(0);
  assert(attendanceTerminal.running() && capture.active);
  assert(attendanceTerminal.mode()==terminal::AttendanceMode::Deferred);
  const unsigned before=images; advance(); advance();
  assert(capture.scans==2 && images==before); // No concurrent local Search/GenImg.
  capture.event=terminal::CaptureEvent::Saved; capture.count=1; advance();
  assert(std::string(terminalHardware.last.line[0])=="CAPTURE SAVED");
  assert(std::string(terminalHardware.last.line[2])=="PENDING MATCH");
  assert(terminalHardware.lastFeedback==terminal::Feedback::CaptureSaved && terminalHardware.feedback==0);
  attendanceTerminal.key(2); assert(!capture.active && !attendanceTerminal.running());
  assert(std::string(terminalHardware.last.line[0])=="DEFERRED STATISTICS");
  const unsigned stopped=capture.scans; advance(1000); assert(capture.scans==stopped);
  attendanceTerminal.cancel(); modeMenu();
  slots[1]=true; terminalHardware.clockPresent=true; terminalHardware.fsOK=true;
  attendanceTerminal.key(0); attendanceTerminal.key(0);
  assert(attendanceTerminal.mode()==terminal::AttendanceMode::Immediate && attendanceTerminal.running());
  terminalHardware.clockPresent=true; terminalHardware.fsOK=true; match();
  assert(terminalHardware.writes==1 && terminalHardware.lastFeedback==terminal::Feedback::AttendanceSaved);
  assert(capture.scans==stopped);

  combined(capture); modeMenu(); attendanceTerminal.key(1); advance(20001);
  assert(attendanceTerminal.mode()==terminal::AttendanceMode::Immediate && !capture.active);
  assert(saves==0 && deletes==0 && clears==0 && terminalHardware.formats==0);

  // Serial arming reports into the same UI without requiring a firmware change.
  combined(capture); capture.active=true; capture.event=terminal::CaptureEvent::Armed; advance();
  assert(attendanceTerminal.mode()==terminal::AttendanceMode::Deferred && attendanceTerminal.running());
  attendanceTerminal.pause(); const unsigned paused=capture.scans; advance();
  assert(!capture.active && capture.scans==paused && attendanceTerminal.paused());
  physical(2,true); advance(2001);
  assert(!attendanceTerminal.paused() && !attendanceTerminal.running() && attendanceTerminal.page()==6);
  physical(2,false);
  attendanceTerminal.key(2); assert(attendanceTerminal.page()==7);
  attendanceTerminal.key(1); assert(attendanceTerminal.state()==State::Idle && deletes==0);
  attendanceTerminal.key(2); assert(attendanceTerminal.page()==8);
  attendanceTerminal.key(1); assert(attendanceTerminal.state()==State::Idle && deletes==0);

  // Every menu keeps its controls in the sixth usable line. The full class
  // UUID must survive the smaller layout, rather than being clipped at the end.
  capture.ready=true; capture.count=512; combined(capture);
  assert(std::string(terminalHardware.last.line[1])=="STOPPED: MENU > START");
  for(unsigned page=0;page<9;++page) {
    assert(attendanceTerminal.page()==page);
    assert(terminalHardware.last.line[terminal::SCREEN_FOOTER][0]);
    for(unsigned i=0;i<256;++i) assert(terminalHardware.pixels[i]==0);
    if(page==1) assert(std::string(terminalHardware.last.line[2]).find("Templates:")==0);
    if(page==8) {
      assert(std::string(terminalHardware.last.line[0])=="CLASS SESSION UUID");
      assert(std::string(terminalHardware.last.line[2])+terminalHardware.last.line[3]==capture.classId());
      assert(std::string(terminalHardware.last.line[4])=="Saved captures: 512");
    }
    attendanceTerminal.key(2);
  }
  modeMenu(); attendanceTerminal.key(1); attendanceTerminal.key(0);
  assert(std::string(terminalHardware.last.line[0])=="DEFERRED CAPTURE");
  assert(std::string(terminalHardware.last.line[1])=="RUNNING: LIFT FINGER");
  assert(std::string(terminalHardware.last.line[2])=="Saved: 512 PENDING");
  assert(std::string(terminalHardware.last.line[3])=="No identity decision");
  assert(std::string(terminalHardware.last.line[4])=="Class batch prepared");
  attendanceTerminal.key(2);
  assert(std::string(terminalHardware.last.line[1])=="Time: boot-relative");
  assert(std::string(terminalHardware.last.line[2])=="Captures: 512 PENDING");
  assert(std::string(terminalHardware.last.line[3])=="Not a presence count");
}
