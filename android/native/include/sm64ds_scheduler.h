// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#else
#include <stdbool.h>
#endif
// Call AFTER I/O initialization, BEFORE any decompiled scheduler access, on
// exactly one engine OS thread. Library-loading constructors must not call it.
// Startup/collection are serial engine-thread operations, not a concurrent API.
bool sm64ds_native_scheduler_init(void);
// Collect only native stacks retired by the original game's exit path.
// Never cancels a live task, unwinds a stack, or shuts down the engine.
// Returns count collected, or -1 with errno=EPERM on a non-owner thread.
int sm64ds_native_scheduler_collect(void);
typedef struct Sm64dsSchedulerStats {
    uint32_t created_slots;
    uint32_t retired_slots;
    uint64_t collected;
} Sm64dsSchedulerStats;
bool sm64ds_native_scheduler_snapshot(Sm64dsSchedulerStats *out);
#ifdef __cplusplus
}
#endif
