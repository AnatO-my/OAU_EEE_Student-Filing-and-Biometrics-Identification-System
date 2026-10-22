#pragma once
#include <stddef.h>
#include <stdint.h>

namespace terminal {
// SSD1306 and SH1106 both support explicit page/column writes. The SH1106 has
// 132 RAM columns and normally exposes columns 2..129 on a 128-pixel panel.
// Keeping page selection explicit avoids repeatedly writing only the top band
// when an SH1106 is connected to an SSD1306 horizontal-window driver.
template <typename Bus> class OledPages {
  Bus &bus_;
  uint8_t address_;
  bool sh1106_;

  bool send(uint8_t control,const uint8_t *bytes,size_t size) {
    bus_.beginTransmission(address_);
    const bool queued=bus_.write(control)==1 && bus_.write(bytes,size)==size;
    const bool acknowledged=bus_.endTransmission()==0;
    return queued && acknowledged;
  }
  bool position(uint8_t page,uint8_t column) {
    const uint8_t cursor[]={static_cast<uint8_t>(0xB0|page),
      static_cast<uint8_t>(column&15),static_cast<uint8_t>(0x10|(column>>4))};
    return send(0,cursor,sizeof(cursor));
  }
public:
  OledPages(Bus &bus,uint8_t address,bool sh1106):bus_(bus),address_(address),sh1106_(sh1106) {}

  bool begin(void (*idle)()=nullptr) {
    // Keep the display off until EVERY RAM page, including unused SH1106 edge
    // columns, has been cleared. Power-on RAM contents must never be displayed.
    const uint8_t common[]={0xAE,0xD5,0x80,0xA8,0x3F,0xD3,0,0x40,
      0xA1,0xC8,0xDA,0x12,0x81,0xCF,0xD9,0x1F,0xDB,0x40,0xA4,0xA6};
    if (!send(0,common,sizeof(common))) return false;
    if (sh1106_) {
      const uint8_t power[]={0xAD,0x8B};
      if (!send(0,power,sizeof(power))) return false;
    } else {
      const uint8_t mode[]={0x2E,0x8D,0x14,0x20,0x02}; // Stop scrolling; page mode.
      if (!send(0,mode,sizeof(mode))) return false;
    }
    const uint8_t blank[16]={};
    const unsigned columns=sh1106_?132:128;
    for (uint8_t page=0;page<8;++page) {
      if (!position(page,0)) return false;
      for (unsigned column=0;column<columns;column+=sizeof(blank)) {
        const size_t count=columns-column<sizeof(blank)?columns-column:sizeof(blank);
        if (!send(0x40,blank,count)) return false;
        if (idle) idle();
      }
    }
    const uint8_t on[]={0xAF};
    return send(0,on,sizeof(on));
  }

  bool page(uint8_t page,const uint8_t *pixels,void (*idle)()=nullptr) {
    if (page>=8 || !pixels || !position(page,sh1106_?2:0)) return false;
    for (size_t column=0;column<128;column+=16) {
      // Seventeen bytes including the control byte also fit a 32-byte Wire bus.
      if (!send(0x40,pixels+column,16)) return false;
      if (idle) idle();
    }
    return true;
  }
  bool contrast(bool dim) {
    const uint8_t value[]={0x81,static_cast<uint8_t>(dim?0x10:0xCF)};
    return send(0,value,sizeof(value));
  }
};
} // namespace terminal
