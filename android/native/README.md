# SM64DS Android native bootstrap — 0.1

**This is a development milestone, not a playable game, APK, or completed recomp.**
The original game logic is intended to compile natively; this is not an emulator wrapper.

Base: `tangosdev/sm64ds-decomp`, `port/link100`,
commit `9bb3c454f9d67ee25ea9d08735e1f3943bbd6225`.
The isolated fork branch is `android/native-bootstrap`. `main` is unchanged.

## Implemented

* Cooperative same-thread fibers for ARMv7, AArch64 and Linux x86-64.
  They preserve callee-saved registers, stack state and floating-point control state.
  Stacks have guard pages; size/alignment use the operating system page size.
* A small adapter for the Windows fiber calls in `port/ntr/rt.cpp`.
  The build generates a portable copy in its output directory, retaining upstream
  VBlank/HBlank/frame-loop logic. It never defines `_WIN32` on Android and does not
  silently remove the upstream 32-bit game ABI requirement.
* Regression tests for switching, stack data, rounding modes, thread ownership,
  completion, repeated creation and the actual upstream frame-loop probe.
  The latter uses explicit I/O/IRQ test doubles, not the real game or full hardware layer.
* A repository portability inventory and separate host/Android-NDK CI jobs.

## Build locally

Only the fibers and their host tests (no checkout of the full upstream needed):

```sh
cmake -S android/native -B build/native -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/native
ctest --test-dir build/native --output-on-failure
```

With this directory inside the pinned upstream checkout, also test the frame loop:

```sh
cmake -S android/native -B build/native -DSM64DS_TEST_UPSTREAM_RUNTIME=ON
cmake --build build/native
ctest --test-dir build/native --output-on-failure
```

Cross-compile with a locally installed NDK (CI pins `28.2.13676358`):

```sh
cmake -S android/native -B build/android-armv7 -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=armeabi-v7a -DANDROID_PLATFORM=android-23 \
  -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release \
  -DSM64DS_TEST_UPSTREAM_RUNTIME=ON
cmake --build build/android-armv7
```

Use `arm64-v8a` and a different build directory to test the 64-bit **platform module**.
That does **not** make the game's pointer-dependent data structures 64-bit compatible.

To run the resulting Android executable on a compatible physical device:

```sh
adb push build/android-armv7/sm64ds_fiber_tests /data/local/tmp/
adb shell chmod 755 /data/local/tmp/sm64ds_fiber_tests
adb shell /data/local/tmp/sm64ds_fiber_tests
```

Repeat with `sm64ds_runtime_tests`. Cross-compilation alone is not an execution test.
The artifacts contain a static platform library and native test executables, not an APK.

## Remaining work before a playable APK

1. Port the game scheduler in `port/hal/boot2_thread.cpp` and the remaining platform
   dependencies inventoried in `build/android-audit.json`. Adapting `ntr/rt.cpp`
   alone does not enable every gameplay path.
2. Resolve Clang/ELF linkage and ABI assumptions across the full playable target.
   The first full-game target should retain the required 32-bit pointer layout;
   support for 64-bit-only Android devices requires further structural work.
3. Integrate Android lifecycle, rendering, audio, controls and user-selected ROM
   resource loading with the game, then build/sign an APK.
4. Validate startup, menus, levels, saving, suspend/resume and sustained gameplay
   on physical Android hardware. No game execution or performance is claimed yet.

## Constraints

Fiber objects are thread-affine. Do not delete a running fiber. Deleting a suspended
fiber does not unwind C++ destructors; the game must perform explicit cleanup.
Do not enable sanitizers requiring fiber-switch hooks, ShadowCallStack, or hardware
shadow stacks for this module until their context support is implemented and tested.
No ROM, Nintendo assets, proprietary SDK, Wine, or emulated CPU is included.
New bootstrap files are MIT licensed; the upstream code retains its original license.
