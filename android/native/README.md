# SM64DS Android native bootstrap — 0.3

**Development components, not a playable game or an APK.** No game execution or
performance is claimed. The project compiles recovered game logic natively;
QEMU is used only to test ARM binaries on CI, never as part of the Android port.

Base: upstream `port/link100`, `9bb3c454f9d67ee25ea9d08735e1f3943bbd6225`.
Stage 0.3 continues fork commit `2d273b0f25549593629d52699c824ebff122bbe0` in
`android/native-bootstrap`. Original `src/`, `port/` and `main` are not edited.

## New in 0.3

The scheduler target now links **17 original C/C++ translation units**. It adds
original creation, slot allocation, priority insertion, make-runnable, join and
exit paths to the eight scheduling/IRQ units from 0.2. Synthetic job entries
exercise these real functions; this is not a card-driver, audio-thread or level test.

Native lifetime ownership now follows the original exit path. Retirement is
captured before switching away from an exited thread; its native stack is freed
only from another stack. Collection never dereferences the old caller-owned
record, so a returned joiner can reuse or destroy that record. Live sleepers are
never collected. Foreign-thread save/restore is rejected BEFORE adoption.

The test fixture uses a **single 0x54-byte manager allocation**, with ELF symbols
at +0x08 and +0x14. Previously the isolated probe stored the manager and table in
separate arrays, which was insufficient for the original allocation function.
This fixture is not the complete engine's production BSS map.

`context_init.cpp` provides explicitly documented native replacements for two
handwritten ARM primitives. Their references and blob hashes are in the source.
The record stores (including ARM/Thumb entry state) are preserved; execution
continues to use native guarded fiber stacks, not the recorded DS stack.

## Build and test

Host fibers only:

```sh
cmake -S android/native -B build/native -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/native
ctest --test-dir build/native --output-on-failure
python3 -m unittest discover -s android/native/tests -p 'test_*.py' -v
```

The full scheduler probe requires this directory inside the pinned repository
and a 32-bit toolchain. Android compilation (NDK `28.2.13676358` in CI):

```sh
cmake -S android/native -B build/android-scheduler -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=armeabi-v7a -DANDROID_PLATFORM=android-23 \
  -DANDROID_ARM_MODE=thumb -DANDROID_STL=c++_static \
  -DCMAKE_BUILD_TYPE=Release -DSM64DS_TEST_UPSTREAM_SCHEDULER=ON
cmake --build build/android-scheduler
```

Use a different build directory and `-DANDROID_ARM_MODE=arm` for ARM mode.
The workflow tests both instruction modes under ARM Linux/QEMU and separately
compiles both using Android NDK. Cross-compilation is not Android execution.
The original layout remains strictly 32-bit. ARM64 support of the independent
fiber component does not imply ARM64 support of the game or scheduler.

Output libraries: `libsm64ds_thread_logic.a` (original game scheduling logic),
`libsm64ds_context_primitives.a`, `libsm64ds_scheduler_support.a` (adapted HAL),
and `libsm64ds_fibers.a`. Full-engine integration must choose these providers
instead of linking duplicate Windows HAL bodies or duplicate original TUs.
The probe also supplies explicit test-owned globals, MMIO, IRQ registry, radio
and display callbacks; the libraries are not a self-contained game engine.

## Coverage and remaining limits

The suite retains 10,000 sleep/wake round trips and 2,000 original VBlank frame
waits. Additional cases cover record/stack initialization, 512 reuses of one
record with different entries/arguments, live sleepers, original join, 14
simultaneous jobs, slot exhaustion, priority order, shared queues and ownership.
Test assertions are in `tests/scheduler_lifetime_cases.inc`; reports are produced
by Actions. The collector is also exposed as an owner-thread API with statistics.

Call `sm64ds_native_scheduler_init()` after I/O setup on a single engine thread.
Initialization and collection are serial operations, not a concurrent API.
`sm64ds_native_scheduler_collect()` reclaims only stacks retired by the original
exit path; it does not cancel tasks, unwind stacks or shut down the game.

**Not covered:** exit while holding nonempty mutex/cleanup queues. The upstream
`func_02058a44.c` has a documented no-argument `OS_WakeupThread` declaration in
that branch. These tests keep its queue empty (as initial creation does), so
they do not validate or repair that path. Forced external destruction, complete
engine restart, savestate restoration of host fibers, all remaining Windows/ELF
seams, graphics, audio, controls, resources and Android lifecycle are unfinished.

No ROM, Nintendo assets, proprietary SDK or emulated DS CPU is included.
Do not enable ShadowCallStack, hardware shadow stacks or sanitizers requiring
fiber-switch hooks before implementing their context support. Exceptions cannot
unwind across fabricated context frames. New code is MIT licensed; upstream
sources retain their license.
