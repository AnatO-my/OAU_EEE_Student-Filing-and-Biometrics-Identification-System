#include <assert.h>
#include "../src/accuracy_main.cpp"

uint32_t fakeMillis=0;
HardwareSerial Serial(0);
TwoWire Wire;
bool occupied[150]={},finger=false,imageTimeout=false,searchTimeout=false,corruptSearch=false;
bool shortReject=false,shortAccept=false;
bool diagnosticTest=false,enrollmentTest=false;
bool imageUsed=false;
uint8_t loadCode=0,matchCode=0,mergeCode=0,storeCode=0;
unsigned stores=0,loads=0,matches=0;
std::vector<unsigned> diagnosticOperations;
uint8_t imageCode=0,featureCode=0,searchCode=0;
uint16_t returned=7,securityLevel=3;
unsigned searches=0,featureCalls=0;

std::vector<uint8_t> ack(std::vector<uint8_t> payload) {
  const size_t length=payload.size()+2;
  std::vector<uint8_t> frame={0xEF,1,255,255,255,255,7,static_cast<uint8_t>(length>>8),static_cast<uint8_t>(length)};
  frame.insert(frame.end(),payload.begin(),payload.end());
  unsigned checksum=0; for (size_t i=6;i<frame.size();++i) checksum+=frame[i];
  frame.push_back(checksum>>8); frame.push_back(checksum); return frame;
}
void reset() {
  fakeMillis=0; authenticated=false; connectedBaud=0;
  Wire=TwoWire();
  accuracyInputs=accuracy::Inputs(); experiment=accuracy::Experiment();
  Serial.incoming.clear(); Serial.output.clear(); scanner.incoming.clear();
  memset(occupied,0,sizeof(occupied)); occupied[1]=occupied[7]=occupied[149]=true;
  finger=imageTimeout=searchTimeout=corruptSearch=shortReject=shortAccept=false;
  diagnosticTest=enrollmentTest=false; loadCode=matchCode=mergeCode=storeCode=0; stores=loads=matches=0;
  diagnosticOperations.clear();
  imageUsed=false;
  imageCode=featureCode=searchCode=0; returned=7; securityLevel=3; searches=featureCalls=0;
  scanner.onWrite=[](uint32_t baud,const uint8_t *r,size_t size) {
    assert(r[6]==1 && baud==57600);
    switch(r[9]) {
    case 0x13: return ack({0});
    case 0x0F: return ack({0,0,0,0,0,0,150,0,static_cast<uint8_t>(securityLevel),255,255,255,255,0,2,0,6});
    case 0x1D: {
      unsigned count=0; for (bool slot:occupied) count+=slot;
      return ack({0,0,static_cast<uint8_t>(count)});
    }
    case 0x1F: {
      assert(r[10]==0); std::vector<uint8_t> table(33,0);
      for (unsigned i=0;i<150;++i) if (occupied[i]) table[1+i/8]|=1U<<(i%8);
      return ack(table);
    }
    case 1:
      if (imageTimeout) return std::vector<uint8_t>{};
      if (finger && !imageCode) imageUsed=false;
      return ack({finger?imageCode:uint8_t(2)});
    case 2:
      assert(size==13 && (r[10]==1 || (enrollmentTest && r[10]==2))); ++featureCalls;
      if (diagnosticTest && imageUsed) return ack({7}); // Repeated conversion can invalidate the module's image.
      imageUsed=true; return ack({featureCode});
    case 3:
      assert(diagnosticTest && size==12); ++matches; diagnosticOperations.push_back(2);
      return matchCode?ack({matchCode}):ack({0,0,87});
    case 5: assert(enrollmentTest && size==12); return ack({mergeCode});
    case 6: {
      assert(enrollmentTest && size==15 && r[10]==1); ++stores;
      const auto id=fingerprint::read16(r+11);
      assert(id<150 && !occupied[id]);
      if (!storeCode) occupied[id]=true;
      return ack({storeCode});
    }
    case 7:
      assert(diagnosticTest && size==15 && r[10]==2 && fingerprint::read16(r+11)==7);
      ++loads; return ack({loadCode});
    case 4: {
      assert(size==17 && r[10]==1); ++searches;
      if (diagnosticTest) {
        const auto first=fingerprint::read16(r+11),count=fingerprint::read16(r+13);
        assert((first==0 && count==150) || (first==7 && count==1));
        diagnosticOperations.push_back(first?1:0);
      } else {
        assert(fingerprint::read16(r+11)==(enrollmentTest?0:(ACCURACY_VERIFICATION?7:0)));
        assert(fingerprint::read16(r+13)==(enrollmentTest?150:(ACCURACY_VERIFICATION?1:150)));
      }
      if (searchTimeout) return std::vector<uint8_t>{};
      if (searchCode==9) return shortReject?ack({9,0}):ack({9,0,0,0,0});
      if (searchCode!=0) return ack({searchCode});
      auto response=shortAccept?ack({0,0,7}):ack({0,static_cast<uint8_t>(returned>>8),static_cast<uint8_t>(returned),0,87});
      if (corruptSearch) response.back()^=1;
      return response;
    }
    // Enrollment writes are accepted ONLY in tests explicitly requesting e.
    // Export, delete and empty commands remain forbidden in every mode.
    default: assert(false); return ack({1});
    }
  };
  setup();
  assert(authenticated && !experiment.running());
}
void send(const char *text) { for (const char *p=text;*p;++p) Serial.incoming.push_back(*p); loop(); }
void step(uint32_t ms=100) { fakeMillis+=ms; loop(); }
void start(const char *which="g") { send("t 7\n"); send(which); assert(experiment.running()); }
void scan() { finger=true; step(); }
const accuracy::Counts &counts(accuracy::Truth truth=accuracy::Truth::Genuine,accuracy::Source source=accuracy::Source::Automatic) {
  return experiment.statistics().buckets[static_cast<unsigned>(source)][static_cast<unsigned>(truth)];
}
int main(int argc,char **argv) {
  using accuracy::Truth; using accuracy::Source;
  reset(); start(); step(10000); assert(counts().attempts==0);
  scan(); assert(counts().attempts==1 && counts().tp==1 && searches==1 && featureCalls==1);
  step(5000); assert(searches==1); // Held finger is not a repeated presentation.
  finger=false; step(); finger=true; step(); assert(searches==2 && counts().tp==2);
  assert(Serial.output.find("ACCREADY")!=std::string::npos);
  reset(); start(); scan(); finger=false; step(); finger=true; step(500);
  assert(searches==1); step(1500); assert(searches==2); // Removal during cooldown adds no extra delay/key.
  reset(); start(); searchCode=9; scan(); assert(counts().fn==1 && counts().tp==0);
  reset(); start("i"); searchCode=9; scan(); assert(counts(Truth::Impostor).tn==1);
  reset(); start("i"); scan(); assert(counts(Truth::Impostor).fp==1);
  reset(); start(); returned=149; scan();
#if ACCURACY_VERIFICATION
  assert(counts().communication==1 && counts().fn==0); // Search range was one; another ID is malformed.
#else
  assert(counts().fn==1 && counts().wrongId==1 && counts().tp==0);
#endif
  reset(); start(); featureCode=6; scan();
  assert(counts().acquisition==1 && counts().fn==0 && counts().attempts==1 && searches==0);
  reset(); start(); imageCode=3; scan(); assert(counts().acquisition==1 && featureCalls==0);
  reset(); start(); featureCode=1; scan(); assert(counts().sensor==1 && counts().fn==0);
  reset(); start(); searchTimeout=true; scan(); assert(counts().communication==1 && counts().fn==0);
  reset(); start(); corruptSearch=true; scan(); assert(counts().communication==1 && counts().tp==0);
  reset(); start(); searchCode=9; shortReject=true; scan(); assert(counts().communication==1 && counts().fn==0);
  reset(); start(); shortAccept=true; scan(); assert(counts().communication==1);
  reset(); start(); returned=148; scan(); assert(counts().communication==1); // Empty returned ID.
  reset(); start(); returned=150; scan(); assert(counts().communication==1); // Out of range.
  reset(); start(); imageTimeout=true; step(); step(); step();
  assert(!experiment.running() && counts().attempts==0 && counts().pollErrors==3);

  reset(); start(); scan(); send("i"); step(5000);
  assert(counts(Truth::Impostor).attempts==0); // A held genuine finger cannot spill into the next block.
  finger=false; step(); finger=true; step(); assert(counts(Truth::Impostor).fp==1 && counts().tp==1);
  reset(); start(); occupied[7]=false; occupied[8]=true; send("g"); assert(!experiment.running());
  assert(Serial.output.find("occupied slots changed")!=std::string::npos);
  reset(); start(); securityLevel=4; send("g"); assert(!experiment.running());
  reset(); send("t 148\ng"); assert(!experiment.running()); // Empty expected target never silently becomes slot zero.
  reset(); send("t 0\ng"); assert(!experiment.running());
  occupied[0]=true; send("n"); send("t 0\ng"); assert(experiment.running()); // Valid slot zero is selectable.
  reset(); send("t 65536\n"); assert(!experiment.running());
  send("t 7"); step(15001); assert(!experiment.running());

  reset(); start(); send("123"); assert(counts().attempts==0);
  send("m"); send("123");
  assert(counts(Truth::Genuine,Source::Manual).attempts==3);
  assert(counts(Truth::Genuine,Source::Manual).tp==1 && counts(Truth::Genuine,Source::Manual).fn==1);
  assert(counts(Truth::Genuine,Source::Manual).unclassified==1 && counts().attempts==0);
  finger=false; step(); scan(); assert(counts(Truth::Genuine,Source::Manual).attempts==3 && counts().attempts==0);
  assert(Serial.output.find(",scan,0,")!=std::string::npos);
  send("i"); send("123");
  assert(counts(Truth::Impostor,Source::Manual).attempts==3 && counts(Truth::Impostor,Source::Manual).tn==1 &&
    counts(Truth::Impostor,Source::Manual).fp==1 && counts(Truth::Impostor,Source::Manual).unclassified==1);
  send("p"); const auto before=counts(Truth::Impostor,Source::Manual).attempts;
  accuracyInputs.buttons[1]=true; accuracyInputs.poll(); step(31);
  assert(counts(Truth::Impostor,Source::Manual).attempts==before+1);
  step(5000); assert(counts(Truth::Impostor,Source::Manual).attempts==before+1);
  send("s"); assert(Serial.output.find("ACCSUMMARY,")!=std::string::npos);
  send("n"); assert(experiment.statistics().combined(Source::Manual).attempts==0 && !experiment.running());
  reset(); send("s"); assert(Serial.output.find(",NA,NA,NA,NA,NA,NA,NA\n")!=std::string::npos);
  reset(); diagnosticTest=true; send("t 7\nq"); step(); scan();
  assert(searches==1 && loads==0 && matches==0 && featureCalls==1);
  assert(counts().attempts==0 && !experiment.running());
  assert(Serial.output.find("operation=selected_search")!=std::string::npos);
  assert(Serial.output.find("ACCTRIAL,")==std::string::npos);
  assert((diagnosticOperations==std::vector<unsigned>{1}));
  finger=false; send("q"); step(); scan();
  finger=false; send("q"); step(); scan();
  assert((diagnosticOperations==std::vector<unsigned>{1,2,0}));
  assert(featureCalls==3 && searches==2 && matches==1 && counts().attempts==0 && stores==0);
  reset(); diagnosticTest=true; send("t 7\nq"); step(); scan();
  loadCode=0x0C; finger=false; send("q"); step(); scan();
  assert(loads==1 && matches==0 && counts().attempts==0 && searches==1);
  reset(); diagnosticTest=true; send("t 7\nq"); step(20001); scan(); assert(searches==0);
  reset(); diagnosticTest=true; send("t 7\nqp"); step(); scan(); assert(searches==0);

  reset(); enrollmentTest=true; searchCode=9; send("e"); step(); scan();
  finger=false; step(); scan();
  assert(stores==1 && occupied[2] && experiment.target()==2 && !experiment.running());
  assert(counts().attempts==0 && Serial.output.find("ACCENROLL SAVED ID=2")!=std::string::npos);
  reset(); enrollmentTest=true; send("e"); step(); scan(); // Existing finger.
  finger=false; step(); scan(); assert(stores==0);
  reset(); enrollmentTest=true; searchCode=9; mergeCode=0x0A; send("e"); step(); scan();
  finger=false; step(); scan(); assert(stores==0);
  reset(); enrollmentTest=true; searchCode=9; send("e"); step(); scan();
  occupied[2]=true; finger=false; step(); scan(); assert(stores==0); // Never overwrite a changed slot.
  reset(); enrollmentTest=true; searchCode=9; send("e"); step(); scan();
  storeCode=0x18; finger=false; step(); scan(); step(); assert(stores==1 && !occupied[2]);
  assert(Serial.output.find("save unconfirmed")!=std::string::npos);
  reset(); enrollmentTest=true; send("ep"); step(); scan(); assert(stores==0 && featureCalls==0);
  reset(); enrollmentTest=true; send("e"); step(20001); scan(); assert(stores==0 && featureCalls==0);
  reset(); enrollmentTest=true; searchCode=9; memset(occupied,0,sizeof(occupied));
  send("e"); step(); scan(); finger=false; step(); scan(); assert(stores==1 && occupied[1]);
  reset(); enrollmentTest=true; memset(occupied,1,sizeof(occupied));
  send("e"); step(); scan(); assert(stores==0 && featureCalls==0);
  if (argc>1 && std::string(argv[1])=="--transcript") {
    reset(); start(); scan(); send("i"); finger=false; step();
    searchCode=9; scan(); send("m"); send("123s");
    printf("%s",Serial.output.c_str());
  }
  printf("Accuracy firmware passed: %s (synthetic scanner only).\n",accuracy::TEST_NAME);
}
