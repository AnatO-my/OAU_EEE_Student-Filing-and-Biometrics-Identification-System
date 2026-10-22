#include <assert.h>
#include <string>
#include "terminal_storage.h"

using namespace terminal;
struct MemoryFile {
  std::string bytes; size_t pos=0;
  explicit MemoryFile(const std::string &s):bytes(s) {}
  bool available() { return pos<bytes.size(); }
  int read() { return available()?static_cast<unsigned char>(bytes[pos++]):-1; }
};
std::string row(const char *date,unsigned slot,const char *hash) {
  return std::string("00000000-0000-4000-8000-000000000001,00000000-0000-4000-8000-000000000002,")+
    date+","+std::to_string(slot)+","+hash+",87\n";
}
int main() {
  Button key;
  key.sample(true,0); key.sample(true,100); assert(!key.take()); // Held at boot.
  key.sample(false,101); key.sample(false,131);
  key.sample(true,140); key.sample(false,150); key.sample(true,155);
  key.sample(true,184); assert(!key.take());
  key.sample(true,185); assert(key.take()); assert(!key.take());
  key.sample(true,4000); assert(!key.take() && key.active());
  key.suppress(); key.sample(true,5000); assert(!key.take() && !key.active());
  key.sample(false,5001); key.sample(false,5031);
  key.sample(true,5040); key.sample(true,5070); assert(key.take());
  key.sample(false,5071); assert(!key.rawDown()); // Erase hold cancels before debounced release.
  Button wrap;
  wrap.sample(false,0xFFFFFFD0); wrap.sample(true,0xFFFFFFF0); wrap.sample(true,15);
  assert(wrap.take());

  uint8_t r[]={0x59,0x59,0x23,0x02,0x31,0x12,0x24}; DateTime t;
  assert(decodeClock(r,t) && t.year==2024 && t.hour==23);
  r[0]|=0x80; assert(!decodeClock(r,t)); r[0]=0x59;
  r[2]=0x72; assert(decodeClock(r,t) && t.hour==12); // 12 PM
  r[2]=0x52; assert(decodeClock(r,t) && t.hour==0); // 12 AM
  r[2]=0x40; assert(!decodeClock(r,t));
  r[2]=0; r[1]=0x6A; assert(!decodeClock(r,t)); r[1]=0;
  r[4]=0x29; r[5]=0x02; r[6]=0x26; assert(!decodeClock(r,t));
  r[6]=0x24; assert(decodeClock(r,t));
  uint8_t encoded[7]; encodeClock(t,encoded); DateTime roundTrip;
  assert(decodeClock(encoded,roundTrip) && dateKey(roundTrip)==20240229);
  DateTime midnight; midnight.year=2025;
  assert(secondsSince2000(midnight)==789004800UL);

  const std::string hashA(64,'a'),hashB(64,'b');
  const std::string history=std::string(LOG_HEADER)+row("2026-10-14T23:59:59",1,hashA.c_str())+
    row("2026-10-15T09:00:00",1,hashB.c_str());
  bool duplicate=false; uint32_t today=0;
  MemoryFile f(history);
  assert(inspectLog(f,20261015,hashA.c_str(),duplicate,today) && !duplicate && today==1);
  MemoryFile g(history); // Slot reused; today's different template must not hide the new identity.
  assert(inspectLog(g,20261015,hashB.c_str(),duplicate,today) && duplicate && today==1);
  MemoryFile torn(history.substr(0,history.size()-1));
  assert(!inspectLog(torn,20261015,nullptr,duplicate,today));
  MemoryFile wrongHeader("date,time,slot\n"); assert(!inspectLog(wrongHeader,0,nullptr,duplicate,today));
  MemoryFile invalidDate(std::string(LOG_HEADER)+row("2026-02-30T00:00:00",1,hashA.c_str()));
  assert(!inspectLog(invalidDate,0,nullptr,duplicate,today));
  MemoryFile overflow(std::string(LOG_HEADER)+std::string(300,'a')+"\n");
  assert(!inspectLog(overflow,0,nullptr,duplicate,today));
}
