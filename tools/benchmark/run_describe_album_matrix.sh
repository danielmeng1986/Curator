#!/usr/bin/env bash

set -euo pipefail

# Batch benchmark matrix for describe_workspace_album.py with multiple ctx/thread combos.
# Usage:
#   tools/benchmark/run_describe_album_matrix.sh
#   tools/benchmark/run_describe_album_matrix.sh 39 5
#
# Optional overrides:
#   INTERVAL=1
#   GPU_LAYERS=999
#   CTX_LIST="2048 4096 8192"
#   THREADS_LIST="4 8 12"
#   MODEL_NAME="Qwen2.5-VL-7B-Instruct-BF16.gguf"
#   MMPROJ_NAME="mmproj-BF16.gguf"
#   EXTRA_ARGS="--max-tokens 800 --temperature 0.2 --image-max-tokens 384"

ALBUM_ID="${1:-39}"
SAMPLE_COUNT="${2:-5}"

INTERVAL="${INTERVAL:-1}"
GPU_LAYERS="${GPU_LAYERS:-999}"
CTX_LIST="${CTX_LIST:-2048 4096 8192}"
THREADS_LIST="${THREADS_LIST:-4 8 12}"
MODEL_NAME="${MODEL_NAME:-Qwen2.5-VL-7B-Instruct-BF16.gguf}"
MMPROJ_NAME="${MMPROJ_NAME:-mmproj-BF16.gguf}"
EXTRA_ARGS="${EXTRA_ARGS:---max-tokens 800 --temperature 0.2 --image-max-tokens 384}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="tools/benchmark/runs_${STAMP}"
mkdir -p "$OUT_DIR"

RESULTS_CSV="$OUT_DIR/matrix_results.csv"
RUN_LOG="$OUT_DIR/matrix_run.log"

printf "run_id,album_id,sample_count,ctx_size,threads,gpu_layers,duration_s,avg_cpu_pct,avg_gpu_pct,peak_memory_gb,peak_swap_gb,peak_rss_gb,peak_compressed_gb,peak_disk_read_mbs,peak_disk_write_mbs,peak_gpu_memory_gb,avg_tokens_per_sec,csv_path,summary_path,runtime_path,events_path,json_output_path\n" > "$RESULTS_CSV"

echo "Batch started at $(date '+%Y-%m-%d %H:%M:%S')" | tee "$RUN_LOG"
echo "OUT_DIR=$OUT_DIR" | tee -a "$RUN_LOG"

run_idx=0
for ctx in $CTX_LIST; do
  for th in $THREADS_LIST; do
    run_idx=$((run_idx + 1))
    run_id="run$(printf '%02d' "$run_idx")_c${ctx}_t${th}"

    base="$OUT_DIR/${run_id}"
    bench_csv="${base}.csv"
    summary_md="${base}_summary.md"
    runtime_csv="${base}_llama_runtime.csv"
    events_log="${base}_events.log"
    llama_log="${base}_llama.log"
    json_out="${base}_describe_output.json"

    echo "[$(date '+%H:%M:%S')] START $run_id" | tee -a "$RUN_LOG"

    cmd="python3 scripts/describe_workspace_album.py ${ALBUM_ID} ${SAMPLE_COUNT} --ctx-size ${ctx} --threads ${th} --gpu-layers ${GPU_LAYERS} ${EXTRA_ARGS} > ${json_out}"

    ./tools/benchmark/macos_llm_benchmark.sh \
      -x "$cmd" \
      -i "$INTERVAL" \
      -o "$bench_csv" \
      --events-log "$events_log" \
      --summary-md "$summary_md" \
      --llama-log "$llama_log" \
      --llama-runtime-csv "$runtime_csv" \
      --model "$MODEL_NAME" \
      --mmproj "$MMPROJ_NAME" \
      --ctx-size "$ctx" \
      --threads "$th" \
      --gpu-layers "$GPU_LAYERS"

    duration="$(awk -F': ' '/^- Duration:/ {gsub(/s/,"",$2); print $2; exit}' "$summary_md")"
    avg_cpu="$(awk -F': ' '/^- Average CPU:/ {gsub(/%/,"",$2); print $2; exit}' "$summary_md")"
    avg_gpu="$(awk -F': ' '/^- Average GPU:/ {gsub(/%/,"",$2); print $2; exit}' "$summary_md")"
    peak_mem="$(awk -F': ' '/^- Peak Memory Used:/ {gsub(/ GB/,"",$2); print $2; exit}' "$summary_md")"
    peak_swap="$(awk -F': ' '/^- Peak Swap:/ {gsub(/ GB/,"",$2); print $2; exit}' "$summary_md")"
    peak_rss="$(awk -F': ' '/^- Peak RSS:/ {gsub(/ GB/,"",$2); print $2; exit}' "$summary_md")"
    peak_comp="$(awk -F': ' '/^- Peak Compressed Memory:/ {gsub(/ GB/,"",$2); print $2; exit}' "$summary_md")"
    peak_read="$(awk -F': ' '/^- Peak Disk Read:/ {gsub(/ MB\/s/,"",$2); print $2; exit}' "$summary_md")"
    peak_write="$(awk -F': ' '/^- Peak Disk Write:/ {gsub(/ MB\/s/,"",$2); print $2; exit}' "$summary_md")"
    peak_gpu_mem="$(awk -F': ' '/^- Peak GPU Memory:/ {gsub(/ GB/,"",$2); print $2; exit}' "$summary_md")"
    avg_tps="$(awk -F',' '$1=="tokens_per_second" {print $2; exit}' "$runtime_csv")"

    printf "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s\n" \
      "$run_id" "$ALBUM_ID" "$SAMPLE_COUNT" "$ctx" "$th" "$GPU_LAYERS" \
      "${duration:-NA}" "${avg_cpu:-NA}" "${avg_gpu:-NA}" \
      "${peak_mem:-NA}" "${peak_swap:-NA}" "${peak_rss:-NA}" "${peak_comp:-NA}" \
      "${peak_read:-NA}" "${peak_write:-NA}" "${peak_gpu_mem:-NA}" "${avg_tps:-NA}" \
      "$bench_csv" "$summary_md" "$runtime_csv" "$events_log" "$json_out" \
      >> "$RESULTS_CSV"

    echo "[$(date '+%H:%M:%S')] DONE  $run_id" | tee -a "$RUN_LOG"
  done
done

MARKDOWN_REPORT="$OUT_DIR/matrix_report.md"
{
  echo "# Describe Album Benchmark Matrix"
  echo
  echo "- Album ID: $ALBUM_ID"
  echo "- Sample Count: $SAMPLE_COUNT"
  echo "- GPU Layers: $GPU_LAYERS"
  echo "- Interval: ${INTERVAL}s"
  echo "- Started: $STAMP"
  echo
  echo "## Result Table"
  echo
  echo "| run_id | ctx | threads | duration(s) | avg_cpu(%) | avg_gpu(%) | peak_mem(GB) | peak_swap(GB) | peak_disk_write(MB/s) | avg_tps |"
  echo "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
  awk -F',' 'NR>1 {
    printf "| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |\n",
      $1,$4,$5,$7,$8,$9,$10,$11,$15,$17
  }' "$RESULTS_CSV"
  echo
  echo "## Files"
  echo
  echo "- Raw matrix CSV: $RESULTS_CSV"
  echo "- Run log: $RUN_LOG"
} > "$MARKDOWN_REPORT"

echo ""
echo "Batch finished."
echo "Results CSV: $RESULTS_CSV"
echo "Markdown report: $MARKDOWN_REPORT"
