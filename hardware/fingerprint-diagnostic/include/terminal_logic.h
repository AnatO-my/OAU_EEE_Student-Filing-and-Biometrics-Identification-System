#pragma once

#include <stdint.h>
#include <stdio.h>
#include <string.h>

namespace terminal {

// One debounced edge per press. A held key at startup or across an action
// boundary must be released before it can initiate another action.
class Button {
  bool initialized_ = false, raw_ = false, down_ = false;
  bool armed_ = false, active_ = false, pending_ = false;
  uint32_t changed_ = 0, pressed_ = 0;
public:
  void sample(bool down, uint32_t now) {
    if (!initialized_) {
      initialized_ = true; raw_ = down_ = down; armed_ = !down; changed_ = now;
    }
    if (down != raw_) { raw_ = down; changed_ = now; }
    if (raw_ != down_ && static_cast<uint32_t>(now - changed_) >= 30) {
      down_ = raw_;
      if (down_) {
        if (armed_) { pending_ = active_ = true; pressed_ = now; }
        armed_ = false;
      } else { armed_ = true; active_ = false; }
    }
    if (!down_ && !raw_) armed_ = true;
  }
  bool take() { const bool p = pending_; pending_ = false; return p; }
  bool down() const { return down_; }
  bool rawDown() const { return raw_; }
  bool active() const { return active_; }
  uint32_t held(uint32_t now) const { return now - pressed_; }
  void suppress() { pending_ = active_ = armed_ = false; }
};

struct DateTime {
  uint16_t year = 2026;
  uint8_t month = 1, day = 1, hour = 0, minute = 0, second = 0;
};
inline uint8_t daysIn(uint16_t year, uint8_t month) {
  if (month == 2) return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) ? 29 : 28;
  return month == 4 || month == 6 || month == 9 || month == 11 ? 30 : 31;
}
inline bool valid(const DateTime &t) {
  return t.year >= 2000 && t.year <= 2099 && t.month >= 1 && t.month <= 12 &&
      t.day >= 1 && t.day <= daysIn(t.year, t.month) && t.hour < 24 &&
      t.minute < 60 && t.second < 60;
}
inline bool bcd(uint8_t n) { return (n & 15) < 10 && (n >> 4) < 10; }
inline uint8_t fromBcd(uint8_t n) { return (n >> 4) * 10 + (n & 15); }
inline uint8_t toBcd(uint8_t n) { return ((n / 10) << 4) | (n % 10); }
inline bool decodeClock(const uint8_t *r, DateTime &t) {
  if ((r[0] & 0x80) || (r[1] & 0x80) || (r[2] & 0x80) ||
      (r[3] < 1 || r[3] > 7) || (r[4] & 0xC0) || (r[5] & 0xE0)) return false;
  uint8_t hour = r[2] & ((r[2] & 0x40) ? 0x1F : 0x3F);
  if (!bcd(r[0]) || !bcd(r[1]) || !bcd(hour) || !bcd(r[4]) ||
      !bcd(r[5]) || !bcd(r[6])) return false;
  DateTime candidate;
  candidate.year = 2000 + fromBcd(r[6]); candidate.month = fromBcd(r[5]);
  candidate.day = fromBcd(r[4]); candidate.minute = fromBcd(r[1]);
  candidate.second = fromBcd(r[0]); candidate.hour = fromBcd(hour);
  if (r[2] & 0x40) {
    if (candidate.hour < 1 || candidate.hour > 12) return false;
    candidate.hour = candidate.hour % 12 + ((r[2] & 0x20) ? 12 : 0);
  }
  if (!valid(candidate)) return false;
  t = candidate; return true;
}
inline void encodeClock(const DateTime &t, uint8_t *r) {
  // Day of week: Sunday=1. DS1307 increments this independently of the date.
  static const int offsets[] = {0,3,2,5,0,3,5,1,4,6,2,4};
  int y = t.year - (t.month < 3);
  const int weekday = (y + y/4 - y/100 + y/400 + offsets[t.month-1] + t.day) % 7 + 1;
  r[0] = toBcd(t.second); r[1] = toBcd(t.minute); r[2] = toBcd(t.hour);
  r[3] = weekday; r[4] = toBcd(t.day); r[5] = toBcd(t.month);
  r[6] = toBcd(t.year - 2000);
}
inline uint32_t dateKey(const DateTime &t) { return t.year*10000UL + t.month*100UL + t.day; }
inline uint32_t secondsSince2000(const DateTime &t) {
  uint32_t days=0;
  for (uint16_t y=2000;y<t.year;++y) days+=y%4==0?366:365;
  for (uint8_t m=1;m<t.month;++m) days+=daysIn(t.year,m);
  return ((days+t.day-1)*24+t.hour)*3600UL+t.minute*60UL+t.second;
}
inline void stamp(const DateTime &t, char *out, size_t size) {
  snprintf(out, size, "%04u-%02u-%02uT%02u:%02u:%02u", t.year, t.month, t.day,
      t.hour, t.minute, t.second);
}

enum class LogResult { Saved, Already, Unavailable, Corrupt, Full, WriteFailed };
constexpr const char *LOG_HEADER = "event_uuid,device_uuid,local_datetime,slot,template_sha256,raw_score\n";
constexpr size_t LOG_LINE_BYTES = 192;
inline bool hexString(const char *s, size_t length) {
  if (strlen(s) != length) return false;
  for (size_t i = 0; i < length; ++i)
    if (!(s[i] >= '0' && s[i] <= '9') && !(s[i] >= 'a' && s[i] <= 'f')) return false;
  return true;
}
inline bool uuid(const char *s) {
  if (strlen(s) != 36) return false;
  for (size_t i = 0; i < 36; ++i) {
    if (i == 8 || i == 13 || i == 18 || i == 23) { if (s[i] != '-') return false; }
    else if (!(s[i] >= '0' && s[i] <= '9') && !(s[i] >= 'a' && s[i] <= 'f')) return false;
  }
  return true;
}
struct LogRow { DateTime time; char hash[65] = {}; uint16_t slot = 0, score = 0; };
inline bool parseRow(const char *line, LogRow &row) {
  char event[37] = {}, device[37] = {}, timestamp[20] = {}, hash[65] = {};
  unsigned slot = 0, score = 0, y=0,m=0,d=0,h=0,n=0,s=0; int end = 0, timeEnd = 0;
  if (sscanf(line, "%36[^,],%36[^,],%19[^,],%u,%64[^,],%u%n",
      event, device, timestamp, &slot, hash, &score, &end) != 6 ||
      line[end] != '\0' || !uuid(event) || !uuid(device) || !hexString(hash,64) ||
      slot > 65535 || score > 65535 ||
      sscanf(timestamp,"%4u-%2u-%2uT%2u:%2u:%2u%n",&y,&m,&d,&h,&n,&s,&timeEnd) != 6 ||
      timeEnd != 19 || y > 2099 || m > 12 || d > 31 || h > 23 || n > 59 || s > 59) return false;
  DateTime t; t.year=y; t.month=m; t.day=d; t.hour=h; t.minute=n; t.second=s;
  if (!valid(t)) return false;
  row.time=t; row.slot=slot; row.score=score; memcpy(row.hash,hash,sizeof(hash)); return true;
}

} // namespace terminal
