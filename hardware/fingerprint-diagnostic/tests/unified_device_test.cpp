#define TERMINAL_ENABLED 1
#define DEFERRED_ENABLED 1
#define main originalLocalTerminalTests
#include "terminal_test.cpp"
#undef main

FakeFlash fakeFlash;
LittleFileSystem LittleFS;
void sendCommand(const std::string &text) {
  for(char c:text) Serial.incoming.push_back(c);
  loop();
}
int main() {
  reset(); fakeFlash=FakeFlash(); deferredDevice=deferred::Device(); deferredDevice.begin();
  new (&attendanceTerminal) UI(terminalHardware,&deferredDevice); attendanceTerminal.begin();
  assert(!attendanceTerminal.running());
  sendCommand("z begin 00000000-0000-4000-8000-000000000002 00000000-0000-4000-8000-000000000003 00000000-0000-4000-8000-000000000004 as608-unit-1\n");
  assert(deferredDevice.prepared() && !deferredDevice.armed());
  sendCommand("z arm 00000000-0000-4000-8000-000000000002\n");
  assert(attendanceTerminal.mode()==terminal::AttendanceMode::Deferred && attendanceTerminal.running());
  commands.clear(); const auto before=fakeFlash.files; const unsigned previous=images;
  capture(false); assert(images==previous+1); // One GenImg, not two competing loop clients.
  capture(true); assert(deferredDevice.savedCount()==1);
  assert(fakeFlash.files.size()==before.size()+1 && saves==0 && deletes==0 && clears==0);
  assert(terminalHardware.writes==0 && terminalHardware.feedback==0);
  assert(std::string(terminalHardware.last.line[0])=="CAPTURE SAVED");
  for(auto command:commands) assert(command==1 || command==2 || command==8 || command==15);
  const auto saved=fakeFlash.files;
  sendCommand("h"); assert(attendanceTerminal.paused() && !deferredDevice.armed());
  const unsigned stopped=images; advance(1000); assert(images==stopped && fakeFlash.files==saved);
  Serial.output.clear();
  sendCommand("z export 00000000-0000-4000-8000-000000000002\n");
  const auto begin=Serial.output.find("FPBATCH 1"),end=Serial.output.find("FPBATCHEND ");
  assert(begin!=std::string::npos && end>begin);
  assert(Serial.output.substr(begin,end-begin).find("UI:")==std::string::npos);
  assert(fakeFlash.files==saved && !deferredDevice.armed());
  sendCommand("a"); assert(deferredDevice.armed());
  capture(true); assert(deferredDevice.savedCount()==1); // Re-arm still requires lift.
  capture(false); capture(true); assert(deferredDevice.savedCount()==2);
  // A fresh physical MENU press during GenImg prevents a pending save.
  capture(false);
  const auto originalScanner=scanner.onWrite;
  scanner.onWrite=[originalScanner](uint32_t baud,const uint8_t *bytes,size_t size) {
    if(bytes[9]==1) {
      terminalHardware.buttons[2]=true; attendanceTerminal.pollInputs();
      fakeMillis+=31; attendanceTerminal.pollInputs();
    }
    return originalScanner(baud,bytes,size);
  };
  capture(true); assert(!deferredDevice.armed() && deferredDevice.savedCount()==2);
  scanner.onWrite=originalScanner;
  advance(); assert(!attendanceTerminal.running());
  assert(saves==0 && deletes==0 && clears==0 && terminalHardware.formats==0);
}
