/* Native Android input. Replaces the Windows controller unit; interfaces in
   pad_backend.h stay intact. Android normalizes controller key positions.
   DirectInput raw-layout learning is deliberately unsupported (returns 0).
   No device polling thread, DLLs, fake OS imports or game-state writes. */
#include "sm64ds_android_input.h"
#include <algorithm>
#include <array>
#include <bitset>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <cstddef>
#ifdef __ANDROID__
#include <android/input.h>
#include <android/keycodes.h>
static_assert(sizeof(PortPadState)==16 && offsetof(PortPadState,buttons)==4,
              "The existing game pad ABI requires 32-bit unsigned long");
static_assert(AINPUT_SOURCE_GAMEPAD==sm64ds::input::Gamepad);
static_assert(AINPUT_SOURCE_JOYSTICK==sm64ds::input::Joystick);
static_assert(AKEYCODE_BUTTON_A==96 && AKEYCODE_BUTTON_Y==100);
static_assert(AKEYCODE_BUTTON_SELECT==109 && AKEYCODE_BUTTON_R2==105);
static_assert(AMOTION_EVENT_ACTION_CANCEL==3 && AMOTION_EVENT_ACTION_POINTER_UP==6);
#endif

namespace {
struct Device {
    bool used{}, pad{};
    int id{};
    std::bitset<256> keys;
    sm64ds::input::Axes analog{};
};
struct Input {
    std::mutex lock;
    bool initialized{}, disabled{}, focus{};
    std::array<Device,8> devices{};
    std::uint32_t generation{}, gesture{};
    bool touch_down{}, virtual_enabled{};
    int touch_device{}, touch_id{-1}, x{}, y{};
    PortPadState virtual_state{};
    unsigned short virtual_edges{};
    unsigned char virtual_lt_edge{}, virtual_rt_edge{};
};
Input &state() {static Input value; return value;}
bool source_has(unsigned source,unsigned kind) {return (source&kind)==kind;}
Device *device(Input &s,int id,bool create) {
    for(auto &d:s.devices) if(d.used&&d.id==id) return &d;
    if(create) for(auto &d:s.devices) if(!d.used){d={};d.used=true;d.id=id;return &d;}
    return nullptr;
}
float finite_clamp(float n,float lo,float hi) {
    return std::isfinite(n)?std::max(lo,std::min(hi,n)):0.0f;
}
short axis_value(float n) {return static_cast<short>(std::lround(finite_clamp(n,-1,1)*32767));}
unsigned char trigger(float n) {return static_cast<unsigned char>(std::lround(finite_clamp(n,0,1)*255));}
unsigned short pad_button(int code) {
    switch(code) {
    case 19:return 1;case 20:return 2;case 21:return 4;case 22:return 8;
    case 23:case 96:return 0x1000;case 97:return 0x2000;
    case 99:return 0x4000;case 100:return 0x8000;
    case 102:return 0x100;case 103:return 0x200;
    case 106:return 0x40;case 107:return 0x80;
    case 108:return 0x10;case 109:return 0x20;
    default:return 0;
    }
}
int legacy_code(int key) {
    if(key>=29&&key<=54)return 'A'+key-29;
    if(key>=7&&key<=16)return '0'+key-7;
    if(key>=131&&key<=142)return 0x70+key-131;
    switch(key) {
    case 19:return 0x26;case 20:return 0x28;case 21:return 0x25;case 22:return 0x27;
    case 59:case 60:return 0x10;case 113:case 114:return 0x11;
    case 57:case 58:return 0x12;case 61:return 9;case 62:return 0x20;
    case 66:case 160:return 13;case 67:return 8;case 111:return 27;
    default:return -1;
    }
}
bool held(const Input &s,int vk) {
    if(!s.initialized||!s.focus)return false;
    for(const auto &d:s.devices) if(d.used&&!d.pad)
        for(int k=0;k<256;++k) if(d.keys[k]&&legacy_code(k)==vk)return true;
    return false;
}
PortPadState translate(const Device &d) {
    PortPadState p{};
    for(int k=0;k<256;++k) if(d.keys[k])p.buttons|=pad_button(k);
    const auto &a=d.analog;
    if(a.hat_y<-.5f)p.buttons|=1;if(a.hat_y>.5f)p.buttons|=2;
    if(a.hat_x<-.5f)p.buttons|=4;if(a.hat_x>.5f)p.buttons|=8;
    p.lx=axis_value(a.lx);p.ly=axis_value(-a.ly);
    p.rx=axis_value(a.rx);p.ry=axis_value(-a.ry);
    p.lt=d.keys[104]?255:trigger(a.lt);p.rt=d.keys[105]?255:trigger(a.rt);
    return p;
}
short strongest(short a,short b) {return std::abs(int(b))>std::abs(int(a))?b:a;}
void clear_held(Input &s) {
    for(auto &d:s.devices){d.keys.reset();d.analog={};}
    s.touch_down=false;s.touch_id=-1;s.virtual_enabled=false;s.virtual_state={};
    s.virtual_edges=0;s.virtual_lt_edge=s.virtual_rt_edge=0;
    ++s.generation;++s.gesture;
}
}

namespace sm64ds::input {
void reset() {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    s.devices={};clear_held(s);s.initialized=false;s.disabled=false;s.focus=false;
}
void focus(bool value) {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(value!=s.focus){clear_held(s);s.focus=value;}
}
bool focused() {auto &s=state();std::lock_guard<std::mutex> guard(s.lock);return s.focus;}
void remove_device(int id) {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(auto *d=device(s,id,false))*d={};
    if(s.touch_down&&s.touch_device==id){s.touch_down=false;s.touch_id=-1;}
    ++s.generation;
}
bool key(int id,unsigned source,int code,int action,bool canceled) {
    const bool is_pad=source_has(source,Gamepad)||source_has(source,Dpad);
    const bool is_keyboard=source_has(source,Keyboard);
    if(code<0||code>=256||(action!=0&&action!=1))return false;
    if(is_pad ? (!pad_button(code)&&code!=104&&code!=105)
              : (!is_keyboard||legacy_code(code)<0))return false;
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(!s.initialized||!s.focus||(is_pad&&s.disabled))return false;
    Device *d=device(s,id,true);if(!d)return false;
    d->pad=is_pad;d->keys[code]=action==0&&!canceled;++s.generation;return true;
}
bool axes(int id,const Axes &value) {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(!s.initialized||!s.focus||s.disabled)return false;
    Device *d=device(s,id,true);if(!d)return false;
    d->pad=true;d->analog=value;
    // Sanitize at ingestion, including hats (NaN must not become a direction).
    auto &a=d->analog;
    a.lx=finite_clamp(a.lx,-1,1);a.ly=finite_clamp(a.ly,-1,1);
    a.rx=finite_clamp(a.rx,-1,1);a.ry=finite_clamp(a.ry,-1,1);
    a.lt=finite_clamp(a.lt,0,1);a.rt=finite_clamp(a.rt,0,1);
    a.hat_x=finite_clamp(a.hat_x,-1,1);a.hat_y=finite_clamp(a.hat_y,-1,1);
    ++s.generation;return true;
}
bool pointer(int id,int pid,int action,float x,float y) {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(!s.initialized||!s.focus)return false;
    if(action==3){if(s.touch_device==id){s.touch_down=false;s.touch_id=-1;++s.generation;}return true;}
    if(pid<0||!std::isfinite(x)||!std::isfinite(y))return false;
    if(action==0||action==5){
        if(s.touch_down)return false; // Another finger cannot steal the stylus.
        s.touch_down=true;s.touch_device=id;s.touch_id=pid;++s.gesture;
    } else if(!s.touch_down||s.touch_device!=id||s.touch_id!=pid)return false;
    if(action==1||action==6){s.touch_down=false;s.touch_id=-1;}
    else if(action!=0&&action!=2&&action!=5)return false;
    s.x=int(std::floor(finite_clamp(x,-1000000,1000000)));
    s.y=int(std::floor(finite_clamp(y,-1000000,1000000)));
    ++s.generation;return true;
}
void virtual_pad(const PortPadState &pad,bool enabled) {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(!s.initialized||!s.focus)return;
    // Preserve a quick virtual press until the sole engine consumer polls it.
    // Repeated taps between two polls coalesce, rather than creating an unbounded queue.
    if(enabled){
        s.virtual_edges |= pad.buttons & ~s.virtual_state.buttons;
        if(pad.lt && !s.virtual_state.lt)s.virtual_lt_edge=pad.lt;
        if(pad.rt && !s.virtual_state.rt)s.virtual_rt_edge=pad.rt;
    }else{s.virtual_edges=0;s.virtual_lt_edge=s.virtual_rt_edge=0;}
    s.virtual_state=pad;
    for(short *v : {&s.virtual_state.lx,&s.virtual_state.ly,&s.virtual_state.rx,&s.virtual_state.ry})
        if(*v < -32767)*v=-32767;
    s.virtual_enabled=enabled;++s.generation;
}
Pointer pointer_snapshot() {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    return {s.focus&&s.touch_down,s.x,s.y,s.focus,held(s,9),s.generation,s.gesture};
}
bool legacy_key_held(int code) {auto &s=state();std::lock_guard<std::mutex> guard(s.lock);return held(s,code);}
}

int port_pad_init() {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(!s.initialized){s.initialized=true;const char *mode=std::getenv("SM64DS_PAD_BACKEND");s.disabled=mode&&std::strcmp(mode,"none")==0;}
    return !s.disabled;
}
int port_pad_poll(PortPadState *out) {
    if(!out)return 0;
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(!s.initialized||!s.focus)return 0;
    PortPadState p{};bool live=false;
    if(!s.disabled)for(const auto &d:s.devices)if(d.used&&d.pad){p=translate(d);live=true;break;}
    if(s.virtual_enabled){
        const auto &v=s.virtual_state;p.buttons|=v.buttons|s.virtual_edges;
        p.lt=std::max({p.lt,v.lt,s.virtual_lt_edge});p.rt=std::max({p.rt,v.rt,s.virtual_rt_edge});
        s.virtual_edges=0;s.virtual_lt_edge=s.virtual_rt_edge=0;
        p.lx=strongest(p.lx,v.lx);p.ly=strongest(p.ly,v.ly);
        p.rx=strongest(p.rx,v.rx);p.ry=strongest(p.ry,v.ry);live=true;
    }
    if(!live)return 0;
    p.packet=s.generation;*out=p;return 1;
}
void port_pad_device_changed() {
    // Legacy notification has no device ID. Invalidate stale physical snapshots;
    // Android's next event repopulates them. Prefer remove_device(id) for hotplug.
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);s.devices={};++s.generation;
}
const char *port_pad_describe() {
    auto &s=state();std::lock_guard<std::mutex> guard(s.lock);
    if(s.disabled)return "Android: physical pad disabled";
    for(const auto &d:s.devices)if(d.used&&d.pad)return "Android: normalized gamepad events";
    return s.virtual_enabled?"Android: virtual pad":"Android: no gamepad events";
}
int port_pad_raw(PortPadRaw *out) {if(out)*out={};return 0;}
int port_pad_set_layout(const HostPadLayout *) {return 0;} // DirectInput layout, not Android's normalized mapping.
int port_pad_selftest() {return axis_value(1)==32767&&axis_value(-1)==-32767&&pad_button(96)==0x1000;}

#ifdef __ANDROID__
extern "C" int sm64ds_android_handle_input(const AInputEvent *event) {
    if(!event)return 0;
    using namespace sm64ds::input;
    const int id=AInputEvent_getDeviceId(event),type=AInputEvent_getType(event);
    const unsigned source=unsigned(AInputEvent_getSource(event));
    if(type==AINPUT_EVENT_TYPE_KEY)return key(id,source,AKeyEvent_getKeyCode(event),
        AKeyEvent_getAction(event),(AKeyEvent_getFlags(event)&AKEY_EVENT_FLAG_CANCELED)!=0);
    if(type!=AINPUT_EVENT_TYPE_MOTION)return 0;
    const int raw=AMotionEvent_getAction(event),action=raw&AMOTION_EVENT_ACTION_MASK;
    const size_t count=AMotionEvent_getPointerCount(event);
    if(source_has(source,Joystick)) {
        if(action==AMOTION_EVENT_ACTION_CANCEL){remove_device(id);return 1;}
        if(action!=AMOTION_EVENT_ACTION_MOVE||count==0)return 0;
        auto get=[&](int axis){return AMotionEvent_getAxisValue(event,axis,0);};
        // Android's standard right stick is Z/RZ, not RX/RY. Trigger aliases
        // BRAKE/GAS and button L2/R2 are kept without adding duplicate presses.
        return axes(id,{get(AMOTION_EVENT_AXIS_X),get(AMOTION_EVENT_AXIS_Y),
          get(AMOTION_EVENT_AXIS_Z),get(AMOTION_EVENT_AXIS_RZ),
          std::max(get(AMOTION_EVENT_AXIS_LTRIGGER),get(AMOTION_EVENT_AXIS_BRAKE)),
          std::max(get(AMOTION_EVENT_AXIS_RTRIGGER),get(AMOTION_EVENT_AXIS_GAS)),
          get(AMOTION_EVENT_AXIS_HAT_X),get(AMOTION_EVENT_AXIS_HAT_Y)});
    }
    if(!source_has(source,Touchscreen)&&!source_has(source,Stylus))return 0;
    if(action==AMOTION_EVENT_ACTION_CANCEL)return pointer(id,0,action,0,0);
    if(action==AMOTION_EVENT_ACTION_MOVE){
        bool used=false;for(size_t i=0;i<count;++i)used=pointer(id,AMotionEvent_getPointerId(event,i),action,
            AMotionEvent_getX(event,i),AMotionEvent_getY(event,i))||used;return used;
    }
    const size_t i=unsigned(raw&AMOTION_EVENT_ACTION_POINTER_INDEX_MASK)>>AMOTION_EVENT_ACTION_POINTER_INDEX_SHIFT;
    if(i>=count)return 0;
    return pointer(id,AMotionEvent_getPointerId(event,i),action,AMotionEvent_getX(event,i),AMotionEvent_getY(event,i));
}
#endif
