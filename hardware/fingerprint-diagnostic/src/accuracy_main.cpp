#include <Arduino.h>
#include "config.h"
#include <accuracy_inputs.h>

accuracy::Inputs accuracyInputs;
void serviceTerminalInputs() { accuracyInputs.poll(); }
#include "scanner_driver.h"
#include "accuracy_experiment.h"

accuracy::Experiment experiment;

void printReport() {
  accuracy::Settings value;
  if (!authenticated || !accuracy::settings(value)) {
    Serial.println("ACCERROR cannot read scanner configuration."); return;
  }
  Serial.printf("ACCSCANNER baud=%lu capacity=%u stored=%u security=%u system_id=%u address=%08lX\n",
    static_cast<unsigned long>(connectedBaud),value.capacity,value.stored,value.security,value.systemId,
    static_cast<unsigned long>(value.address));
}

void setup() {
  Serial.begin(CONSOLE_BAUD); accuracyInputs.begin(); delay(1500);
  probeScanner(); experiment.begin(accuracyInputs.bootNonce());
}
void loop() {
  accuracyInputs.poll();
  while (Serial.available()) { experiment.command(Serial.read()); accuracyInputs.suppress(); }
  for (unsigned i=0;i<3;++i) if (accuracyInputs.take(i)) experiment.tally(i);
  experiment.tick(); delay(5);
}
