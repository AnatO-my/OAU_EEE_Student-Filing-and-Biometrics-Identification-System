#pragma once

#include <stdint.h>
#include <string.h>

namespace oled_integrity {
constexpr unsigned WIDTH=128, HEIGHT=64, PAGES=8, TOP_PIXELS=16;
constexpr unsigned STATIC_STEPS=11, STEP_COUNT=STATIC_STEPS+PAGES+HEIGHT;

enum class Pattern { Text, White, Black, Horizontal, HorizontalInverse,
                     Vertical, VerticalInverse, Checker, CheckerInverse,
                     Top, Lower, Band, PixelRow };

struct Step {
  Pattern pattern;
  unsigned index;
  uint32_t holdMs;
};

inline Step step(unsigned number) {
  number%=STEP_COUNT;
  if (number<STATIC_STEPS) return {static_cast<Pattern>(number),0,number==0?5000U:3000U};
  number-=STATIC_STEPS;
  if (number<PAGES) return {Pattern::Band,number,1000};
  number-=PAGES;
  return {Pattern::PixelRow,number,number<TOP_PIXELS?600U:120U};
}

// Each text line is one eight-pixel page, matching the terminal's text height.
// Repeating the same digits on every line makes a damaged region easy to compare.
inline void digit(uint8_t *frame,unsigned page,unsigned x,unsigned value) {
  static const uint8_t rows[10][7]={
    {14,17,19,21,25,17,14},{4,12,4,4,4,4,14},{14,17,1,2,4,8,31},
    {30,1,1,14,1,1,30},{2,6,10,18,31,2,2},{31,16,16,30,1,1,30},
    {14,16,16,30,17,17,14},{31,1,2,4,8,8,8},{14,17,17,14,17,17,14},
    {14,17,17,15,1,1,14}};
  for (unsigned y=0;y<7;++y) for (unsigned col=0;col<5;++col)
    if (rows[value%10][y] & (1U<<(4-col))) frame[page*WIDTH+x+col]|=1U<<y;
}

inline void render(uint8_t *frame,const Step &current) {
  memset(frame,0,WIDTH*PAGES);
  if (current.pattern==Pattern::Text) {
    for (unsigned page=0;page<PAGES;++page) {
      digit(frame,page,0,page+1);
      frame[page*WIDTH+8]=0x36; // Colon after the one-based text-row number.
      for (unsigned col=0;col<18;++col) digit(frame,page,18+col*6,col);
    }
    return;
  }
  for (unsigned page=0;page<PAGES;++page) for (unsigned x=0;x<WIDTH;++x) {
    uint8_t value=0;
    switch (current.pattern) {
      case Pattern::White: value=0xFF; break;
      case Pattern::Horizontal: value=0x55; break;
      case Pattern::HorizontalInverse: value=0xAA; break;
      case Pattern::Vertical: value=(x&1)?0:0xFF; break;
      case Pattern::VerticalInverse: value=(x&1)?0xFF:0; break;
      case Pattern::Checker: value=((page+x/8)&1)?0:0xFF; break;
      case Pattern::CheckerInverse: value=((page+x/8)&1)?0xFF:0; break;
      case Pattern::Top: value=page<TOP_PIXELS/8?0xFF:0; break;
      case Pattern::Lower: value=page<TOP_PIXELS/8?0:0xFF; break;
      case Pattern::Band: value=page==current.index?0xFF:0; break;
      case Pattern::PixelRow:
        value=page==current.index/8?static_cast<uint8_t>(1U<<(current.index%8)):0;
        break;
      default: break; // Black, or an unsupported pattern, clears every byte.
    }
    frame[page*WIDTH+x]=value;
  }
}
} // namespace oled_integrity
