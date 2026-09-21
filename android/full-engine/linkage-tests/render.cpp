// Calls the actual four matching Render bodies after dynamic-receiver adaptation.
#include <cassert>
#include <cstdint>
#include <cstring>
extern "C" {
int bullet(void*) asm("_ZN10BulletBill6RenderEv");
int flame(void*) asm("_ZN10FlameChomp6RenderEv");
int baby(void*) asm("_ZN11BabyPenguin6RenderEv");
int butterfly(void*) asm("_ZN9Butterfly6RenderEv");
}
static void *receivers[8], *arguments[8];
static int calls;
static void pointer_call(void *self, void *arg) { receivers[calls]=self;arguments[calls++]=arg; }
static void integer_call(void *self, int arg) { receivers[calls]=self;arguments[calls++]=(void*)(intptr_t)arg; }
static void unexpected(void*,void*) { assert(false); }
static void *pointer_table[6] = {(void*)unexpected,(void*)unexpected,(void*)unexpected,
    (void*)unexpected,(void*)unexpected,(void*)pointer_call};
static void *integer_table[6] = {(void*)unexpected,(void*)unexpected,(void*)unexpected,
    (void*)unexpected,(void*)unexpected,(void*)integer_call};
static void table(unsigned char *object, unsigned offset, void **vt) {
    std::memcpy(object+offset,&vt,sizeof(vt));
}
int main() {
    static_assert(sizeof(void*)==4);
    alignas(8) unsigned char object[0x600]{};
    table(object,0x30c,integer_table);table(object,0x35c,integer_table);
    assert(bullet(object)==1 && calls==2);
    assert(receivers[0]==object+0x30c && receivers[1]==object+0x35c);
    assert(!arguments[0] && !arguments[1]);
    calls=0;table(object,0xd4,pointer_table);
    assert(flame(object)==1 && calls==1);
    assert(receivers[0]==object+0xd4 && arguments[0]==object+0x80);
    calls=0;assert(baby(object)==1 && calls==1);
    assert(receivers[0]==object+0xd4 && arguments[0]==object+0x80);
    uint32_t hidden=0x40000;std::memcpy(object+0xb0,&hidden,4);
    calls=0;assert(baby(object)==1 && calls==0);
    table(object,0xd4,integer_table);table(object,0x138,pointer_table);
    object[0x3f1]=1;assert(butterfly(object)==1 && calls==1);
    assert(receivers[0]==object+0xd4 && !arguments[0]);
    calls=0;object[0x3f1]=0;assert(butterfly(object)==1 && calls==1);
    assert(receivers[0]==object+0x138 && arguments[0]==object+0x80);
    calls=0;uint32_t disabled=4;std::memcpy(object+0x3e4,&disabled,4);
    assert(butterfly(object)==1 && calls==0);
}
