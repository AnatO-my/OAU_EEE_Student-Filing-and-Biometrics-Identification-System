#pragma once
inline int64_t esp_timer_get_time() { return static_cast<int64_t>(fakeMillis)*1000; }
