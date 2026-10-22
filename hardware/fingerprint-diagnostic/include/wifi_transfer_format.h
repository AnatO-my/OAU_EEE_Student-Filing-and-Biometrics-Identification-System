#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>

namespace wireless {
constexpr size_t MAX_CONFIG_BYTES=4096;
constexpr int64_t MIN_CLOCK=1704067200LL,MAX_CLOCK=2145916799LL;
inline bool civilEpoch(unsigned year,unsigned month,unsigned day,unsigned hour,unsigned minute,
    unsigned second,int offsetSeconds,int64_t &epoch) {
  if(year<2024 || year>2037 || !month || month>12 || !day || hour>23 || minute>59 || second>59 ||
      offsetSeconds < -50400 || offsetSeconds > 50400) return false;
  const unsigned lengths[]={31,28,31,30,31,30,31,31,30,31,30,31};
  const bool leap=year%4==0 && (year%100!=0 || year%400==0);
  if(day>lengths[month-1]+(month==2 && leap?1U:0U)) return false;
  int64_t days=0;
  for(unsigned y=1970;y<year;++y) days+=365+(y%4==0 && (y%100!=0 || y%400==0)?1:0);
  for(unsigned m=1;m<month;++m) days+=lengths[m-1]+(m==2 && leap?1:0);
  epoch=((days+day-1)*24+hour)*3600+minute*60+second-offsetSeconds;
  return epoch>=MIN_CLOCK && epoch<=MAX_CLOCK;
}
struct Config {
  uint16_t port=0;
  const char *ssid=nullptr,*password=nullptr,*host=nullptr,*token=nullptr,*fingerprint=nullptr,*ca=nullptr;
};
inline bool hex64(const char *value) {
  if(strlen(value)!=64) return false;
  for(unsigned i=0;i<64;++i) if(!((value[i]>='0'&&value[i]<='9')||(value[i]>='a'&&value[i]<='f'))) return false;
  return true;
}
inline bool printable(const char *value,size_t low,size_t high) {
  const size_t n=strlen(value); if(n<low || n>high) return false;
  for(size_t i=0;i<n;++i) if(value[i]<32 || value[i]>126) return false;
  return true;
}
// A single sealed NVS blob avoids partially updated independent credentials.
inline bool parseConfig(char *bytes,size_t n,Config &out) {
  if(n<12 || n>MAX_CONFIG_BYTES || memcmp(bytes,"FPW1",4)) return false;
  Config c; c.port=(static_cast<uint8_t>(bytes[4])<<8)|static_cast<uint8_t>(bytes[5]);
  const char **fields[]={&c.ssid,&c.password,&c.host,&c.token,&c.fingerprint,&c.ca};
  size_t offset=6;
  for(auto field:fields) {
    if(offset>=n) return false;
    *field=bytes+offset;
    const auto end=static_cast<const char *>(memchr(bytes+offset,0,n-offset));
    if(!end) return false;
    offset=static_cast<size_t>(end-bytes)+1;
  }
  if(offset!=n || !c.port || !printable(c.ssid,1,32) || !printable(c.password,8,63) ||
      !printable(c.host,1,253) || !hex64(c.token) || !hex64(c.fingerprint) ||
      strlen(c.ca)>3000 || strncmp(c.ca,"-----BEGIN CERTIFICATE-----\n",28) ||
      !strstr(c.ca,"\n-----END CERTIFICATE-----\n")) return false;
  for(const char *p=c.host;*p;++p)
    if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='.'||*p=='-')) return false;
  out=c; return true;
}
inline bool validReceipt(const char *line,const char *type,const char *id,const char *wire,unsigned count) {
  char gotType[12]={},gotId[40]={},gotWire[65]={},saved[65]={}; unsigned gotCount=0; int end=0;
  return sscanf(line,"FPWRECEIPT 1 %11s %39s %64s %64s %u%n",gotType,gotId,gotWire,saved,&gotCount,&end)==5 &&
    line[end]==0 && !strcmp(type,gotType) && !strcmp(id,gotId) && !strcmp(wire,gotWire) &&
    hex64(gotWire) && hex64(saved) && count==gotCount;
}
} // namespace wireless
