# Retained isolating experiments

Standalone measurements behind decisions recorded in
[../IMPLEMENTATION.md](../IMPLEMENTATION.md). They are not part of the
benchmark series, the Conan package or the test suite; each file states its
build command and the retained result.

- `dispatch_micro.cpp`: fold dispatch over the heterogeneous case tuple against
  a per-index function table, for identity, rotating, single-draw and fully
  shuffled candidate orders (fourth iteration, item 3; not adopted).
- `lock_micro.cpp`: uncontended `std::mutex` against a bare atomic spin lock
  (fourth iteration; not adopted).

The executor and scheduler rows that motivated the fourth iteration's turn
scheduling are part of [../microbench.cpp](../microbench.cpp).
