#include "api.h"
extern "C" {
/* Deliberate conversions: eliding these wrappers would change the result. */
int32_t _ZN5Mixer5ApplyEi(void *p,int32_t x) {return static_cast<Mixer*>(p)->Mixer::Apply(x+3)+1;}
Triple _ZN5Mixer6VectorEi(void *p,int32_t n) {
 Triple v=static_cast<Mixer*>(p)->Mixer::Vector(n);v.z-=100;return v;
}
/* An explicitly recovered table must coexist with the compiler's vtable. */
uintptr_t _ZTV4Face[4]={17,19,23,29};
uintptr_t *literal_face_table() {return _ZTV4Face;}
}
