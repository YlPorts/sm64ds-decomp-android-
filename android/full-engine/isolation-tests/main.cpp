#include "api.h"
#include <cstdio>
#include <cstdlib>
extern "C" uintptr_t *literal_face_table();
static int checks;
static void check(bool good){++checks;if(!good){std::fprintf(stderr,"FAIL %d\n",checks);std::exit(3);}}
int main(){
 for(int i=0;i<1000;++i){
  Mixer m{10};Triple got{};
  check(fixture_c(&m.state,&got)==23);check(m.state==22);
  check(got.x==27&&got.y==10&&got.z==-105);
  check(m.Apply(2)==24);Triple direct=m.Vector(4);check(direct.x==28&&direct.z==-4);
  Record r;check(r.x==0x12345678&&r.y==0xabcdef01);
  int32_t count=0;{Cleanup d{&count};}check(count==1);
 }
 Face f;Face *p=&f;check(p->Value()==81);
 auto *table=literal_face_table();check(table[0]==17&&table[3]==29);
 check(*reinterpret_cast<void**>(&f)!=reinterpret_cast<void*>(table));
 std::printf("PASS %d synthetic ABI checks: both directions, conversions, aggregate return, constructor/destructor and distinct tables; NOT gameplay\n",checks);
}
