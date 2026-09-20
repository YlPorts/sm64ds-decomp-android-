# Android native platform integration — stage 0.4

**This target is a platform integration probe, not the complete game or an APK.**
It builds the 13 source files in upstream `port/ntr/` into a native static library.
The probe links and exercises real I/O, geometry command decoding, texture
sampling and software rasterisation. It does not replace the renderer with a
mock. The display list and checker texture are synthetic, not game assets.

Baseline: fork `android/native-bootstrap`, commit
`17af8ddbfde52acee1aafa47cfe754904ec8f073`, built upon upstream `port/link100`
`9bb3c454f9d67ee25ea9d08735e1f3943bbd6225`.
All adaptations are generated in the build directory. Upstream `src/`, `port/`
and the fork's `main` branch are not changed.

## What is added

* `sm64ds_ntr_platform`: original platform files plus the previously reviewed
  fiber adapter for `rt.cpp` and narrow, hash-pinned adaptations of `io.cpp`,
  `runtime.cpp` and `backup.cpp`.
* Explicit ELF section attributes on the NTR state globals that previously
  used MSVC section pragmas. This is not a complete save-state implementation;
  section-wide capture of the whole engine and restoration of host resources
  remain unimplemented.
* A standard path-size constant and the missing standard declaration of
  `size_t`, without suppressing compiler errors or defining `_WIN32`.
* A probe of memory initialisation, division/remainder, square root, GX FIFO
  readiness, real command submission, textured pixels, coverage and BMP output.
* Seven Python regression tests of the reviewed source transformations.

## Build with Android NDK

Use this module inside the fork checkout, not as a standalone directory.
The project still requires 32-bit pointers; it intentionally rejects ARM64.

```sh
cmake -S android/engine -B build/platform-android -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=armeabi-v7a -DANDROID_PLATFORM=android-23 \
  -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release
cmake --build build/platform-android --parallel 2
```

CI uses NDK `28.2.13676358`. Outputs include `libsm64ds_ntr_platform.a` and
`sm64ds_platform_probe`. They are not an Android application package.
Cross-compilation alone does not establish Android execution.

## Execute on ARM Linux (CI)

```sh
cmake -S android/engine -B build/platform-arm -G Ninja \
  -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_SYSTEM_PROCESSOR=armv7 \
  -DCMAKE_C_COMPILER=arm-linux-gnueabihf-gcc \
  -DCMAKE_CXX_COMPILER=arm-linux-gnueabihf-g++ \
  -DCMAKE_ASM_COMPILER=arm-linux-gnueabihf-gcc \
  '-DCMAKE_CROSSCOMPILING_EMULATOR=qemu-arm;-L;/usr/arm-linux-gnueabihf' \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build/platform-arm --parallel 2
ctest --test-dir build/platform-arm --verbose --output-on-failure
```

QEMU is only an instruction runner for CI; it is not included in the port.
The rendered diagnostic is `build/platform-arm/platform-probe.bmp`.

## Important boundaries

Archiving all platform objects is not full-engine link closure. The executable
uses ordinary dead-code elimination and only pulls the platform paths reached
by the probe. The backup driver's initialiser, production BSS aliases, complete
IRQ/frame integration, resource loading, main-screen compositing, the second
screen, audio output, controls and Android lifecycle are not validated here.

In particular, GCC reports a pre-existing `backup.cpp` bound mismatch: its
60-byte declaration is used for a copy into the larger contiguous card span.
The live engine's storage and declarations must be reconciled before enabling
that path; this probe does not use it, disable bounds checks, or claim saving
works. The original fixed-address memory mapping also needs device testing.

A full engine target that starts a real scene is still required. No gameplay,
frame-rate, GPU acceleration, widescreen or physical-device result is claimed.

The bootstrap code retains its MIT license; upstream files retain their license.

## Verified stage-0.4 run

Code commit `b4730efe0f7a638b1a356dce8bebe38b7f244767` passed workflow
`35494196213`: Android ARMv7 NDK compilation/linking, ARM Linux compilation
and the real platform probe under QEMU. The probe rasterised one textured
triangle with 6,144 covered pixels (3,000 white, 3,144 green), then wrote a BMP.
Both CTest entries (pipeline and fibers) passed. No Android device was used.
