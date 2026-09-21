// Controlled dependencies; the HalFaderWipe class under test is extracted from
// port/hal/fader_wipes.cpp, then transformed by the production adapter.
#include <cassert>
#include <cstdint>
using Fix12i=int;
static bool g_hal_fader_stepping=false;
static void hal_wipe_note(const char*,void*) {}
static void *destroyed, *deleted;
extern "C" void *_ZN9FaderWipeD1Ev(void *p) { destroyed=p;return p; }
extern "C" void *_ZN9FaderWipeD0Ev(void *p) { deleted=p;return p; }
extern "C" void _ZN3G2x18SetBlendBrightnessEPVtts(volatile unsigned short*,unsigned short,short) { assert(false); }
struct Fader {
    void AdvanceInterp() { auto *p=(int*)this;p[1]+=p[2]; }
};
struct FaderBrightness {
    int IsAtStart() { return ((int*)this)[1]==0; }
    int IsAtEnd() { return ((int*)this)[1]==0x1000; }
    void SetToEnd() { ((int*)this)[1]=0x1000; }
    void SetToStart() { ((int*)this)[1]=0; }
};
