# Unmodified upstream Asio component overlay

`asio/impl/awaitable.hpp` is byte-for-byte the file from upstream tag
`asio-1-38-2` (commit `8806a6803cde7054c3049d3666d3ec36786568c5`), SHA256
`5ef353a54789a676723c62f62f041a24d07b4f69ce25fa9587b002ef69ad0657`.
Its copyright and Boost Software License notice are retained.

The current tree modifies that file: it adds the opt-in
`awaitable_async_op_immediate` hook used by the channel selection's immediate
coroutine path. The frozen `asio-baseline`, `asio-v1`, `asio-v1-reuse`,
`asio-v2` and `asio-v2-reuse` engines were all measured against the upstream
file, so their build commands place this overlay before the normal include
directory. The historical engines therefore compile exactly the component bytes
they were measured with; nothing from the current `include/` tree replaces them
silently. The overlay is benchmark/control-only and is not installed or
included by the library or Conan package.
