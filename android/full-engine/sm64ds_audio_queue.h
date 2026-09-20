/* Single engine-thread producer and single audio-thread consumer. Reset only
 * after the consumer has stopped. PCM is stereo signed 16 bit at 32768 Hz.
 * No mixer, game state, allocation, locks or file I/O on the consumer path.
 */
#ifndef SM64DS_AUDIO_QUEUE_H
#define SM64DS_AUDIO_QUEUE_H
#include <atomic>
#include <cstddef>
#include <cstdint>
namespace sm64ds_audio {
struct Frame { int16_t l, r; };
class Queue {
    static constexpr uint32_t capacity_ = 4096;
    Frame data_[capacity_]{};
    alignas(64) std::atomic<uint32_t> written_{0};
    alignas(64) std::atomic<uint32_t> read_{0};
public:
    static_assert(std::atomic<uint32_t>::is_always_lock_free, "PCM queue must be lock-free");
    uint32_t push(const int16_t *pcm, uint32_t frames) {
        const uint32_t w = written_.load(std::memory_order_relaxed);
        const uint32_t r = read_.load(std::memory_order_acquire);
        uint32_t free = capacity_ - (w - r);
        const uint32_t n = frames < free ? frames : free;
        for (uint32_t i=0; i<n; ++i) data_[(w+i) & (capacity_-1)] = {pcm[i*2],pcm[i*2+1]};
        written_.store(w+n,std::memory_order_release);
        return n;
    }
    uint32_t available() const {
        return written_.load(std::memory_order_acquire) - read_.load(std::memory_order_relaxed);
    }
    Frame peek(uint32_t offset) const { return data_[(read_.load(std::memory_order_relaxed)+offset)&(capacity_-1)]; }
    void consume(uint32_t n) { read_.store(read_.load(std::memory_order_relaxed)+n,std::memory_order_release); }
    void reset() { written_.store(0); read_.store(0); }
};
/* Output fixed at 48000 Hz. Integer phase persists across block boundaries;
 * at an underrun silence is emitted, and existing data is never read out of
 * bounds or repeated as a stuck tone. One look-ahead source frame is kept. */
class Resampler {
    uint32_t phase_ = 0;
public:
    void reset() { phase_ = 0; }
    uint32_t render(Queue &q, int16_t *out, uint32_t frames) {
        uint32_t silent=0;
        for(uint32_t i=0;i<frames;++i) {
            if(q.available()<2) {out[i*2]=out[i*2+1]=0;phase_=0;++silent;continue;}
            const auto a=q.peek(0), b=q.peek(1);
            out[i*2]=static_cast<int16_t>((int64_t(a.l)*(48000-phase_)+int64_t(b.l)*phase_)/48000);
            out[i*2+1]=static_cast<int16_t>((int64_t(a.r)*(48000-phase_)+int64_t(b.r)*phase_)/48000);
            phase_+=32768;
            const uint32_t used=phase_/48000;
            phase_%=48000;
            if(used) q.consume(used);
        }
        return silent;
    }
};
class FrameClock {
    uint32_t remainder_ = 0;
public:
    unsigned next() {remainder_+=32768;unsigned n=remainder_/60;remainder_%=60;return n;}
    void reset() {remainder_=0;}
};
struct Device {
    virtual ~Device()=default;
    virtual bool open()=0;
    // Write at most frames. 0 means timeout; negative means a device failure.
    virtual int write(const int16_t *pcm,int frames)=0;
    // Called only after writer has joined; never races with write().
    virtual void close()=0;
};
#ifdef SM64DS_AUDIO_TEST
void set_test_device(Device *device);
uint32_t test_dropped_frames();
uint32_t test_silent_frames();
#endif
}
#endif
