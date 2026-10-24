# Archived controls

`legacy_pipeline_control-intree-c834f8b.py` is the unmodified in-tree version of
the pipeline control (SHA256 `720ae168182d532c…`). It was written for the layout in
which the benchmark lived inside the library checkout as `csp/bench/`, cloned that
checkout with `git clone --shared`, and ran both the original `c834f8b` scripts
(`csp/bench/reference/*-original.py`, RED: stale binaries accepted) and the then
current in-tree scripts (GREEN: changed manifest, flags and legacy metadata
rejected) with the real toolchains. After the benchmark moved to this separate
repository its paths and the in-tree script interface no longer exist, so it
cannot run as written.

It is superseded by two controls on the current layout, both using the same real
C++/Go/Cargo toolchains:

- `tests/provenance_control.py`: the current pipeline (GREEN): a real build is
  accepted; a changed optimization flag, a changed Cargo manifest, a changed
  binary and legacy build metadata are each rejected before any measurement.
- `tests/legacy_pipeline_control.py`: the original pipeline (RED): the frozen
  `c834f8b` scripts, kept byte-for-byte in `bench/reference/`, are rebuilt in a
  disposable shared clone of a library revision that still carries the in-tree
  layout and shown to accept stale binaries after the same manifest and flag
  changes.

The archived file is kept as the record of the original control; it is not run.
