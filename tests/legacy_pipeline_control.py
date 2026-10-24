#!/usr/bin/env python3
"""Retained original pipeline RED: the frozen c834f8b scripts accept stale binaries.

The original in-tree build/run scripts (frozen byte-for-byte in
bench/reference/build-original.py and run-original.py) recorded only a few
source hashes and no binary hashes, so after changing Cargo's release profile
or the C++ optimization flag they still ran the existing binaries as if the
inputs were unchanged. This control rebuilds that pipeline with the real
C++/Go/Cargo toolchains inside a disposable shared clone of the Asio history
(a revision whose tree still carries the in-tree csp/bench layout the originals
expect), changes the manifest and the flag after building, and shows the
original runner accepting the stale binaries (exit 0 with full progress).

The current pipeline's rejection of the same changes, of changed binaries and
of legacy metadata is covered by tests/provenance_control.py on the current
layout; both controls use the same toolchains. Production inputs are never
edited; the clone is disposable.

Usage: python3 tests/legacy_pipeline_control.py OUTPUT_DIRECTORY \
           --asio-root /path/to/asio --go /path/to/go [--cxx c++] [--rev e663a273]
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument('out', type=Path)
p.add_argument('--asio-root', type=Path, required=True, help='Asio git checkout; cloned, never modified')
p.add_argument('--go', required=True)
p.add_argument('--cxx', default=os.environ.get('CXX', 'c++'))
p.add_argument('--rev', default='e663a273eafa2db4be598fdf8b53eb79eddd1332',
               help='revision whose tree carries the in-tree csp/bench layout')
a = p.parse_args()
benchmarks = Path(__file__).resolve().parents[1]
originals = {name: benchmarks / 'bench/reference' / (name.replace('.py', '-original.py'))
             for name in ('build.py', 'run.py')}
frozen = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in originals.items()}
out = a.out.resolve()
assert not out.exists(), 'use a fresh output directory'
out.mkdir(parents=True)
fixture = out / 'original-pipeline'
subprocess.run(['git', 'clone', '--shared', '--quiet', str(a.asio_root.resolve()), str(fixture)], check=True)
subprocess.run(['git', '-C', str(fixture), 'checkout', '--quiet', a.rev], check=True)
assert (fixture / 'csp/bench/select.cpp').is_file(), 'revision lacks the in-tree csp/bench layout'
for name, path in originals.items():
    shutil.copy2(path, fixture / 'csp/bench' / name)
env = dict(os.environ, PATH=str(Path.home() / '.cargo/bin') + os.pathsep + os.environ.get('PATH', ''))
with (out / 'build.log').open('w') as log:
    subprocess.run(['python3', 'csp/bench/build.py', '--cxx', a.cxx, '--go', a.go],
                   cwd=fixture, stdout=log, stderr=subprocess.STDOUT, check=True, env=env)
for target in ('manifest', 'flags'):
    file = fixture / ('csp/bench/rust/Cargo.toml' if target == 'manifest' else 'csp/bench/build.py')
    before = file.read_text()
    changed = (before + '\n[profile.release]\nopt-level = 0\n' if target == 'manifest'
               else before.replace("'-O3'", "'-O2'"))
    assert changed != before
    file.write_text(changed)
    try:
        engine = 'tokio' if target == 'manifest' else 'asio'
        progress = '6/6' if target == 'manifest' else '8/8'
        run = subprocess.run(['python3', 'csp/bench/run.py', '--engines', engine, '--n', '1', '--repeats', '1',
                              '--out', str(out / (target + '-observations'))],
                             cwd=fixture, capture_output=True, text=True, timeout=120, env=env)
        text = run.stdout + run.stderr
        (out / (target + '.log')).write_text(text + '\nexit=' + str(run.returncode) + '\n')
        # RED: the original runner accepts the binaries built before the change.
        assert run.returncode == 0 and progress in text, text
    finally:
        file.write_text(before)
# The frozen originals themselves were not touched.
assert all(hashlib.sha256(path.read_bytes()).hexdigest() == frozen[name] for name, path in originals.items())
print('Original pipeline RED: stale binaries accepted after the manifest and flag changes '
      '(frozen scripts ' + ', '.join(f'{n} {h[:16]}' for n, h in frozen.items()) + '); '
      'the current pipeline\'s rejection is tests/provenance_control.py')
