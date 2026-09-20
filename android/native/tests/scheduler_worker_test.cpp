// SPDX-License-Identifier: MIT
// Model library loading on the application thread and game execution on a
// different worker. The original scheduling/IRQ functions remain unchanged.
#define main sm64ds_scheduler_probe_main
#include "scheduler_test.cpp"
#undef main
int main() {
    int result = 1;
    std::thread game_worker([&result] { result = sm64ds_scheduler_probe_main(); });
    game_worker.join();
    return result;
}
