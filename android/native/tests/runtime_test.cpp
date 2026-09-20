// SPDX-License-Identifier: MIT
// Test doubles below model ONLY enough I/O for the real upstream rt.cpp.
// This test is NOT the game, nor a test of the complete DS hardware abstraction.
#include "ntr/rt.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <sys/mman.h>
#include <unistd.h>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); std::abort(); } } while (0)
namespace {
void *io_mapping;
std::size_t io_size;
std::uint64_t ticks;
std::uint64_t hooks;
std::uint64_t irq_calls;
bool hblank_enabled;
std::uint64_t hook_limit;
void game120() {
    for (unsigned i=0; i<120; ++i) {
        CHECK(ntr::rt_frame() == i);
        ++ticks;
        ntr::rt_vblank_wait();
    }
}
void endless() { for (;;) { ++ticks; ntr::rt_vblank_wait(); } }
bool hook(std::uint64_t frame) {
    ++hooks; CHECK(frame == hooks);
    return !hook_limit || frame < hook_limit;
}
}
extern "C" void *_ZN3IRQ13GetIRQHandlerEj(unsigned) { return nullptr; }
namespace ntr {
bool io_init() {
    if (io_mapping) return true;
    const long page_value = sysconf(_SC_PAGESIZE);
    if (page_value <= 0) return false;
    const auto page = static_cast<std::size_t>(page_value);
    io_size = ((0x2000 + page - 1) / page) * page;
    auto *wanted = reinterpret_cast<void *>(std::uintptr_t(0x04000000));
    // An address HINT, never MAP_FIXED: a collision must fail, not overwrite memory.
    void *p = mmap(wanted, io_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) return false;
    if (p != wanted) { munmap(p, io_size); return false; }
    io_mapping = p;
    return true;
}
unsigned rt_hblank_gates() { return hblank_enabled ? HBLANK_GATE_ALL : 0; }
bool rt_hblank_armed() { return hblank_enabled; }
void rt_hblank_dispatch() { ++irq_calls; }
}
int main() {
    CHECK(ntr::io_init());
    CHECK(ntr::rt_irq_disable() == 0);
    CHECK(ntr::rt_irq_masked());
    CHECK(ntr::rt_irq_restore(0) == 0x80);
    CHECK(!ntr::rt_irq_masked());
    hblank_enabled = true;
    CHECK(ntr::rt_run(game120, hook, 0) == 120);
    CHECK(ticks == 120 && hooks == 120);
    CHECK(irq_calls == 120u * 263u);
    ticks = hooks = irq_calls = 0;
    CHECK(ntr::rt_run(endless, hook, 7) == 7);
    CHECK(ticks == 7 && hooks == 7 && irq_calls == 7u * 263u);
    ticks = hooks = irq_calls = 0;
    hook_limit = 5;
    CHECK(ntr::rt_run(endless, hook, 0) == 5);
    CHECK(ticks == 5 && hooks == 5 && irq_calls == 5u * 263u);
    CHECK(munmap(io_mapping, io_size) == 0);
    std::puts("PASS: upstream rt.cpp: VBlank yields, 120 frames, 263 HBlank edges/frame, max-frame and hook exits, repeated initialization");
}
