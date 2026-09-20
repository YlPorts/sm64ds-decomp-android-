/* Test-only x86 seam shapes. The adapter must transform BOTH ends. */
#include "sm64ds_call_abi.h"
struct State { void **vt; int a; int b; };
int __fastcall slot0(void *s, void *) { return ((State*)s)->a; }
int __fastcall slot1(void *s, void *, int a) { return ((State*)s)->a + a; }
int __fastcall slotp(void *s, void *, State *p) { return ((State*)s)->a + p->b; }
int __fastcall slot3(void *s, void *, int a, int b, int c) { return ((State*)s)->a+a*3+b*5+c*7; }
int __fastcall slot5(void *s, void *, int a, int b, int c, int d, int e) { return ((State*)s)->a+a+b*2+c*3+d*4+e*5; }
unsigned long long __fastcall slot64(void *s, void *, unsigned long long a, int b) {return a + ((State*)s)->a + b;}
double __fastcall slotfp(void *s, void *, double a, float b) {return a + b + ((State*)s)->a;}
int __fastcall onlyself(void *s) {return ((State*)s)->b;}
int __fastcall discard(void*s,void *dead_edx) {(void)dead_edx;return ((State*)s)->a;}
#define THUNK(N) int __fastcall macro_##N(void*s,void*){return ((State*)s)->a + N;}
THUNK(9)
int direct(void*s){return slot1(s,0,12);}
typedef int(__fastcall *Slot)(void*,void*,int);
int typed(void*s,void**v){return ((Slot)v[1])(s,0,13);}
int nested(void*s,void**v){return ((int(__fastcall*)(void*,void*,int))(v[1]))(s,0,14);}
int local(void*s,void**v){int(__fastcall*fn)(void*,void*,int)=(int(__fastcall*)(void*,void*,int))v[1];return fn(s,0,15);}
int __cdecl cdecl_body(void*s,int a){return ((State*)s)->a+a;}
/* A secondary-object receiver must retain its deliberate -8 adjustment. */
int __fastcall adjusted(void*s,void*,int a){return ((State*)((char*)s-8))->a+a;}
extern "C" void *call_test_slots[]={(void*)slot0,(void*)slot1,(void*)slotp,(void*)slot3,(void*)slot5,(void*)slot64,(void*)slotfp,(void*)onlyself,(void*)discard,(void*)macro_9,(void*)adjusted};
/* The same real model-call signature reached by generated func_02016ff4. */
struct BMD_File {int marker;};
int __fastcall model_set(void*s,void*,BMD_File*f,int a,int b){return f->marker+a*10+b;}
extern "C" void *call_model_slots[3]={0,0,(void*)model_set};
extern "C" int offset_calls=0, complete_calls=0;
extern "C" void _ZN5Model17UpdateFileOffsetsER8BMD_File(BMD_File &f){++offset_calls;f.marker+=1;}
extern "C" int func_02017060(BMD_File*){++complete_calls;return 0;}
/* Test configuration enables the post-vcall callback. This is a fixture, not
   the game's production settings provider or a resource-loading test. */
extern "C" int port_model_shrink_enabled(void){return 1;}
