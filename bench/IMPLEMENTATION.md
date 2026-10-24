# Implementation comparison and optimization boundary

The comparison inspected the sources actually built by Cargo.lock: Crossbeam
Channel 0.5.17 and Tokio 1.54.1. These are source references, not a claim that
all runtime/channel contracts are equivalent. The C++ changes implement the
following techniques directly; they do not wrap Rust or add another runtime.

## What the references do

[Crossbeam run_select](https://github.com/crossbeam-rs/crossbeam/blob/crossbeam-channel-0.5.17/crossbeam-channel/src/select.rs)
shuffles the candidate handles and first attempts to commit a ready operation.
Only after that fails does it create/use a waiting context, register operations,
block, and unregister losers. Its bounded
[array channel](https://github.com/crossbeam-rs/crossbeam/blob/crossbeam-channel-0.5.17/crossbeam-channel/src/flavors/array.rs)
reserves stamped ring slots through atomics before moving a message; it includes
CAS retries/backoff. Its rendezvous flavor uses a separate packet/waiter protocol.
Crossbeam blocks OS threads. We keep coroutine suspension and do not copy its
blocking waits or readiness/backoff loop into application tasks.

[Tokio select!](https://github.com/tokio-rs/tokio/blob/tokio-1.54.1/tokio/src/macros/select.rs)
stores futures in the enclosing async frame, picks a random first branch, and
polls until one returns Ready. A ready selection does not spawn another task.
[Tokio MPSC recv](https://github.com/tokio-rs/tokio/blob/tokio-1.54.1/tokio/src/sync/mpsc/chan.rs)
tries the queue before registering a waker, then checks again to close the
registration race. It consumes a cooperative task budget so always-ready loops
yield. Its random starting branch followed by cyclic polling is not the same
as uniformly shuffling every case when only a sparse subset is ready. This C++
implementation retains full shuffling and its existing equal-priority contract.
MPSC has one receiving owner; this C++ channel supports concurrent
receivers as well. Our Rust mixed benchmark reserves capacity before sending,
so the comparison does not gain speed by throwing away a losing send's payload.

[Go select](https://go.dev/src/runtime/select.go) uses compiler/runtime support,
random polling order and ordered channel locking, checks readiness before parking
a goroutine, then withdraws losing waiters. Its wait records and stack lifetime
benefit from the language/runtime integration.

These differences do not explain or justify the original 22-microsecond ready
path. Exactly-one commitment, FIFO and lossless receives are shared requirements.
C++ explicitly retains unsent move-only payloads and supports general completion
executors; that machinery must not be built on every already-ready iteration.

## C++ changes

- `use_awaitable` and `as_tuple(use_awaitable)` first probe on the calling
  coroutine's executor, provided it equals the explicitly requested owner.
  The tuple retains owning references to channels. Each randomized candidate is
  attempted under its own channel lock; the unregistered probe cannot be claimed
  by another task and stops at the first commitment. No speculative receives,
  rollback or waiter insertion occurs. An explicitly different owner uses the
  suspended/deferred path instead.
- After 64 calls on a worker, the next coroutine probe first posts/yields to the
  executor. Cancellation/deadline are checked before commitment after that yield.
  This budget is per worker, not Tokio's per-task budget. Its bounded yield is
  tested; strict scheduler fairness is not claimed.
- If the probe cannot complete, normal startup rechecks under all channel locks
  before publishing waiters. Coroutine startup can dispatch onto its operation
  strand, since the coroutine is already suspended. Notification then finalizes
  on that owner; an asynchronous continuation can dispatch on its completion
  executor. A completion from the initial turn is still posted. Generic tokens
  retain their original deferred startup/completion behavior.
- A small context-owned registry, without threads or scheduling, owns suspended
  operations. The original used an infinite steady_timer for ownership even when
  no deadline existed. That initialized the reactor and made ready executor work
  repeatedly enter it. Finite timers are now created only for actual deadlines.
  Registry and channel locks are never nested; references retire outside both.
  The registry mutex is an explicit primitive-internal synchronization boundary,
  not shared application protocol state.
- Up to four suspended cases use inline storage for channel/order/lock arrays;
  larger selections retain dynamic storage. Acquired peer references have four
  inline retirement slots plus overflow storage. A finalized operation does not
  reaccess channel pointers after handing channel ownership to its completion.

The original header remains unchanged under `reference/` and the immutable tag
`kth-csp-performance-baseline`. Every build produces both C++ engines. Ready and
mixed probes still use the same default randomized arbitration; no biased mode
or refusal to suspend is hidden in the optimized benchmark.

## Evidence and remaining costs

`performance_control.py` compiles the same public ready loop and pending receive
against both headers. The original loop delivers all 256 messages but needs 514
executor handlers; the current path needs fewer than 20 while allowing queued
work to run. The original channel-only wait creates a reactor; the current wait
does not. Both baselines fail the intended assertion and both current controls
pass. These are mechanism regressions, not unreliable wall-clock assertions.

The original macOS CPU sample placed 1,573/1,655 main-thread samples in `kevent`.
This identified the scheduler/reactor path, not an upstream Asio contract defect.
The changes avoid unnecessary work in this extension; existing upstream headers
and scheduler behavior remain unchanged.

The ready path still constructs an Asio awaitable frame, takes channel owning
references, randomizes arbitration and locks a candidate channel. The suspended
path still allocates an operation/strand and wait records, touches the context
registry, and schedules a wakeup. Crossbeam's ring and Tokio's single-consumer
queue have different costs. Performance parity is not an established guarantee;
retain the raw observations and compare each configuration rather than selecting
only a favorable result.

## Case-handle reuse experiment

The separately named `asio-reuse` engine uses the same current header and
operation semantics. It transfers owning cases out of `result.cases` into the
next `make_select`, clears consumed receive optionals, and replenishes a selected
send. No channel ownership is borrowed or dropped. It measures a potential
optimization without changing the ordinary API benchmark. On the first paired
Mac ready experiment it produced no material improvement, so repeated handle
construction is not established as the dominant remaining cost. This negative
result is retained rather than reporting only a promising hypothesis.

## GCC coroutine lifetime finding during Linux sanitization

The additional GCC 16.1/Linux `-O1 -fsanitize=address,undefined` run reported
592 leaked bytes in the original `awaitable_path` scenario. The same 592-byte
report reproduced against the frozen original C++ header, so it is not attributed
to the ready-path optimization. A two-value example using ordinary Asio showed
the first directly destructured awaited tuple retaining ownership.

The retained `csp/tests/coroutine_tuple_lifetime.cpp` further reproduces ownership
retention with only standard C++20 coroutines, `std::tuple` and `std::shared_ptr`:
no Asio, channel, strand or executor appears in it. The measured GCC 16.1
configurations at `-O1`/`-O2` retain the first owner; GCC `-O0` and the measured
Linux Clang 21.1.8 do not. These observations are evidence for this toolchain
configuration, not a statement about every GCC release/platform.

The alternate path names each awaited tuple and binds references to its fields.
It uses natural scope destruction and the exact same ownership observations;
there is no manual reset, leak suppression, or weakened postcondition. The full
Asio coroutine test uses this storage pattern and additionally checks weak channel
probes after the coroutine finishes. The benchmark's bindings already end at each
loop iteration, so they do not survive a later suspension in the same scope.

Run `CXX=g++ python3 csp/tests/coroutine_tuple_control.py /tmp/tuple-control`
to characterize the direct path and verify the named path. The script retains
compiler version and both outputs. The original LeakSanitizer report and
unchanged-header reproduction are preserved in the local evidence archive;
they are not relabeled as successful sanitizer runs.

## Second iteration: arbitration and optional cancellation

Crossbeam's [shuffle implementation](https://github.com/crossbeam-rs/crossbeam/blob/crossbeam-channel-0.5.17/crossbeam-channel/src/utils.rs)
uses a small per-thread Xorshift generator and multiply-high range reduction.
The second C++ iteration uses per-worker Xorshift64* in place of the default
Mersenne Twister. It retains `std::shuffle` and its unbiased range reduction,
full permutations, random per-worker initialization, and the original
`std::mt19937` path when an explicit reproducibility seed is supplied. It does
not adopt Tokio's random-start cyclic scan or introduce biased branch priority.
The generator is for arbitration, not cryptographic use.

Suspended startup also skips constructing a type-erased stop callback when
`stop.stop_possible()` is false. Such a token can never receive a stop request;
Asio cancellation slots and every stoppable token retain their existing path.
The channel ring, ownership, locks, registration, wakeups and completion-executor
semantics remain the same. These are specific costs removed from the selector,
not a translation of Crossbeam's entire concurrent queue or Tokio's runtime.

The previous optimized header is frozen under `reference-v1/`. Both its ordinary
and owning-case reuse engines remain runnable alongside the original and current
versions. Paired observations are retained separately from the preceding series.

## Third iteration: in-frame commitment and continuation wakeups

### Where the second iteration's ready path spent its time

Source reading of the second iteration (now frozen under `reference-v2/`): its
`use_awaitable` paths were coroutines. Every ready selection allocated an
awaitable frame (recycled through Asio's per-thread cache), suspended the
caller, resumed the nested frame through the awaitable pump, probed, returned
through `final_suspend` and a second resume, and moved the result through the
frame's result storage and out again. A diagnostic synchronous probe in the
caller's frame (`try_wait`, outside the repository) measured about 34 ns on the
Mac ready loop against about 57 ns for the second iteration: the frame and its
two pump round trips were roughly 23 ns. That diagnostic skipped the owner
affinity check and the executor transport, so it is a lower bound, not a
product.

Two prototypes were retained as negative results. A `deferred` token whose
initiation probed inside the initiation (that is, after the coroutine had
suspended) measured about 90 ns: each ready completion re-entered the coroutine
from inside its own `after_suspend` callback, nesting pumps up to the yield
budget. A first hook prototype with an `await_ready` probe was instrumented and
did engage on 98.4% of selections (the other 1/64 are budget yields), yet
measured 51 to 59 ns: its suspended start was the posted generic turn, and its
ready path still carried the extra copies described below.

### Changes

- `asio/impl/awaitable.hpp` gains `awaitable_async_op_immediate<Op>`.
  `awaitable_async_op::await_ready` consults it; the primary template returns
  false, so every existing awaited operation initiates after suspension exactly
  as before. `awaitable_frame_base::executor()` exposes the resuming thread's
  executor by reference. This is the only ordinary Asio component changed; the
  frozen engines compile against the unmodified upstream file under
  `reference-upstream/`.
- `channel_select_operation<Tuple, Cases...>` is the lazy operation returned
  for `asio::deferred`, `as_tuple(asio::deferred)` and the partial
  `asio::as_tuple` token. Awaited from an `asio::awaitable` coroutine on the
  owner executor, its `await_ready` runs the same single-channel-at-a-time
  probe as before, in the awaiting frame, and on commitment stores the
  completion in the operation and hands the awaiter pointers to it. Nothing is
  initiated. When the probe may not run (different executor), the per-worker
  budget is exhausted, or nothing is ready, the coroutine suspends and the
  owned operation starts exactly as the second iteration's suspended path did
  (inline owner start, dispatched continuation). A budget yield suspends, posts
  one turn so queued work runs, probes again on the executor and only then
  registers. Invoked with any other completion token, the operation keeps the
  posted start and queued completion that generic tokens always had. The
  `use_awaitable` tokens keep returning `awaitable<T>`: their frame probes with
  the same static function on its own locals and awaits the lazy operation
  only to suspend, which removes the second initiation coroutine frame the
  previous suspended path created.
- Fewer owning moves per selection: `channel_selection` forwards the cases
  into its tuple, the operation and `select_op` take rvalue tuples, and the
  lazy operation's completion tuple is its only case storage, so a committed
  probe sets an error and an index in place and moves nothing
  (`channel_select_detail::committed` builds a result inside the tuple with
  one move at construction). Six moves of the case tuple per ready selection
  became three. Measured in isolation each move is about 5 ns, but removing
  them did not change the ready loop: moves are independent work that the
  core overlaps with the probe's serialized atomics (see the floors below).
- A committed peer's wakeup and a queued completion use `asio::defer` instead
  of `asio::post`. Asio's scheduler treats a continuation from a thread that
  runs that scheduler as a private-queue push (`scheduler.ipp`,
  `post_immediate_completion` with `is_continuation`): no scheduler mutex, no
  condition-variable signal, no migration to another worker. From other
  threads or contexts the call degrades to an ordinary post. Deferring only
  the wakeup changed an observable single-thread order: a peer claimed during
  a start turn was finalized after the committing operation's posted
  completion, so that completion could observe the peer's not yet withdrawn
  registration (`csp/tests/select.cpp`, rendezvous control). Deferring the
  completion as well keeps both in commit order on the thread's private queue,
  which is the order posted wakeups gave; cancellation ingress and the
  cooperative yield remain posts.
- The per-operation `asio::strand` is replaced by a serial turn runner: one
  atomic word in the operation records requested turns (first start, cancel,
  timer resume, finalize) and whether a runner is scheduled or running. At most
  one runner exists per operation; a request while it runs only sets a bit,
  and the runner drains all bits before it exits. A queued runner is one
  `asio::defer` on the owner executor. The retained microbenchmark that
  motivated it: a strand turn (enqueue under the strand mutex, an invoker
  operation, the scheduler turn, the strand's exit bookkeeping) costs about
  106 ns on the Mac and 91 ns on the Linux host, against 33 and 26 ns for a
  plain executor turn, and `make_strand` alone 26 and 19 ns per operation
  (table below). The serialization guarantee is the same as the strand's; the
  first start of a coroutine-initiated operation still runs inline on the
  owner and a generic initiation's still is posted.
- No heap allocation per suspended operation apart from the operation itself,
  which now comes from Asio's per-thread recycling allocator (its block is
  below the recycler's limit): wait registrations are intrusive nodes stored
  in the operation beside its cases instead of `std::list` nodes, and the
  lifetime registry is an intrusive list of self-owning operations instead of
  an `unordered_map`. A linked node implies a live operation, because the
  owner unlinks its nodes under the channel mutex before destruction; claiming
  still acquires a strong reference through the node's weak reference before
  the claim and retires it after unlocking, as before. The lifetime control's
  observer now fires when an unlink relinks a peer's neighbouring node, which
  keeps that control's scenario and its RED/GREEN meaning unchanged.

### Measured and rejected: multiply-high shuffle

Crossbeam and Tokio reduce a 32-bit draw with a multiply-high. In isolation on
the Mac, `std::shuffle` of three indices with the per-worker generator cost
10.3 ns and a multiply-high Fisher-Yates 3.6 ns; with libstdc++ on the Linux
host the two were 3.1 and 4.0 ns. In situ, `try_ready` plus refill on three
ready channels did not change on the Mac (29.1 vs 29.1 ns, both headers) and
changed by 1.6 ns on Linux (28.9 vs 30.5 ns). The 9 to 10 ns that separate the
unbiased probe from a biased one on both hosts are therefore the randomly
chosen candidate itself (a data-dependent branch and a different channel each
time), not the reduction arithmetic. `std::shuffle` and its unbiased range
reduction are retained; the only change is the shared `shuffle_order` helper.

### Controls

`csp/tests/immediate_path.cpp` awaits 256 ready selections through
`as_tuple(asio::deferred)` with a queued task and counts executor turns and
global `operator new` calls. Against the frozen second iteration with the
upstream awaitable implementation, that token is the generic deferred path:
514 executor turns and 774 heap allocations on the Mac. Against the current
headers: 6 turns and 2 allocations on the Mac, the two being the first
cooperative yield's executor blocks (later yields reuse the recycled blocks),
and 6 turns and 0 allocations on the Linux host, whose recycler allocates
through `std::aligned_alloc`. `performance_control.py`
asserts both outcomes; `mutation_control.py` checks that the losing-consumption
mutation of the probe is rejected through this path as well as through
`ready_path.cpp`. The existing suspension, cancellation, affinity, lifetime and
teardown controls run with both token families (`awaitable_path.cpp`), and the
lazy operation's laziness and generic-token invocation are checked there.

`csp/bench/microbench.cpp` isolates the component costs; its outputs are
retained as `microbench.txt` with the observations of each host (isolated
loops on one thread; in situ these overlap, so they bound rather than add up
to the benchmark figures):

| Component | Mac, ns | Linux, ns |
|---|---:|---:|
| `std::shuffle` of 3 with the per-worker generator | 11.2 | 3.8 |
| Fisher-Yates of 3 with 32-bit multiply-high (rejected) | 3.3 | 4.8 |
| `retired_operations` construct+destroy | 1.6 | 2.8 |
| `std::mutex` lock+unlock | 3.2 | 3.0 |
| `any_io_executor` copy+destroy | 1.2 | 2.3 |
| `any_io_executor` equality | 1.7 | 3.7 |
| `receive(channel)` construct+destroy | 2.7 | 3.9 |
| three-case tuple construct+destroy | 5.6 | 9.0 |
| three-case tuple move | 5.6 | 9.1 |
| completion emplace (one move) + move out | 9.8 | 12.3 |
| `ready_budget_exhausted()` | 1.3 | 1.2 |
| `try_ready` (3 ready) + refill | 29.6 | 40.2 |
| `try_ready` (3 ready, biased) + refill | 17.6 | 24.4 |
| `try_receive` + `try_send` (one channel) | 11.6 | 13.5 |
| floor: 3 owning handles + random channel pop/push | 10.1 | 12.3 |
| floor: one executor turn (post + run_one) | 32.9 | 25.8 |
| floor: one continuation turn (defer + run_one) | 32.1 | 34.0 |
| strand: `make_strand` construct+destroy | 26.1 | 18.6 |
| strand: one strand turn (post + run) | 106.2 | 90.7 |
| floor: recycled owned operation construct+destroy | 56.3 | 51.6 |
| floor: register + withdraw one case under its mutex (with the operation) | 66.3 | 62.8 |

### Floors, the remaining gap and what accounts for it

The acceptance target is at most 1.05 times the applicable Rust reference.
`csp/bench/microbench.cpp` measures two minimal floors on each host: the work
the contract itself requires of a ready selection (take three owning handles,
inspect one randomly chosen channel's mutex-protected FIFO state, give the
slot back) and the building blocks of a suspended handoff (one executor turn,
one recycled owned operation, one registration and withdrawal under the
channel mutex). The retained outputs are `microbench.txt` in each
observations directory.

The ready floor is about 10 ns on the Mac and 12 ns on Linux, below Tokio's
and Crossbeam's whole ready iteration, so the contract's mutex-protected FIFO
state and owning handles are not what keeps this path at 1.1 to 2.0 times the
Rust figures. The rest is the selection machinery: dispatching on a randomly
chosen case through the case tuple mispredicts (the probe costs 12 to 16 ns
more unbiased than biased, and the floor loop, which indexes an array
instead, shows no such penalty), the owning result is transported by value
through the awaiter, and the probe and refill logic around the ring is
generic. Tokio's
`select!` polls borrowed futures stored once in the task frame and transports
no owning result; Crossbeam borrows handles and reserves ring slots without
locks. Closing the remaining factor would need borrowed cases or a different
result transport, which the owning-lifetime contract excludes, or a
specialized dispatch; none is claimed here.

On the suspended path one executor turn (post or defer, then run) costs about
33 ns on the Mac and 26 to 34 ns on the Linux host, a recycled owned operation
about 56 and 52 ns, and a registration plus withdrawal about 10 ns more. A
handoff needs at least one such turn to resume the waiter without nesting
coroutine resumptions inside the committing call (which may be a user's
`try_send`), plus an owned operation that outlives the committing call, so the
floor of this design is on the order of 100 ns per suspended handoff on both
hosts, against Tokio's 71 ns (Mac) and 147 ns (Linux) for a whole capacity-one
fan-in message. Tokio resumes through a task waker that is the task's own allocation,
reused across awaits, and schedules into a worker-local LIFO slot. Reaching
the target there would require the awaiting coroutine to own a reusable
registration and waker across selections and a scheduler slot that Asio's
executors do not provide; that is a redesign of the operation lifecycle, not
an iteration of this one, and it is not claimed here. (The fourth iteration
below is that redesign.)

## Fourth iteration: task-owned reusable selector, scheduler-linked turns, readiness hints

### Where the third iteration's suspended path spent its time

Profiling the capacity-one fan-in loop on the Mac (`sample`, top-of-stack
histograms of the `asio-reusable` build after change 1 and after change 3
below, retained as `profile-fanin-1-1-after-change-*.txt` in
`observations/macos-v4/`) and isolating the candidates in microbenchmarks
(`csp/bench/microbench.cpp`, rows added in this iteration) gave the following
picture of one suspended wait:

- `std::shuffle` of the case order was the single largest self-time item (10%),
  drawn twice per suspended wait: once by the probe and again by the start
  turn, each through a thread-local generator.
- Every executor turn went through `any_io_executor`: a continuation turn
  (defer + run_one) costs 56 to 60 ns through it against 32 ns handed to the
  plain `io_context` executor and 20.7 ns as a preallocated scheduler
  operation; in situ, inside one `run()`, a typed defer of a small lambda
  costs 10.4 ns per turn and a re-queued preallocated operation 6.8 ns. Inline
  dispatch costs 5.4 ns through `any_io_executor` and 1.7 ns typed.
- Mutex pairs were 14 to 15% of self time: the probe's per-candidate locks,
  the start turn's lock of every participating channel, finalization's lock
  of every channel again (also for nodes a claiming peer had already
  unlinked), and the lifetime registry's lock twice per suspended wait.
- Claiming a waiter promoted the node's weak reference (`weak_ptr::lock`,
  about 4.4 ns), kept the strong reference in the retirement collection, and
  paid for it again at destruction; registering stored a weak reference.
- `std::error_code` was constructed or cleared about five times per message
  (each is a call to `system_category()`), and the awaiting coroutine's
  cancellation slot was assigned and cleared once per suspended wait (13.7
  ns, inherent to Asio's per-await slot discipline).
- The one-shot owned operation itself: 70 ns to construct and destroy on the
  Mac (recycled allocation, executor copy, work guard, case tuple moves,
  channel set), per suspended selection.

### Changes, each measured in isolation and in the quick loop

The quick loop is `csp/bench/select.cpp` built like the series, 100,000
iterations, three repeats, medians, on the Mac; the paired seven-repeat series
on both hosts is in [README.md](README.md). The frozen third iteration is
`asio-v3` (173 ns on capacity-one fan-in with one worker, 42.3 ns ready).

1. Task-owned reusable selector (`channel_selector`, `make_selector`). The
   selector owns one `reusable_state`: the case tuple, one intrusive wait
   node per case, the channel set, the arbitration word, the turn runner, the
   timer, the registry link and a two-word in-place slot for the stored
   completion. The awaiting coroutine's handler
   (`awaitable_async_op_handler`, the detached coroutine thread and a result
   pointer) is stored in that slot without allocation for any executor type;
   any other completion handler is type-erased on the heap with the executor
   work it needs. Each `wait()` is a lazy operation like the third
   iteration's: a ready wait commits in the awaiting frame through the same
   `awaitable_async_op_immediate` hook and resumes from the selector's
   decision storage; a suspended wait arms the next generation. The result is
   the compact `(error_code, index)`; values stay in the selector. Quick loop
   after this step alone: capacity-one fan-in 173 to 125 ns, ready 42 to 34
   ns.
2. Executor fast path. Turns and completions submitted through an
   `any_io_executor` whose target is the plain `io_context` executor are
   handed to that executor (`submit_fast`), later replaced for turns by the
   operation being its own scheduler operation (change 8). The arming task's
   probe draws the permutation into the state's own order, so the start that
   follows an unsuccessful probe does not draw again. Capacity-one fan-in 125
   to 111 ns.
3. Lock-free readiness hints. The buffered count, the two registration counts
   and the closed flag of a channel are relaxed atomics modified only under
   the channel mutex; a probe reads them before taking a candidate's mutex
   and passes over a case that cannot be ready. A stale hint only costs a
   mutex that finds nothing or a trip through the suspended path, which
   decides under every participating mutex; correctness never depends on a
   hint. Per-operation generator with exactly uniform Fisher-Yates draws
   (multiply-high with Lemire's rejection, so no bias and no division),
   seeded once from the per-worker generator: 2.9 ns for three cases against
   11.0 ns for `std::shuffle` with the thread-local engine, and no
   thread-local access per draw. `std::error_code` is constructed once per
   scan (channel operations write an error only when the ready case carries
   one) and copied from a cleared constant otherwise. Capacity-one fan-in 111
   to 94 ns, mixed 33 to 26 ns.
4. Claims through the node pointer. A linked node belongs to a live operation
   that is strongly owned from registration until withdrawal (its runner,
   then the registry, which is resolved at construction so that keeping a
   registration cannot throw), so a peer claims and wakes it through the
   node's pointer. The weak reference per node, its promotion per claim and
   the retirement collection are gone. Capacity-one fan-in 94 to 87 ns.
5. Withdrawal after commitment, first attempted selectively and then
   reverted. The first form withdrew each node still linked under its own
   channel mutex, reading the node's list membership as a relaxed hint and
   taking no mutex for a node the claiming peer had already unlinked
   (capacity-one fan-in 87 to 84 ns in the quick loop). That form is a
   use-after-free: a peer's `take()` unlinks a node under the channel mutex
   and still has to dereference the owning operation to claim it; the owner's
   finalization, finding the node already unlinked, returned without that
   mutex, so it did not serialize with the peer, finished, and was destroyed
   while the peer was about to claim it (a rare SIGSEGV in the four-worker
   rendezvous fan-in; AddressSanitizer heap-use-after-free in
   `channel_state::take`; ThreadSanitizer claim-versus-constructor through the
   recycling allocator's reuse of the storage). The adopted form withdraws
   under every participating channel mutex again, as the third iteration did:
   the owner cannot finish while a peer holds one of its nodes under that
   channel's mutex, which is the property that lets `take()` claim through a
   linked node's raw pointer at all. A deterministic regression
   (`csp/tests/finalize_withdraw_race.cpp` in the library) reproduces the
   interleaving, RED on the former header and GREEN on the adopted one, and
   the former header is retained as the opt-in `asio-v4-unsafe*` engines,
   excluded from the default series. The all-channel lock order is thus used
   for the scan-and-register start, timer resumption, finalization and
   teardown alike. The awaiting coroutine's slot handler refers to the state
   directly (Asio clears the slot when the coroutine resumes through the
   stored completion; the generic path keeps a weak reference), and a
   completion known to run on the owner is handed to the typed executor.
6. Persistent registry registration. A selector's state is kept by the
   execution context's registry from its first registration until the
   selector's destructor requests a release turn on the owner, serialized
   with any wait in progress by the same runner, or until shutdown; later
   generations touch the registry lock not at all. The release turn is the
   only new runner turn.
7. The operation is its own scheduler operation. `operation` derives from
   `asio::detail::scheduler_operation`; when the owner is the plain
   `io_context` executor, a turn links the operation into that scheduler's
   queue (`post_immediate_completion`, with the continuation flag of
   `asio::defer`, or inline when `dispatch` would run inline), with no
   function object and no allocation; the operation holds a self-reference
   while queued or running, and the scheduler's shutdown path drops it. Other
   executors keep the generic submission. Changes 6 and 7 together:
   capacity-one fan-in 84 to 74 ns, four-worker capacity-one 369 to 280 ns
   and four-worker capacity-zero 535 to 307 ns, the multi-worker gains coming
   from the registry lock and the type-erased function no longer being shared
   points of contention.
8. Memory orders of the turn runner were tightened and documented: the
   runner's exchange acquires, its release store publishes the turn's writes
   to the next runner, and generation marks are read relaxed inside a turn
   because every request writes its mark before the acquire-release
   `fetch_or` that requests the turn.

Generation isolation: every operation serves generations (one-shot: one,
reusable: one per wait). Cancellation, timer and wakeup requests carry the
generation they were raised for in monotonic atomic marks (`raise`), checked
at ingress and again in the runner; `reusable_path.cpp` injects stale requests
of each kind between waits and while the next generation is registered behind
a second waiter, and `mutation_control.py` removes each filter.

### Measured and rejected

- Specialized case dispatch (item 3 of the plan). Isolating experiment
  (`experiments/dispatch_micro.cpp`, measured against the third-iteration
  header): dispatching a ready attempt through the fold over the
  heterogeneous tuple against a per-index function table, for an identity
  order, a predictable rotation over different channels, a single random
  draw and a full shuffle. Identity order 17.5 to 19.8 ns (fold) against
  14.7 ns (table); a predictable rotation 15.5 against 14.6; a single random
  draw 19.7 against 20.0; a full shuffle 23.9 against 23.3. With a random
  order the table saves nothing: the cost is the randomly chosen channel
  (its line and its branch history), not the way the index selects the case.
  Not adopted; the unbiased full-permutation arbitration stays.
- A spin lock instead of `std::mutex` for the channel
  (`experiments/lock_micro.cpp`): uncontended lock+unlock 4.1 ns against 3.6
  ns on the Mac, and two pairs (a probe and a `try_send`) 6.6 against 7.3 ns.
  Apple's mutex fast path is already a compare-and-swap; nothing to gain, and
  a spin lock would misbehave under contention. Not adopted.
- Multiply-high draws without rejection (the Crossbeam/Tokio reduction) are
  biased by about `bound / 2^32` per draw; the adopted reduction keeps the
  multiply-high and adds Lemire's rejection branch, which is taken with
  probability below that bias, so the permutation is exactly uniform at the
  same cost (2.9 against 3.2 ns).

### Controls

`csp/tests/reusable_path.cpp` runs 256 rounds of an unbuffered
producer/consumer pair through the one-shot API and through two selectors,
counting owned operation constructions (through the
`ASIO_CHANNEL_SELECT_TEST_OBSERVE_OPERATION` hook) and global `operator new`
calls from the second round on. The one-shot loop constructs 254 operations in
those rounds; the selector loop constructs none and allocates nothing.
`performance_control.py` builds the same source with `-DONE_SHOT_ONLY` against
the frozen third-iteration header with that hook inserted into its operation
constructor (test-only, no behavioral change) and requires the RED outcome,
then the current header and requires the GREEN one. The same binary checks
generation isolation (stale cancellation, timer and wakeup requests between
and during waits, with FIFO against a second waiter), simultaneous-use
rejection, executor work while suspended, teardown with a suspended wait,
release after the context stopped, payload and receive-slot ownership, case
and option changes between waits, stop-token cancellation and four-worker
cross-thread wakeups. `mutation_control.py` removes the cancel, resume and
wakeup generation filters in turn; each mutant is rejected by that binary
(an aborted third wait, a FIFO violation, and a completion with no case).

A first version of this control hung under ThreadSanitizer: its own
`std::vector` of observed operations was pushed from several threads in the
cross-thread scenario. The observers are synchronized now; the library paths
ran clean under ThreadSanitizer before and after (`v4-sanitizers` logs on both
hosts, including every benchmark variant with four workers).

### Floors and the remaining gap

The component table of this iteration (`microbench.txt` in
`observations/macos-v4/` and `observations/linux-v4/`):

| Component | Mac, ns | Linux, ns |
|---|---:|---:|
| `std::shuffle` of 3 with the per-worker generator (third iteration) | 11.0 | 3.7 |
| Fisher-Yates of 3, exact draws, per-operation generator (adopted) | 2.9 | 3.1 |
| `std::mutex` lock+unlock | 3.2 | 3.1 |
| `try_ready` (3 ready) + refill | 22.3 (29.6 before) | 33.1 (40.2 before) |
| reusable state: ready probe (3 ready) + refill | 19.8 | 21.6 |
| `try_receive` + `try_send` (one channel) | 9.0 | 10.9 |
| floor: 3 owning handles + random channel pop/push | 10.5 | 12.5 |
| continuation turn via `any_io_executor` (defer + run_one) | 56.1 | 45.3 |
| continuation turn via the `io_context` executor | 32.1 | 33.0 |
| continuation turn, preallocated scheduler operation | 20.7 | 23.4 |
| in situ: typed defer of a small lambda per turn | 10.4 | 10.8 |
| in situ: preallocated operation re-queued per turn | 6.8 | 7.1 |
| in situ: inline dispatch via `any_io_executor` / typed | 5.4 / 1.7 | 6.4 / 0.4 |
| cancellation slot assign + clear (16-byte handler) | 13.7 | 3.4 |
| floor: recycled one-shot operation construct+destroy | 70.1 | 81.5 |
| reusable state: register + withdraw one case under its mutex | 9.6 | 8.7 |

A suspended handoff through a selector now costs: the probe that found
nothing (hints, so no mutex on an empty channel), one start turn (all
participating mutexes once, registration), one scheduler turn for the wakeup
(about 7 ns in situ), the withdrawal of the remaining nodes under all
participating mutexes once more (see change 5: the per-node form was a
use-after-free and was reverted), the stored completion handed to the typed
executor inline, and the coroutine's resumption with Asio's per-await slot
assignment. That is the
reusable registration and waker the previous section asked for; what Asio's
scheduler does not provide is a worker-local LIFO slot, and the four-worker
scenarios still pay the scheduler mutex per turn (`do_run_one` locks the
scheduler mutex to pop each operation, and `wake_one_thread_and_unlock`
signals a condition variable when more work is queued). The paired series in
[README.md](README.md) states the remaining ratio per scenario and host. On
Linux the selector is below Tokio on every scenario Tokio runs and meets the
target against the best applicable reference on four of the seven scenarios
that have one; on the Mac the single-worker suspended scenarios sit at 1.06
of Tokio and the ready loop at 1.15 to 1.17, where the remainder is the
awaiting machinery around a 10 ns floor (the `co_await` of an async
operation, the owner comparison, the cooperative budget, the probe's fold and
the result tuple) and no single remaining item exceeds 2 ns. The buffered
four-worker fan-ins miss it on both hosts (Linux 1.35 of Tokio on capacity 64
and 2.54 of Crossbeam on capacity one, which blocks four threads on a
lock-free ring).

Minimal falsifiable experiments for the remaining obstacles: for the
multi-worker gap, count scheduler mutex acquisitions and futex calls per
message with four workers (the `strace` logs in `observations/linux-v4/` give
the futex side) and prototype a per-thread run queue with stealing in
`asio::detail::scheduler` under an `ASIO_` macro, measuring the same scenarios;
for the ready loop, a build with `ASIO_RECYCLING_ALLOCATOR_CACHE_SIZE` raised
(so no cancellation-slot handler is ever malloc'd) and a build that compares
the owner through the typed executor bound the two remaining candidates; each
is a one-line change to measure, not a redesign.
