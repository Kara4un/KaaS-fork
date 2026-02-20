#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

source venv-fresh/bin/activate

: "${GIGACHAT_AUTH_DATA:?GIGACHAT_AUTH_DATA is required}"
export GIGACHAT_SCOPE="${GIGACHAT_SCOPE:-GIGACHAT_API_PERS}"

attempt=1
max_attempts=5
INGEST_PHASE="${INGEST_PHASE:-all}"   # all|graph|vector
INGEST_RESET="${INGEST_RESET:-false}" # true|false
INGEST_RESUME="${INGEST_RESUME:-true}" # true|false

EXTRA_ARGS=("--phase" "$INGEST_PHASE" "--retry-max" "5")
if [[ "$INGEST_RESET" == "true" ]]; then
  EXTRA_ARGS+=("--reset")
fi
if [[ "$INGEST_RESUME" == "true" ]]; then
  EXTRA_ARGS+=("--resume")
fi

while (( attempt <= max_attempts )); do
  echo "[INFO] Ingest attempt ${attempt}/${max_attempts} started at $(date '+%Y-%m-%d %H:%M:%S')"
  echo "[INFO] Phase=${INGEST_PHASE} reset=${INGEST_RESET} resume=${INGEST_RESUME}"
  if python ingest_vault.py \
    --folders ontology 0-Slipbox 1-Projects 2-Areas 3-Resources \
    --storage-graph ./storage_graph \
    --storage-vector ./storage_vector \
    --gigachat-auth-data "$GIGACHAT_AUTH_DATA" \
    --gigachat-scope "$GIGACHAT_SCOPE" \
    "${EXTRA_ARGS[@]}"; then
    echo "[INFO] Ingest completed successfully on attempt ${attempt}."
    break
  fi

  echo "[WARN] Ingest failed on attempt ${attempt}. Retrying in 20s..."
  attempt=$((attempt + 1))
  sleep 20

done

if (( attempt > max_attempts )); then
  echo "[ERROR] Ingest failed after ${max_attempts} attempts."
  exit 1
fi

echo "[INFO] Starting Streamlit app..."
exec streamlit run app.py
