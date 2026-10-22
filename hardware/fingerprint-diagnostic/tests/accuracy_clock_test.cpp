#include <assert.h>
#include <Arduino.h>
#include "accuracy_clock.h"
uint32_t fakeMillis=0;
HardwareSerial Serial(0);
TwoWire Wire;
void set(accuracy::Clock &clock,const char *text) {
  clock.startSet(); for (const char *p=text;*p;++p) clock.consume(*p);
}
int main() {
  accuracy::Clock clock; clock.begin(); terminal::DateTime t;
  assert(Wire.sda==21 && Wire.scl==22 && Wire.rate==100000 && Wire.clockWrites==0);
  Wire.error=2; assert(!strcmp(clock.read(t),"io_error")); Wire.error=0;
  Wire.readCount=6; assert(!strcmp(clock.read(t),"io_error")); Wire.readCount=7;
  Wire.registers[0]=0x80; assert(!strcmp(clock.read(t),"stopped")); Wire.registers[0]=0;
  Wire.registers[5]=0x13; assert(!strcmp(clock.read(t),"invalid")); Wire.registers[5]=1;
  set(clock,"2026-10-15T15:45:00\n");
  assert(Wire.clockWrites==1 && !clock.entering());
  assert(!strcmp(clock.read(t),"ok") && t.hour==15 && t.minute==45);
  fakeMillis+=3000; assert(!strcmp(clock.read(t),"stalled"));
  Wire.registers[0]=1; assert(!strcmp(clock.read(t),"ok"));
  Wire.registers[0]=0; assert(!strcmp(clock.read(t),"backward"));
  set(clock,"2026-02-30T15:45:00\n"); assert(Wire.clockWrites==1);
  set(clock,"2026-10-15T25:45:00\n"); assert(Wire.clockWrites==1);
  set(clock,"2026-10-15T15:45:000\n"); assert(Wire.clockWrites==1);
  set(clock,"p"); assert(Wire.clockWrites==1 && !clock.entering());
  clock.startSet(); fakeMillis+=20001; clock.tick(1,1,"verify_1to1"); assert(!clock.entering());
  Serial.output.clear(); clock.watch();
  for (unsigned i=0;i<11;++i) { clock.tick(1,1,"verify_1to1"); fakeMillis+=1000; }
  size_t count=0,pos=0; while ((pos=Serial.output.find("ACCTIME,",pos))!=std::string::npos) { ++count; ++pos; }
  assert(count==10);
  Wire.error=2; Serial.output.clear(); clock.record(1,1,"identify_1toN",4,"trial");
  assert(Serial.output.find(",4,trial,NA,io_error,60,")!=std::string::npos);
  puts("RTC tests passed: I2C errors, stopped/invalid/stalled/backward clock, set/readback, timeout and watch.");
}
