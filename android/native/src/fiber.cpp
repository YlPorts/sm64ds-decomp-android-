// SPDX-License-Identifier: MIT
#include "sm64ds_fiber.h"
#include <cerrno>
#include <cstdint>
#include <cstdlib>
#include <exception>
#include <cstring>
#include <limits>
#include <new>
#include <pthread.h>
#include <sys/mman.h>
#include <unistd.h>

extern "C" void sm64ds_context_swap(void **old_sp, void *new_sp);
extern "C" [[noreturn]] void sm64ds_fiber_entry();

namespace sm64ds::platform {
struct Fiber {
    void *sp = nullptr;
    void *mapping = nullptr;
    std::size_t mapping_size = 0;
    FiberEntry entry = nullptr;
    void *arg = nullptr;
    Fiber *caller = nullptr;
    pthread_t owner{};
    bool root = false;
    bool finished = false;
};
namespace {
thread_local Fiber *active = nullptr;
thread_local std::size_t live_fibers = 0;
constexpr std::size_t kMinStack = 64 * 1024;
constexpr std::size_t kMaxStack = 64 * 1024 * 1024;
bool owned(const Fiber *f) { return f && pthread_equal(f->owner, pthread_self()); }
void write_word(std::uintptr_t at, std::uintptr_t value) {
    std::memcpy(reinterpret_cast<void *>(at), &value, sizeof(value));
}
void initialize_stack(Fiber *f, std::uintptr_t top) {
    top &= ~std::uintptr_t(15);
#if defined(__x86_64__)
    // After six register pops and RET, the SysV function-entry RSP is 8 mod 16.
    // 24 bytes of FP control + 48 of saved registers + 8 of return address.
    const std::uintptr_t sp = top - 88;
    std::memset(reinterpret_cast<void *>(sp), 0, 88);
    asm volatile("stmxcsr (%0)\n\tfnstcw 4(%0)" : : "r"(sp) : "memory");
    write_word(sp + 72, reinterpret_cast<std::uintptr_t>(&sm64ds_fiber_entry));
#elif defined(__arm__)
    const std::uintptr_t sp = top - 112;
    std::memset(reinterpret_cast<void *>(sp), 0, 112);
    std::uint32_t fpscr;
    asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
    std::memcpy(reinterpret_cast<void *>(sp), &fpscr, sizeof(fpscr));
    write_word(sp + 108, reinterpret_cast<std::uintptr_t>(&sm64ds_fiber_entry));
#elif defined(__aarch64__)
    const std::uintptr_t sp = top - 176;
    std::memset(reinterpret_cast<void *>(sp), 0, 176);
    std::uint64_t fpcr, fpsr;
    asm volatile("mrs %0, fpcr" : "=r"(fpcr));
    asm volatile("mrs %0, fpsr" : "=r"(fpsr));
    std::memcpy(reinterpret_cast<void *>(sp + 160), &fpcr, sizeof(fpcr));
    std::memcpy(reinterpret_cast<void *>(sp + 168), &fpsr, sizeof(fpsr));
    write_word(sp + 88, reinterpret_cast<std::uintptr_t>(&sm64ds_fiber_entry));
#else
#error Unsupported context-switch architecture
#endif
    f->sp = reinterpret_cast<void *>(sp);
}
} // namespace

Fiber *thread_to_fiber() noexcept {
    if (active) { errno = EALREADY; return nullptr; }
    auto *f = new (std::nothrow) Fiber;
    if (!f) { errno = ENOMEM; return nullptr; }
    f->owner = pthread_self();
    f->root = true;
    active = f;
    return f;
}
bool fiber_to_thread() noexcept {
    if (!active || !active->root || live_fibers) { errno = EBUSY; return false; }
    delete active;
    active = nullptr;
    return true;
}
Fiber *current_fiber() noexcept { return active; }
Fiber *create_fiber(std::size_t size, FiberEntry entry, void *arg) noexcept {
    if (!active || !entry) { errno = EINVAL; return nullptr; }
    if (size > kMaxStack) { errno = EINVAL; return nullptr; }
    if (size < kMinStack) size = kMinStack;
    const long page_value = sysconf(_SC_PAGESIZE);
    if (page_value <= 0) { errno = EINVAL; return nullptr; }
    const auto page = static_cast<std::size_t>(page_value);
    size = ((size + page - 1) / page) * page;
    const std::size_t total = size + 2 * page;
    void *mapping = mmap(nullptr, total, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    if (mapping == MAP_FAILED) return nullptr;
    auto *base = static_cast<unsigned char *>(mapping) + page;
    if (mprotect(base, size, PROT_READ | PROT_WRITE) != 0) {
        const int error = errno; munmap(mapping, total); errno = error; return nullptr;
    }
    auto *f = new (std::nothrow) Fiber;
    if (!f) { munmap(mapping, total); errno = ENOMEM; return nullptr; }
    f->mapping = mapping;
    f->mapping_size = total;
    f->entry = entry;
    f->arg = arg;
    f->owner = pthread_self();
    initialize_stack(f, reinterpret_cast<std::uintptr_t>(base + size));
    ++live_fibers;
    return f;
}
bool switch_to_fiber(Fiber *target) noexcept {
    if (!active || !owned(target) || target->finished) { errno = EINVAL; return false; }
    if (target == active) return true;
    Fiber *old = active;
    // A return from the entry function goes back to the fiber that last resumed it.
    target->caller = old;
    active = target;
    sm64ds_context_swap(&old->sp, target->sp);
    return true;
}
bool delete_fiber(Fiber *f) noexcept {
    if (!owned(f) || f == active || f->root) { errno = EINVAL; return false; }
    if (munmap(f->mapping, f->mapping_size) != 0) return false;
    delete f;
    --live_fibers;
    return true;
}
bool fiber_finished(const Fiber *f) noexcept { return owned(f) && f->finished; }
} // namespace sm64ds::platform

extern "C" [[noreturn]] void sm64ds_fiber_entry() {
    using namespace sm64ds::platform;
    Fiber *f = current_fiber();
    // Exceptions must never unwind through a manufactured context frame.
    try { f->entry(f->arg); } catch (...) { std::terminate(); }
    f->finished = true;
    Fiber *caller = f->caller;
    if (!caller || !switch_to_fiber(caller)) std::abort();
    std::abort(); // A finished fiber must never be resumed.
}
