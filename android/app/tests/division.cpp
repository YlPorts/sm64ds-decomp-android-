#include "native_division.h"
#include <cassert>
#include <climits>
#include <cstdio>
int main() {
    const uint32_t edges[]={0,1,2,3,0x7fffffff,0x80000000,0xfffffffe,0xffffffff};
    uint32_t state=0x19412004;unsigned checks=0;
    auto test=[&](uint32_t n,uint32_t d) {
        assert(sm64ds_unsigned_quotient(n,d)==(d?n/d:0));
        int32_t a=int32_t(n),b=int32_t(d);
        int64_t expected=b?int64_t(a)/int64_t(b):0;
        assert(uint32_t(sm64ds_signed_quotient(a,b))==uint32_t(expected));checks+=2;
    };
    for(uint32_t n:edges)for(uint32_t d:edges)test(n,d);
    for(int i=0;i<10000;i++){state=state*1664525u+1013904223u;uint32_t n=state;state=state*1664525u+1013904223u;test(n,state);}
    std::printf("PASS %u signed/unsigned division cases\n",checks);
}
