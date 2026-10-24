// Isolating experiment for the random-candidate penalty of the ready probe:
// does dispatching a ready attempt through the fold over the heterogeneous
// case tuple cost more than a per-index function table, and does the cost
// come from the dispatch or from the randomly chosen channel itself? Build
// like the benchmark:
//   c++ -std=c++20 -O3 -DNDEBUG -DASIO_STANDALONE -pthread -Iinclude \
//     csp/bench/experiments/dispatch_micro.cpp -o /tmp/dispatch_micro && /tmp/dispatch_micro
// Retained result (Mac, third-iteration header): identity order 17.5 to 19.8
// ns (fold) against 14.7 ns (table); a predictable rotation 15.5 against
// 14.6; a single random draw 19.7 against 20.0; a full shuffle 23.9 against
// 23.3. A table saves nothing once the candidate is random, so specialized
// dispatch was not adopted. See IMPLEMENTATION.md.
#include <asio.hpp>
#include <asio/experimental/channel_select.hpp>
#include <chrono>
#include <cstdio>
using namespace asio::experimental;
namespace d = asio::experimental::channel_select_detail;
using clk = std::chrono::steady_clock;
template<class F> void bench(const char* name, F f, long n = 10000000) {
  auto t0 = clk::now(); for (long i = 0; i < n; ++i) f(); auto t1 = clk::now();
  std::printf("%-58s %7.2f ns\n", name, std::chrono::duration<double, std::nano>(t1 - t0).count() / n);
}
static inline void sink(const void* p) { asm volatile("" : : "r"(p) : "memory"); }
// Same per-candidate work as try_ready: lock one channel, attempt, commit; the
// fold dispatch is the one in the header, the table dispatch an alternative.
template<class... Cases>
bool probe_fold(std::tuple<Cases...>& cases, std::span<const std::size_t> order, d::ready_decision& decision) {
  for (auto index : order) {
    bool ready = std::apply([&](auto&... c) {
      std::size_t current = 0;
      auto attempt = [&](auto& selected) {
        std::unique_lock<std::mutex> lock;
        if (auto* channel = selected.base()) lock = std::unique_lock<std::mutex>(channel->mutex);
        return selected.attempt(decision, index);
      };
      return ((current++ == index && attempt(c)) || ...);
    }, cases);
    if (ready) return true;
  }
  return false;
}
template<class Tuple, std::size_t I>
bool attempt_at(Tuple& cases, std::size_t index, d::ready_decision& decision) {
  auto& selected = std::get<I>(cases);
  std::unique_lock<std::mutex> lock;
  if (auto* channel = selected.base()) lock = std::unique_lock<std::mutex>(channel->mutex);
  return selected.attempt(decision, index);
}
template<class... Cases>
bool probe_table(std::tuple<Cases...>& cases, std::span<const std::size_t> order, d::ready_decision& decision) {
  using fn = bool (*)(std::tuple<Cases...>&, std::size_t, d::ready_decision&);
  static constexpr auto table = []<std::size_t... I>(std::index_sequence<I...>) {
    return std::array<fn, sizeof...(Cases)>{&attempt_at<std::tuple<Cases...>, I>...};
  }(std::index_sequence_for<Cases...>());
  for (auto index : order) if (table[index](cases, index, decision)) return true;
  return false;
}
int main() {
  asio::io_context ctx; select_channel<std::uint64_t> a(1), b(1), c(1);
  a.try_send(7); b.try_send(7); c.try_send(7);
  select_channel<std::uint64_t>* channels[] = {&a, &b, &c};
  thread_local d::selection_random engine;
  std::size_t rotation = 0;
  auto run = [&](const char* name, auto&& dispatch, auto&& make_order) {
    bench(name, [&] {
      auto cases = std::tuple{receive(a), receive(b), receive(c)};
      std::array<std::size_t, 3> order = make_order();
      d::ready_decision decision;
      bool ok = dispatch(cases, std::span<const std::size_t>(order), decision); sink(&ok);
      channels[decision.index]->try_send(7);
    });
  };
  auto fold = [](auto& cases, auto order, auto& dn) { return probe_fold(cases, order, dn); };
  auto table = [](auto& cases, auto order, auto& dn) { return probe_table(cases, order, dn); };
  auto identity = [] { return std::array<std::size_t, 3>{0, 1, 2}; };
  auto rotate = [&] { auto s = rotation++ % 3; return std::array<std::size_t, 3>{s, (s + 1) % 3, (s + 2) % 3}; };
  auto shuffled = [&] { std::array<std::size_t, 3> o{0, 1, 2}; std::shuffle(o.begin(), o.end(), engine); return o; };
  auto random_start = [&] { auto s = static_cast<std::size_t>(engine() % 3); return std::array<std::size_t, 3>{s, (s + 1) % 3, (s + 2) % 3}; };
  for (int pass = 0; pass < 2; ++pass) {
    run("E1 fold, identity order (predictable, same channel)", fold, identity);
    run("E2 fold, deterministic rotation (predictable pattern)", fold, rotate);
    run("E3 fold, random start only (one draw, no shuffle)", fold, random_start);
    run("E4 fold, full shuffle (as the header)", fold, shuffled);
    run("E5 table, identity order", table, identity);
    run("E6 table, deterministic rotation", table, rotate);
    run("E7 table, random start only", table, random_start);
    run("E8 table, full shuffle", table, shuffled);
  }
  bench("reference: shuffle only", [&] { auto o = shuffled(); sink(&o); });
  bench("reference: try_ready (header) + refill", [&] {
    auto cases = std::tuple{receive(a), receive(b), receive(c)}; d::ready_decision dn;
    bool ok = d::try_ready(cases, {}, {}, false, dn); sink(&ok); channels[dn.index]->try_send(7); });
}
