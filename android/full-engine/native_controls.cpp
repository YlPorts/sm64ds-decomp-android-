// Publish Ctrl's split storage at the same boundary as the Windows frontend:
// after Stage::Behavior, before the other actors read their controller record.
#include <cstdint>
#include <cstring>
#include "hal/vs_width.h"

extern "C" {
extern unsigned char data_0209f498[], data_0209f21c;
extern unsigned char data_0209f49c[], data_0209f49e[], data_0209f4a0[];
extern unsigned char data_0209f4a2[], data_0209f4a4[], data_0209f4a6[], data_0209f4ac[];

// Registered by port_actor_registry_install; also read by quarantine diagnostics.
const char *(*port_classname_resolver)(unsigned) = nullptr;

void port_frame_ctrl_publish() {
    unsigned count = data_0209f21c;
    if (count < 1) count = 1;
    if (count > kPortMaxPlayers) count = kPortMaxPlayers;
    for (unsigned player = 0; player < count; ++player) {
        const unsigned offset = player * 0x18;
        const auto *record = data_0209f498 + offset;
        // memcpy permits the original byte/halfword declarations to coexist
        // without alignment or strict-aliasing assumptions in the native host.
        std::memcpy(data_0209f49c + offset, record + 4, 2);
        std::memcpy(data_0209f49e + offset, record + 6, 2);
        std::memcpy(data_0209f4a0 + offset, record + 8, 2);
        std::memcpy(data_0209f4a2 + offset, record + 10, 2);
        std::memcpy(data_0209f4a4 + offset, record + 12, 2);
        std::memcpy(data_0209f4a6 + offset, record + 14, 2);
        data_0209f4ac[offset] = record[20];
    }
}
}
