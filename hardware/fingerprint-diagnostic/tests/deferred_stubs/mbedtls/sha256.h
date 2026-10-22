#pragma once
// Controller fixture only. Actual SHA-256 is checked in Python and ESP32 builds.
struct mbedtls_sha256_context { size_t count; };
inline void mbedtls_sha256_init(mbedtls_sha256_context *p) { p->count=0; }
inline int mbedtls_sha256_starts_ret(mbedtls_sha256_context *,int) { return 0; }
inline int mbedtls_sha256_update_ret(mbedtls_sha256_context *p,const uint8_t *,size_t n) { p->count+=n; return 0; }
inline int mbedtls_sha256_finish_ret(mbedtls_sha256_context *,uint8_t *p) { memset(p,0,32); return 0; }
inline void mbedtls_sha256_free(mbedtls_sha256_context *) {}
inline std::string &fakeLastShaInput() { static std::string value; return value; }
inline int mbedtls_sha256_ret(const uint8_t *data,size_t n,uint8_t *out,int) {
  fakeLastShaInput().assign(reinterpret_cast<const char *>(data),n); memset(out,0,32); return 0;
}
