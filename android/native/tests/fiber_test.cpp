// SPDX-License-Identifier: MIT
#include "sm64ds_fiber.h"
#include <cfenv>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>
using namespace sm64ds::platform;
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #x); std::abort(); } } while (0)
struct State { Fiber *root; std::uint64_t count = 0; std::uint64_t limit; };
static void counter(void *arg) {
    auto &s = *static_cast<State *>(arg);
    volatile std::uint64_t stack_canary[8];
    for (unsigned i=0; i<8; ++i) stack_canary[i] = 0xabcd0000u+i;
    CHECK(std::fesetround(FE_DOWNWARD) == 0);
    for (std::uint64_t i=0; i<s.limit; ++i) {
        CHECK(std::fegetround() == FE_DOWNWARD);
        for (unsigned j=0; j<8; ++j) CHECK(stack_canary[j] == 0xabcd0000u+j);
        ++s.count;
        CHECK(switch_to_fiber(s.root));
    }
}
static void empty(void *) {}
int main() {
    CHECK(current_fiber() == nullptr);
    CHECK(create_fiber(0, empty, nullptr) == nullptr);
    auto *root = thread_to_fiber(); CHECK(root);
    CHECK(thread_to_fiber() == nullptr);
    CHECK(create_fiber(0, nullptr, nullptr) == nullptr);
    CHECK(create_fiber(128u*1024*1024, empty, nullptr) == nullptr);
    CHECK(switch_to_fiber(root));
    const int saved_round = std::fegetround();
    CHECK(std::fesetround(FE_UPWARD) == 0);
    State a{root, 0, 100000}, b{root, 0, 100000};
    auto *fa = create_fiber(256*1024, counter, &a);
    auto *fb = create_fiber(256*1024, counter, &b);
    CHECK(fa && fb); CHECK(!fiber_to_thread());
    for (std::uint64_t i=0; i<a.limit; ++i) {
        CHECK(switch_to_fiber(fa)); CHECK(a.count == i+1);
        CHECK(std::fegetround() == FE_UPWARD);
        CHECK(switch_to_fiber(fb)); CHECK(b.count == i+1);
        CHECK(std::fegetround() == FE_UPWARD);
    }
    CHECK(switch_to_fiber(fa)); CHECK(fiber_finished(fa));
    CHECK(switch_to_fiber(fb)); CHECK(fiber_finished(fb));
    CHECK(!switch_to_fiber(fa)); CHECK(!delete_fiber(root));
    std::thread other([&] {
        auto *r = thread_to_fiber(); CHECK(r);
        CHECK(!switch_to_fiber(fa)); CHECK(!delete_fiber(fb));
        auto *f = create_fiber(0, empty, nullptr); CHECK(f);
        CHECK(switch_to_fiber(f)); CHECK(fiber_finished(f));
        CHECK(delete_fiber(f)); CHECK(fiber_to_thread());
    }); other.join();
    CHECK(delete_fiber(fa)); CHECK(delete_fiber(fb));
    // Repeated creation/deletion detects broken root state or leaked live counters.
    for (int i=0; i<1000; ++i) {
        auto *f = create_fiber(1, empty, nullptr); CHECK(f);
        CHECK(switch_to_fiber(f)); CHECK(fiber_finished(f)); CHECK(delete_fiber(f));
    }
    CHECK(std::fesetround(saved_round) == 0);
    CHECK(fiber_to_thread()); CHECK(current_fiber() == nullptr);
    std::puts("PASS: 200000 yields, 400000 stress switches, two fibers, stack canaries, FP rounding, thread ownership, 1000 lifecycles");
}
