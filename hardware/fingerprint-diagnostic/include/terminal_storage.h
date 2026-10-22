#pragma once
#include "terminal_logic.h"

namespace terminal {
// File adapter needs available()/read(). Stream records rather than loading
// the entire history into ESP32 RAM. A torn/invalid record blocks new appends.
template <typename File> bool logLine(File &file, char *line, size_t size, void (*idle)()=nullptr) {
  size_t n = 0;
  while (file.available()) {
    const int c = file.read();
    if (c < 0) return false;
    if (c == '\n') { line[n] = 0; return true; }
    if (n + 1 >= size) return false;
    line[n++] = static_cast<char>(c);
    if (idle && n%64==0) idle();
  }
  return false;
}
template <typename File> bool inspectLog(File &file, uint32_t date,
    const char *hash, bool &duplicate, uint32_t &today, void (*idle)()=nullptr) {
  duplicate = false; today = 0;
  char line[LOG_LINE_BYTES] = {};
  if (!logLine(file, line, sizeof(line),idle)) return false;
  if (strlen(line) != strlen(LOG_HEADER)-1 ||
      strncmp(line, LOG_HEADER, strlen(line)) != 0) return false;
  while (file.available()) {
    LogRow row;
    if (!logLine(file,line,sizeof(line),idle) || !parseRow(line,row)) return false;
    if (dateKey(row.time) == date) {
      ++today;
      if (hash && strcmp(hash,row.hash) == 0) duplicate = true;
    }
  }
  return true;
}
} // namespace terminal
