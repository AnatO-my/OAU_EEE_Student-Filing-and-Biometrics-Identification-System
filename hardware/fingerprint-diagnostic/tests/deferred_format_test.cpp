#include <assert.h>
#include <map>
#include <string>
#include <vector>
#include "deferred_format.h"

struct Storage {
  std::map<std::string,std::vector<uint8_t>> files;
  bool partial=false,corrupt=false,renameFails=false,finalCorrupt=false;
  bool exists(const char *path) { return files.count(path); }
  bool writeNew(const char *path,const uint8_t *p,size_t n) {
    assert(!exists(path));
    files[path]=std::vector<uint8_t>(p,p+(partial?n-1:n));
    if(corrupt) files[path][0]^=1;
    return !partial;
  }
  bool equals(const char *path,const uint8_t *p,size_t n) {
    return files[path]==std::vector<uint8_t>(p,p+n);
  }
  bool renameNew(const char *from,const char *to) {
    assert(!exists(to));
    if(renameFails) return false;
    files[to]=files[from]; files.erase(from);
    if(finalCorrupt) files[to][0]^=1;
    return true;
  }
};

int main() {
  const char *id="550e8400-e29b-41d4-a716-446655440000";
  uint8_t uuid[16]; char text[37];
  assert(deferred::uuidBytes(id,uuid)); deferred::uuidText(uuid,text); assert(!strcmp(id,text));
  assert(!deferred::uuidBytes("00000000-0000-0000-0000-000000000000",uuid));
  assert(!deferred::uuidBytes("../../../../outside",uuid));
  assert(!deferred::uuidBytes("550e8400_e29b-41d4-a716-446655440000",uuid));
  uint8_t header[deferred::HEADER_BYTES]={}; memcpy(header,"FPB1",4);
  for(unsigned i=4;i<68;i+=16) assert(deferred::uuidBytes(id,header+i));
  memcpy(header+68,"as608-unit-1",12);
  deferred::put16(header+148,150); deferred::put16(header+150,3);
  deferred::put16(header+152,128); deferred::put32(header+156,0xFFFFFFFF);
  deferred::seal(header,sizeof(header)); assert(deferred::headerValid(header,sizeof(header)));
  header[80]='!'; deferred::seal(header,sizeof(header)); assert(!deferred::headerValid(header,sizeof(header)));
  header[80]=0; deferred::seal(header,sizeof(header));
  assert(!deferred::headerValid(header,sizeof(header)-1));
  header[20]^=1; assert(!deferred::headerValid(header,sizeof(header))); header[20]^=1;

  uint8_t event[deferred::MAX_EVENT_BYTES]={}; memcpy(event,"FPE1",4);
  assert(deferred::uuidBytes(id,event+4)); assert(deferred::uuidBytes(id,event+20));
  deferred::put64(event+36,0x100000010ULL); deferred::put16(event+44,2048);
  memset(event+46,0xA5,2048); deferred::seal(event,sizeof(event));
  assert(deferred::eventValid(event,sizeof(event)));
  event[60]^=1; assert(!deferred::eventValid(event,sizeof(event))); event[60]^=1;
  deferred::put16(event+44,2047); deferred::seal(event,sizeof(event));
  assert(!deferred::eventValid(event,sizeof(event)));

  Storage good;
  assert(deferred::commit(good,"pending","saved",header,sizeof(header)));
  const auto original=good.files;
  assert(!deferred::commit(good,"pending","saved",event,sizeof(event)) && good.files==original);
  Storage partial; partial.partial=true;
  assert(!deferred::commit(partial,"pending","saved",header,sizeof(header)));
  assert(partial.exists("pending") && !partial.exists("saved"));
  partial.partial=false;
  assert(!deferred::commit(partial,"pending","saved",header,sizeof(header)));
  Storage corrupt; corrupt.corrupt=true;
  assert(!deferred::commit(corrupt,"pending","saved",header,sizeof(header)) && !corrupt.exists("saved"));
  Storage rename; rename.renameFails=true;
  assert(!deferred::commit(rename,"pending","saved",header,sizeof(header)) && rename.exists("pending"));
  Storage final; final.finalCorrupt=true;
  assert(!deferred::commit(final,"pending","saved",header,sizeof(header)));
  // Synthetic fixture for the Python cross-language wire decoder; no biometrics.
  for(uint8_t c:header) printf("%02X",c);
  printf("\n");
  return 0;
}
