#pragma once
constexpr int ESP_PARTITION_TYPE_DATA=1,ESP_PARTITION_SUBTYPE_DATA_SPIFFS=130,ESP_OK=0;
struct esp_partition_t { size_t size; };
inline const esp_partition_t *esp_partition_find_first(int,int,const char *) {
  static const esp_partition_t partition={4096}; return &partition;
}
inline int esp_partition_read(const esp_partition_t *,size_t offset,void *out,size_t n) {
  if(fakeFlash.rawReadFails) return -1;
  memset(out,255,n);
  if(!fakeFlash.rawErased && offset==3072) static_cast<uint8_t *>(out)[n-1]=0;
  return 0;
}
