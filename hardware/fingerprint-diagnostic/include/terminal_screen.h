#pragma once

#include <stddef.h>
#include <stdint.h>
#include <string.h>

namespace terminal {
// The reported faulty pixel lines (2,4,6,8,10,12) lie within this band.
// Keep complete eight-pixel text rows below y=16; diagnostics still test all 64.
constexpr size_t OLED_WIDTH=128, OLED_RESERVED_TOP=16, OLED_FRAME_BYTES=1024;
constexpr size_t SCREEN_ROWS=(64-OLED_RESERVED_TOP)/8, SCREEN_COLUMNS=21;
constexpr size_t SCREEN_FOOTER=SCREEN_ROWS-1;
struct Screen { char line[SCREEN_ROWS][SCREEN_COLUMNS+1] = {}; };

// Existing terminal 5x7 uppercase font, represented as rows.
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

inline void renderScreen(const Screen &screen,uint8_t (&frame)[OLED_FRAME_BYTES]) {
  // Always clear the reserved band as well as previously displayed content.
  memset(frame,0,sizeof(frame));
  for (size_t row=0;row<SCREEN_ROWS;++row)
    for (size_t c=0;c<SCREEN_COLUMNS && screen.line[row][c];++c) {
      const uint8_t *bits=glyph(screen.line[row][c]);
      for (unsigned y=0;y<7;++y) for (unsigned x=0;x<5;++x)
        if (bits[y] & (1U<<(4-x)))
          frame[(OLED_RESERVED_TOP/8+row)*OLED_WIDTH+c*6+x]|=1U<<y;
    }
}
} // namespace terminal
