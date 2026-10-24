# Frozen C++ baseline

`asio/experimental/channel_select.hpp` is byte-for-byte the header from
`035b2c7850e26f8d8ecd826899b76ae9bc9db9ae` in k-nuth/asio, before performance
changes. SHA256: `1a553194765e1e73513f4584442fd03da12b4d55a932d3bd00c08be70d26e27b`.
Its Boost Software License notice is retained; the license is at repository root.

`build.py` puts this overlay before the normal include directory to build
`asio-baseline-bench`; `asio-bench` builds the current implementation. Both use
exactly the same benchmark source and compiler flags. The overlay is restricted
to benchmarks and is not installed or included by the library or Conan package.

`build-original.py` and `run-original.py` are unmodified pipeline scripts from
`c834f8b7d9db45c9485e4ff40962b89781d9d1cf` (SHA256 `962899b3c43217d9…` and
`f4306f788a00964c…`). They are regression data, not the measurement entry
points. The original pipeline incorrectly accepts existing binaries after
changing Cargo release flags or the C++ build recipe. Two controls in `tests/`
demonstrate that boundary with real builds and the same toolchains as the
measurements: `tests/legacy_pipeline_control.py` rebuilds these original scripts
in a disposable shared clone of a library revision that still carries the
in-tree `csp/bench` layout and shows the stale binaries accepted (RED);
`tests/provenance_control.py` shows the current `build.py`/`run.py` rejecting
changed flags, a changed manifest, a changed binary and legacy metadata (GREEN).

`awaitable-lifetime-original.cpp` preserves `ready_contracts()` from
`f0ba53bf3a0d5dc8e07558ab227f978832bb4ed0`; only its entry point is narrowed to
that same full scenario. On the measured GCC 16.1/Linux toolchain, from the
library checkout (`/path/to/asio`) with this repository checked out next to it:

```sh
g++ -std=c++20 -O1 -g -fsanitize=address,undefined -DASIO_STANDALONE -pthread \
  -I/path/to/asio/include bench/reference/awaitable-lifetime-original.cpp -o /tmp/tuple-original
/tmp/tuple-original
```

This intentionally reproduces the retained 592-byte LeakSanitizer finding. Adding
`-Ibench/reference` before the library include directory reproduces it with the
frozen original channel header too. The compiler-only source under the library's
`csp/tests/` reproduces ownership retention with no Asio dependency. The current
full control uses named tuple storage and checks weak ownership after natural
coroutine destruction. See `../IMPLEMENTATION.md`; the original report is never
classified as clean.
