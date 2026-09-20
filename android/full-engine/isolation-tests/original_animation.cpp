/* A real Animation object; its destructor is an explicit test-only boundary.
 * SetFlags/GetFrameCount and the C->C++ SetFlags bridge are original sources. */
#include "Animation.h"
#include <cstdint>
Animation::~Animation() = default;
extern "C" void _ZN9Animation8SetFlagsEi(void *,int);
extern "C" int probe_original_animation(int *checks) {
 struct Guarded { uint32_t before; Animation a; uint32_t after; } v;
 v.before=0xface1234;v.after=0xaabbccdd;
 v.a.currFrame=Fix12i(0x123450);v.a.speed=Fix12i(-0x45600);
 // Copy the object representation of fields to avoid relying on test assumptions
 // about the implicit fixed-point constructor's scaling convention.
 auto curr=v.a.currFrame, speed=v.a.speed;
 for(unsigned f=0;f<1000;++f){
  uint32_t frames=(f+1)<<12;
  v.a.numFramesAndFlags=frames;
  _ZN9Animation8SetFlagsEi(&v.a,(int)(f%4u<<30));
  ++*checks;if(v.a.numFramesAndFlags!=(frames|(f%4u<<30)))return 1;
  ++*checks;if(v.a.GetFrameCount()!=f+1)return 2;
  ++*checks;if(v.a.currFrame!=curr || v.a.speed!=speed)return 3;
  ++*checks;if(v.before!=0xface1234 || v.after!=0xaabbccdd)return 4;
 }
 return 0;
}
