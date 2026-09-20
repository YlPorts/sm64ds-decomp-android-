#include "sm64ds_memory_delta.h"
#include <cassert>
#include <cstdio>
#include <vector>
#include <unistd.h>
int main() {
    unsigned checks = 0;
    for (size_t block : {size_t(4096), size_t(16384)}) {
        const size_t bytes = block * 3 + 17;
        std::vector<unsigned char> live(bytes), before(bytes);
        void *hits[6]{};
        size_t n = 6;
        assert(sm64ds_changed_blocks(live.data(), before.data(), bytes, block, hits, &n) == 0 && n == 0); ++checks;
        for (size_t offset : {size_t(0), block-1, block, block*2+7, bytes-1}) {
            live[offset] = 42;
            n = 6;
            assert(sm64ds_changed_blocks(live.data(), before.data(), bytes, block, hits, &n) == 0 && n == 1);
            assert(hits[0] == live.data() + (offset / block) * block); ++checks;
            live[offset] = 0;
        }
        for (size_t i = 0; i < bytes; ++i) live[i] = static_cast<unsigned char>(1+i%255);
        n = 2; hits[2] = reinterpret_cast<void*>(uintptr_t(0x1234));
        assert(sm64ds_changed_blocks(live.data(), before.data(), bytes, block, hits, &n) == ENOSPC && n == 4);
        assert(hits[2] == reinterpret_cast<void*>(uintptr_t(0x1234))); ++checks;
        assert(before[0] == 0 && before[bytes-1] == 0); ++checks;
        n = 6; assert(sm64ds_changed_blocks(live.data(), live.data(), bytes, block, hits, &n) == 0 && n == 0); ++checks;
    }
    size_t n = 0;
    assert(sm64ds_changed_blocks(nullptr, nullptr, 0, 4096, nullptr, &n) == 0); ++checks;
    assert(sm64ds_changed_blocks(nullptr, nullptr, 1, 4096, nullptr, &n) == EINVAL); ++checks;
    assert(sm64ds_changed_blocks(nullptr, nullptr, 0, 0, nullptr, &n) == EINVAL); ++checks;
    assert(sm64ds_changed_blocks(nullptr, nullptr, 0, 4096, nullptr, nullptr) == EINVAL); ++checks;
    void *memory = sm64ds_snapshot_alloc(16384 + 1); assert(memory); ++checks;
    auto *p = static_cast<unsigned char*>(memory);
    assert(p[0] == 0 && p[16384] == 0); ++checks;
    p[16384] = 70; assert(p[16384] == 70); ++checks;
    sm64ds_snapshot_free(memory, 16384+1);
    std::printf("PASS %u native memory-delta checks; logical blocks 4/16 KiB; no device claim\n", checks);
}
