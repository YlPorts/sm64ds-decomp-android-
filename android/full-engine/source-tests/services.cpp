#include "sm64ds_posix_clock.h"
#include "sm64ds_posix_debug.h"
#include <signal.h>
#include <sys/mman.h>
#include <sys/time.h>
#include <unistd.h>
#include <cstring>
static int cases;
#define CHECK(c) do { if (!(c)) { fprintf(stderr,"FAIL services line %d: %s\n",__LINE__,#c); return 1; } ++cases; } while(0)
static volatile sig_atomic_t signals_seen;
static void alarm_handler(int) { ++signals_seen; }
int main() {
    long long freq=0, a=0, b=0;
    CHECK(sm64ds_performance_frequency(&freq) && freq == 1000000000LL);
    CHECK(sm64ds_performance_counter(&a));
    sm64ds_sleep_ms(3);
    CHECK(sm64ds_performance_counter(&b) && b >= a + 3000000LL);
    CHECK(!sm64ds_performance_frequency(nullptr) && errno==EINVAL);
    CHECK(!sm64ds_performance_counter(nullptr) && errno==EINVAL);
    uint32_t first=sm64ds_ticks_ms(); sm64ds_sleep_ms(3);
    CHECK((uint32_t)(sm64ds_ticks_ms()-first) >= 3u);
    struct sigaction action{}, old{}; action.sa_handler=alarm_handler;
    CHECK(sigaction(SIGALRM,&action,&old)==0);
    itimerval alarm{}; alarm.it_value.tv_usec=5000;
    CHECK(setitimer(ITIMER_REAL,&alarm,nullptr)==0);
    sm64ds_performance_counter(&a); sm64ds_sleep_ms(20); sm64ds_performance_counter(&b);
    CHECK(signals_seen==1 && b-a>=20000000LL);
    alarm={}; setitimer(ITIMER_REAL,&alarm,nullptr); sigaction(SIGALRM,&old,nullptr);
    const long page=sysconf(_SC_PAGESIZE); CHECK(page>0);
    void *block=mmap(nullptr,(size_t)page*3,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(block!=MAP_FAILED);
    CHECK(mprotect(block,(size_t)page*2,PROT_READ|PROT_WRITE)==0);
    CHECK(sm64ds_bad_read_span(block,(size_t)page*2)==0);
    CHECK(sm64ds_bad_read_span(block,(size_t)page*2+1)!=0);
    CHECK(sm64ds_bad_read_span(nullptr,1)!=0 && sm64ds_bad_read_span(nullptr,0)==0);
    CHECK(sm64ds_bad_read_span(reinterpret_cast<void*>(UINTPTR_MAX-2),8)!=0);
    CHECK(mprotect(static_cast<char*>(block)+page,(size_t)page,PROT_NONE)==0);
    CHECK(sm64ds_bad_read_span(block,(size_t)page+1)!=0);
    CHECK(munmap(block,(size_t)page*3)==0);
    CHECK(sm64ds_module_base()!=nullptr);
    void *trace[8]{}; unsigned n=sm64ds_capture_backtrace(trace,8);
    CHECK(n>0 && n<=8 && trace[0]!=nullptr);
    CHECK(sm64ds_capture_backtrace(nullptr,8)==0 && sm64ds_capture_backtrace(trace,0)==0);
    printf("PASS: %d native service checks; clocks, interrupted sleep, map snapshots, module and unwinder. NOT GAMEPLAY\n",cases);
}
