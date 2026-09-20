/* Synthetic OS event records driving the production state/mapping backend.
   This is not an Android input queue or a physical-controller/device test. */
#include "sm64ds_android_input.h"
#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <thread>
using namespace sm64ds::input;
static int checks;
#define CHECK(x) do {++checks;if(!(x)){std::fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);return 1;}}while(0)
int main() {
    reset();CHECK(port_pad_init());PortPadState p{};p.packet=1234;
    CHECK(!port_pad_poll(&p)&&p.packet==1234);
    CHECK(!key(1,Gamepad,96,0));focus(true);
    CHECK(!key(1,Keyboard,4,0));CHECK(!key(1,Keyboard,24,0)); // Android Back/volume
    CHECK(!key(1,Gamepad,96,2));CHECK(!key(1,0,96,0));
    CHECK(key(1,Gamepad,96,0));CHECK(port_pad_poll(&p)&&p.buttons==0x1000);
    CHECK(key(1,Gamepad,97,0));CHECK(port_pad_poll(&p)&&p.buttons==0x3000);
    CHECK(key(1,Gamepad,96,1));CHECK(port_pad_poll(&p)&&p.buttons==0x2000);
    CHECK(key(1,Gamepad,97,0,true));CHECK(port_pad_poll(&p)&&p.buttons==0);
    CHECK(axes(1,{1,-1,-.5f,.5f,.5f,1,-1,1}));CHECK(port_pad_poll(&p));
    CHECK(p.lx==32767&&p.ly==32767&&p.rx==-16384&&p.ry==-16384);
    CHECK(p.lt==128&&p.rt==255&&p.buttons==6);
    CHECK(key(1,Dpad,19,0));CHECK(port_pad_poll(&p)&&p.buttons==7);
    CHECK(axes(1,{}));CHECK(port_pad_poll(&p)&&p.buttons==1); // hat release cannot erase key
    CHECK(key(1,Dpad,19,1));CHECK(port_pad_poll(&p)&&p.buttons==0);
    CHECK(key(1,Gamepad,104,0));CHECK(axes(1,{}));CHECK(port_pad_poll(&p)&&p.lt==255);
    CHECK(key(1,Gamepad,104,1));CHECK(port_pad_poll(&p)&&p.lt==0);
    CHECK(axes(1,{NAN,INFINITY,-INFINITY,2,-1,2,NAN,NAN}));CHECK(port_pad_poll(&p));
    CHECK(p.lx==0&&p.ly==0&&p.rx==0&&p.ry==-32767&&p.lt==0&&p.rt==255&&p.buttons==0);
    CHECK(key(2,Gamepad,100,0));CHECK(port_pad_poll(&p)&&p.buttons==0); // first pad remains owner
    remove_device(1);CHECK(port_pad_poll(&p)&&p.buttons==0x8000);
    focus(false);p.packet=123;CHECK(!port_pad_poll(&p)&&p.packet==123);
    CHECK(!key(2,Gamepad,96,0));focus(true);CHECK(port_pad_poll(&p)&&p.buttons==0);
    CHECK(key(3,Keyboard,29,0));CHECK(legacy_key_held('A'));
    CHECK(key(3,Keyboard,59,0));CHECK(key(3,Keyboard,60,0));
    CHECK(key(3,Keyboard,59,1));CHECK(legacy_key_held(0x10));
    CHECK(key(3,Keyboard,60,1));CHECK(!legacy_key_held(0x10));
    CHECK(key(3,Keyboard,61,0));CHECK(pointer_snapshot().tab);
    CHECK(pointer(10,4,0,100.75f,200.5f));auto t=pointer_snapshot();CHECK(t.down&&t.x==100&&t.y==200);
    CHECK(!pointer(10,9,5,7,7));CHECK(!pointer(10,9,2,8,8));
    CHECK(pointer(10,4,2,120,230));CHECK(pointer_snapshot().x==120);
    CHECK(!pointer(10,9,6,1,2));CHECK(pointer_snapshot().down);
    CHECK(pointer(10,4,6,120,230));CHECK(!pointer_snapshot().down);
    CHECK(!pointer(10,9,2,3,4)); // no ownership handover to another held finger
    CHECK(!pointer(10,6,0,NAN,1));CHECK(!pointer_snapshot().down);
    CHECK(pointer(10,6,0,-.1f,1));CHECK(pointer_snapshot().x==-1);
    CHECK(pointer(10,0,3,0,0));CHECK(!pointer_snapshot().down);
    CHECK(pointer(10,7,0,1,1));remove_device(10);CHECK(!pointer_snapshot().down);
    PortPadState v{};v.buttons=0x1000;v.lx=12000;virtual_pad(v,true);
    CHECK(axes(2,{-1,0,0,0,0,0,0,0}));CHECK(port_pad_poll(&p)&&p.buttons==0x1000&&p.lx==-32767);
    virtual_pad({},false);CHECK(port_pad_poll(&p)&&p.buttons==0&&p.lx==-32767);
    focus(false);focus(true);CHECK(!legacy_key_held('A')&&!pointer_snapshot().tab);
    CHECK(port_pad_poll(&p)&&p.lx==0);
    PortPadRaw raw{};raw.live=1;CHECK(!port_pad_raw(&raw)&&raw.live==0);
    CHECK(!port_pad_set_layout(nullptr));CHECK(port_pad_selftest());
    // All snapshots must be coherent while another thread publishes input.
    std::atomic<bool> done{false},bad{false};
    CHECK(pointer(10,7,0,0,0));
    std::thread writer([&]{for(int n=1;n<=100000;++n)pointer(10,7,2,float(n),float(-n));done=true;});
    do {auto q=pointer_snapshot();if(q.x!=-q.y)bad=true;}while(!done);
    writer.join();CHECK(!bad);CHECK(pointer_snapshot().x==100000);
    port_pad_device_changed();CHECK(!port_pad_poll(&p));
    reset();setenv("SM64DS_PAD_BACKEND","none",1);CHECK(!port_pad_init());focus(true);
    CHECK(!key(1,Gamepad,96,0));CHECK(key(1,Keyboard,29,0)&&legacy_key_held('A'));
    virtual_pad(v,true);CHECK(port_pad_poll(&p)&&p.buttons==0x1000); // touchscreen still usable
    unsetenv("SM64DS_PAD_BACKEND");reset();
    std::printf("input backend: %d checks PASS; 100000 coherent concurrent snapshots\n",checks);
}
