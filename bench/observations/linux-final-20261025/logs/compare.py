#!/usr/bin/env python3
"""Compare a new observation set with linux-v4-fixed: medians, spans, ratios to the best applicable Rust engine, deltas."""
import json
import statistics
import sys
from pathlib import Path

new_dir, old_dir = Path(sys.argv[1]), Path(sys.argv[2])
scenarios = [('ready', 1, 1), ('mixed', 1, 1), ('fanin', 0, 1), ('fanin', 0, 4),
             ('fanin', 1, 1), ('fanin', 1, 4), ('fanin', 64, 1), ('fanin', 64, 4)]

def load(d):
    raw = json.loads((d / 'raw.json').read_text())
    by = {}
    for r in raw:
        by.setdefault((r['engine'], r['mode'], r['capacity'], r['workers']), []).append(r['ns_per_message'])
    return raw, by

new_raw, new = load(new_dir)
old_raw, old = load(old_dir)
meta = json.loads((new_dir / 'metadata.json').read_text())
print(f"samples: new {len(new_raw)} (expected {meta['expected_samples']}, completed {meta['completed']}), old {len(old_raw)}")

def med(by, e, s):
    v = by.get((e,) + s)
    return statistics.median(v) if v else None

def span(by, e, s):
    v = by.get((e,) + s)
    return max(v) / min(v) if v else None

def label(m, c, w):
    return f"{m}, cap {c}, {w} worker{'s' if w > 1 else ''}" if m == 'fanin' else f"{m}, {w} worker"

def ratio_text(x, by, s):
    rust = {e: med(by, e, s) for e in ('tokio', 'crossbeam') if med(by, e, s)}
    if x is None or not rust:
        g = med(by, 'go', s)
        return f"none ({x / g:.2f} vs Go)" if x and g else "none"
    best = min(rust, key=rust.get)
    txt = f"{x / rust[best]:.2f} ({best.capitalize()})"
    other = [e for e in rust if e != best]
    if other:
        txt += f", {x / rust[other[0]]:.2f} vs {other[0].capitalize()}"
    return txt

print("\n## Main comparison (median ns/message, lower is better)\n")
print("| Scenario | C++ v3 | C++ one-shot | C++ selector | Go | Tokio | Crossbeam | Selector / best Rust | One-shot / best Rust |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
for s in scenarios:
    f = lambda e: (lambda v: f"{v:.1f}" if v else "none")(med(new, e, s))
    print(f"| {label(*s)} | {f('asio-v3')} | {f('asio')} | {f('asio-reusable')} | {f('go')} | {f('tokio')} | {f('crossbeam')} | "
          f"{ratio_text(med(new, 'asio-reusable', s), new, s)} | {ratio_text(med(new, 'asio', s), new, s)} |")

print("\n## Every engine: median (min–max), span max/min, change vs linux-v4-fixed\n")
print("| Engine | Scenario | Median | Min–max | Span | v4-fixed median | Change |")
print("|---|---|---:|---:|---:|---:|---:|")
engines = []
for r in new_raw:
    if r['engine'] not in engines:
        engines.append(r['engine'])
for e in engines:
    for s in scenarios:
        v = new.get((e,) + s)
        if not v:
            continue
        o = med(old, e, s)
        chg = f"{(statistics.median(v) / o - 1) * 100:+.1f}%" if o else "n/a"
        print(f"| {e} | {label(*s)} | {statistics.median(v):.1f} | {min(v):.1f}–{max(v):.1f} | {max(v) / min(v):.2f} | "
              f"{o:.1f} | {chg}" if o else f"| {e} | {label(*s)} | {statistics.median(v):.1f} | {min(v):.1f}–{max(v):.1f} | {max(v) / min(v):.2f} | n/a | n/a |")

print("\n## Parity check (selector and one-shot vs best applicable Rust: median ratio, and slowest sample vs fastest Rust sample)\n")
print("| Scenario | Engine | Best Rust | Median ratio | Worst-case ratio (max C++ / min Rust) | Verdict (<= 1.05 on medians) |")
print("|---|---|---|---:|---:|---|")
for s in scenarios:
    rust = {e: med(new, e, s) for e in ('tokio', 'crossbeam') if med(new, e, s)}
    if not rust:
        continue
    best = min(rust, key=rust.get)
    for e in ('asio-reusable', 'asio'):
        v = new[(e,) + s]
        rv = new[(best,) + s]
        mr = statistics.median(v) / rust[best]
        wr = max(v) / min(rv)
        print(f"| {label(*s)} | {e} | {best} | {mr:.3f} | {wr:.2f} | {'met' if mr <= 1.05 else 'not met'} |")

print("\n## Unsupported scenarios\n")
print("- tokio: fanin with capacity 0 (bounded MPSC requires capacity >= 1) -> no sample; 'none' above.")
print("- crossbeam: fanin with 1 worker (blocking sends need the four-thread topology) -> no sample; 'none' above.")
