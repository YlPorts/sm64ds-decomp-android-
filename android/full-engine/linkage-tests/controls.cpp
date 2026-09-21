#include <cassert>
#include <cstring>
#include <initializer_list>
#include "hal/vs_width.h"
extern "C" {
unsigned char data_0209f498[24*kPortMaxPlayers], data_0209f21c;
unsigned char data_0209f49c[24*kPortMaxPlayers], data_0209f49e[24*kPortMaxPlayers];
unsigned char data_0209f4a0[24*kPortMaxPlayers], data_0209f4a2[24*kPortMaxPlayers];
unsigned char data_0209f4a4[24*kPortMaxPlayers], data_0209f4a6[24*kPortMaxPlayers];
unsigned char data_0209f4ac[24*kPortMaxPlayers];
void port_frame_ctrl_publish();
}
int main() {
    unsigned char *dest[] = {data_0209f49c, data_0209f49e, data_0209f4a0,
                            data_0209f4a2, data_0209f4a4, data_0209f4a6, data_0209f4ac};
    const unsigned fields[] = {4,6,8,10,12,14,20};
    for (unsigned i=0;i<sizeof(data_0209f498);++i) data_0209f498[i] = i % 251;
    for (unsigned count : {0u,1u,4u,16u,255u}) {
        for (auto *d : dest) std::memset(d, 0xed, sizeof(data_0209f498));
        data_0209f21c=count;
        port_frame_ctrl_publish();
        const unsigned n = count == 0 ? 1 : count > kPortMaxPlayers ? kPortMaxPlayers : count;
        for (unsigned field=0;field<7;++field)
            for (unsigned byte=0;byte<sizeof(data_0209f498);++byte) {
                const unsigned player=byte/24, within=byte%24, size=field==6?1:2;
                const unsigned char expected = player<n && within<size ?
                    data_0209f498[player*24+fields[field]+within] : 0xed;
                assert(dest[field][byte] == expected);
            }
    }
}
