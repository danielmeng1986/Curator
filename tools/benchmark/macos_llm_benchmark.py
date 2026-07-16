#!/usr/bin/env python3

import argparse
import csv
import datetime as dt
import os
import plistlib
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional


def run_cmd(cmd: list[str], text: bool = True) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=text)
        return out.strip() if text else out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def unit_to_bytes(value: float, unit: str) -> int:
    u = unit.upper()
    mul = 1
    if u in ("", "B"):
        mul = 1
    elif u in ("K", "KB"):
        mul = 1024
    elif u in ("M", "MB"):
        mul = 1024**2
    elif u in ("G", "GB"):
        mul = 1024**3
    elif u in ("T", "TB"):
        mul = 1024**4
    return int(round(value * mul))


def bytes_to_mb(value: int) -> str:
    return f"{value / 1024 / 1024:.2f}"


def bytes_to_gb(value: int) -> str:
    return f"{value / 1024 / 1024 / 1024:.2f}"


def is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False


def parse_vm_value(vm_text: str, key: str) -> int:
    for line in vm_text.splitlines():
        if line.startswith(f"{key}:"):
            digits = re.sub(r"[^0-9]", "", line)
            return int(digits or "0")
    return 0


def get_memory_metrics() -> dict[str, str]:
    total_mem = int(run_cmd(["sysctl", "-n", "hw.memsize"]) or "0")
    vm = run_cmd(["vm_stat"])

    m = re.search(r"page size of\s+(\d+) bytes", vm)
    page_size = int(m.group(1)) if m else 4096

    free_pages = parse_vm_value(vm, "Pages free")
    speculative_pages = parse_vm_value(vm, "Pages speculative")
    compressor_pages = parse_vm_value(vm, "Pages occupied by compressor")
    wired_pages = parse_vm_value(vm, "Pages wired down")
    active_pages = parse_vm_value(vm, "Pages active")
    inactive_pages = parse_vm_value(vm, "Pages inactive")
    file_backed_pages = parse_vm_value(vm, "File-backed pages")

    pageins = parse_vm_value(vm, "Pageins")
    pageouts = parse_vm_value(vm, "Pageouts")
    swapins = parse_vm_value(vm, "Swapins")
    swapouts = parse_vm_value(vm, "Swapouts")

    free_bytes = (free_pages + speculative_pages) * page_size
    used_bytes = max(total_mem - free_bytes, 0)
    compressed_bytes = compressor_pages * page_size
    wired_bytes = wired_pages * page_size
    active_bytes = active_pages * page_size
    inactive_bytes = inactive_pages * page_size
    cached_bytes = (file_backed_pages + speculative_pages) * page_size

    pressure_used = "NA"
    mp = run_cmd(["memory_pressure"])
    pm = re.search(r"System-wide memory free percentage:\s*([0-9.]+)%", mp)
    if pm:
        pressure_used = f"{100 - float(pm.group(1)):.2f}"

    swap_used = 0
    swap_line = run_cmd(["sysctl", "vm.swapusage"])
    sm = re.search(r"used\s*=\s*([0-9.]+)([KMGTP]?)(B)?", swap_line)
    if sm:
        swap_used = unit_to_bytes(float(sm.group(1)), f"{sm.group(2)}{sm.group(3) or ''}")

    return {
        "memory_total": str(total_mem),
        "memory_used": str(used_bytes),
        "memory_free": str(free_bytes),
        "memory_pressure": pressure_used,
        "swap_used": str(swap_used),
        "compressed_memory": str(compressed_bytes),
        "memory_wired": str(wired_bytes),
        "memory_active": str(active_bytes),
        "memory_inactive": str(inactive_bytes),
        "memory_cached": str(cached_bytes),
        "vm_pageins": str(pageins),
        "vm_pageouts": str(pageouts),
        "vm_swapins": str(swapins),
        "vm_swapouts": str(swapouts),
    }


def get_cpu_usage_total() -> str:
    line = run_cmd(["top", "-l", "1", "-n", "0"])
    for ln in line.splitlines():
        if "CPU usage" in ln:
            m = re.search(r"(\d+(?:\.\d+)?)%\s*idle", ln)
            if m:
                return f"{100 - float(m.group(1)):.2f}"
    return "NA"


def get_cpu_per_core() -> str:
    ncpu = int(run_cmd(["sysctl", "-n", "hw.ncpu"]) or "0")
    if ncpu <= 0:
        return "NA"
    out = run_cmd(["ps", "-A", "-o", "cpuid=", "-o", "%cpu="])
    sums = [0.0 for _ in range(ncpu)]
    for ln in out.splitlines():
        parts = ln.split()
        if len(parts) != 2:
            continue
        if parts[0].isdigit() and is_number(parts[1]):
            idx = int(parts[0])
            if 0 <= idx < ncpu:
                sums[idx] += float(parts[1])
    return ";".join(f"{min(v, 100.0):.2f}" for v in sums)


def get_gpu_usage() -> str:
    ioreg = run_cmd(["ioreg", "-r", "-d", "1", "-w", "0", "-c", "AGXAccelerator"])
    for ln in ioreg.splitlines():
        if any(k in ln for k in ["Device Utilization %", "GPU Busy", "GPU Core Utilization"]):
            num = re.sub(r"[^0-9.]", "", ln)
            if is_number(num):
                v = float(num)
                if 0 <= v <= 1:
                    v *= 100
                if 0 <= v <= 100:
                    return f"{v:.2f}"
    return "NA"


def parse_bytes_token(tok: str) -> int:
    tok = tok.strip()
    m = re.match(r"^([0-9.]+)\s*([KMGTP]?)$", tok)
    if not m:
        return 0
    return unit_to_bytes(float(m.group(1)), m.group(2))


def get_gpu_memory_bytes(pid: int) -> str:
    vmmap = run_cmd(["vmmap", "-summary", str(pid)])
    if not vmmap:
        return "NA"
    total = 0
    for ln in vmmap.splitlines():
        parts = ln.split()
        if len(parts) < 2:
            continue
        name = parts[0]
        if name in ("IOSurface", "IOAccelerator", "Metal") or re.match(r"MALLOC_.*GPU", name):
            total += parse_bytes_token(parts[1])
    return str(total) if total > 0 else "NA"


def get_disk_counters() -> tuple[int, int, int, int]:
    # Prefer APFS XML statistics because text mode can wrap and break key parsing.
    try:
        raw = subprocess.check_output(
            ["ioreg", "-r", "-c", "AppleAPFSContainer", "-k", "Statistics", "-a"],
            stderr=subprocess.DEVNULL,
        )
        nodes = plistlib.loads(raw)
        rb = wb = ro = wo = 0
        for node in nodes if isinstance(nodes, list) else []:
            stats = node.get("Statistics") if isinstance(node, dict) else None
            if not isinstance(stats, dict):
                continue
            rb += int(stats.get("Bytes read from block device", 0) or 0)
            wb += int(stats.get("Bytes written to block device", 0) or 0)
            ro += int(stats.get("Read requests sent to block device", 0) or 0)
            wo += int(stats.get("Write requests sent to block device", 0) or 0)
        if rb or wb or ro or wo:
            return (rb, wb, ro, wo)
    except Exception:
        pass

    io = run_cmd(["ioreg", "-r", "-c", "IOBlockStorageDriver", "-k", "Statistics"])
    if not io:
        return (0, 0, 0, 0)

    def sum_key(key: str) -> int:
        rgx = re.compile(rf'"{re.escape(key)}"\s*=\s*([0-9]+)')
        s = 0
        for ln in io.splitlines():
            m = rgx.search(ln)
            if m:
                s += int(m.group(1))
        return s

    rb = sum_key("Bytes (Read)")
    wb = sum_key("Bytes (Write)")
    ro = sum_key("Operations (Read)")
    wo = sum_key("Operations (Write)")
    return (rb, wb, ro, wo)


def get_process_metrics(pid: int) -> dict[str, str]:
    out = run_cmd(["ps", "-p", str(pid), "-o", "rss=", "-o", "vsz=", "-o", "%cpu=", "-o", "thcount="])
    parts = out.split()
    if len(parts) != 4:
        return {
            "proc_rss": "NA",
            "proc_vsz": "NA",
            "proc_cpu": "NA",
            "proc_threads": "NA",
        }

    rss = str(int(parts[0]) * 1024) if parts[0].isdigit() else "NA"
    vsz = str(int(parts[1]) * 1024) if parts[1].isdigit() else "NA"
    cpu = parts[2] if is_number(parts[2]) else "NA"
    th = parts[3] if parts[3].isdigit() else "NA"
    return {"proc_rss": rss, "proc_vsz": vsz, "proc_cpu": cpu, "proc_threads": th}


def collect_system_info() -> dict[str, str]:
    machine = ""
    sp = run_cmd(["system_profiler", "SPHardwareDataType"])
    for ln in sp.splitlines():
        if "Model Name:" in ln:
            machine = ln.split(":", 1)[1].strip()
            break
    if not machine:
        machine = run_cmd(["sysctl", "-n", "hw.model"]) or "Unknown"

    os_ver = run_cmd(["sw_vers", "-productVersion"]) or "Unknown"
    total_mem = run_cmd(["sysctl", "-n", "hw.memsize"]) or "0"

    cpu = ""
    for ln in sp.splitlines():
        if "Chip:" in ln:
            cpu = ln.split(":", 1)[1].strip()
            break
    if not cpu:
        cpu = run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"]) or "Unknown"

    gpu = ""
    dsp = run_cmd(["system_profiler", "SPDisplaysDataType"])
    for ln in dsp.splitlines():
        if "Chipset Model:" in ln:
            gpu = ln.split(":", 1)[1].strip()
            break
    if not gpu:
        gpu = "Apple GPU"

    return {
        "machine": machine,
        "os": os_ver,
        "total_mem": total_mem,
        "cpu": cpu,
        "gpu": gpu,
    }


def parse_llama_runtime_metrics(log_path: Path) -> dict[str, str]:
    metrics = {
        "model_load_time_ms": "NA",
        "prompt_eval_time_ms": "NA",
        "eval_time_ms": "NA",
        "total_generated_tokens": "NA",
        "tokens_per_second": "NA",
    }
    if not log_path.exists():
        return metrics

    text = log_path.read_text(errors="ignore")
    lines = text.splitlines()

    def find_last(pattern: str) -> Optional[str]:
        rgx = re.compile(pattern, re.IGNORECASE)
        for ln in reversed(lines):
            if rgx.search(ln):
                return ln
        return None

    line = find_last(r"load time|model load time")
    if line:
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*ms", line)
        if m:
            metrics["model_load_time_ms"] = m.group(1)
        else:
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*s([^a-zA-Z]|$)", line)
            if m:
                metrics["model_load_time_ms"] = f"{float(m.group(1)) * 1000:.2f}"

    line = find_last(r"prompt eval time")
    if line:
        m = re.search(r"=\s*([0-9]+(?:\.[0-9]+)?)\s*ms", line)
        if m:
            metrics["prompt_eval_time_ms"] = m.group(1)

    line = find_last(r"(^|\s)eval time")
    if line:
        m = re.search(r"=\s*([0-9]+(?:\.[0-9]+)?)\s*ms", line)
        if m:
            metrics["eval_time_ms"] = m.group(1)

    line = find_last(r"generated\s+[0-9]+\s+tokens|total\s+tokens|tokens generated")
    if line:
        m = re.search(r"([0-9]+)\s+tokens", line)
        if m:
            metrics["total_generated_tokens"] = m.group(1)

    line = find_last(r"tokens per second|tok/s")
    if line:
        m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*tokens\s*per\s*second", line, re.IGNORECASE)
        if not m:
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*tok/s", line, re.IGNORECASE)
        if m:
            metrics["tokens_per_second"] = m.group(1)

    return metrics


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_summary(
    summary_md: Path,
    output_csv: Path,
    event_log: Path,
    runtime_csv: Path,
    interval: float,
    model: str,
    mmproj: str,
    ctx_size: str,
    threads: str,
    gpu_layers: str,
    start_ts: str,
    end_ts: str,
    duration_sec: int,
    peak_memory_used: int,
    peak_memory_pressure: float,
    peak_swap: int,
    peak_rss: int,
    peak_compressed: int,
    avg_cpu: str,
    avg_gpu: str,
    peak_disk_read: int,
    peak_disk_write: int,
    peak_gpu_memory: str,
    avg_tps: str,
) -> None:
    info = collect_system_info()
    lines = [
        "# Benchmark Summary",
        "",
        "## System Information",
        "",
        f"- Machine: {info['machine']}",
        f"- macOS: {info['os']}",
        f"- Total Memory: {bytes_to_gb(int(info['total_mem']))} GB",
        f"- CPU: {info['cpu']}",
        f"- GPU: {info['gpu']}",
        f"- Model: {model}",
        f"- mmproj: {mmproj}",
        f"- Context Size: {ctx_size}",
        f"- Threads: {threads}",
        f"- GPU Layers: {gpu_layers}",
        f"- Sampling Interval: {interval} s",
        "",
        "## Run Information",
        "",
        f"- Start: {start_ts}",
        f"- End: {end_ts}",
        f"- Duration: {duration_sec}s",
        f"- CSV: {output_csv}",
        f"- Events Log: {event_log}",
        f"- llama Runtime CSV: {runtime_csv}",
        "",
        "## Metrics",
        "",
        f"- Peak Memory Used: {bytes_to_gb(peak_memory_used)} GB",
        f"- Peak Memory Pressure: {peak_memory_pressure:.2f}%",
        f"- Peak Swap: {bytes_to_gb(peak_swap)} GB",
        f"- Peak RSS: {bytes_to_gb(peak_rss)} GB",
        f"- Peak Compressed Memory: {bytes_to_gb(peak_compressed)} GB",
        f"- Average CPU: {avg_cpu}%",
        f"- Average GPU: {avg_gpu}%",
        f"- Peak Disk Read: {bytes_to_mb(peak_disk_read)} MB/s",
        f"- Peak Disk Write: {bytes_to_mb(peak_disk_write)} MB/s",
        f"- Peak GPU Memory: {bytes_to_gb(int(peak_gpu_memory)) + ' GB' if peak_gpu_memory.isdigit() else 'NA'}",
        f"- Average Tokens/sec: {avg_tps}",
    ]
    summary_md.write_text("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect macOS system/process metrics while target process runs.")
    parser.add_argument("-i", dest="interval", default="1")
    parser.add_argument("-n", dest="target_name", default="llama-cli")
    parser.add_argument("-p", dest="target_pid", default="")
    parser.add_argument("-o", dest="output_csv", default="")
    parser.add_argument("-x", dest="run_command", default="")

    parser.add_argument("--events-log", dest="event_log", default="")
    parser.add_argument("--summary-md", dest="summary_md", default="")
    parser.add_argument("--llama-log", dest="llama_log", default="")
    parser.add_argument("--llama-runtime-csv", dest="llama_runtime_csv", default="")

    parser.add_argument("--model", dest="model_name", default="NA")
    parser.add_argument("--mmproj", dest="mmproj_name", default="NA")
    parser.add_argument("--ctx-size", dest="ctx_size", default="NA")
    parser.add_argument("--threads", dest="threads", default="NA")
    parser.add_argument("--gpu-layers", dest="gpu_layers", default="NA")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        interval = float(args.interval)
        if interval <= 0:
            raise ValueError
    except Exception:
        print(f"Invalid interval: {args.interval}", file=sys.stderr)
        return 1

    script_dir = Path(__file__).resolve().parent
    output_csv = Path(args.output_csv) if args.output_csv else script_dir / f"benchmark_{dt.datetime.now():%Y%m%d_%H%M%S}.csv"

    event_log = Path(args.event_log) if args.event_log else Path(str(output_csv).replace(".csv", "_events.log"))
    summary_md = Path(args.summary_md) if args.summary_md else Path(str(output_csv).replace(".csv", "_summary.md"))
    llama_log = Path(args.llama_log) if args.llama_log else Path(str(output_csv).replace(".csv", "_llama.log"))
    llama_runtime_csv = Path(args.llama_runtime_csv) if args.llama_runtime_csv else Path(str(output_csv).replace(".csv", "_llama_runtime.csv"))

    ensure_parent(output_csv)
    ensure_parent(event_log)
    ensure_parent(summary_md)
    ensure_parent(llama_log)
    ensure_parent(llama_runtime_csv)

    target_pid: Optional[int] = None
    target_name = args.target_name

    if args.run_command and args.target_pid:
        print("-x and -p cannot be used together.", file=sys.stderr)
        return 1

    proc: Optional[subprocess.Popen] = None
    if args.run_command:
        print(f"Launching command: {args.run_command}")
        log_fp = llama_log.open("w", encoding="utf-8")
        proc = subprocess.Popen(
            args.run_command,
            shell=True,
            executable="/bin/bash",
            stdout=log_fp,
            stderr=subprocess.STDOUT,
        )
        target_pid = proc.pid
        if not target_name or target_name == "llama-cli":
            try:
                target_name = Path(shlex.split(args.run_command)[0]).name
            except Exception:
                pass
    elif args.target_pid:
        if not args.target_pid.isdigit():
            print(f"Invalid PID: {args.target_pid}", file=sys.stderr)
            return 1
        target_pid = int(args.target_pid)
    else:
        pgrep = run_cmd(["pgrep", "-x", target_name])
        pids = [p for p in pgrep.splitlines() if p.strip().isdigit()]
        if not pids:
            print(f"Process not found by name: {target_name}", file=sys.stderr)
            return 1
        target_pid = int(pids[-1])

    assert target_pid is not None
    if run_cmd(["ps", "-p", str(target_pid), "-o", "pid="]) == "":
        print(f"PID {target_pid} is not running or not accessible.", file=sys.stderr)
        return 1

    target_comm = run_cmd(["ps", "-p", str(target_pid), "-o", "comm="]).strip() or target_name

    header = [
        "timestamp",
        "cpu_usage",
        "gpu_usage",
        "memory_used",
        "swap_used",
        "disk_read",
        "disk_write",
        "llama_memory",
        "llama_cpu",
        "memory_total",
        "memory_free",
        "memory_pressure",
        "compressed_memory",
        "disk_iops_read",
        "disk_iops_write",
        "disk_iops_total",
        "process_virtual_memory",
        "process_threads",
        "cpu_per_core",
        "target_pid",
        "target_name",
        "memory_wired",
        "memory_active",
        "memory_inactive",
        "memory_cached",
        "vm_pageins",
        "vm_pageouts",
        "vm_swapins",
        "vm_swapouts",
        "gpu_memory",
        "gpu_metric_mode",
    ]

    with output_csv.open("w", newline="", encoding="utf-8") as fcsv, event_log.open("w", encoding="utf-8") as fev:
        writer = csv.writer(fcsv)
        writer.writerow(header)

        fev.write("# Memory pressure and VM events\n")
        fev.write(f"# Generated at {dt.datetime.now():%Y-%m-%d %H:%M:%S}\n\n")

        prev_rb, prev_wb, prev_ro, prev_wo = get_disk_counters()

        start_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_epoch = int(time.time())

        print(f"[{start_ts}] Monitoring PID {target_pid} ({target_comm}) every {interval}s")
        print(f"[{start_ts}] Writing CSV to: {output_csv}")
        print(f"[{start_ts}] Writing events log to: {event_log}")

        cpu_sum = 0.0
        cpu_count = 0
        gpu_sum = 0.0
        gpu_count = 0

        peak_memory_used = 0
        peak_memory_pressure = 0.0
        peak_swap = 0
        peak_rss = 0
        peak_compressed = 0
        peak_disk_read = 0
        peak_disk_write = 0

        pressure_threshold = 80.0
        free_threshold = 500 * 1024 * 1024
        pressure_high_state = False
        free_low_state = False
        prev_swap: Optional[int] = None
        prev_pageouts: Optional[int] = None

        max_gpu_memory = 0

        while run_cmd(["ps", "-p", str(target_pid), "-o", "pid="]) != "":
            ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            mem = get_memory_metrics()
            cpu_usage = get_cpu_usage_total()
            gpu_usage = get_gpu_usage()
            cpu_per_core = get_cpu_per_core()

            gpu_memory = "NA"
            gpu_metric_mode = "usage"
            if gpu_usage == "NA":
                gpu_memory = get_gpu_memory_bytes(target_pid)
                gpu_metric_mode = "memory"
                if gpu_memory.isdigit():
                    max_gpu_memory = max(max_gpu_memory, int(gpu_memory))

            proc_metrics = get_process_metrics(target_pid)
            cur_rb, cur_wb, cur_ro, cur_wo = get_disk_counters()

            d_rb = max(cur_rb - prev_rb, 0)
            d_wb = max(cur_wb - prev_wb, 0)
            d_ro = max(cur_ro - prev_ro, 0)
            d_wo = max(cur_wo - prev_wo, 0)

            disk_read_bps = int(d_rb / interval)
            disk_write_bps = int(d_wb / interval)
            disk_iops_read = int(d_ro / interval)
            disk_iops_write = int(d_wo / interval)
            disk_iops_total = disk_iops_read + disk_iops_write

            prev_rb, prev_wb, prev_ro, prev_wo = cur_rb, cur_wb, cur_ro, cur_wo

            if is_number(cpu_usage):
                cpu_sum += float(cpu_usage)
                cpu_count += 1
            if is_number(gpu_usage):
                gpu_sum += float(gpu_usage)
                gpu_count += 1

            mu = int(mem["memory_used"]) if mem["memory_used"].isdigit() else 0
            su = int(mem["swap_used"]) if mem["swap_used"].isdigit() else 0
            cm = int(mem["compressed_memory"]) if mem["compressed_memory"].isdigit() else 0
            pr = int(proc_metrics["proc_rss"]) if proc_metrics["proc_rss"].isdigit() else 0

            peak_memory_used = max(peak_memory_used, mu)
            peak_swap = max(peak_swap, su)
            peak_compressed = max(peak_compressed, cm)
            peak_rss = max(peak_rss, pr)
            peak_disk_read = max(peak_disk_read, disk_read_bps)
            peak_disk_write = max(peak_disk_write, disk_write_bps)
            if is_number(mem["memory_pressure"]):
                peak_memory_pressure = max(peak_memory_pressure, float(mem["memory_pressure"]))

            if is_number(mem["memory_pressure"]):
                p = float(mem["memory_pressure"])
                if p > pressure_threshold and not pressure_high_state:
                    fev.write(f"{ts}\nMemory pressure exceeded {pressure_threshold}% (current: {p:.2f}%)\n\n")
                    pressure_high_state = True
                if p <= pressure_threshold:
                    pressure_high_state = False

            if mem["swap_used"].isdigit():
                cur_swap = int(mem["swap_used"])
                if prev_swap is not None and cur_swap > prev_swap:
                    fev.write(f"{ts}\nSwap usage increased by {bytes_to_mb(cur_swap - prev_swap)} MB\n\n")
                prev_swap = cur_swap

            if mem["vm_pageouts"].isdigit():
                cur_po = int(mem["vm_pageouts"])
                if prev_pageouts is not None and cur_po > prev_pageouts:
                    fev.write(f"{ts}\nPageouts increased by {cur_po - prev_pageouts} pages\n\n")
                prev_pageouts = cur_po

            if mem["memory_free"].isdigit():
                mf = int(mem["memory_free"])
                if mf < free_threshold and not free_low_state:
                    fev.write(f"{ts}\nFree memory below 500 MB (current: {bytes_to_mb(mf)} MB)\n\n")
                    free_low_state = True
                if mf >= free_threshold:
                    free_low_state = False

            writer.writerow(
                [
                    ts,
                    cpu_usage,
                    gpu_usage,
                    mem["memory_used"],
                    mem["swap_used"],
                    disk_read_bps,
                    disk_write_bps,
                    proc_metrics["proc_rss"],
                    proc_metrics["proc_cpu"],
                    mem["memory_total"],
                    mem["memory_free"],
                    mem["memory_pressure"],
                    mem["compressed_memory"],
                    disk_iops_read,
                    disk_iops_write,
                    disk_iops_total,
                    proc_metrics["proc_vsz"],
                    proc_metrics["proc_threads"],
                    cpu_per_core,
                    target_pid,
                    target_comm,
                    mem["memory_wired"],
                    mem["memory_active"],
                    mem["memory_inactive"],
                    mem["memory_cached"],
                    mem["vm_pageins"],
                    mem["vm_pageouts"],
                    mem["vm_swapins"],
                    mem["vm_swapouts"],
                    gpu_memory,
                    gpu_metric_mode,
                ]
            )

            fcsv.flush()
            fev.flush()
            time.sleep(interval)

    end_ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    end_epoch = int(time.time())
    duration_sec = end_epoch - start_epoch

    avg_cpu = f"{(cpu_sum / cpu_count):.2f}" if cpu_count > 0 else "NA"
    avg_gpu = f"{(gpu_sum / gpu_count):.2f}" if gpu_count > 0 else "NA"

    runtime = parse_llama_runtime_metrics(llama_log)
    with llama_runtime_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value"])
        for k in [
            "model_load_time_ms",
            "prompt_eval_time_ms",
            "eval_time_ms",
            "total_generated_tokens",
            "tokens_per_second",
        ]:
            w.writerow([k, runtime[k]])

    avg_tps = runtime["tokens_per_second"] if is_number(runtime["tokens_per_second"]) else "NA"

    write_summary(
        summary_md=summary_md,
        output_csv=output_csv,
        event_log=event_log,
        runtime_csv=llama_runtime_csv,
        interval=interval,
        model=args.model_name,
        mmproj=args.mmproj_name,
        ctx_size=args.ctx_size,
        threads=args.threads,
        gpu_layers=args.gpu_layers,
        start_ts=start_ts,
        end_ts=end_ts,
        duration_sec=duration_sec,
        peak_memory_used=peak_memory_used,
        peak_memory_pressure=peak_memory_pressure,
        peak_swap=peak_swap,
        peak_rss=peak_rss,
        peak_compressed=peak_compressed,
        avg_cpu=avg_cpu,
        avg_gpu=avg_gpu,
        peak_disk_read=peak_disk_read,
        peak_disk_write=peak_disk_write,
        peak_gpu_memory=str(max_gpu_memory) if max_gpu_memory > 0 else "NA",
        avg_tps=avg_tps,
    )

    print("")
    print("Benchmark Summary")
    print(f"Duration: {duration_sec}s")
    print(f"Peak Memory Used: {bytes_to_gb(peak_memory_used)} GB")
    print(f"Peak Memory Pressure: {peak_memory_pressure:.2f}%")
    print(f"Peak Swap: {bytes_to_gb(peak_swap)} GB")
    print(f"Peak RSS: {bytes_to_gb(peak_rss)} GB")
    print(f"Peak Compressed Memory: {bytes_to_gb(peak_compressed)} GB")
    print(f"Average CPU: {avg_cpu}%")
    print(f"Average GPU: {avg_gpu}%")
    print(f"Peak Disk Read: {bytes_to_mb(peak_disk_read)} MB/s")
    print(f"Peak Disk Write: {bytes_to_mb(peak_disk_write)} MB/s")
    print(f"Peak GPU Memory: {bytes_to_gb(max_gpu_memory) + ' GB' if max_gpu_memory > 0 else 'NA'}")
    print(f"Average Tokens/sec: {avg_tps}")
    print("")
    print(f"[{end_ts}] Target process exited. Benchmark stopped.")
    print(f"[{end_ts}] CSV saved: {output_csv}")
    print(f"[{end_ts}] Events log saved: {event_log}")
    print(f"[{end_ts}] llama runtime CSV saved: {llama_runtime_csv}")
    print(f"[{end_ts}] Summary markdown saved: {summary_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
