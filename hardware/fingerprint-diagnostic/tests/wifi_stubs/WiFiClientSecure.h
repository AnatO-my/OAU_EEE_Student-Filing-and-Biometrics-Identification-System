#pragma once
#include <functional>
#include <string>
#include <deque>
struct FakeTls {
  bool connectOK=true,connected=false,pinOK=true,shortWrite=false;
  unsigned connects=0;
  std::string output,ca;
  std::deque<char> incoming;
  std::function<std::string(const std::string &)> onLine;
};
extern FakeTls fakeTls;
class WiFiClientSecure {
  std::string pending_;
public:
  void stop() { fakeTls.connected=false; }
  bool connected() { return fakeTls.connected; }
  void setCACert(const char *ca) { fakeTls.ca=ca; }
  void setHandshakeTimeout(unsigned) {}
  void setTimeout(unsigned) {}
  bool connect(const char *,uint16_t,int) { ++fakeTls.connects; return fakeTls.connected=fakeTls.connectOK; }
  bool getFingerprintSHA256(uint8_t *out) { memset(out,fakeTls.pinOK?0:1,32); return true; }
  size_t write(const uint8_t *data,size_t n) {
    if(fakeTls.shortWrite) return 0;
    fakeTls.output.append(reinterpret_cast<const char *>(data),n);
    for(size_t i=0;i<n;++i) {
      if(data[i]=='\n') {
        if(fakeTls.onLine) { const auto response=fakeTls.onLine(pending_); fakeTls.incoming.insert(fakeTls.incoming.end(),response.begin(),response.end()); }
        pending_.clear();
      } else pending_+=static_cast<char>(data[i]);
    }
    return n;
  }
  size_t write(uint8_t c) { return write(&c,1); }
  int available() { return static_cast<int>(fakeTls.incoming.size()); }
  int read() { if(fakeTls.incoming.empty()) return -1; const auto c=fakeTls.incoming.front(); fakeTls.incoming.pop_front(); return c; }
};
