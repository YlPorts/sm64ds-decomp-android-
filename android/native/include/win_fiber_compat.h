// SPDX-License-Identifier: MIT
// Deliberately small adapter for port/ntr/rt.cpp. NOT a Windows API emulator.
#pragma once
#include "sm64ds_fiber.h"
#include <cstdlib>
#ifndef CALLBACK
#define CALLBACK
#endif
inline void *ConvertThreadToFiber(void *) {
    return sm64ds::platform::thread_to_fiber();
}
inline bool ConvertFiberToThread() {
    return sm64ds::platform::fiber_to_thread();
}
inline void *CreateFiber(std::size_t size, void (*entry)(void *), void *arg) {
    return sm64ds::platform::create_fiber(size, entry, arg);
}
inline void SwitchToFiber(void *fiber) {
    if (!sm64ds::platform::switch_to_fiber(static_cast<sm64ds::platform::Fiber *>(fiber)))
        std::abort();
}
inline void DeleteFiber(void *fiber) {
    if (!sm64ds::platform::delete_fiber(static_cast<sm64ds::platform::Fiber *>(fiber)))
        std::abort();
}
