#include "api.h"
int fixture_c(int32_t *state,struct Triple *output) {
 int answer=_ZN5Mixer5ApplyEi(state,9);
 *output=_ZN5Mixer6VectorEi(state,5);
 return answer;
}
/* These are original-style recovered C bodies, called by C++ shadows. */
void _ZN6RecordC1Ev(void *p) { uint32_t *v=p;v[0]=0x12345678;v[1]=0xabcdef01; }
void _ZN7CleanupD1Ev(void *p) { int32_t **count=p;++**count; }
