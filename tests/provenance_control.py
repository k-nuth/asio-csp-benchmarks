"""Exercise source/binary provenance checks using real C++/Go/Rust builds."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument('out', type=Path)
p.add_argument('--asio-root', type=Path, required=True)
p.add_argument('--go', required=True)
p.add_argument('--cxx', default=os.environ.get('CXX', 'c++'))
a = p.parse_args()
source = Path(__file__).resolve().parents[1]
out = a.out.resolve()
assert not out.exists(), 'use a fresh output directory'
fixture = out / 'fixture'
shutil.copytree(source, fixture, ignore=shutil.ignore_patterns('.git', 'target', 'build', '__pycache__'))
build = out / 'build'
with (out / 'build.log').open('w') as log:
    subprocess.run(['python3', 'bench/build.py', '--asio-root', str(a.asio_root.resolve()),
                    '--out', str(build), '--go', a.go, '--cxx', a.cxx], cwd=fixture,
                   stdout=log, stderr=subprocess.STDOUT, check=True)

def run(label, expected, message=None):
    cmd = ['python3', 'bench/run.py', '--asio-root', str(a.asio_root.resolve()),
           '--bin-dir', str(build), '--engines', 'asio', '--n', '1', '--repeats', '1',
           '--out', str(out / label)]
    result = subprocess.run(cmd, cwd=fixture, capture_output=True, text=True, timeout=30)
    (out / (label + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == expected, (label, result.stdout, result.stderr)
    if message:
        assert message in result.stderr, (label, result.stderr)

run('valid', 0)
files = [fixture / 'bench/build.py', fixture / 'bench/rust/Cargo.toml', build / 'asio-bench', build / 'build.json']
original = {file: file.read_bytes() for file in files}
try:
    files[0].write_bytes(original[files[0]].replace(b"'-O3'", b"'-O2'"))
    run('flags', 2, 'source differs from build metadata')
    files[0].write_bytes(original[files[0]])
    files[1].write_bytes(original[files[1]] + b'\n[profile.release]\nopt-level = 0\n')
    run('manifest', 2, 'source differs from build metadata')
    files[1].write_bytes(original[files[1]])
    files[2].write_bytes(original[files[2]] + b'changed')
    run('binary', 2, 'binary differs from build metadata')
    files[2].write_bytes(original[files[2]])
    # Metadata written by an earlier harness (the in-tree pipeline recorded
    # schema_version 2) must be rejected rather than partially trusted.
    files[3].write_bytes(original[files[3]].replace(b'"schema_version": 3', b'"schema_version": 2'))
    run('legacy-metadata', 2, 'old or unsupported build metadata')
finally:
    for file, content in original.items():
        file.write_bytes(content)
assert all(hashlib.sha256(file.read_bytes()).digest() == hashlib.sha256(content).digest()
           for file, content in original.items())
print('Real build accepted; changed flags, manifest, binary and legacy metadata rejected; fixture restored')
