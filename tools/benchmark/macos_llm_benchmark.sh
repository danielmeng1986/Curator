#!/usr/bin/env bash

set -u

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INTERVAL="1"
TARGET_NAME="llama-cli"
TARGET_PID=""
OUTPUT_CSV="$SCRIPT_DIR/benchmark_$(date +%Y%m%d_%H%M%S).csv"
EVENT_LOG=""
SUMMARY_MD=""
LLAMA_LOG=""
LLAMA_RUNTIME_CSV=""

RUN_COMMAND=""
MODEL_NAME="NA"
MMPROJ_NAME="NA"
CONTEXT_SIZE="NA"
THREADS="NA"
GPU_LAYERS="NA"

PRESSURE_THRESHOLD="80"
FREE_MEMORY_THRESHOLD_BYTES=$((500 * 1024 * 1024))

START_EPOCH=0
END_EPOCH=0

CPU_SUM="0"
CPU_COUNT=0
GPU_SUM="0"
GPU_COUNT=0
SAMPLE_COUNT=0

PEAK_MEMORY_USED=0
PEAK_MEMORY_PRESSURE=0
PEAK_SWAP=0
PEAK_RSS=0
PEAK_COMPRESSED=0
PEAK_DISK_READ=0
PEAK_DISK_WRITE=0

PREV_SWAP=""
PREV_PAGEOUTS=""
PRESSURE_HIGH_STATE=0
FREE_LOW_STATE=0

GPU_FALLBACK_MODE="usage"

usage() {
  cat <<EOF
Usage: $SCRIPT_NAME [options]

Collect macOS system/process metrics periodically while a target process is running.

Options:
  -i   Sampling interval in seconds (default: 1)
  -n   Target process name for pgrep matching (default: llama-cli)
  -p   Target PID (overrides -n)
  -o   Output CSV path
  -x   Command to launch and monitor (stdout/stderr can be captured with --llama-log)
  -h   Show this help message

  --events-log PATH        Event log output path
  --summary-md PATH        Benchmark markdown summary path
  --llama-log PATH         llama.cpp stdout/stderr log path for runtime metric parsing
  --llama-runtime-csv PATH Runtime metrics CSV output path

  --model NAME             Model name for environment report
  --mmproj NAME            mmproj file name for environment report
  --ctx-size N             Context size for environment report
  --threads N              Thread count for environment report
  --gpu-layers N           GPU layers for environment report
  -h   Show this help message

Examples:
  $SCRIPT_NAME
  $SCRIPT_NAME -n llama-cli -i 0.5 -o tools/benchmark/run.csv
  $SCRIPT_NAME -p 12345 -i 1
  $SCRIPT_NAME -x "llama-cli -m model.gguf -p 'hello'" --llama-log tools/benchmark/llama.log
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i)
      INTERVAL="$2"
      shift 2
      ;;
    -n)
      TARGET_NAME="$2"
      shift 2
      ;;
    -p)
      TARGET_PID="$2"
      shift 2
      ;;
    -o)
      OUTPUT_CSV="$2"
      shift 2
      ;;
    -x)
      RUN_COMMAND="$2"
      shift 2
      ;;
    --events-log)
      EVENT_LOG="$2"
      shift 2
      ;;
    --summary-md)
      SUMMARY_MD="$2"
      shift 2
      ;;
    --llama-log)
      LLAMA_LOG="$2"
      shift 2
      ;;
    --llama-runtime-csv)
      LLAMA_RUNTIME_CSV="$2"
      shift 2
      ;;
    --model)
      MODEL_NAME="$2"
      shift 2
      ;;
    --mmproj)
      MMPROJ_NAME="$2"
      shift 2
      ;;
    --ctx-size)
      CONTEXT_SIZE="$2"
      shift 2
      ;;
    --threads)
      THREADS="$2"
      shift 2
      ;;
    --gpu-layers)
      GPU_LAYERS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Invalid option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! [[ "$INTERVAL" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "Invalid interval: $INTERVAL" >&2
  exit 1
fi

if [[ -n "$RUN_COMMAND" ]]; then
  if [[ -n "$TARGET_PID" ]]; then
    echo "-x and -p cannot be used together." >&2
    exit 1
  fi
  if [[ -z "$LLAMA_LOG" ]]; then
    LLAMA_LOG="${OUTPUT_CSV%.csv}_llama.log"
  fi
  mkdir -p "$(dirname "$LLAMA_LOG")"
  echo "Launching command: $RUN_COMMAND"
  # shellcheck disable=SC2086
  eval "$RUN_COMMAND" >"$LLAMA_LOG" 2>&1 &
  TARGET_PID="$!"
  if [[ -z "$TARGET_NAME" || "$TARGET_NAME" == "llama-cli" ]]; then
    TARGET_NAME="$(basename "$(echo "$RUN_COMMAND" | awk '{print $1}')")"
  fi
fi

if [[ -z "$TARGET_PID" ]]; then
  if ! command -v pgrep >/dev/null 2>&1; then
    echo "pgrep not found; use -p <pid> or -x <command>." >&2
    exit 1
  fi
  TARGET_PID="$(pgrep -x "$TARGET_NAME" | tail -n 1)"
fi

if ! [[ "$TARGET_PID" =~ ^[0-9]+$ ]]; then
  echo "Invalid PID: $TARGET_PID" >&2
  exit 1
fi

if ! kill -0 "$TARGET_PID" 2>/dev/null; then
  echo "PID $TARGET_PID is not running or not accessible." >&2
  exit 1
fi

TARGET_COMM="$(ps -p "$TARGET_PID" -o comm= 2>/dev/null | awk '{$1=$1; print}')"
if [[ -z "$TARGET_COMM" ]]; then
  TARGET_COMM="$TARGET_NAME"
fi

mkdir -p "$(dirname "$OUTPUT_CSV")"

if [[ -z "$EVENT_LOG" ]]; then
  EVENT_LOG="${OUTPUT_CSV%.csv}_events.log"
fi
if [[ -z "$SUMMARY_MD" ]]; then
  SUMMARY_MD="${OUTPUT_CSV%.csv}_summary.md"
fi
if [[ -z "$LLAMA_RUNTIME_CSV" ]]; then
  LLAMA_RUNTIME_CSV="${OUTPUT_CSV%.csv}_llama_runtime.csv"
fi

mkdir -p "$(dirname "$EVENT_LOG")"
mkdir -p "$(dirname "$SUMMARY_MD")"
mkdir -p "$(dirname "$LLAMA_RUNTIME_CSV")"

# Convert human-readable units (K/M/G/T, with optional B suffix) to bytes.
unit_to_bytes() {
  local value="$1"
  local unit="$2"
  awk -v v="$value" -v u="$unit" 'BEGIN {
    mul=1
    if (u=="B" || u=="") mul=1
    else if (u=="K" || u=="KB") mul=1024
    else if (u=="M" || u=="MB") mul=1024*1024
    else if (u=="G" || u=="GB") mul=1024*1024*1024
    else if (u=="T" || u=="TB") mul=1024*1024*1024*1024
    printf "%.0f", v*mul
  }'
}

is_number() {
  [[ "$1" =~ ^-?[0-9]+([.][0-9]+)?$ ]]
}

to_human_mb() {
  local bytes="$1"
  awk -v b="$bytes" 'BEGIN { printf "%.2f", b / 1024 / 1024 }'
}

to_human_gb() {
  local bytes="$1"
  awk -v b="$bytes" 'BEGIN { printf "%.2f", b / 1024 / 1024 / 1024 }'
}

max_float() {
  local a="$1"
  local b="$2"
  awk -v x="$a" -v y="$b" 'BEGIN { if (x+0 >= y+0) print x; else print y }'
}

append_event() {
  local ts="$1"
  local msg="$2"
  {
    echo "$ts"
    echo "$msg"
    echo ""
  } >> "$EVENT_LOG"
}

parse_size_token_to_bytes() {
  local token="$1"
  token="$(echo "$token" | tr -d '[:space:]')"
  if [[ -z "$token" ]]; then
    echo 0
    return
  fi
  if [[ "$token" =~ ^([0-9.]+)([KMGTP]?)(B)?$ ]]; then
    local n="${BASH_REMATCH[1]}"
    local u="${BASH_REMATCH[2]}${BASH_REMATCH[3]}"
    unit_to_bytes "$n" "$u"
  else
    echo 0
  fi
}

collect_system_info() {
  local machine
  local os
  local total_mem
  local cpu
  local gpu

  machine="$(system_profiler SPHardwareDataType 2>/dev/null | awk -F': ' '/Model Name/ {print $2; exit}')"
  if [[ -z "$machine" ]]; then
    machine="$(sysctl -n hw.model 2>/dev/null || echo "Unknown")"
  fi

  os="$(sw_vers -productVersion 2>/dev/null || echo "Unknown")"
  total_mem="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"

  cpu="$(system_profiler SPHardwareDataType 2>/dev/null | awk -F': ' '/Chip/ {print $2; exit}')"
  if [[ -z "$cpu" ]]; then
    cpu="$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")"
  fi

  gpu="$(system_profiler SPDisplaysDataType 2>/dev/null | awk -F': ' '/Chipset Model/ {print $2; exit}')"
  if [[ -z "$gpu" ]]; then
    gpu="Apple GPU"
  fi

  echo "$machine|$os|$total_mem|$cpu|$gpu"
}

get_vm_pages_value() {
  local vm="$1"
  local key="$2"
  echo "$vm" | awk -v k="$key" '
    index($0, k ":") == 1 {
      line=$0
      sub(/.*:/, "", line)
      gsub(/[^0-9]/, "", line)
      if (line == "") line=0
      print line
      exit
    }
  '
}

get_memory_metrics() {
  local page_size
  local total_mem
  local vm
  local free_pages
  local speculative_pages
  local compressor_pages
  local free_bytes
  local used_bytes
  local compressed_bytes
  local wired_pages
  local active_pages
  local inactive_pages
  local file_backed_pages
  local wired_bytes
  local active_bytes
  local inactive_bytes
  local cached_bytes
  local pageins
  local pageouts
  local swapins
  local swapouts
  local pressure_used_percent
  local swap_line
  local swap_num
  local swap_unit
  local swap_used_bytes

  total_mem="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
  vm="$(vm_stat 2>/dev/null)"

  page_size="$(echo "$vm" | awk '/page size of/ {gsub("\\.","",$8); print $8; exit}')"
  if [[ -z "$page_size" ]]; then
    page_size=4096
  fi

  free_pages="$(get_vm_pages_value "$vm" "Pages free")"
  speculative_pages="$(get_vm_pages_value "$vm" "Pages speculative")"
  compressor_pages="$(get_vm_pages_value "$vm" "Pages occupied by compressor")"
  wired_pages="$(get_vm_pages_value "$vm" "Pages wired down")"
  active_pages="$(get_vm_pages_value "$vm" "Pages active")"
  inactive_pages="$(get_vm_pages_value "$vm" "Pages inactive")"
  file_backed_pages="$(get_vm_pages_value "$vm" "File-backed pages")"

  pageins="$(get_vm_pages_value "$vm" "Pageins")"
  pageouts="$(get_vm_pages_value "$vm" "Pageouts")"
  swapins="$(get_vm_pages_value "$vm" "Swapins")"
  swapouts="$(get_vm_pages_value "$vm" "Swapouts")"

  free_pages="${free_pages:-0}"
  speculative_pages="${speculative_pages:-0}"
  compressor_pages="${compressor_pages:-0}"
  wired_pages="${wired_pages:-0}"
  active_pages="${active_pages:-0}"
  inactive_pages="${inactive_pages:-0}"
  file_backed_pages="${file_backed_pages:-0}"
  pageins="${pageins:-0}"
  pageouts="${pageouts:-0}"
  swapins="${swapins:-0}"
  swapouts="${swapouts:-0}"

  free_bytes=$(( (free_pages + speculative_pages) * page_size ))
  used_bytes=$(( total_mem - free_bytes ))
  if (( used_bytes < 0 )); then
    used_bytes=0
  fi
  compressed_bytes=$(( compressor_pages * page_size ))
  wired_bytes=$(( wired_pages * page_size ))
  active_bytes=$(( active_pages * page_size ))
  inactive_bytes=$(( inactive_pages * page_size ))
  cached_bytes=$(( (file_backed_pages + speculative_pages) * page_size ))

  pressure_used_percent="NA"
  if command -v memory_pressure >/dev/null 2>&1; then
    pressure_used_percent="$(memory_pressure 2>/dev/null | awk -F': ' '/System-wide memory free percentage/ {
      gsub("%", "", $2)
      if ($2 ~ /^[0-9.]+$/) printf "%.2f", 100 - $2
      else print "NA"
      exit
    }')"
    pressure_used_percent="${pressure_used_percent:-NA}"
  fi

  swap_used_bytes=0
  swap_line="$(sysctl vm.swapusage 2>/dev/null)"
  # Example: vm.swapusage: total = 1024.00M  used = 512.00M  free = 512.00M  (encrypted)
  if [[ "$swap_line" =~ used[[:space:]]*=[[:space:]]*([0-9.]+)([KMGTP]?)(B)? ]]; then
    swap_num="${BASH_REMATCH[1]}"
    swap_unit="${BASH_REMATCH[2]}${BASH_REMATCH[3]}"
    swap_used_bytes="$(unit_to_bytes "$swap_num" "$swap_unit")"
  fi

  echo "$total_mem,$used_bytes,$free_bytes,$pressure_used_percent,$swap_used_bytes,$compressed_bytes,$wired_bytes,$active_bytes,$inactive_bytes,$cached_bytes,$pageins,$pageouts,$swapins,$swapouts"
}

get_cpu_usage_total() {
  local line
  local usage
  line="$(top -l 1 -n 0 2>/dev/null | awk -F'[:,% ]+' '/CPU usage/ {print $0; exit}')"
  usage="$(echo "$line" | awk -F'[:,% ]+' '{ if ($7 ~ /^[0-9.]+$/) printf "%.2f", 100-$7; else print "NA" }')"
  echo "${usage:-NA}"
}

get_cpu_per_core() {
  local ncpu
  local out
  ncpu="$(sysctl -n hw.ncpu 2>/dev/null || echo 0)"
  out="$(ps -A -o cpuid= -o %cpu= 2>/dev/null | awk -v n="$ncpu" '
    function to_num(x) { return (x ~ /^[0-9.]+$/) ? x+0 : 0 }
    {
      c=$1
      u=$2
      if (c ~ /^[0-9]+$/ && u ~ /^[0-9.]+$/) sum[c]+=u
    }
    END {
      if (n <= 0) { print "NA"; exit }
      first=1
      for (i=0; i<n; i++) {
        v=(i in sum)?sum[i]:0
        if (v>100) v=100
        if (!first) printf ";"
        printf "%.2f", v
        first=0
      }
      if (first) print "NA"
    }
  ')"

  if [[ -z "$out" ]]; then
    echo "NA"
  else
    echo "$out"
  fi
}

get_gpu_usage() {
  local value
  value="$(ioreg -r -d 1 -w 0 -c AGXAccelerator 2>/dev/null | awk -F'= ' '
    /Device Utilization %|GPU Busy|GPU Core Utilization/ {
      gsub(/[^0-9.]/, "", $2)
      if ($2 ~ /^[0-9.]+$/) { print $2; exit }
    }
  ')"

  if [[ -z "$value" && "$EUID" -eq 0 ]] && command -v powermetrics >/dev/null 2>&1; then
    value="$(powermetrics --samplers gpu_power -n 1 2>/dev/null | awk '
      /GPU Busy|GPU active|GPU Activity|GPU utilization/ {
        for (i = 1; i <= NF; i++) {
          gsub(/[^0-9.]/, "", $i)
          if ($i ~ /^[0-9.]+$/) { print $i; exit }
        }
      }
    ')"
  fi

  if [[ -n "$value" ]]; then
    value="$(awk -v v="$value" 'BEGIN {
      if (v !~ /^[0-9.]+$/) { print "NA"; exit }
      if (v < 0) { print "NA"; exit }
      if (v > 1000000) { print "NA"; exit }
      if (v > 100) { print "NA"; exit }
      if (v <= 1) printf "%.2f", v * 100
      else printf "%.2f", v
    }')"
  fi

  if [[ -z "$value" ]]; then
    echo "NA"
  elif [[ "$value" == "NA" ]]; then
    echo "NA"
  else
    printf "%.2f\n" "$value"
  fi
}

get_gpu_memory_bytes() {
  local pid="$1"
  local value

  if ! command -v vmmap >/dev/null 2>&1; then
    echo "NA"
    return
  fi

  value="$(vmmap -summary "$pid" 2>/dev/null | awk '
    function tobytes(tok,    unit, num, mul) {
      gsub(/[[:space:]]/, "", tok)
      if (tok == "") return 0
      unit=""
      num=tok
      if (tok ~ /[A-Za-z]$/) {
        unit=substr(tok, length(tok), 1)
        num=substr(tok, 1, length(tok)-1)
      }
      mul=1
      if (unit == "K") mul=1024
      else if (unit == "M") mul=1024*1024
      else if (unit == "G") mul=1024*1024*1024
      else if (unit == "T") mul=1024*1024*1024*1024
      return num * mul
    }
    ($1 ~ /^IOSurface$/ || $1 ~ /^IOAccelerator$/ || $1 ~ /^Metal$/ || $1 ~ /^MALLOC_.*GPU$/) {
      sum += tobytes($2)
    }
    END {
      if (sum > 0) printf "%.0f", sum
    }
  ')"

  if [[ -z "$value" ]]; then
    echo "NA"
  else
    echo "$value"
  fi
}

get_disk_counters_apfs() {
  local io
  local read_bytes
  local write_bytes
  local read_ops
  local write_ops

  io="$(ioreg -r -c AppleAPFSContainer -k Statistics -a 2>/dev/null)"

  if [[ -z "$io" ]]; then
    echo "0,0,0,0"
    return
  fi

  read_bytes="$(echo "$io" | awk -v k='Bytes read from block device' '
    $0 ~ "<key>" k "</key>" {want=1; next}
    want && /<integer>/ {
      gsub(/.*<integer>/, "")
      gsub(/<\/integer>.*/, "")
      s += $0 + 0
      want=0
    }
    END {print s+0}
  ')"

  write_bytes="$(echo "$io" | awk -v k='Bytes written to block device' '
    $0 ~ "<key>" k "</key>" {want=1; next}
    want && /<integer>/ {
      gsub(/.*<integer>/, "")
      gsub(/<\/integer>.*/, "")
      s += $0 + 0
      want=0
    }
    END {print s+0}
  ')"

  read_ops="$(echo "$io" | awk -v k='Read requests sent to block device' '
    $0 ~ "<key>" k "</key>" {want=1; next}
    want && /<integer>/ {
      gsub(/.*<integer>/, "")
      gsub(/<\/integer>.*/, "")
      s += $0 + 0
      want=0
    }
    END {print s+0}
  ')"

  write_ops="$(echo "$io" | awk -v k='Write requests sent to block device' '
    $0 ~ "<key>" k "</key>" {want=1; next}
    want && /<integer>/ {
      gsub(/.*<integer>/, "")
      gsub(/<\/integer>.*/, "")
      s += $0 + 0
      want=0
    }
    END {print s+0}
  ')"

  echo "$read_bytes,$write_bytes,$read_ops,$write_ops"
}

get_disk_counters_fallback() {
  local io
  local read_bytes
  local write_bytes
  local read_ops
  local write_ops

  io="$(ioreg -r -c IOBlockStorageDriver -k Statistics 2>/dev/null)"

  if [[ -z "$io" ]]; then
    echo "0,0,0,0"
    return
  fi

  read_bytes="$(echo "$io" | awk -F'=' '/"Bytes \(Read\)"/ {gsub(/[^0-9]/, "", $2); s+=$2} END {print s+0}')"
  write_bytes="$(echo "$io" | awk -F'=' '/"Bytes \(Write\)"/ {gsub(/[^0-9]/, "", $2); s+=$2} END {print s+0}')"
  read_ops="$(echo "$io" | awk -F'=' '/"Operations \(Read\)"/ {gsub(/[^0-9]/, "", $2); s+=$2} END {print s+0}')"
  write_ops="$(echo "$io" | awk -F'=' '/"Operations \(Write\)"/ {gsub(/[^0-9]/, "", $2); s+=$2} END {print s+0}')"

  echo "$read_bytes,$write_bytes,$read_ops,$write_ops"
}

get_disk_counters() {
  local data
  data="$(get_disk_counters_apfs)"
  IFS=',' read -r rb wb ro wo <<< "$data"
  if (( rb == 0 && wb == 0 && ro == 0 && wo == 0 )); then
    get_disk_counters_fallback
    return
  fi
  echo "$data"
}

get_process_metrics() {
  local pid="$1"
  local line
  local rss_kb
  local vsz_kb
  local cpu
  local thcount

  line="$(ps -p "$pid" -o rss= -o vsz= -o %cpu= -o thcount= 2>/dev/null | awk '{$1=$1; print}')"
  if [[ -z "$line" ]]; then
    echo "NA,NA,NA,NA"
    return
  fi

  rss_kb="$(echo "$line" | awk '{print $1}')"
  vsz_kb="$(echo "$line" | awk '{print $2}')"
  cpu="$(echo "$line" | awk '{print $3}')"
  thcount="$(echo "$line" | awk '{print $4}')"

  if [[ "$rss_kb" =~ ^[0-9]+$ ]]; then
    rss_kb=$((rss_kb * 1024))
  else
    rss_kb="NA"
  fi

  if [[ "$vsz_kb" =~ ^[0-9]+$ ]]; then
    vsz_kb=$((vsz_kb * 1024))
  else
    vsz_kb="NA"
  fi

  if [[ ! "$cpu" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    cpu="NA"
  fi

  if [[ ! "$thcount" =~ ^[0-9]+$ ]]; then
    thcount="NA"
  fi

  echo "$rss_kb,$vsz_kb,$cpu,$thcount"
}

parse_llama_runtime_metrics() {
  local log_file="$1"
  local load_ms="NA"
  local prompt_eval_ms="NA"
  local eval_ms="NA"
  local tokens="NA"
  local tps="NA"
  local line

  if [[ -z "$log_file" || ! -f "$log_file" ]]; then
    echo "$load_ms,$prompt_eval_ms,$eval_ms,$tokens,$tps"
    return
  fi

  line="$(grep -E 'load time|model load time' "$log_file" | tail -n 1 || true)"
  if [[ -n "$line" ]]; then
    if [[ "$line" =~ ([0-9]+([.][0-9]+)?)\ *ms ]]; then
      load_ms="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ([0-9]+([.][0-9]+)?)\ *s([^[:alpha:]]|$) ]]; then
      load_ms="$(awk -v s="${BASH_REMATCH[1]}" 'BEGIN {printf "%.2f", s*1000}')"
    fi
  fi

  line="$(grep -E 'prompt eval time' "$log_file" | tail -n 1 || true)"
  if [[ -n "$line" && "$line" =~ =\ *([0-9]+([.][0-9]+)?)\ *ms ]]; then
    prompt_eval_ms="${BASH_REMATCH[1]}"
  fi

  line="$(grep -E '(^|[[:space:]])eval time' "$log_file" | tail -n 1 || true)"
  if [[ -n "$line" && "$line" =~ =\ *([0-9]+([.][0-9]+)?)\ *ms ]]; then
    eval_ms="${BASH_REMATCH[1]}"
  fi

  line="$(grep -E 'generated[[:space:]]+[0-9]+[[:space:]]+tokens|total[[:space:]]+tokens|tokens generated' "$log_file" | tail -n 1 || true)"
  if [[ -n "$line" && "$line" =~ ([0-9]+)[[:space:]]+tokens ]]; then
    tokens="${BASH_REMATCH[1]}"
  fi

  line="$(grep -E 'tokens per second|tok/s' "$log_file" | tail -n 1 || true)"
  if [[ -n "$line" ]]; then
    if [[ "$line" =~ ([0-9]+([.][0-9]+)?)\ *tokens\ per\ second ]]; then
      tps="${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ([0-9]+([.][0-9]+)?)\ *tok/s ]]; then
      tps="${BASH_REMATCH[1]}"
    fi
  fi

  echo "$load_ms,$prompt_eval_ms,$eval_ms,$tokens,$tps"
}

write_llama_runtime_csv() {
  local load_ms="$1"
  local prompt_eval_ms="$2"
  local eval_ms="$3"
  local tokens="$4"
  local tps="$5"

  {
    echo "metric,value"
    echo "model_load_time_ms,$load_ms"
    echo "prompt_eval_time_ms,$prompt_eval_ms"
    echo "eval_time_ms,$eval_ms"
    echo "total_generated_tokens,$tokens"
    echo "tokens_per_second,$tps"
  } > "$LLAMA_RUNTIME_CSV"
}

print_system_info() {
  local info
  local machine
  local os
  local total_mem
  local cpu
  local gpu

  info="$(collect_system_info)"
  IFS='|' read -r machine os total_mem cpu gpu <<< "$info"

  echo "System Information"
  echo ""
  echo "Machine:"
  echo "$machine"
  echo ""
  echo "macOS:"
  echo "$os"
  echo ""
  echo "Total Memory:"
  echo "$(to_human_gb "$total_mem") GB"
  echo ""
  echo "CPU:"
  echo "$cpu"
  echo ""
  echo "GPU:"
  echo "$gpu"
  echo ""
  echo "Model:"
  echo "$MODEL_NAME"
  echo ""
  echo "mmproj:"
  echo "$MMPROJ_NAME"
  echo ""
  echo "Context Size:"
  echo "$CONTEXT_SIZE"
  echo ""
  echo "Threads:"
  echo "$THREADS"
  echo ""
  echo "GPU Layers:"
  echo "$GPU_LAYERS"
  echo ""
  echo "Sampling Interval:"
  echo "${INTERVAL} s"
  echo ""
}

write_summary_md() {
  local start_ts="$1"
  local end_ts="$2"
  local duration_sec="$3"
  local avg_cpu="$4"
  local avg_gpu="$5"
  local avg_tps="$6"
  local peak_gpu_memory="$7"

  local sysinfo
  local machine
  local os
  local total_mem
  local cpu
  local gpu

  sysinfo="$(collect_system_info)"
  IFS='|' read -r machine os total_mem cpu gpu <<< "$sysinfo"

  {
    echo "# Benchmark Summary"
    echo ""
    echo "## System Information"
    echo ""
    echo "- Machine: $machine"
    echo "- macOS: $os"
    echo "- Total Memory: $(to_human_gb "$total_mem") GB"
    echo "- CPU: $cpu"
    echo "- GPU: $gpu"
    echo "- Model: $MODEL_NAME"
    echo "- mmproj: $MMPROJ_NAME"
    echo "- Context Size: $CONTEXT_SIZE"
    echo "- Threads: $THREADS"
    echo "- GPU Layers: $GPU_LAYERS"
    echo "- Sampling Interval: ${INTERVAL} s"
    echo ""
    echo "## Run Information"
    echo ""
    echo "- Start: $start_ts"
    echo "- End: $end_ts"
    echo "- Duration: ${duration_sec}s"
    echo "- CSV: $OUTPUT_CSV"
    echo "- Events Log: $EVENT_LOG"
    echo "- llama Runtime CSV: $LLAMA_RUNTIME_CSV"
    echo ""
    echo "## Metrics"
    echo ""
    echo "- Peak Memory Used: $(to_human_gb "$PEAK_MEMORY_USED") GB"
    echo "- Peak Memory Pressure: ${PEAK_MEMORY_PRESSURE}%"
    echo "- Peak Swap: $(to_human_gb "$PEAK_SWAP") GB"
    echo "- Peak RSS: $(to_human_gb "$PEAK_RSS") GB"
    echo "- Peak Compressed Memory: $(to_human_gb "$PEAK_COMPRESSED") GB"
    echo "- Average CPU: ${avg_cpu}%"
    echo "- Average GPU: ${avg_gpu}%"
    echo "- Peak Disk Read: $(to_human_mb "$PEAK_DISK_READ") MB/s"
    echo "- Peak Disk Write: $(to_human_mb "$PEAK_DISK_WRITE") MB/s"
    if is_number "$peak_gpu_memory"; then
      echo "- Peak GPU Memory: $(to_human_gb "$peak_gpu_memory") GB"
    else
      echo "- Peak GPU Memory: NA"
    fi
    echo "- Average Tokens/sec: $avg_tps"
  } > "$SUMMARY_MD"
}

# Required columns are included first; additional columns follow for full diagnostics.
echo "timestamp,cpu_usage,gpu_usage,memory_used,swap_used,disk_read,disk_write,llama_memory,llama_cpu,memory_total,memory_free,memory_pressure,compressed_memory,disk_iops_read,disk_iops_write,disk_iops_total,process_virtual_memory,process_threads,cpu_per_core,target_pid,target_name,memory_wired,memory_active,memory_inactive,memory_cached,vm_pageins,vm_pageouts,vm_swapins,vm_swapouts,gpu_memory,gpu_metric_mode" > "$OUTPUT_CSV"

echo "# Memory pressure and VM events" > "$EVENT_LOG"
echo "# Generated at $(date '+%Y-%m-%d %H:%M:%S')" >> "$EVENT_LOG"
echo "" >> "$EVENT_LOG"

prev_disk="$(get_disk_counters)"

start_ts="$(date '+%Y-%m-%d %H:%M:%S')"
START_EPOCH="$(date +%s)"

print_system_info

echo "[$start_ts] Monitoring PID $TARGET_PID ($TARGET_COMM) every ${INTERVAL}s"
echo "[$start_ts] Writing CSV to: $OUTPUT_CSV"
echo "[$start_ts] Writing events log to: $EVENT_LOG"

while kill -0 "$TARGET_PID" 2>/dev/null; do
  timestamp="$(date '+%Y-%m-%d %H:%M:%S')"

  mem_csv="$(get_memory_metrics)"
  IFS=',' read -r memory_total memory_used memory_free memory_pressure swap_used compressed_memory memory_wired memory_active memory_inactive memory_cached vm_pageins vm_pageouts vm_swapins vm_swapouts <<< "$mem_csv"

  cpu_usage="$(get_cpu_usage_total)"
  gpu_usage="$(get_gpu_usage)"
  cpu_per_core="$(get_cpu_per_core)"

  gpu_memory="NA"
  if [[ "$gpu_usage" == "NA" ]]; then
    gpu_memory="$(get_gpu_memory_bytes "$TARGET_PID")"
    GPU_FALLBACK_MODE="memory"
  else
    GPU_FALLBACK_MODE="usage"
  fi

  proc_csv="$(get_process_metrics "$TARGET_PID")"
  IFS=',' read -r proc_rss proc_vsz proc_cpu proc_threads <<< "$proc_csv"

  cur_disk="$(get_disk_counters)"
  IFS=',' read -r cur_rb cur_wb cur_ro cur_wo <<< "$cur_disk"
  IFS=',' read -r prev_rb prev_wb prev_ro prev_wo <<< "$prev_disk"

  delta_rb=$((cur_rb - prev_rb))
  delta_wb=$((cur_wb - prev_wb))
  delta_ro=$((cur_ro - prev_ro))
  delta_wo=$((cur_wo - prev_wo))

  if (( delta_rb < 0 )); then delta_rb=0; fi
  if (( delta_wb < 0 )); then delta_wb=0; fi
  if (( delta_ro < 0 )); then delta_ro=0; fi
  if (( delta_wo < 0 )); then delta_wo=0; fi

  interval_divisor="$INTERVAL"
  if [[ ! "$interval_divisor" =~ ^[0-9]+([.][0-9]+)?$ ]] || awk -v i="$interval_divisor" 'BEGIN{exit !(i<=0)}'; then
    interval_divisor="1"
  fi

  disk_read_bps="$(awk -v d="$delta_rb" -v i="$interval_divisor" 'BEGIN{printf "%.0f", d/i}')"
  disk_write_bps="$(awk -v d="$delta_wb" -v i="$interval_divisor" 'BEGIN{printf "%.0f", d/i}')"
  disk_iops_read="$(awk -v d="$delta_ro" -v i="$interval_divisor" 'BEGIN{printf "%.0f", d/i}')"
  disk_iops_write="$(awk -v d="$delta_wo" -v i="$interval_divisor" 'BEGIN{printf "%.0f", d/i}')"
  disk_iops_total=$((disk_iops_read + disk_iops_write))

  # Summary accumulators
  SAMPLE_COUNT=$((SAMPLE_COUNT + 1))

  if is_number "$cpu_usage"; then
    CPU_SUM="$(awk -v s="$CPU_SUM" -v v="$cpu_usage" 'BEGIN{printf "%.6f", s+v}')"
    CPU_COUNT=$((CPU_COUNT + 1))
  fi

  if is_number "$gpu_usage"; then
    GPU_SUM="$(awk -v s="$GPU_SUM" -v v="$gpu_usage" 'BEGIN{printf "%.6f", s+v}')"
    GPU_COUNT=$((GPU_COUNT + 1))
  fi

  if [[ "$memory_used" =~ ^[0-9]+$ ]] && (( memory_used > PEAK_MEMORY_USED )); then PEAK_MEMORY_USED=$memory_used; fi
  if [[ "$swap_used" =~ ^[0-9]+$ ]] && (( swap_used > PEAK_SWAP )); then PEAK_SWAP=$swap_used; fi
  if [[ "$compressed_memory" =~ ^[0-9]+$ ]] && (( compressed_memory > PEAK_COMPRESSED )); then PEAK_COMPRESSED=$compressed_memory; fi
  if [[ "$proc_rss" =~ ^[0-9]+$ ]] && (( proc_rss > PEAK_RSS )); then PEAK_RSS=$proc_rss; fi
  if [[ "$disk_read_bps" =~ ^[0-9]+$ ]] && (( disk_read_bps > PEAK_DISK_READ )); then PEAK_DISK_READ=$disk_read_bps; fi
  if [[ "$disk_write_bps" =~ ^[0-9]+$ ]] && (( disk_write_bps > PEAK_DISK_WRITE )); then PEAK_DISK_WRITE=$disk_write_bps; fi
  if is_number "$memory_pressure"; then
    PEAK_MEMORY_PRESSURE="$(max_float "$PEAK_MEMORY_PRESSURE" "$memory_pressure")"
  fi

  # Event detection
  if is_number "$memory_pressure"; then
    if awk -v p="$memory_pressure" -v t="$PRESSURE_THRESHOLD" 'BEGIN{exit !(p>t)}'; then
      if (( PRESSURE_HIGH_STATE == 0 )); then
        append_event "$timestamp" "Memory pressure exceeded ${PRESSURE_THRESHOLD}% (current: ${memory_pressure}%)"
        PRESSURE_HIGH_STATE=1
      fi
    else
      PRESSURE_HIGH_STATE=0
    fi
  fi

  if [[ "$swap_used" =~ ^[0-9]+$ ]]; then
    if [[ -n "$PREV_SWAP" ]] && (( swap_used > PREV_SWAP )); then
      delta_swap=$((swap_used - PREV_SWAP))
      append_event "$timestamp" "Swap usage increased by $(to_human_mb "$delta_swap") MB"
    fi
    PREV_SWAP="$swap_used"
  fi

  if [[ "$vm_pageouts" =~ ^[0-9]+$ ]]; then
    if [[ -n "$PREV_PAGEOUTS" ]] && (( vm_pageouts > PREV_PAGEOUTS )); then
      delta_pageouts=$((vm_pageouts - PREV_PAGEOUTS))
      append_event "$timestamp" "Pageouts increased by ${delta_pageouts} pages"
    fi
    PREV_PAGEOUTS="$vm_pageouts"
  fi

  if [[ "$memory_free" =~ ^[0-9]+$ ]]; then
    if (( memory_free < FREE_MEMORY_THRESHOLD_BYTES )); then
      if (( FREE_LOW_STATE == 0 )); then
        append_event "$timestamp" "Free memory below 500 MB (current: $(to_human_mb "$memory_free") MB)"
        FREE_LOW_STATE=1
      fi
    else
      FREE_LOW_STATE=0
    fi
  fi

  # Required row fields: timestamp,cpu_usage,gpu_usage,memory_used,swap_used,disk_read,disk_write,llama_memory,llama_cpu
  echo "$timestamp,$cpu_usage,$gpu_usage,$memory_used,$swap_used,$disk_read_bps,$disk_write_bps,$proc_rss,$proc_cpu,$memory_total,$memory_free,$memory_pressure,$compressed_memory,$disk_iops_read,$disk_iops_write,$disk_iops_total,$proc_vsz,$proc_threads,$cpu_per_core,$TARGET_PID,$TARGET_COMM,$memory_wired,$memory_active,$memory_inactive,$memory_cached,$vm_pageins,$vm_pageouts,$vm_swapins,$vm_swapouts,$gpu_memory,$GPU_FALLBACK_MODE" >> "$OUTPUT_CSV"

  prev_disk="$cur_disk"

  sleep "$INTERVAL"
done

end_ts="$(date '+%Y-%m-%d %H:%M:%S')"
END_EPOCH="$(date +%s)"

duration_sec=$((END_EPOCH - START_EPOCH))

avg_cpu="NA"
avg_gpu="NA"
if (( CPU_COUNT > 0 )); then
  avg_cpu="$(awk -v s="$CPU_SUM" -v c="$CPU_COUNT" 'BEGIN{printf "%.2f", s/c}')"
fi
if (( GPU_COUNT > 0 )); then
  avg_gpu="$(awk -v s="$GPU_SUM" -v c="$GPU_COUNT" 'BEGIN{printf "%.2f", s/c}')"
fi

llama_metrics="$(parse_llama_runtime_metrics "$LLAMA_LOG")"
IFS=',' read -r llama_load_ms llama_prompt_eval_ms llama_eval_ms llama_tokens llama_tps <<< "$llama_metrics"
write_llama_runtime_csv "$llama_load_ms" "$llama_prompt_eval_ms" "$llama_eval_ms" "$llama_tokens" "$llama_tps"

avg_tps="NA"
if is_number "$llama_tps"; then
  avg_tps="$llama_tps"
fi

peak_gpu_memory="NA"
peak_gpu_memory="$(awk -F',' 'NR>1 && $29 ~ /^[0-9]+$/ { if ($29 > max) max=$29 } END { if (max>0) print max; else print "NA" }' "$OUTPUT_CSV")"

write_summary_md "$start_ts" "$end_ts" "$duration_sec" "$avg_cpu" "$avg_gpu" "$avg_tps" "$peak_gpu_memory"

echo ""
echo "Benchmark Summary"
echo "Duration: ${duration_sec}s"
echo "Peak Memory Used: $(to_human_gb "$PEAK_MEMORY_USED") GB"
echo "Peak Memory Pressure: ${PEAK_MEMORY_PRESSURE}%"
echo "Peak Swap: $(to_human_gb "$PEAK_SWAP") GB"
echo "Peak RSS: $(to_human_gb "$PEAK_RSS") GB"
echo "Peak Compressed Memory: $(to_human_gb "$PEAK_COMPRESSED") GB"
echo "Average CPU: ${avg_cpu}%"
echo "Average GPU: ${avg_gpu}%"
echo "Peak Disk Read: $(to_human_mb "$PEAK_DISK_READ") MB/s"
echo "Peak Disk Write: $(to_human_mb "$PEAK_DISK_WRITE") MB/s"
if is_number "$peak_gpu_memory"; then
  echo "Peak GPU Memory: $(to_human_gb "$peak_gpu_memory") GB"
else
  echo "Peak GPU Memory: NA"
fi
echo "Average Tokens/sec: $avg_tps"
echo ""
echo "[$end_ts] Target process exited. Benchmark stopped."
echo "[$end_ts] CSV saved: $OUTPUT_CSV"
echo "[$end_ts] Events log saved: $EVENT_LOG"
echo "[$end_ts] llama runtime CSV saved: $LLAMA_RUNTIME_CSV"
echo "[$end_ts] Summary markdown saved: $SUMMARY_MD"