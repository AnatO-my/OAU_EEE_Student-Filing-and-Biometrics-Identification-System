#define main previousTransferTests
#include "template_transfer_test.cpp"
#undef main

unsigned captures=0;
std::vector<uint8_t> probeBytes;

void probeFixture() {
  resetFixture(); captures=0;
  probeBytes={11,12,13,14,15,16,17,18};
  const auto previous=scanner.onWrite;
  scanner.onWrite=[previous](uint32_t baud,const uint8_t *frame,size_t size) {
    if (frame[6]==1 && frame[9]==1) {
      ++captures;
      return captures==1 ? packet(7,{2}) : ACK_OK;
    }
    if (frame[6]==1 && frame[9]==2) { buffer=probeBytes; return ACK_OK; }
    return previous(baud,frame,size);
  };
}

void queuedProbe(bool badCrc=false) {
  std::string text=importText(probeBytes,badCrc);
  text.replace(0,2,"1 "); // compareSavedProbe receives slot,length,CRC (j consumed).
  sendText(text);
}

int main() {
  probeFixture(); const auto original=flash;
  captureProbe();
  assert(Serial.output.find("FPPROBE 1 ")!=std::string::npos);
  assert(Serial.output.find("FPEND 8 ")!=std::string::npos);
  assert(captures==2 && stores==0 && downloads==0 && flash==original);

  probeFixture(); queuedProbe(); compareSavedProbe();
  assert(Serial.output.find("FPPROBERESULT 1 MATCH 124")!=std::string::npos);
  assert(captures==0 && searches==1 && stores==0 && downloads==1 && uploads==1);
  assert(flash==original && occupiedSlots.size()==1);

  probeFixture(); rejectFinger=true; queuedProbe(); compareSavedProbe();
  assert(Serial.output.find("FPPROBERESULT 1 NO_MATCH 0")!=std::string::npos);
  assert(stores==0 && captures==0);

  probeFixture(); queuedProbe(true); compareSavedProbe();
  assert(downloads==0 && searches==0 && stores==0);
  assert(Serial.output.find("FPERROR")!=std::string::npos);

  probeFixture(); changedBuffer=true; queuedProbe(); compareSavedProbe();
  assert(searches==0 && stores==0);
  assert(Serial.output.find("FPPROBERESULT")==std::string::npos);

  probeFixture(); wrongMatchId=true; queuedProbe(); compareSavedProbe();
  assert(Serial.output.find("FPPROBERESULT")==std::string::npos);

  probeFixture(); occupiedSlots.clear(); queuedProbe(); compareSavedProbe();
  assert(downloads==0 && searches==0 && stores==0);

  probeFixture(); authenticated=false; captureProbe();
  assert(captures==0 && stores==0);
  assert(Serial.output.find("FPPROBE 1")==std::string::npos);
  // Independent direct-comparison fixture: reference must go to buffer 2.
  probeFixture(); const auto base=scanner.onWrite;
  unsigned referenceLoads=0,directMatches=0;
  scanner.onWrite=[&](uint32_t baud,const uint8_t *frame,size_t size) {
    if (frame[6]==1 && frame[9]==7 && frame[10]==2) {
      assert(fingerprint::read16(frame+11)==1); ++referenceLoads; return ACK_OK;
    }
    if (frame[6]==1 && frame[9]==3) {
      assert(referenceLoads==1 && uploads==1 && buffer==probeBytes);
      ++directMatches; return packet(7,{0,0,172});
    }
    return base(baud,frame,size);
  };
  queuedProbe(); compareSavedProbe(true);
  assert(Serial.output.find("FPPROBEDIRECTRESULT 1 MATCH 172")!=std::string::npos);
  assert(directMatches==1 && searches==0 && captures==0 && stores==0 && flash==original);

}
