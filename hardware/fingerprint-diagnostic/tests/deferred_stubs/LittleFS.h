#pragma once
#include <algorithm>
#include <map>
#include <set>
#include <string>
#include <vector>
#include <string.h>

struct FakeFlash {
  std::map<std::string,std::vector<uint8_t>> files;
  std::set<std::string> dirs;
  bool mountOK=true,shortWrite=false,renameFail=false,full=false;
  bool rawErased=true,rawReadFails=false;
  unsigned formats=0;
};
extern FakeFlash fakeFlash;
class File {
  std::string path_;
  size_t position_=0,index_=0;
  bool valid_=false,dir_=false;
  std::vector<std::string> entries_;
public:
  File() {}
  File(std::string p,bool directory):path_(p),valid_(true),dir_(directory) {
    if(dir_) {
      const std::string prefix=path_+"/";
      for(const auto &d:fakeFlash.dirs) if(d.find(prefix)==0 && d.find('/',prefix.size())==std::string::npos) entries_.push_back(d);
      for(const auto &f:fakeFlash.files) if(f.first.find(prefix)==0 && f.first.find('/',prefix.size())==std::string::npos) entries_.push_back(f.first);
    }
  }
  explicit operator bool() const { return valid_; }
  bool isDirectory() const { return dir_; }
  const char *name() const { return path_.c_str(); }
  size_t size() { return fakeFlash.files[path_].size(); }
  size_t read(uint8_t *out,size_t n) {
    auto &bytes=fakeFlash.files[path_]; const size_t count=std::min(n,bytes.size()-position_);
    memcpy(out,bytes.data()+position_,count); position_+=count; return count;
  }
  int available() { return valid_ && position_<size(); }
  int read() { return available()?fakeFlash.files[path_][position_++]:-1; }
  bool seek(size_t position) { if(position>size()) return false; position_=position; return true; }
  size_t write(const uint8_t *p,size_t n) {
    if(fakeFlash.shortWrite && n) --n;
    auto &bytes=fakeFlash.files[path_]; bytes.insert(bytes.end(),p,p+n); return n;
  }
  File openNextFile() {
    if(index_==entries_.size()) return File();
    const std::string name=entries_[index_++]; return File(name,fakeFlash.dirs.count(name));
  }
  void flush() {}
  void close() { valid_=false; }
};
struct LittleFileSystem {
  bool begin(bool format) { assert(!format); return fakeFlash.mountOK; }
  bool format() { ++fakeFlash.formats; fakeFlash.mountOK=true; return true; }
  bool exists(const char *p) { return fakeFlash.files.count(p)||fakeFlash.dirs.count(p); }
  bool mkdir(const char *p) {
    std::string path=p; if(path.back()=='/') return false;
    return fakeFlash.dirs.insert(path).second;
  }
  File open(const char *p,const char *mode) {
    std::string path=p; if(path.size()>1 && path.back()=='/') path.pop_back();
    if(fakeFlash.dirs.count(path)) return File(path,true);
    if(!strcmp(mode,"w")) { fakeFlash.files[path].clear(); return File(path,false); }
    return fakeFlash.files.count(path)?File(path,false):File();
  }
  bool rename(const char *from,const char *to) {
    if(fakeFlash.renameFail || exists(to) || !fakeFlash.files.count(from)) return false;
    fakeFlash.files[to]=fakeFlash.files[from]; fakeFlash.files.erase(from); return true;
  }
  size_t totalBytes() const { return 1500000; }
  size_t usedBytes() const {
    if(fakeFlash.full) return totalBytes();
    size_t n=0; for(const auto &f:fakeFlash.files) n+=f.second.size(); return n;
  }
};
extern LittleFileSystem LittleFS;
