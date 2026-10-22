#pragma once
#include <sys/time.h>
constexpr int WIFI_OFF=0,WIFI_STA=1,WL_CONNECTED=3,LOW=0;
extern bool fakeMenu;
inline int digitalRead(int) { return fakeMenu?LOW:1; }
inline void configTime(int,int,const char *,const char *) {}
inline int fakeSettimeofday(const timeval *,const void *) { return 0; }
#define settimeofday fakeSettimeofday
struct WiFiClass {
  bool connected=true; unsigned begins=0; int currentMode=WIFI_OFF;
  void persistent(bool) {}
  void setAutoReconnect(bool) {}
  void mode(int value) { currentMode=value; }
  void begin(const char *,const char *) { ++begins; }
  int status() { return connected?WL_CONNECTED:0; }
  void disconnect(bool,bool) {}
};
extern WiFiClass WiFi;
