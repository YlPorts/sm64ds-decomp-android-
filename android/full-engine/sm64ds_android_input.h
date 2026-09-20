#ifndef SM64DS_ANDROID_INPUT_H
#define SM64DS_ANDROID_INPUT_H
#include <cstdint>
#include "hal/pad_backend.h"

/* Android event producers may run on another thread. All publication is under
   one short mutex; the engine reads copies, never pointers into event storage.
   Android must notify focus loss AND device removal (InputDeviceListener).
   This is an input backend, not a UI or an Activity implementation. */
namespace sm64ds::input {
constexpr unsigned Keyboard = 0x101, Dpad = 0x201, Gamepad = 0x401;
constexpr unsigned Touchscreen = 0x1002, Stylus = 0x4002, Joystick = 0x1000010;
struct Axes {
    float lx{}, ly{}, rx{}, ry{}, lt{}, rt{}, hat_x{}, hat_y{};
};
struct Pointer {
    int down{}, x{}, y{}, focused{}, tab{};
    std::uint32_t generation{}, gesture{};
};
// Raw standard Android keycodes/actions, not Windows scan codes. Unknown keys
// and system Back/volume events are left unconsumed for Android to handle.
bool key(int device, unsigned source, int code, int action, bool canceled=false);
bool axes(int device, const Axes &value);
bool pointer(int device, int id, int action, float x, float y);
void focus(bool focused);
void remove_device(int device);
void reset();
// Optional on-screen pad publisher. This does NOT draw controls or hit-test a UI.
// It remains independent from a connected physical pad; neutral virtual axes
// never mask physical axes. The caller aggregates its own multi-touch controls.
void virtual_pad(const PortPadState &state, bool enabled);
Pointer pointer_snapshot();
bool focused();
// Legacy VK preferences are translated only for the game's existing keyboard
// bindings. No global operating-system keyboard polling or Windows API shim.
bool legacy_key_held(int code);
} // namespace sm64ds::input

#ifdef __ANDROID__
struct AInputEvent;
extern "C" int sm64ds_android_handle_input(const AInputEvent *event);
#endif
#endif
