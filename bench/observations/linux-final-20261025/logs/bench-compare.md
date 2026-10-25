samples: new 805 (expected 805, completed True), old 805

## Main comparison (median ns/message, lower is better)

| Scenario | C++ v3 | C++ one-shot | C++ selector | Go | Tokio | Crossbeam | Selector / best Rust | One-shot / best Rust |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ready, 1 worker | 52.5 | 44.7 | 30.7 | 59.9 | 51.8 | 28.5 | 1.08 (Crossbeam), 0.59 vs Tokio | 1.57 (Crossbeam), 0.86 vs Tokio |
| mixed, 1 worker | 52.7 | 44.3 | 36.9 | 59.6 | 47.4 | 29.8 | 1.24 (Crossbeam), 0.78 vs Tokio | 1.48 (Crossbeam), 0.94 vs Tokio |
| fanin, cap 0, 1 worker | 341.4 | 258.6 | 108.4 | 154.1 | none | none | none (0.70 vs Go) | none (1.68 vs Go) |
| fanin, cap 0, 4 workers | 569.8 | 532.9 | 326.7 | 140.6 | none | 465.3 | 0.70 (Crossbeam) | 1.15 (Crossbeam) |
| fanin, cap 1, 1 worker | 227.9 | 181.5 | 82.3 | 148.7 | 147.2 | none | 0.56 (Tokio) | 1.23 (Tokio) |
| fanin, cap 1, 4 workers | 453.7 | 378.7 | 206.0 | 114.1 | 216.5 | 81.2 | 2.54 (Crossbeam), 0.95 vs Tokio | 4.66 (Crossbeam), 1.75 vs Tokio |
| fanin, cap 64, 1 worker | 84.3 | 87.6 | 45.1 | 61.1 | 52.5 | none | 0.86 (Tokio) | 1.67 (Tokio) |
| fanin, cap 64, 4 workers | 114.8 | 130.6 | 64.0 | 80.7 | 43.9 | 60.9 | 1.46 (Tokio), 1.05 vs Crossbeam | 2.97 (Tokio), 2.14 vs Crossbeam |

## Every engine: median (min–max), span max/min, change vs linux-v4-fixed

| Engine | Scenario | Median | Min–max | Span | v4-fixed median | Change |
|---|---|---:|---:|---:|---:|---:|
| asio-baseline | ready, 1 worker | 674.2 | 673.1–855.2 | 1.27 | 712.8 | -5.4%
| asio-baseline | mixed, 1 worker | 677.4 | 668.9–843.3 | 1.26 | 718.6 | -5.7%
| asio-baseline | fanin, cap 0, 1 worker | 1475.8 | 1463.9–1847.3 | 1.26 | 1662.8 | -11.2%
| asio-baseline | fanin, cap 0, 4 workers | 2973.6 | 2940.3–3249.9 | 1.11 | 2982.0 | -0.3%
| asio-baseline | fanin, cap 1, 1 worker | 1395.9 | 1389.3–1420.0 | 1.02 | 1539.6 | -9.3%
| asio-baseline | fanin, cap 1, 4 workers | 2719.7 | 2695.9–2954.3 | 1.10 | 2735.8 | -0.6%
| asio-baseline | fanin, cap 64, 1 worker | 1407.6 | 1393.0–1747.7 | 1.25 | 1549.6 | -9.2%
| asio-baseline | fanin, cap 64, 4 workers | 2687.9 | 2675.1–3220.7 | 1.20 | 2680.3 | +0.3%
| asio-v3 | ready, 1 worker | 52.5 | 51.7–63.8 | 1.23 | 52.2 | +0.6%
| asio-v3 | mixed, 1 worker | 52.7 | 52.2–63.9 | 1.22 | 52.3 | +0.7%
| asio-v3 | fanin, cap 0, 1 worker | 341.4 | 333.2–412.6 | 1.24 | 320.7 | +6.4%
| asio-v3 | fanin, cap 0, 4 workers | 569.8 | 561.7–694.3 | 1.24 | 564.9 | +0.9%
| asio-v3 | fanin, cap 1, 1 worker | 227.9 | 227.2–281.2 | 1.24 | 220.2 | +3.5%
| asio-v3 | fanin, cap 1, 4 workers | 453.7 | 351.2–454.7 | 1.29 | 347.8 | +30.5%
| asio-v3 | fanin, cap 64, 1 worker | 84.3 | 84.1–85.1 | 1.01 | 82.9 | +1.7%
| asio-v3 | fanin, cap 64, 4 workers | 114.8 | 114.1–144.3 | 1.26 | 114.8 | -0.0%
| asio-v2-reuse | ready, 1 worker | 80.6 | 77.7–96.2 | 1.24 | 78.0 | +3.4%
| asio-v2-reuse | mixed, 1 worker | 79.3 | 78.4–97.4 | 1.24 | 79.4 | -0.2%
| asio-v2-reuse | fanin, cap 0, 1 worker | 603.4 | 598.4–607.1 | 1.01 | 611.7 | -1.4%
| asio-v2-reuse | fanin, cap 0, 4 workers | 970.1 | 960.1–1091.5 | 1.14 | 973.4 | -0.3%
| asio-v2-reuse | fanin, cap 1, 1 worker | 505.7 | 410.0–511.2 | 1.25 | 412.9 | +22.5%
| asio-v2-reuse | fanin, cap 1, 4 workers | 414.8 | 411.9–514.7 | 1.25 | 417.4 | -0.6%
| asio-v2-reuse | fanin, cap 64, 1 worker | 135.9 | 135.4–166.8 | 1.23 | 134.2 | +1.3%
| asio-v2-reuse | fanin, cap 64, 4 workers | 300.8 | 276.9–391.3 | 1.41 | 315.2 | -4.6%
| asio-reusable | ready, 1 worker | 30.7 | 30.3–38.1 | 1.26 | 30.3 | +1.2%
| asio-reusable | mixed, 1 worker | 36.9 | 29.3–38.0 | 1.30 | 32.1 | +15.2%
| asio-reusable | fanin, cap 0, 1 worker | 108.4 | 108.3–108.5 | 1.00 | 106.8 | +1.5%
| asio-reusable | fanin, cap 0, 4 workers | 326.7 | 316.9–404.6 | 1.28 | 320.3 | +2.0%
| asio-reusable | fanin, cap 1, 1 worker | 82.3 | 80.9–102.3 | 1.27 | 81.4 | +1.1%
| asio-reusable | fanin, cap 1, 4 workers | 206.0 | 201.4–262.4 | 1.30 | 205.0 | +0.5%
| asio-reusable | fanin, cap 64, 1 worker | 45.1 | 44.5–55.6 | 1.25 | 44.5 | +1.3%
| asio-reusable | fanin, cap 64, 4 workers | 64.0 | 63.6–83.3 | 1.31 | 64.1 | -0.3%
| go | ready, 1 worker | 59.9 | 58.8–74.5 | 1.27 | 59.8 | +0.2%
| go | mixed, 1 worker | 59.6 | 58.9–74.9 | 1.27 | 60.7 | -1.8%
| go | fanin, cap 0, 1 worker | 154.1 | 153.7–154.6 | 1.01 | 154.1 | -0.0%
| go | fanin, cap 0, 4 workers | 140.6 | 140.0–180.5 | 1.29 | 141.1 | -0.3%
| go | fanin, cap 1, 1 worker | 148.7 | 122.0–154.4 | 1.27 | 122.7 | +21.2%
| go | fanin, cap 1, 4 workers | 114.1 | 113.9–147.2 | 1.29 | 114.2 | -0.1%
| go | fanin, cap 64, 1 worker | 61.1 | 60.9–76.2 | 1.25 | 62.2 | -1.7%
| go | fanin, cap 64, 4 workers | 80.7 | 63.4–81.5 | 1.29 | 64.7 | +24.8%
| asio | ready, 1 worker | 44.7 | 44.2–55.1 | 1.24 | 44.5 | +0.5%
| asio | mixed, 1 worker | 44.3 | 43.6–54.1 | 1.24 | 43.5 | +1.8%
| asio | fanin, cap 0, 1 worker | 258.6 | 257.4–327.8 | 1.27 | 258.3 | +0.1%
| asio | fanin, cap 0, 4 workers | 532.9 | 529.6–638.0 | 1.20 | 529.8 | +0.6%
| asio | fanin, cap 1, 1 worker | 181.5 | 179.4–221.9 | 1.24 | 177.4 | +2.3%
| asio | fanin, cap 1, 4 workers | 378.7 | 298.1–381.8 | 1.28 | 303.1 | +24.9%
| asio | fanin, cap 64, 1 worker | 87.6 | 71.1–88.4 | 1.24 | 71.5 | +22.5%
| asio | fanin, cap 64, 4 workers | 130.6 | 104.8–135.1 | 1.29 | 102.8 | +27.1%
| asio-v2 | ready, 1 worker | 77.2 | 75.7–93.2 | 1.23 | 75.8 | +1.9%
| asio-v2 | mixed, 1 worker | 78.2 | 75.8–92.2 | 1.22 | 77.4 | +1.0%
| asio-v2 | fanin, cap 0, 1 worker | 622.5 | 619.2–624.8 | 1.01 | 611.7 | +1.8%
| asio-v2 | fanin, cap 0, 4 workers | 966.8 | 956.4–1017.5 | 1.06 | 953.3 | +1.4%
| asio-v2 | fanin, cap 1, 1 worker | 416.4 | 414.7–417.7 | 1.01 | 412.0 | +1.1%
| asio-v2 | fanin, cap 1, 4 workers | 462.0 | 445.9–577.2 | 1.29 | 457.4 | +1.0%
| asio-v2 | fanin, cap 64, 1 worker | 164.0 | 133.4–166.6 | 1.25 | 132.6 | +23.6%
| asio-v2 | fanin, cap 64, 4 workers | 375.8 | 338.3–487.6 | 1.44 | 364.8 | +3.0%
| tokio | ready, 1 worker | 51.8 | 40.4–53.3 | 1.32 | 41.0 | +26.4%
| tokio | mixed, 1 worker | 47.4 | 45.8–61.2 | 1.34 | 47.4 | +0.0%
| tokio | fanin, cap 1, 1 worker | 147.2 | 146.1–185.0 | 1.27 | 146.8 | +0.3%
| tokio | fanin, cap 1, 4 workers | 216.5 | 213.3–277.8 | 1.30 | 215.9 | +0.3%
| tokio | fanin, cap 64, 1 worker | 52.5 | 51.9–68.1 | 1.31 | 52.2 | +0.5%
| tokio | fanin, cap 64, 4 workers | 43.9 | 43.6–54.7 | 1.26 | 44.1 | -0.4%
| asio-v1 | ready, 1 worker | 78.6 | 77.8–93.5 | 1.20 | 79.1 | -0.7%
| asio-v1 | mixed, 1 worker | 81.8 | 78.8–97.6 | 1.24 | 79.1 | +3.4%
| asio-v1 | fanin, cap 0, 1 worker | 623.1 | 622.0–772.8 | 1.24 | 624.0 | -0.2%
| asio-v1 | fanin, cap 0, 4 workers | 1167.8 | 970.2–1175.9 | 1.21 | 977.5 | +19.5%
| asio-v1 | fanin, cap 1, 1 worker | 418.9 | 415.6–452.8 | 1.09 | 418.8 | +0.0%
| asio-v1 | fanin, cap 1, 4 workers | 454.7 | 444.2–587.4 | 1.32 | 459.9 | -1.1%
| asio-v1 | fanin, cap 64, 1 worker | 137.1 | 135.7–168.0 | 1.24 | 137.3 | -0.2%
| asio-v1 | fanin, cap 64, 4 workers | 371.4 | 360.7–492.3 | 1.36 | 373.3 | -0.5%
| asio-v3-reuse | ready, 1 worker | 51.3 | 50.7–64.8 | 1.28 | 51.2 | +0.2%
| asio-v3-reuse | mixed, 1 worker | 51.7 | 51.4–63.7 | 1.24 | 51.3 | +0.7%
| asio-v3-reuse | fanin, cap 0, 1 worker | 324.4 | 323.2–400.9 | 1.24 | 322.4 | +0.6%
| asio-v3-reuse | fanin, cap 0, 4 workers | 556.6 | 555.7–668.2 | 1.20 | 555.6 | +0.2%
| asio-v3-reuse | fanin, cap 1, 1 worker | 221.5 | 220.6–278.0 | 1.26 | 219.5 | +0.9%
| asio-v3-reuse | fanin, cap 1, 4 workers | 327.1 | 318.7–368.3 | 1.16 | 323.6 | +1.1%
| asio-v3-reuse | fanin, cap 64, 1 worker | 83.1 | 82.1–100.0 | 1.22 | 83.1 | -0.1%
| asio-v3-reuse | fanin, cap 64, 4 workers | 115.5 | 90.0–118.4 | 1.32 | 91.8 | +25.9%
| crossbeam | ready, 1 worker | 28.5 | 27.7–37.4 | 1.35 | 28.8 | -1.2%
| crossbeam | mixed, 1 worker | 29.8 | 29.7–31.1 | 1.05 | 30.5 | -2.3%
| crossbeam | fanin, cap 0, 4 workers | 465.3 | 456.8–545.2 | 1.19 | 459.5 | +1.3%
| crossbeam | fanin, cap 1, 4 workers | 81.2 | 80.5–105.0 | 1.30 | 83.3 | -2.4%
| crossbeam | fanin, cap 64, 4 workers | 60.9 | 59.0–76.2 | 1.29 | 58.0 | +5.0%
| asio-reuse | ready, 1 worker | 43.3 | 42.1–51.9 | 1.23 | 42.6 | +1.5%
| asio-reuse | mixed, 1 worker | 42.4 | 42.2–52.0 | 1.23 | 41.5 | +2.2%
| asio-reuse | fanin, cap 0, 1 worker | 306.8 | 248.2–308.3 | 1.24 | 250.4 | +22.5%
| asio-reuse | fanin, cap 0, 4 workers | 516.3 | 509.8–626.5 | 1.23 | 518.1 | -0.3%
| asio-reuse | fanin, cap 1, 1 worker | 172.5 | 171.7–212.6 | 1.24 | 172.8 | -0.2%
| asio-reuse | fanin, cap 1, 4 workers | 286.4 | 285.3–346.0 | 1.21 | 284.7 | +0.6%
| asio-reuse | fanin, cap 64, 1 worker | 70.3 | 69.0–71.3 | 1.03 | 69.7 | +0.9%
| asio-reuse | fanin, cap 64, 4 workers | 84.4 | 82.2–103.6 | 1.26 | 83.9 | +0.6%
| asio-v1-reuse | ready, 1 worker | 84.5 | 81.5–101.9 | 1.25 | 81.5 | +3.7%
| asio-v1-reuse | mixed, 1 worker | 80.8 | 79.0–98.7 | 1.25 | 79.9 | +1.2%
| asio-v1-reuse | fanin, cap 0, 1 worker | 661.1 | 659.3–831.7 | 1.26 | 650.5 | +1.6%
| asio-v1-reuse | fanin, cap 0, 4 workers | 983.2 | 970.2–1193.7 | 1.23 | 970.3 | +1.3%
| asio-v1-reuse | fanin, cap 1, 1 worker | 442.9 | 439.4–547.4 | 1.25 | 437.7 | +1.2%
| asio-v1-reuse | fanin, cap 1, 4 workers | 416.3 | 413.7–432.0 | 1.04 | 418.3 | -0.5%
| asio-v1-reuse | fanin, cap 64, 1 worker | 138.7 | 137.6–140.1 | 1.02 | 139.3 | -0.4%
| asio-v1-reuse | fanin, cap 64, 4 workers | 384.7 | 283.2–400.0 | 1.41 | 307.0 | +25.3%
| asio-v3-awaitable | ready, 1 worker | 78.6 | 78.0–97.2 | 1.25 | 79.0 | -0.6%
| asio-v3-awaitable | mixed, 1 worker | 79.5 | 78.8–96.0 | 1.22 | 77.9 | +2.0%
| asio-v3-awaitable | fanin, cap 0, 1 worker | 390.5 | 389.3–483.0 | 1.24 | 392.0 | -0.4%
| asio-v3-awaitable | fanin, cap 0, 4 workers | 617.7 | 612.5–792.4 | 1.29 | 628.6 | -1.7%
| asio-v3-awaitable | fanin, cap 1, 1 worker | 283.1 | 281.0–349.0 | 1.24 | 283.7 | -0.2%
| asio-v3-awaitable | fanin, cap 1, 4 workers | 429.8 | 425.2–551.1 | 1.30 | 431.7 | -0.4%
| asio-v3-awaitable | fanin, cap 64, 1 worker | 133.6 | 131.6–163.2 | 1.24 | 133.1 | +0.4%
| asio-v3-awaitable | fanin, cap 64, 4 workers | 170.1 | 135.2–170.6 | 1.26 | 136.4 | +24.7%
| asio-awaitable | ready, 1 worker | 72.1 | 70.4–87.2 | 1.24 | 70.1 | +2.9%
| asio-awaitable | mixed, 1 worker | 71.1 | 69.8–87.0 | 1.25 | 69.6 | +2.1%
| asio-awaitable | fanin, cap 0, 1 worker | 312.7 | 311.8–326.1 | 1.05 | 314.0 | -0.4%
| asio-awaitable | fanin, cap 0, 4 workers | 572.8 | 565.8–575.4 | 1.02 | 570.3 | +0.4%
| asio-awaitable | fanin, cap 1, 1 worker | 284.8 | 231.6–286.5 | 1.24 | 234.7 | +21.3%
| asio-awaitable | fanin, cap 1, 4 workers | 356.9 | 349.1–462.9 | 1.33 | 355.3 | +0.4%
| asio-awaitable | fanin, cap 64, 1 worker | 120.7 | 120.0–149.2 | 1.24 | 118.0 | +2.3%
| asio-awaitable | fanin, cap 64, 4 workers | 130.8 | 125.5–132.4 | 1.05 | 130.1 | +0.5%

## Parity check (selector and one-shot vs best applicable Rust: median ratio, and slowest sample vs fastest Rust sample)

| Scenario | Engine | Best Rust | Median ratio | Worst-case ratio (max C++ / min Rust) | Verdict (<= 1.05 on medians) |
|---|---|---|---:|---:|---|
| ready, 1 worker | asio-reusable | crossbeam | 1.078 | 1.38 | not met |
| ready, 1 worker | asio | crossbeam | 1.571 | 1.99 | not met |
| mixed, 1 worker | asio-reusable | crossbeam | 1.237 | 1.28 | not met |
| mixed, 1 worker | asio | crossbeam | 1.484 | 1.82 | not met |
| fanin, cap 0, 4 workers | asio-reusable | crossbeam | 0.702 | 0.89 | met |
| fanin, cap 0, 4 workers | asio | crossbeam | 1.145 | 1.40 | not met |
| fanin, cap 1, 1 worker | asio-reusable | tokio | 0.559 | 0.70 | met |
| fanin, cap 1, 1 worker | asio | tokio | 1.233 | 1.52 | not met |
| fanin, cap 1, 4 workers | asio-reusable | crossbeam | 2.536 | 3.26 | not met |
| fanin, cap 1, 4 workers | asio | crossbeam | 4.662 | 4.74 | not met |
| fanin, cap 64, 1 worker | asio-reusable | tokio | 0.858 | 1.07 | met |
| fanin, cap 64, 1 worker | asio | tokio | 1.668 | 1.70 | not met |
| fanin, cap 64, 4 workers | asio-reusable | tokio | 1.456 | 1.91 | not met |
| fanin, cap 64, 4 workers | asio | tokio | 2.972 | 3.10 | not met |

## Unsupported scenarios

- tokio: fanin with capacity 0 (bounded MPSC requires capacity >= 1) -> no sample; 'none' above.
- crossbeam: fanin with 1 worker (blocking sends need the four-thread topology) -> no sample; 'none' above.
