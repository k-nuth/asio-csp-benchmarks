#!/usr/bin/env bash
# Provenance and legacy-pipeline controls of the benchmark harness (compile-heavy; must finish before any timing).
RUN=/home/fernando/.local/share/kth-asio-bench/runs/resume-20261025
PRIOR=/home/fernando/.local/share/kth-asio-bench/runs/paired-r3-20261024-2058Z/asio
GO=/home/fernando/.local/share/kth-asio-bench/toolchains/go1.27.3/go/bin/go
export PATH=$HOME/.cargo/bin:$PATH
cd $RUN/benchmarks
echo "provenance start $(date -u +%FT%TZ)"
python3 tests/provenance_control.py $RUN/bench-controls/provenance --asio-root $RUN/source --go $GO --cxx g++ > $RUN/work/logs/bench-provenance-control.log 2>&1; echo "provenance exit=$? end $(date -u +%FT%TZ)"
# The frozen scripts need a revision with the in-tree csp/bench layout (e663a273), which this bundle's squashed history lacks;
# the previous run's checkout holds it and is used read-only as the clone source (git clone --shared).
echo "legacy start $(date -u +%FT%TZ)"
python3 tests/legacy_pipeline_control.py $RUN/bench-controls/legacy --asio-root $PRIOR --go $GO --cxx g++ > $RUN/work/logs/bench-legacy-pipeline-control.log 2>&1; echo "legacy exit=$? end $(date -u +%FT%TZ)"
git -C $PRIOR status --short | head -3; git -C $PRIOR rev-parse HEAD
echo BENCH-CONTROLS-DONE
