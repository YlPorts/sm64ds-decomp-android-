/* Integrates the COMPLETE adapted sub_screen.cpp with the production Android
   input backend. Layout and game services below are explicit fixtures. This
   runs the original touch mapper, TouchInfo writer and ring-store path, not
   a scene, pixel renderer or Android Surface. */
#include "sm64ds_android_input.h"
#include "ntr/ppu.h"
#include <cstdio>
#include <cstring>
extern "C" {
void sm64ds_test_touch_config(int stacked,int panel_x,int panel_y,int divisor);
void sm64ds_test_poll_touch();
void hal_present_set_rect(int,int,int,int,int,int);
int hal_present_client_to_sub(int,int,int*,int*);
int hal_present_client_to_fb(int,int,int*,int*);
int hal_window_focused();
alignas(4) unsigned char data_020a0de8[16]{};
unsigned char data_020a0df8[72]{};
unsigned short data_020a0dd8[4]{};
// Fixture aliases only: the live engine's whole BSS map is not linked here.
asm(".globl data_020a0de9\n.set data_020a0de9, data_020a0de8+1\n"
    ".globl data_020a0dea\n.set data_020a0dea, data_020a0de8+2\n"
    ".globl data_020a0deb\n.set data_020a0deb, data_020a0de8+3\n");
int port_tsc_ring_armed(){return 0;}
void port_tsc_arm7_frame_touch(){}
unsigned long port_tsc_arm7_sample_count(){return 0;}
}
namespace port {
static int ring;
int touch_ring_index(){return ring;}
void touch_ring_advance(){ring=(ring+1)%9;}
bool comms_inject_touch(int*,int*,int*){return false;}
}
namespace ntr { int active_w=512,active_h=384; }
static ntr::StackLayout layout{};
const ntr::StackLayout *hal_screen_layout(){return &layout;}
static int checks;
#define CHECK(x) do {++checks;if(!(x)){std::fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x);return 1;}}while(0)
int main(){
    using namespace sm64ds::input;
    reset();port_pad_init();focus(true);
    layout.w=512;layout.h=864;layout.top_y=0;layout.bottom_y=480;
    layout.pan_x0=0;layout.pan_w=512;
    sm64ds_test_touch_config(1,0,0,2);
    hal_present_set_rect(50,30,512,864,512,864);
    int x=-1,y=-1;
    CHECK(hal_present_client_to_sub(50,510,&x,&y)&&x==0&&y==0);
    CHECK(hal_present_client_to_sub(561,893,&x,&y)&&x==255&&y==191);
    CHECK(!hal_present_client_to_sub(50,509,&x,&y)); // gap
    CHECK(!hal_present_client_to_sub(49,510,&x,&y)); // negative letterbox offset
    CHECK(!hal_present_client_to_sub(562,510,&x,&y));
    CHECK(!hal_present_client_to_sub(50,894,&x,&y));
    CHECK(hal_present_client_to_fb(50,30,&x,&y)&&x==0&&y==0);
    CHECK(!hal_present_client_to_fb(50,414,&x,&y));
    CHECK(pointer(7,1,0,306,702));sm64ds_test_poll_touch();
    CHECK(data_020a0de8[0]==1&&data_020a0de8[1]==1&&data_020a0de8[2]==128&&data_020a0de8[3]==96);
    unsigned short record[4];std::memcpy(record,data_020a0df8,8);
    CHECK(record[0]==128&&record[1]==96&&record[2]==1&&record[3]==0);
    sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==1&&data_020a0de8[1]==0);
    pointer(7,1,2,900,1000);sm64ds_test_poll_touch();
    CHECK(data_020a0de8[0]==1&&data_020a0de8[1]==0&&data_020a0de8[2]==255&&data_020a0de8[3]==191);
    pointer(7,1,2,306,702);sm64ds_test_poll_touch();
    CHECK(data_020a0de8[1]==0&&data_020a0de8[2]==128);
    pointer(7,0,3,0,0);sm64ds_test_poll_touch();
    CHECK(data_020a0de8[0]==0&&data_020a0de8[1]==1&&data_020a0de8[2]==128&&data_020a0de8[3]==96);
    sm64ds_test_poll_touch();CHECK(data_020a0de8[1]==0);
    // A fresh touch on the top screen must NOT become a bottom-screen click.
    pointer(7,2,0,306,200);sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==0);
    pointer(7,2,1,306,200);sm64ds_test_poll_touch();
    pointer(7,3,0,306,702);sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==1);
    focus(false);sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==0&&data_020a0de8[1]==1&&!hal_window_focused());
    focus(true);sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==0&&data_020a0de8[1]==0&&hal_window_focused());
    // Lost focus and a fresh gesture can both occur before the next frame.
    pointer(7,20,0,306,702);sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==1);
    focus(false);focus(true);pointer(7,21,0,900,1000);sm64ds_test_poll_touch();
    CHECK(data_020a0de8[0]==0&&data_020a0de8[1]==1); // old gesture release
    sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==0); // new off-panel touch cannot inherit the drag
    pointer(7,21,1,900,1000);pointer(7,22,0,306,702);sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==1);
    pointer(7,22,1,306,702);pointer(7,23,0,306,702);sm64ds_test_poll_touch();
    CHECK(data_020a0de8[0]==0&&data_020a0de8[1]==1);
    sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==1&&data_020a0de8[1]==1);
    pointer(7,23,1,306,702);sm64ds_test_poll_touch();
    // Non-unit surface scaling and the widened bottom panel's pillarboxing.
    layout.w=768;layout.h=864;layout.pan_x0=128;layout.pan_w=512;
    hal_present_set_rect(20,10,1536,1728,768,864);
    CHECK(hal_present_client_to_sub(788,1354,&x,&y)&&x==128&&y==96);
    CHECK(!hal_present_client_to_sub(275,970,&x,&y));
    CHECK(hal_present_client_to_sub(276,970,&x,&y)&&x==0&&y==0);
    CHECK(!hal_present_client_to_sub(1300,970,&x,&y));
    // Inset keeps the original panel offset/divisor convention.
    layout.w=512;layout.h=384;layout.top_y=0;layout.bottom_y=384;layout.pan_x0=0;layout.pan_w=512;
    sm64ds_test_touch_config(0,300,200,2);hal_present_set_rect(10,20,1024,768,512,384);
    pointer(7,4,0,738,516);sm64ds_test_poll_touch();
    CHECK(data_020a0de8[0]==1&&data_020a0de8[1]==1&&data_020a0de8[2]==128&&data_020a0de8[3]==96);
    remove_device(7);sm64ds_test_poll_touch();CHECK(data_020a0de8[0]==0&&data_020a0de8[1]==1);
    sm64ds_test_poll_touch();CHECK(data_020a0de8[1]==0);
    std::printf("original sub-screen touch path: %d checks PASS; layout/services are fixtures\n",checks);
}
