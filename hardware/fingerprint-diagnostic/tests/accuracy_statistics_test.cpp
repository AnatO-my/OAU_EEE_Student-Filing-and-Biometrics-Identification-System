#include <assert.h>
#include "accuracy_statistics.h"
using namespace accuracy;
int main() {
  Statistics s;
  auto &g=s.get(Source::Automatic,Truth::Genuine);
  g.add(Truth::Genuine,Outcome::Accepted); g.add(Truth::Genuine,Outcome::Rejected);
  g.add(Truth::Genuine,Outcome::WrongIdentity); g.add(Truth::Genuine,Outcome::AcquisitionError);
  g.add(Truth::Genuine,Outcome::CommunicationError); g.add(Truth::Genuine,Outcome::SensorError);
  g.add(Truth::Genuine,Outcome::Unclassified);
  assert(g.attempts==7 && g.tp==1 && g.fn==2 && g.wrongId==1 && g.completed()==3 && g.correct()==1);
  assert(g.fp==0 && g.tn==0 && g.acquisition==1 && g.communication==1 && g.sensor==1 && g.unclassified==1);
  auto &i=s.get(Source::Automatic,Truth::Impostor);
  i.add(Truth::Impostor,Outcome::Accepted); i.add(Truth::Impostor,Outcome::Rejected);
  assert(i.attempts==2 && i.fp==1 && i.tn==1 && i.tp==0 && i.fn==0);
  const auto combined=s.combined(Source::Automatic);
  assert(combined.attempts==9 && combined.completed()==5 && combined.correct()==2);
  assert(s.combined(Source::Manual).attempts==0);
  assert(combined.attempts==combined.completed()+combined.acquisition+combined.communication+combined.sensor+combined.unclassified);
  Counts many; many.attempts=0xFFFFFFFFULL; many.tp=0xFFFFFFFFULL;
  many.add(Truth::Genuine,Outcome::Accepted); assert(many.attempts==0x100000000ULL && many.tp==0x100000000ULL);
  PresentationGate gate;
  assert(!gate.ready(0)); gate.noFinger(); assert(gate.ready(0));
  gate.finished(100); assert(!gate.ready(99999)); // A held finger never becomes another trial.
  gate.noFinger(); assert(!gate.ready(2099) && gate.ready(2100));
  gate.finished(0xFFFFFF00); gate.noFinger();
  assert(!gate.ready(0xFFFFFF00+1999U) && gate.ready(0xFFFFFF00+2000U));
  gate.reset(); assert(!gate.ready(99999));
}
