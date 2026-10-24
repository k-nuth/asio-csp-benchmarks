# Second optimized C++ snapshot

`asio/experimental/channel_select.hpp` is byte-for-byte the header from
`3f9a9e5708e5c540f9a613fc9ac7b17d857c939b`, SHA256
`36e924196e8e1dcf0dc8d4cd8df6c51873eb5e06000018369d02239ad5ce77e5`.
The copyright and Boost Software License notice are retained.

`asio-v2` and `asio-v2-reuse` compile this overlay together with
`../reference-upstream/`, which holds the unmodified upstream
`asio/impl/awaitable.hpp` that this snapshot was measured against. They use the
same benchmark source and flags as the current `asio` and `asio-reuse` engines,
plus `-DASIO_BENCH_AWAITABLE_TOKEN`: this snapshot's coroutine path is
`as_tuple(use_awaitable)`, and its `deferred` token is the generic deferred
startup/completion path, not an inline path. The reuse macro is the only
difference between each pair. This snapshot is benchmark-only and is not
installed in the Conan package. The earlier versions remain available as
`asio-baseline` under `../reference/` and `asio-v1` under `../reference-v1/`.
