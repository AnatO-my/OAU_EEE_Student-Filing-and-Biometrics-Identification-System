#pragma once

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "portable_template.h"

// Explicit big-endian wire layout; never serialize C++ struct padding.
namespace deferred {
constexpr size_t HEADER_BYTES=164, EVENT_FIXED_BYTES=50;
constexpr size_t MAX_EVENT_BYTES=EVENT_FIXED_BYTES+fingerprint::MAX_TEMPLATE_BYTES;
constexpr unsigned MAX_EVENTS=512;

inline void put16(uint8_t *p,uint16_t n) { p[0]=n>>8; p[1]=n; }
inline void put32(uint8_t *p,uint32_t n) { for(int i=3;i>=0;--i) { p[i]=n; n>>=8; } }
inline void put64(uint8_t *p,uint64_t n) { for(int i=7;i>=0;--i) { p[i]=n; n>>=8; } }
inline bool uuidBytes(const char *text,uint8_t *out) {
  if(strlen(text)!=36) return false;
  size_t used=0; unsigned any=0;
  for(size_t i=0;i<36;) {
    if(i==8 || i==13 || i==18 || i==23) { if(text[i++]!='-') return false; continue; }
    const int hi=fingerprint::hexDigit(text[i++]),lo=fingerprint::hexDigit(text[i++]);
    if(hi<0 || lo<0) return false;
    out[used++]=(hi<<4)|lo; any|=out[used-1];
  }
  return used==16 && any;
}
inline void uuidText(const uint8_t *p,char *out) {
  static const char hex[]="0123456789abcdef";
  size_t used=0;
  for(size_t i=0;i<16;++i) {
    if(i==4 || i==6 || i==8 || i==10) out[used++]='-';
    out[used++]=hex[p[i]>>4]; out[used++]=hex[p[i]&15];
  }
  out[used]=0;
}
inline bool groupValid(const char *group) {
  const size_t n=strlen(group);
  if(!n || n>79) return false;
  for(size_t i=0;i<n;++i) {
    const char c=group[i];
    if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='_'||c=='-'||c=='.')) return false;
  }
  return true;
}
inline void seal(uint8_t *bytes,size_t n) { put32(bytes+n-4,fingerprint::crc32(bytes,n-4)); }
inline bool sealed(const uint8_t *bytes,size_t n) {
  return n>=4 && fingerprint::read32(bytes+n-4)==fingerprint::crc32(bytes,n-4);
}
inline bool headerValid(const uint8_t *p,size_t n) {
  if(n!=HEADER_BYTES || memcmp(p,"FPB1",4) || !sealed(p,n)) return false;
  for(unsigned start=4;start<68;start+=16) {
    unsigned any=0; for(unsigned i=0;i<16;++i) any|=p[start+i];
    if(!any) return false;
  }
  if(!memchr(p+68,0,80) || !groupValid(reinterpret_cast<const char *>(p+68))) return false;
  const size_t length=strlen(reinterpret_cast<const char *>(p+68));
  for(size_t i=length;i<80;++i) if(p[68+i]) return false;
  const uint16_t packet=fingerprint::read16(p+152);
  return fingerprint::read16(p+148)>0 && (packet==32||packet==64||packet==128||packet==256);
}
inline bool eventValid(const uint8_t *p,size_t n) {
  if(n<EVENT_FIXED_BYTES+1 || n>MAX_EVENT_BYTES || memcmp(p,"FPE1",4) || !sealed(p,n) ||
      fingerprint::read16(p+44)!=n-EVENT_FIXED_BYTES) return false;
  for(unsigned start=4;start<36;start+=16) {
    unsigned any=0; for(unsigned i=0;i<16;++i) any|=p[start+i];
    if(!any) return false;
  }
  return true;
}

// A staged write is never reported saved until close, readback, rename and
// final readback succeed. An interrupted staging file blocks further capture;
// recovery/download preserves evidence rather than deleting it automatically.
template<class Storage>
bool commit(Storage &storage,const char *temporary,const char *target,
            const uint8_t *bytes,size_t size) {
  if(storage.exists(temporary)||storage.exists(target)) return false;
  if(!storage.writeNew(temporary,bytes,size) || !storage.equals(temporary,bytes,size)) return false;
  return storage.renameNew(temporary,target) && storage.equals(target,bytes,size);
}
}
