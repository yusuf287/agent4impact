#!/usr/bin/env bash
# One-shot environment bootstrap (Cloud Shell or local). Usage: bash scripts/bootstrap.sh
set -euo pipefail
source "$(dirname "$0")/lib.sh"

cd "$KIT_ROOT"

# 1. .env
if [ ! -f .env ]; then
  cp .env.example .env
  track_undo "rm -f '$KIT_ROOT/.env'"
  PID="$(gcloud config get-value project 2>/dev/null || true)"
  [ -n "$PID" ] && sed -i "s/^GOOGLE_CLOUD_PROJECT=.*/GOOGLE_CLOUD_PROJECT=$PID/" .env
  log "Created .env (project=$PID). Review it, then: source .env"
fi
set -a; source .env; set +a
require_env GOOGLE_CLOUD_PROJECT

# 2. venv + deps
if [ ! -d .venv ]; then
  if command -v uv >/dev/null 2>&1; then run uv venv .venv; else run python3 -m venv .venv; fi
  track_undo "rm -rf '$KIT_ROOT/.venv'"
fi
source .venv/bin/activate
if command -v uv >/dev/null 2>&1; then run uv pip install -r requirements.txt; else run pip install -r requirements.txt; fi

# 3. APIs (idempotent)
run gcloud services enable aiplatform.googleapis.com bigquery.googleapis.com \
  run.googleapis.com cloudbuild.googleapis.com storage.googleapis.com \
  mapstools.googleapis.com --project "$GOOGLE_CLOUD_PROJECT" || log "WARN: some APIs failed to enable (often already enabled / not permitted)"

# 4. Dataset
if ! bq --project_id="$GOOGLE_CLOUD_PROJECT" show "$BQ_DATASET" >/dev/null 2>&1; then
  run bq --project_id="$GOOGLE_CLOUD_PROJECT" mk --location="$BQ_LOCATION" --dataset "$GOOGLE_CLOUD_PROJECT:$BQ_DATASET"
  track_undo "bq --project_id=$GOOGLE_CLOUD_PROJECT rm -r -f -d $GOOGLE_CLOUD_PROJECT:$BQ_DATASET"
fi

run adk --version
log "Bootstrap done. Next: source .venv/bin/activate && set -a && source .env && set +a"
