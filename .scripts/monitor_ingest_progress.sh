#!/usr/bin/env bash
set -euo pipefail

LOG_FILE="${1:-.scripts/out/ingest_phase2_vector.log}"
TOTAL_NODES="${2:-8963}"
INTERVAL_SEC="${3:-60}"

if [[ ! -f "$LOG_FILE" ]]; then
  echo "[ERROR] Log file not found: $LOG_FILE" >&2
  exit 1
fi

while true; do
  if ! pgrep -f "python ingest_vault.py" >/dev/null 2>&1; then
    echo "$(date '+%F %T') | ingest process not found | monitoring stopped"
    exit 0
  fi

  METRICS="$(
    tr '\r' '\n' < "$LOG_FILE" | awk '
      BEGIN { starts=0; done=0; cur=0; denom=2048; max_denom=0; }
      /Generating embeddings:/ {
        if (match($0, /([0-9]+)\/([0-9]+)/, m)) {
          n=m[1]+0; d=m[2]+0;
          denom=d;
          if (d > max_denom) max_denom=d;
          if (n==0) starts++;
          cur=n;
          if (n==d) done++;
        }
      }
      END {
        if (starts>0) batch_idx=starts-1; else batch_idx=0;
        if (max_denom==0) max_denom=2048;
        print batch_idx, cur, denom, done, max_denom;
      }
    '
  )"

  read -r BATCH_IDX CUR DENOM DONE_MARKS BASE_DENOM <<< "$METRICS"
  PROCESSED=$(( BATCH_IDX * BASE_DENOM + CUR ))
  if (( PROCESSED > TOTAL_NODES )); then
    PROCESSED="$TOTAL_NODES"
  fi

  PCT="$(awk -v p="$PROCESSED" -v t="$TOTAL_NODES" 'BEGIN { if (t>0) printf "%.2f", (p/t)*100; else print "0.00"; }')"

  echo "$(date '+%F %T') | real_progress=${PCT}% | processed=${PROCESSED}/${TOTAL_NODES} | batch=$((BATCH_IDX+1)) | batch_pos=${CUR}/${DENOM}"
  sleep "$INTERVAL_SEC"
done
