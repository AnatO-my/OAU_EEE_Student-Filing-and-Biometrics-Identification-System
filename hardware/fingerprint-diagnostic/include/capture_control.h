#pragma once

namespace terminal {
enum class CaptureEvent { None, Prepared, Armed, Saved, Retry, Stopped, Exported, Error, Cancelled };
// The UI owns scheduling. No local matching may run while this port captures.
class CaptureControl {
public:
  virtual ~CaptureControl() {}
  virtual bool prepared() const=0;
  virtual bool armed() const=0;
  virtual unsigned savedCount() const=0;
  virtual const char *batchId() const=0;
  virtual const char *classId() const=0;
  virtual const char *message() const=0;
  virtual CaptureEvent takeEvent()=0;
  virtual bool startSelected()=0;
  virtual bool nextBatch()=0;
  virtual void stop()=0;
  virtual void tick()=0;
  virtual void storageChanged() {}
  virtual bool wirelessAvailable() const { return false; }
  virtual bool requestWirelessExport() { return false; }
  virtual bool requestWirelessLog() { return false; }
};
} // namespace terminal
