/* Native aggregate-return contract for Actor virtual slot 30. */
#ifndef SM64DS_CALL_ABI_H
#define SM64DS_CALL_ABI_H
struct Sm64dsAbiVec3 { int x, y, z; };
static_assert(sizeof(Sm64dsAbiVec3) == 12 && alignof(Sm64dsAbiVec3) == 4,
              "Actor slot 30 requires a 12-byte vector with word alignment");
#endif
