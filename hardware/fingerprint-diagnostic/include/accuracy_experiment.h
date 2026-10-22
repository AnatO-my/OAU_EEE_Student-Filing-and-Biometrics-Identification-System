#pragma once

// Shared by the two separate accuracy sketches; depends on scanner_driver.h.
#include "accuracy_statistics.h"
#include "portable_template.h"
#include "accuracy_clock.h"
#include <stdio.h>

#ifndef ACCURACY_VERIFICATION
#define ACCURACY_VERIFICATION 0
#endif

namespace accuracy {
constexpr const char *TEST_NAME=ACCURACY_VERIFICATION?"verify_1to1":"identify_1toN";
struct Settings {
  uint16_t capacity=0,stored=0,security=0,systemId=0,packetCode=0,baudMultiplier=0;
  uint32_t address=0;
  bool same(const Settings &b) const {
    return capacity==b.capacity && stored==b.stored && security==b.security &&
      systemId==b.systemId && packetCode==b.packetCode && baudMultiplier==b.baudMultiplier && address==b.address;
  }
};
inline bool settings(Settings &out) {
  const uint8_t p[]={0x0F},n[]={0x1D};
  const auto parameters=query(p,sizeof(p)),count=query(n,sizeof(n));
  if (!checkQuery("ReadSysPara",parameters) || parameters.reply.length!=17 ||
      !checkQuery("TemplateNum",count) || count.reply.length!=3) return false;
  const auto *v=parameters.reply.payload;
  out.capacity=fingerprint::read16(v+5); out.security=fingerprint::read16(v+7);
  out.systemId=fingerprint::read16(v+3); out.address=fingerprint::read32(v+9);
  out.packetCode=fingerprint::read16(v+13); out.baudMultiplier=fingerprint::read16(v+15);
  out.stored=fingerprint::read16(count.reply.payload+1);
  return out.capacity>0 && out.stored<=out.capacity;
}

class Experiment {
  Clock clock_;
  Statistics stats_;
  Settings frozen_;
  uint8_t inventory_[8192]={};
  bool frozenOK_=false,hasTarget_=false,caseSet_=false,running_=false,announced_=false;
  uint16_t target_=0;
  Truth truth_=Truth::Genuine;
  Source source_=Source::Automatic;
  PresentationGate gate_;
  uint32_t polledAt_=0,boot_=0,session_=0,pollFailures_=0;
  uint64_t event_=0;
  char config_[12]={}; size_t configLength_=0;
  bool enteringTarget_=false,configOverflow_=false;
  uint32_t configAt_=0;
  bool diagnostic_=false;
  uint8_t nextDiagnosticOrder_=1,diagnosticOrder_=0;
  uint32_t diagnosticAt_=0;
  enum class Enrollment { Idle, LiftFirst, First, LiftSecond, Second };
  Enrollment enrollment_=Enrollment::Idle;
  uint32_t enrollmentAt_=0;
  uint16_t enrollmentSlot_=0;

  void stopEnrollment(const char *reason) {
    enrollment_=Enrollment::Idle;
    Serial.printf("ACCENROLL %s; paused. No accuracy trial counted.\n",reason);
  }
  void enrollmentStage(Enrollment stage,const char *prompt) {
    enrollment_=stage; enrollmentAt_=millis();
    Serial.printf("ACCENROLL %s (20 s; p cancels)\n",prompt);
  }
  void beginEnrollment() {
    enrollment_=Enrollment::Idle;
    command('n'); // Publish the previous results before changing the gallery.
    if (!freezeGallery(true)) return;
    bool found=false;
    for (uint32_t id=1;id<frozen_.capacity;++id) {
      if (!(inventory_[id/8] & (1U<<(id%8)))) { enrollmentSlot_=id; found=true; break; }
    }
    if (!found && !(inventory_[0]&1)) { enrollmentSlot_=0; found=true; }
    if (!found) { stopEnrollment("library full; nothing changed"); return; }
    Serial.printf("ACCENROLL selected empty slot %u; new statistics session started.\n",enrollmentSlot_);
    polledAt_=millis()-100;
    enrollmentStage(Enrollment::LiftFirst,"Lift finger before enrollment");
  }
  void tickEnrollment() {
    if (millis()-enrollmentAt_>=20000) { stopEnrollment("timed out"); return; }
    if (millis()-polledAt_<100) return;
    polledAt_=millis();
    const uint8_t image[]={1}; const auto captured=query(image,sizeof(image));
    if (captured.error!=QueryError::None || captured.reply.length!=1 ||
        (captured.reply.payload[0]!=0 && captured.reply.payload[0]!=2)) {
      stopEnrollment("image capture failed; retry e"); return;
    }
    const bool noFinger=captured.reply.payload[0]==2;
    if (enrollment_==Enrollment::LiftFirst || enrollment_==Enrollment::LiftSecond) {
      if (noFinger) enrollmentStage(enrollment_==Enrollment::LiftFirst?Enrollment::First:Enrollment::Second,
        enrollment_==Enrollment::LiftFirst?"Place NEW finger: scan 1 of 2":"Place SAME finger: scan 2 of 2");
      return;
    }
    if (noFinger) return;
    const bool first=enrollment_==Enrollment::First;
    const uint8_t features[]={2,static_cast<uint8_t>(first?1:2)};
    if (!checkOperationAck("Enrollment features",query(features,sizeof(features),SENSOR_OPERATION_TIMEOUT_MS))) {
      stopEnrollment("feature extraction failed; retry e"); return;
    }
    if (first) {
      const uint8_t search[]={4,1,0,0,static_cast<uint8_t>(frozen_.capacity>>8),static_cast<uint8_t>(frozen_.capacity)};
      const auto duplicate=query(search,sizeof(search),SENSOR_OPERATION_TIMEOUT_MS);
      if (duplicate.error==QueryError::None && duplicate.reply.length==5 && duplicate.reply.payload[0]==0) {
        Serial.printf("ACCENROLL existing match ID=%u; no duplicate stored.\n",fingerprint::read16(duplicate.reply.payload+1));
        stopEnrollment("choose a different finger or select its existing ID with t"); return;
      }
      if (duplicate.error!=QueryError::None || (duplicate.reply.length!=1 && duplicate.reply.length!=5) || duplicate.reply.payload[0]!=9) {
        stopEnrollment("duplicate check failed; nothing stored"); return;
      }
      enrollmentStage(Enrollment::LiftSecond,"Scan 1 accepted. Lift finger"); return;
    }
    const uint8_t merge[]={5};
    if (!checkOperationAck("Enrollment merge",query(merge,sizeof(merge),SENSOR_OPERATION_TIMEOUT_MS))) {
      stopEnrollment("scans did not form a model; retry e"); return;
    }
    // Recheck the entire inventory immediately before the sole flash write.
    if (!freezeGallery(true) || (inventory_[enrollmentSlot_/8] & (1U<<(enrollmentSlot_%8)))) {
      stopEnrollment("gallery changed before saving; nothing stored"); return;
    }
    const uint16_t previous=frozen_.stored;
    const uint8_t store[]={6,1,static_cast<uint8_t>(enrollmentSlot_>>8),static_cast<uint8_t>(enrollmentSlot_)};
    const auto saved=query(store,sizeof(store),SENSOR_OPERATION_TIMEOUT_MS);
    enrollment_=Enrollment::Idle; frozenOK_=false;
    if (!checkOperationAck("Enrollment store",saved)) {
      stopEnrollment("save unconfirmed; inspect inventory before retrying; no automatic retry"); return;
    }
    if (!freezeGallery(true) || frozen_.stored!=previous+1 ||
        !(inventory_[enrollmentSlot_/8] & (1U<<(enrollmentSlot_%8)))) {
      stopEnrollment("store acknowledged but inventory verification failed; do not assume success"); return;
    }
    target_=enrollmentSlot_; hasTarget_=true;
    Serial.printf("ACCENROLL SAVED ID=%u; count=%u; occupied slot verified. Lift finger.\n",target_,frozen_.stored);
    Serial.println("ACCENROLL selected this ID for testing. a then g starts genuine scans; i needs a different finger.");
  }

  void diagnosticReply(const char *operation,const QueryResult &r,bool search=false) const {
    Serial.printf("ACCDIAG operation=%s transport=%u bytes=%u",operation,
      static_cast<unsigned>(r.error),static_cast<unsigned>(r.reply.length));
    if (r.error==QueryError::None && r.reply.length) {
      Serial.printf(" code=0x%02X",r.reply.payload[0]);
      if (search && r.reply.payload[0]==0 && r.reply.length==5)
        Serial.printf(" returned_slot=%u",fingerprint::read16(r.reply.payload+1));
    }
    Serial.println("");
  }
  bool diagnosticFeatures() {
    const uint8_t command[]={2,1};
    const auto r=query(command,sizeof(command),SENSOR_OPERATION_TIMEOUT_MS);
    diagnosticReply("features_buffer1",r);
    return r.error==QueryError::None && r.reply.length==1 && r.reply.payload[0]==0;
  }
  void diagnoseImage(const QueryResult &image) {
    diagnostic_=false;
    diagnosticReply("image",image);
    if (image.reply.payload[0]!=0) return;
    // Hardware observations show repeat processing can invalidate later results.
    // Perform exactly one feature extraction and one method per fresh capture.
    const unsigned part=diagnosticOrder_;
    if (!diagnosticFeatures()) return;
    if (part<2) {
        const uint16_t first=part?target_:0,count=part?1:frozen_.capacity;
        Serial.printf("ACCDIAG request=%s first=%u count=%u\n",part?"selected_search":"full_search",first,count);
        const uint8_t command[]={4,1,static_cast<uint8_t>(first>>8),static_cast<uint8_t>(first),
          static_cast<uint8_t>(count>>8),static_cast<uint8_t>(count)};
        const auto r=query(command,sizeof(command),SENSOR_OPERATION_TIMEOUT_MS);
        diagnosticReply(part?"selected_search":"full_search",r,true);
    } else {
        const uint8_t load[]={7,2,static_cast<uint8_t>(target_>>8),static_cast<uint8_t>(target_)};
        const auto loaded=query(load,sizeof(load),SENSOR_OPERATION_TIMEOUT_MS);
        diagnosticReply("load_reference_buffer2",loaded);
        if (loaded.error!=QueryError::None || loaded.reply.length!=1 || loaded.reply.payload[0]!=0) return;
        const uint8_t match[]={3};
        const auto compared=query(match,sizeof(match),SENSOR_OPERATION_TIMEOUT_MS);
        diagnosticReply("direct_match",compared);
    }
    Serial.println("ACCDIAG done; paused. No accuracy trial counted. q repeats; g/i returns to testing.");
  }

  bool freezeGallery(bool allowEmpty=false) {
    Settings current;
    if (!authenticated || !settings(current) || (!allowEmpty && !current.stored)) {
      Serial.println("ACCERROR sensor/library unavailable or empty; enroll using normal firmware first."); return false;
    }
    if (frozenOK_ && !frozen_.same(current)) {
      Serial.println("ACCERROR settings/gallery count changed; save results, then n for a new session."); return false;
    }
    uint32_t occupied=0;
    for (uint32_t base=0;base<current.capacity;base+=256) {
      Reply table;
      if (!readIndexPage(static_cast<uint8_t>(base/256),table)) return false;
      for (unsigned byte=0;byte<32 && base+byte*8<current.capacity;++byte) {
        uint8_t value=table.payload[1+byte];
        const uint32_t remaining=current.capacity-base-byte*8;
        if (remaining<8) value &= (1U<<remaining)-1;
        for (unsigned bit=0;bit<8;++bit) if (value & (1U<<bit)) ++occupied;
        const size_t offset=base/8+byte;
        if (frozenOK_ && inventory_[offset]!=value) {
          Serial.println("ACCERROR occupied slots changed; save results, then n for a new session."); return false;
        }
        inventory_[offset]=value;
      }
    }
    if (occupied!=current.stored) {
      Serial.println("ACCERROR count/index disagreement; session not started."); return false;
    }
    frozen_=current; frozenOK_=true; return true;
  }
  bool targetOccupied() const {
    return hasTarget_ && target_<frozen_.capacity && (inventory_[target_/8] & (1U<<(target_%8)));
  }
  static void rate(char *out,size_t size,uint64_t numerator,uint64_t denominator) {
    if (!denominator) snprintf(out,size,"NA");
    else snprintf(out,size,"%.4f",100.0*static_cast<double>(numerator)/static_cast<double>(denominator));
  }
  void summaryRow(Source source,const char *category,const Counts &c) const {
    char acc[24],precision[24],recall[24],specificity[24],fpr[24],fnr[24],coverage[24];
    rate(acc,sizeof(acc),c.correct(),c.completed());
    rate(precision,sizeof(precision),c.tp,c.tp+c.fp);
    rate(recall,sizeof(recall),c.tp,c.tp+c.fn);
    rate(specificity,sizeof(specificity),c.tn,c.tn+c.fp);
    rate(fpr,sizeof(fpr),c.fp,c.fp+c.tn); rate(fnr,sizeof(fnr),c.fn,c.fn+c.tp);
    rate(coverage,sizeof(coverage),c.completed(),c.attempts);
    Serial.printf("ACCSUMMARY,%08lX-%lu,%s,%s,%s,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%s,%s,%s,%s,%s,%s,%s\n",
      static_cast<unsigned long>(boot_),static_cast<unsigned long>(session_),TEST_NAME,sourceName(source),category,
      c.attempts,c.tp,c.fp,c.fn,c.tn,c.acquisition,c.communication,c.sensor,c.unclassified,c.wrongId,c.pollErrors,
      c.completed(),acc,precision,recall,specificity,fpr,fnr,coverage);
  }
  void trial(Source source,Truth truth,Outcome outcome,const char *stage,uint32_t elapsed,
             int returned=-1,int code=-1,int searchMs=-1,bool observation=true) {
    const bool counted=source==Source::Automatic || !observation;
    if (counted) stats_.get(source,truth).add(truth,outcome);
    char expected[12]="NA",found[12]="NA",confirmation[12]="NA",searchTime[16]="NA";
    if (hasTarget_ && (truth==Truth::Genuine || ACCURACY_VERIFICATION)) snprintf(expected,sizeof(expected),"%u",target_);
    if (returned>=0) snprintf(found,sizeof(found),"%d",returned);
    if (code>=0) snprintf(confirmation,sizeof(confirmation),"0x%02X",code);
    if (searchMs>=0) snprintf(searchTime,sizeof(searchTime),"%d",searchMs);
    Serial.printf("ACCTRIAL,%08lX-%lu,%s,%s,%s,%llu,%s,%u,%s,%s,%s,%s,%s,%s,%lu,%s,%u,%u,%u,%lu\n",
      static_cast<unsigned long>(boot_),static_cast<unsigned long>(session_),TEST_NAME,sourceName(source),truthName(truth),
      ++event_,observation?"scan":"manual_key",counted?1:0,outcomeName(outcome),classification(truth,outcome),
      expected,found,confirmation,stage,static_cast<unsigned long>(elapsed),searchTime,
      frozen_.security,frozen_.stored,frozen_.capacity,static_cast<unsigned long>(millis()));
    clock_.record(boot_,session_,TEST_NAME,event_,"trial");
    if (counted) {
      const auto &c=stats_.get(source,truth);
      Serial.printf("COUNT %s/%s attempts=%llu TP=%llu FP=%llu FN=%llu TN=%llu unclassified=%llu errors=%llu\n",
        sourceName(source),truthName(truth),c.attempts,c.tp,c.fp,c.fn,c.tn,c.unclassified,c.acquisition+c.communication+c.sensor);
    } else Serial.println("OBSERVATION ONLY: manual mode; keys 1/2/3 tally separate operator results.");
  }
  void finish(Outcome outcome,const char *stage,uint32_t started,int returned=-1,int code=-1,int searchMs=-1) {
    trial(source_,truth_,outcome,stage,millis()-started,returned,code,searchMs);
    gate_.finished(millis()); announced_=false;
    Serial.println("ACCCOOLDOWN 2000 ms; lift now. Next scan needs no key.");
  }
  void processImage(const QueryResult &image,uint32_t started) {
    if (image.reply.payload[0]==3) { finish(Outcome::AcquisitionError,"image",started,-1,3); return; }
    const uint8_t features[]={2,1};
    const auto extracted=query(features,sizeof(features),SENSOR_OPERATION_TIMEOUT_MS);
    if (extracted.error!=QueryError::None || extracted.reply.length!=1) {
      finish(Outcome::CommunicationError,"features",started); return;
    }
    const uint8_t featureCode=extracted.reply.payload[0];
    if (featureCode!=0) {
      finish(featureCode==6 || featureCode==7 || featureCode==0x15?Outcome::AcquisitionError:Outcome::SensorError,
        "features",started,-1,featureCode); return;
    }
    const uint16_t first=ACCURACY_VERIFICATION?target_:0;
    const uint16_t count=ACCURACY_VERIFICATION?1:frozen_.capacity;
    const uint8_t search[]={4,1,static_cast<uint8_t>(first>>8),static_cast<uint8_t>(first),
      static_cast<uint8_t>(count>>8),static_cast<uint8_t>(count)};
    const uint32_t searchStarted=millis();
    const auto result=query(search,sizeof(search),SENSOR_OPERATION_TIMEOUT_MS);
    const int searchMs=millis()-searchStarted;
    if (result.error!=QueryError::None) { finish(Outcome::CommunicationError,"search",started); return; }
    const uint8_t code=result.reply.payload[0];
    if (code==9) {
      if (result.reply.length==1 || result.reply.length==5) finish(Outcome::Rejected,"search",started,-1,code,searchMs);
      else finish(Outcome::CommunicationError,"search",started,-1,code);
      return;
    }
    if (code!=0) {
      finish(Outcome::SensorError,"search",started,-1,code,searchMs); return;
    }
    if (result.reply.length!=5) { finish(Outcome::CommunicationError,"search",started); return; }
    const uint16_t returned=fingerprint::read16(result.reply.payload+1);
    if (returned>=frozen_.capacity || !(inventory_[returned/8] & (1U<<(returned%8))) ||
        (ACCURACY_VERIFICATION && returned!=target_)) {
      finish(Outcome::CommunicationError,"search_id",started,returned,code,searchMs); return;
    }
    const Outcome outcome=truth_==Truth::Genuine && returned!=target_?Outcome::WrongIdentity:Outcome::Accepted;
    finish(outcome,"search",started,returned,code,searchMs);
  }
public:
  void begin(uint32_t boot) {
    clock_.begin(); boot_=boot; session_=1; help(); headers();
    clock_.record(boot_,session_,TEST_NAME,0,"check");
    Serial.println("ACCPAUSED Choose t <known occupied ID> then g (genuine) or i (impostor). No per-scan key required.");
  }
  void headers() const {
    Serial.println("ACCHEADER,session,test,source,case,event_id,event_type,counted,outcome,class,expected_slot,returned_slot,scanner_code,stage,total_ms,search_ms,security,gallery_count,capacity,uptime_ms");
    Serial.println("ACCSUMMARYHEADER,session,test,source,case,attempts,tp,fp,fn,tn,acquisition_errors,communication_errors,sensor_errors,unclassified,wrong_id,poll_errors,completed,accuracy_pct,precision_pct,recall_pct,specificity_pct,fpr_pct,fnr_pct,coverage_pct");
    Serial.println("ACCTIMEHEADER,session,test,event_id,scope,rtc_local_datetime,rtc_status,rtc_utc_offset_minutes,uptime_ms");
    Serial.printf("ACCMETA version=accuracy-v3 test=%s boot=%08lX scanner_rx=%d scanner_tx=%d baud=%lu cooldown_ms=2000\n",
      TEST_NAME,static_cast<unsigned long>(boot_),FINGERPRINT_RX_PIN,FINGERPRINT_TX_PIN,static_cast<unsigned long>(connectedBaud));
  }
  void help() const {
    Serial.printf("\nFingerprint accuracy test: %s (e explicitly enrolls; scans do not change stored templates)\n",TEST_NAME);
    Serial.println("t <ID> + Enter = expected genuine ID / claimed verification ID; pauses scanning");
    Serial.println("g = GENUINE block; i = IMPOSTOR block; a = automatic counts; m = manual tally");
    Serial.println("1 = attempt only; 2 = expected success + attempt; 3 = failure + attempt (manual only)");
    Serial.println("Physical ENROLL/DELETE/MENU = 1/2/3 in THIS test firmware. No destructive actions.");
    Serial.println("s = summaries; h = help/headers; p = pause; r = resume; b = baud probe; n = new session/clear RAM counts");
    Serial.println("q = one fresh-capture diagnostic; cycles selected Search, direct Match, full Search; no accuracy counts");
    Serial.println("e = enroll a new finger in an empty slot; publishes old counts and starts a new session");
    Serial.println("z = read RTC; w = 10-second ticking check; k YYYY-MM-DDTHH:MM:SS + Enter = set RTC/new session");
    Serial.println(ACCURACY_VERIFICATION?
      "Genuine = the selected finger; impostor = a DIFFERENT finger (enrolled elsewhere or unenrolled).":
      "Genuine = finger enrolled in selected expected ID; impostor = a finger NOT enrolled anywhere in the gallery.");
    Serial.println("For 1:N, a wrong returned identity counts FN plus wrong_id, not TP. Errors/unclassified remain outside TP/FP/FN/TN.");
    Serial.println("Counters live in RAM; capture serial output before reset/unplugging. No confidence percentage is used.");
  }
  bool startCase(Truth truth) {
    diagnostic_=false; running_=false; caseSet_=false;
    if ((truth==Truth::Genuine || ACCURACY_VERIFICATION) && !hasTarget_) {
      Serial.println("ACCERROR select an expected/claimed ID with t <ID> + Enter first."); return false;
    }
    if (!freezeGallery()) return false;
    if ((truth==Truth::Genuine || ACCURACY_VERIFICATION) && !targetOccupied()) {
      Serial.println("ACCERROR expected/claimed ID is empty or out of range."); return false;
    }
    truth_=truth; caseSet_=true; running_=true; gate_.reset(); announced_=false; pollFailures_=0;
    polledAt_=millis()-100;
    Serial.printf("ACCCONFIG session=%08lX-%lu test=%s source=%s case=%s expected_or_claimed=%d security=%u gallery=%u capacity=%u system_id=%u address=%08lX inventory_crc32=%08lX baud=%lu\n",
      static_cast<unsigned long>(boot_),static_cast<unsigned long>(session_),TEST_NAME,sourceName(source_),truthName(truth_),
      hasTarget_?target_:-1,frozen_.security,frozen_.stored,frozen_.capacity,frozen_.systemId,
      static_cast<unsigned long>(frozen_.address),static_cast<unsigned long>(fingerprint::crc32(inventory_,(frozen_.capacity+7U)/8U)),
      static_cast<unsigned long>(connectedBaud));
    Serial.println("Lift finger once to arm this block, then present fingers repeatedly. No result-entry key required in auto mode.");
    return true;
  }
  void summary() const {
    for (unsigned s=0;s<2;++s) {
      const auto source=static_cast<Source>(s);
      summaryRow(source,"genuine",stats_.buckets[s][0]); summaryRow(source,"impostor",stats_.buckets[s][1]);
      summaryRow(source,"combined",stats_.combined(source));
    }
  }
  void tally(unsigned key) {
    if (source_!=Source::Manual || !caseSet_) {
      Serial.println("ACCIGNORED manual keys require m plus a configured g/i block; auto counts are never incremented by these keys."); return;
    }
    Outcome outcome=Outcome::Unclassified;
    if (key==1) outcome=truth_==Truth::Genuine?Outcome::Accepted:Outcome::Rejected;
    if (key==2) outcome=truth_==Truth::Genuine?Outcome::Rejected:Outcome::Accepted;
    trial(Source::Manual,truth_,outcome,"operator",0,-1,-1,-1,false);
  }
  // Nonblocking command parser. Target entry never steals digits as tally keys.
  void command(int key) {
    if (clock_.entering()) { clock_.consume(key); return; }
    if (key=='P') key='p';
    if (enrollment_!=Enrollment::Idle) {
      if (key=='p') stopEnrollment("cancelled");
      else if (key=='s') summary();
      else if (key=='h' || key=='?') { help(); headers(); }
      return; // Tally and configuration keys cannot alter an enrollment in progress.
    }
    if (enteringTarget_) {
      if (key=='\r') return;
      if (key=='\n') {
        enteringTarget_=false; config_[configLength_]=0;
        uint32_t value=0; const char *text=config_; while (*text==' ') ++text;
        if (configOverflow_ || !fingerprint::parseNumber(text,value,10) ||
            !fingerprint::onlyWhitespace(text) || value>65535) {
          Serial.println("ACCERROR invalid target; previous target unchanged. Use t <ID> + Enter."); return;
        }
        target_=value; hasTarget_=true;
        Serial.printf("ACCTARGET %u selected. Send g or i to start a block.\n",target_); return;
      }
      if (configLength_+1<sizeof(config_)) config_[configLength_++]=key;
      else configOverflow_=true;
      return;
    }
    if (key>='A' && key<='Z') key+=32;
    switch(key) {
    case 'z': clock_.record(boot_,session_,TEST_NAME,0,"check"); break;
    case 'w': clock_.watch(); break;
    case 'k': command('n'); clock_.startSet(); break;
    case 'e': beginEnrollment(); break;
    case 't': diagnostic_=false; enteringTarget_=true; configLength_=0; configOverflow_=false; configAt_=millis(); running_=caseSet_=false;
      Serial.println("ACCTARGET Enter occupied ID then Enter (15 s). Scanning paused."); break;
    case 'g': startCase(Truth::Genuine); break;
    case 'i': startCase(Truth::Impostor); break;
    case 'a': case 'm': source_=key=='a'?Source::Automatic:Source::Manual;
      Serial.printf("ACCMODE %s (separate counters).\n",sourceName(source_));
      if (caseSet_) startCase(truth_);
      break;
    case '1': case '2': case '3': tally(key-'1'); break;
    case 's': summary(); break;
    case 'h': case '?': help(); headers(); break;
    case 'q':
      running_=caseSet_=diagnostic_=false;
      if (!hasTarget_ || !freezeGallery() || !targetOccupied()) {
        Serial.println("ACCDIAG select a valid occupied ID with t <ID> first."); break;
      }
      diagnosticOrder_=nextDiagnosticOrder_; nextDiagnosticOrder_=(nextDiagnosticOrder_+1)%3;
      diagnostic_=true; diagnosticAt_=millis(); polledAt_=millis()-100; gate_.reset();
      Serial.printf("ACCDIAG armed target=%u method=%s; lift then place finger within 20 s. Counters unchanged. p cancels.\n",
        target_,diagnosticOrder_==1?"selected_search":diagnosticOrder_==2?"direct_match":"full_search");
      break;
    case 'p': diagnostic_=false; running_=false; Serial.println("ACCPAUSED r resumes; counters retained."); break;
    case 'r': if (caseSet_) startCase(truth_); else Serial.println("ACCERROR choose g or i first."); break;
    case 'b': diagnostic_=false; running_=false; probeScanner(); break;
    case 'n': diagnostic_=false; summary(); stats_=Statistics(); ++session_; event_=0; caseSet_=running_=frozenOK_=false;
      memset(inventory_,0,sizeof(inventory_)); gate_.reset();
      Serial.println("ACCNEWSESSION RAM counters cleared; select g or i. Gallery/settings will be read afresh."); break;
    default: break;
    }
  }
  void tick() {
    clock_.tick(boot_,session_,TEST_NAME);
    if (clock_.entering()) return;
    if (enrollment_!=Enrollment::Idle) { tickEnrollment(); return; }
    if (enteringTarget_ && millis()-configAt_>=15000) {
      enteringTarget_=false; Serial.println("ACCERROR target entry timed out; scanning remains paused.");
    }
    if (diagnostic_ && millis()-diagnosticAt_>=20000) {
      diagnostic_=false; Serial.println("ACCDIAG timed out; paused. No trial counted.");
    }
    if ((!running_ && !diagnostic_) || enteringTarget_ || millis()-polledAt_<100) return;
    polledAt_=millis();
    const uint8_t image[]={1}; const uint32_t started=millis();
    const auto captured=query(image,sizeof(image));
    if (captured.error!=QueryError::None || captured.reply.length!=1 ||
        (captured.reply.payload[0]!=0 && captured.reply.payload[0]!=2 && captured.reply.payload[0]!=3)) {
      if (diagnostic_) {
        diagnostic_=false; diagnosticReply("image_poll_failed",captured); return;
      }
      ++stats_.get(source_,truth_).pollErrors;
      Serial.println("ACCPOLLERROR no presentation established; excluded from attempts/confusion matrix.");
      if (++pollFailures_>=3) { running_=false; Serial.println("ACCPAUSED repeated poll errors; check wiring, b to probe, r to resume."); }
      return;
    }
    pollFailures_=0;
    if (captured.reply.payload[0]==2) gate_.noFinger();
    if (!gate_.ready(millis())) return;
    if (diagnostic_) {
      if (captured.reply.payload[0]!=2) diagnoseImage(captured);
      return;
    }
    if (!announced_) { announced_=true; Serial.println("ACCREADY place next finger; no key required."); }
    if (captured.reply.payload[0]!=2) processImage(captured,started);
  }
  const Statistics &statistics() const { return stats_; }
  bool running() const { return running_; }
  uint16_t target() const { return target_; }
};
} // namespace accuracy
