// ELF equivalent of io.cpp's Windows TLS process-attach reservation.
// NitroFsNamesBoot writes the cartridge header mirror during dynamic init.
#include "ntr/mmio.h"
#include <unistd.h>

__attribute__((constructor(101))) static void reserve_ds_memory() {
    // Reserve only. io_init also starts IPC, which must wait for the ARM7
    // model's ordinary C++ registration constructor to have run.
    ntr::io_reserve(1);
    if (!ntr::io_reserve_stage_won()) {
        const char message[] = "SM64DS: cannot reserve required Nintendo DS memory\n";
        (void)!write(STDERR_FILENO,message,sizeof(message)-1);
        _exit(2);
    }
}
