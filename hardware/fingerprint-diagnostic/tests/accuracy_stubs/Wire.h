#pragma once
#include <stdint.h>
#include <stddef.h>
#include <vector>
class TwoWire {
  std::vector<uint8_t> pending_;
  size_t index_=0;
public:
  bool busOK=true;
  uint8_t error=0,readCount=7;
  uint8_t registers[7]={0,0,0,1,1,1,0};
  unsigned clockWrites=0;
  int sda=-1,scl=-1; uint32_t rate=0;
  bool begin(int a,int b,uint32_t hz) { sda=a; scl=b; rate=hz; return busOK; }
  void setTimeOut(unsigned) {}
  void beginTransmission(uint8_t address) { (void)address; pending_.clear(); }
  size_t write(uint8_t byte) { pending_.push_back(byte); return 1; }
  size_t write(const uint8_t *bytes,size_t length) {
    pending_.insert(pending_.end(),bytes,bytes+length); return length;
  }
  uint8_t endTransmission(bool=true) {
    if (!error && pending_.size()==8 && pending_[0]==0) {
      for (unsigned i=0;i<7;++i) registers[i]=pending_[i+1];
      ++clockWrites;
    }
    return error;
  }
  uint8_t requestFrom(uint8_t,uint8_t) { index_=0; return readCount; }
  int read() { return registers[index_++]; }
};
extern TwoWire Wire;
