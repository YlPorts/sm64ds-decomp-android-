// SPDX-License-Identifier: MIT
// Included into the scheduler probe. Original C/C++ creation, resume, join and
// exit functions are linked from src/. Entries below are synthetic test jobs.
extern "C" {
void func_02058200(char *, int, int, int, int, int);
void func_02058048(void *);
void func_0205816c(void *);
void func_020581a8();
void func_02058568(void *, unsigned, unsigned);
void MultiStore_Int(int, int *, int);
int func_02058538();
}
namespace {
struct alignas(8) TestStack {
    uint32_t before[4];
    uint32_t words[256];
    uint32_t after[4];
};
uint16_t child_queue;
unsigned child_phase[16];
unsigned child_calls;
uint32_t last_argument;
uint32_t order[32];
unsigned order_size;

void returning_child(uint32_t argument) {
    require(mgr_current() == g_running && g_running != &g_main, "entry uses created record");
    require(data_020a6148[g_running->id] == static_cast<int>(reinterpret_cast<intptr_t>(g_running)), "created entry owns real table slot");
    ++child_calls;
    last_argument = argument;
}
void different_child(uint32_t argument) {
    returning_child(argument ^ 0x5a5a1234u);
}
void sleeping_child(uint32_t index) {
    require(index < 16, "entry argument reaches correct job");
    volatile uint32_t canary[32];
    for (unsigned i=0; i<32; ++i) canary[i] = index * 100 + i;
    child_phase[index] = 1;
    OS_SleepThread(&child_queue);
    for (unsigned i=0; i<32; ++i)
        require(canary[i] == index * 100 + i, "created thread preserves its own stack");
    child_phase[index] = 2;
}
void ordered_child(uint32_t value) {
    require(order_size < 32, "bounded order log");
    order[order_size++] = value;
}
int word(const void *p) { return static_cast<int>(reinterpret_cast<intptr_t>(p)); }
int entry_word(void (*entry)(uint32_t)) {
    return static_cast<int>(reinterpret_cast<uintptr_t>(entry));
}
void create_job(RomThread &record, TestStack &stack, void (*entry)(uint32_t),
                uint32_t argument, unsigned priority) {
    std::memset(&record, 0xa5, sizeof(record));
    std::memset(&stack, 0x7e, sizeof(stack));
    func_02058200(reinterpret_cast<char *>(&record), entry_word(entry),
                 static_cast<int>(argument), word(stack.words + 256),
                 sizeof(stack.words), priority);
}
Sm64dsSchedulerStats snapshot() {
    Sm64dsSchedulerStats value{};
    require(sm64ds_native_scheduler_snapshot(&value), "owner can inspect native lifetime counts");
    return value;
}
void no_created_slots() {
    auto s = snapshot();
    require(s.created_slots == 0 && s.retired_slots == 0, "all completed native slots collected");
    require(func_02058538() == 2, "original allocator sees slot 2 free again");
    require(mgr_head() == &g_main && g_main.next == &g_idle && g_idle.next == nullptr,
            "original exit removed every created ready-list node");
}
void run_lifetime_cases() {
    require(reinterpret_cast<unsigned char *>(data_020a6148) == mgr() + 0x14,
            "table symbol aliases manager tail instead of relying on linker order");
    require(func_02058538() == 2, "creation skips the two boot threads");
    pass("contiguous 0x54-byte original manager and slot-table aliases");

    alignas(4) uint32_t context[0x94/4];
    for (unsigned thumb=0; thumb<2; ++thumb) {
        std::memset(context, 0xa5, sizeof(context));
        func_02058568(context, 0x12340000u + thumb, 0x20000u);
        require(context[0] == (thumb ? 0x3fu : 0x1fu), "context ARM/Thumb CPSR bit");
        require(context[0x40/4] == 0x12340004u + thumb && context[0x44/4] == 0x20000u &&
                context[0x38/4] == 0x1ffc0u, "context entry and stack arithmetic");
        for (unsigned i=1; i<=13; ++i) require(context[i] == 0, "context r0-r12 clear");
        require(context[0x3c/4] == 0, "context LR clear");
        for (unsigned i=0x48/4; i<0x94/4; ++i)
            require(context[i] == 0xa5a5a5a5u, "context primitive leaves thread fields alone");
    }
    int filled[4] = {9,9,9,9};
    MultiStore_Int(3, filled, 5);
    require(filled[0] == 3 && filled[1] == 3 && filled[2] == 9, "original word-fill length semantics");
    MultiStore_Int(7, filled, 0);
    require(filled[0] == 3, "zero-length fill leaves memory unchanged");
    pass("native context initialization and word-fill match hand-assembly stores");

    RomThread record;
    TestStack stack;
    create_job(record, stack, returning_child, 0xfedcba98u, 8);
    require(record.id == 2 && record.state == 0 && record.prio == 8, "original create record fields");
    require(record.r0 == 0xfedcba98u && record.pc4 == static_cast<uint32_t>(entry_word(returning_child)) + 4u,
            "original create records argument and entry");
    require(record.lr == static_cast<uint32_t>(reinterpret_cast<uintptr_t>(&func_020581a8)), "original exit thunk stored in LR");
    require(stack.words[0] == 0x7bf9dd5bu && stack.words[255] == 0xfddb597du, "original DS stack guards");
    for (unsigned i=1; i<255; ++i) require(stack.words[i] == 0, "original create fills stack interior");
    for (unsigned i=0; i<4; ++i)
        require(stack.before[i] == 0x7e7e7e7eu && stack.after[i] == 0x7e7e7e7eu, "DS stack outside canaries untouched");
    auto completed = snapshot().collected;
    func_02058048(&record);
    require(child_calls == 1 && last_argument == 0xfedcba98u, "original resume entered new job");
    require(record.state == 2 && data_020a6148[2] == 0, "original exit cleared slot and marked exited");
    require(snapshot().collected == completed + 1, "native stack collected after original exit switch");
    no_created_slots();
    pass("original create/resume/return/exit, guard words and native stack retirement");

    completed = snapshot().collected;
    for (unsigned i=0; i<512; ++i) {
        const auto entry = (i & 1u) ? different_child : returning_child;
        create_job(record, stack, entry, i, 8);
        const auto calls = child_calls;
        func_02058048(&record);
        require(child_calls == calls + 1, "reused record must execute a NEW entry");
        require(last_argument == ((i & 1u) ? (i ^ 0x5a5a1234u) : i), "reused record must not cache old argument or function");
        require(record.state == 2 && snapshot().created_slots == 0, "no native slot accumulation over lifetimes");
    }
    require(snapshot().collected == completed + 512, "512 stacks retired and collected");
    no_created_slots();
    pass("512 reused-record lifetimes with alternating entries; no stale fiber or slot leak");

    create_job(record, stack, sleeping_child, 0, 8);
    child_queue = 0; child_phase[0] = 0;
    func_02058048(&record);
    require(child_phase[0] == 1 && record.state == 0 && child_queue == (1u << record.id), "created thread really slept on original queue");
    require(sm64ds_native_scheduler_collect() == 0 && snapshot().created_slots == 1, "collector must not cancel a live sleeper");
    OS_WakeupThread(&child_queue);
    require(child_phase[0] == 2 && child_queue == 0 && record.state == 2, "created sleeper resumed and exited");
    no_created_slots();
    pass("created-thread sleep/wake, preserved locals and no collection of a live stack");

    create_job(record, stack, returning_child, 42, 24);
    const auto calls = child_calls;
    func_02058048(&record);
    require(child_calls == calls && record.state == 1, "lower-priority runnable child waits behind main");
    func_0205816c(&record);
    require(child_calls == calls + 1 && record.state == 2 && record.joinq == 0, "original join sleeps until original exit wakes it");
    const auto switches = g_stat.restores;
    func_0205816c(&record);
    require(g_stat.restores == switches, "join of exited thread must not sleep");
    no_created_slots();
    pass("original join and lower-priority execution; join of an exited thread returns");

    RomThread records[15];
    TestStack stacks[15];
    for (unsigned i=0; i<14; ++i) {
        create_job(records[i], stacks[i], ordered_child, i, 15-i);
        require(records[i].id == i+2, "original allocator uses every free slot");
    }
    require(func_02058538() == -1, "original sixteen-slot exhaustion");
    std::memset(&records[14], 0x6d, sizeof(RomThread));
    RomThread untouched = records[14];
    func_02058200(reinterpret_cast<char *>(&records[14]), entry_word(returning_child), 0,
                 word(stacks[14].words+256), sizeof(stacks[14].words), 3);
    require(std::memcmp(&records[14], &untouched, sizeof(RomThread)) == 0, "failed creation does not mutate record");
    order_size = 0;
    mgr_u16(4) = 1;
    for (unsigned i=0; i<14; ++i) func_02058048(&records[i]);
    require(order_size == 0, "scheduler lock defers all fourteen ready tasks");
    mgr_u16(4) = 0; mgr_u16(0) = 0;
    func_02057f54();
    require(order_size == 14, "all fourteen jobs entered and returned");
    for (unsigned i=0; i<14; ++i) require(order[i] == 13-i, "original priority list selects correct execution order");
    no_created_slots();
    pass("14 concurrent created jobs, slot exhaustion, priority order and all slots reusable");

    child_queue = 0;
    for (unsigned i=0; i<4; ++i) {
        child_phase[i] = 0;
        create_job(records[i], stacks[i], sleeping_child, i, i+4);
        func_02058048(&records[i]);
    }
    require(child_queue == 0x3cu, "shared wake queue contains four real thread-id bits");
    OS_WakeupThread(&child_queue);
    require(child_queue == 0, "shared wake cleared original queue");
    for (unsigned i=0; i<4; ++i) require(child_phase[i] == 2 && records[i].state == 2, "all shared-queue sleepers resumed and exited");
    no_created_slots();
    pass("one original wake resumes four created threads and completes all exits");

    create_job(record, stack, returning_child, 73, 8);
    const auto adopted = g_stat.adopted;
    const auto wrong = g_stat.wrong_thread;
    std::thread other([&record] {
        ARMRestoreContext(&record);
        require(ARMSaveContext(&record) == 1, "foreign save refused before slot binding");
        require(sm64ds_native_scheduler_collect() == -1 && errno == EPERM, "foreign collection refused");
    });
    other.join();
    require(g_stat.wrong_thread == wrong+2 && g_stat.adopted == adopted && snapshot().created_slots == 0,
            "foreign restore must not adopt the valid record before rejecting ownership");
    func_02058048(&record);
    no_created_slots();
    const auto rejected = g_stat.rejected;
    ARMRestoreContext(nullptr);
    require(g_stat.rejected == rejected+1 && mgr_current() == &g_main, "null restore rejected without dereference");
    pass("foreign-thread operations have no adoption side effects; null contexts rejected");
    std::printf("LIFETIMES: %llu completed native stacks collected; 17 original scheduling TUs; NOT GAMEPLAY\n",
                static_cast<unsigned long long>(snapshot().collected));
}
}
