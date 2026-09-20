/* Native timing used only at reviewed Windows timing call sites.
 * CLOCK_BOOTTIME supplies uptime including suspend for 32-bit tick timeouts;
 * CLOCK_MONOTONIC supplies the high-resolution interval counter. Both clocks
 * are kernel services. No fabricated time, Windows imports or polling loop.
 */
#ifndef SM64DS_POSIX_CLOCK_H
#define SM64DS_POSIX_CLOCK_H
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

static inline uint64_t sm64ds_clock_ns(clockid_t clock_id) {
    struct timespec now;
    if (clock_gettime(clock_id, &now) != 0) {
        perror("sm64ds: clock_gettime");
        abort();
    }
    return (uint64_t)now.tv_sec * UINT64_C(1000000000) + (uint64_t)now.tv_nsec;
}
static inline uint32_t sm64ds_ticks_ms(void) {
    return (uint32_t)(sm64ds_clock_ns(CLOCK_BOOTTIME) / UINT64_C(1000000));
}
static inline int sm64ds_performance_counter(long long *out) {
    if (!out) { errno = EINVAL; return 0; }
    *out = (long long)sm64ds_clock_ns(CLOCK_MONOTONIC);
    return 1;
}
static inline int sm64ds_performance_frequency(long long *out) {
    if (!out) { errno = EINVAL; return 0; }
    *out = 1000000000LL;
    return 1;
}
static inline void sm64ds_sleep_ms(uint32_t milliseconds) {
    struct timespec remaining;
    remaining.tv_sec = (time_t)(milliseconds / 1000u);
    remaining.tv_nsec = (long)(milliseconds % 1000u) * 1000000L;
    while (nanosleep(&remaining, &remaining) != 0) {
        if (errno != EINTR) { perror("sm64ds: nanosleep"); abort(); }
    }
}
#endif
