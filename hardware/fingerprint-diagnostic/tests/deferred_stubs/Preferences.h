#pragma once
#include <string>
#include <map>
using String=std::string;
class Preferences {
  std::string scope_;
  static std::map<std::string,std::string> &values() {
    static std::map<std::string,std::string> saved; return saved;
  }
public:
  bool begin(const char *scope,bool) { scope_=scope; return true; }
  String getString(const char *key,const char *fallback) {
    const auto found=values().find(scope_+":"+key);
    if(found!=values().end()) return found->second;
    return !strcmp(key,"device")?"550e8400-e29b-41d4-a716-446655440000":fallback;
  }
  size_t putString(const char *key,const char *value) { values()[scope_+":"+key]=value; return strlen(value); }
  size_t getBytesLength(const char *key) { return values()[scope_+":"+key].size(); }
  size_t getBytes(const char *key,void *out,size_t n) {
    const auto &value=values()[scope_+":"+key]; if(n<value.size()) return 0;
    memcpy(out,value.data(),value.size()); return value.size();
  }
  size_t putBytes(const char *key,const void *data,size_t n) {
    values()[scope_+":"+key]=std::string(static_cast<const char *>(data),n); return n;
  }
  bool isKey(const char *key) { return values().count(scope_+":"+key)!=0; }
  bool remove(const char *key) { return values().erase(scope_+":"+key)!=0; }
  void end() {}
};
