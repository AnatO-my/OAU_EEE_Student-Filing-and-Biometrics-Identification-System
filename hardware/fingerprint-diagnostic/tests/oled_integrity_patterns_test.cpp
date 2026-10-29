#include <assert.h>
#include <string.h>
#include "oled_integrity_patterns.h"

using namespace oled_integrity;

bool pixel(const uint8_t *frame,unsigned x,unsigned y) {
  return (frame[(y/8)*WIDTH+x] & (1U<<(y%8)))!=0;
}

int main() {
  uint8_t frame[WIDTH*PAGES],inverse[WIDTH*PAGES];
  render(frame,{Pattern::Top,0,0});
  for (unsigned y=0;y<HEIGHT;++y) for (unsigned x=0;x<WIDTH;++x)
    assert(pixel(frame,x,y)==(y<TOP_PIXELS));
  render(inverse,{Pattern::Lower,0,0});
  for (unsigned i=0;i<sizeof(frame);++i) assert((frame[i]^inverse[i])==0xFF);

  // Every physical row must light exactly once, including each page boundary.
  uint8_t visited[WIDTH*PAGES]={};
  for (unsigned y=0;y<HEIGHT;++y) {
    memset(frame,0xFF,sizeof(frame));
    render(frame,step(STATIC_STEPS+PAGES+y));
    for (unsigned other=0;other<HEIGHT;++other) for (unsigned x=0;x<WIDTH;++x)
      assert(pixel(frame,x,other)==(other==y));
    for (unsigned i=0;i<sizeof(frame);++i) { assert(!(visited[i]&frame[i])); visited[i]|=frame[i]; }
  }
  for (uint8_t value:visited) assert(value==0xFF);

  for (unsigned page=0;page<PAGES;++page) {
    render(frame,step(STATIC_STEPS+page));
    for (unsigned y=0;y<HEIGHT;++y) for (unsigned x=0;x<WIDTH;++x)
      assert(pixel(frame,x,y)==(y/8==page));
  }
  render(frame,{Pattern::Horizontal,0,0});
  render(inverse,{Pattern::HorizontalInverse,0,0});
  for (unsigned y=0;y<HEIGHT;++y) for (unsigned x=0;x<WIDTH;++x)
    assert(pixel(frame,x,y)==(y%2==0));
  for (unsigned i=0;i<sizeof(frame);++i) assert((frame[i]^inverse[i])==0xFF);
  render(frame,{Pattern::Vertical,0,0});
  render(inverse,{Pattern::VerticalInverse,0,0});
  for (unsigned y=0;y<HEIGHT;++y) for (unsigned x=0;x<WIDTH;++x)
    assert(pixel(frame,x,y)==(x%2==0));
  for (unsigned i=0;i<sizeof(frame);++i) assert((frame[i]^inverse[i])==0xFF);
  render(frame,{Pattern::Checker,0,0});
  render(inverse,{Pattern::CheckerInverse,0,0});
  for (unsigned y=0;y<HEIGHT;++y) for (unsigned x=0;x<WIDTH;++x)
    assert(pixel(frame,x,y)==((y/8+x/8)%2==0));
  for (unsigned i=0;i<sizeof(frame);++i) assert((frame[i]^inverse[i])==0xFF);

  render(frame,{Pattern::White,0,0});
  for (uint8_t value:frame) assert(value==0xFF);
  render(frame,{Pattern::Black,0,0});
  for (uint8_t value:frame) assert(value==0);
  render(frame,step(0));
  for (unsigned page=0;page<PAGES;++page) {
    assert(frame[page*WIDTH+8]==0x36);
    // Apart from row labels, all text rows have the same seven-pixel-high sample.
    assert(memcmp(frame+18,frame+page*WIDTH+18,WIDTH-18)==0);
    bool lit=false;
    for (unsigned x=18;x<WIDTH;++x) { lit|=frame[page*WIDTH+x]!=0; assert(!(frame[page*WIDTH+x]&0x80)); }
    assert(lit);
  }
  assert(step(STEP_COUNT).pattern==Pattern::Text);
  assert(step(STATIC_STEPS+PAGES+15).holdMs>step(STATIC_STEPS+PAGES+16).holdMs);
}
