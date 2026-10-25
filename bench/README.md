# Cross-language select benchmark

This harness compares the fork's public coroutine API with Go's built-in
`select`, Rust Crossbeam's `select!`, and Tokio's `select!` over bounded MPSC
channels. All payloads are unsigned 64-bit integers. Each selector has three
branches and uses the implementation's default randomized arbitration.

This is a throughput benchmark, not a proof of semantic equivalence or fairness.
A reported nanoseconds/message figure is elapsed batch time divided by delivered
messages; it is not an individual message's latency or a p99 measurement.

## Scenarios

- `ready`: three capacity-one channels each contain a message. Receive from one
  selected channel and immediately refill that same channel. All three branches
  are ready on every iteration. Check the received value and the final three
  buffered messages.
- `mixed`: receive from the first channel, send to the second, or receive from
  the third. Immediately refill a winning receive or drain a winning send.
  All branches are ready. The final buffers must contain exactly two messages.
  Tokio uses `reserve()` and sends only after winning, preserving ownership when
  the branch loses.
- `fanin`: three producers each send `n` sequential values on separate bounded
  channels; one consumer receives `3*n` values through selection. Every received
  value must equal the next sequence number for its channel. Join all producers
  and verify every channel has delivered exactly `n` messages and is empty.
  Capacities are 0 (rendezvous), 1, and 64. Asio additionally checks that no
  registrations remain after completion.

Go, Asio and Tokio run with one or four execution workers. Crossbeam uses four
OS threads (three producers plus the consumer) for fan-in; its blocking sends
cannot run with this topology on one worker. Tokio bounded MPSC requires capacity
at least one, so it has no capacity-zero result. Crossbeam's ready/mixed cases
use only the calling thread. The async runtimes and their ancillary threads are
not identical implementations.

Asio uses one `make_select(send(...))` operation for each producer send, which is
its current public async sending interface. Go and Rust use their ordinary send
operations. Asio's channel synchronization, executor dispatch, operation
allocation and cancellation machinery are included; checks and immediate
refills/drains are included in every implementation. This compares usable APIs,
not isolated queue instructions.

## Reproduce

The benchmark retains fifteen engines: `asio-baseline` (frozen original C++),
`asio-v1` and `asio-v1-reuse` (first optimized version, frozen at
`6c107b9dc076532aaeaa5cdd74991afff93ded6a`), `asio-v2` and `asio-v2-reuse`
(second optimized version, frozen at `3f9a9e5708e5c540f9a613fc9ac7b17d857c939b`),
`asio-v3`, `asio-v3-reuse` and `asio-v3-awaitable` (third optimized version,
frozen with the awaitable implementation it was measured with), `asio`,
`asio-reuse`, `asio-reusable` and `asio-awaitable` (the current iteration),
`go`, `crossbeam`, and `tokio`. Reuse variants transfer owning case handles
between iterations; `asio-reusable` runs each task's loop through one
task-owned `channel_selector`. The snapshots and hashes are documented in
[reference/README.md](reference/README.md),
[reference-v1/README.md](reference-v1/README.md),
[reference-v2/README.md](reference-v2/README.md),
[reference-v3/README.md](reference-v3/README.md) and, for the unmodified
upstream `asio/impl/awaitable.hpp` that the engines before the third iteration
compile against, [reference-upstream/README.md](reference-upstream/README.md).
All C++ engines compile the same benchmark source and optimization flags; only
the header overlays and three explicit macros differ: `ASIO_BENCH_REUSE_CASES`
for the reuse variants, `ASIO_BENCH_REUSABLE_SELECTOR` for the reusable
selector, and `ASIO_BENCH_AWAITABLE_TOKEN`, which selects the
`as_tuple(use_awaitable)` coroutine token. The engines frozen before the third
iteration are built with that token, the one their versions documented;
`asio-v3`, `asio` and the reuse engines use the `as_tuple(asio::deferred)` lazy
operation, and `asio-v3-awaitable` and `asio-awaitable` measure their headers
with the old token so the token effect is visible on otherwise identical code.

Use a release C++20 compiler, Python 3, Go, and Cargo/Rust. `Cargo.lock` pins all
Rust packages. Nothing is added to the normal Asio build or Conan package tests.
From the repository root (use `g++` on Linux or `clang++` on macOS):

```sh
export PATH="$HOME/.cargo/bin:$PATH"
python3 bench/build.py --asio-root /path/to/asio --cxx c++ --go /path/to/go
python3 bench/run.py --asio-root /path/to/asio --n 30000 --repeats 7
```

`build.py` records compiler/runtime versions, build commands, and input source
hashes. No dependencies are fetched from mutable branches; Cargo downloads its
locked registry versions. The script requires an existing Go toolchain and does
not install one globally. `run.py` rejects binaries whose recorded input sources
have changed. Use `--engines asio-v3,asio,asio-reusable` for the latest paired C++ comparison,
`--bin-dir /path/to/build` to select build output, and `--out /path/to/results`
to preserve distinct machines or revisions. On Linux, optional `taskset -c 0-3
python3 bench/run.py --asio-root /path/to/asio ...` constrains the runner and inherited workers alike;
recorded metadata includes the actual affinity.

The initial Go toolchain was downloaded from the official Go distribution,
verified against the SHA256 from its release JSON, and extracted under `/tmp`.
It did not replace a global toolchain.

The runner launches one benchmark process at a time, shuffles trials with a
fixed orchestration seed, and retains all observations in `results/raw.json`.
It runs one separate discarded warmup process per configuration to warm system
caches; runtime initialization within each measured process is not warmed by
that process. Runtime/channel/task setup and OS-thread creation are outside the
internal timer. Timed fan-in includes releasing a start gate, executing the
work, and joining the producers/workers. The ready/mixed cases include their
loops and executor driving. Process startup, compilation and printing results
are outside the timer. Threads and producers are joined before inspecting
observations. Each child has a 120-second timeout; an invariant failure or timeout
fails the run rather than contributing a successful sample.

`summary.json` and `table.md` contain median, minimum and maximum across trials.
`metadata.json` records the library commit/tree, source and binary hashes,
compiler/runtime versions, machine and parameters. These are local observations
on one machine without CPU affinity, a fixed frequency, or a dedicated idle host;
repeat on Linux and deployment hardware before extrapolating. No allocation,
CPU-time, memory or tail-latency profile is claimed by these figures.

References: [Go selection](https://go.dev/ref/spec#Select_statements),
[Crossbeam selection](https://docs.rs/crossbeam-channel/0.5.17/crossbeam_channel/macro.select.html),
[Tokio selection](https://docs.rs/tokio/1.54.1/tokio/macro.select.html), and
[Tokio bounded-channel capacity](https://docs.rs/tokio/1.54.1/tokio/sync/mpsc/fn.channel.html).

## Initial local results

Measured library commit: `035b2c7850e26f8d8ecd826899b76ae9bc9db9ae`
(tree `81928be3764bd7f7139911bf1e55b25fb4a7add5`), with the benchmark
sources recorded separately by SHA256 in the results metadata. Apple M6,
macOS 27.0.1 arm64, Apple Clang 21.0.0 (`-O3 -DNDEBUG`), Go 1.27.3,
Rust 1.99.0, Crossbeam Channel 0.5.17 and Tokio 1.54.1. Seven trials per
configuration, 30,000 selections for ready/mixed and 90,000 deliveries for fan-in.

This frozen original implementation is substantially slower in every measured configuration.
For example, the ready path is about 563 times slower than Go and 1,055 times
slower than Tokio. These results do not satisfy a performance-parity objective.
They are a baseline for investigating and changing the implementation, not an
acceptance result. No primitive code was changed during these initial measurements. The table uses
`asio` for that original run; new runs identify this version as `asio-baseline`.

| Engine | Scenario | Capacity | Workers | Median ns/message | Min–max |
|---|---|---:|---:|---:|---:|
| asio | ready | 1 | 1 | 22351.4 | 22047.4–23430.4 |
| asio | mixed | 1 | 1 | 22473.4 | 22084.5–22870.8 |
| asio | fanin | 0 | 1 | 22459.1 | 22365.2–24754.7 |
| asio | fanin | 0 | 4 | 5457.5 | 5440.9–5550.3 |
| asio | fanin | 1 | 1 | 22444.2 | 22366.8–23387.3 |
| asio | fanin | 1 | 4 | 4732.3 | 4534.6–4790.0 |
| asio | fanin | 64 | 1 | 22429.5 | 22365.0–25812.2 |
| asio | fanin | 64 | 4 | 4674.0 | 4135.2–4708.2 |
| go | ready | 1 | 1 | 39.7 | 39.4–42.5 |
| go | mixed | 1 | 1 | 39.7 | 39.3–42.9 |
| go | fanin | 0 | 1 | 101.9 | 100.6–104.6 |
| go | fanin | 0 | 4 | 203.1 | 185.9–210.8 |
| go | fanin | 1 | 1 | 85.9 | 81.4–87.3 |
| go | fanin | 1 | 4 | 157.9 | 155.5–161.7 |
| go | fanin | 64 | 1 | 42.9 | 41.7–45.6 |
| go | fanin | 64 | 4 | 115.2 | 98.5–118.8 |
| crossbeam | ready | 1 | 1 | 20.9 | 20.2–24.1 |
| crossbeam | mixed | 1 | 1 | 21.1 | 20.5–21.2 |
| crossbeam | fanin | 0 | 4 | 1377.8 | 1297.9–1401.0 |
| crossbeam | fanin | 1 | 4 | 128.3 | 86.9–429.9 |
| crossbeam | fanin | 64 | 4 | 54.0 | 51.4–66.0 |
| tokio | ready | 1 | 1 | 21.2 | 20.9–24.3 |
| tokio | mixed | 1 | 1 | 22.5 | 22.0–23.7 |
| tokio | fanin | 1 | 1 | 70.5 | 69.1–70.9 |
| tokio | fanin | 1 | 4 | 263.6 | 260.9–268.2 |
| tokio | fanin | 64 | 1 | 29.1 | 28.6–30.8 |
| tokio | fanin | 64 | 4 | 65.4 | 63.8–66.8 |

A separate macOS `sample` run (2 seconds, 1ms sampling, 300,000 ready
iterations) placed 1,573 of 1,655 main-thread samples in `kevent` beneath
Asio's scheduler/reactor. This locates the dominant sampled path on this
machine; it does not establish a portable root cause or predict the benefit
of a particular change. Profiled execution is excluded from the timing table.

Supplementary short runs of ready, mixed, and fan-in with capacities 0/1/64
passed with C++ ASan+UBSan, C++ TSan and Go's race detector. Sanitizer executions
are excluded from performance measurements. The original observations and metadata are retained in
[observations/macos-original](observations/macos-original/). The raw profiler log
is local evidence rather than a portable regression assertion. Rust was exercised by the ordinary checked harness;
no Rust sanitizer run is claimed.

## Optimized comparison on macOS and Linux

The full six-engine series is retained with every sample, source hash and build
command in [macos-current](observations/macos-current/) and
[linux-current](observations/linux-current/). The measured commits are
`f0ba53bf3a0d5dc8e07558ab227f978832bb4ed0` (macOS) and
`e8ebfc6e1aa069c780b67b4c7020cf0a50246457` (Linux). Every compiled project input
has the same recorded SHA256 in both runs; the later commit adds the compiler
lifetime characterization and named-storage test without changing the primitive
or benchmark inputs. Each run has 301 samples (43 configurations x 7 repetitions).
macOS uses `n=30000`; Linux uses `n=300000` and inherited CPU affinity 0-3 on a
Ryzen 9 9950X3D. The C++ header SHA256 is
`f299765376c3cecca2d5520dac5c7858c8628df3b07b583f39d73f4eba5a3612`.

| Machine/scenario | Original C++ | Current C++ | Go | Tokio | Crossbeam |
|---|---:|---:|---:|---:|---:|
| Mac, ready, 1 worker | 22284.1 | 74.5 | 40.2 | 21.4 | 20.3 |
| Mac, capacity 64, 4 workers | 4877.3 | 417.7 | 118.1 | 64.7 | 53.9 |
| Linux, ready, 1 worker | 674.5 | 79.8 | 58.7 | 41.0 | 28.7 |
| Linux, capacity 64, 4 workers | 2653.0 | 374.2 | 63.5 | 44.5 | 59.2 |

All figures are median ns/message (lower is better), derived from batch elapsed
time; they are not per-message latency percentiles. The improvement is real in
these controls, but the current implementation still does not meet performance
parity with Go or Rust. The complete tables include rendezvous, capacity-one and
one-worker fan-in results; do not infer uniform gains from this compact subset.

A separate Linux `strace -c` observation over 30,000 ready selections counted
60,000 `epoll_wait` calls with the frozen header and none with the current one.
These instrumented executions are excluded from throughput measurements. Their
logs are in the Linux observations directory. The implementation techniques,
guarantees retained, and remaining costs are explained in
[IMPLEMENTATION.md](IMPLEMENTATION.md).

`asio-reuse` is an additional public-API experiment, not a replacement for `asio`.
It moves the owning case handles from each result into the next selection, clears
old receive values, and replenishes a winning send. It introduces no borrowed
channel references or weaker lifetime rules. It tests the hypothesis that
reconstructing handles/refcounts dominates the remaining cost. The first paired
Mac experiment found essentially unchanged ready throughput (75.0 versus 75.2
ns/message); it does not justify attributing the remaining gap to refcounts.
The plain engine remains in every default comparison.

## Build-input integrity control

The build metadata format records all project headers, the Cargo manifest/lock,
benchmark sources, the build script, compiler versions, commands, and executable
hashes. The runner rejects obsolete metadata, changed inputs, or changed binaries
before executing measurements and checks recorded sources again at completion.
Historical observations above retain their original metadata format; rebuild
before collecting new observations with the current harness.

With the same toolchains used for measurement, reproduce the current rejection
and the retained original pipeline defect without editing production sources
(both output directories must be new; both controls need Go/Cargo as well as
C++, which the library's ordinary CTest suite does not):

```sh
python3 tests/provenance_control.py /tmp/asio-provenance-control \
  --asio-root /path/to/asio --go /path/to/go --cxx c++
python3 tests/legacy_pipeline_control.py /tmp/asio-legacy-pipeline-control \
  --asio-root /path/to/asio --go /path/to/go --cxx c++
```

`provenance_control.py` copies this repository to a fixture, builds every engine
with the real toolchains, runs one measurement, then changes the C++
optimization flag, Cargo's release optimization level, a binary and the
metadata schema after building: the current runner rejects each before any
measurement. `legacy_pipeline_control.py` rebuilds the frozen original
`c834f8b` scripts (`bench/reference/*-original.py`) in a disposable shared clone
of a library revision that still carries the in-tree layout they expect and
shows them accepting the stale binaries after the same manifest and flag
changes. The in-tree predecessor of these controls is archived unchanged in
`tests/archive/`.

The complete paired reuse experiment is retained in
[macos-reuse](observations/macos-reuse/) and
[linux-reuse](observations/linux-reuse/). Linux likewise showed no ready-path
improvement (78.6 versus 82.6 ns/message), while capacity-64/four-worker fan-in
improved in that series (395.7 versus 301.4). These are workload-dependent
observations, not evidence that reuse resolves the remaining gap.

## Second iteration: paired measurements

The new iteration replaces default arbitration's Mersenne Twister with a small
Xorshift64* generator, retaining full `std::shuffle` and the original explicit
seed behavior. It also avoids installing a stop callback for a non-stoppable
token. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the source comparison.

Seven-engine paired series retain all 357 observations on each host:
[Mac](observations/macos-v2/table.md) and [Labruna](observations/linux-v2/table.md).
Mac uses 100,000 iterations and Linux 300,000, seven repetitions, randomized
process order, the same toolchains and Linux affinity as the preceding series.
The old original engine remains available and its previous measurements are
retained; this paired series focuses on the preceding optimized version.
All 643 recorded build-input hashes agree across hosts. Metadata records the
working-tree patch over `6c107b9` on Mac and `e8ebfc6` on Labruna, rather than
claiming those base commits already contained the new header. The input hashes
identify the measured code.

| Host/scenario | C++ v1 | C++ v2 | Go | Tokio | Crossbeam |
|---|---:|---:|---:|---:|---:|
| Mac, ready | 75.5 | 58.5 | 39.7 | 21.8 | 21.4 |
| Mac, fan-in 64/4 workers | 420.7 | 369.3 | 113.1 | 63.0 | 54.0 |
| Labruna, ready | 78.4 | 75.9 | 59.5 | 41.0 | 27.9 |
| Labruna, fan-in 64/4 workers | 363.6 | 372.4 | 64.6 | 43.7 | 59.1 |

Values are median ns/message. Mac's ready path improves about 22%; Linux's about
3%. Linux's four-worker buffered fan-in does not improve consistently. This is
an architecture-dependent arbitration improvement, not performance parity or a
solution to suspended-operation allocation and scheduler costs. The reuse pairs,
capacity-zero channels and all other scenarios are included in the full tables.

## Third iteration: in-frame commitment, serial turn runner, no per-wait allocation

The third iteration adds the lazy `deferred` operation whose ready probe
commits in the awaiting coroutine's frame, replaces the per-operation strand
with a serial turn runner, allocates the owned operation through Asio's
recycling allocator, makes wait registrations and the lifetime registry
intrusive, and schedules wakeups and queued completions as continuations. See
[IMPLEMENTATION.md](IMPLEMENTATION.md) for each change, its measured
motivation, the rejected hypotheses, the floors and the remaining gap.

The acceptance target for this work is at most 1.05 times the applicable Rust
reference in comparable scenarios. It is not met. The table reports the ratio
against the best applicable Rust implementation and against each one; "none"
means no Rust engine runs that scenario (Tokio's bounded MPSC has no
capacity-zero channel; Crossbeam blocks threads and runs fan-in only with four
workers). Tokio is an asynchronous runtime with a single-consumer channel;
Crossbeam is a blocking multi-producer multi-consumer channel; neither
contract matches this extension's owning, cancellable, executor-affine
selection exactly, so the comparison is of throughput for the same message
pattern, not of equivalent semantics.

All eleven engines, seven repetitions and the complete per-sample records are
retained in [macos-v3](observations/macos-v3/) (100,000 iterations, Apple M6,
Apple Clang 21) and [linux-v3](observations/linux-v3/) (300,000 iterations,
Ryzen 9 9950X3D, GCC 16.1, inherited affinity 0-3), together with the
component microbenchmark output (`microbench.txt`) of each host. The source
identities of every engine are recorded in `metadata.json`; the preceding
optimized header is the frozen `asio-v2` engine, measured in the same series.

Mac, median ns/message:

| Scenario | C++ v2 | C++ current | Go | Tokio | Crossbeam | Current / best Rust |
|---|---:|---:|---:|---:|---:|---:|
| ready, 1 worker | 59.1 | 43.1 | 40.1 | 21.9 | 21.2 | 2.03 (Crossbeam), 1.97 vs Tokio |
| mixed, 1 worker | 58.5 | 43.1 | 39.6 | 23.2 | 21.7 | 1.99 (Crossbeam), 1.86 vs Tokio |
| fan-in, capacity 0, 1 worker | 517.1 | 258.0 | 103.3 | none | none | none (2.50 vs Go) |
| fan-in, capacity 0, 4 workers | 2211.1 | 925.8 | 182.6 | none | 1323.3 | 0.70 (Crossbeam) |
| fan-in, capacity 1, 1 worker | 346.3 | 175.7 | 83.9 | 71.1 | none | 2.47 (Tokio) |
| fan-in, capacity 1, 4 workers | 1085.0 | 596.1 | 150.1 | 252.6 | 155.7 | 3.83 (Crossbeam), 2.36 vs Tokio |
| fan-in, capacity 64, 1 worker | 101.3 | 65.2 | 44.1 | 29.8 | none | 2.19 (Tokio) |
| fan-in, capacity 64, 4 workers | 362.4 | 147.8 | 108.5 | 63.5 | 53.4 | 2.77 (Crossbeam), 2.33 vs Tokio |

Against the preceding C++ version the current one is 27% faster on the ready
and mixed loops and between 36% and 59% faster on every suspended scenario,
and it is below Crossbeam on the four-worker rendezvous fan-in. Against the
Rust references it remains about 2.0 times slower on the ready paths and 2.2
to 2.8 times slower on buffered fan-in (3.8 against Crossbeam on capacity-one
fan-in with four workers, where Crossbeam's own samples vary from 100 to 365
ns). The `asio-awaitable` engine shows the retained `use_awaitable` token on
the same headers: 63.4 ns on the ready loop, 7% slower than the preceding
version's 59.1, while 37% faster on capacity-one fan-in (219.0 vs 346.3);
the recommended lazy token is the `asio` engine.

Linux (Labruna), median ns/message:

| Scenario | C++ v2 | C++ current | Go | Tokio | Crossbeam | Current / best Rust |
|---|---:|---:|---:|---:|---:|---:|
| ready, 1 worker | 76.2 | 52.2 | 59.6 | 40.9 | 28.9 | 1.81 (Crossbeam), 1.28 vs Tokio |
| mixed, 1 worker | 77.2 | 52.9 | 59.8 | 47.6 | 30.7 | 1.73 (Crossbeam), 1.11 vs Tokio |
| fan-in, capacity 0, 1 worker | 634.5 | 333.0 | 154.4 | none | none | none (2.16 vs Go) |
| fan-in, capacity 0, 4 workers | 953.6 | 566.7 | 140.6 | none | 459.3 | 1.23 (Crossbeam) |
| fan-in, capacity 1, 1 worker | 424.5 | 227.6 | 122.8 | 146.9 | none | 1.55 (Tokio) |
| fan-in, capacity 1, 4 workers | 458.3 | 354.0 | 114.5 | 214.0 | 76.5 | 4.63 (Crossbeam), 1.65 vs Tokio |
| fan-in, capacity 64, 1 worker | 135.2 | 84.1 | 61.2 | 52.6 | none | 1.60 (Tokio) |
| fan-in, capacity 64, 4 workers | 369.9 | 114.0 | 63.6 | 43.8 | 59.9 | 2.60 (Tokio), 1.90 vs Crossbeam |

On Linux the current version is 31% faster than the preceding one on the ready
and mixed loops and 23% to 69% faster on the suspended scenarios. It is within
1.28 and 1.11 of Tokio on the ready and mixed loops but 1.7 to 1.8 of
Crossbeam, 1.55 to 1.65 of Tokio on capacity-one fan-in, 1.6 and 2.6 of Tokio
on capacity-64 fan-in, and 4.6 of Crossbeam on capacity-one fan-in with four
workers. No scenario with a Rust reference meets the 1.05 target on either
host; the capacity-zero four-worker fan-in is below Crossbeam on the Mac
(0.70) and above it on Linux (1.23).

A Linux `strace -f -c -e trace=futex` observation over 30,000 fan-in messages
with four workers (logs in `linux-v3/`) counts the scheduler wakeups the
continuation scheduling and the turn runner removed: capacity-one fan-in made
245,628 futex calls with the preceding header and 75,836 with the current
one; capacity-64 fan-in 117,536 and 11,975. With one worker both make one.
These instrumented executions are excluded from the throughput measurements.

## Fourth iteration: task-owned reusable selector, scheduler-linked turns, readiness hints

The fourth iteration adds `channel_selector`, a task-owned reusable selector
whose waits complete with the selected index while case values stay in the
selector (engine `asio-reusable`), and improves the operation shared by both
APIs: turns are linked directly into the `io_context` scheduler instead of
going through `any_io_executor`, peers claim waiters through the registration
node without reference counting, channels expose lock-free readiness hints to
the probe, a selector's registry registration persists across its waits, and
arbitration draws from a per-operation generator. The series below measured a
version that also withdrew a committed operation's remaining registrations one
channel at a time, each under its own mutex; that withdrawal was a
use-after-free (a peer's `take()` could still be about to claim the operation
through a node it had just unlinked) and was reverted to withdrawing under
every participating channel mutex, as the third iteration did. The corrected
header is measured in the paired series of the next section; the version
below is retained as the opt-in `asio-v4-unsafe*` engines, excluded from the
default series. See [IMPLEMENTATION.md](IMPLEMENTATION.md) for each change,
its isolated measurement, the rejected experiments, the controls and the
remaining gap.

The acceptance target is at most 1.05 times the applicable Rust reference in
comparable scenarios, on each host separately. On Linux the selector meets it
against the best applicable reference on the mixed loop (0.97 of Crossbeam),
capacity-one fan-in with one worker (0.53 of Tokio), capacity-64 fan-in with
one worker (0.84 of Tokio) and the four-worker rendezvous fan-in (0.68 of
Crossbeam), is below Tokio on every scenario Tokio runs, and misses it on
the ready loop (1.06 of Crossbeam, 0.75 of Tokio) and on the two buffered
four-worker fan-ins (2.54 of Crossbeam on capacity one, 1.35 of Tokio on
capacity 64). On the Mac it misses it everywhere Rust has a reference: 1.06
of Tokio on the mixed loop and on capacity-one fan-in with one worker, 1.12
to 1.21 on the other single-worker scenarios, and 1.19 to 2.44 on the
buffered four-worker fan-ins, while the rendezvous four-worker fan-in is 0.32
of Crossbeam. The one-shot API, which keeps its owning result, is 0.9 to 1.4
times the best reference on Linux single-worker scenarios and 1.5 to 1.9 on
the Mac's. "none" means no Rust engine runs that scenario (Tokio's bounded
MPSC has no capacity-zero channel; Crossbeam blocks threads and runs fan-in
only with four workers). Tokio is an asynchronous runtime with a
single-consumer channel; Crossbeam is a blocking multi-producer
multi-consumer channel; neither contract matches this extension's owning,
cancellable, executor-affine selection exactly, so the comparison is of
throughput for the same message pattern.

All fifteen engines, seven repetitions and the complete per-sample records are
retained in [macos-v4](observations/macos-v4/) (100,000 iterations, Apple M6,
Apple Clang 21, 805 samples) and [linux-v4](observations/linux-v4/) (300,000
iterations, Ryzen 9 9950X3D, GCC 16.1, affinity 0-3), together with each
host's component microbenchmark output (`microbench.txt`), the retained
experiment outputs and, on the Mac, the two development profiles. The source
identities of every engine are recorded in `metadata.json`; the preceding
optimized header is the frozen `asio-v3` engine, measured in the same series,
and the reference engines moved by at most 2% against the third-iteration
series on the Mac except Crossbeam's capacity-one four-worker fan-in (155.7
to 123.3 ns, within its own 100 to 365 ns sample range).

Mac, median ns/message:

| Scenario | C++ v3 | C++ one-shot | C++ selector | Go | Tokio | Crossbeam | Selector / best Rust | One-shot / best Rust |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ready, 1 worker | 42.6 | 35.8 | 24.9 | 39.5 | 21.7 | 21.3 | 1.17 (Crossbeam), 1.15 vs Tokio | 1.68 (Crossbeam), 1.65 vs Tokio |
| mixed, 1 worker | 42.7 | 35.3 | 24.6 | 40.0 | 23.2 | 22.0 | 1.12 (Crossbeam), 1.06 vs Tokio | 1.60 (Crossbeam), 1.53 vs Tokio |
| fan-in, capacity 0, 1 worker | 257.4 | 200.8 | 106.0 | 103.3 | none | none | none (1.03 vs Go) | none (1.94 vs Go) |
| fan-in, capacity 0, 4 workers | 904.0 | 746.2 | 429.8 | 183.5 | none | 1333.4 | 0.32 (Crossbeam) | 0.56 (Crossbeam) |
| fan-in, capacity 1, 1 worker | 176.2 | 137.4 | 75.2 | 84.7 | 71.1 | none | 1.06 (Tokio) | 1.93 (Tokio) |
| fan-in, capacity 1, 4 workers | 588.8 | 478.7 | 300.3 | 149.2 | 253.2 | 123.3 | 2.44 (Crossbeam), 1.19 vs Tokio | 3.88 (Crossbeam), 1.89 vs Tokio |
| fan-in, capacity 64, 1 worker | 65.7 | 54.3 | 35.8 | 43.3 | 29.7 | none | 1.21 (Tokio) | 1.83 (Tokio) |
| fan-in, capacity 64, 4 workers | 148.0 | 138.3 | 98.9 | 109.6 | 63.3 | 54.1 | 1.83 (Crossbeam), 1.56 vs Tokio | 2.56 (Crossbeam), 2.18 vs Tokio |

Against the frozen third iteration the selector is 42% faster on the ready
and mixed loops, 46% to 59% faster on the single-worker fan-in scenarios and
33% to 52% faster with four workers; the unchanged one-shot API gains 16% to
22% on single-worker scenarios and 7% to 19% with four workers from the
shared operation changes. The selector is below Go on every scenario but the
four-worker ones and below Crossbeam on the four-worker rendezvous fan-in.
The token variants on the current headers: `asio-awaitable` (the
`use_awaitable` token) 55.6 ns ready and 179.9 ns capacity-one fan-in,
`asio-reuse` (owning case handles transferred between iterations) 36.3 and
138.3 ns, against 64.1 and 218.5 ns and 43.2 and 177.2 ns for the same
variants of the third iteration.

Linux (Labruna), median ns/message:

| Scenario | C++ v3 | C++ one-shot | C++ selector | Go | Tokio | Crossbeam | Selector / best Rust | One-shot / best Rust |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ready, 1 worker | 52.3 | 44.1 | 30.6 | 58.9 | 40.8 | 28.9 | 1.06 (Crossbeam), 0.75 vs Tokio | 1.53 (Crossbeam), 1.08 vs Tokio |
| mixed, 1 worker | 52.1 | 44.1 | 29.2 | 59.1 | 48.5 | 30.1 | 0.97 (Crossbeam), 0.60 vs Tokio | 1.47 (Crossbeam), 0.91 vs Tokio |
| fan-in, capacity 0, 1 worker | 330.6 | 242.1 | 104.4 | 154.0 | none | none | none (0.68 vs Go) | none (1.57 vs Go) |
| fan-in, capacity 0, 4 workers | 569.2 | 533.3 | 311.6 | 140.8 | none | 456.6 | 0.68 (Crossbeam) | 1.17 (Crossbeam) |
| fan-in, capacity 1, 1 worker | 226.6 | 170.6 | 78.4 | 122.7 | 147.1 | none | 0.53 (Tokio) | 1.16 (Tokio) |
| fan-in, capacity 1, 4 workers | 355.5 | 292.2 | 197.6 | 114.5 | 216.0 | 77.8 | 2.54 (Crossbeam), 0.91 vs Tokio | 3.76 (Crossbeam), 1.35 vs Tokio |
| fan-in, capacity 64, 1 worker | 84.0 | 69.4 | 44.0 | 61.1 | 52.7 | none | 0.84 (Tokio) | 1.32 (Tokio) |
| fan-in, capacity 64, 4 workers | 115.2 | 101.7 | 59.0 | 63.7 | 43.6 | 61.1 | 1.35 (Tokio), 0.96 vs Crossbeam | 2.33 (Tokio), 1.66 vs Crossbeam |

On Linux the selector is 41% to 44% faster than the frozen third iteration on
the ready and mixed loops, 48% to 68% faster on the single-worker fan-in
scenarios and 44% to 49% faster with four workers; the one-shot API gains 15%
to 27% on single-worker scenarios and 6% to 18% with four workers. The
selector is below Go on every single-worker scenario, but above Go on the
rendezvous four-worker fan-in. Every reference engine of the third-iteration
series moved by at most 2% on this host. Token and reuse variants:
`asio-awaitable` 70.0 ns ready and 233.7 ns capacity-one fan-in, `asio-reuse`
43.0 and 171.8 ns, against 79.0 and 281.5 ns and 51.0 and 244.7 ns for the
third iteration's variants.

A Linux `strace -f -c -e trace=futex` observation over 30,000 fan-in messages
with four workers (logs in `linux-v4/`) counts scheduler wakeups: capacity-one
fan-in made 74,938 futex calls with the third-iteration header, 60,947 with the
current one-shot operation and 45,537 with the selector; capacity-64 fan-in
11,849, 9,307 and 8,769. With one worker each makes one. These instrumented
executions are excluded from the throughput measurements. The remaining
four-worker gap sits in Asio's single scheduler queue, whose mutex every turn
takes and whose condition variable signals an idle worker when work remains;
[IMPLEMENTATION.md](IMPLEMENTATION.md) names the experiment that would bound it.

## Fourth iteration, corrected: paired series with the safe withdrawal

The fourth-iteration series above measured a header whose finalization
withdrew a committed operation's remaining registrations one channel at a
time without that channel's mutex on the skip path; a rare SIGSEGV in a full
repetition of the four-worker rendezvous fan-in was a use-after-free of the
operation by a peer's `take()` (see [IMPLEMENTATION.md](IMPLEMENTATION.md),
fourth iteration, change 5). The corrected header withdraws under every
participating channel mutex again. This section is the fresh paired series of
that header, with the previous header retained as the opt-in
`asio-v4-unsafe`, `asio-v4-unsafe-reuse` and `asio-v4-unsafe-reusable`
engines, built by default and excluded from the default series.

Provenance: both hosts built and ran the same inputs, the library at
`e663a273eafa2db4be598fdf8b53eb79eddd1332` plus the working tree whose
`channel_select.hpp` has SHA256 `1b1339b02a05593b…` (the opt-in engines
compile the previous header, `88cee7151f630ef3…`, as an overlay), and all 650
recorded input hashes are identical in the two `metadata.json` files. The
fifteen default engines, seven repetitions and every sample are retained in
[macos-v4-fixed](observations/macos-v4-fixed/) (100,000 iterations, Apple M6,
Apple Clang 21.0.0, Go 1.27.3, Rust 1.99.0, 805 samples) and
[linux-v4-fixed](observations/linux-v4-fixed/) (300,000 iterations, Ryzen 9
9950X3D, GCC 16.1.0, Go 1.27.3, Rust 1.94.1, `taskset -c 0-3`, 805 samples);
the opt-in engines' separate series (168 samples each, no crash in either) are
in [macos-v4-unsafe-optin](observations/macos-v4-unsafe-optin/) and
[linux-v4-unsafe-optin](observations/linux-v4-unsafe-optin/). The build and
run provenance controls (`tests/provenance_control.py`,
`tests/legacy_pipeline_control.py`) passed on both hosts with the same
toolchains before these builds. No series was retried and no sample was
discarded.

Mac, median ns/message (ratios use the best applicable Rust engine; "none"
means no Rust engine runs the scenario):

| Scenario | C++ v3 | C++ one-shot | C++ selector | Go | Tokio | Crossbeam | Selector / best Rust | One-shot / best Rust |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ready, 1 worker | 42.9 | 35.4 | 24.9 | 40.5 | 21.9 | 21.5 | 1.16 (Crossbeam), 1.14 vs Tokio | 1.65 (Crossbeam), 1.62 vs Tokio |
| mixed, 1 worker | 43.0 | 35.5 | 25.1 | 40.6 | 23.1 | 21.9 | 1.15 (Crossbeam), 1.09 vs Tokio | 1.62 (Crossbeam), 1.54 vs Tokio |
| fan-in, capacity 0, 1 worker | 258.9 | 209.4 | 112.6 | 103.3 | none | none | none (1.09 vs Go) | none (2.03 vs Go) |
| fan-in, capacity 0, 4 workers | 920.2 | 815.0 | 512.0 | 179.6 | none | 1342.8 | 0.38 (Crossbeam) | 0.61 (Crossbeam) |
| fan-in, capacity 1, 1 worker | 175.6 | 140.9 | 80.5 | 84.1 | 71.5 | none | 1.12 (Tokio) | 1.97 (Tokio) |
| fan-in, capacity 1, 4 workers | 599.5 | 519.2 | 346.7 | 148.5 | 253.8 | 152.7 | 2.27 (Crossbeam), 1.37 vs Tokio | 3.40 (Crossbeam), 2.05 vs Tokio |
| fan-in, capacity 64, 1 worker | 65.5 | 54.2 | 35.5 | 43.1 | 29.9 | none | 1.19 (Tokio) | 1.81 (Tokio) |
| fan-in, capacity 64, 4 workers | 146.3 | 138.6 | 100.5 | 110.8 | 65.0 | 54.2 | 1.85 (Crossbeam), 1.55 vs Tokio | 2.56 (Crossbeam), 2.13 vs Tokio |

Linux (Labruna), median ns/message:

| Scenario | C++ v3 | C++ one-shot | C++ selector | Go | Tokio | Crossbeam | Selector / best Rust | One-shot / best Rust |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ready, 1 worker | 52.2 | 44.5 | 30.3 | 59.8 | 41.0 | 28.8 | 1.05 (Crossbeam; 1.052, above the threshold), 0.74 vs Tokio | 1.54 (Crossbeam), 1.09 vs Tokio |
| mixed, 1 worker | 52.3 | 43.5 | 32.1 | 60.7 | 47.4 | 30.5 | 1.05 (Crossbeam; 1.053, above the threshold), 0.68 vs Tokio | 1.42 (Crossbeam), 0.92 vs Tokio |
| fan-in, capacity 0, 1 worker | 320.7 | 258.3 | 106.8 | 154.1 | none | none | none (0.69 vs Go) | none (1.68 vs Go) |
| fan-in, capacity 0, 4 workers | 564.9 | 529.8 | 320.3 | 141.1 | none | 459.5 | 0.70 (Crossbeam) | 1.15 (Crossbeam) |
| fan-in, capacity 1, 1 worker | 220.2 | 177.4 | 81.4 | 122.7 | 146.8 | none | 0.55 (Tokio) | 1.21 (Tokio) |
| fan-in, capacity 1, 4 workers | 347.8 | 303.1 | 205.0 | 114.2 | 215.9 | 83.3 | 2.46 (Crossbeam), 0.95 vs Tokio | 3.64 (Crossbeam), 1.40 vs Tokio |
| fan-in, capacity 64, 1 worker | 82.9 | 71.5 | 44.5 | 62.2 | 52.2 | none | 0.85 (Tokio) | 1.37 (Tokio) |
| fan-in, capacity 64, 4 workers | 114.8 | 102.8 | 64.1 | 64.7 | 44.1 | 58.0 | 1.45 (Tokio), 1.11 vs Crossbeam | 2.33 (Tokio), 1.77 vs Crossbeam |

The acceptance target, at most 1.05 times the best applicable Rust engine on
each host, is stated only where the median ratio is at or below 1.05. On
Linux the selector meets it on the four-worker rendezvous fan-in (0.70 of
Crossbeam), capacity-one fan-in with one worker (0.55 of Tokio) and
capacity-64 fan-in with one worker (0.85 of Tokio; its slowest sample is 1.05
of Tokio's fastest, so that one holds on medians rather than on every
sample); on the ready and mixed loops it is at 1.052 and 1.053 of Crossbeam,
which is not met, while 0.74 and 0.68 of Tokio; it misses on the two buffered
four-worker fan-ins (2.46 of Crossbeam on capacity one, where it is 0.95 of
Tokio, and 1.45 of Tokio on capacity 64). On the Mac it meets the target only
on the four-worker rendezvous fan-in (0.38 of Crossbeam) and is 1.09 to 1.19
of the best reference on the single-worker scenarios and 1.85 to 2.27 on the
buffered four-worker fan-ins. The one-shot API meets it only on the Mac's
four-worker rendezvous fan-in (0.61 of Crossbeam). The selector is below Go on
every single-worker scenario on Linux; on Mac the single-worker rendezvous
remains above Go (112.6 versus 103.3 ns/message). Against the frozen third iteration
measured in the same series it is 42% faster on the Mac's ready and mixed
loops and 31% to 57% faster on the suspended scenarios, and on Linux 39% to
42% and 41% to 67%.

Cost of the safe withdrawal. Measured in the same session with the same
build directory (the opt-in engines against the corrected ones), the selector
pays about 2% on the ready and mixed loops and on single-worker capacity-64
fan-in, 6% to 7% on the single-worker rendezvous and capacity-one fan-ins, and
8% to 13% on the four-worker rendezvous and capacity-one fan-ins on the Mac;
on Linux 2% to 5% on every scenario except mixed (10%, inside that scenario's
sample spread of 1.31) and four-worker capacity-64 fan-in (9%); the one-shot
engine pays at most 4% on the Mac. The Linux opt-in series' one-shot engine
had bimodal ready, mixed and four-worker capacity-64 samples (minimum at the
corrected engine's value, median about 20% above it); that series was neither
rerun nor trimmed, and the cross-session comparison below shows no such
effect. Against the previous series (`macos-v4`, `linux-v4`), measured on the
same hosts six hours earlier, the selector moved by at most 2% on the Mac's
ready, mixed and capacity-64 scenarios and by 6% to 19% on its rendezvous and
capacity-one fan-ins, and on Linux by 1% to 10%; the reference engines moved
by at most 3% on both hosts except Crossbeam's capacity-one four-worker fan-in
(within its own 124 to 210 ns sample range), while the frozen original engine
moved 5% to 11% on Linux single-worker scenarios, so cross-session differences
below about 10% on that host are within the drift of the floor.

Uncertainty: the seven samples of a configuration span at most 1.1 (max over
min) on the Mac except the four-worker rendezvous (1.31), the one-shot
capacity-one single-worker fan-in (1.42, one slow sample) and the selector's
mixed loop (1.26); on Linux single-worker scenarios often span 1.2 to 1.3 on
every engine, including Go and Tokio, from occasional slow samples, while the
four-worker buffered fan-ins span less than 1.1. Medians are reported; the
parity verdicts above state when the slowest sample also stays within 1.05.
Tokio is an asynchronous runtime with a single-consumer channel; Crossbeam is
a blocking multi-producer multi-consumer channel; Go's channels are runtime
scheduled; none matches this extension's owning, cancellable, executor-affine
selection exactly, so the comparison is of throughput for the same message
pattern, not of equivalent semantics.

## Final validation series (2026-10-25)

The final library source is commit `4b04892f2d02d5c9e04b79b428d8fe905a927a48` (tree `3ce98d09c449c7cdd95e44991ba81c0a74c0db4d`), header SHA256 `0148fa61e76a5da4…`. The fresh [Mac series](observations/macos-final-20261025/) and [Linux series](observations/linux-final-20261025/) each completed **805/805 samples**: fifteen default engines, 115 configurations, seven repetitions. All **650 compiled input hashes match across hosts** and the final sources. The Linux metadata retains its original `eb05df406` HEAD plus the seven-file working-tree status; `validated-source.json` maps that byte-identical patch to the final commit without rewriting the recorded metadata.

Mac: Apple Clang 21, Go 1.27.3, Rust 1.99.0, `n=100000`. Linux: GCC 16.1, Go 1.27.3, Rust 1.94.1, `n=300000`, inherited affinity CPUs 0–3, matching the preceding paired series. Crossbeam 0.5.17 and Tokio 1.54.1 remain locked. No compilation or sanitizer execution overlapped timing. Provenance and original-pipeline controls passed before timing; the first Mac provenance attempt was blocked by the sandbox at CPU discovery, before measurements, and the permitted run passed. All measured samples are retained; no series was rerun or trimmed.

Median batch ns/message, lower is better. `n/a` means that engine does not support the scenario. The final column compares the reusable selector with the fastest applicable Rust engine. The complete tables include min/max for every configuration.

| Host / scenario (capacity, workers) | C++ one-shot | C++ selector | Go | Tokio | Crossbeam | Selector / best Rust |
|---|---:|---:|---:|---:|---:|---:|
| Mac / ready (1, 1) | 35.7 | 24.8 | 40.6 | 22.1 | 21.4 | 1.159 |
| Mac / mixed (1, 1) | 36.2 | 24.7 | 40.6 | 22.9 | 21.7 | 1.142 |
| Mac / fanin (0, 1) | 209.8 | 114.0 | 103.9 | n/a | n/a | n/a |
| Mac / fanin (0, 4) | 838.9 | 506.0 | 179.6 | n/a | 1387.6 | 0.365 |
| Mac / fanin (1, 1) | 141.9 | 80.8 | 84.3 | 71.5 | n/a | 1.131 |
| Mac / fanin (1, 4) | 535.3 | 337.1 | 149.2 | 254.5 | 133.2 | 2.532 |
| Mac / fanin (64, 1) | 54.9 | 35.1 | 43.9 | 29.8 | n/a | 1.177 |
| Mac / fanin (64, 4) | 143.5 | 101.7 | 114.8 | 63.7 | 54.0 | 1.883 |
| Linux / ready (1, 1) | 44.7 | 30.7 | 59.9 | 51.8 | 28.5 | 1.078 |
| Linux / mixed (1, 1) | 44.3 | 36.9 | 59.6 | 47.4 | 29.8 | 1.237 |
| Linux / fanin (0, 1) | 258.6 | 108.4 | 154.1 | n/a | n/a | n/a |
| Linux / fanin (0, 4) | 532.9 | 326.7 | 140.6 | n/a | 465.3 | 0.702 |
| Linux / fanin (1, 1) | 181.5 | 82.3 | 148.7 | 147.2 | n/a | 0.559 |
| Linux / fanin (1, 4) | 378.7 | 206.0 | 114.1 | 216.5 | 81.2 | 2.536 |
| Linux / fanin (64, 1) | 87.6 | 45.1 | 61.1 | 52.5 | n/a | 0.858 |
| Linux / fanin (64, 4) | 130.6 | 64.0 | 80.7 | 43.9 | 60.9 | 1.456 |

The selector meets the 1.05× median target against the best applicable Rust engine on one of seven Rust-comparable scenarios on Mac (four-worker rendezvous) and three of seven on Linux (four-worker rendezvous, and single-worker capacity-one and capacity-64 fan-in). Capacity-zero single-worker fan-in has no applicable Rust engine. Universal parity is **not achieved**. Buffered four-worker fan-in remains the main gap: selector/Crossbeam is 2.53× on capacity one on both hosts; on capacity 64 the selector is 1.88× the best Rust engine on Mac and 1.46× on Linux. One-shot results are reported separately, not replaced by selector results.

Against Go, the selector is faster on ready/mixed and buffered single-worker scenarios on both hosts, but slower on four-worker rendezvous (Mac 2.82×, Linux 2.32×) and capacity-one four-worker fan-in (2.26×, 1.81×). The Mac single-worker rendezvous is also slower than Go (1.10×); Linux is faster there (0.70×). Capacity-64 four-worker fan-in is faster than Go on these medians (0.89×, 0.79×).

Compared with `macos-v4-fixed`, the selector medians change by less than 3% in every scenario. On Linux seven of eight selector medians change by at most 2%; mixed is +15%, within a distinctly bimodal series that also affects Go and Rust. There are 211/805 Linux samples more than 12% above their configuration minimum, versus 92/805 previously, and 16 configuration medians sit in the slower mode. The cause is unresolved; frequency management is a hypothesis. No samples are excluded and minima are not substituted for medians. For example the Linux mixed selector spans 29.3–38.0 ns/message; quote its median (36.9) with the spread. Mac capacity-one four-worker selector samples also have a wide span (174.3–346.9 ns/message, median 337.2), so its median must not be read as a stable latency guarantee. Raw samples, Linux activity snapshots and the per-configuration comparison are retained in the observation directories.

These are throughput observations on dynamically managed, non-isolated hosts. They do not demonstrate latency percentiles or equivalent contracts: Tokio uses async MPSC, Crossbeam blocking MPMC, and Go runtime-scheduled channels. Tokio has no capacity-zero result; Crossbeam fan-in cannot use this topology with one worker. The withdrawal regression now observes actual mutex acquisition and rejects the faithful lock-bypassed mutant; benchmarks remain supplementary to correctness controls.
