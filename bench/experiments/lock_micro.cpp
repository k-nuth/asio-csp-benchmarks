// Upper bound of what a different channel lock could buy on the ready path:
// uncontended std::mutex versus a bare atomic spin lock, lock+unlock pairs.
// Build: c++ -std=c++20 -O3 -DNDEBUG -pthread csp/bench/experiments/lock_micro.cpp -o /tmp/lock_micro
// Retained result (Mac): 4.1 ns against 3.6 ns per pair, 6.6 against 7.3 ns
// for the two pairs of a probe and a try_send; not adopted. See IMPLEMENTATION.md.
#include <atomic>
#include <chrono>
#include <cstdio>
#include <mutex>
using clock_type = std::chrono::steady_clock;
template<class F> void bench(const char* name, F f, long n = 20000000) {
  auto t0 = clock_type::now();
  for (long i = 0; i < n; ++i) f();
  auto t1 = clock_type::now();
  std::printf("%-46s %7.2f ns\n", name, std::chrono::duration<double, std::nano>(t1 - t0).count() / n);
}
static inline void sink(const void* p) { asm volatile("" : : "r"(p) : "memory"); }
struct spin_lock {
  std::atomic<bool> held{false};
  void lock() { while (held.exchange(true, std::memory_order_acquire)) {} }
  void unlock() { held.store(false, std::memory_order_release); }
};
int main() {
  std::mutex m; spin_lock s;
  bench("std::mutex lock+unlock", [&] { std::lock_guard<std::mutex> l(m); sink(&m); });
  bench("atomic spin lock+unlock", [&] { std::lock_guard<spin_lock> l(s); sink(&s); });
  bench("two std::mutex pairs (probe + try_send)", [&] {
    { std::lock_guard<std::mutex> l(m); sink(&m); } { std::lock_guard<std::mutex> l(m); sink(&m); } });
  bench("two spin pairs (probe + try_send)", [&] {
    { std::lock_guard<spin_lock> l(s); sink(&s); } { std::lock_guard<spin_lock> l(s); sink(&s); } });
}
