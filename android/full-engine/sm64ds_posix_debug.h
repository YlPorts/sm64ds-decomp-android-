/* Native diagnostics, not SEH or proof that an object is alive.
 * A /proc/self/maps check is a snapshot. It must not be used as a security
 * boundary or against concurrent unmapping. The reviewed callers use it on
 * the engine thread for level teardown diagnostics; no crash is swallowed.
 */
#ifndef SM64DS_POSIX_DEBUG_H
#define SM64DS_POSIX_DEBUG_H
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <dlfcn.h>
#include <unwind.h>

static inline void *sm64ds_module_base(void) {
    Dl_info info{};
    return dladdr(reinterpret_cast<void*>(&sm64ds_module_base), &info) ? info.dli_fbase : nullptr;
}
struct Sm64dsTraceBuffer { void **frames; unsigned count; unsigned capacity; };
static inline _Unwind_Reason_Code sm64ds_trace_step(_Unwind_Context *context, void *arg) {
    auto *trace = static_cast<Sm64dsTraceBuffer*>(arg);
    const uintptr_t ip = _Unwind_GetIP(context);
    if (ip == 0 || trace->count >= trace->capacity) return _URC_END_OF_STACK;
    trace->frames[trace->count++] = reinterpret_cast<void*>(ip);
    return _URC_NO_REASON;
}
static inline unsigned sm64ds_capture_backtrace(void **frames, unsigned capacity) {
    if (!frames || capacity == 0) return 0;
    Sm64dsTraceBuffer trace{frames, 0, capacity};
    _Unwind_Backtrace(sm64ds_trace_step, &trace);
    return trace.count;
}
static inline int sm64ds_bad_read_span(const void *address, size_t bytes) {
    if (bytes == 0) return 0;
    uintptr_t next = reinterpret_cast<uintptr_t>(address);
    if (next == 0 || bytes > UINTPTR_MAX - next) return 1;
    const uintptr_t end = next + bytes;
    FILE *maps = fopen("/proc/self/maps", "r");
    if (!maps) return 1; // Fail closed when the OS does not expose a map.
    char line[1024];
    bool readable = false;
    while (fgets(line, sizeof line, maps)) {
        unsigned long long low, high;
        char permissions[5] = {};
        if (sscanf(line, "%llx-%llx %4s", &low, &high, permissions) != 3) continue;
        if (high <= next) continue;
        if (low > next || permissions[0] != 'r') break;
        if (high >= end) { readable = true; break; }
        next = static_cast<uintptr_t>(high);
    }
    fclose(maps);
    return !readable;
}
#endif
