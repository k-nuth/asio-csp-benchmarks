// Component costs behind the ready selection path. These are isolated loops
// on one thread; in-situ costs overlap in an out-of-order core, so they bound
// rather than add up to the benchmark figures. Build like the benchmark:
//   c++ -std=c++20 -O3 -DNDEBUG -DASIO_STANDALONE -pthread -Iinclude \
//     csp/bench/microbench.cpp -o /tmp/microbench && /tmp/microbench
#include <asio.hpp>
#include <asio/experimental/channel_select.hpp>
#include <chrono>
#include <cstdio>
#include <random>
using namespace asio::experimental;
using clock_type = std::chrono::steady_clock;
template<class F> void bench(const char* name, F f, long n = 10000000) {
  auto t0 = clock_type::now();
  for (long i = 0; i < n; ++i) f();
  auto t1 = clock_type::now();
  std::printf("%-46s %7.2f ns\n", name, std::chrono::duration<double, std::nano>(t1 - t0).count() / n);
}
static inline void sink(const void* p) { asm volatile("" : : "r"(p) : "memory"); }
// Xorshift64* with multiply-high reduction, the Crossbeam/Tokio style draw that
// was measured and not adopted (see IMPLEMENTATION.md).
struct multiply_high_random {
  std::uint64_t s = 0x9e3779b97f4a7c15;
  std::uint64_t next() { auto x = s; x ^= x >> 12; x ^= x << 25; x ^= x >> 27; s = x; return x * 2685821657736338717ULL; }
};
int main() {
  asio::io_context ctx;
  select_channel<std::uint64_t> a(1), b(1), c(1);
  a.try_send(7); b.try_send(7); c.try_send(7);
  asio::any_io_executor first = ctx.get_executor(), second = ctx.get_executor();
  std::array<std::size_t, 3> order{0, 1, 2};
  using cases_type = std::tuple<decltype(receive(a)), decltype(receive(b)), decltype(receive(c))>;
  using completion_type = std::tuple<asio::error_code, channel_select_result<
      decltype(receive(a)), decltype(receive(b)), decltype(receive(c))>>;
  bench("std::shuffle(3), per-worker generator", [&] {
    thread_local channel_select_detail::selection_random engine;
    std::shuffle(order.begin(), order.end(), engine); sink(&order); });
  bench("fisher-yates(3), 32-bit multiply-high (biased draw)", [&] {
    thread_local multiply_high_random engine;
    for (std::size_t i = 2; i > 0; --i) {
      auto draw = static_cast<std::uint64_t>(static_cast<std::uint32_t>(engine.next() >> 32));
      std::swap(order[i], order[static_cast<std::size_t>((draw * (i + 1)) >> 32)]);
    }
    sink(&order); });
  channel_select_detail::selection_random owned_engine(channel_select_detail::worker_random());
  bench("fisher-yates(3), exact draws, per-operation generator", [&] {
    channel_select_detail::shuffle_order(order, channel_select_options{}, owned_engine); sink(&order); });
  std::mutex mutex;
  bench("std::mutex lock+unlock", [&] { std::unique_lock<std::mutex> lock(mutex); sink(&mutex); });
  bench("any_io_executor copy+destroy", [&] { asio::any_io_executor copy = first; sink(&copy); });
  bench("any_io_executor ==", [&] { bool equal = first == second; sink(&equal); });
  bench("receive(channel) construct+destroy", [&] { auto r = receive(a); sink(&r); });
  bench("three-case tuple construct+destroy", [&] { cases_type t{receive(a), receive(b), receive(c)}; sink(&t); });
  bench("three-case tuple move", [&] { cases_type t{receive(a), receive(b), receive(c)}; auto u = std::move(t); sink(&u); });
  bench("completion emplace (one move) + move out", [&] {
    cases_type cases{receive(a), receive(b), receive(c)};
    std::optional<completion_type> completed;
    completed.emplace(asio::error_code{}, channel_select_detail::committed{std::size_t{1}, cases});
    auto out = std::move(*completed); sink(&out); });
  bench("ready_budget_exhausted()", [&] { bool y = channel_select_detail::ready_budget_exhausted(); sink(&y); });
  bench("try_ready(3 ready) + refill", [&] {
    cases_type cases{receive(a), receive(b), receive(c)}; channel_select_detail::ready_decision d;
    bool ok = channel_select_detail::try_ready(cases, {}, {}, false, d); sink(&ok);
    select_channel<std::uint64_t>* channels[] = {&a, &b, &c}; channels[d.index]->try_send(7); });
  bench("try_ready(3 ready, biased) + refill", [&] {
    cases_type cases{receive(a), receive(b), receive(c)}; channel_select_detail::ready_decision d;
    channel_select_options options; options.biased = true;
    bool ok = channel_select_detail::try_ready(cases, options, {}, false, d); sink(&ok);
    select_channel<std::uint64_t>* channels[] = {&a, &b, &c}; channels[d.index]->try_send(7); });
  bench("try_receive + try_send (one channel)", [&] {
    asio::error_code e; auto v = a.try_receive(e); a.try_send(std::move(*v)); sink(&v); });
  // Floors: the work the contract itself requires, without any selection
  // machinery. A ready selection must take owning case handles, inspect one
  // randomly chosen channel's mutex-protected FIFO state, and give the buffer
  // slot back; a suspended handoff must allocate and construct an owned
  // operation, register and withdraw under the channel mutex, and resume the
  // waiter through one executor turn.
  bench("floor: 3 owning handles + random channel pop/push", [&] {
    thread_local channel_select_detail::selection_random engine;
    auto ha = a.state(), hb = b.state(), hc = c.state();
    channel_select_detail::channel_state<std::uint64_t>* channels[] = {ha.get(), hb.get(), hc.get()};
    auto* channel = channels[engine() % 3];
    std::optional<std::uint64_t> value;
    { std::lock_guard<std::mutex> lock(channel->mutex); channel->pop(value); }
    { std::lock_guard<std::mutex> lock(channel->mutex); channel->push(value); }
    sink(&value); sink(ha.get()); sink(hb.get()); sink(hc.get()); });
  bench("floor: one executor turn (post + run_one)", [&] {
    asio::post(ctx.get_executor(), [] {}); ctx.restart(); ctx.run_one(); });
  bench("floor: one continuation turn (defer + run_one)", [&] {
    asio::defer(ctx.get_executor(), [] {}); ctx.restart(); ctx.run_one(); });
  // The same turn submitted through any_io_executor: a type-erased function
  // object per submission. The fourth iteration hands turns to the plain
  // io_context executor behind it, or links the operation itself into the
  // scheduler, instead.
  bench("one continuation turn via any_io_executor (defer + run_one)", [&] {
    asio::defer(first, [] {}); ctx.restart(); ctx.run_one(); });
  struct turn_op : asio::detail::scheduler_operation {
    turn_op() : scheduler_operation(&turn_op::run) {}
    static void run(void*, scheduler_operation*, const asio::error_code&, std::size_t) {}
  } preallocated;
  auto& scheduler = asio::use_service<asio::detail::scheduler>(ctx);
  bench("one continuation turn, preallocated scheduler operation", [&] {
    scheduler.post_immediate_completion(&preallocated, true); ctx.restart(); ctx.run_one(); });
  // In situ: a chain of continuations inside one run(), each handler queueing
  // the next on the private queue, as a wakeup chain does.
  for (int variant = 0; variant < 2; ++variant) {
    long n = 2000000, count = 0; double ns = 0; clock_type::time_point t0;
    struct chain_op : asio::detail::scheduler_operation {
      asio::detail::scheduler* scheduler; long* count; long n; double* ns; clock_type::time_point* t0;
      chain_op() : scheduler_operation(&chain_op::run) {}
      static void run(void* owner, scheduler_operation* base, const asio::error_code&, std::size_t) {
        auto* self = static_cast<chain_op*>(base);
        if (!owner) return;
        if (++*self->count < self->n) self->scheduler->post_immediate_completion(self, true);
        else *self->ns = std::chrono::duration<double, std::nano>(clock_type::now() - *self->t0).count() / self->n;
      }
    } chain;
    chain.scheduler = &scheduler; chain.count = &count; chain.n = n; chain.ns = &ns; chain.t0 = &t0;
    struct typed_chain { asio::io_context::executor_type ex; long* count; long n; double* ns; clock_type::time_point* t0;
      void operator()() const {
        if (++*count < n) asio::defer(ex, typed_chain{ex, count, n, ns, t0});
        else *ns = std::chrono::duration<double, std::nano>(clock_type::now() - *t0).count() / n; } };
    t0 = clock_type::now();
    if (variant) scheduler.post_immediate_completion(&chain, true);
    else asio::defer(ctx.get_executor(), typed_chain{ctx.get_executor(), &count, n, &ns, &t0});
    ctx.restart(); ctx.run();
    std::printf("%-46s %7.2f ns\n", variant ? "in situ: preallocated operation re-queued per turn"
        : "in situ: typed defer of a small lambda per turn", ns);
  }
  for (int typed_path = 0; typed_path < 2; ++typed_path) {
    double ns = 0;
    asio::post(ctx, [&] {
      auto t0 = clock_type::now();
      for (long i = 0; i < 5000000; ++i) {
        if (typed_path) asio::dispatch(ctx.get_executor(), [] { sink(nullptr); });
        else asio::dispatch(first, [] { sink(nullptr); });
      }
      ns = std::chrono::duration<double, std::nano>(clock_type::now() - t0).count() / 5000000;
    });
    ctx.restart(); ctx.run();
    std::printf("%-46s %7.2f ns\n", typed_path ? "in situ: inline dispatch via io_context executor"
        : "in situ: inline dispatch via any_io_executor", ns);
  }
  asio::cancellation_signal signal;
  bench("cancellation slot assign + clear (16-byte handler)", [&] {
    signal.slot().assign([p = &ctx, g = std::uint64_t{1}](asio::cancellation_type_t) { sink(p); sink(&g); });
    signal.slot().clear(); });
  // What a per-operation asio::strand added to each of those turns, and to
  // each operation, before the serial turn runner replaced it.
  bench("strand: make_strand construct+destroy", [&] { auto s = asio::make_strand(first); sink(&s); });
  auto strand = asio::make_strand(first);
  bench("strand: one strand turn (post + run)", [&] {
    asio::post(strand, [] {}); ctx.restart(); ctx.run(); });
  auto handler = [](asio::error_code, auto) {};
  using owned = channel_select_detail::select_op<decltype(handler),
      decltype(receive(a)), decltype(receive(b)), decltype(receive(c))>;
  bench("floor: recycled owned operation construct+destroy", [&] {
    auto op = std::allocate_shared<owned>(asio::recycling_allocator<void>(), first, channel_select_options{},
        handler, cases_type{receive(a), receive(b), receive(c)}); sink(op.get()); }, 2000000);
  bench("floor: register + withdraw one case under its mutex", [&] {
    auto op = std::allocate_shared<owned>(asio::recycling_allocator<void>(), first, channel_select_options{},
        handler, cases_type{receive(a), receive(b), receive(c)});
    { std::lock_guard<std::mutex> lock(a.state()->mutex); op->register_case(0); }
    { std::lock_guard<std::mutex> lock(a.state()->mutex); op->unlink_cases(); }
    sink(op.get()); }, 2000000);
  // The reusable state keeps its registration storage: registering and
  // withdrawing one case costs only the list links under the mutex.
  auto state = std::make_shared<channel_select_detail::reusable_state<
      decltype(receive(a)), decltype(receive(b)), decltype(receive(c))>>(first, channel_select_options{},
      std::stop_token{}, cases_type{receive(a), receive(b), receive(c)});
  bench("reusable state: register + withdraw one case under its mutex", [&] {
    { std::lock_guard<std::mutex> lock(a.state()->mutex); state->register_case(0); }
    state->withdraw_cases(); sink(state.get()); });
  bench("reusable state: ready probe (3 ready) + refill", [&] {
    state->begin_wait();
    bool ok = state->probe_now(false); sink(&ok);
    select_channel<std::uint64_t>* channels[] = {&a, &b, &c}; channels[std::get<1>(state->decision)]->try_send(7); });
}
