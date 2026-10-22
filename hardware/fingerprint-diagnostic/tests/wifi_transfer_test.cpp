#define TERMINAL_ENABLED 1
#define DEFERRED_ENABLED 1
#define WIFI_TRANSFER_ENABLED 1
#define main originalWifiTerminalTests
#include "terminal_test.cpp"
#undef main

FakeFlash fakeFlash;
LittleFileSystem LittleFS;
WiFiClass WiFi;
FakeTls fakeTls;
bool fakeMenu=false;
const std::string zeros(64,'0');
const char *batchId="00000000-0000-4000-8000-000000000002";

void wifiCommand(const std::string &text) {
  for(char c:text) Serial.incoming.push_back(c);
  wifiTransfer.command();
}
void configure() {
  std::string data("FPW1\x20\xfb",6);
  for(const auto &value:std::vector<std::string>{"classroom","private-password","192.168.1.5",std::string(64,'a'),zeros,
      "-----BEGIN CERTIFICATE-----\nsynthetic-test-only\n-----END CERTIFICATE-----\n"}) {
    data+=value; data.push_back(0);
  }
  wifiCommand("configure "+std::to_string(data.size())+" "+zeros+"\n"+data);
  assert(Serial.output.find("FPWCONFIGURED")!=std::string::npos);
  assert(Serial.output.find(std::string(64,'a'))==std::string::npos);
}
void fixture() {
  reset(); fakeMenu=false; fakeFlash=FakeFlash(); deferredDevice=deferred::Device(); deferredDevice.begin();
  new (&attendanceTerminal) UI(terminalHardware,&deferredDevice); attendanceTerminal.begin();
  WiFi=WiFiClass(); fakeTls=FakeTls();
  new (&wifiTransfer) wireless::Transfer(deferredDevice); wifiTransfer.begin(cancelWireless);
  deferredDevice.setWireless(queueWireless); configure();
  Serial.output.clear(); commands.clear();
}
void reply(const std::string &type,const std::string &id,unsigned count,bool valid=true) {
  fakeTls.onLine=[type,id,count,valid](const std::string &line) {
    if(line.find("FPWIFI 1 ")==0) return std::string("FPWREADY 1\n");
    if(line.find("FPBATCHEND ")==0 || line.find("FPFILEEND ")==0)
      return "FPWRECEIPT 1 "+type+" "+id+" "+(valid?zeros:std::string(64,'b'))+" "+zeros+" "+std::to_string(count)+"\n";
    return std::string();
  };
}
void runTransfer(const char *type,const char *id) {
  assert(wifiTransfer.queue(type,id));
  for(unsigned i=0;i<4 && wifiTransfer.busy();++i) loop();
  assert(!wifiTransfer.busy());
}
int main() {
  fixture(); wifiCommand("status\n");
  assert(Serial.output.find(std::string("FPWSTATUS 1 ")+deferredDevice.deviceId()+" 1 ")!=std::string::npos);
  wifiCommand("forget\n"); assert(!wifiTransfer.queue("csv","attendance"));
  configure();
  assert(!wifiTransfer.queue("batch","../invalid"));
  assert(!wifiTransfer.queue("csv","wrong"));
  assert(!wifiTransfer.queue("template","01") && !wifiTransfer.queue("template","65535") && !wifiTransfer.queue("template","65536"));
  assert(!wifiTransfer.queue("template","1 extra"));

  // Prepare a real controller batch; Wi-Fi reuses the identical USB frame source.
  for(char c:std::string("begin ")+batchId+" 00000000-0000-4000-8000-000000000003 00000000-0000-4000-8000-000000000004 as608-unit-1\n") Serial.incoming.push_back(c);
  deferredDevice.command(); assert(deferredDevice.prepared());
  auto before=fakeFlash.files; reply("batch",batchId,0); runTransfer("batch",batchId);
  assert(fakeTls.output.find("FPBATCH 1 0 0")!=std::string::npos);
  assert(!fakeTls.ca.empty() && Serial.output.find("FPWSAVED")!=std::string::npos);
  assert(fakeFlash.files==before && !deferredDevice.armed());
  assert(fakeLastShaInput()==zeros+":0");
  const std::string pendingPath=std::string("/probes/")+batchId+"/pending";
  fakeFlash.files[pendingPath]={1};
  fakeTls=FakeTls(); reply("batch",batchId,0); runTransfer("batch",batchId);
  assert(fakeLastShaInput()==zeros+":1" && fakeFlash.files.count(pendingPath));
  fakeFlash.files.erase(pendingPath); // Fixture reset only; firmware never deletes it.

  // A changed certificate pin stops before credentials/data are transmitted.
  fakeTls=FakeTls(); fakeTls.pinOK=false; runTransfer("batch",batchId);
  assert(fakeTls.output.empty() && fakeFlash.files==before);
  assert(deferredDevice.takeEvent()==terminal::CaptureEvent::Error);
  fakeTls=FakeTls(); reply("batch",batchId,0,false); runTransfer("batch",batchId);
  assert(fakeFlash.files==before && deferredDevice.takeEvent()==terminal::CaptureEvent::Error);
  fakeTls=FakeTls(); fakeTls.shortWrite=true; runTransfer("batch",batchId);
  assert(fakeFlash.files==before && deferredDevice.takeEvent()==terminal::CaptureEvent::Error);
  fakeTls=FakeTls(); fakeTls.connectOK=false; runTransfer("batch",batchId);
  assert(fakeTls.output.empty() && fakeFlash.files==before);

  // Capture/menu actions never run while association owns the loop.
  fakeTls=FakeTls(); WiFi.connected=false;
  assert(wifiTransfer.queue("batch",batchId)); const unsigned initial=images;
  loop(); fakeMillis+=20001; loop();
  assert(!wifiTransfer.busy() && images==initial && fakeFlash.files==before);
  WiFi.connected=true; fakeMenu=true; const auto connects=fakeTls.connects;
  runTransfer("batch",batchId); assert(fakeTls.connects==connects); fakeMenu=false;
  assert(deferredDevice.takeEvent()==terminal::CaptureEvent::Cancelled);
  assert(Serial.output.find("FPWCANCELLED ")!=std::string::npos);

  // CSV is streamed without replacing its historical origin UUID or bytes.
  const std::string csv=std::string(terminal::LOG_HEADER)+
    "00000000-0000-4000-8000-000000000010,00000000-0000-4000-8000-000000000011,2026-10-21T09:10:11,1,"+std::string(64,'a')+",87\n";
  fakeFlash.files["/attendance.csv"]={csv.begin(),csv.end()}; before=fakeFlash.files;
  fakeTls=FakeTls(); reply("csv","attendance",1); runTransfer("csv","attendance");
  assert(fakeTls.output.find("FPFILE 1 csv "+std::to_string(csv.size()))!=std::string::npos);
  assert(fakeFlash.files==before && deferredDevice.takeEvent()==terminal::CaptureEvent::Exported);
  fakeFlash.files["/attendance.csv"].pop_back(); fakeTls=FakeTls(); reply("csv","attendance",1);
  runTransfer("csv","attendance"); assert(fakeTls.output.find("FPFILE 1 csv")==std::string::npos);
  assert(deferredDevice.takeEvent()==terminal::CaptureEvent::Error);

  // Enrolled backup only reads LoadChar/UpChar: no Store/Delete/Empty/GenImg.
  slots[1]=true; commands.clear(); fakeTls=FakeTls(); reply("template","1",1);
  const auto files=fakeFlash.files; runTransfer("template","1");
  assert(fakeTls.output.find("FPFILE 1 template 50 ")!=std::string::npos);
  assert(fakeTls.output.find("46505431")!=std::string::npos);
  for(unsigned command:commands) assert(command==15 || command==31 || command==7 || command==8);
  assert(saves==0 && deletes==0 && clears==0 && fakeFlash.files==files && fakeFlash.formats==0);

  // Fresh DELETE on either export page queues transfer rather than deletion.
  attendanceTerminal.cancel(); attendanceTerminal.key(2); attendanceTerminal.key(2);
  assert(attendanceTerminal.page()==2); attendanceTerminal.key(1);
  assert(wifiTransfer.busy() && !attendanceTerminal.running() && deletes==0);
  fakeMenu=true; loop(); fakeMenu=false; assert(!wifiTransfer.busy());
  attendanceTerminal.tick();
  assert(terminalHardware.lastFeedback==terminal::Feedback::Cancelled && terminalHardware.feedback==0);
  assert(std::string(terminalHardware.last.line[0])=="TRANSFER CANCELLED");
  // A MENU press while frames are sent also produces neutral cancellation.
  fakeTls=FakeTls(); fakeTls.onLine=[](const std::string &line) {
    if(line.find("FPWIFI 1 ")==0) return std::string("FPWREADY 1\n");
    if(line.find("FPFILE 1 template ")==0) fakeMenu=true;
    return std::string();
  };
  runTransfer("template","1"); fakeMenu=false;
  assert(deferredDevice.takeEvent()==terminal::CaptureEvent::Cancelled);
  assert(fakeTls.output.find("FPFILEEND")==std::string::npos && fakeFlash.files==files);
  return 0;
}
