/* Separate translation unit: Clang must implement the native virtual ABI. */
#include "sm64ds_call_abi.h"
struct Dispatch {
 virtual int zero(); virtual int one(int); virtual int pointer(void*);
 virtual int three(int,int,int); virtual int five(int,int,int,int,int);
 virtual unsigned long long wide(unsigned long long,int);
 virtual double floating(double,float); virtual int receiver(); virtual int discarded();
 virtual int macro(); virtual int adjust(int);
};
extern "C" __attribute__((noinline)) int native_scalar(void*p, int which, void*other){
 auto*d=(Dispatch*)p;
 switch(which){case 0:return d->zero();case 1:return d->one(17);case 2:return d->pointer(other);
 case 3:return d->three(2,3,4);case 4:return d->five(2,3,4,5,6);
 case 7:return d->receiver();case 8:return d->discarded();case 9:return d->macro();default:return -1;}
}
extern "C" __attribute__((noinline)) unsigned long long native_wide(void*p){return ((Dispatch*)p)->wide(0x1234567887654321ULL,31);}
extern "C" __attribute__((noinline)) double native_fp(void*p){return ((Dispatch*)p)->floating(5.5,2.25f);}
struct ActorSlots {
 virtual int v0();virtual int v1();virtual int v2();virtual int v3();virtual int v4();virtual int v5();virtual int v6();virtual int v7();virtual int v8();virtual int v9();
 virtual int v10();virtual int v11();virtual int v12();virtual int v13();virtual int v14();virtual int v15();virtual int v16();virtual int v17();virtual int v18();virtual int v19();
 virtual int v20();virtual int v21();virtual int v22();virtual int v23();virtual int v24();virtual int v25();virtual int v26();virtual int v27();virtual int v28();virtual int radius();
 virtual Sm64dsAbiVec3 result();
};
extern "C" __attribute__((noinline)) Sm64dsAbiVec3 native_actor_result(void*p){return ((ActorSlots*)p)->result();}
