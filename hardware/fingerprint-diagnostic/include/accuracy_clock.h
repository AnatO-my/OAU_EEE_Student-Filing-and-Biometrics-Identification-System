#pragma once
#include <Wire.h>
#include "terminal_config.h"
#include "terminal_logic.h"

#ifndef ACCURACY_RTC_UTC_OFFSET_MINUTES
#define ACCURACY_RTC_UTC_OFFSET_MINUTES 60
#endif

namespace accuracy {
static_assert(ACCURACY_RTC_UTC_OFFSET_MINUTES>=-840 && ACCURACY_RTC_UTC_OFFSET_MINUTES<=840,"Invalid RTC UTC offset");
static_assert(TERMINAL_SDA_PIN!=TERMINAL_SCL_PIN && TERMINAL_SDA_PIN!=FINGERPRINT_RX_PIN &&
  TERMINAL_SDA_PIN!=FINGERPRINT_TX_PIN && TERMINAL_SCL_PIN!=FINGERPRINT_RX_PIN &&
  TERMINAL_SCL_PIN!=FINGERPRINT_TX_PIN,"RTC pins overlap scanner pins");
// The DS1307 stores local calendar time, with no built-in timezone.
class Clock {
  bool bus_=false,baseline_=false,entry_=false,overflow_=false;
  uint32_t changedAt_=0,previous_=0,watchAt_=0,entryAt_=0;
  unsigned watchRemaining_=0;
  char text_[20]={}; size_t length_=0;
public:
  void begin() {
    bus_=Wire.begin(TERMINAL_SDA_PIN,TERMINAL_SCL_PIN,100000);
    Wire.setTimeOut(25);
  }
  const char *read(terminal::DateTime &t) {
    if (!bus_) return "io_error";
    Wire.beginTransmission(0x68); Wire.write(uint8_t(0));
    if (Wire.endTransmission(false)!=0 || Wire.requestFrom(uint8_t(0x68),uint8_t(7))!=7) {
      baseline_=false; return "io_error";
    }
    uint8_t r[7]; for (auto &v:r) v=Wire.read();
    if (r[0]&0x80) { baseline_=false; return "stopped"; }
    if (!terminal::decodeClock(r,t)) { baseline_=false; return "invalid"; }
    const uint32_t now=millis(),seconds=terminal::secondsSince2000(t);
    if (baseline_ && seconds<previous_) {
      previous_=seconds; changedAt_=now; return "backward";
    }
    if (!baseline_ || seconds!=previous_) { baseline_=true; previous_=seconds; changedAt_=now; }
    return now-changedAt_>=2500?"stalled":"ok";
  }
  void record(uint32_t boot,uint32_t session,const char *test,uint64_t event,const char *scope) {
    terminal::DateTime t;
    const char *status=read(t); char stamp[32]="NA",id[24]="NA";
    if (!strcmp(status,"ok") || !strcmp(status,"stalled") || !strcmp(status,"backward"))
      terminal::stamp(t,stamp,sizeof(stamp));
    if (event) snprintf(id,sizeof(id),"%llu",static_cast<unsigned long long>(event));
    Serial.printf("ACCTIME,%08lX-%lu,%s,%s,%s,%s,%s,%d,%lu\n",
      static_cast<unsigned long>(boot),static_cast<unsigned long>(session),test,id,scope,stamp,status,
      ACCURACY_RTC_UTC_OFFSET_MINUTES,static_cast<unsigned long>(millis()));
  }
  bool entering() const { return entry_; }
  void startSet() {
    entry_=true; length_=0; overflow_=false; entryAt_=millis(); watchRemaining_=0;
    Serial.printf("ACCRTC enter local YYYY-MM-DDTHH:MM:SS then Enter (20 s; p cancels). UTC offset minutes=%d.\n",ACCURACY_RTC_UTC_OFFSET_MINUTES);
  }
  void consume(int key) {
    if (key=='p' || key=='P') { entry_=false; Serial.println("ACCRTC set cancelled."); return; }
    if (key=='\r') return;
    if (key==' ' && length_==0) return;
    if (key!='\n') {
      if (length_<19) text_[length_++]=key; else overflow_=true;
      return;
    }
    entry_=false; text_[length_]=0;
    terminal::DateTime t;
    unsigned y,m,d,h,n,s; int end=0;
    if (overflow_ || length_!=19 || sscanf(text_,"%4u-%2u-%2uT%2u:%2u:%2u%n",&y,&m,&d,&h,&n,&s,&end)!=6 ||
        end!=19 || y<2000 || y>2099 || m>12 || d>31 || h>23 || n>59 || s>59) {
      Serial.println("ACCRTC invalid timestamp; clock unchanged."); return;
    }
    t.year=y; t.month=m; t.day=d; t.hour=h; t.minute=n; t.second=s;
    if (!bus_ || !terminal::valid(t)) { Serial.println("ACCRTC invalid date or I2C unavailable; clock unchanged."); return; }
    uint8_t r[7]; terminal::encodeClock(t,r);
    Wire.beginTransmission(0x68); Wire.write(uint8_t(0)); Wire.write(r,7);
    if (Wire.endTransmission()!=0) { Serial.println("ACCRTC write failed; time unconfirmed."); return; }
    baseline_=false; terminal::DateTime back;
    const char *status=read(back);
    const auto intended=terminal::secondsSince2000(t);
    if (strcmp(status,"ok") || terminal::secondsSince2000(back)<intended || terminal::secondsSince2000(back)-intended>1)
      Serial.println("ACCRTC write sent but readback failed; time unconfirmed.");
    else Serial.println("ACCRTC SET VERIFIED; check advancing time with w. No automatic setting on boot.");
  }
  void watch() { watchRemaining_=10; watchAt_=millis()-1000; }
  void tick(uint32_t boot,uint32_t session,const char *test) {
    if (entry_ && millis()-entryAt_>=20000) { entry_=false; Serial.println("ACCRTC set entry timed out; clock unchanged."); }
    if (watchRemaining_ && millis()-watchAt_>=1000) {
      watchAt_=millis(); --watchRemaining_; record(boot,session,test,0,"check");
    }
  }
};
} // namespace accuracy
