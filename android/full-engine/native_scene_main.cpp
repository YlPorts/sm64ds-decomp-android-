// Finite native scene runner replacing walk_window.cpp's Windows executable.
// This is an engine integration entry, not an Android Activity or a game APK.
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include "ntr/mmio.h"
#include "hal/comms_loopback.h"

extern "C" {
void port_romdata_load();
bool sm64ds_native_scheduler_init();
void port_boot_rom_pre_main();
void _ZN4Heap18InitializeRootHeapEv();
extern void *data_020a0ea0;
void port_rom_main_run();
void port_install_host_frame_pump(int (*)(unsigned));
void hal_fill_model_vtable();
void hal_fill_shadow_vtable();
void hal_fill_mmc_vtable();
void hal_fill_modelanim2_vtable();
void port_ov002_patch();
void port_cross_patch();
extern int data_0209b3ec[12];
int port_scene_run();
int port_scene_is_hosted(int);
void port_scene_layout_propose();
void func_0201a4e4();
#define SINIT(address) void __sinit_ov002_##address();
SINIT(02100560) SINIT(02100938) SINIT(02100adc) SINIT(02100c50)
SINIT(02100d44) SINIT(02100e50) SINIT(02100ec4) SINIT(02100f84)
SINIT(02101064) SINIT(02101478) SINIT(021014e4) SINIT(02101588)
SINIT(02101738) SINIT(02101894) SINIT(02101900) SINIT(02101968)
SINIT(021019d0) SINIT(02106e40) SINIT(02107118) SINIT(021071f4)
SINIT(02107298) SINIT(02107304) SINIT(02107370) SINIT(02107f88)
SINIT(0210804c) SINIT(02108094)
#undef SINIT
}

namespace {
int pace(unsigned) {
    timespec delay{0, 16666667};
    while (nanosleep(&delay, &delay) != 0) {
        if (errno != EINTR) return 0;
    }
    return 1;
}
bool number(const char *text, long low, long high, long &value) {
    char *end = nullptr;
    errno = 0;
    value = std::strtol(text, &end, 10);
    return !errno && end != text && !*end && value >= low && value <= high;
}
void usage() {
    std::fputs("sm64ds-native-scene --assets ROOT --scene ID --frames COUNT\n"
               "Finite scene runner; ROOT contains build/assets and extracted.\n"
               "Synthetic LINK-ONLY inventories cannot run scenes.\n", stderr);
}
}

extern "C" int sm64ds_engine_initialize(int (*pump)(unsigned)) {
#ifndef SM64DS_NATIVE_REAL_RESOURCES
    const volatile bool synthetic_resources = true;
    if (synthetic_resources) {
        std::fputs("Cannot boot: this inventory contains LINK-ONLY tables.\n", stderr);
        return 3;
    }
#endif
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    if (!ntr::io_init()) { std::fputs("Native memory reservation failed.\n", stderr); return 2; }
    port::comms_loopback_install_from_env();
    port_romdata_load();
    if (!sm64ds_native_scheduler_init()) {
        std::fputs("Native scheduler initialization failed.\n", stderr);
        return 2;
    }
    std::fputs("[android-boot] pre-main\n", stderr);
    port_boot_rom_pre_main();
    std::fputs("[android-boot] root heap\n", stderr);
    _ZN4Heap18InitializeRootHeapEv();
    if (!data_020a0ea0) { std::fputs("Root heap initialization failed.\n", stderr); return 2; }
    port_install_host_frame_pump(pump ? pump : pace);
    std::fputs("[android-boot] ROM main\n", stderr);
    port_rom_main_run();
    std::memset(data_0209b3ec, 0, sizeof data_0209b3ec);
    data_0209b3ec[0] = data_0209b3ec[4] = data_0209b3ec[8] = 0x1000;
    hal_fill_model_vtable(); hal_fill_shadow_vtable();
    hal_fill_mmc_vtable(); hal_fill_modelanim2_vtable();
    port_ov002_patch(); port_cross_patch();
#define SINIT(address) __sinit_ov002_##address();
    SINIT(02100560) SINIT(02100938) SINIT(02100adc) SINIT(02100c50)
    SINIT(02100d44) SINIT(02100e50) SINIT(02100ec4) SINIT(02100f84)
    SINIT(02101064) SINIT(02101478) SINIT(021014e4) SINIT(02101588)
    SINIT(02101738) SINIT(02101894) SINIT(02101900) SINIT(02101968)
    SINIT(021019d0) SINIT(02106e40) SINIT(02107118) SINIT(021071f4)
    SINIT(02107298) SINIT(02107304) SINIT(02107370) SINIT(02107f88)
    SINIT(0210804c) SINIT(02108094)
#undef SINIT
    func_0201a4e4();
    port_scene_layout_propose();
    std::fputs("[android-boot] engine initialized\n", stderr);
    return 0;
}

#ifndef SM64DS_NATIVE_SHARED
int main(int argc, char **argv) {
    if (argc == 2 && !std::strcmp(argv[1], "--help")) { usage(); return 0; }
    const char *root = nullptr, *scene = nullptr, *frames = nullptr;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) { usage(); return 2; }
        const char **slot = !std::strcmp(argv[i], "--assets") ? &root :
                            !std::strcmp(argv[i], "--scene") ? &scene :
                            !std::strcmp(argv[i], "--frames") ? &frames : nullptr;
        if (!slot || *slot) { usage(); return 2; }
        *slot = argv[i + 1];
    }
    long scene_id = 0, frame_count = 0;
    if (!root || !scene || !frames || !*root ||
        !number(scene, 0, 10000, scene_id) ||
        !number(frames, 1, 1000000, frame_count)) { usage(); return 2; }
    // The resource generator's mode is part of the build, never a runtime
    // override. Keep the complete boot code linked for the retained-reference
    // audit while refusing execution with fabricated tables.
#ifndef SM64DS_NATIVE_REAL_RESOURCES
    const volatile bool synthetic_resources = true;
    if (synthetic_resources) {
        std::fputs("Cannot boot: this inventory contains LINK-ONLY tables.\n", stderr);
        return 3;
    }
#endif
    // The hosted spawn table is installed by port_scene_begin, after loading
    // ROM data and seating the registry. Before boot it is correctly empty.
    if (setenv("SM64DS_ASSET_ROOT", root, 1) ||
        setenv("SM64DS_SCENE", scene, 1) ||
        setenv("SM64DS_SCENE_FRAMES", frames, 1)) return 2;
    // A finite scene owns its loop. The ROM main still performs its real boot
    // and constructor walk; its optional infinite-loop diagnostic stays off.
    if (setenv("SM64DS_ROM_LOOP", "0", 1) ||
        setenv("SM64DS_ROM_MAIN", "1", 1) ||
        setenv("SM64DS_TITLE_ENTRY", "0", 1)) return 2;
    int result = sm64ds_engine_initialize(pace);
    if (result) return result;
    return port_scene_run();
}
#endif
