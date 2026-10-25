# Asio channel-selection comparisons

This repository contains the C++, Go, Tokio and Crossbeam benchmark harness,
historical C++ implementations and retained measurement series. The library,
Conan recipe and correctness regressions live in
[k-nuth/asio](https://github.com/k-nuth/asio).

Build against an explicit Asio checkout; the harness never modifies it:

```sh
python3 bench/build.py --asio-root /path/to/asio --go /path/to/go --out build
python3 bench/run.py --asio-root /path/to/asio --bin-dir build --n 100000 --repeats 7 --out results
```

The frozen `asio-v4-unsafe`, `asio-v4-unsafe-reuse` and
`asio-v4-unsafe-reusable` engines preserve the version with the known
withdrawal use-after-free. They are built for explicit reproduction and
comparison, but excluded from the default run. Request them with `--engines`;
a crash is recorded as a failed series, never discarded as an outlier.
The build-input and original-pipeline controls are `tests/provenance_control.py`
and `tests/legacy_pipeline_control.py` (see [bench/README.md](bench/README.md)).

On Linux, the comparable four-core series uses `taskset -c 0-3` and `--n 300000`.
Builds and sanitizer runs must finish before timing on the same host. The runner
checks source and executable hashes and retains every sample, including counts
and commands. Timings are median batch ns/message, not latency percentiles.
Tokio uses asynchronous MPSC channels; Crossbeam uses blocking MPMC channels.
Unsupported scenarios are excluded explicitly rather than emulated.

All fifteen engines remain available: the original implementation, versions
v1/v2/v3, their token/reuse variants, the current one-shot and reusable APIs,
Go, Tokio and Crossbeam. See [the detailed comparison](bench/README.md) and
[implementation analysis](bench/IMPLEMENTATION.md). Historical metadata retains
its original checkout paths and source identities; it is evidence, not current
build configuration.

Raw crash reports and diagnostic logs stay in local evidence. A measurement
series that fails is incomplete and must not be reported as a passing full run.

The [final validated comparison](bench/README.md#final-validation-series-2026-10-25) records 805 samples on each host against Go, Tokio and Crossbeam, including the remaining performance gaps.
