#!/usr/bin/env python3
"""Run binaries serially in randomized order; retain every observation."""
import argparse
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--asio-root', type=Path, required=True, help='Same Asio checkout used by build.py')
p.add_argument('--bin-dir', type=Path, default=Path(__file__).parent / 'build')
p.add_argument('--n', type=int, default=30000)
p.add_argument('--repeats', type=int, default=7)
p.add_argument('--engines', default='asio-baseline,asio-v1,asio-v1-reuse,asio-v2,asio-v2-reuse,'
               'asio-v3,asio-v3-reuse,asio-v3-awaitable,asio,asio-reuse,asio-reusable,asio-awaitable,go,crossbeam,tokio')
p.add_argument('--out', type=Path, default=Path(__file__).parent / 'results')
a = p.parse_args()
if a.n < 1 or a.repeats < 1:
    p.error('--n and --repeats must be positive')
root = a.asio_root.resolve()
benchmark_root = Path(__file__).resolve().parents[1]
bench = Path(__file__).resolve().parent
a.bin_dir = a.bin_dir.resolve()
a.out = a.out.resolve()
a.out.mkdir(parents=True, exist_ok=True)

def call(cmd):
    return subprocess.check_output([str(c) for c in cmd], text=True, stderr=subprocess.STDOUT, timeout=120).strip()

def digest(file):
    return hashlib.sha256(file.read_bytes()).hexdigest()

def identity(file):
    if file.is_relative_to(root):
        return 'asio/' + str(file.relative_to(root))
    return 'benchmarks/' + str(file.relative_to(benchmark_root))

def source_file(identity):
    owner, relative = identity.split('/', 1)
    roots = dict(asio=root, benchmarks=benchmark_root)
    if owner not in roots:
        p.error('unknown source root in build metadata: ' + owner)
    return roots[owner] / relative

all_engines = {'asio-baseline': [a.bin_dir / 'asio-baseline-bench'],
               'asio-v4-unsafe': [a.bin_dir / 'asio-v4-unsafe-bench'],
               'asio-v4-unsafe-reuse': [a.bin_dir / 'asio-v4-unsafe-reuse-bench'],
               'asio-v4-unsafe-reusable': [a.bin_dir / 'asio-v4-unsafe-reusable-bench'],
               'asio-v1': [a.bin_dir / 'asio-v1-bench'],
               'asio-v1-reuse': [a.bin_dir / 'asio-v1-reuse-bench'],
               'asio-v2': [a.bin_dir / 'asio-v2-bench'],
               'asio-v2-reuse': [a.bin_dir / 'asio-v2-reuse-bench'],
               'asio-v3': [a.bin_dir / 'asio-v3-bench'], 'asio-v3-reuse': [a.bin_dir / 'asio-v3-reuse-bench'],
               'asio-v3-awaitable': [a.bin_dir / 'asio-v3-awaitable-bench'],
               'asio': [a.bin_dir / 'asio-bench'], 'asio-reuse': [a.bin_dir / 'asio-reuse-bench'],
               'asio-reusable': [a.bin_dir / 'asio-reusable-bench'],
               'asio-awaitable': [a.bin_dir / 'asio-awaitable-bench'], 'go': [a.bin_dir / 'go-bench'],
               'crossbeam': [bench / 'rust/target/release/select-bench', 'crossbeam'],
               'tokio': [bench / 'rust/target/release/select-bench', 'tokio']}
try:
    engines = {e: all_engines[e] for e in a.engines.split(',')}
except KeyError as e:
    p.error('unknown engine: ' + str(e))
scenarios = [('ready', 1, 1), ('mixed', 1, 1), ('fanin', 0, 1), ('fanin', 0, 4),
             ('fanin', 1, 1), ('fanin', 1, 4), ('fanin', 64, 1), ('fanin', 64, 4)]
cases = [(e, m, c, w) for e in engines for m, c, w in scenarios
         if not (e == 'tokio' and c == 0)
         and not (e == 'crossbeam' and m == 'fanin' and w == 1)]
files = [bench / 'select.cpp', bench / 'select.go', bench / 'rust/src/main.rs',
         bench / 'rust/Cargo.toml', bench / 'rust/Cargo.lock', bench / 'build.py', Path(__file__),
         root / 'include/asio/experimental/channel_select.hpp',
         root / 'include/asio/impl/awaitable.hpp',
         bench / 'reference/asio/experimental/channel_select.hpp',
         bench / 'reference-v1/asio/experimental/channel_select.hpp',
         bench / 'reference-v2/asio/experimental/channel_select.hpp',
         bench / 'reference-v4/asio/experimental/channel_select.hpp',
         bench / 'reference-v4/asio/impl/awaitable.hpp',
         bench / 'reference-v3/asio/experimental/channel_select.hpp',
         bench / 'reference-v3/asio/impl/awaitable.hpp',
         bench / 'reference-upstream/asio/impl/awaitable.hpp']
source_hashes = {identity(f): digest(f) for f in files}
build_file = a.bin_dir / 'build.json'
if not build_file.exists():
    p.error('missing build.json; run build.py first')
build = json.loads(build_file.read_text())
if build.get('schema_version') != 3:
    p.error('old or unsupported build metadata; rebuild with build.py first')
if build.get('source_roots') != dict(asio=str(root), benchmarks=str(benchmark_root)):
    p.error('source roots differ from build metadata; rebuild first')
for engine, cmd in engines.items():
    if digest(Path(cmd[0])) != build['binary_sha256'].get(engine):
        p.error('binary differs from build metadata; rebuild first: ' + engine)
if build:
    for file, expected in build['source_sha256'].items():
        if digest(source_file(file)) != expected:
            p.error('source differs from build metadata; rebuild first: ' + file)
machine = platform.processor()
if platform.system() == 'Darwin':
    machine = call(['sysctl', '-n', 'machdep.cpu.brand_string'])
elif Path('/proc/cpuinfo').exists():
    machine = next((s.split(':', 1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines()
                    if s.startswith('model name')), machine)
meta = dict(timestamp=time.strftime('%Y-%m-%dT%H:%M:%S%z'), platform=platform.platform(), machine=machine,
            cpu_count=os.cpu_count(), affinity=sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None,
            head=call(['git', '-C', root, 'rev-parse', 'HEAD']), tree=call(['git', '-C', root, 'rev-parse', 'HEAD^{tree}']),
            status=call(['git', '-C', root, 'status', '--short']), n=a.n, repeats=a.repeats,
            expected_samples=len(cases) * a.repeats, completed=False,
            source_sha256=source_hashes, build=build,
            binary_sha256={e: digest(Path(cmd[0])) for e, cmd in engines.items()})
(a.out / 'metadata.json').write_text(json.dumps(meta, indent=2) + '\n')
records = []
# Separate discarded processes warm system caches; timed loops remain uninstrumented.
for e, m, c, w in cases:
    call(engines[e] + [m, str(min(a.n, 3000)), str(c), str(w)])
jobs = cases * a.repeats
random.Random(1907).shuffle(jobs)
for e, m, c, w in jobs:
    cmd = engines[e] + [m, str(a.n), str(c), str(w)]
    try:
        output = call(cmd)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        failure = dict(engine=e, mode=m, capacity=c, workers=w, n=a.n,
                       command=list(map(str, cmd)), error=type(error).__name__,
                       returncode=getattr(error, 'returncode', None),
                       output=str(getattr(error, 'output', '')))
        (a.out / 'failure.json').write_text(json.dumps(failure, indent=2) + '\n')
        raise
    ns, *counts = map(int, output.split(','))
    ops = a.n * (3 if m == 'fanin' else 1)
    assert len(counts) == 3 and sum(counts) == ops and ns > 0
    if m == 'fanin':
        assert counts == [a.n] * 3
    records.append(dict(engine=e, mode=m, capacity=c, workers=w, n=a.n, ns=ns,
                        ns_per_message=ns / ops, counts=counts, command=list(map(str, cmd))))
    print(f'{len(records)}/{len(jobs)} {e} {m} c={c} w={w}: {ns / ops:.1f} ns/msg', flush=True)
    (a.out / 'raw.json').write_text(json.dumps(records, indent=2) + '\n')
for file, expected in {**source_hashes, **build['source_sha256']}.items():
    assert digest(source_file(file)) == expected, 'source changed during run: ' + file
rows = []
for e, m, c, w in cases:
    vals = [r['ns_per_message'] for r in records
            if (r['engine'], r['mode'], r['capacity'], r['workers']) == (e, m, c, w)]
    median = statistics.median(vals)
    rows.append(dict(engine=e, mode=m, capacity=c, workers=w, median_ns=median,
                     min_ns=min(vals), max_ns=max(vals), messages_per_second=1e9 / median))
(a.out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
lines = ['| Engine | Scenario | Capacity | Workers | Median ns/message | Min–max |',
         '|---|---|---:|---:|---:|---:|']
for r in rows:
    lines.append(f"| {r['engine']} | {r['mode']} | {r['capacity']} | {r['workers']} | "
                 f"{r['median_ns']:.1f} | {r['min_ns']:.1f}–{r['max_ns']:.1f} |")
(a.out / 'table.md').write_text('\n'.join(lines) + '\n')
meta['completed'] = True
(a.out / 'metadata.json').write_text(json.dumps(meta, indent=2) + '\n')
print('\n'.join(lines))
