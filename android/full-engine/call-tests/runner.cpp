#include "sm64ds_call_abi.h"
extern "C" int printf(const char*,...);
extern "C" void *call_test_slots[], *call_model_slots[];
extern "C" int native_scalar(void*,int,void*);
extern "C" unsigned long long native_wide(void*);
extern "C" double native_fp(void*);
extern "C" Sm64dsAbiVec3 native_actor_result(void*);
extern "C" Sm64dsAbiVec3 port_actor_s30_base(void*);
extern "C" void *whomp_test_seat();
extern "C" int func_02016ff4(void*,void*,int,int);
extern "C" int offset_calls,complete_calls;
int direct(void*);int typed(void*,void**);int nested(void*,void**);int local(void*,void**);
int cdecl_body(void*,int);
short data_02082214[8192]{};
struct State {void**vt;int a,b;};
static int cases;
#define CHECK(condition,name) do {if(!(condition)){printf("FAIL: %s line %d\n",name,__LINE__);return 1;}++cases;}while(0)
static int radius(void*p){return *(int*)((char*)p+0x68);}
int main(){
 static_assert(sizeof(void*)==4,"Tests require the actual 32-bit game ABI");
 State a{call_test_slots,101,203},b{call_test_slots,4,301};
 CHECK(native_scalar(&a,0,&b)==101,"zero arguments");
 CHECK(native_scalar(&a,1,&b)==118,"integer argument after this");
 CHECK(native_scalar(&a,2,&b)==402,"pointer argument");
 CHECK(native_scalar(&a,3,&b)==150,"three explicit integer arguments");
 CHECK(native_scalar(&a,4,&b)==171,"register and stack arguments");
 CHECK(native_wide(&a)==0x1234567887654321ULL+132,"64-bit alignment after this");
 CHECK(native_fp(&a)==108.75,"floating point call ABI");
 CHECK(native_scalar(&a,7,&b)==203,"single-parameter legacy fastcall");
 CHECK(native_scalar(&a,8,&b)==101,"named discarded EDX");
 CHECK(native_scalar(&a,9,&b)==110,"macro-generated seat");
 CHECK(direct(&a)==113 && typed(&a,call_test_slots)==114 && nested(&a,call_test_slots)==115 && local(&a,call_test_slots)==116,"explicit callers lose only dead argument");
 CHECK(cdecl_body(&a,19)==120,"cdecl natural native call");
 CHECK(((int(*)(void*,int))call_test_slots[10])((char*)&a+8,19)==120,"secondary receiver adjustment retained");
 State model{call_model_slots,0,0};int file=8;
 CHECK(func_02016ff4(&model,&file,3,4)==43 && offset_calls==1 && complete_calls==1,"actual generated model virtual caller");
 CHECK(func_02016ff4(&model,0,3,4)==0 && offset_calls==1,"actual model null resource branch");
 void*vt[31]{};vt[29]=(void*)radius;vt[30]=(void*)port_actor_s30_base;
 alignas(4) unsigned actor[0x420/4]{};*(void***)actor=vt;actor[0x68/4]=47;
 struct Guarded {unsigned before;Sm64dsAbiVec3 value;unsigned after;};
 bool all=true;
 for(int i=0;i<1000;++i){actor[0x5c/4]=i;actor[0x60/4]=i*3;actor[0x64/4]=i*5;
  Guarded g{0x12345678,{},0x87654321};g.value=native_actor_result(actor);
  all=all && g.value.x==i && g.value.y==i*3+47 && g.value.z==i*5 && g.before==0x12345678 && g.after==0x87654321;
 }
 CHECK(all,"actual Actor slot 30: 1000 aggregate returns, nested v29, canaries");
 vt[30]=whomp_test_seat();data_02082214[0]=4096;data_02082214[1]=0;
 actor[0x5c/4]=11;actor[0x60/4]=22;actor[0x64/4]=33;
 Sm64dsAbiVec3 w=native_actor_result(actor);
 CHECK(w.x==819211 && w.y==69 && w.z==33,"actual Whomp slot 30 standard branch");
 ((unsigned char*)actor)[0x414]=1;w=native_actor_result(actor);
 CHECK(w.x==1638411 && w.y==69 && w.z==33,"actual Whomp slot 30 alternate branch");
 printf("PASS: %d native call-ABI cases; real Actor/Whomp vector bodies and generated model caller; NOT GAMEPLAY\n",cases);
 return 0;
}
