// SPDX-License-Identifier: MIT
#pragma once
#include <cstddef>

namespace sm64ds::platform {
struct Fiber;
using FiberEntry = void (*)(void *);
// Cooperative, same-thread fibers. NOT an ARM CPU emulator.
// All operations on a fiber must take place on the OS thread that created it.
Fiber *thread_to_fiber() noexcept;
bool fiber_to_thread() noexcept;
Fiber *current_fiber() noexcept;
Fiber *create_fiber(std::size_t stack_size, FiberEntry entry, void *arg) noexcept;
bool switch_to_fiber(Fiber *target) noexcept;
// A suspended fiber may be destroyed, but its stack is not unwound.
// Game shutdown must release resources explicitly before destroying its fiber.
bool delete_fiber(Fiber *fiber) noexcept;
bool fiber_finished(const Fiber *fiber) noexcept;
} // namespace sm64ds::platform
