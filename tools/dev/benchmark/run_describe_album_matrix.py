#!/usr/bin/env python3

import argparse
import csv
import datetime as dt
import os
import shlex
import subprocess
import sys
from pathlib import Path


def parse_summary_value(summary_path: Path, key: str, suffix: str) -> str:
    if not summary_path.exists():
        return "NA"
    for line in summary_path.read_text(errors="ignore").splitlines():
        if line.startswith(f"- {key}:"):
            val = line.split(":", 1)[1].strip()
            if suffix and val.endswith(suffix):
                val = val[: -len(suffix)].strip()
            return val or "NA"
    return "NA"


def parse_runtime_tps(runtime_path: Path) -> str:
    if not runtime_path.exists():
        return "NA"
    with runtime_path.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2 and row[0] == "tokens_per_second":
                return row[1] or "NA"
    return "NA"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch benchmark matrix for describe_workspace_album.py with multiple ctx/thread combos."
    )
    parser.add_argument("album_id", nargs="?", default="39")
    parser.add_argument("sample_count", nargs="?", default="5")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    album_id = args.album_id
    sample_count = args.sample_count

    interval = os.getenv("INTERVAL", "1")
    gpu_layers = os.getenv("GPU_LAYERS", "999")
    ctx_list = os.getenv("CTX_LIST", "2048 4096 8192").split()
    threads_list = os.getenv("THREADS_LIST", "4 8 12").split()
    model_name = os.getenv("MODEL_NAME", "Qwen2.5-VL-7B-Instruct-BF16.gguf")
    mmproj_name = os.getenv("MMPROJ_NAME", "mmproj-BF16.gguf")
    extra_args = os.getenv("EXTRA_ARGS", "--max-tokens 800 --temperature 0.2 --image-max-tokens 384")

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(f"tools/benchmark/runs_{stamp}")
    out_dir.mkdir(parents=True, exist_ok=True)

    results_csv = out_dir / "matrix_results.csv"
    run_log = out_dir / "matrix_run.log"

    headers = [
        "run_id",
        "album_id",
        "sample_count",
        "ctx_size",
        "threads",
        "gpu_layers",
        "duration_s",
        "avg_cpu_pct",
        "avg_gpu_pct",
        "peak_memory_gb",
        "peak_swap_gb",
        "peak_rss_gb",
        "peak_compressed_gb",
        "peak_disk_read_mbs",
        "peak_disk_write_mbs",
        "peak_gpu_memory_gb",
        "avg_tokens_per_sec",
        "csv_path",
        "summary_path",
        "runtime_path",
        "events_path",
        "json_output_path",
    ]

    with results_csv.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(headers)

    with run_log.open("w", encoding="utf-8") as logf:
        logf.write(f"Batch started at {dt.datetime.now():%Y-%m-%d %H:%M:%S}\n")
        logf.write(f"OUT_DIR={out_dir}\n")

    run_idx = 0
    for ctx in ctx_list:
        for th in threads_list:
            run_idx += 1
            run_id = f"run{run_idx:02d}_c{ctx}_t{th}"

            base = out_dir / run_id
            bench_csv = Path(f"{base}.csv")
            summary_md = Path(f"{base}_summary.md")
            runtime_csv = Path(f"{base}_llama_runtime.csv")
            events_log = Path(f"{base}_events.log")
            llama_log = Path(f"{base}_llama.log")
            json_out = Path(f"{base}_describe_output.json")

            ts = dt.datetime.now().strftime("%H:%M:%S")
            with run_log.open("a", encoding="utf-8") as logf:
                logf.write(f"[{ts}] START {run_id}\n")

            describe_cmd = (
                f"python3 scripts/describe_workspace_album.py {shlex.quote(album_id)} {shlex.quote(sample_count)} "
                f"--ctx-size {shlex.quote(ctx)} --threads {shlex.quote(th)} --gpu-layers {shlex.quote(gpu_layers)} "
                f"{extra_args} > {shlex.quote(str(json_out))}"
            )

            cmd = [
                "python3",
                "tools/benchmark/macos_llm_benchmark.py",
                "-x",
                describe_cmd,
                "-i",
                interval,
                "-o",
                str(bench_csv),
                "--events-log",
                str(events_log),
                "--summary-md",
                str(summary_md),
                "--llama-log",
                str(llama_log),
                "--llama-runtime-csv",
                str(runtime_csv),
                "--model",
                model_name,
                "--mmproj",
                mmproj_name,
                "--ctx-size",
                ctx,
                "--threads",
                th,
                "--gpu-layers",
                gpu_layers,
            ]

            ret = subprocess.run(cmd)
            if ret.returncode != 0:
                print(f"Run failed: {run_id}", file=sys.stderr)
                return ret.returncode

            duration = parse_summary_value(summary_md, "Duration", "s")
            avg_cpu = parse_summary_value(summary_md, "Average CPU", "%")
            avg_gpu = parse_summary_value(summary_md, "Average GPU", "%")
            peak_mem = parse_summary_value(summary_md, "Peak Memory Used", "GB")
            peak_swap = parse_summary_value(summary_md, "Peak Swap", "GB")
            peak_rss = parse_summary_value(summary_md, "Peak RSS", "GB")
            peak_comp = parse_summary_value(summary_md, "Peak Compressed Memory", "GB")
            peak_read = parse_summary_value(summary_md, "Peak Disk Read", "MB/s")
            peak_write = parse_summary_value(summary_md, "Peak Disk Write", "MB/s")
            peak_gpu_mem = parse_summary_value(summary_md, "Peak GPU Memory", "GB")
            avg_tps = parse_runtime_tps(runtime_csv)

            row = [
                run_id,
                album_id,
                sample_count,
                ctx,
                th,
                gpu_layers,
                duration,
                avg_cpu,
                avg_gpu,
                peak_mem,
                peak_swap,
                peak_rss,
                peak_comp,
                peak_read,
                peak_write,
                peak_gpu_mem,
                avg_tps,
                str(bench_csv),
                str(summary_md),
                str(runtime_csv),
                str(events_log),
                str(json_out),
            ]

            with results_csv.open("a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(row)

            ts = dt.datetime.now().strftime("%H:%M:%S")
            with run_log.open("a", encoding="utf-8") as logf:
                logf.write(f"[{ts}] DONE  {run_id}\n")

    markdown_report = out_dir / "matrix_report.md"

    rows: list[list[str]] = []
    with results_csv.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append([
                r["run_id"],
                r["ctx_size"],
                r["threads"],
                r["duration_s"],
                r["avg_cpu_pct"],
                r["avg_gpu_pct"],
                r["peak_memory_gb"],
                r["peak_swap_gb"],
                r["peak_disk_write_mbs"],
                r["avg_tokens_per_sec"],
            ])

    report_lines = [
        "# Describe Album Benchmark Matrix",
        "",
        f"- Album ID: {album_id}",
        f"- Sample Count: {sample_count}",
        f"- GPU Layers: {gpu_layers}",
        f"- Interval: {interval}s",
        f"- Started: {stamp}",
        "",
        "## Result Table",
        "",
        "| run_id | ctx | threads | duration(s) | avg_cpu(%) | avg_gpu(%) | peak_mem(GB) | peak_swap(GB) | peak_disk_write(MB/s) | avg_tps |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        report_lines.append(
            f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]} | {row[8]} | {row[9]} |"
        )

    report_lines.extend([
        "",
        "## Files",
        "",
        f"- Raw matrix CSV: {results_csv}",
        f"- Run log: {run_log}",
        "",
    ])

    markdown_report.write_text("\n".join(report_lines), encoding="utf-8")

    print("")
    print("Batch finished.")
    print(f"Results CSV: {results_csv}")
    print(f"Markdown report: {markdown_report}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
