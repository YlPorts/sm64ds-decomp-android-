/* Device and mixer are explicit boundary fixtures: this is not a recording of
 * the game, AAudio execution, or a test with real SDAT resources. */
#include "sdat.h"
#include "sm64ds_audio_queue.h"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <vector>
using namespace sm64ds_audio;
static int checks=0;
#define CHECK(x) do {if(!(x)){std::fprintf(stderr,"FAIL audio line %d: %s\n",__LINE__,#x);std::exit(1);}++checks;}while(0)
static const auto engine=std::this_thread::get_id();
static unsigned mixed=0;
static bool wrong_thread=false;
void sd_mix_render(sd_s16 *pcm,int n) {
    if(std::this_thread::get_id()!=engine)wrong_thread=true;
    mixed+=n;
    for(int i=0;i<n;++i){pcm[i*2]=1234;pcm[i*2+1]=-1234;}
}
struct FakeDevice final:Device {
    bool fail_open=false;
    std::atomic<bool> fail_write{false}, closed{true}, overlap{false}, on_engine{false};
    std::atomic<unsigned> calls{0}, frames{0};
    bool open() override {closed=fail_open;return !fail_open;}
    int write(const int16_t*,int n) override {
        if(closed.load())overlap=true;
        if(std::this_thread::get_id()==engine)on_engine=true;
        unsigned c=calls.fetch_add(1);
        std::this_thread::sleep_for(std::chrono::microseconds(50));
        if(fail_write.load())return -1;
        if(c==0)return 0; // exercise a timeout, then partial writes
        int used=n<17?n:17;frames.fetch_add(used);return used;
    }
    void close() override {closed=true;}
};
static uint32_t le32(const unsigned char *p){return p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;}
int main(int argc,char **argv) {
    CHECK(argc==2);
    FrameClock clock;unsigned sum=0;bool bounded=true;
    for(int i=0;i<60;++i){unsigned n=clock.next();sum+=n;bounded&=n==546||n==547;}
    CHECK(sum==32768 && bounded);
    Queue q;std::vector<int16_t> samples(10000);
    for(int i=0;i<5000;++i){samples[2*i]=i;samples[2*i+1]=-i;}
    CHECK(q.push(samples.data(),5000)==4096);
    CHECK(q.push(samples.data(),1)==0 && q.available()==4096);
    q.consume(4000);CHECK(q.push(samples.data(),4000)==4000 && q.available()==4096);
    q.reset();Queue q2;
    CHECK(q.push(samples.data(),4000)==4000 && q2.push(samples.data(),4000)==4000);
    Resampler r,r2;std::vector<int16_t> one(6000), split(6000);
    CHECK(r.render(q,one.data(),3000)==0);
    CHECK(r2.render(q2,split.data(),711)==0 && r2.render(q2,split.data()+1422,2289)==0);
    CHECK(one==split && q.available()==q2.available());
    bool reference=true;
    for(int i=0;i<3000;++i){int expected=int(uint64_t(i)*32768/48000);reference &= one[2*i]==expected && one[2*i+1]==-expected;}
    CHECK(reference);
    q.reset();r.reset();std::fill(one.begin(),one.end(),-1);
    CHECK(r.render(q,one.data(),3000)==3000);
    CHECK(one==std::vector<int16_t>(6000,0));
    // Enough wraparounds and a concurrent producer to exercise ring ownership.
    q.reset();std::atomic<bool> okay{true};constexpr unsigned total=200000;
    std::thread producer([&]{for(unsigned i=0;i<total;){int16_t p[2]={int16_t(i%32767),int16_t(-(int(i%32767)))};if(q.push(p,1))++i;else std::this_thread::yield();}});
    for(unsigned i=0;i<total;){if(q.available()){auto p=q.peek(0);if(p.l!=int(i%32767)||p.r!=-int(i%32767))okay=false;q.consume(1);++i;}else std::this_thread::yield();}
    producer.join();CHECK(okay.load() && q.available()==0);
    // Open failure still advances the original mixer's interface at exact rate.
    FakeDevice fake;fake.fail_open=true;set_test_device(&fake);mixed=0;
    sd_wav_open(argv[1]);CHECK(sd_out_open()==0);
    for(int i=0;i<60;++i)sd_out_push();sd_out_close();CHECK(mixed==32768 && !wrong_thread);
    FILE *f=std::fopen(argv[1],"rb");CHECK(f!=nullptr);
    unsigned char header[48];CHECK(std::fread(header,1,48,f)==48);
    CHECK(!std::memcmp(header,"RIFF",4) && le32(header+24)==32768 && le32(header+40)==32768*4);
    CHECK(header[44]==0xd2 && header[45]==0x04 && header[46]==0x2e && header[47]==0xfb);
    std::fseek(f,0,SEEK_END);CHECK(std::ftell(f)==44+32768*4);std::fclose(f);
    // Healthy/partial writes, saturation, idempotent shutdown and restart.
    fake.fail_open=false;CHECK(sd_out_open()==1);
    for(int i=0;i<200;++i)sd_out_push();
    for(int i=0;i<100 && fake.frames.load()==0;++i)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    CHECK(fake.frames.load()>0 && test_dropped_frames()>0);
    sd_out_close();sd_out_close();CHECK(fake.closed && !fake.overlap && !fake.on_engine && !wrong_thread);
    const unsigned count=fake.calls.load();std::this_thread::sleep_for(std::chrono::milliseconds(5));CHECK(fake.calls.load()==count);
    fake.fail_write=true;CHECK(sd_out_open()==1);
    for(int i=0;i<100 && fake.calls.load()==count;++i)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    std::this_thread::sleep_for(std::chrono::milliseconds(5));sd_out_push();
    CHECK(fake.closed && sd_out_open()==0);sd_out_close();
    fake.fail_write=false;CHECK(sd_out_open()==1);sd_out_push();sd_out_close();
    out_set_volume_pct(-1);CHECK(out_volume_pct()==0);out_set_volume_pct(200);CHECK(out_volume_pct()==100);
    std::printf("audio pipeline: %d checks PASS; PCM fixture, not device playback\n",checks);
}
