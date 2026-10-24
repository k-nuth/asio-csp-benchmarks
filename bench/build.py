#!/usr/bin/env python3
"""Build every comparison without replacing system toolchains."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--asio-root', type=Path, required=True, help='Asio source checkout (read-only)')
p.add_argument('--out', type=Path, default=Path(__file__).parent / 'build')
p.add_argument('--cxx', default=os.environ.get('CXX', 'c++'))
p.add_argument('--go', default=shutil.which('go'))
p.add_argument('--cargo', default=shutil.which('cargo') or str(Path.home() / '.cargo/bin/cargo'))
a = p.parse_args()
if not a.go:
    p.error('Go is required: pass --go /path/to/go')
root = a.asio_root.resolve()
benchmark_root = Path(__file__).resolve().parents[1]
bench = Path(__file__).resolve().parent
if not (root / 'include/asio.hpp').is_file():
    p.error('--asio-root must contain include/asio.hpp')
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=True)
commands = []
# Frozen engines compile their historical channel header together with the
# awaitable implementation they were measured against (the unmodified
# upstream one before the third iteration, the third iteration's own copy for
# asio-v3*), and with the coroutine token of their era. The current engines
# use the lazy as_tuple(deferred) operation (asio, asio-reuse), the task-owned
# reusable selector (asio-reusable), or the awaitable<T> token on the current
# headers (asio-awaitable).
upstream = '-I' + str(bench / 'reference-upstream')
awaitable_token = '-DASIO_BENCH_AWAITABLE_TOKEN'
reuse = '-DASIO_BENCH_REUSE_CASES'
reusable = '-DASIO_BENCH_REUSABLE_SELECTOR'
v3 = '-I' + str(bench / 'reference-v3')
v4 = '-I' + str(bench / 'reference-v4')
for name, overlay in [('asio', []), ('asio-reuse', [reuse]), ('asio-reusable', [reusable]), ('asio-awaitable', [awaitable_token]),
                      ('asio-v4-unsafe', [v4]), ('asio-v4-unsafe-reuse', [reuse, v4]),
                      ('asio-v4-unsafe-reusable', [reusable, v4]),
                      ('asio-v3', [v3]), ('asio-v3-reuse', [reuse, v3]), ('asio-v3-awaitable', [awaitable_token, v3]),
                      ('asio-v2', [awaitable_token, '-I' + str(bench / 'reference-v2'), upstream]),
                      ('asio-v2-reuse', [reuse, awaitable_token, '-I' + str(bench / 'reference-v2'), upstream]),
                      ('asio-v1', [awaitable_token, '-I' + str(bench / 'reference-v1'), upstream]),
                      ('asio-v1-reuse', [reuse, awaitable_token, '-I' + str(bench / 'reference-v1'), upstream]),
                      ('asio-baseline', [awaitable_token, '-I' + str(bench / 'reference'), upstream])]:
    commands.append([a.cxx, '-std=c++20', '-O3', '-DNDEBUG', '-DASIO_STANDALONE', '-pthread',
                     *overlay, '-I' + str(root / 'include'), str(bench / 'select.cpp'),
                     '-o', str(a.out / (name + '-bench'))])
commands += [[a.go, 'build', '-o', str(a.out / 'go-bench'), str(bench / 'select.go')],
             [a.cargo, 'build', '--release', '--locked', '--manifest-path', str(bench / 'rust/Cargo.toml')]]
for cmd in commands:
    print(' '.join(cmd), flush=True)
    subprocess.run(cmd, cwd=root, check=True)
versions = {}
for name, cmd in [('cxx', [a.cxx, '--version']), ('go', [a.go, 'version']), ('cargo', [a.cargo, '--version']),
                  ('rustc', [os.environ.get('RUSTC', shutil.which('rustc') or str(Path.home() / '.cargo/bin/rustc')), '--version'])]:
    versions[name] = subprocess.check_output(cmd, text=True).strip()
files = [root / 'include/asio/experimental/channel_select.hpp', bench / 'reference/asio/experimental/channel_select.hpp',
         bench / 'reference-v1/asio/experimental/channel_select.hpp',
         bench / 'reference-v2/asio/experimental/channel_select.hpp',
         bench / 'reference-v4/asio/experimental/channel_select.hpp',
         bench / 'reference-v4/asio/impl/awaitable.hpp',
         bench / 'reference-v3/asio/experimental/channel_select.hpp',
         bench / 'reference-v3/asio/impl/awaitable.hpp',
         bench / 'reference-upstream/asio/impl/awaitable.hpp',
         bench / 'select.cpp', bench / 'select.go', bench / 'rust/src/main.rs',
         bench / 'rust/Cargo.lock', bench / 'rust/Cargo.toml', bench / 'run.py', Path(__file__)]
# Hidden files (for example AppleDouble `._name.hpp` sidecars that a macOS tar
# can leave in a transferred tree) are not compiled and are not recorded, so the
# recorded input set is the same on every host that holds the same sources.
files += sorted(p for p in (root / 'include').rglob('*')
                if p.suffix in ('.hpp', '.ipp') and not p.name.startswith('.'))
binaries = {name: a.out / (name + '-bench') for name in ('asio', 'asio-reuse', 'asio-reusable', 'asio-awaitable',
                                                         'asio-v4-unsafe', 'asio-v4-unsafe-reuse', 'asio-v4-unsafe-reusable',
                                                         'asio-v3', 'asio-v3-reuse', 'asio-v3-awaitable',
                                                         'asio-v2', 'asio-v2-reuse',
                                                         'asio-v1', 'asio-v1-reuse', 'asio-baseline', 'go')}
for name in ('crossbeam', 'tokio'):
    binaries[name] = bench / 'rust/target/release/select-bench'
def identity(file):
    if file.is_relative_to(root):
        return 'asio/' + str(file.relative_to(root))
    return 'benchmarks/' + str(file.relative_to(benchmark_root))

metadata = dict(schema_version=3, commands=commands, versions=versions,
                source_roots=dict(asio=str(root), benchmarks=str(benchmark_root)),
                source_sha256={identity(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
                binary_sha256={name: hashlib.sha256(file.read_bytes()).hexdigest() for name, file in binaries.items()})
(a.out / 'build.json').write_text(json.dumps(metadata, indent=2) + '\n')
