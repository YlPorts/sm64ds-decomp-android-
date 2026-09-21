#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <jni.h>

// Loads the exact JNI library packaged in the APK. JNIEnv is unused by these
// entry points; this exercises initialization, steps and screen composition,
// but intentionally makes no claim about Activity or Android input delivery.
template<class T> T symbol(void* library,const char* name) {
    auto result=reinterpret_cast<T>(dlsym(library,name));
    if(!result){std::fprintf(stderr,"%s: %s\n",name,dlerror());std::exit(2);}
    return result;
}
int main(int argc,char** argv) {
    if(argc!=3){std::fputs("Set SM64DS_ASSET_ROOT and pass bootstrap.so engine.so\n",stderr);return 2;}
    setenv("SM64DS_SCENE","1",1);setenv("SM64DS_ROM_LOOP","0",1);
    setenv("SM64DS_ROM_MAIN","1",1);setenv("SM64DS_TITLE_ENTRY","0",1);
    setenv("SM64DS_DUAL_SCREEN","1",1);
    if(!dlopen(argv[1],RTLD_NOW|RTLD_LOCAL)){std::fprintf(stderr,"bootstrap: %s\n",dlerror());return 2;}
    void* library=dlopen(argv[2],RTLD_NOW|RTLD_LOCAL);
    if(!library){std::fprintf(stderr,"dlopen: %s\n",dlerror());return 2;}
    using Step=int(*)(JNIEnv*,jclass);
    auto start=symbol<Step>(library,"Java_org_ylports_sm64ds_nativeport_EngineBridge_start");
    auto step=symbol<Step>(library,"Java_org_ylports_sm64ds_nativeport_EngineBridge_step");
    auto finish=symbol<void(*)(JNIEnv*,jclass)>(library,"Java_org_ylports_sm64ds_nativeport_EngineBridge_finish");
    assert(start(nullptr,nullptr)==0);
    for(int frame=1;frame<=3;frame++)assert(step(nullptr,nullptr)==frame);
    finish(nullptr,nullptr);
    std::puts("PASS: APK engine library loaded, three frames composed through JNI entry points");
    // Process teardown owns static engine state; do not dlclose a live engine.
}
