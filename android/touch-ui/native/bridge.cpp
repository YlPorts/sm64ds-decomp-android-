#include <jni.h>
#include <cmath>
#include "sm64ds_android_input.h"
using namespace sm64ds::input;
#define JNI(name) Java_org_ylports_sm64ds_controls_NativeBridge_##name
namespace {
short axis(float v){return std::isfinite(v)?short(std::lround(std::fmax(-1.f,std::fmin(1.f,v))*32767)):0;}
constexpr int touch_device=-901;
}
extern "C" {
JNIEXPORT void JNICALL JNI(init)(JNIEnv*,jclass){reset();port_pad_init();focus(true);}
JNIEXPORT void JNICALL JNI(focus)(JNIEnv*,jclass,jboolean value){focus(value);}
JNIEXPORT void JNICALL JNI(submit)(JNIEnv*,jclass,jint b,jfloat x,jfloat y,jint rt){
    PortPadState p{};p.buttons=static_cast<unsigned short>(b);p.lx=axis(x);p.ly=axis(y);
    p.rt=static_cast<unsigned char>(rt<0?0:rt>255?255:rt);virtual_pad(p,true);
}
JNIEXPORT void JNICALL JNI(cancel)(JNIEnv*,jclass){virtual_pad({},false);pointer(touch_device,0,3,0,0);}
JNIEXPORT void JNICALL JNI(pointer)(JNIEnv*,jclass,jint id,jint action,jfloat x,jfloat y){pointer(touch_device,id,action,x,y);}
JNIEXPORT jboolean JNICALL JNI(key)(JNIEnv*,jclass,jint dev,jint src,jint code,jint action,jboolean canceled){return key(dev,src,code,action,canceled);}
JNIEXPORT void JNICALL JNI(axes)(JNIEnv*env,jclass,jint dev,jfloatArray array){
    if(!array||env->GetArrayLength(array)!=8)return;jfloat a[8];env->GetFloatArrayRegion(array,0,8,a);
    if(env->ExceptionCheck())return;axes(dev,{a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7]});
}
JNIEXPORT void JNICALL JNI(removeDevice)(JNIEnv*,jclass,jint dev){remove_device(dev);}
JNIEXPORT jintArray JNICALL JNI(poll)(JNIEnv*env,jclass){
    PortPadState p{};port_pad_poll(&p);auto t=pointer_snapshot();
    const jint result[]={p.buttons,p.lx,p.ly,p.rt,t.down,t.x,t.y,t.focused};
    auto out=env->NewIntArray(8);if(out)env->SetIntArrayRegion(out,0,8,result);return out;
}
}
