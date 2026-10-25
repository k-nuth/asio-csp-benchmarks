#!/usr/bin/env bash
# Snapshot of other system activity around a timing run: load, governor, top CPU consumers, benchmark-unrelated processes.
echo "=== $(date -u +%FT%TZ) $1"
echo "loadavg: $(cat /proc/loadavg)"
echo "governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null) driver: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver 2>/dev/null) epp: $(cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference 2>/dev/null) auto-cpufreq: $(systemctl is-active auto-cpufreq 2>/dev/null)"
echo "cpu0-3 MHz: $(grep MHz /proc/cpuinfo | head -4 | awk '{printf "%s ", $4}')"
echo "podman containers: $(podman ps -q 2>/dev/null | wc -l)"
echo "top processes by CPU (excluding this snapshot):"
ps -eo pid,pcpu,pmem,psr,etime,comm --sort=-pcpu | head -12
echo "processes with recent CPU not belonging to the benchmark:"
ps -eo pid,pcpu,comm --sort=-pcpu | awk 'NR>1 && $2>1.0 && $3 !~ /bench|select-bench|python3|taskset/' | head
