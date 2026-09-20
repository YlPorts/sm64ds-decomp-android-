/* ABI probe over original recovered providers, called by their C symbol names.
 * The cylinder and mesh query storage below is a 32-bit layout fixture, not
 * gameplay or proof of C++ object lifetime for every actor class.
 * The timer clock and active-list head are explicit boundary fixtures.
 */
#include "types.h"
#include "CylinderClsn.h"
_Static_assert(sizeof(void*) == 4, "Probe requires actual 32-bit layouts");
void *data_0209cee8;
static s64 clock_value;
s64 func_02059650(void) { return clock_value; }
extern void _ZN12CylinderClsn5ClearEv(void *);
extern void _ZN12CylinderClsn6UpdateEv(void *);
extern void _ZN12WithMeshClsn13SetGroundFlagEv(void *);
extern void _ZN12WithMeshClsn13SetLimMovFlagEv(void *);
extern void _ZN12WithMeshClsn15ClearGroundFlagEv(void *);
extern void _ZN12WithMeshClsn15ClearLimMovFlagEv(void *);
extern void _ZN12WithMeshClsn19ClearAllGroundFlagsEv(void *);
extern void _ZN5Timer10ResetTimerEv(void *);
extern void _ZN5Timer10StartTimerEv(void *);
extern void _ZN5Timer9StopTimerEv(void *);
extern s64 _ZN5Timer7GetTimeEv(void *);
int native_face_checks;
#define CHECK(x) do { ++native_face_checks; if (!(x)) return __LINE__; } while(0)
int native_face_probe(void) {
    struct { u32 before; struct CylinderClsn c; u32 after; } a = {0};
    struct CylinderClsn b = {0};
    a.before=0x13572468; a.after=0xabcdef01;
    a.c.radius=71; a.c.height=82; a.c.flags=0x2222; a.c.vulnFlags=0x55;
    a.c.pushbackX=3; a.c.pushbackY=-7; a.c.pushbackZ=9;
    a.c.hitFlags=19; a.c.otherOwner=23;
    _ZN12CylinderClsn5ClearEv(&a.c);
    CHECK(a.c.pushbackX==0 && a.c.pushbackY==0 && a.c.pushbackZ==0);
    CHECK(a.c.hitFlags==0 && a.c.otherOwner==0);
    CHECK(a.c.radius==71 && a.c.height==82 && a.c.flags==0x2222 && a.c.vulnFlags==0x55);
    CHECK(a.before==0x13572468 && a.after==0xabcdef01);
    _ZN12CylinderClsn6UpdateEv(&a.c);
    CHECK(data_0209cee8==&a.c && a.c.next==0);
    _ZN12CylinderClsn6UpdateEv(&b);
    CHECK(data_0209cee8==&b && b.next==&a.c && a.c.prev==&b);
    a.c.flags |= 1;
    _ZN12CylinderClsn6UpdateEv(&a.c);
    CHECK(data_0209cee8==&b && b.next==&a.c);
    CHECK(a.before==0x13572468 && a.after==0xabcdef01);
    u32 mesh[128];
    for (int i=0;i<128;++i) mesh[i]=0xa5000000u+(u32)i;
    mesh[4]=0x55667700;
    _ZN12WithMeshClsn13SetGroundFlagEv(mesh); CHECK(mesh[4]==0x55667710);
    _ZN12WithMeshClsn13SetLimMovFlagEv(mesh); CHECK(mesh[4]==0x55667790);
    _ZN12WithMeshClsn15ClearGroundFlagEv(mesh); CHECK(mesh[4]==0x55667780);
    _ZN12WithMeshClsn15ClearLimMovFlagEv(mesh); CHECK(mesh[4]==0x55667700);
    mesh[4]|=0x70;
    _ZN12WithMeshClsn19ClearAllGroundFlagsEv(mesh); CHECK(mesh[4]==0x55667700);
    for (int i=0;i<128;++i) if(i!=4) CHECK(mesh[i]==0xa5000000u+(u32)i);
    union { s64 align; u32 words[4]; } timer = {0};
    timer.words[3]=0xcafef00d;
    _ZN5Timer10ResetTimerEv(&timer); CHECK(_ZN5Timer7GetTimeEv(&timer)==0);
    clock_value=0x123456789LL;
    _ZN5Timer10StartTimerEv(&timer);
    clock_value += 0x100000005LL;
    CHECK(_ZN5Timer7GetTimeEv(&timer)==0x100000005LL);
    _ZN5Timer9StopTimerEv(&timer);
    clock_value += 0x456;
    CHECK(_ZN5Timer7GetTimeEv(&timer)==0x100000005LL);
    _ZN5Timer10StartTimerEv(&timer);
    clock_value += 0x44;
    CHECK(_ZN5Timer7GetTimeEv(&timer)==0x100000049LL);
    _ZN5Timer9StopTimerEv(&timer);
    _ZN5Timer10ResetTimerEv(&timer);
    CHECK(_ZN5Timer7GetTimeEv(&timer)==0 && timer.words[3]==0xcafef00d);
    return 0;
}
#ifndef SM64DS_BARE_FACE_PROBE
#include <stdio.h>
int main(void) { int result=native_face_probe();
    printf("%s %d checks across 11 original 32-bit method providers, failing line %d; not gameplay\n", result?"FAIL":"PASS",native_face_checks,result);
    return result?1:0;
}
#endif
