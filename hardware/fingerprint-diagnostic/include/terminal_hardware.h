#pragma once

#include <Arduino.h>
#include <Wire.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <esp_system.h>
#include <mbedtls/sha256.h>
#include "terminal_config.h"
#include "terminal_storage.h"
#include "oled_pages.h"
#include "terminal_feedback.h"

void serviceTerminalInputs();

namespace terminal {
struct Screen { char line[8][22] = {}; };

// A small 5x7 uppercase font, represented as rows. Drawn into a native
// SSD1306 framebuffer; no display/fingerprint/RTC third-party library needed.
inline const uint8_t *glyph(char c) {
  static const uint8_t letters[][7] = {
    {14,17,17,31,17,17,17},{30,17,17,30,17,17,30},{14,17,16,16,16,17,14},
    {30,17,17,17,17,17,30},{31,16,16,30,16,16,31},{31,16,16,30,16,16,16},
    {14,17,16,23,17,17,15},{17,17,17,31,17,17,17},{14,4,4,4,4,4,14},
    {7,2,2,2,18,18,12},{17,18,20,24,20,18,17},{16,16,16,16,16,16,31},
    {17,27,21,21,17,17,17},{17,25,21,19,17,17,17},{14,17,17,17,17,17,14},
    {30,17,17,30,16,16,16},{14,17,17,17,21,18,13},{30,17,17,30,20,18,17},
    {15,16,16,14,1,1,30},{31,4,4,4,4,4,4},{17,17,17,17,17,17,14},
    {17,17,17,17,17,10,4},{17,17,17,21,21,21,10},{17,17,10,4,10,17,17},
    {17,17,10,4,4,4,4},{31,1,2,4,8,16,31}};
  static const uint8_t digits[][7] = {
    {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},
    {30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},
    {14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},
    {14,17,17,15,1,1,14}};
  static const uint8_t blank[7]={}, colon[]={0,4,4,0,4,4,0}, dash[]={0,0,0,31,0,0,0},
    plus[]={0,4,4,31,4,4,0}, slash[]={1,2,2,4,8,8,16}, dot[]={0,0,0,0,0,6,6},
    eq[]={0,0,31,0,31,0,0}, gt[]={16,8,4,2,4,8,16}, question[]={14,17,1,2,4,0,4};
  if (c>='a' && c<='z') c-=32;
  if (c>='A' && c<='Z') return letters[c-'A'];
  if (c>='0' && c<='9') return digits[c-'0'];
  switch(c) { case ':': return colon; case '-': return dash; case '+': return plus;
    case '/': return slash; case '.': return dot; case '=': return eq; case '>': return gt;
    case '?': return question; default: return blank; }
}

class TerminalHardware {
  uint8_t frame_[1024] = {}, shown_[1024] = {};
  OledPages<TwoWire> oled_{Wire,OLED_ADDRESS,TERMINAL_OLED_SH1106!=0};
  bool redrawAll_=true;
  FeedbackPlayer feedback_;
  char device_[37] = {};
  bool bus_ = false;
  bool prepareLog() {
    if (!fsOK || !uuid(device_)) return false;
    if (LittleFS.exists("/attendance.csv")) return true;
    auto f=LittleFS.open("/attendance.csv","w");
    if (!f) return false;
    const bool ok=f.print(LOG_HEADER)==strlen(LOG_HEADER); f.flush(); f.close(); return ok;
  }
  static void newUuid(char *out) {
    uint8_t b[16]; esp_fill_random(b,sizeof(b));
    b[6]=(b[6]&15)|0x40; b[8]=(b[8]&63)|0x80;
    snprintf(out,37,"%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
      b[0],b[1],b[2],b[3],b[4],b[5],b[6],b[7],b[8],b[9],b[10],b[11],b[12],b[13],b[14],b[15]);
  }
public:
  bool oledOK=false, rtcOK=false, fsOK=false;
  void begin() {
    pinMode(TERMINAL_ENROLL_PIN,INPUT_PULLUP); pinMode(TERMINAL_DELETE_PIN,INPUT_PULLUP);
    pinMode(TERMINAL_MENU_PIN,INPUT_PULLUP);
    pinMode(TERMINAL_GREEN_PIN,OUTPUT); pinMode(TERMINAL_RED_PIN,OUTPUT);
    pinMode(TERMINAL_BUZZER_PIN,OUTPUT); off();
    bus_=Wire.begin(TERMINAL_SDA_PIN,TERMINAL_SCL_PIN,I2C_RATE); Wire.setTimeOut(25);
    if (bus_ && TERMINAL_OLED_ENABLED) {
      oledOK=oled_.begin(serviceTerminalInputs); redrawAll_=true;
      Serial.printf("OLED: %s at 0x%02X; explicit page writes; %s.\n",
        TERMINAL_OLED_SH1106?"SH1106":"SSD1306",OLED_ADDRESS,oledOK?"ready":"unavailable");
    }
    fsOK=LittleFS.begin(false); // Never format an unknown/failed filesystem automatically.
    Preferences prefs;
    if (prefs.begin("fp-terminal",false)) {
      const String saved=prefs.getString("device", "");
      if (saved.length()==36) memcpy(device_,saved.c_str(),37);
      if (!uuid(device_)) {
        newUuid(device_);
        if (prefs.putString("device",device_)!=36) device_[0]=0;
      }
      prefs.end();
    }
    notify(Feedback::Startup);
  }
  bool button(unsigned i) const {
    const int pins[]={TERMINAL_ENROLL_PIN,TERMINAL_DELETE_PIN,TERMINAL_MENU_PIN};
    return digitalRead(pins[i])==LOW;
  }
  void off() {
    feedback_.stop();
    digitalWrite(TERMINAL_GREEN_PIN,LOW); digitalWrite(TERMINAL_RED_PIN,LOW);
    digitalWrite(TERMINAL_BUZZER_PIN,TERMINAL_BUZZER_ACTIVE_HIGH ? LOW : HIGH);
  }
  void notify(Feedback event) {
    feedback_.start(event,millis()); tick();
  }
  void tick() {
    feedback_.tick(millis());
    digitalWrite(TERMINAL_GREEN_PIN,feedback_.green()?HIGH:LOW);
    digitalWrite(TERMINAL_RED_PIN,feedback_.red()?HIGH:LOW);
    digitalWrite(TERMINAL_BUZZER_PIN,(feedback_.buzzer()==bool(TERMINAL_BUZZER_ACTIVE_HIGH))?HIGH:LOW);
  }
  bool readClock(DateTime &time) {
    rtcOK=false;
    if (!bus_) return false;
    Wire.beginTransmission(RTC_ADDRESS); Wire.write(uint8_t(0));
    if (Wire.endTransmission(false)!=0 || Wire.requestFrom(RTC_ADDRESS,uint8_t(7))!=7) return false;
    uint8_t registers[7]; for (auto &r:registers) r=Wire.read();
    rtcOK=decodeClock(registers,time); return rtcOK;
  }
  bool setClock(const DateTime &time) {
    if (!bus_ || !valid(time)) return false;
    uint8_t registers[7]; encodeClock(time,registers);
    Wire.beginTransmission(RTC_ADDRESS); Wire.write(uint8_t(0)); Wire.write(registers,7);
    if (Wire.endTransmission()!=0) return false;
    DateTime readback;
    return readClock(readback) && secondsSince2000(readback)>=secondsSince2000(time) &&
      secondsSince2000(readback)-secondsSince2000(time)<=1;
  }
  bool hashTemplate(const uint8_t *bytes,size_t size,char *out) {
    uint8_t hash[32];
    if (mbedtls_sha256_ret(bytes,size,hash,0)!=0) return false;
    for (size_t i=0;i<32;++i) snprintf(out+2*i,3,"%02x",hash[i]);
    return true;
  }
  bool todayCount(const DateTime &t,uint32_t &count) {
    if (!prepareLog()) return false;
    auto f=LittleFS.open("/attendance.csv","r"); bool duplicate=false;
    return f && f.size()<=MAX_LOG_BYTES && inspectLog(f,dateKey(t),nullptr,duplicate,count,serviceTerminalInputs);
  }
  LogResult record(const DateTime &t,uint16_t slot,uint16_t score,const char *hash) {
    if (!valid(t) || !hexString(hash,64) || !prepareLog()) return LogResult::Unavailable;
    auto f=LittleFS.open("/attendance.csv","r");
    if (!f) return LogResult::Unavailable;
    if (f.size()>MAX_LOG_BYTES) return LogResult::Full;
    bool duplicate=false; uint32_t count=0;
    if (!inspectLog(f,dateKey(t),hash,duplicate,count,serviceTerminalInputs)) return LogResult::Corrupt;
    const size_t offset=f.size(); f.close();
    if (duplicate) return LogResult::Already;
    char event[37], timestamp[20], row[LOG_LINE_BYTES]; newUuid(event); stamp(t,timestamp,sizeof(timestamp));
    const int length=snprintf(row,sizeof(row),"%s,%s,%s,%u,%s,%u\n",event,device_,timestamp,slot,hash,score);
    if (length<=0 || static_cast<size_t>(length)>=sizeof(row)) return LogResult::WriteFailed;
    if (offset+length>MAX_LOG_BYTES) return LogResult::Full;
    f=LittleFS.open("/attendance.csv","a"); if (!f) return LogResult::WriteFailed;
    const bool written=f.print(row)==static_cast<size_t>(length); f.flush(); f.close();
    // Confirm the saved bytes before presenting a successful check-in.
    f=LittleFS.open("/attendance.csv","r"); char back[LOG_LINE_BYTES]={};
    if (!written || !f || f.size()!=offset+length || !f.seek(offset) ||
        f.readBytes(back,length)!=static_cast<size_t>(length) || memcmp(back,row,length)!=0)
      return LogResult::WriteFailed;
    return LogResult::Saved;
  }
  bool exportLog() {
    if (!prepareLog()) return false;
    auto f=LittleFS.open("/attendance.csv","r"); bool duplicate=false; uint32_t count=0;
    if (!f || f.size()>MAX_LOG_BYTES || !inspectLog(f,0,nullptr,duplicate,count,serviceTerminalInputs) || !f.seek(0)) return false;
    Serial.println("LOGBEGIN CSV local-check-ins v1");
    uint8_t bytes[128];
    while (f.available()) {
      const size_t n=f.read(bytes,sizeof(bytes)); if (!n) return false;
      Serial.write(bytes,n);
      serviceTerminalInputs();
    }
    Serial.println("LOGEND"); return true;
  }
  bool formatStorage() {
    LittleFS.end(); fsOK=false;
    if (!LittleFS.format()) return false;
    fsOK=LittleFS.begin(false); return prepareLog();
  }
  void contrast(bool dim) {
    if (!oledOK) return;
    oledOK=oled_.contrast(dim);
  }
  void show(const Screen &screen) {
    if (!oledOK) return;
    memset(frame_,0,sizeof(frame_));
    for (size_t row=0;row<8;++row) for (size_t c=0;c<21 && screen.line[row][c];++c) {
      const uint8_t *bits=glyph(screen.line[row][c]);
      for (unsigned y=0;y<7;++y) for (unsigned x=0;x<5;++x)
        if (bits[y] & (1U<<(4-x))) frame_[row*128+c*6+x]|=1U<<y;
    }
    for (unsigned p=0;p<8;++p) {
      if (!redrawAll_ && memcmp(frame_+128*p,shown_+128*p,128)==0) continue;
      if (!oled_.page(p,frame_+128*p,serviceTerminalInputs)) { oledOK=false; return; }
      memcpy(shown_+128*p,frame_+128*p,128);
    }
    redrawAll_=false;
  }
};
} // namespace terminal
