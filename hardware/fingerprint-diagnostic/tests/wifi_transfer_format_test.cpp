#include <assert.h>
#include <string>
#include <vector>
#include "wifi_transfer_format.h"

std::vector<char> packet() {
  std::string data("FPW1\x20\xfb",6);
  for(const auto &value:std::vector<std::string>{"classroom","private-password","192.168.1.5",std::string(64,'a'),
      std::string(64,'b'),"-----BEGIN CERTIFICATE-----\nsynthetic-test-only\n-----END CERTIFICATE-----\n"}) {
    data+=value; data.push_back(0);
  }
  return std::vector<char>(data.begin(),data.end());
}
int main() {
  int64_t epoch=0;
  assert(wireless::civilEpoch(2026,10,21,10,10,11,3600,epoch) && epoch==1792573811);
  assert(wireless::civilEpoch(2024,2,29,12,0,0,0,epoch));
  assert(!wireless::civilEpoch(2025,2,29,12,0,0,0,epoch));
  assert(!wireless::civilEpoch(2038,1,1,0,0,0,0,epoch));
  assert(!wireless::civilEpoch(2024,1,1,0,0,0,3600,epoch));
  auto bytes=packet(); wireless::Config config;
  assert(wireless::parseConfig(bytes.data(),bytes.size(),config));
  assert(config.port==8443 && !strcmp(config.ssid,"classroom"));
  for(size_t n=0;n<bytes.size();++n) assert(!wireless::parseConfig(bytes.data(),n,config));
  auto changed=bytes; changed.push_back(0); assert(!wireless::parseConfig(changed.data(),changed.size(),config));
  changed=bytes; changed[0]='X'; assert(!wireless::parseConfig(changed.data(),changed.size(),config));
  changed=bytes; changed[4]=changed[5]=0; assert(!wireless::parseConfig(changed.data(),changed.size(),config));
  changed=bytes; changed[6]='\n'; assert(!wireless::parseConfig(changed.data(),changed.size(),config));
  changed=bytes; changed[static_cast<size_t>(config.host-bytes.data())]=':';
  assert(!wireless::parseConfig(changed.data(),changed.size(),config));
  const std::string sha(64,'a'),saved(64,'b');
  const std::string receipt="FPWRECEIPT 1 batch id "+sha+" "+saved+" 2";
  assert(wireless::validReceipt(receipt.c_str(),"batch","id",sha.c_str(),2));
  assert(!wireless::validReceipt(receipt.c_str(),"csv","id",sha.c_str(),2));
  assert(!wireless::validReceipt(receipt.c_str(),"batch","other",sha.c_str(),2));
  assert(!wireless::validReceipt(receipt.c_str(),"batch","id",saved.c_str(),2));
  assert(!wireless::validReceipt(receipt.c_str(),"batch","id",sha.c_str(),1));
  assert(!wireless::validReceipt((receipt+" garbage").c_str(),"batch","id",sha.c_str(),2));
  assert(!wireless::validReceipt("FPWRECEIPT 1 batch id bad bad 2","batch","id",sha.c_str(),2));
}
