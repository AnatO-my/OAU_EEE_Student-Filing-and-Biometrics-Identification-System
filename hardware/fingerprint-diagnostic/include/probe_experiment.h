#pragma once

// Diagnostic only: fresh capture export and saved-probe search of ONE reference.
// Never invokes RegModel, Store, DeleteChar or Empty. Bytes stay in volatile buffers.
void printProbeBytes(const fingerprint::SensorTemplate &data) {
  for (size_t offset=0; offset<data.length; offset+=32) {
    char hex[65]={};
    const size_t count=data.length-offset<32?data.length-offset:32;
    for (size_t i=0;i<count;++i) snprintf(hex+2*i,3,"%02X",data.bytes[offset+i]);
    Serial.print("FPDATA "); Serial.println(hex);
  }
  Serial.printf("FPEND %u %08lX\n",static_cast<unsigned>(data.length),
      static_cast<unsigned long>(fingerprint::crc32(data.bytes,data.length)));
}

void captureProbe() {
  static fingerprint::SensorTemplate data;
  data.clear();
  TemplateParameters parameters;
  if (!authenticated || !readTemplateParameters(parameters)) { templateTransferError(); return; }
  Serial.println("FPSTEP Lift finger, then present it once when prompted; no enrollment or matching");
  if (!waitForFinger(false) || !waitForFinger(true)) { templateTransferError(); return; }
  const uint8_t features[]={0x02,1};
  if (!checkOperationAck("Img2Tz",query(features,sizeof(features),SENSOR_OPERATION_TIMEOUT_MS)) ||
      !receiveTemplate(data,parameters) || !data.length) {
    data.clear(); templateTransferError(); return;
  }
  Serial.printf("FPPROBE 1 %u %u %u %u %08lX\n",parameters.capacity,parameters.security,
      parameters.packetBytes,parameters.systemId,static_cast<unsigned long>(parameters.address));
  printProbeBytes(data);
  data.clear();
  Serial.println("FPSTEP Probe exported; host must save it. Lift finger. Gallery unchanged.");
}

void compareSavedProbe(bool direct=false) {
  char line[80];
  uint32_t slot=0,length=0,checksum=0;
  const char *cursor=line;
  TemplateParameters parameters;
  Reply table;
  if (!readTemplateConsoleLine(line,sizeof(line)) ||
      !fingerprint::parseNumber(cursor,slot,10) ||
      !fingerprint::parseNumber(cursor,length,10) ||
      !fingerprint::parseNumber(cursor,checksum,16) ||
      !fingerprint::onlyWhitespace(cursor) || !authenticated ||
      !length || length>fingerprint::MAX_TEMPLATE_BYTES || slot>65534 ||
      !readTemplateParameters(parameters) || slot>=parameters.capacity ||
      !readIndexPage(static_cast<uint8_t>(slot/256),table) ||
      !(table.payload[1+(slot%256)/8] & (1U<<(slot%8)))) {
    templateTransferError(); return;
  }
  static fingerprint::SensorTemplate data,verified;
  data.clear(); verified.clear();
  Serial.printf("%s %u %u %u %u %08lX\n",direct?"FPPROBEDIRECTREADY":"FPPROBEREADY",static_cast<unsigned>(slot),
      static_cast<unsigned>(length),parameters.security,parameters.systemId,
      static_cast<unsigned long>(parameters.address));
  const uint32_t started=millis();
  while (data.length<length) {
    if (!readTemplateConsoleLine(line,sizeof(line),started)) {
      data.clear(); templateTransferError(); return;
    }
    const size_t characters=strlen(line);
    if (!characters || characters%2 || characters>64 || data.length+characters/2>length) {
      data.clear(); templateTransferError(); return;
    }
    for (size_t i=0;i<characters;i+=2) {
      const int high=fingerprint::hexDigit(line[i]),low=fingerprint::hexDigit(line[i+1]);
      if (high<0 || low<0) { data.clear(); templateTransferError(); return; }
      data.bytes[data.length++]=static_cast<uint8_t>((high<<4)|low);
    }
  }
  if (fingerprint::crc32(data.bytes,data.length)!=checksum || !sendTemplate(data,parameters) ||
      !receiveTemplate(verified,parameters) || verified.length!=data.length ||
      memcmp(verified.bytes,data.bytes,data.length)) {
    Serial.println("Saved probe CRC/readback failed; no comparison result issued.");
    data.clear(); verified.clear(); templateTransferError(); return;
  }
  data.clear(); verified.clear();
  if (direct) {
    // Keep the downloaded probe in buffer 1; load the reference into buffer 2.
    const uint8_t load[]={0x07,2,static_cast<uint8_t>(slot>>8),static_cast<uint8_t>(slot)};
    if (!checkOperationAck("Load reference buffer 2",query(load,sizeof(load),SENSOR_OPERATION_TIMEOUT_MS))) {
      templateTransferError(); return;
    }
    const uint8_t match[]={0x03};
    const auto compared=query(match,sizeof(match),SENSOR_OPERATION_TIMEOUT_MS);
    if (compared.error==QueryError::None && compared.reply.payload[0]==0x08 &&
        (compared.reply.length==1 || compared.reply.length==3)) {
      Serial.printf("FPPROBEDIRECTRESULT %u NO_MATCH 0\n",static_cast<unsigned>(slot)); return;
    }
    if (!checkQuery("Compare buffers",compared) || compared.reply.length!=3) {
      templateTransferError(); return;
    }
    Serial.printf("FPPROBEDIRECTRESULT %u MATCH %u\n",static_cast<unsigned>(slot),
        fingerprint::read16(compared.reply.payload+1));
    return;
  }
  // Search buffer 1 over exactly the requested occupied slot; no fresh image.
  const uint8_t search[]={0x04,1,static_cast<uint8_t>(slot>>8),static_cast<uint8_t>(slot),0,1};
  const auto result=query(search,sizeof(search),SENSOR_OPERATION_TIMEOUT_MS);
  if (result.error==QueryError::None && result.reply.payload[0]==0x09 &&
      (result.reply.length==1 || result.reply.length==5)) {
    Serial.printf("FPPROBERESULT %u NO_MATCH 0\n",static_cast<unsigned>(slot)); return;
  }
  if (!checkQuery("Saved probe Search",result) || result.reply.length!=5 ||
      fingerprint::read16(result.reply.payload+1)!=slot) {
    templateTransferError(); return;
  }
  Serial.printf("FPPROBERESULT %u MATCH %u\n",static_cast<unsigned>(slot),
      fingerprint::read16(result.reply.payload+3));
}
