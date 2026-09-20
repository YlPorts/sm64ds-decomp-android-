/* Native snapshot support. The blocks below are logical undo-log blocks, not
 * OS pages: 4 KiB and 16 KiB Android kernels use the same byte comparisons.
 * Caller owns both buffers and serializes writes with snapshot/restore.
 * A write that restores the old bytes need not be logged. This is NOT kernel
 * write-watch and has O(region size) read cost per capture.
 */
#ifndef SM64DS_MEMORY_DELTA_H
#define SM64DS_MEMORY_DELTA_H
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cerrno>
#include <sys/mman.h>

static inline void *sm64ds_snapshot_alloc(std::size_t bytes) {
    if (!bytes) bytes = 1;
    void *p = mmap(nullptr, bytes, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    return p == MAP_FAILED ? nullptr : p;
}
static inline void sm64ds_snapshot_free(void *p, std::size_t bytes) {
    if (p) munmap(p, bytes ? bytes : 1);
}
/* Always reports the full required count. On insufficient capacity it returns
 * ENOSPC, never mutates the baseline, and never writes beyond the output array.
 * Addresses identify starts of logical blocks; the final block can be short.
 */
static inline int sm64ds_changed_blocks(void *live, const void *shadow,
        std::size_t bytes, std::size_t block, void **changed, std::size_t *count) {
    if (!count) return EINVAL;
    const std::size_t capacity = *count;
    *count = 0;
    if (!block || (bytes && (!live || !shadow)) || (capacity && !changed)) return EINVAL;
    if (bytes > UINTPTR_MAX - reinterpret_cast<std::uintptr_t>(live) ||
        bytes > UINTPTR_MAX - reinterpret_cast<std::uintptr_t>(shadow)) return EINVAL;
    const auto *old = static_cast<const unsigned char *>(shadow);
    auto *now = static_cast<unsigned char *>(live);
    std::size_t found = 0, offset = 0;
    while (offset < bytes) {
        const std::size_t left = bytes - offset;
        const std::size_t n = left < block ? left : block;
        if (std::memcmp(now + offset, old + offset, n)) {
            if (found < capacity) changed[found] = now + offset;
            ++found;
        }
        offset += n;
    }
    *count = found;
    return found > capacity ? ENOSPC : 0;
}
#endif
