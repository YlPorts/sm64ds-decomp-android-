// SPDX-License-Identifier: MIT
#pragma once
// Call on the engine OS thread, AFTER platform I/O initialization and BEFORE
// any decompiled code accesses the thread manager. Repeated calls on that
// same thread succeed. Calls from another thread return false (errno=EPERM).
// This API does not start the game or provide game shutdown/resource cleanup.
#ifdef __cplusplus
extern "C" {
#else
#include <stdbool.h>
#endif
bool sm64ds_native_scheduler_init(void);
#ifdef __cplusplus
}
#endif
