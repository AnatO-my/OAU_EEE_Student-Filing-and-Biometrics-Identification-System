// Display-only integrity check. No scanner, filesystem, Wi-Fi or RTC operations.
#include <Arduino.h>
#include <Wire.h>
#include "terminal_config.h"
#include "oled_pages.h"
#include "oled_integrity_patterns.h"

namespace {
uint8_t frame[oled_integrity::WIDTH*oled_integrity::PAGES];
terminal::OledPages<TwoWire> *display=nullptr;
bool ready=false, paused=false;
unsigned stepNumber=0;
uint32_t stepAt=0, drawnAt=0, pausedAt=0;

void instructions() {
  Serial.println("Commands: p=pause/resume, n=next pattern/row, t=hold text grid, r=restart, h=help.");
  Serial.println("Text rows 1-2 occupy pixel y=0..15. Compare them with rows 3-8 (y=16..63).");
  Serial.println("Check the physical panel; successful I2C writes do not prove pixel integrity.");
  Serial.println("Report the affected text rows or pixel y positions, and the pattern name.");
}

bool draw() {
  const auto current=oled_integrity::step(stepNumber);
  oled_integrity::render(frame,current);
  for (uint8_t page=0;page<oled_integrity::PAGES;++page) {
    if (!display->page(page,frame+page*oled_integrity::WIDTH)) {
      Serial.printf("FAIL: I2C write on page %u (text row %u). Press EN/RESET to retry.\n",page,page+1);
      ready=false;
      return false;
    }
  }
  drawnAt=millis();
  return true;
}

void announce() {
  const auto current=oled_integrity::step(stepNumber);
  static const char *names[]={
    "NUMBERED TEXT: same digit sample on rows 1-8",
    "ALL WHITE: inspect missing/dark lines and pixels",
    "ALL BLACK: inspect stuck lit pixels or noise",
    "HORIZONTAL STRIPES: even pixel rows lit",
    "HORIZONTAL STRIPES INVERSE: odd pixel rows lit",
    "VERTICAL STRIPES: even columns lit",
    "VERTICAL STRIPES INVERSE: odd columns lit",
    "CHECKERBOARD A: 8x8 squares",
    "CHECKERBOARD B: inverse 8x8 squares",
    "TOP ONLY: y=0..15 white; y=16..63 black",
    "LOWER ONLY: y=0..15 black; y=16..63 white"};
  Serial.printf("STEP %u/%u: ",stepNumber+1,oled_integrity::STEP_COUNT);
  if (stepNumber<oled_integrity::STATIC_STEPS) Serial.println(names[stepNumber]);
  else if (current.pattern==oled_integrity::Pattern::Band)
    Serial.printf("BAND: text row %u, y=%u..%u white; all others black.\n",
      current.index+1,current.index*8,current.index*8+7);
  else Serial.printf("SINGLE PIXEL ROW: y=%u white; all others black.\n",current.index);
  if (paused) Serial.println("PAUSED: p resumes; n advances one step while paused.");
}

void selectStep(unsigned number) {
  stepNumber=number%oled_integrity::STEP_COUNT;
  stepAt=pausedAt=millis();
  announce();
  draw();
}
} // namespace

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.printf("\nOLED integrity test: %s 128x64, SDA=%d SCL=%d, 100kHz.\n",
    TERMINAL_OLED_SH1106?"SH1106":"SSD1306",TERMINAL_SDA_PIN,TERMINAL_SCL_PIN);
  if (!Wire.begin(TERMINAL_SDA_PIN,TERMINAL_SCL_PIN,100000)) {
    Serial.println("FAIL: could not start I2C.");
    return;
  }
  Wire.setTimeOut(50);
  uint8_t address=0;
  for (const uint8_t candidate:{uint8_t(0x3C),uint8_t(0x3D)}) {
    Wire.beginTransmission(candidate);
    const bool ack=Wire.endTransmission()==0;
    Serial.printf("OLED address 0x%02X: %s\n",candidate,ack?"ACK":"NO ACK");
    if (ack && !address) address=candidate;
  }
  if (!address) {
    Serial.println("FAIL: no OLED at 0x3C/0x3D. Check power, GND, SDA and SCL.");
    return;
  }
  static terminal::OledPages<TwoWire> panel(Wire,address,TERMINAL_OLED_SH1106!=0);
  display=&panel;
  if (!display->begin()) {
    Serial.println("FAIL: display initialization failed. Press EN/RESET to retry.");
    return;
  }
  ready=true;
  Serial.println("Starting a repeating sequence of approximately one minute.");
  instructions();
  selectStep(0);
}

void loop() {
  if (!ready) { delay(10); return; }
  // Bound each pass so serial input cannot starve the display refresh.
  for (unsigned i=0;i<16 && ready && Serial.available()>0;++i) {
    char key=static_cast<char>(Serial.read());
    if (key>='A' && key<='Z') key+=32;
    switch (key) {
      case 'p':
        if (paused) { stepAt+=millis()-pausedAt; paused=false; }
        else { paused=true; pausedAt=millis(); }
        Serial.println(paused?"PAUSED":"RUNNING");
        break;
      case 'n': selectStep(stepNumber+1); break;
      case 't': paused=true; selectStep(0); break;
      case 'r': paused=false; selectStep(0); break;
      case 'h': instructions(); break;
      default: break; // Serial monitors may append CR/LF.
    }
  }
  if (!ready) return;
  if (!paused && millis()-stepAt>=oled_integrity::step(stepNumber).holdMs)
    selectStep(stepNumber+1);
  // Re-send all eight pages to check for corruption that returns while held.
  if (ready && millis()-drawnAt>=250) draw();
  delay(2);
}
