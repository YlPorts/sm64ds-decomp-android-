#include <jni.h>
#include <cstdlib>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>

extern "C" JNIEXPORT jboolean JNICALL
Java_org_ylports_sm64ds_nativeport_EngineBridge_prepare(JNIEnv* env,jclass,jstring path) {
    const char* root=env->GetStringUTFChars(path,nullptr);if(!root)return false;
    bool ok = root[0]=='/' && chdir(root)==0;
    if(ok) {
        ok = !setenv("SM64DS_ASSET_ROOT",root,1) && !setenv("SM64DS_ERROR_DIR",root,1) &&
             !setenv("SM64DS_SCENE","1",1) && !setenv("SM64DS_ROM_LOOP","0",1) &&
             !setenv("SM64DS_ROM_MAIN","1",1) && !setenv("SM64DS_TITLE_ENTRY","0",1) &&
             !setenv("SM64DS_DUAL_SCREEN","1",1);
        int log=open("engine.log",O_CREAT|O_TRUNC|O_WRONLY|O_CLOEXEC,0600);
        if(log>=0) {ok=ok && dup2(log,STDOUT_FILENO)>=0 && dup2(log,STDERR_FILENO)>=0;close(log);}
        else ok=false;
        std::setvbuf(stdout,nullptr,_IONBF,0);std::setvbuf(stderr,nullptr,_IONBF,0);
    }
    env->ReleaseStringUTFChars(path,root);return ok;
}
