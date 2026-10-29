#pragma once

// Included after the existing scanner/portable-transfer functions. This UI is
// the sole additional UART client and never runs during a serial command.
#include "terminal_logic.h"
#include "terminal_config.h"
#include "capture_control.h"
#include "terminal_feedback.h"
#include <terminal_hardware.h>

namespace terminal {
enum class State { Idle, First, Second, Third, Remove, DeleteScan, DeleteConfirm,
                   ClearHold, Clock, Notice, ModeConfirm };
enum class AfterLift { Second, Third, DeleteConfirm, Retry };
enum class AttendanceMode { Immediate, Deferred };

template <class Hardware> class AttendanceTerminal {
  Hardware &hw_;
  CaptureControl *capture_=nullptr;
  AttendanceMode mode_=AttendanceMode::Immediate,proposedMode_=AttendanceMode::Immediate;
  bool running_=true;
  Button keys_[3];
  bool ready_=false, paused_=false, countsOK_=false, clockOK_=false;
  bool mustLift_=true, dimmed_=false, todayOK_=false;
  State state_=State::Idle, retryState_=State::First;
  AfterLift after_=AfterLift::Second;
  unsigned page_=0, retries_=0, errors_=0, field_=0;
  uint16_t capacity_=0, stored_=0, target_=0;
  uint32_t stateAt_=0, pageAt_=0, activity_=0, scanAt_=0, clockAt_=0, drawAt_=0;
  uint32_t retryAt_=0, repeatAt_=0, today_=0, todayDate_=0;
  DateTime time_, edit_;
  Screen screen_;

  void line(unsigned row,const char *text) { snprintf(screen_.line[row],sizeof(screen_.line[row]),"%s",text); }
  void draw(const char *title,const char *detail,const char *footer="MENU=CANCEL") {
    screen_=Screen(); line(0,title); line(2,detail); line(SCREEN_FOOTER,footer); hw_.show(screen_);
    Serial.printf("UI: %s | %s | %s\n",title,detail,footer);
  }
  void suppress() { for (auto &key:keys_) key.suppress(); }
  void transition(State state) { state_=state; stateAt_=millis(); scanAt_=millis()-150; }
  void notice(const char *title,const char *detail,Feedback feedback=Feedback::Error) {
    transition(State::Notice); mustLift_=true; suppress(); draw(title,detail,"LIFT FINGER");
    hw_.notify(feedback);
  }
  void stopCapture() {
    if(capture_) { capture_->stop(); capture_->takeEvent(); }
  }
  void selectMode(AttendanceMode mode) {
    proposedMode_=mode; transition(State::ModeConfirm); suppress();
    draw(mode==AttendanceMode::Immediate?"USE IMMEDIATE MODE?":"USE DEFERRED MODE?",
      "Existing records kept","ENR=YES MENU=CANCEL");
  }
  bool startAttendance() {
    if(mode_==AttendanceMode::Deferred) {
      if(!capture_ || !capture_->startSelected()) {
        running_=false;
        if(capture_) capture_->takeEvent();
        notice("CAPTURE NOT STARTED",capture_?capture_->message():"Deferred unavailable"); return false;
      }
      capture_->takeEvent();
    } else if(capture_) {
      DateTime time; uint32_t count=0;
      if(!refresh() || !stored_) {
        running_=false; notice("CANNOT START","Check sensor / enroll"); return false;
      }
      if(!hw_.readClock(time)) {
        running_=false; notice("CANNOT START","Set / connect DS1307"); return false;
      }
      if(!hw_.todayCount(time,count)) {
        running_=false; notice("CANNOT START","Check log storage"); return false;
      }
    }
    running_=true; paused_=false; mustLift_=true; page_=0;
    hw_.notify(Feedback::Started); return true;
  }
  // Consume device results only at UI boundaries, never inside framed exports.
  void captureEvent() {
    if(!capture_) return;
    const auto event=capture_->takeEvent();
    if(event==CaptureEvent::None) return;
    if(event==CaptureEvent::Armed) {
      mode_=AttendanceMode::Deferred; running_=true; paused_=false; page_=0; state_=State::Idle;
      hw_.notify(Feedback::Started); pageScreen(); return;
    }
    if(event==CaptureEvent::Saved) {
      activity_=millis();
      // Remain in Idle: the capture controller enforces its own finger-lift gate.
      draw("CAPTURE SAVED","PENDING MATCH","LIFT FINGER");
      hw_.notify(Feedback::CaptureSaved); drawAt_=millis(); return;
    }
    if(event==CaptureEvent::Retry) {
      draw("TRY AGAIN","Lift and reposition","LIFT FINGER");
      hw_.notify(Feedback::Retry); drawAt_=millis(); return;
    }
    if(event==CaptureEvent::Error) {
      running_=false; draw("CAPTURE STOPPED",capture_->message(),"FILES RETAINED");
      hw_.notify(Feedback::Error); drawAt_=millis(); return;
    }
    if(event==CaptureEvent::Cancelled) {
      running_=false; draw("TRANSFER CANCELLED","Device files retained","No receipt confirmed");
      hw_.notify(Feedback::Cancelled); drawAt_=millis(); return;
    }
    if(event==CaptureEvent::Stopped) running_=false;
    if(event==CaptureEvent::Exported) {
      draw("EXPORT COMPLETE",capture_->message(),"Device files retained");
      hw_.notify(Feedback::Exported);
    } else if(event==CaptureEvent::Prepared) {
      draw("BATCH PREPARED","Select deferred mode","HOLD MENU 2S: MODES");
      hw_.notify(Feedback::ModeChanged);
    }
  }
  bool refresh() {
    countsOK_=authenticated && readLibraryStats(capacity_,stored_);
    return countsOK_;
  }
  bool op(const char *name,const uint8_t *cmd,size_t size) {
    return checkOperationAck(name,query(cmd,size,SENSOR_OPERATION_TIMEOUT_MS));
  }
  bool features(uint8_t buffer) {
    const uint8_t cmd[]={0x02,buffer}; return op("Img2Tz",cmd,sizeof(cmd));
  }
  // 1=match, 0=confirmed no-match, -1=error. Scores remain raw unitless values.
  int search(uint16_t &slot,uint16_t &score) {
    const uint8_t cmd[]={0x04,1,0,0,static_cast<uint8_t>(capacity_>>8),static_cast<uint8_t>(capacity_)};
    const auto result=query(cmd,sizeof(cmd),SENSOR_OPERATION_TIMEOUT_MS);
    if (result.error==QueryError::None && result.reply.payload[0]==9 &&
        (result.reply.length==1 || result.reply.length==5)) return 0;
    if (!checkQuery("Search",result) || result.reply.length!=5) return -1;
    slot=fingerprint::read16(result.reply.payload+1); score=fingerprint::read16(result.reply.payload+3);
    return slot<capacity_?1:-1;
  }
  bool occupied(uint16_t id,bool expected) {
    Reply table;
    if (id>=capacity_ || !readIndexPage(static_cast<uint8_t>(id/256),table)) return false;
    const bool used=(table.payload[1+(id%256)/8] & (1U<<(id%8)))!=0;
    return used==expected;
  }
  void removeFor(AfterLift after) {
    after_=after; transition(State::Remove); draw("LIFT FINGER","Remove completely");
  }
  void scanPrompt(State state) {
    transition(state);
    draw(state==State::First?"ENROLL 1 OF 3":state==State::Second?"ENROLL 2 OF 3":
         state==State::Third?"ENROLL 3 OF 3":"DELETE FINGER", "Place SAME finger");
  }
  bool cancelled() {
    pollInputs();
    if (keys_[2].take()) { cancel(); return true; }
    return false;
  }
  void retryScan() {
    if (++retries_>=5) { notice("ENROLL FAILED","Too many bad scans"); return; }
    retryState_=state_; removeFor(AfterLift::Retry);
    draw("TRY AGAIN","Lift finger first"); hw_.notify(Feedback::Retry);
  }
  void enroll() {
    stopCapture();
    if(mode_==AttendanceMode::Deferred) running_=false;
    if (!refresh() || !findFreeSlot(capacity_,stored_,target_)) {
      notice("CANNOT ENROLL","Check sensor / slots"); return;
    }
    retries_=0; suppress(); scanPrompt(State::First);
  }
  void startDelete() {
    stopCapture();
    if(mode_==AttendanceMode::Deferred) running_=false;
    if (!refresh() || !stored_) { notice("CANNOT DELETE","No verified templates"); return; }
    suppress(); scanPrompt(State::DeleteScan);
  }
  void saveEnrollment() {
    // All three presentations must succeed before a persistent command.
    if (cancelled()) return;
    if (!slotStillFree(target_)) { notice("NOT SAVED","Slot check failed"); return; }
    if (cancelled()) return;
    const uint16_t before=stored_;
    const uint8_t store[]={6,1,static_cast<uint8_t>(target_>>8),static_cast<uint8_t>(target_)};
    if (!op("Store",store,sizeof(store)) || !refresh() || stored_!=before+1 || !occupied(target_,true)) {
      countsOK_=false;
      notice("SAVE UNCONFIRMED","Check l / r before retry"); return;
    }
    char msg[40]; snprintf(msg,sizeof(msg),"Saved slot %u",target_);
    notice("ENROLLED",msg,Feedback::Enrolled);
  }
  void captured() {
    mustLift_=true;
    if (state_==State::First) {
      if (!features(1)) { retryScan(); return; }
      uint16_t slot=0,score=0;
      const int result=stored_?search(slot,score):0;
      if (result<0) { notice("ENROLL FAILED","Duplicate check failed"); return; }
      if (result>0) {
        char msg[40]; snprintf(msg,sizeof(msg),"Already in slot %u",slot);
        notice("ALREADY ENROLLED",msg,Feedback::Duplicate); return;
      }
      removeFor(AfterLift::Second);
    } else if (state_==State::Second) {
      if (!features(2)) { retryScan(); return; }
      const uint8_t combine[]={5};
      if (!op("RegModel",combine,sizeof(combine))) { notice("ENROLL FAILED","Scans did not agree"); return; }
      removeFor(AfterLift::Third);
    } else if (state_==State::Third) {
      if (!features(2)) { retryScan(); return; }
      const uint8_t match[]={3};
      const auto result=query(match,sizeof(match),SENSOR_OPERATION_TIMEOUT_MS);
      if (!checkQuery("Match third scan",result) || result.reply.length!=3) {
        notice("ENROLL FAILED","Third scan not verified"); return;
      }
      Serial.printf("Third-scan match score=%u (raw, unitless).\n",fingerprint::read16(result.reply.payload+1));
      saveEnrollment();
    } else if (state_==State::DeleteScan) {
      uint16_t score=0;
      if (!features(1)) { notice("NOT DELETED","Unreadable fingerprint"); return; }
      const int result=search(target_,score);
      if (result!=1) { notice("NOT DELETED",result==0?"Finger not registered":"Search failed"); return; }
      removeFor(AfterLift::DeleteConfirm);
    }
  }
  void confirmDelete() {
    if (!refresh() || !occupied(target_,true) || cancelled()) {
      if (state_!=State::Idle) notice("NOT DELETED","Slot check failed");
      return;
    }
    const uint16_t before=stored_;
    const uint8_t cmd[]={0x0C,static_cast<uint8_t>(target_>>8),static_cast<uint8_t>(target_),0,1};
    if (!op("DeleteChar",cmd,sizeof(cmd)) || !refresh() || stored_+1!=before || !occupied(target_,false)) {
      countsOK_=false;
      notice("DELETE UNCONFIRMED","Check l / r"); return;
    }
    notice("DELETED","Check-in history kept",Feedback::Deleted);
  }
  void clearLibrary() {
    if (!refresh()) { notice("ERASE FAILED","Cannot read library"); return; }
    if (cancelled()) return;
    const uint8_t cmd[]={0x0D};
    if (!op("Empty",cmd,sizeof(cmd)) || !refresh() || stored_!=0) {
      countsOK_=false;
      notice("ERASE UNCONFIRMED","Check l / r"); return;
    }
    notice("LIBRARY ERASED","Check-in history kept",Feedback::Deleted);
  }
  void mark(uint16_t slot,uint16_t score) {
    Serial.printf("MATCH: template ID=%u; score=%u (raw, unitless).\n",slot,score);
    DateTime capturedTime;
    if (!hw_.readClock(capturedTime)) { notice("MATCHED / NOT SAVED","Set / connect DS1307"); return; }
    TemplateParameters parameters;
    static fingerprint::SensorTemplate data;
    char hash[65]={};
    const uint8_t load[]={7,1,static_cast<uint8_t>(slot>>8),static_cast<uint8_t>(slot)};
    if (!readTemplateParameters(parameters) || !op("LoadChar",load,sizeof(load)) ||
        !receiveTemplate(data,parameters) || !hw_.hashTemplate(data.bytes,data.length,hash)) {
      data.clear(); notice("MATCHED / NOT SAVED","Template hash failed"); return;
    }
    data.clear();
    if (cancelled()) return;
    const auto result=hw_.record(capturedTime,slot,score,hash);
    todayOK_=hw_.todayCount(capturedTime,today_); todayDate_=dateKey(capturedTime);
    switch(result) {
    case LogResult::Saved: notice("ATTENDANCE SAVED","Local record saved",Feedback::AttendanceSaved); break;
    case LogResult::Already: notice("ALREADY CHECKED IN","Same template / date",Feedback::Duplicate); break;
    case LogResult::Full: notice("MATCHED / NOT SAVED","Log full: export first"); break;
    case LogResult::Corrupt: notice("MATCHED / NOT SAVED","Log damaged: inspect"); break;
    case LogResult::WriteFailed: notice("MATCHED / NOT SAVED","Log write failed"); break;
    default: notice("MATCHED / NOT SAVED","Storage unavailable"); break;
    }
  }
  void idleScan() {
    const uint8_t capture[]={1};
    const auto result=query(capture,sizeof(capture));
    if (result.error!=QueryError::None || result.reply.length!=1) {
      if (++errors_>=3) { authenticated=false; countsOK_=false; }
      return;
    }
    errors_=0;
    const uint8_t code=result.reply.payload[0];
    if (code==2) { mustLift_=false; return; }
    if (mustLift_) return;
    mustLift_=true;
    if (code!=0) { checkQuery("GenImg",result); notice("SCAN FAILED","Lift and reposition"); return; }
    activity_=millis();
    if (!countsOK_ && !refresh()) { notice("SCAN FAILED","Cannot read library"); return; }
    if (!stored_) { notice("NO TEMPLATES","Press ENROLL first",Feedback::Duplicate); return; }
    uint16_t slot=0,score=0;
    if (!features(1)) { notice("SCAN FAILED","Lift and reposition"); return; }
    const int matched=search(slot,score);
    if (cancelled()) return;
    if (matched==1) mark(slot,score);
    else notice(matched==0?"NO MATCH":"SCAN FAILED","Lift and retry");
  }
  void clockScreen() {
    static const char *names[]={"YEAR","MONTH","DAY","HOUR","MINUTE"};
    char text[22];
    const unsigned values[]={edit_.year,edit_.month,edit_.day,edit_.hour,edit_.minute};
    snprintf(text,sizeof(text),"%s: %u",names[field_],values[field_]);
    draw("SET CLOCK",text,"ENR+ DEL- MENU>NEXT");
  }
  void adjust(int step) {
    unsigned value=0,lo=0,hi=0;
    switch(field_) {
      case 0: value=edit_.year; lo=2000; hi=2099; break;
      case 1: value=edit_.month; lo=1; hi=12; break;
      case 2: value=edit_.day; lo=1; hi=daysIn(edit_.year,edit_.month); break;
      case 3: value=edit_.hour; hi=23; break;
      default: value=edit_.minute; hi=59; break;
    }
    value=step>0?(value==hi?lo:value+1):(value==lo?hi:value-1);
    switch(field_) { case 0: edit_.year=value; break; case 1: edit_.month=value; break;
      case 2: edit_.day=value; break; case 3: edit_.hour=value; break; default: edit_.minute=value; }
    const uint8_t limit=daysIn(edit_.year,edit_.month); if (edit_.day>limit) edit_.day=limit;
    stateAt_=activity_=repeatAt_=millis(); clockScreen();
  }
  const char *readiness() const {
    if (!authenticated) return "CHECK SENSOR WIRING";
    if (countsOK_ && !stored_) return "ENROLL A FINGER";
    if (!countsOK_) return "CHECK SCANNER STATUS";
    if (!clockOK_) return "SET CLOCK TO RECORD";
    if (!todayOK_) return "CHECK LOG STORAGE";
    return "READY FOR ATTENDANCE";
  }
  void pageScreen(bool announce=false) {
    screen_=Screen();
    const char *titles[]={"ATTENDANCE","STATISTICS","EXPORT LOG","SET CLOCK","SYSTEM","ERASE FINGERPRINTS",
      "ATTENDANCE MODE","START / STOP","DEFERRED CLASS BATCH"};
    line(0,titles[page_]);
    char text[40];
    if (page_==0) {
      // Home fits six lines. Template totals remain available on Statistics.
      line(1,mustLift_?"Lift finger first":"Place finger");
      if (clockOK_) { stamp(time_,text,sizeof(text)); line(2,text); }
      else line(2,"RTC UNSET / ABSENT");
      line(3,readiness());
      if (todayOK_) snprintf(text,sizeof(text),"Today records: %lu",static_cast<unsigned long>(today_));
      else snprintf(text,sizeof(text),"Local log unavailable");
      line(4,text); line(SCREEN_FOOTER,"ENR DEL MENU");
      if(capture_) {
        line(0,mode_==AttendanceMode::Immediate?"IMMEDIATE ATTENDANCE":"DEFERRED CAPTURE");
        line(1,running_?(mustLift_?"RUN: LIFT FINGER":"RUN: PLACE FINGER"):"STOPPED: MENU > START");
        if(mode_==AttendanceMode::Deferred) {
          if(running_) line(1,"RUNNING: LIFT FINGER");
          snprintf(text,sizeof(text),"Saved: %u PENDING",capture_->savedCount()); line(2,text);
          line(3,"No identity decision");
          line(4,capture_->prepared()?"Class batch prepared":"PREPARE CLASS VIA USB");
        }
      }
    } else if (page_==1) {
      if(capture_ && mode_==AttendanceMode::Deferred) {
        line(0,"DEFERRED STATISTICS"); line(1,"Time: boot-relative");
        snprintf(text,sizeof(text),"Captures: %u PENDING",capture_->savedCount()); line(2,text);
        line(3,"Not a presence count");
        line(4,capture_->prepared()?"Class batch prepared":"PREPARE CLASS VIA USB");
      } else {
        if(clockOK_) { stamp(time_,text,sizeof(text)); line(1,text); }
        else line(1,"RTC UNSET / ABSENT");
        if(countsOK_) snprintf(text,sizeof(text),"Templates: %u/%u",stored_,capacity_);
        else snprintf(text,sizeof(text),"%s",authenticated?"Counts unavailable":"Sensor unavailable");
        line(2,text);
        if(todayOK_) snprintf(text,sizeof(text),"Today records: %lu",static_cast<unsigned long>(today_));
        else snprintf(text,sizeof(text),"Local log unavailable");
        line(3,text); line(4,readiness());
      }
      line(SCREEN_FOOTER,"MENU=NEXT");
    } else if (page_==2) {
      if(capture_ && mode_==AttendanceMode::Deferred) {
        line(0,"DEFERRED EXPORT"); line(2,"Download batch via USB");
        line(3,"Device files retained");
        line(4,capture_->wirelessAvailable()?"DEL: SEND VIA WI-FI":"USB downloader needed");
        line(SCREEN_FOOTER,"ENR=HELP MENU=NEXT");
      } else { line(2,"Print CSV over USB");
        if(capture_ && capture_->wirelessAvailable()) line(4,"DEL: CSV VIA WI-FI");
        line(SCREEN_FOOTER,"ENR=EXPORT MENU>NEXT"); }
    }
    else if (page_==3) { line(2,"No automatic default"); line(SCREEN_FOOTER,"ENR=SET MENU>NEXT"); }
    else if (page_==4) {
      snprintf(text,sizeof(text),"UART: %lu",static_cast<unsigned long>(connectedBaud)); line(1,text);
      snprintf(text,sizeof(text),"RTC:%s OLED:%s",clockOK_?"OK":"ERR",hw_.oledOK?"OK":"OFF"); line(2,text);
      line(3,hw_.fsOK?"LittleFS mounted":"LittleFS unavailable"); line(SCREEN_FOOTER,"MENU=NEXT");
    } else if(page_==5) { line(2,"HOLD DELETE FOR 3S"); line(4,"Check-in logs kept"); line(SCREEN_FOOTER,"MENU=HOME"); }
    else if(page_==6) {
      line(2,"ENR: IMMEDIATE"); line(3,"DEL: DEFERRED");
      line(4,"Confirm before start"); line(SCREEN_FOOTER,"MENU=NEXT");
    } else if(page_==7) {
      line(2,running_?"ENR: STOP ATTENDANCE":"ENR: START ATTENDANCE");
      line(4,mode_==AttendanceMode::Immediate?"Mode: IMMEDIATE":"Mode: DEFERRED"); line(SCREEN_FOOTER,"MENU=NEXT");
    } else {
      line(1,"ENR: NEXT SAVED BATCH");
      if(capture_ && capture_->prepared()) {
        const char *id=capture_->classId(); line(0,"CLASS SESSION UUID");
        snprintf(text,sizeof(text),"%.18s",id); line(2,text);
        line(3,id+18); snprintf(text,sizeof(text),"Saved captures: %u",capture_->savedCount()); line(4,text);
      } else line(3,"PREPARE CLASS VIA USB");
      line(SCREEN_FOOTER,"MENU=HOME");
    }
    hw_.show(screen_);
    if (announce) Serial.printf("UI: %s | %s | %s\n",screen_.line[0],screen_.line[2],screen_.line[SCREEN_FOOTER]);
  }
  void reconnect() {
    if (millis()-retryAt_<5000) return;
    retryAt_=millis();
    if (!connectedBaud) { scanner.begin(57600,SERIAL_8N1,FINGERPRINT_RX_PIN,FINGERPRINT_TX_PIN); }
    uint8_t cmd[5]={0x13}; fingerprint::write32(cmd+1,FINGERPRINT_PASSWORD);
    const auto response=query(cmd,sizeof(cmd));
    if (response.error==QueryError::None && response.reply.length==1 && response.reply.payload[0]==0) {
      authenticated=true; errors_=0; if (!connectedBaud) connectedBaud=57600; refresh();
      mustLift_=true; Serial.println("UI: sensor reconnected.");
    }
  }
public:
  explicit AttendanceTerminal(Hardware &hw,CaptureControl *capture=nullptr):hw_(hw),capture_(capture),running_(!capture) {}
  void begin() {
    hw_.begin(); ready_=true; pollInputs(); suppress(); refresh();
    stateAt_=pageAt_=activity_=millis(); clockAt_=millis()-1000;
    Serial.println("UI ready: 1=ENROLL, 2=DELETE, 3=MENU; a=resume UI; p=pause UI.");
    Serial.println("Immediate mode matches enrolled fingers; deferred mode saves unidentified probes. MENU selects mode, start/stop and prepared class batch.");
    Serial.println("Attendance records stay on this device until exported; no website attendance is submitted by this firmware.");
    Serial.println("Existing diagnostic/backup commands pause UI until a. f formats local log storage after FORMAT confirmation.");
    if(authenticated) pageScreen(true);
    else draw("STARTING...","Checking scanner","PLEASE WAIT");
  }
  void bootReady() { suppress(); refresh(); pageScreen(true); }
  // Safe to call inside UART waits: no I2C, file I/O, serial output or scanner commands.
  void pollInputs() {
    if (!ready_) return;
    for (unsigned i=0;i<3;++i) keys_[i].sample(hw_.button(i),millis());
    // A fresh control press may disarm capture during a bounded UART wait.
    // stop() only changes controller state; it performs no I/O or scanner command.
    if(capture_ && running_ && mode_==AttendanceMode::Deferred)
      for(const auto &key:keys_) if(key.active() && key.down()) capture_->stop();
    hw_.tick();
  }
  void pause() {
    stopCapture(); if(capture_) running_=false;
    paused_=true; state_=State::Idle; mustLift_=true; countsOK_=false; suppress(); hw_.off();
    Screen pausedScreen; snprintf(pausedScreen.line[0],22,"ATTENDANCE PAUSED");
    snprintf(pausedScreen.line[2],22,"Serial maintenance");
    snprintf(pausedScreen.line[SCREEN_FOOTER],22,"%s",capture_?"HOLD MENU 2S: MODES":"SEND A TO RESUME"); hw_.show(pausedScreen);
  }
  void resume() {
    paused_=false; state_=State::Idle; page_=0; mustLift_=true; suppress(); refresh();
    if(capture_ && !startAttendance()) return;
    todayDate_=0; pageAt_=activity_=millis(); pageScreen(true);
  }
  void cancel() {
    state_=State::Idle; page_=0; mustLift_=true; suppress();
    pageAt_=activity_=millis(); hw_.notify(Feedback::Cancelled);
    Serial.println("UI: action cancelled; lift finger."); pageScreen();
  }
  void key(unsigned key) {
    if (paused_) resume();
    activity_=millis(); hw_.notify(Feedback::Click);
    if(state_==State::ModeConfirm) {
      if(key==2) { cancel(); return; }
      if(key==0) {
        stopCapture(); mode_=proposedMode_; state_=State::Idle; suppress();
        if(startAttendance()) { pageAt_=millis(); pageScreen(true); }
      }
      return;
    }
    if (key==2 && state_!=State::Idle && state_!=State::Clock) { cancel(); return; }
    if (state_==State::Clock) {
      if (key<2) adjust(key==0?1:-1);
      else if (++field_==5) {
        edit_.second=0;
        if (hw_.setClock(edit_)) { clockAt_=millis()-1000; todayDate_=0; notice("CLOCK SAVED","Readback verified",Feedback::ClockSaved); }
        else notice("CLOCK NOT SAVED","Check DS1307 wiring");
      } else { suppress(); repeatAt_=millis(); stateAt_=millis(); clockScreen(); }
      return;
    }
    if (state_==State::DeleteConfirm && key==1) { confirmDelete(); return; }
    if (state_!=State::Idle) return;
    pageAt_=millis();
    if (key==2) {
      if(capture_ && mode_==AttendanceMode::Deferred) { stopCapture(); running_=false; }
      page_=(page_+1)%(capture_?9:6); pageScreen(true); return;
    }
    if(page_==6 && capture_) { selectMode(key==0?AttendanceMode::Immediate:AttendanceMode::Deferred); return; }
    if(page_==7 && capture_) {
      if(key!=0) return;
      if(running_) { stopCapture(); running_=false; hw_.notify(Feedback::Stopped); }
      else if(!startAttendance()) return;
      pageAt_=millis(); pageScreen(true); return;
    }
    if(page_==8 && capture_) {
      if(key!=0) return;
      stopCapture(); running_=false;
      if(!capture_->nextBatch()) { notice("NO PREPARED BATCH","Prepare class via USB"); return; }
      capture_->takeEvent(); hw_.notify(Feedback::ModeChanged); pageScreen(true); return;
    }
    if(page_==2 && key==1 && capture_ && capture_->wirelessAvailable()) {
      stopCapture(); running_=false;
      if(!capture_->wirelessAvailable()) { notice("WI-FI UNAVAILABLE","Configure over USB"); return; }
      const bool queued=mode_==AttendanceMode::Deferred?capture_->requestWirelessExport():capture_->requestWirelessLog();
      notice(queued?"WI-FI TRANSFER":"TRANSFER NOT STARTED",queued?"MENU cancels; kept":"Check Wi-Fi setup",queued?Feedback::ModeChanged:Feedback::Error);
      return;
    }
    if (key==0) {
      if(page_==2 && capture_ && mode_==AttendanceMode::Deferred) {
        notice("CONNECT USB LAPTOP","Use batch downloader",Feedback::ModeChanged);
      }
      else if (page_==2) { const bool ok=hw_.exportLog(); notice(ok?"LOG EXPORTED":"EXPORT FAILED",ok?"USB output complete":"Storage unavailable",ok?Feedback::Exported:Feedback::Error); }
      else if (page_==3) {
        edit_=DateTime(); hw_.readClock(edit_); field_=0; suppress(); transition(State::Clock); clockScreen();
      } else enroll();
    } else if (page_==5) {
      // Only a fresh physical press can start the destructive hold.
      if (!keys_[1].active()) { Serial.println("UI: use physical DELETE hold, or serial d then ERASE."); return; }
      transition(State::ClearHold); draw("ERASE FINGERPRINTS","Keep DELETE held 3s");
    } else startDelete();
  }
  void formatStorage() {
    pause();
    Serial.println("Formats LittleFS: deletes ALL local check-ins AND pending capture batches. Sensor templates are unaffected. Type FORMAT then Enter within 15 seconds.");
    char confirm[16]={};
    const uint32_t started=millis();
    bool read=false;
    while (readTemplateConsoleLine(confirm,sizeof(confirm),started)) {
      if (confirm[0]) { read=true; break; } // Allow Enter immediately after f.
    }
    if (!read || strcmp(confirm,"FORMAT")!=0) {
      Serial.println("Storage format cancelled."); return;
    }
    const bool formatted=hw_.formatStorage();
    if(formatted && capture_) capture_->storageChanged();
    Serial.println(formatted?"Storage formatted. Send a to resume UI.":"Storage format failed.");
    todayDate_=0; todayOK_=false;
  }
  void tick() {
    if (!ready_) return;
    pollInputs();
    captureEvent();
    if (paused_) {
      // tick() runs only after a serial command/frame completes. A fresh long
      // MENU hold may leave maintenance, but opens selection with capture off.
      if(capture_ && keys_[2].active() && keys_[2].down() && keys_[2].held(millis())>=2000) {
        paused_=false; running_=false; state_=State::Idle; page_=6; suppress();
        pageAt_=activity_=millis(); hw_.notify(Feedback::ModeChanged); pageScreen(true);
      }
      for (auto &key:keys_) { key.take(); }
      return;
    }
    // MENU wins if buttons are pressed together, including during erase hold.
    const bool e=keys_[0].take(), d=keys_[1].take(), m=keys_[2].take();
    if (m) key(2); else if (e && !d) key(0); else if (d && !e) key(1);
    const uint32_t now=millis();
    if (now-clockAt_>=1000) {
      clockAt_=now; clockOK_=hw_.readClock(time_);
      if (!clockOK_) { todayOK_=false; todayDate_=0; }
      if (clockOK_ && todayDate_!=dateKey(time_)) {
        todayDate_=dateKey(time_); todayOK_=hw_.todayCount(time_,today_);
      }
    }
    const bool dim=now-activity_>=DIM_AFTER;
    if (dim!=dimmed_) { dimmed_=dim; hw_.contrast(dim); }
    if (state_==State::Clock) {
      if (now-stateAt_>=60000) { cancel(); return; }
      for (unsigned i=0;i<2;++i) if (keys_[i].active() && keys_[i].down() &&
          !keys_[1-i].down() && keys_[i].held(now)>=500 && now-repeatAt_>=120) adjust(i==0?1:-1);
      return;
    }
    if (state_==State::ClearHold) {
      // Use raw release to cancel immediately; debounce can only delay a press.
      if (!keys_[1].rawDown()) { cancel(); return; }
      if (now-stateAt_>=CLEAR_HOLD) clearLibrary();
      return;
    }
    if (state_==State::DeleteConfirm) {
      if (now-stateAt_>=8000) notice("DELETE CANCELLED","Confirmation timed out",Feedback::Cancelled);
      return;
    }
    if (state_==State::Notice) {
      if (now-stateAt_>=2000) { state_=State::Idle; page_=0; suppress(); pageAt_=now; pageScreen(); }
      return;
    }
    if (state_!=State::Idle && now-stateAt_>=ACTION_TIMEOUT) {
      notice("ACTION TIMED OUT","Lift and retry",Feedback::Error); return;
    }
    if(state_==State::ModeConfirm) return;
    if (state_==State::Idle) {
      if (page_ && now-pageAt_>=PAGE_TIMEOUT) { page_=0; pageScreen(true); }
      if (now-drawAt_>=1000) { drawAt_=now; pageScreen(); }
      if (!authenticated) { reconnect(); return; }
      if (page_ || now-scanAt_<150) return;
      if(capture_ && (!running_ || mode_==AttendanceMode::Deferred)) {
        if(running_ && mode_==AttendanceMode::Deferred) { capture_->tick(); captureEvent(); }
        return;
      }
      scanAt_=now; idleScan(); return;
    }
    if (now-scanAt_<150) return;
    scanAt_=now;
    const uint8_t cmd[]={1}; const auto result=query(cmd,sizeof(cmd));
    if (cancelled()) return;
    if (result.error!=QueryError::None || result.reply.length!=1) { notice("SENSOR ERROR","Check power / UART"); return; }
    const uint8_t code=result.reply.payload[0];
    if (state_==State::Remove) {
      if (code==2) {
        if (after_==AfterLift::DeleteConfirm) {
          suppress(); transition(State::DeleteConfirm); char msg[40];
          snprintf(msg,sizeof(msg),"Delete slot %u?",target_); draw("CONFIRM DELETE",msg,"DEL=YES MENU=CANCEL");
        } else scanPrompt(after_==AfterLift::Second?State::Second:after_==AfterLift::Third?State::Third:retryState_);
      } else if (code!=0) { checkQuery("GenImg removal",result); notice("REMOVAL FAILED","Lift and retry"); }
      return;
    }
    if (code==2) return;
    if (code!=0) {
      checkQuery("GenImg",result);
      if (code==3 && state_!=State::DeleteScan) retryScan();
      else notice("CAPTURE FAILED","Lift and retry");
      return;
    }
    captured();
  }
  State state() const { return state_; }
  bool paused() const { return paused_; }
  unsigned page() const { return page_; }
  AttendanceMode mode() const { return mode_; }
  bool running() const { return running_; }
};
} // namespace terminal
