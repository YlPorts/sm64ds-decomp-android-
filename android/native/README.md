# SM64DS Android native bootstrap — 0.2

**Development code, not a playable game, APK or completed recomp.**
The goal is native compilation of the game logic, not an emulator wrapper.
No ROM, Nintendo assets, proprietary SDK, Wine or emulated DS CPU is included.

Base: `tangosdev/sm64ds-decomp`, `port/link100`, commit
`9bb3c454f9d67ee25ea9d08735e1f3943bbd6225`. Work lives in the isolated fork
branch `android/native-bootstrap`; `main` is unchanged.

## Implemented

* Cooperative, same-thread fibers for ARMv7, AArch64 and Linux x86-64.
  Callee-saved registers, stack state and floating-point control state are
  preserved. Guarded stacks use the actual OS page size.
* Generated adaptation of `port/ntr/rt.cpp`, preserving the upstream frame and
  HBlank logic without defining `_WIN32` on Android.
* Generated adaptation of the pinned `port/hal/boot2_thread.cpp`, with a Git
  blob-hash check, native thread ownership and explicit engine-thread startup.
* A 32-bit scheduler probe linking eight original C translation units directly
  from `src/`: sleep, wake, reschedule, ready-list selection, idle, two sleep
  call sites and the original VBlank handler. No upstream source is edited.
* Separate host tests, ARM Linux execution under QEMU user-mode, and Android
  NDK compilation. QEMU is a CI testing tool, not part of the port.

## What the scheduler probe establishes

Nine cases cover original layouts, empty wakes, 10,000 sleep/wake round trips
(20,000 native context switches), stack preservation, interrupt masks,
scheduler locking, 2,000 frame waits, IRQ-return deferral, bad-context
rejection, OS-thread ownership and disposal of probe-owned stacks.

The worker wrapper loads on the application thread and runs the probe on a
separate game thread. Storage for globals/MMIO, the IRQ registry, radio pump
and display callbacks are explicit test doubles. The scheduling and VBlank
C functions themselves are the original decompiled sources, not doubles.
This does not test a level, the full engine, valid game-created thread
lifetimes, graphics, audio, persistence or Android lifecycle integration.

## Build

Fibers and host tests only (no full upstream checkout required):

```sh
cmake -S android/native -B build/native -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/native
ctest --test-dir build/native --output-on-failure
```

Inside the pinned repository, add `-DSM64DS_TEST_UPSTREAM_RUNTIME=ON` to also
test the actual frame-loop adaptation. For the original scheduler, use a
32-bit toolchain and `-DSM64DS_TEST_UPSTREAM_SCHEDULER=ON`:

```sh
cmake -S android/native -B build/android-scheduler -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=armeabi-v7a -DANDROID_PLATFORM=android-23 \
  -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release \
  -DSM64DS_TEST_UPSTREAM_SCHEDULER=ON
cmake --build build/android-scheduler
```

CI pins NDK `28.2.13676358`. Output includes
`libsm64ds_scheduler_support.a`, `libsm64ds_fibers.a` and
`sm64ds_scheduler_tests`. These are not an APK. Run the Android test executable
on a device that supports 32-bit applications with:

```sh
adb push build/android-scheduler/sm64ds_scheduler_tests /data/local/tmp/
adb shell chmod 755 /data/local/tmp/sm64ds_scheduler_tests
adb shell /data/local/tmp/sm64ds_scheduler_tests
```

Cross-compilation is not a device execution test. The scheduler target
intentionally refuses 64-bit pointers. The independent fiber module can
still build for `arm64-v8a`; this does not port the game's 32-bit layouts.

## Engine-thread initialization

Call `sm64ds_native_scheduler_init()` from `sm64ds_scheduler.h` on the engine
OS thread, after I/O initialization and before any decompiled code reads the
thread manager. Same-thread repeat calls succeed. Calls from another thread
fail with `errno=EPERM`. Do not bind the scheduler in a library-loading
constructor: the loader and game worker may be different OS threads.
This function does not start the game and is not a game shutdown API.

## Remaining integration

1. Exercise game-created thread records and complete thread lifetimes, then
   integrate the remaining Windows dependencies from `audit_port.py`.
2. Resolve Clang/ELF linkage and ABI assumptions across the complete playable
   target. Preserve the 32-bit layout until the game structures are ported.
3. Integrate Android lifecycle, graphics, audio, controls and user-selected
   ROM resources. Build/sign the APK only after there is a real engine target.
4. Test startup, menus, levels, saving and suspend/resume on physical hardware.
   No gameplay or performance result is claimed by this bootstrap.

## Constraints

Fibers are thread-affine; never delete a running fiber. Deleting a suspended
fiber does not unwind C++ destructors, so resource cleanup must be explicit.
Do not enable sanitizers requiring fiber-switch hooks, ShadowCallStack or
hardware shadow stacks until their context support is implemented and tested.
New bootstrap code is MIT licensed; upstream code retains its original license.
