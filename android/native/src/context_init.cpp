// SPDX-License-Identifier: MIT
// Native replacements for two original hand-written assembly primitives.
// References at upstream 9bb3c454f9d67ee25ea9d08735e1f3943bbd6225:
// src/func_02058568.c (blob 4a5b34f255e605898736e7d5d7ab352925c7cbce)
// src/MultiStore_Int.c (blob 6e598fa2bf5caab8c1550ba060ad70ba87ea1c2f)
// This INITIALIZES the original record, not the host CPU context. The separate
// fiber backend carries execution state. Do not also link the Windows HAL bodies.
#include <cstdint>
#include <cstring>
static_assert(sizeof(void *) == 4, "Original context records require 32-bit pointers");
namespace {
void store(void *ctx, unsigned offset, std::uint32_t value) {
    std::memcpy(static_cast<unsigned char *>(ctx) + offset, &value, 4);
}
}
extern "C" void func_02058568(void *ctx, unsigned pc, unsigned sp) {
    store(ctx, 0x40, pc + 4u);
    store(ctx, 0x44, sp);
    store(ctx, 0x38, sp - 0x40u);
    store(ctx, 0, (pc & 1u) ? 0x3fu : 0x1fu);
    for (unsigned offset = 4; offset <= 0x34; offset += 4) store(ctx, offset, 0);
    store(ctx, 0x3c, 0);
}
extern "C" void MultiStore_Int(int value, int *dst, int length) {
    // Each original store is four bytes; valid game callers provide a byte count
    // and writable, aligned memory. A positive non-multiple of four rounds up.
    auto *p = reinterpret_cast<unsigned char *>(dst);
    for (int offset = 0; offset < length;) {
        std::memcpy(p + offset, &value, 4);
        if (length - offset <= 4) break;
        offset += 4;
    }
}
