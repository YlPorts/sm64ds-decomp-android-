/* Native output for the existing SDAT mixer. AAudio is dynamically resolved
 * so the API-23 diagnostic binary still loads: audio requires Android API 26.
 * Older versions/device failures explicitly return "no device"; mixing and
 * WAV capture continue. No emulator, Java audio loop or synthetic game sound.
 *
 * Lifecycle contract: sd_out_open/push/close and WAV functions are serialized
 * on the engine thread. The output worker alone calls write(). It owns no DS
 * state: the game thread calls sd_mix_render, publishes PCM and never waits
 * for the audio device. On close, join BEFORE touching/deleting the stream.
 */
#include "sdat.h"
#include "sm64ds_audio_queue.h"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <type_traits>
#ifdef __ANDROID__
#include <aaudio/AAudio.h>
#include <dlfcn.h>
#endif
namespace sm64ds_audio {
class AndroidDevice final: public Device {
#ifdef __ANDROID__
    void *library_=nullptr;
    AAudioStream *stream_=nullptr;
// Typed dynamic symbols: do not take addresses of unavailable declarations
// in an API-23 build. On API 26+ verify every type against the NDK itself.
#if __ANDROID_API__ >= 26
#define AA_POINTER(result, name, ...) \
    result (*name)(__VA_ARGS__)=nullptr; \
    static_assert(std::is_same_v<decltype(name), decltype(&AAudio##name)>, "AAudio type mismatch");
#else
#define AA_POINTER(result, name, ...) result (*name)(__VA_ARGS__)=nullptr;
#endif
    AA_POINTER(aaudio_result_t, _createStreamBuilder, AAudioStreamBuilder **)
    AA_POINTER(void, StreamBuilder_setDirection, AAudioStreamBuilder *, aaudio_direction_t)
    AA_POINTER(void, StreamBuilder_setSharingMode, AAudioStreamBuilder *, aaudio_sharing_mode_t)
    AA_POINTER(void, StreamBuilder_setFormat, AAudioStreamBuilder *, aaudio_format_t)
    AA_POINTER(void, StreamBuilder_setChannelCount, AAudioStreamBuilder *, int32_t)
    AA_POINTER(void, StreamBuilder_setSampleRate, AAudioStreamBuilder *, int32_t)
    AA_POINTER(void, StreamBuilder_setBufferCapacityInFrames, AAudioStreamBuilder *, int32_t)
    AA_POINTER(aaudio_result_t, StreamBuilder_openStream, AAudioStreamBuilder *, AAudioStream **)
    AA_POINTER(aaudio_result_t, StreamBuilder_delete, AAudioStreamBuilder *)
    AA_POINTER(int32_t, Stream_getChannelCount, AAudioStream *)
    AA_POINTER(int32_t, Stream_getSampleRate, AAudioStream *)
    AA_POINTER(aaudio_format_t, Stream_getFormat, AAudioStream *)
    AA_POINTER(aaudio_result_t, Stream_requestStart, AAudioStream *)
    AA_POINTER(aaudio_result_t, Stream_requestStop, AAudioStream *)
    AA_POINTER(aaudio_result_t, Stream_write, AAudioStream *, const void *, int32_t, int64_t)
    AA_POINTER(aaudio_result_t, Stream_close, AAudioStream *)
#undef AA_POINTER
#endif
public:
    bool open() override {
#ifdef __ANDROID__
        library_=dlopen("libaaudio.so",RTLD_NOW|RTLD_LOCAL);
        if(!library_) {std::fprintf(stderr,"[audio:native] AAudio unavailable; Android 26+ required\n");return false;}
#define AA_LOAD(name) name=reinterpret_cast<decltype(name)>(dlsym(library_,"AAudio" #name)); if(!name){close();return false;}
        AA_LOAD(_createStreamBuilder)
        AA_LOAD(StreamBuilder_setDirection) AA_LOAD(StreamBuilder_setSharingMode)
        AA_LOAD(StreamBuilder_setFormat) AA_LOAD(StreamBuilder_setChannelCount)
        AA_LOAD(StreamBuilder_setSampleRate) AA_LOAD(StreamBuilder_setBufferCapacityInFrames)
        AA_LOAD(StreamBuilder_openStream) AA_LOAD(StreamBuilder_delete)
        AA_LOAD(Stream_getChannelCount) AA_LOAD(Stream_getSampleRate) AA_LOAD(Stream_getFormat)
        AA_LOAD(Stream_requestStart) AA_LOAD(Stream_requestStop) AA_LOAD(Stream_write) AA_LOAD(Stream_close)
#undef AA_LOAD
        AAudioStreamBuilder *builder=nullptr;
        if(_createStreamBuilder(&builder)!=AAUDIO_OK || !builder) {close();return false;}
        StreamBuilder_setDirection(builder,AAUDIO_DIRECTION_OUTPUT);
        StreamBuilder_setSharingMode(builder,AAUDIO_SHARING_MODE_SHARED);
        StreamBuilder_setFormat(builder,AAUDIO_FORMAT_PCM_I16);
        StreamBuilder_setChannelCount(builder,2);
        StreamBuilder_setSampleRate(builder,48000);
        StreamBuilder_setBufferCapacityInFrames(builder,1920);
        const auto result=StreamBuilder_openStream(builder,&stream_);
        StreamBuilder_delete(builder);
        if(result!=AAUDIO_OK || !stream_) {close();return false;}
        if(Stream_getChannelCount(stream_)!=2 || Stream_getSampleRate(stream_)!=48000 ||
           Stream_getFormat(stream_)!=AAUDIO_FORMAT_PCM_I16 || Stream_requestStart(stream_)!=AAUDIO_OK) {
            close();return false;
        }
        return true;
#else
        std::fprintf(stderr,"[audio:native] AAudio device requires Android; no output device\n");
        return false;
#endif
    }
    int write(const int16_t *pcm,int frames) override {
#ifdef __ANDROID__
        return Stream_write(stream_,pcm,frames,20000000LL);
#else
        (void)pcm;(void)frames;return -1;
#endif
    }
    void close() override {
#ifdef __ANDROID__
        if(stream_) {Stream_requestStop(stream_);Stream_close(stream_);stream_=nullptr;}
        if(library_) {dlclose(library_);library_=nullptr;}
#endif
    }
};
namespace {
AndroidDevice native_device;
Device *device=&native_device;
Queue queue;
Resampler resampler;
FrameClock frame_clock;
std::thread worker;
std::atomic<bool> stop{false}, failed{false};
std::atomic<uint32_t> dropped{0}, silent{0};
int opened=0, volume=-1;
bool cleanup_registered=false;
FILE *wav=nullptr;
uint32_t wav_frames=0;
void le16(FILE *f,uint16_t v) {unsigned char b[]={static_cast<unsigned char>(v),static_cast<unsigned char>(v>>8)};std::fwrite(b,1,2,f);}
void le32(FILE *f,uint32_t v) {le16(f,v&65535);le16(f,v>>16);}
void wav_header(FILE *f,uint32_t frames) {
    std::fwrite("RIFF",1,4,f);le32(f,36+frames*4);std::fwrite("WAVEfmt ",1,8,f);
    le32(f,16);le16(f,1);le16(f,2);le32(f,32768);le32(f,32768*4);le16(f,4);le16(f,16);
    std::fwrite("data",1,4,f);le32(f,frames*4);
}
void output_worker() {
    int16_t block[480*2];
    while(!stop.load(std::memory_order_acquire)) {
        silent.fetch_add(resampler.render(queue,block,480),std::memory_order_relaxed);
        int sent=0;
        while(sent<480 && !stop.load(std::memory_order_acquire)) {
            const int n=device->write(block+sent*2,480-sent);
            if(n<0 || n>480-sent) {failed.store(true,std::memory_order_release);return;}
            sent+=n;
            if(n==0) std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    }
}
void stop_device() {
    stop.store(true,std::memory_order_release);
    if(worker.joinable()) worker.join();
    device->close();
    queue.reset();resampler.reset();
}
}
#ifdef SM64DS_AUDIO_TEST
void set_test_device(Device *d) {if(opened>0 || worker.joinable())std::abort();device=d?d:&native_device;}
uint32_t test_dropped_frames(){return dropped.load();}
uint32_t test_silent_frames(){return silent.load();}
#endif
}
using namespace sm64ds_audio;
int out_volume_pct() {
    if(volume<0) {
        const char *s=std::getenv("SM64DS_VOLUME");
        const long n=s&&*s?std::strtol(s,nullptr,10):(std::getenv("SM64DS_SOUND")?100:50);
        volume=static_cast<int>(n<0?0:(n>100?100:n));
    }
    return volume;
}
extern "C" void out_set_volume_pct(int value){volume=std::max(0,std::min(100,value));}
int sd_out_open() {
    if(opened) return opened>0;
    opened=-1;
    if(std::getenv("SM64DS_NO_AUDIO")) return 0;
    if(!device->open()) {std::fprintf(stderr,"[audio:native] open failed; mixer continues without device\n");return 0;}
    stop.store(false);failed.store(false);queue.reset();resampler.reset();
    try {worker=std::thread(output_worker);} catch(...) {device->close();return 0;}
    opened=1;
    if(!cleanup_registered) {std::atexit(sd_out_close);cleanup_registered=true;}
    std::fprintf(stderr,"[audio:native] stereo 32768 -> 48000 Hz, engine-owned mixer\n");
    return 1;
}
void sd_out_close() {
    if(opened>0 || worker.joinable()) stop_device();
    opened=0;failed.store(false);frame_clock.reset();sd_wav_close();
}
void sd_out_push() {
    if(!opened) sd_out_open();
    if(opened>0 && failed.load(std::memory_order_acquire)) {
        stop_device();opened=-1;
        std::fprintf(stderr,"[audio:native] device disconnected; close/reopen required\n");
    }
    int16_t pcm[547*2];
    const unsigned frames=frame_clock.next();
    sd_mix_render(pcm,static_cast<int>(frames)); // volume is applied by the ORIGINAL mixer
    sd_wav_write(pcm,static_cast<int>(frames));
    if(opened>0) dropped.fetch_add(frames-queue.push(pcm,frames),std::memory_order_relaxed);
}
void sd_wav_open(const char *path) {
    if(wav || !path || !*path) return;
    wav=std::fopen(path,"wb");
    if(!wav) {std::perror("[audio:native] WAV open");return;}
    wav_frames=0;wav_header(wav,0);std::atexit(sd_wav_close);
}
void sd_wav_write(const sd_s16 *pcm,int frames) {
    if(!wav || !pcm || frames<=0) return;
    constexpr uint32_t max_frames=(UINT32_MAX-36u)/4u;
    const uint32_t n=std::min(static_cast<uint32_t>(frames),max_frames-wav_frames);
    // Android and our tested ELF hosts are little-endian; reject elsewhere.
#if __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "WAV PCM output requires little-endian samples"
#endif
    const size_t wrote=std::fwrite(pcm,4,n,wav);
    wav_frames+=static_cast<uint32_t>(wrote);
    if(wrote!=n || n<static_cast<uint32_t>(frames)) {
        std::fprintf(stderr,"[audio:native] WAV write failed or RIFF limit reached\n");sd_wav_close();
    }
}
void sd_wav_close() {
    if(!wav) return;
    if(std::fseek(wav,0,SEEK_SET)==0) wav_header(wav,wav_frames);
    if(std::fclose(wav)!=0) std::perror("[audio:native] WAV close");
    wav=nullptr;
}
