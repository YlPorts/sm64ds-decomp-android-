// SPDX-License-Identifier: MIT
// Included once, after the adapted upstream scheduler. Internal symbols belong
// to that translation unit. This does not cancel live game tasks or unwind stacks.
namespace {
unsigned native_reap_completed() {
    unsigned count = 0;
    auto *active = sm64ds::platform::current_fiber();
    for (FiberSlot &slot : g_slots) {
        if (!slot.retired || slot.fiber == active) continue;
        // retired is captured at the original exit's context switch, NOT inferred
        // from the record here. Its owner may already have freed the record.
        if (slot.fiber && !sm64ds::platform::delete_fiber(
                static_cast<sm64ds::platform::Fiber *>(slot.fiber))) {
            std::fprintf(stderr, "[native] cannot collect retired scheduler stack\n");
            std::abort();
        }
        slot = FiberSlot{};
        ++count;
    }
    native_reaped_total += count;
    return count;
}
}
extern "C" int sm64ds_native_scheduler_collect() {
    if (!g_booted || g_owner_tid != sm64ds_host_thread_id()) {
        errno = EPERM;
        return -1;
    }
    return static_cast<int>(native_reap_completed());
}
extern "C" bool sm64ds_native_scheduler_snapshot(Sm64dsSchedulerStats *out) {
    if (!out) { errno = EINVAL; return false; }
    if (!g_booted || g_owner_tid != sm64ds_host_thread_id()) {
        errno = EPERM;
        return false;
    }
    *out = {};
    for (const FiberSlot &slot : g_slots) {
        if (slot.created) ++out->created_slots;
        if (slot.retired) ++out->retired_slots;
    }
    out->collected = native_reaped_total;
    return true;
}
