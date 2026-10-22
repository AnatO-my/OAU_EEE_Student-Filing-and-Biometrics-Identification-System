#pragma once
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <sys/time.h>
#include <time.h>
#include "wifi_transfer_format.h"
#include "terminal_storage.h"

namespace wireless {
// Outgoing TLS only; no wireless scanner commands or inbound biometric server.
class Transfer : public deferred::BatchSink {
  deferred::Device &device_;
  WiFiClientSecure tls_;
  char bytes_[MAX_CONFIG_BYTES]={}; Config config_;
  bool configured_=false,joining_=false,userCancelled_=false;
  char type_[12]={},id_[40]={};
  uint32_t started_=0,transferAt_=0;
  bool (*cancel_)()=nullptr;
  bool (*seedClock_)()=nullptr;
  enum class Phase { Idle, Join, Clock, Send } phase_=Phase::Idle;
  void finish(bool ok,const char *message) {
    tls_.stop(); WiFi.disconnect(false,false); WiFi.mode(WIFI_OFF);
    phase_=Phase::Idle; joining_=false;
    if(userCancelled_) {
      device_.wirelessCancelled();
      Serial.println("FPWCANCELLED transfer cancelled; files retained; laptop receipt not confirmed");
    } else {
      device_.wirelessResult(ok,message);
      Serial.println(ok?"FPWSAVED laptop copy verified; device files retained; website upload still pending":"FPWERROR transfer not confirmed; all device files retained");
    }
  }
  bool cancelled() {
    serviceTerminalInputs(); if(cancel_ && cancel_()) userCancelled_=true;
    return userCancelled_;
  }
  bool usable() {
    return !cancelled() && tls_.connected() && static_cast<uint32_t>(millis()-transferAt_)<120000;
  }
  static void digest(const uint8_t *data,size_t n,char *out) {
    uint8_t sum[32]; mbedtls_sha256_ret(data,n,sum,0);
    for(unsigned i=0;i<32;++i) snprintf(out+2*i,3,"%02x",sum[i]);
  }
  bool readLine(char *out,size_t capacity) {
    size_t used=0; const uint32_t at=millis();
    while(static_cast<uint32_t>(millis()-at)<10000 && usable()) {
      if(!tls_.available()) { delay(1); continue; }
      const int c=tls_.read();
      if(c=='\n') { out[used]=0; return true; }
      if(c<32 || c>126 || used+1>=capacity) return false;
      out[used++]=static_cast<char>(c);
    }
    return false;
  }
  bool fileFrame(const char *type,size_t n,const char *sha) {
    char text[128]; snprintf(text,sizeof(text),"FPFILE 1 %s %u %s",type,static_cast<unsigned>(n),sha);
    return line(text);
  }
  bool fileData(const uint8_t *data,size_t n) {
    for(size_t at=0;at<n;at+=32) {
      char text[72]="FPDATA "; const size_t count=n-at<32?n-at:32;
      for(size_t i=0;i<count;++i) snprintf(text+7+2*i,3,"%02X",data[at+i]);
      if(!line(text)) return false;
    }
    return true;
  }
  bool fileEnd(size_t n,const char *sha) {
    char text[128]; snprintf(text,sizeof(text),"FPFILEEND %u %s",static_cast<unsigned>(n),sha); return line(text);
  }
  bool csv(char *wire,unsigned &count) {
    auto f=LittleFS.open("/attendance.csv","r"); bool duplicate=false; uint32_t ignored=0;
    if(!f || f.isDirectory() || f.size()>terminal::MAX_LOG_BYTES ||
       !terminal::inspectLog(f,0,nullptr,duplicate,ignored,serviceTerminalInputs) || !f.seek(0)) return false;
    const size_t size=f.size(); uint8_t chunk[128]; count=0;
    mbedtls_sha256_context hash; mbedtls_sha256_init(&hash); mbedtls_sha256_starts_ret(&hash,0);
    bool ok=true;
    while(f.available()) {
      const size_t n=f.read(chunk,sizeof(chunk));
      if(!n || cancelled()) { ok=false; break; }
      mbedtls_sha256_update_ret(&hash,chunk,n);
      for(size_t i=0;i<n;++i) if(chunk[i]=='\n') ++count;
    }
    uint8_t sum[32]; mbedtls_sha256_finish_ret(&hash,sum); mbedtls_sha256_free(&hash);
    if(!ok || !count || !f.seek(0)) return false;
    --count;
    for(unsigned i=0;i<32;++i) snprintf(wire+2*i,3,"%02x",sum[i]);
    if(!fileFrame("csv",size,wire)) return false;
    size_t sent=0;
    while(f.available()) {
      const size_t n=f.read(chunk,sizeof(chunk));
      if(!n || !fileData(chunk,n)) { memset(chunk,0,sizeof(chunk)); return false; }
      sent+=n;
    }
    memset(chunk,0,sizeof(chunk));
    return sent==size && fileEnd(size,wire);
  }
  bool enrolled(char *wire,unsigned &count) {
    const unsigned slot=static_cast<unsigned>(strtoul(id_,nullptr,10));
    TemplateParameters p; Reply table;
    if(!authenticated || !readTemplateParameters(p) || slot>=p.capacity ||
       !readIndexPage(static_cast<uint8_t>(slot/256),table) ||
       !(table.payload[1+(slot%256)/8]&(1U<<(slot%8)))) return false;
    const uint8_t load[]={7,1,static_cast<uint8_t>(slot>>8),static_cast<uint8_t>(slot)};
    static fingerprint::SensorTemplate value; value.clear();
    if(cancelled() || !checkOperationAck("LoadChar",query(load,sizeof(load),SENSOR_OPERATION_TIMEOUT_MS)) ||
       !receiveTemplate(value,p) || !value.length) { value.clear(); return false; }
    uint8_t header[18]; memcpy(header,"FPT1",4); deferred::put16(header+4,slot);
    deferred::put16(header+6,p.capacity); deferred::put16(header+8,p.security);
    deferred::put16(header+10,p.packetBytes); deferred::put16(header+12,p.systemId); deferred::put32(header+14,p.address);
    mbedtls_sha256_context hash; uint8_t sum[32];
    mbedtls_sha256_init(&hash); mbedtls_sha256_starts_ret(&hash,0);
    mbedtls_sha256_update_ret(&hash,header,sizeof(header)); mbedtls_sha256_update_ret(&hash,value.bytes,value.length);
    mbedtls_sha256_finish_ret(&hash,sum); mbedtls_sha256_free(&hash);
    for(unsigned i=0;i<32;++i) snprintf(wire+2*i,3,"%02x",sum[i]);
    const size_t n=sizeof(header)+value.length;
    const bool ok=fileFrame("template",n,wire) && fileData(header,sizeof(header)) &&
      fileData(value.bytes,value.length) && fileEnd(n,wire);
    value.clear(); count=1; return ok;
  }
  void send() {
    transferAt_=millis();
    tls_.setCACert(config_.ca); tls_.setHandshakeTimeout(5); tls_.setTimeout(2);
    if(cancelled() || !tls_.connect(config_.host,config_.port,5000)) { finish(false,"TLS connection failed"); return; }
    uint8_t peer[32]; char fingerprint[65]={};
    if(!tls_.getFingerprintSHA256(peer)) { finish(false,"Certificate unavailable"); return; }
    for(unsigned i=0;i<32;++i) snprintf(fingerprint+2*i,3,"%02x",peer[i]);
    if(strcmp(fingerprint,config_.fingerprint)) { finish(false,"Certificate pin changed"); return; }
    char text[256]; snprintf(text,sizeof(text),"FPWIFI 1 %s %s %s %s",config_.token,device_.deviceId(),type_,id_);
    if(!line(text) || !readLine(text,sizeof(text)) || strcmp(text,"FPWREADY 1")) { finish(false,"Receiver refused transfer"); return; }
    char wire[65]={}; unsigned count=0;
    bool pending=false;
    const bool batch=!strcmp(type_,"batch");
    const bool ok=batch?device_.exportTo(id_,*this,wire,count,&pending):
      !strcmp(type_,"csv")?csv(wire,count):enrolled(wire,count);
    // USB's stream digest predates the recovery flag. Bind that flag in the
    // Wi-Fi receipt as well, so two snapshots cannot share its confirmation.
    if(ok && batch) {
      char binding[67]; snprintf(binding,sizeof(binding),"%s:%u",wire,pending?1:0);
      digest(reinterpret_cast<const uint8_t *>(binding),strlen(binding),wire);
    }
    if(!ok || !readLine(text,sizeof(text)) || !validReceipt(text,type_,id_,wire,count)) {
      finish(false,"Laptop save unconfirmed"); return;
    }
    finish(true,"Laptop saved; web pending");
  }
public:
  explicit Transfer(deferred::Device &device):device_(device) {}
  void begin(bool (*cancel)(),bool (*seedClock)()=nullptr) {
    cancel_=cancel; seedClock_=seedClock; Preferences prefs;
    if(prefs.begin("fp-wifi",true)) {
      const size_t n=prefs.getBytesLength("config");
      if(n && n<=sizeof(bytes_) && prefs.getBytes("config",bytes_,n)==n) configured_=parseConfig(bytes_,n,config_);
      prefs.end();
    }
    WiFi.persistent(false); WiFi.setAutoReconnect(false); WiFi.mode(WIFI_OFF);
  }
  bool line(const char *text) override {
    if(!usable()) return false;
    const size_t n=strlen(text);
    return tls_.write(reinterpret_cast<const uint8_t *>(text),n)==n && tls_.write('\n')==1;
  }
  bool busy() const { return phase_!=Phase::Idle; }
  bool queue(const char *type,const char *id) {
    if(busy() || !configured_ || !device_.deviceId()[0]) return false;
    if(strcmp(type,"batch") && strcmp(type,"csv") && strcmp(type,"template")) return false;
    if(!strcmp(type,"batch")) { uint8_t uuid[16]; char canonical[37];
      if(!deferred::uuidBytes(id,uuid)) return false;
      deferred::uuidText(uuid,canonical); if(strcmp(id,canonical)) return false;
    } else if(!strcmp(type,"csv")) { if(strcmp(id,"attendance")) return false; }
    else {
      const size_t n=strlen(id); if(!n || n>5 || (n>1 && *id=='0')) return false;
      for(size_t i=0;i<n;++i) if(id[i]<'0'||id[i]>'9') return false;
      if(strtoul(id,nullptr,10)>65534) return false;
    }
    if((time(nullptr)<MIN_CLOCK || time(nullptr)>MAX_CLOCK) && seedClock_) seedClock_();
    strcpy(type_,type); strcpy(id_,id); device_.stop(); phase_=Phase::Join; joining_=false; userCancelled_=false; return true;
  }
  void tick() {
    if(!busy()) return;
    if(cancelled()) { finish(false,"Transfer cancelled"); return; }
    if(phase_==Phase::Join) {
      if(!joining_) { joining_=true; started_=millis(); WiFi.mode(WIFI_STA); WiFi.begin(config_.ssid,config_.password); }
      if(WiFi.status()==WL_CONNECTED) {
        configTime(0,0,"pool.ntp.org","time.cloudflare.com"); started_=millis(); phase_=Phase::Clock;
      } else if(static_cast<uint32_t>(millis()-started_)>20000) finish(false,"Wi-Fi connection failed");
    } else if(phase_==Phase::Clock) {
      if(time(nullptr)>=1704067200L && time(nullptr)<=2145916799L) phase_=Phase::Send;
      else if(static_cast<uint32_t>(millis()-started_)>15000) finish(false,"Set TLS clock via USB");
    } else send();
  }
  void command() {
    char text[160];
    if(!readTemplateConsoleLine(text,sizeof(text))) { Serial.println("FPWERROR invalid command"); return; }
    if(!strcmp(text,"status")) { Serial.printf("FPWSTATUS 1 %s %u %u\n",device_.deviceId(),configured_?1:0,WiFi.status()==WL_CONNECTED?1:0); return; }
    if(!strcmp(text,"forget")) {
      Preferences prefs; const bool opened=prefs.begin("fp-wifi",false);
      const bool ok=opened && (!prefs.isKey("config") || prefs.remove("config")); if(opened) prefs.end();
      if(ok) { memset(bytes_,0,sizeof(bytes_)); config_=Config(); configured_=false; }
      Serial.println(ok?"FPWFORGOTTEN":"FPWERROR settings not removed"); return;
    }
    unsigned long long epoch=0; int end=0;
    if(sscanf(text,"clock %llu%n",&epoch,&end)==1 && !text[end] && epoch>=1704067200ULL && epoch<=2145916799ULL) {
      timeval now={}; now.tv_sec=static_cast<decltype(now.tv_sec)>(epoch);
      Serial.println(settimeofday(&now,nullptr)==0?"FPWCLOCK":"FPWERROR clock failed"); return;
    }
    unsigned n=0; char expected[65]={}; end=0;
    if(sscanf(text,"configure %u %64s%n",&n,expected,&end)==2 && !text[end] && n<=MAX_CONFIG_BYTES && n>=12 && hex64(expected)) {
      static char staged[MAX_CONFIG_BYTES]; memset(staged,0,sizeof(staged));
      Serial.printf("FPWREADY %u\n",n); size_t used=0; const uint32_t at=millis();
      while(used<n && static_cast<uint32_t>(millis()-at)<15000) {
        if(Serial.available()) staged[used++]=static_cast<char>(Serial.read()); else delay(1);
      }
      char actual[65]={}; digest(reinterpret_cast<const uint8_t *>(staged),used,actual); Config parsed;
      bool ok=used==n && !strcmp(actual,expected) && parseConfig(staged,n,parsed);
      if(ok) { Preferences prefs; ok=prefs.begin("fp-wifi",false);
        if(ok) {
          static char readback[MAX_CONFIG_BYTES]; memset(readback,0,sizeof(readback));
          ok=prefs.putBytes("config",staged,n)==n && prefs.getBytesLength("config")==n &&
            prefs.getBytes("config",readback,n)==n && !memcmp(staged,readback,n);
          memset(readback,0,sizeof(readback)); prefs.end();
        }
      }
      if(ok) { memset(bytes_,0,sizeof(bytes_)); memcpy(bytes_,staged,n); configured_=parseConfig(bytes_,n,config_); }
      memset(staged,0,sizeof(staged));
      Serial.println(ok?"FPWCONFIGURED":"FPWERROR configuration not saved");
      if(!ok) { templateTransferError(); }
      return;
    }
    char kind[12]={},identifier[40]={}; end=0;
    if(sscanf(text,"send %11s %39s%n",kind,identifier,&end)==2 && !text[end] && queue(kind,identifier)) {
      Serial.println("FPWQUEUED"); return;
    }
    // Friendly CSV shorthand; no identifier guessing for class batches/templates.
    if(!strcmp(text,"send csv") && queue("csv","attendance")) { Serial.println("FPWQUEUED"); return; }
    Serial.println("FPWERROR use status, configure, clock, forget, send batch UUID, send csv or send template SLOT");
  }
};
} // namespace wireless
