#pragma once
#include <stdint.h>

namespace accuracy {
enum class Truth { Genuine, Impostor };
enum class Source { Automatic, Manual };
enum class Outcome { Accepted, Rejected, WrongIdentity, AcquisitionError,
                     CommunicationError, SensorError, Unclassified };

struct Counts {
  uint64_t attempts=0, tp=0, fp=0, fn=0, tn=0;
  uint64_t acquisition=0, communication=0, sensor=0, unclassified=0, wrongId=0;
  uint64_t pollErrors=0; // No presentation established; excluded from attempts.
  uint64_t completed() const { return tp+fp+fn+tn; }
  uint64_t correct() const { return tp+tn; }
  void add(Truth truth,Outcome outcome) {
    ++attempts;
    switch(outcome) {
    case Outcome::Accepted: if (truth==Truth::Genuine) ++tp; else ++fp; break;
    case Outcome::Rejected: if (truth==Truth::Genuine) ++fn; else ++tn; break;
    case Outcome::WrongIdentity: if (truth==Truth::Genuine) ++fn; else ++fp; ++wrongId; break;
    case Outcome::AcquisitionError: ++acquisition; break;
    case Outcome::CommunicationError: ++communication; break;
    case Outcome::SensorError: ++sensor; break;
    case Outcome::Unclassified: ++unclassified; break;
    }
  }
  Counts &operator+=(const Counts &b) {
    attempts+=b.attempts; tp+=b.tp; fp+=b.fp; fn+=b.fn; tn+=b.tn;
    acquisition+=b.acquisition; communication+=b.communication; sensor+=b.sensor;
    unclassified+=b.unclassified; wrongId+=b.wrongId; pollErrors+=b.pollErrors;
    return *this;
  }
};
struct Statistics {
  Counts buckets[2][2];
  Counts &get(Source source,Truth truth) { return buckets[static_cast<unsigned>(source)][static_cast<unsigned>(truth)]; }
  Counts combined(Source source) const {
    Counts c=buckets[static_cast<unsigned>(source)][0];
    c+=buckets[static_cast<unsigned>(source)][1]; return c;
  }
};
inline const char *truthName(Truth t) { return t==Truth::Genuine?"genuine":"impostor"; }
inline const char *sourceName(Source s) { return s==Source::Automatic?"auto":"manual"; }
inline const char *outcomeName(Outcome o) {
  switch(o) {
  case Outcome::Accepted: return "accepted";
  case Outcome::Rejected: return "rejected";
  case Outcome::WrongIdentity: return "wrong_identity";
  case Outcome::AcquisitionError: return "acquisition_error";
  case Outcome::CommunicationError: return "communication_error";
  case Outcome::SensorError: return "sensor_error";
  default: return "unclassified";
  }
}
inline const char *classification(Truth t,Outcome o) {
  if (o==Outcome::Accepted) return t==Truth::Genuine?"TP":"FP";
  if (o==Outcome::Rejected) return t==Truth::Genuine?"FN":"TN";
  if (o==Outcome::WrongIdentity) return "FN";
  return "NA";
}
// Exactly one new trial per presentation. Removal can occur during cooldown;
// it does not add another delay. A held finger never becomes another trial.
struct PresentationGate {
  bool cooling=false, removed=false;
  uint32_t ended=0;
  void reset() { cooling=false; removed=false; }
  void finished(uint32_t now) { cooling=true; removed=false; ended=now; }
  void noFinger() { removed=true; }
  bool ready(uint32_t now) const { return removed && (!cooling || static_cast<uint32_t>(now-ended)>=2000); }
};
} // namespace accuracy
