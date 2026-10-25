#!/usr/bin/env bash
# Linux final series: build all engines against the final Asio working tree (host GCC 16.1), then the default 15-engine comparison,
# n=300000, 7 repeats, taskset -c 0-3. Nothing else is compiled or sanitized while timing runs.
set -u
RUN=/home/fernando/.local/share/kth-asio-bench/runs/resume-20261025
GO=/home/fernando/.local/share/kth-asio-bench/toolchains/go1.27.3/go/bin/go
OUT=$RUN/benchmarks/bench/observations/linux-final-20261025
BUILD=$RUN/bench-build
LOG=$RUN/work/logs
export PATH=$HOME/.cargo/bin:$PATH
cd $RUN/benchmarks
echo "build start $(date -u +%FT%TZ)"
python3 bench/build.py --asio-root $RUN/source --out $BUILD --cxx g++ --go $GO > $LOG/bench-build.log 2>&1; b=$?
echo "build exit=$b end $(date -u +%FT%TZ)"
[ $b -eq 0 ] || { echo "BUILD FAILED; series not started"; exit 1; }
sha256sum $BUILD/*-bench bench/rust/target/release/select-bench > $LOG/bench-binaries.sha256
$RUN/work/sysactivity.sh before-series > $LOG/bench-sysactivity.log 2>&1
# light sampler: loadavg and non-benchmark CPU consumers every 20 s during the series
( while true; do echo "$(date -u +%FT%TZ) $(cat /proc/loadavg) | $(ps -eo pcpu,comm --sort=-pcpu | awk 'NR>1 && $1>2.0 && $2 !~ /bench|select-bench/ {printf "%s:%s ", $2, $1}')"; sleep 20; done ) > $LOG/bench-load-sampler.log 2>&1 &
SAMPLER=$!
echo "series start $(date -u +%FT%TZ)"
taskset -c 0-3 python3 bench/run.py --asio-root $RUN/source --bin-dir $BUILD --n 300000 --repeats 7 --out $OUT > $LOG/bench-series.log 2>&1; r=$?
echo "series exit=$r end $(date -u +%FT%TZ)"
kill $SAMPLER 2>/dev/null
$RUN/work/sysactivity.sh after-series >> $LOG/bench-sysactivity.log 2>&1
echo BENCH-SERIES-DONE
