#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "terminal_screen.h"

using namespace terminal;

bool lit(const uint8_t *frame,unsigned x,unsigned y) {
  return (frame[(y/8)*OLED_WIDTH+x] & (1U<<(y%8)))!=0;
}

int main() {
  static_assert(SCREEN_ROWS==6,"The damaged panel has six usable text rows");
  static_assert(SCREEN_COLUMNS==21,"Keep the existing text width");
  struct GuardedFrame {
    uint8_t before[8],pixels[OLED_FRAME_BYTES],after[8];
  } guarded;
  memset(&guarded,0xA5,sizeof(guarded));
  Screen screen;
  strcpy(screen.line[0],"A");
  strcpy(screen.line[SCREEN_FOOTER],"Z");
  renderScreen(screen,guarded.pixels);
  for (unsigned y=0;y<16;++y) for (unsigned x=0;x<128;++x)
    assert(!lit(guarded.pixels,x,y));
  assert(lit(guarded.pixels,2,16) && !lit(guarded.pixels,0,16));
  for (unsigned x=0;x<5;++x) assert(lit(guarded.pixels,x,19)); // A crossbar.
  for (unsigned x=0;x<5;++x) assert(lit(guarded.pixels,x,56)); // Footer Z.
  assert(lit(guarded.pixels,0,62));
  for (unsigned x=0;x<128;++x) assert(!lit(guarded.pixels,x,63));

  // Fill every character position, including the last column of the footer.
  // Deliberately omit a terminator to exercise the renderer's column bound.
  for (auto &row:screen.line) memset(row,'A',sizeof(row));
  renderScreen(screen,guarded.pixels);
  for (unsigned i=0;i<256;++i) assert(guarded.pixels[i]==0);
  for (unsigned row=0;row<6;++row) assert(lit(guarded.pixels,122,16+row*8));
  for (uint8_t value:guarded.before) assert(value==0xA5);
  for (uint8_t value:guarded.after) assert(value==0xA5);

  // A new blank screen must remove both old text and any stale top-band data.
  memset(guarded.pixels,0xFF,sizeof(guarded.pixels));
  renderScreen(Screen(),guarded.pixels);
  for (uint8_t value:guarded.pixels) assert(value==0);
}
