#define main previousTransferTests
#include "template_transfer_test.cpp"
#undef main
#include "deferred_device.h"

FakeFlash fakeFlash;
LittleFileSystem LittleFS;
const char *BATCH="00000000-0000-4000-8000-000000000002";
const char *DIRECTORY="/probes/00000000-0000-4000-8000-000000000002/";
bool finger=false;
unsigned fresh=0;

void command(deferred::Device &device,const std::string &text) {
  Serial.output.clear(); sendText(text+"\n"); device.command();
}
void newBatch(deferred::Device &device) {
  command(device,std::string("begin ")+BATCH+" 00000000-0000-4000-8000-000000000003 00000000-0000-4000-8000-000000000004 as608-unit-1");
  assert(Serial.output.find("FPBCREATED")!=std::string::npos);
}
void tick(deferred::Device &device,bool placed) {
  finger=placed; fakeMillis+=150; device.tick();
}
void fixture() {
  resetFixture(); fakeFlash=FakeFlash(); finger=false; fresh=0;
  const auto previous=scanner.onWrite;
  scanner.onWrite=[previous](uint32_t baud,const uint8_t *frame,size_t size) {
    if(frame[6]==1 && frame[9]==1) { ++fresh; return finger?ACK_OK:packet(7,{2}); }
    if(frame[6]==1 && frame[9]==2) { buffer={1,2,3,4,5}; return ACK_OK; }
    // No enrolment, search, comparison, delete or persistent sensor write.
    if(frame[6]==1) assert(frame[9]==1||frame[9]==2||frame[9]==8||frame[9]==15);
    return previous(baud,frame,size);
  };
}

int main() {
  fixture(); deferred::Device device; device.begin(); newBatch(device);
  assert(device.nextBatch() && device.prepared() && !device.armed());
  const auto original=flash;
  command(device,std::string("arm ")+BATCH);
  assert(Serial.output.find("FPBARMED")!=std::string::npos);
  tick(device,true); // Finger already placed on arm must be lifted first.
  assert(uploads==0);
  tick(device,false); tick(device,true);
  assert(Serial.output.find("FPBSAVED")!=std::string::npos && uploads==1);
  tick(device,true); tick(device,true); assert(uploads==1);
  const auto saved=fakeFlash.files;
  assert(saved.count(std::string(DIRECTORY)+"000000"));
  assert(!saved.count(std::string(DIRECTORY)+"pending"));
  assert(stores==0 && downloads==0 && searches==0 && flash==original);

  // Simulated reboot: files survive, capture never auto-arms.
  deferred::Device reboot; reboot.begin(); const unsigned earlier=fresh;
  assert(reboot.prepared() && !reboot.armed() && !strcmp(reboot.batchId(),BATCH));
  assert(reboot.savedCount()==1);
  tick(reboot,true); assert(fresh==earlier);
  command(reboot,std::string("export ")+BATCH);
  assert(Serial.output.find("FPBATCH 1 1 0")!=std::string::npos);
  assert(Serial.output.find("FPBLOCK event")!=std::string::npos && fresh==earlier);
  assert(fakeFlash.files==saved); // Export is read-only and repeatable.
  command(reboot,std::string("arm ")+BATCH);
  tick(reboot,false); tick(reboot,true); assert(uploads==2);
  assert(fakeFlash.files.count(std::string(DIRECTORY)+"000001"));
  command(reboot,"stop"); const unsigned stopped=fresh; tick(reboot,false); assert(fresh==stopped);
  command(reboot,std::string("begin ")+BATCH+" 00000000-0000-4000-8000-000000000003 00000000-0000-4000-8000-000000000004 as608-unit-1");
  assert(Serial.output.find("FPBERROR")!=std::string::npos);

  // A torn write never receives a save receipt and never gets overwritten.
  command(reboot,std::string("arm ")+BATCH); Serial.output.clear();
  fakeFlash.shortWrite=true; tick(reboot,false); tick(reboot,true);
  assert(Serial.output.find("FPBERROR")!=std::string::npos && Serial.output.find("FPBSAVED")==std::string::npos);
  assert(fakeFlash.files.count(std::string(DIRECTORY)+"pending"));
  fakeFlash.shortWrite=false;
  command(reboot,std::string("arm ")+BATCH); assert(Serial.output.find("interrupted write")!=std::string::npos);
  command(reboot,std::string("export ")+BATCH); assert(Serial.output.find("FPBATCH 1 2 1")!=std::string::npos);
  fakeFlash.files[std::string(DIRECTORY)+"000000"][50]^=1;
  command(reboot,std::string("export ")+BATCH);
  assert(Serial.output.find("FPBERROR")!=std::string::npos && Serial.output.find("FPBATCH ")==std::string::npos);

  fixture(); deferred::Device full; full.begin(); newBatch(full); fakeFlash.full=true;
  command(full,std::string("arm ")+BATCH); assert(Serial.output.find("FPBERROR")!=std::string::npos);
  tick(full,false); tick(full,true); assert(uploads==0);
  fixture(); fakeFlash.mountOK=false; deferred::Device missing; missing.begin();
  command(missing,"list"); assert(Serial.output.find("no automatic format")!=std::string::npos);
  fakeFlash.rawErased=false;
  command(missing,"initialize EMPTY"); assert(fakeFlash.formats==0);
  assert(Serial.output.find("partition contains data")!=std::string::npos);
  fakeFlash.rawErased=true; fakeFlash.rawReadFails=true;
  command(missing,"initialize EMPTY"); assert(fakeFlash.formats==0);
  fakeFlash.rawReadFails=false;
  command(missing,"initialize EMPTY"); assert(fakeFlash.formats==1);
  assert(Serial.output.find("FPBINITIALIZED")!=std::string::npos);
  command(missing,"initialize EMPTY"); assert(fakeFlash.formats==1);
  return 0;
}
