# Describe Album Benchmark Matrix

- Album ID: 39
- Sample Count: 5
- GPU Layers: 999
- Interval: 1s
- Started: 20260716_002106

## Result Table

| run_id | ctx | threads | duration(s) | avg_cpu(%) | avg_gpu(%) | peak_mem(GB) | peak_swap(GB) | peak_disk_write(MB/s) | avg_tps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| run01_c2048_t4 | 2048 | 4 | 33 | 14.49 | NA | 23.93 | 1.86 | 1.03 | NA |
| run02_c2048_t8 | 2048 | 8 | 29 | 16.35 | NA | 23.90 | 1.86 | 0.84 | NA |
| run03_c2048_t12 | 2048 | 12 | 28 | 16.65 | NA | 23.93 | 1.86 | 0.70 | NA |
| run04_c4096_t4 | 4096 | 4 | 46 | 18.27 | NA | 23.94 | 1.85 | 1.24 | NA |
| run05_c4096_t8 | 4096 | 8 | 40 | 14.90 | NA | 23.94 | 1.85 | 1.23 | NA |
| run06_c4096_t12 | 4096 | 12 | 38 | 13.81 | NA | 23.92 | 1.85 | 0.93 | NA |
| run07_c8192_t4 | 8192 | 4 | 41 | 14.55 | NA | 23.93 | 1.85 | 0.82 | NA |
| run08_c8192_t8 | 8192 | 8 | 37 | 14.72 | NA | 23.90 | 1.83 | 0.55 | NA |
| run09_c8192_t12 | 8192 | 12 | 44 | 14.23 | NA | 23.91 | 1.83 | 0.95 | NA |

## Files

- Raw matrix CSV: tools/benchmark/runs_20260716_002106/matrix_results.csv
- Run log: tools/benchmark/runs_20260716_002106/matrix_run.log
