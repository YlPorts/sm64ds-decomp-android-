#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
static_assert(sizeof(void*)==4,"Recovered source checks require 32-bit addresses");
static int cases, deaths, stars, transitions, dma_calls, clear_calls;
#define CHECK(c) do { if(!(c)) {fprintf(stderr,"FAIL source line %d: %s\n",__LINE__,#c);return 1;} ++cases; } while(0)
extern "C" {
void func_ov002_020e8c34(void*);
void func_ov002_020e8dd8(unsigned char*);
void func_ov014_0211150c(char*);
void func_0205a290();
void func_020393d4(int*,int);
int *RotatingFirebar_Spawn();
void func_ov002_020e8abc(){++deaths;}
signed char data_0209f2f8;
unsigned char data_0209f264;
void _ZN9PowerStar13AddStarMarkerEv(){++stars;}
static int busy, timer;
int _Z14ApproachLinearRiii(int *p,int a,int){*p=a;return 0;}
int ApproachAngle(void*,int,int,int,int){return 0;}
int Math_Function_0203b14c(void*,int,int,int,int){return busy;}
int DecIfAbove0_Short(void*){return timer;}
int func_ov014_02111ebc(void*,int v){transitions+=v;return 0;}
struct G6460 {void(*f0)(int);int f4,f8,fc;void(*f10)(int);int f14,f18;void*f1c;} data_020a6460;
struct DMAIRQEntry {uint32_t handler,active,arg;} data_020a60c4[8];
uint32_t _ZN3IRQ10EnableIRQsEj(uint32_t mask){return mask;}
void func_0205a21c(){}
static int dma_args[4];
void DMAStartTransfer(int a,int b,int c,int d){++dma_calls;dma_args[0]=a;dma_args[1]=b;dma_args[2]=c;dma_args[3]=d;}
void _ZN3IRQ15ClearInterruptsEj(unsigned int){++clear_calls;}
alignas(16) unsigned char firebar[0x540+16];
void * _ZTV15RotatingFirebar[1];
static int alloc_failed, ctor_calls, array_ok;
void* _ZN9ActorBasenwEj(unsigned n){return alloc_failed||n!=0x540?nullptr:firebar;}
void _ZN8PlatformC2Ev(void*){}
void _ZN19CylinderClsnWithPosC1Ev(void*p){++ctor_calls;*static_cast<unsigned*>(p)=0x76543210;}
void _ZN19CylinderClsnWithPosD1Ev(void*){}
// Deliberate boundary fixture, NOT the original array constructor.
void func_020733a8(void *p,int n,int size,void *ctor,void *dtor){
 array_ok=p==firebar+0x360 && n==8 && size==0x3c && ctor==reinterpret_cast<void*>(&_ZN19CylinderClsnWithPosC1Ev) && dtor==reinterpret_cast<void*>(&_ZN19CylinderClsnWithPosD1Ev);
 if(array_ok) for(int i=0;i<n;++i) reinterpret_cast<void(*)(void*)>(ctor)(static_cast<char*>(p)+i*size);
}
}
static void callback(int*p){*p=47;}
int main(){
 alignas(16) unsigned char actor[0x620]{};
 func_ov002_020e8c34(actor); CHECK(deaths==0);
 *reinterpret_cast<int*>(actor+0x5c)=0x13880001;func_ov002_020e8c34(actor);CHECK(deaths==1);
 *reinterpret_cast<int*>(actor+0x5c)=0;*reinterpret_cast<int*>(actor+0x60)=-1;func_ov002_020e8c34(actor);CHECK(deaths==2);
 data_0209f2f8=5;actor[0x49d]=5;func_ov002_020e8dd8(actor);CHECK(stars==0);
 data_0209f2f8=0x16;actor[0x49d]=4;data_0209f264=3;func_ov002_020e8dd8(actor);CHECK(stars==0);
 data_0209f264=4;func_ov002_020e8dd8(actor);CHECK(stars==1);
 data_0209f2f8=0;actor[0x49a]=0;func_ov002_020e8dd8(actor);CHECK(stars==1);
 *reinterpret_cast<int*>(actor+0x43c)=2;func_ov002_020e8dd8(actor);CHECK(stars==2);
 busy=1;timer=0;func_ov014_0211150c(reinterpret_cast<char*>(actor));CHECK(transitions==0);
 busy=0;timer=1;func_ov014_0211150c(reinterpret_cast<char*>(actor));CHECK(transitions==0);
 timer=0;func_ov014_0211150c(reinterpret_cast<char*>(actor));CHECK(transitions==1);
 CHECK(*reinterpret_cast<int*>(actor+0x80)==0x1000 && *reinterpret_cast<int*>(actor+0x84)==0x1000);
 data_020a6460={};func_0205a290();CHECK(dma_calls==0);
 data_020a6460.f4=2;data_020a6460.f8=0x10000;data_020a6460.fc=16;func_0205a290();
 CHECK(dma_calls==1 && clear_calls==1 && data_020a6460.fc==0 && data_020a6460.f8==0x10010);
 CHECK(data_020a60c4[2].handler==reinterpret_cast<uintptr_t>(&func_0205a21c) && data_020a60c4[2].arg==0 && data_020a60c4[2].active==(1u<<10));
 CHECK(dma_args[0]==2 && dma_args[1]==0x10000 && dma_args[2]==0x4000400);
 data_020a60c4[2].handler=0;data_020a6460.fc=0x200;func_0205a290();
 CHECK(data_020a6460.fc==0x28 && data_020a60c4[2].handler==0);
 int record[8]{};func_020393d4(record,(int)reinterpret_cast<uintptr_t>(&callback));
 int value=0;reinterpret_cast<void(*)(int*)>((uintptr_t)(uint32_t)record[6])(&value);CHECK(value==47);
 memset(firebar,0,sizeof firebar);memset(firebar+0x540,0xa5,16);
 int *p=RotatingFirebar_Spawn();CHECK(p==reinterpret_cast<int*>(firebar) && array_ok && ctor_calls==8);
 CHECK(*reinterpret_cast<void***>(firebar)==_ZTV15RotatingFirebar);
 CHECK(firebar[0x540]==0xa5 && firebar[sizeof firebar-1]==0xa5);
 alloc_failed=1;CHECK(RotatingFirebar_Spawn()==nullptr && ctor_calls==8);
 printf("PASS: %d recovered-source checks. DMA registration and callback word store are original providers; other subsystem callbacks are explicit fixtures. NOT GAMEPLAY\n",cases);
}
