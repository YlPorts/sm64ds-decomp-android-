/* These storage fixtures test field offsets and actual bridge/provider calls,
 * not the construction or lifecycle of a complete game Player. */
#include <cstdint>
#include <cstdio>
#include <cstring>
static_assert(sizeof(void*)==4,"Original layout probes require 32-bit execution");
struct PathPtr {int a,b;PathPtr();void FromID(unsigned);};
struct Player {struct State{int value;};int IsState(State&);};
extern "C" int probe_original_animation(int*);
extern "C" void _ZN5Sound13Func_02048eb4Ev();
static int sound=-1;
extern "C" void func_02048fd4(int i){sound=i;}
int main(){
 int checks=0;int result=probe_original_animation(&checks);
 if(result){std::printf("FAIL animation %d\n",result);return 1;}
 for(int i=0;i<1000;++i){
  struct P {uint32_t before;PathPtr p;uint32_t after;} p;
  p.before=0x12345678;p.after=0x87654321;
  ++checks;if(p.p.a||p.p.b||p.before!=0x12345678||p.after!=0x87654321)return 2;
  alignas(void*) unsigned char storage[0x400];std::memset(storage,0x5a,sizeof storage);
  Player::State a{12},b{15};void *state=&a;std::memcpy(storage+0x370,&state,sizeof state);
  unsigned char before[0x400];std::memcpy(before,storage,sizeof storage);
  auto *player=reinterpret_cast<Player*>(storage);
  ++checks;if(!player->IsState(a)||player->IsState(b))return 3;
  ++checks;if(std::memcmp(before,storage,sizeof storage))return 4;
  sound=-1;_ZN5Sound13Func_02048eb4Ev();++checks;if(sound!=0)return 5;
 }
 std::printf("PASS %d checks: 5 original recovered bodies and original forward/reverse bridge units; storage/destructor/audio boundaries are fixtures, NOT gameplay\n",checks);
}
