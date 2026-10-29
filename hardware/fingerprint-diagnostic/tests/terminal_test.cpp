#define TERMINAL_ENABLED 1
#include <assert.h>
#include <new>
#include "../src/main.cpp"

uint32_t fakeMillis=0;
HardwareSerial Serial(0);
using terminal::State;
using UI=terminal::AttendanceTerminal<terminal::TerminalHardware>;

bool slots[150]={},finger=false,thirdMismatch=false,badChecksum=false,storeFailure=false;
bool changedSlot=false;
uint8_t imageStatus=0,searchStatus=9;
uint16_t foundSlot=1;
unsigned saves=0,deletes=0,clears=0,images=0;
std::vector<unsigned> commands,featuresSeen;

std::vector<uint8_t> ack(std::vector<uint8_t> payload) {
  std::vector<uint8_t> f={0xEF,1,255,255,255,255,7,0,static_cast<uint8_t>(payload.size()+2)};
  f.insert(f.end(),payload.begin(),payload.end());
  uint16_t sum=0; for (size_t i=6;i<f.size();++i) sum+=f[i];
  f.push_back(sum>>8); f.push_back(sum); return f;
}
unsigned occupiedCount() { unsigned n=0; for (bool used:slots) n+=used; return n; }
void reset() {
  fakeMillis=0; authenticated=true; connectedBaud=57600;
  Serial.output.clear(); Serial.incoming.clear(); scanner.incoming.clear();
  memset(slots,0,sizeof(slots)); finger=thirdMismatch=badChecksum=storeFailure=changedSlot=false;
  imageStatus=0; searchStatus=9; foundSlot=1; saves=deletes=clears=images=0;
  commands.clear(); featuresSeen.clear();
  terminalHardware=terminal::TerminalHardware();
  new (&attendanceTerminal) UI(terminalHardware);
  scanner.onWrite=[](uint32_t,const uint8_t *r,size_t) {
    commands.push_back(r[9]);
    switch (r[9]) {
    case 0x0F: return ack({0,0,0,0,0,0,150,0,3,255,255,255,255,0,2,0,6});
    case 0x1D: return ack({0,0,static_cast<uint8_t>(occupiedCount())});
    case 0x1F: {
      assert(r[10]==0); std::vector<uint8_t> p(33,0);
      for (unsigned i=0;i<150;++i) if (slots[i]) p[1+i/8]|=1U<<(i%8);
      return ack(p);
    }
    case 1: {
      ++images; auto f=ack({finger?imageStatus:uint8_t(2)});
      if (badChecksum) f.back()^=1;
      return f;
    }
    case 2: featuresSeen.push_back(r[10]); return ack({0});
    case 3:
      if (changedSlot) slots[1]=true;
      return thirdMismatch?ack({8}):ack({0,0,88});
    case 4:
      assert(fingerprint::read16(r+13)==150);
      return searchStatus==9?ack({9,0,0,0,0}):ack({0,static_cast<uint8_t>(foundSlot>>8),static_cast<uint8_t>(foundSlot),0,87});
    case 5: return ack({0});
    case 6:
      ++saves; assert(r[10]==1);
      if (storeFailure) return ack({0x18});
      slots[fingerprint::read16(r+11)]=true; return ack({0});
    case 7: return ack({0});
    case 8: {
      auto response=ack({0}); uint8_t data[32]={},frame[64]={};
      const size_t n=fingerprint::encodeData(frame,sizeof(frame),FINGERPRINT_ADDRESS,data,sizeof(data),true);
      response.insert(response.end(),frame,frame+n); return response;
    }
    case 0x0C:
      ++deletes; assert(fingerprint::read16(r+12)==1);
      slots[fingerprint::read16(r+10)]=false; return ack({0});
    case 0x0D: ++clears; memset(slots,0,sizeof(slots)); return ack({0});
    case 0x13: return ack({0});
    default: assert(false); return ack({1});
    }
  };
  attendanceTerminal.begin();
}
void advance(uint32_t ms=151) { fakeMillis+=ms; attendanceTerminal.tick(); }
void capture(bool present) { finger=present; advance(); }
void physical(unsigned key,bool down,uint32_t ms=31) {
  terminalHardware.buttons[key]=down; attendanceTerminal.pollInputs(); advance(ms);
}
void enrollThree() {
  attendanceTerminal.key(0); assert(attendanceTerminal.state()==State::First);
  capture(true); assert(attendanceTerminal.state()==State::Remove && saves==0);
  capture(false); assert(attendanceTerminal.state()==State::Second);
  capture(true); assert(attendanceTerminal.state()==State::Remove && saves==0);
  capture(false); assert(attendanceTerminal.state()==State::Third);
  capture(true);
}
void match() {
  slots[1]=true; searchStatus=0; attendanceTerminal.resume();
  capture(false); capture(true);
}
int main() {
  reset(); enrollThree();
  assert(saves==1 && slots[1] && attendanceTerminal.state()==State::Notice);
  assert(featuresSeen==std::vector<unsigned>({1,2,2}));
  assert(Serial.output.find("ENROLLED")!=std::string::npos);
  reset(); thirdMismatch=true; enrollThree(); assert(saves==0);
  reset(); changedSlot=true; enrollThree(); assert(saves==0);
  reset(); storeFailure=true; enrollThree();
  assert(saves==1 && occupiedCount()==0 && Serial.output.find("ENROLLED | Saved")==std::string::npos);
  reset(); for (auto &slot:slots) slot=true; slots[0]=false;
  enrollThree(); assert(saves==1 && slots[0]); // Last free slot can be zero.
  reset(); for (auto &slot:slots) slot=true;
  attendanceTerminal.key(0); assert(saves==0 && images==0); // Capacity comes from the module.

  reset(); attendanceTerminal.key(0); capture(true); advance(20001);
  assert(saves==0 && featuresSeen==std::vector<unsigned>({1})); // Lift is mandatory.
  reset(); attendanceTerminal.key(0); capture(true); attendanceTerminal.key(2);
  assert(attendanceTerminal.state()==State::Idle && saves==0);
  reset(); slots[149]=true; foundSlot=149; searchStatus=0;
  attendanceTerminal.key(0); capture(true); assert(saves==0);
  assert(Serial.output.find("Already in slot 149")!=std::string::npos);
  reset(); attendanceTerminal.key(0); imageStatus=3; capture(true);
  assert(attendanceTerminal.state()==State::Remove && saves==0); // Capture failure is not absence.
  reset(); attendanceTerminal.key(0); badChecksum=true; capture(true);
  assert(saves==0 && attendanceTerminal.state()==State::Notice);

  // Confirm a different DELETE press only after identifying and lifting.
  reset(); slots[1]=true; searchStatus=0;
  physical(1,true); capture(true); assert(deletes==0 && attendanceTerminal.state()==State::Remove);
  capture(false); assert(attendanceTerminal.state()==State::DeleteConfirm);
  advance(1000); assert(deletes==0); // Original held key cannot confirm.
  physical(1,false); physical(1,true); assert(deletes==1 && !slots[1]);
  reset(); slots[1]=true; searchStatus=0;
  attendanceTerminal.key(1); capture(true); capture(false); attendanceTerminal.key(2);
  assert(deletes==0);
  reset(); slots[1]=true; searchStatus=0;
  attendanceTerminal.key(1); capture(true); capture(false); advance(8001); assert(deletes==0);

  reset(); slots[1]=true;
  for (int i=0;i<5;++i) attendanceTerminal.key(2);
  assert(attendanceTerminal.page()==5);
  physical(1,true); advance(2900); physical(1,false,0); assert(clears==0);
  assert(attendanceTerminal.state()==State::Idle);
  reset(); slots[1]=true;
  for (int i=0;i<5;++i) attendanceTerminal.key(2);
  physical(1,true); advance(3001); assert(clears==1 && occupiedCount()==0);
  assert(terminalHardware.formats==0); // Erasing fingerprints preserves historical logs.
  advance(5000); assert(clears==1); // No repeat while held.
  reset(); for (int i=0;i<5;++i) attendanceTerminal.key(2);
  physical(1,true); physical(2,true); advance(3001); assert(clears==0);

  reset(); match(); assert(terminalHardware.writes==0);
  assert(Serial.output.find("MATCHED / NOT SAVED")!=std::string::npos);
  assert(std::string(terminalHardware.last.line[0])=="MATCHED / NOT SAVED");
  reset(); terminalHardware.clockPresent=true; terminalHardware.fsOK=true;
  terminalHardware.nextRecord=terminal::LogResult::WriteFailed; match();
  assert(terminalHardware.writes==1 && terminalHardware.feedback<0);
  assert(Serial.output.find("ATTENDANCE SAVED")==std::string::npos);
  reset(); terminalHardware.clockPresent=true; terminalHardware.fsOK=true;
  terminalHardware.nextRecord=terminal::LogResult::Already; match();
  assert(Serial.output.find("ALREADY CHECKED IN")!=std::string::npos);
  reset(); terminalHardware.clockPresent=true; terminalHardware.fsOK=true; match();
  assert(terminalHardware.writes==1 && Serial.output.find("ATTENDANCE SAVED")!=std::string::npos);
  assert(std::string(terminalHardware.last.line[0])=="ATTENDANCE SAVED");
  advance(2500); advance(1000); assert(terminalHardware.writes==1); // Lift gate prevents repeat.

  reset(); attendanceTerminal.key(2); const unsigned before=images;
  capture(true); assert(images==before); // Menus never take attendance.
  advance(20001); assert(attendanceTerminal.page()==0);
  assert(std::string(terminalHardware.last.line[0])=="ATTENDANCE");
  assert(std::string(terminalHardware.last.line[3])=="ENROLL A FINGER");
  reset(); slots[1]=true; attendanceTerminal.resume(); advance(1000);
  assert(std::string(terminalHardware.last.line[3])=="SET CLOCK TO RECORD");
  terminalHardware.clockPresent=true; advance(1000);
  assert(std::string(terminalHardware.last.line[3])=="CHECK LOG STORAGE");
  terminalHardware.fsOK=true; attendanceTerminal.resume(); advance(1000);
  assert(std::string(terminalHardware.last.line[3])=="READY FOR ATTENDANCE");
  reset(); authenticated=false; attendanceTerminal.key(2); attendanceTerminal.key(2);
  attendanceTerminal.key(0); assert(terminalHardware.exports==1); // Sensor offline doesn't block menus.

  reset(); for (int i=0;i<3;++i) attendanceTerminal.key(2);
  attendanceTerminal.key(0); assert(attendanceTerminal.state()==State::Clock);
  for (int i=0;i<5;++i) attendanceTerminal.key(2);
  assert(terminalHardware.clockWrites==1 && Serial.output.find("CLOCK SAVED")==std::string::npos);
  reset(); for (int i=0;i<3;++i) attendanceTerminal.key(2);
  terminalHardware.setOK=true; attendanceTerminal.key(0);
  for (int i=0;i<5;++i) attendanceTerminal.key(2);
  assert(Serial.output.find("CLOCK SAVED")!=std::string::npos);

  reset(); Serial.incoming.push_back('h'); loop();
  assert(attendanceTerminal.paused()); const unsigned pausedImages=images;
  assert(std::string(terminalHardware.last.line[0])=="ATTENDANCE PAUSED");
  finger=true; physical(0,true); advance(5000);
  assert(images==pausedImages && saves==0); // Backup lease excludes physical UI too.
  Serial.incoming.push_back('a'); loop(); assert(!attendanceTerminal.paused());
  reset(); slots[1]=true;
  for (char c:std::string("t 1\n")) Serial.incoming.push_back(c);
  loop();
  const auto begin=Serial.output.find("FPBEGIN "),end=Serial.output.find("FPEND ");
  assert(begin!=std::string::npos && end>begin && attendanceTerminal.paused());
  assert(Serial.output.substr(begin,end-begin).find("UI:")==std::string::npos);
  assert(Serial.output.substr(begin,end-begin).find("FPDATA ")!=std::string::npos);
  reset(); attendanceTerminal.formatStorage(); assert(terminalHardware.formats==0);
  reset(); for (char c:std::string("\nFORMAT\n")) Serial.incoming.push_back(c);
  attendanceTerminal.formatStorage(); assert(terminalHardware.formats==1 && clears==0);
  return 0;
}
