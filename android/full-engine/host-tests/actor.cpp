// Intentional actor declines use C++ unwinding; actual hardware faults are NOT
// intercepted. These fixtures stand in for names/level telemetry, not game logic.
#include "native_actor.inc"
#include <cassert>
#include <stdexcept>
extern "C" {
signed char data_0209f2f8 = 1;
port_classname_fn port_classname_resolver = nullptr;
}
struct TestActor {unsigned char bytes[32]{};};
static int hits = 0, destroyed = 0;
struct Scoped{~Scoped(){++destroyed;}};
static int good(void*){++hits;return 0;}
static int decline(void*){Scoped guard;port_actor_slot_decline("intentional test");return 0;}
static TestActor *receiver;
static int named(void*){port_actor_slot_decline_for(receiver,"named test");return 0;}
static int foreign(void*){throw std::runtime_error("foreign error");}
int main(int argc,char**argv){
    TestActor a,b,c;*reinterpret_cast<unsigned short*>(a.bytes+12)=0xbf;
    *reinterpret_cast<unsigned short*>(b.bytes+12)=0xbf;*reinterpret_cast<unsigned short*>(c.bytes+12)=9;
    if(argc>1){ if(argv[1][0]=='h'){ // Deliberate unmapped access must remain fatal, subprocess only.
        auto crash=[](void*)->int{*static_cast<volatile int*>(nullptr)=1;return 0;};
        port_dispatch_guarded(crash,&a);return 99;
    } setenv("SM64DS_FAULTS_FATAL","1",1);port_dispatch_guarded(decline,&a);return 99;}
    assert(port_dispatch_guarded(good,&a)==0 && hits==1);
    assert(port_dispatch_guarded(decline,&a)==1 && destroyed==1);
    assert(port_quarantine_frozen_count()==1);
    assert(port_dispatch_guarded(good,&a)==1 && hits==1);
    assert(port_dispatch_guarded(good,&b)==0 && hits==2); // other player remains active
    receiver=&c;assert(port_dispatch_guarded(named,&b)==1);
    assert(port_q_is_frozen(&c) && !port_q_is_frozen(&b));
    bool propagated=false;try{port_dispatch_guarded(foreign,&b);}catch(const std::runtime_error&){propagated=true;}
    assert(propagated);port_quarantine_reset();assert(port_quarantine_frozen_count()==0);
    assert(port_dispatch_guarded(good,&a)==0 && hits==3);
    puts("PASS: original actor dispatch, explicit decline, named receiver, player isolation, C++ destructors and reset; no scene run");
}
