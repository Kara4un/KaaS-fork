#!/usr/bin/env bash
set -euo pipefail

# One-command launcher for personal GigaChat key (PERS scope)
# Usage:
#   ./run_personal.sh
#   ./run_personal.sh --no-ingest
#   GIGACHAT_AUTH_DATA=... ./run_personal.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -d "venv-fresh" ]]; then
  echo "[INFO] venv-fresh not found, creating..."
  python3 -m venv venv-fresh
fi

source venv-fresh/bin/activate

export GIGACHAT_SCOPE="${GIGACHAT_SCOPE:-GIGACHAT_API_PERS}"
export GIGACHAT_VERIFY_SSL_CERTS="false"

if [[ -z "${GIGACHAT_AUTH_DATA:-}" ]]; then
  echo "[ERROR] GIGACHAT_AUTH_DATA is not set."
  echo "Set it and rerun:"
  echo "  export GIGACHAT_AUTH_DATA='<your_personal_token_or_auth_data>'"
  exit 2
fi

RUN_INGEST=1
if [[ "${1:-}" == "--no-ingest" ]]; then
  RUN_INGEST=0
fi

if [[ "$RUN_INGEST" -eq 1 ]]; then
  echo "[INFO] Running ingestion with personal scope: $GIGACHAT_SCOPE"
  python ingest_vault.py \
    --folders ontology 0-Slipbox 2-Areas/Code 2-Areas/MOCs \
    --storage-graph ./storage_graph \
    --storage-vector ./storage_vector \
    --gigachat-auth-data "$GIGACHAT_AUTH_DATA" \
    --gigachat-scope "$GIGACHAT_SCOPE"
else
  echo "[INFO] Skipping ingestion (--no-ingest)."
fi

echo "[INFO] Starting Streamlit app..."
streamlit run app.py
