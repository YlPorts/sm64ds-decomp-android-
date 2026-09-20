#pragma once
#include <stdint.h>
#ifdef __cplusplus
struct Triple { int32_t x,y,z; };
struct Mixer { int32_t state; int Apply(int32_t); Triple Vector(int32_t); };
struct Record { uint32_t x,y; Record(); };
struct Cleanup { int32_t *counter; ~Cleanup(); };
struct Face { virtual int Value(); virtual ~Face(); };
extern "C" {
#else
struct Triple { int32_t x,y,z; };
#endif
int32_t _ZN5Mixer5ApplyEi(void*, int32_t);
struct Triple _ZN5Mixer6VectorEi(void*, int32_t);
void _ZN6RecordC1Ev(void*);
void _ZN7CleanupD1Ev(void*);
int fixture_c(int32_t *,struct Triple*);
#ifdef __cplusplus
}
#endif
