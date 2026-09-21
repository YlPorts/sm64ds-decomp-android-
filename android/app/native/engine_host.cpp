#include <jni.h>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <pthread.h>
#include "ntr/ppu.h"
#include "hal/screen_gap.h"
#include "sm64ds_android_input.h"
extern "C" {
int sm64ds_engine_initialize(int (*)(unsigned));
int sm64ds_native_scheduler_collect();
int port_scene_begin(void*,int);
void port_scene_tick(int,int);
int port_scene_finish(int);
const void* port_scene_framebuffer();
void port_rom_frame_begin(const char*);
void port_rom_frame_phase6();
int port_rom_frame_checked(int,const char*);
unsigned int* hal_sub_screen_stacked_image(const unsigned int*);
void hal_present_set_rect(int,int,int,int,int,int);
}
namespace {
std::mutex picture_mutex;
std::array<jint,256*384> picture{};
int frames=0;
bool started=false;
pthread_t owner;
int pump(unsigned) {return 1;}
// UI touches use a virtual 256x384 client. The engine's own mapper includes
// any simulated hinge, so UI coordinates are converted on its owner thread.
std::mutex touch_mutex;
struct Touch {int id=0,action=3;float x=0,y=0;};
// No allocation during dlopen: the game's allocator is not initialized yet.
std::array<Touch,64> touches{};
unsigned touch_head=0,touch_count=0;
void publish_touch() {
    const auto& lay=*hal_screen_layout();
    hal_present_set_rect(0,0,lay.w,lay.h,lay.w,lay.h);
    Touch t;bool pending;
    {std::lock_guard<std::mutex> lock(touch_mutex);pending=touch_count!=0;
     if(pending){t=touches[touch_head];touch_head=(touch_head+1)%touches.size();--touch_count;}}
    if(pending) {
        sm64ds::input::pointer(-901,t.id,t.action,lay.pan_x0+t.x*lay.pan_w/256.f,
            lay.bottom_y+t.y*(lay.h-lay.bottom_y)/192.f);
    }
}
}
extern "C" {
JNIEXPORT jint JNICALL Java_org_ylports_sm64ds_nativeport_EngineBridge_start(JNIEnv*,jclass) {
    if(started)return 2;owner=pthread_self();
    ntr::configure_aspect(0.0);
    int result=sm64ds_engine_initialize(pump);if(result)return result;
    // A non-null marker enables the actual Android event source, not a Win32 handle.
    result=port_scene_begin(reinterpret_cast<void*>(1),1);if(result)return result;
    port_rom_frame_begin("Android scene loop");started=true;return 0;
}
JNIEXPORT jint JNICALL Java_org_ylports_sm64ds_nativeport_EngineBridge_step(JNIEnv*,jclass) {
    if(!started||!pthread_equal(owner,pthread_self()))return -1;
    publish_touch();port_scene_tick(port_rom_frame_checked(frames,"android-frame"),1);port_rom_frame_phase6();
    if(sm64ds_native_scheduler_collect()<0)return -3;
    const auto* top=static_cast<const ntr::Framebuffer*>(port_scene_framebuffer());
    const auto* stacked=hal_sub_screen_stacked_image(&top->px[0][0]);
    if(!stacked)return -2;
    const auto& lay=*hal_screen_layout();
    std::lock_guard<std::mutex> lock(picture_mutex);
    for(int panel=0;panel<2;panel++)for(int y=0;y<192;y++)for(int x=0;x<256;x++) {
        int sy=(panel?lay.bottom_y:lay.top_y)+y*ntr::active_h/192;
        int sx=panel?lay.pan_x0+x*lay.pan_w/256:x*ntr::active_w/256;
        picture[(panel*192+y)*256+x]=static_cast<jint>(stacked[sy*lay.w+sx]);
    }
    if(frames==0)std::fputs("[android-frame] first two-screen frame rendered\n",stderr);
    return ++frames;
}
JNIEXPORT jboolean JNICALL Java_org_ylports_sm64ds_nativeport_EngineBridge_copyFrame(JNIEnv* env,jclass,jintArray array) {
    if(!array||env->GetArrayLength(array)!=256*384)return false;
    std::lock_guard<std::mutex> lock(picture_mutex);
    env->SetIntArrayRegion(array,0,picture.size(),picture.data());return !env->ExceptionCheck();
}
JNIEXPORT void JNICALL Java_org_ylports_sm64ds_nativeport_EngineBridge_touch(JNIEnv*,jclass,jint id,jint action,jfloat x,jfloat y) {
    std::lock_guard<std::mutex> lock(touch_mutex);
    unsigned last=(touch_head+touch_count+touches.size()-1)%touches.size();
    if(action==3){touch_head=0;touch_count=1;touches[0]={id,3,0,0};}
    else if(action==2&&touch_count&&touches[last].action==2&&touches[last].id==id)touches[last]={id,action,x,y};
    else if(touch_count<touches.size()){touches[(touch_head+touch_count)%touches.size()]={id,action,x,y};++touch_count;}
    else {touch_head=0;touch_count=1;touches[0]={id,3,0,0};}
}
JNIEXPORT void JNICALL Java_org_ylports_sm64ds_nativeport_EngineBridge_finish(JNIEnv*,jclass) {
    if(started&&pthread_equal(owner,pthread_self())) {port_scene_finish(frames);started=false;}
}
}
