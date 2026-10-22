#pragma once
inline void esp_fill_random(void *p,size_t n) {
  static uint8_t counter=0;
  memset(p,++counter,n); // deterministic synthetic UUIDs, never production entropy.
}
