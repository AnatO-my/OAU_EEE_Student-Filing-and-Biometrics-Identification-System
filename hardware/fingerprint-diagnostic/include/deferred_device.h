#pragma once

#include <LittleFS.h>
#include <Preferences.h>
#include <esp_system.h>
#include <esp_timer.h>
#include <esp_partition.h>
#include <mbedtls/sha256.h>
#include "deferred_format.h"
#include "capture_control.h"

namespace deferred {
// Transport-independent textual frames; USB and TLS carry identical exports.
class BatchSink {
public:
  virtual ~BatchSink() {}
  virtual bool line(const char *text)=0;
};
class SerialBatchSink : public BatchSink {
public:
  bool line(const char *text) override { Serial.println(text); return true; }
};
class FlashStorage {
public:
  bool exists(const char *path) { return LittleFS.exists(path); }
  bool writeNew(const char *path,const uint8_t *data,size_t size) {
    if(exists(path)) return false;
    auto f=LittleFS.open(path,"w");
    if(!f) return false;
    const bool ok=f.write(data,size)==size; f.flush(); f.close(); return ok;
  }
  bool equals(const char *path,const uint8_t *data,size_t size) {
    auto f=LittleFS.open(path,"r");
    if(!f || f.size()!=size) return false;
    uint8_t chunk[64]; size_t offset=0;
    while(offset<size) {
      const size_t count=size-offset<sizeof(chunk)?size-offset:sizeof(chunk);
      if(f.read(chunk,count)!=count || memcmp(chunk,data+offset,count)) return false;
      offset+=count;
    }
    return true;
  }
  bool renameNew(const char *from,const char *to) {
    return !exists(to) && LittleFS.rename(from,to);
  }
};

class Device : public terminal::CaptureControl {
  FlashStorage storage_;
  bool mounted_=false,armed_=false,needLift_=true;
  char device_[37]={},active_[37]={};
  char class_[37]={},message_[80]={};
  terminal::CaptureEvent event_=terminal::CaptureEvent::None;
  uint8_t boot_[16]={},header_[HEADER_BYTES]={};
  unsigned next_=0;
  uint32_t pollAt_=0;
  bool (*wireless_)(const char *,const char *)=nullptr;
  static constexpr size_t RESERVE=32768;

  void emit(terminal::CaptureEvent event,const char *message) {
    event_=event; snprintf(message_,sizeof(message_),"%s",message);
  }
  void remember() {
    Preferences prefs;
    if(prefs.begin("fp-deferred",false)) { prefs.putString("selected",active_); prefs.end(); }
  }
  bool select(const char *id) {
    unsigned count=0; bool pending=false;
    if(!load(id,count,pending)) return false;
    uint8_t expected[16]; uuidBytes(device_,expected);
    if(memcmp(expected,header_+4,16)) return false;
    strcpy(active_,id); uuidText(header_+36,class_); next_=count; remember();
    return true;
  }

  static void randomUuid(uint8_t *p) {
    esp_fill_random(p,16); p[6]=(p[6]&15)|0x40; p[8]=(p[8]&63)|0x80;
  }
  static bool canonical(const char *text,char *out) {
    uint8_t b[16]; if(!uuidBytes(text,b)) return false;
    uuidText(b,out); return true;
  }
  static void path(char *out,const char *id,const char *name) {
    if(*name) snprintf(out,96,"/probes/%s/%s",id,name);
    else snprintf(out,96,"/probes/%s",id);
  }
  static void eventPath(char *out,const char *id,unsigned index) {
    char name[16]; snprintf(name,sizeof(name),"%06u",index); path(out,id,name);
  }
  static bool readFile(const char *pathName,uint8_t *out,size_t capacity,size_t &n) {
    auto f=LittleFS.open(pathName,"r");
    if(!f || f.isDirectory() || f.size()>capacity) return false;
    n=f.size(); return f.read(out,n)==n;
  }
  static bool eventName(const char *name,unsigned &number) {
    if(strlen(name)!=6) return false;
    number=0;
    for(unsigned i=0;i<6;++i) {
      if(name[i]<'0'||name[i]>'9') return false;
      number=number*10+name[i]-'0';
    }
    return number<MAX_EVENTS;
  }
  bool inventory(const char *id,unsigned &count,bool &pending) {
    char directory[96]; path(directory,id,"");
    auto dir=LittleFS.open(directory,"r");
    if(!dir || !dir.isDirectory()) return false;
    bool seen[MAX_EVENTS]={}; count=0; pending=false;
    auto f=dir.openNextFile();
    while(f) {
      const char *name=f.name(); const char *slash=strrchr(name,'/'); if(slash) name=slash+1;
      if(f.isDirectory()) return false;
      if(!strcmp(name,"pending")) pending=true;
      else if(strcmp(name,"header")) {
        unsigned index;
        if(!eventName(name,index) || seen[index]) return false;
        seen[index]=true; ++count;
      }
      f=dir.openNextFile();
    }
    for(unsigned i=0;i<count;++i) if(!seen[i]) return false;
    return true;
  }
  bool load(const char *id,unsigned &count,bool &pending) {
    char file[96]; path(file,id,"header"); size_t size=0;
    if(!readFile(file,header_,sizeof(header_),size) || !headerValid(header_,size) ||
        !inventory(id,count,pending)) return false;
    char saved[37]; uuidText(header_+20,saved);
    if(strcmp(id,saved)) return false;
    // Fail closed on any committed corruption, including after power loss.
    static uint8_t bytes[MAX_EVENT_BYTES];
    for(unsigned i=0;i<count;++i) {
      eventPath(file,id,i);
      if(!readFile(file,bytes,sizeof(bytes),size) || !eventValid(bytes,size)) {
        memset(bytes,0,sizeof(bytes)); return false;
      }
    }
    memset(bytes,0,sizeof(bytes)); return true;
  }
  bool parametersMatch(const TemplateParameters &p) const {
    return p.capacity==fingerprint::read16(header_+148) && p.security==fingerprint::read16(header_+150) &&
      p.packetBytes==fingerprint::read16(header_+152) && p.systemId==fingerprint::read16(header_+154) &&
      p.address==fingerprint::read32(header_+156);
  }
  bool space() const {
    return LittleFS.totalBytes()>=LittleFS.usedBytes()+RESERVE+MAX_EVENT_BYTES;
  }
  void error(const char *message) {
    armed_=false; emit(terminal::CaptureEvent::Error,message);
    Serial.print("FPBERROR "); Serial.println(message);
  }
  void initializeEmpty() {
    if(mounted_) { error("storage already initialized; no formatting performed"); return; }
    const auto partition=esp_partition_find_first(ESP_PARTITION_TYPE_DATA,ESP_PARTITION_SUBTYPE_DATA_SPIFFS,"spiffs");
    if(!partition || !partition->size) { error("filesystem partition not found"); return; }
    uint8_t chunk[512];
    for(size_t offset=0;offset<partition->size;offset+=sizeof(chunk)) {
      const size_t n=partition->size-offset<sizeof(chunk)?partition->size-offset:sizeof(chunk);
      if(esp_partition_read(partition,offset,chunk,n)!=ESP_OK) { error("raw storage check failed; no formatting performed"); return; }
      for(size_t i=0;i<n;++i) if(chunk[i]!=0xFF) {
        error("partition contains data; preserve it for recovery; no formatting performed"); return;
      }
      delay(1);
    }
    if(!LittleFS.format()) { error("empty storage initialization failed"); return; }
    begin();
    if(!mounted_) { error("initialized storage could not be mounted"); return; }
    Serial.println("FPBINITIALIZED empty partition verified and filesystem created");
  }
  void beginBatch(char **tokens,unsigned count) {
    if(count!=5) { error("begin needs batch, class, commissioned scanner UUID and group"); return; }
    char batch[37],classId[37],scannerId[37];
    if(!canonical(tokens[1],batch)||!canonical(tokens[2],classId)||!canonical(tokens[3],scannerId)||
       !groupValid(tokens[4])) { error("invalid batch metadata"); return; }
    char directory[96]; path(directory,batch,"");
    if(LittleFS.exists(directory)) { error("batch exists; use arm or export"); return; }
    TemplateParameters p;
    if(!authenticated || !readTemplateParameters(p)) { error("scanner unavailable"); return; }
    if(!space()) { error("storage full; pending evidence retained"); return; }
    memset(header_,0,sizeof(header_)); memcpy(header_,"FPB1",4);
    uuidBytes(device_,header_+4); uuidBytes(batch,header_+20);
    uuidBytes(classId,header_+36); uuidBytes(scannerId,header_+52);
    memcpy(header_+68,tokens[4],strlen(tokens[4]));
    put16(header_+148,p.capacity); put16(header_+150,p.security);
    put16(header_+152,p.packetBytes); put16(header_+154,p.systemId); put32(header_+156,p.address);
    seal(header_,sizeof(header_));
    if(!headerValid(header_,sizeof(header_))) { error("invalid generated batch header"); return; }
    if(!LittleFS.mkdir(directory)) { error("batch directory creation failed"); return; }
    char pending[96],target[96]; path(pending,batch,"pending"); path(target,batch,"header");
    if(!commit(storage_,pending,target,header_,sizeof(header_))) { error("header save incomplete; retain files for recovery"); return; }
    strcpy(active_,batch); strcpy(class_,classId); next_=0; remember();
    emit(terminal::CaptureEvent::Prepared,"Class batch prepared");
    Serial.printf("FPBCREATED %s %s\n",batch,device_);
  }
  void arm(const char *id) {
    bool pending=false; unsigned count=0;
    if(!load(id,count,pending)) { error("batch is invalid or committed file is damaged"); return; }
    if(pending) { error("interrupted write; export committed records and retain pending file for recovery"); return; }
    uint8_t expected[16]; uuidBytes(device_,expected);
    if(memcmp(expected,header_+4,16)) { error("batch belongs to another commissioned device"); return; }
    TemplateParameters p;
    if(!authenticated || !readTemplateParameters(p) || !parametersMatch(p)) { error("scanner settings changed"); return; }
    if(count>=MAX_EVENTS || !space()) { error("batch or storage full; use a new batch after download review"); return; }
    strcpy(active_,id); next_=count; needLift_=true; armed_=true; pollAt_=millis();
    uuidText(header_+36,class_); remember(); emit(terminal::CaptureEvent::Armed,"Lift then scan");
    Serial.printf("FPBARMED %s %u Lift finger; subsequent captures are PENDING MATCH\n",id,count);
  }
  bool block(BatchSink &sink,const char *kind,const uint8_t *bytes,size_t n,mbedtls_sha256_context &hash) {
    char line[128];
    snprintf(line,sizeof(line),"FPBLOCK %s %u %08lX",kind,static_cast<unsigned>(n),
        static_cast<unsigned long>(fingerprint::crc32(bytes,n)));
    if(!sink.line(line)) return false;
    for(size_t offset=0;offset<n;offset+=32) {
      char hex[65]={}; const size_t length=n-offset<32?n-offset:32;
      for(size_t i=0;i<length;++i) snprintf(hex+2*i,3,"%02X",bytes[offset+i]);
      snprintf(line,sizeof(line),"FPDATA %s",hex);
      if(!sink.line(line)) return false;
    }
    snprintf(line,sizeof(line),"FPEND %u %08lX",static_cast<unsigned>(n),
        static_cast<unsigned long>(fingerprint::crc32(bytes,n)));
    if(!sink.line(line)) return false;
    mbedtls_sha256_update_ret(&hash,bytes,n); return true;
  }
  bool exportBatch(const char *id,BatchSink &sink,char *digestOut,unsigned &countOut,bool *pendingOut=nullptr) {
    unsigned count=0; bool pending=false;
    if(!load(id,count,pending)) { error("batch invalid; files preserved for recovery"); return false; }
    mbedtls_sha256_context hash; mbedtls_sha256_init(&hash); mbedtls_sha256_starts_ret(&hash,0);
    char line[128]; snprintf(line,sizeof(line),"FPBATCH 1 %u %u",count,pending?1:0);
    bool ok=sink.line(line) && block(sink,"header",header_,sizeof(header_),hash);
    static uint8_t bytes[MAX_EVENT_BYTES];
    for(unsigned i=0;ok && i<count;++i) {
      char file[96]; eventPath(file,id,i); size_t n=0;
      ok=readFile(file,bytes,sizeof(bytes),n) && eventValid(bytes,n) && block(sink,"event",bytes,n,hash);
    }
    memset(bytes,0,sizeof(bytes)); uint8_t digest[32]; char hex[65]={};
    mbedtls_sha256_finish_ret(&hash,digest); mbedtls_sha256_free(&hash);
    if(!ok) return false;
    for(unsigned i=0;i<32;++i) snprintf(hex+2*i,3,"%02x",digest[i]);
    snprintf(line,sizeof(line),"FPBATCHEND %u %s",count,hex);
    if(!sink.line(line)) return false;
    strcpy(digestOut,hex); countOut=count; if(pendingOut) *pendingOut=pending; return true;
  }
  void exportBatch(const char *id) {
    SerialBatchSink sink; char digest[65]; unsigned count=0;
    if(exportBatch(id,sink,digest,count)) emit(terminal::CaptureEvent::Exported,"Downloaded; files kept");
    else error("export incomplete; files retained");
  }
  void list() {
    auto root=LittleFS.open("/probes","r");
    if(!root || !root.isDirectory()) { error("storage root missing"); return; }
    Serial.println("FPBLISTBEGIN 1");
    auto f=root.openNextFile();
    while(f) {
      const char *name=f.name(); const char *slash=strrchr(name,'/'); if(slash) name=slash+1;
      char id[37];
      if(f.isDirectory() && canonical(name,id)) {
        unsigned count=0; bool pending=false;
        if(load(id,count,pending)) Serial.printf("FPBLIST %s %u %u\n",id,count,pending?1:0);
        else Serial.printf("FPBDAMAGED %s\n",id);
      }
      f=root.openNextFile();
    }
    Serial.println("FPBLISTEND");
  }
public:
  const char *deviceId() const { return device_; }
  void setWireless(bool (*callback)(const char *,const char *)) { wireless_=callback; }
  bool wirelessAvailable() const override { return wireless_!=nullptr; }
  bool requestWirelessExport() override { stop(); return prepared() && wireless_ && wireless_("batch",active_); }
  bool requestWirelessLog() override { stop(); return wireless_ && wireless_("csv","attendance"); }
  bool exportTo(const char *id,BatchSink &sink,char *digest,unsigned &count,bool *pending=nullptr) {
    stop(); return mounted_ && exportBatch(id,sink,digest,count,pending);
  }
  void wirelessResult(bool ok,const char *message) {
    emit(ok?terminal::CaptureEvent::Exported:terminal::CaptureEvent::Error,message);
  }
  void wirelessCancelled() { emit(terminal::CaptureEvent::Cancelled,"Transfer cancelled"); }
  void begin() {
    armed_=false; active_[0]=class_[0]=0;
    randomUuid(boot_);
    mounted_=LittleFS.begin(false); // Never format to make this feature work.
    if(!mounted_) return;
    if(!LittleFS.exists("/probes") && !LittleFS.mkdir("/probes")) { mounted_=false; return; }
    Preferences prefs;
    if(!prefs.begin("fp-deferred",false)) { mounted_=false; return; }
    const String saved=prefs.getString("device",""); uint8_t bytes[16];
    if(saved.length()==36 && uuidBytes(saved.c_str(),bytes)) uuidText(bytes,device_);
    else {
      randomUuid(bytes); uuidText(bytes,device_);
      if(prefs.putString("device",device_)!=36) mounted_=false;
    }
    const String selected=prefs.getString("selected","");
    prefs.end();
    char selectedId[37];
    if(mounted_ && canonical(selected.c_str(),selectedId)) select(selectedId);
  }
  bool prepared() const override { return mounted_ && active_[0]; }
  void storageChanged() override { begin(); event_=terminal::CaptureEvent::None; }
  bool armed() const override { return armed_; }
  unsigned savedCount() const override { return next_; }
  const char *batchId() const override { return active_; }
  const char *classId() const override { return class_; }
  const char *message() const override { return message_; }
  terminal::CaptureEvent takeEvent() override {
    const auto event=event_; event_=terminal::CaptureEvent::None; return event;
  }
  bool startSelected() override {
    if(!prepared()) { error("Prepare a class batch over USB first"); return false; }
    char id[37]; strcpy(id,active_); arm(id); return armed_;
  }
  bool nextBatch() override {
    stop(); if(!mounted_) return false;
    auto root=LittleFS.open("/probes","r");
    if(!root || !root.isDirectory()) return false;
    char first[37]={},next[37]={}; auto f=root.openNextFile();
    while(f) {
      const char *name=f.name(); const char *slash=strrchr(name,'/'); if(slash) name=slash+1;
      char id[37]; unsigned count=0; bool pending=false;
      if(f.isDirectory() && canonical(name,id) && load(id,count,pending)) {
        uint8_t expected[16]; uuidBytes(device_,expected);
        if(!memcmp(expected,header_+4,16)) {
          if(!first[0] || strcmp(id,first)<0) strcpy(first,id);
          if(strcmp(id,active_)>0 && (!next[0] || strcmp(id,next)<0)) strcpy(next,id);
        }
      }
      f=root.openNextFile();
    }
    const char *choice=next[0]?next:first;
    if(!choice[0] || !select(choice)) return false;
    emit(terminal::CaptureEvent::Prepared,"Class batch selected"); return true;
  }
  void stop() override {
    if(armed_) emit(terminal::CaptureEvent::Stopped,"Capture stopped");
    armed_=false;
  }
  void command() {
    stop(); char line[256];
    if(!readTemplateConsoleLine(line,sizeof(line))) { error("invalid command"); return; }
    char *save=nullptr,*tokens[6]; unsigned count=0;
    char *word=strtok_r(line," \t",&save);
    while(word && count<6) { tokens[count++]=word; word=strtok_r(nullptr," \t",&save); }
    if(count==2 && !word && !strcmp(tokens[0],"initialize") && !strcmp(tokens[1],"EMPTY")) {
      initializeEmpty(); return;
    }
    if(!mounted_) { error("storage unavailable; no automatic format performed"); return; }
    if(!count || word) { error("invalid command"); return; }
    if(!strcmp(tokens[0],"begin")) { beginBatch(tokens,count); return; }
    if(count==1 && !strcmp(tokens[0],"stop")) { Serial.println("FPBSTOPPED"); return; }
    if(count==1 && !strcmp(tokens[0],"list")) { list(); return; }
    char id[37];
    if(count!=2 || !canonical(tokens[1],id)) { error("use begin, arm UUID, stop, list, or export UUID"); return; }
    if(!strcmp(tokens[0],"arm")) arm(id);
    else if(!strcmp(tokens[0],"export")) exportBatch(id);
    else error("unknown operation");
  }
  void tick() override {
    if(!armed_ || static_cast<uint32_t>(millis()-pollAt_)<150) return;
    pollAt_=millis(); const uint8_t capture[]={0x01};
    const auto result=query(capture,sizeof(capture),SENSOR_OPERATION_TIMEOUT_MS);
    if(!armed_) return;
    if(result.error!=QueryError::None || result.reply.length!=1) { error("capture communication failed"); return; }
    if(result.reply.payload[0]==0x02) { needLift_=false; return; }
    if(needLift_) return;
    needLift_=true; // Always require lift after any attempt, even poor images.
    if(result.reply.payload[0]!=0) { emit(terminal::CaptureEvent::Retry,"Lift and retry"); Serial.println("FPBRETRY image rejected; lift and retry"); return; }
    const uint64_t uptime=esp_timer_get_time()/1000;
    if(next_>=MAX_EVENTS || !space()) { error("storage full; no scan saved, existing files retained"); return; }
    TemplateParameters p;
    if(!readTemplateParameters(p)||!parametersMatch(p)) { error("scanner settings changed"); return; }
    static fingerprint::SensorTemplate probe;
    static uint8_t bytes[MAX_EVENT_BYTES]; probe.clear(); memset(bytes,0,sizeof(bytes));
    const uint8_t features[]={0x02,1};
    if(!checkOperationAck("Img2Tz",query(features,sizeof(features),SENSOR_OPERATION_TIMEOUT_MS)) ||
        !receiveTemplate(probe,p) || !probe.length) {
      probe.clear(); emit(terminal::CaptureEvent::Retry,"Lift and retry"); Serial.println("FPBRETRY feature export failed; lift and retry"); return;
    }
    const size_t n=EVENT_FIXED_BYTES+probe.length;
    if(!armed_) { probe.clear(); return; }
    memcpy(bytes,"FPE1",4); randomUuid(bytes+4); memcpy(bytes+20,boot_,16);
    put64(bytes+36,uptime); put16(bytes+44,probe.length); memcpy(bytes+46,probe.bytes,probe.length);
    probe.clear(); seal(bytes,n);
    char pending[96],target[96]; path(pending,active_,"pending"); eventPath(target,active_,next_);
    const bool ok=eventValid(bytes,n) && commit(storage_,pending,target,bytes,n);
    char event[37]; uuidText(bytes+4,event); memset(bytes,0,sizeof(bytes));
    if(!ok) { error("save not confirmed; retain files for recovery; scan is not attendance"); return; }
    ++next_; Serial.printf("FPBSAVED %s %u PENDING_MATCH Lift finger\n",event,next_);
    emit(terminal::CaptureEvent::Saved,"Pending identity match");
  }
};
}

deferred::Device deferredDevice;
