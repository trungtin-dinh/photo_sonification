#!/usr/bin/env bash
set -Eeuo pipefail
export MAX_RENDER_SECONDS="${MAX_RENDER_SECONDS:-900}"
python3 -m streamlit run app_local.py \
  --server.headless=true \
  --server.address=127.0.0.1 \
  --server.port="${PHOTO_SONIFICATION_PORT:-8501}" \
  --server.maxUploadSize=2048 \
  --browser.gatherUsageStats=false
