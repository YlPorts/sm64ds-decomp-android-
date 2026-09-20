// SPDX-License-Identifier: MIT
// Real decompiled sleep, wake, ready-list, reschedule, idle and VBlank handler.
// Only MMIO storage, the IRQ registry, display callbacks and radio pump are doubles.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <sys/mman.h>
#include "boot2_thread_portable.cpp"

extern "C" {
int data_020a612c[4] = {};
int data_020a6134[5] = {};
int data_020a6128 = 0;
int data_020a6148[16] = {};
alignas(4) unsigned char data_0209d4fc[4] = {};
alignas(4) unsigned char data_0209d4f0[4] = {};
int data_0209d500 = 0;
int data_0209d514 = 0;
int data_0208ee44 = 2;
alignas(4) char data_023c0000[0x4000] = {};
int ARMProcessorMode() { return port_irq_mode_depth ? 0x12 : 0x1f; }
unsigned _ZN3IRQ7DisableEv() { return ntr::rt_irq_disable(); }
unsigned _ZN3IRQ6EnableEv() { return ntr::rt_irq_enable(); }
void _ZN3IRQ7RestoreEj(unsigned value) { (void)ntr::rt_irq_restore(value); }
void func_0201a4bc();
void _ZN3IRQ13VBlankHandlerEv();
}

namespace {
unsigned cases = 0;
unsigned display_commits = 0;
unsigned irq_tails = 0;
void (*vblank_handler)() = nullptr;
port::ThreadPump radio_pump = nullptr;
void require(bool ok, const char *what) {
    if (!ok) { std::fprintf(stderr, "FAIL: %s\n", what); std::exit(1); }
}
void pass(const char *name) { ++cases; std::printf("PASS %u: %s\n", cases, name); }
}

namespace ntr {
bool io_init() {
    static bool initialized = false;
    if (initialized) return true;
    void *wanted = reinterpret_cast<void *>(0x04000000u);
    void *p = mmap(wanted, 0x10000, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (p == MAP_FAILED) return false;
    if (p != wanted) { munmap(p, 0x10000); return false; }
    initialized = true;
    return true;
}
unsigned rt_hblank_gates() { return 0; }
bool rt_hblank_armed() { return false; }
void rt_hblank_dispatch() { require(false, "unexpected HBlank dispatch in this probe"); }
}
namespace port {
ThreadPump thread_pump() { return radio_pump; }
unsigned thread_pump_limit() { return 8; }
void thread_set_irq_mode_hooks(void (*)(), void (*)(), uint16_t (*)()) {}
}
extern "C" void *_ZN3IRQ13GetIRQHandlerEj(unsigned mask) {
    return mask == ntr::IRQ_VBLANK ? reinterpret_cast<void *>(vblank_handler) : nullptr;
}
extern "C" void func_02019144() {
    require(ARMProcessorMode() == 0x12, "display commit must finish inside IRQ mode");
    require(mgr_current() == &g_idle, "wake must defer switching until IRQ return");
    ++display_commits;
}
extern "C" void func_02019100() { ++irq_tails; }

int main() {
    require(sizeof(void *) == 4, "original 32-bit layout");
    require(ntr::io_init(), "reserve test MMIO without overwriting an existing mapping");
    require(!g_booted, "loading the module must not bind the game thread");
    require(sm64ds_native_scheduler_init(), "explicit initialization on the engine thread");
    require(sm64ds_native_scheduler_init(), "same-thread initialization is idempotent");
    ntr::rt_irq_boot_state();
    require(mgr_current() == &g_main && mgr_head() == &g_main, "boot manager links");
    require(g_main.next == &g_idle && g_idle.id == 1, "idle boot record");
    pass("original manager and thread layouts");

    uint16_t empty = 0;
    auto before = g_stat.restores;
    OS_WakeupThread(&empty);
    require(g_stat.restores == before && empty == 0, "empty wake must not switch");
    pass("original wake on an empty queue");

    volatile uint32_t stack_words[64];
    for (unsigned j = 0; j < 64; ++j) stack_words[j] = 0xa55a0000u + j;
    before = g_stat.restores;
    auto wakes = g_stat.vblank_wakes;
    for (unsigned i = 0; i < 10000; ++i) {
        func_0201a4d0();
        require(vblank_queue() == 0, "original wake cleared queue");
        require(mgr_current() == &g_main && g_main.state == 1, "sleep returned on main");
        for (unsigned j = 0; j < 64; ++j)
            require(stack_words[j] == 0xa55a0000u + j, "stack survived scheduling");
    }
    require(g_stat.restores - before == 20000, "two native switches per sleep/wake");
    require(g_stat.vblank_wakes - wakes == 10000, "10000 original wake round trips");
    require(g_stat.starved == 0, "normal queue wake must not use starvation fallback");
    pass("10000 real sleep/wake round trips; 20000 switches; preserved stack");

    ntr::rt_irq_disable();
    func_0201a4d0();
    require(ntr::rt_irq_masked(), "sleep restored caller interrupt mask");
    ntr::rt_irq_enable();
    pass("interrupt mask survives the idle-thread round trip");

    mgr_u16(4) = 1;
    before = g_stat.restores;
    func_02057f54();
    require(mgr_u16(0) == 1 && g_stat.restores == before, "scheduler lock defers switch");
    mgr_u16(4) = 0; mgr_u16(0) = 0;
    pass("original scheduler lock and pending flag");

    vblank_handler = _ZN3IRQ13VBlankHandlerEv;
    data_0209d4f0[0] = 1;
    auto entered = g_stat.vblank_enters;
    auto deferred = g_stat.deferred;
    auto starved = g_stat.starved;
    for (unsigned i = 0; i < 2000; ++i) {
        port_thread_frame_wait_begin();
        func_0201a4bc();
        require(data_0209d500 == 0 && data_0209d514 == 0, "frame queue and divider reset");
        require(display_commits == i + 1 && irq_tails == (i + 1) * 2, "IRQ completed before resume");
        require(port_irq_mode_depth == 0 && mgr_current() == &g_main, "IRQ returned to main");
    }
    require(g_stat.vblank_enters - entered == 4000, "two VBlanks per frame wait");
    require(g_stat.deferred - deferred == 2000, "original IRQ-mode reschedule deferral");
    require(g_stat.irqswitch == 0 && g_stat.starved == starved, "no inline IRQ switch or forced wake");
    require(*reinterpret_cast<uint32_t *>(data_023c0000 + 0x3ff8) == 1, "original IRQ flag store");
    data_0209d4f0[0] = 0; vblank_handler = nullptr;
    pass("2000 frame waits through the real VBlank handler; correct IRQ-return order");

    RomThread invalid{};
    invalid.id = 16;
    auto rejected = g_stat.rejected;
    ARMRestoreContext(&invalid);
    require(g_stat.rejected == rejected + 1 && mgr_current() == &g_main, "invalid record refused");
    require(ARMSaveContext(&invalid) == 1, "unknown save refused");
    pass("unregistered and malformed thread contexts refused");

    auto wrong = g_stat.wrong_thread;
    before = g_stat.restores;
    std::thread other([] {
        require(!sm64ds_native_scheduler_init(), "another OS thread cannot rebind the scheduler");
        ARMRestoreContext(&g_idle);
    });
    other.join();
    require(g_stat.wrong_thread == wrong + 1 && g_stat.restores == before, "cross-thread switch refused");
    pass("native OS-thread ownership enforced");

    port::thread_sched_report("ANDROID-SCHEDULER-PROBE");
    // End the isolated probe cleanly. Do not expose this as a game shutdown API:
    // integration must arrange for all game resources to finish before disposal.
    for (auto &slot : g_slots) {
        if (slot.fiber && slot.fiber != sm64ds::platform::current_fiber()) {
            require(sm64ds::platform::delete_fiber(static_cast<sm64ds::platform::Fiber *>(slot.fiber)), "test fiber cleanup");
        }
    }
    require(sm64ds::platform::fiber_to_thread(), "test root cleanup");
    pass("probe-owned suspended stacks released");
    std::printf("RESULT: %u/%u scheduler cases passed; 8 original C translation units; NOT GAMEPLAY\n", cases, cases);
    return 0;
}
