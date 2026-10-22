#include <assert.h>
#include <string.h>
#include <vector>
#include "oled_pages.h"

// Model page-addressed display RAM, initially filled with power-on noise.
// SH1106 deliberately rejects SSD1306's horizontal addressing commands.
struct PanelBus {
  bool sh1106,on=false,clearedBeforeOn=false,overflow=false,fail=false,shortWrite=false;
  unsigned page=0,column=0,dataPackets=0;
  uint8_t ram[8][132];
  std::vector<uint8_t> pending;
  explicit PanelBus(bool sh):sh1106(sh) { memset(ram,0xA5,sizeof(ram)); }
  unsigned width() const { return sh1106?132:128; }
  void beginTransmission(uint8_t address) { assert(address==0x3C); pending.clear(); }
  size_t write(uint8_t byte) { pending.push_back(byte); return 1; }
  size_t write(const uint8_t *bytes,size_t size) {
    if (shortWrite && size) --size;
    pending.insert(pending.end(),bytes,bytes+size); return size;
  }
  uint8_t endTransmission() {
    assert(pending.size()<=32 && !pending.empty());
    if (fail) return 4;
    if (pending[0]==0x40) {
      ++dataPackets;
      for (size_t i=1;i<pending.size();++i) {
        if (column>=width()) { column=0; overflow=true; }
        ram[page][column++]=pending[i];
      }
    } else {
      assert(pending[0]==0);
      for (size_t i=1;i<pending.size();++i) {
        const uint8_t cmd=pending[i];
        if (cmd>=0xB0 && cmd<=0xB7) page=cmd&7;
        else if (cmd<=0x0F) column=(column&0xF0)|cmd;
        else if (cmd>=0x10 && cmd<=0x1F) column=(column&15)|((cmd&15)<<4);
        else if (cmd==0xAF) {
          on=true; clearedBeforeOn=true;
          for (unsigned p=0;p<8;++p) for (unsigned c=0;c<width();++c)
            if (ram[p][c]) clearedBeforeOn=false;
        } else if (cmd==0xAE) on=false;
        else if (cmd==0x20) {
          assert(!sh1106 && ++i<pending.size() && pending[i]==2);
        } else if (cmd==0x21 || cmd==0x22) {
          assert(false); // Neither controller path may depend on a window write.
        } else if (cmd==0xD5 || cmd==0xA8 || cmd==0xD3 || cmd==0xDA ||
                   cmd==0x81 || cmd==0xD9 || cmd==0xDB || cmd==0x8D || cmd==0xAD) {
          assert(++i<pending.size());
        }
      }
    }
    return 0;
  }
};

unsigned idleCalls=0;
void idle() { ++idleCalls; }

int main() {
  for (bool sh:{false,true}) {
    PanelBus bus(sh);
    terminal::OledPages<PanelBus> display(bus,0x3C,sh);
    idleCalls=0;
    assert(display.begin(idle) && bus.on && bus.clearedBeforeOn && !bus.overflow);
    assert(idleCalls==(sh?72U:64U));

    // Distinct bytes on EVERY page catch top-band-only updates and offsets.
    uint8_t frame[8][128];
    for (unsigned p=0;p<8;++p) {
      for (unsigned c=0;c<128;++c) frame[p][c]=static_cast<uint8_t>((p+1)*13+c);
      assert(display.page(p,frame[p],idle));
    }
    const unsigned offset=sh?2:0;
    for (unsigned p=0;p<8;++p) {
      assert(memcmp(bus.ram[p]+offset,frame[p],128)==0);
      if (sh) assert(bus.ram[p][0]==0 && bus.ram[p][1]==0 &&
                     bus.ram[p][130]==0 && bus.ram[p][131]==0);
    }
    assert(!bus.overflow);
    uint8_t blank[128]={};
    assert(display.page(7,blank));
    assert(memcmp(bus.ram[7]+offset,blank,128)==0);
    assert(display.contrast(true) && display.contrast(false));
    const unsigned before=bus.dataPackets;
    assert(!display.page(8,blank) && !display.page(0,nullptr));
    assert(bus.dataPackets==before);
    bus.shortWrite=true; assert(!display.page(0,blank));
    bus.shortWrite=false; bus.fail=true; assert(!display.page(0,blank));
    assert(!display.begin() && !display.contrast(true));
  }
  PanelBus truncated(false); truncated.shortWrite=true;
  terminal::OledPages<PanelBus> display(truncated,0x3C,false);
  assert(!display.begin() && !truncated.on);
}
