# Third optimized C++ snapshot

`asio/experimental/channel_select.hpp` is byte-for-byte the third-iteration
header, SHA256
`c469b0ec77bff998096a48ca7e866aa75258b5f2e448f6f771084f7d9c3e7788`, and
`asio/impl/awaitable.hpp` is the awaitable implementation it was measured with
(the opt-in immediate-completion hook version), SHA256
`66bf427516c0df91bf28bfdf0565372d3454ed7e6b9b840234e236f73258fd73`. Both are
the files recorded in `../observations/macos-v3/` and `../observations/linux-v3/`.
The copyright and Boost Software License notices are retained.

`asio-v3`, `asio-v3-reuse` and `asio-v3-awaitable` compile this overlay before
the normal include directory, with the same benchmark source and flags as the
current engines: `asio-v3` with the `as_tuple(asio::deferred)` lazy operation
that this snapshot documented as its recommended coroutine token, `asio-v3-reuse`
additionally with `-DASIO_BENCH_REUSE_CASES`, and `asio-v3-awaitable` with
`-DASIO_BENCH_AWAITABLE_TOKEN`. The snapshot therefore never compiles against a
later `include/` component. It is benchmark-only and not installed in the Conan
package. Earlier versions remain available under `../reference/` (original),
`../reference-v1/` and `../reference-v2/`.
