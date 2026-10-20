#!/usr/bin/env bash
# Load every CSV/Parquet in DATA_DIR into BigQuery, create views, apply column
# descriptions (the thing that makes NL->SQL work), optionally train the BQML model.
#
# Usage: bash scripts/load_data.sh <data_dir> [--views] [--model]
#   <data_dir>  folder of .csv / .parquet files (table name = file name)
#   --views     run $VIEWS_SQL (envsubst'd with PROJECT_ID, DATASET)
#   --model     run $MODEL_SQL
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cd "$KIT_ROOT"
set -a; source .env; set +a
require_env GOOGLE_CLOUD_PROJECT BQ_DATASET DOMAIN_FILE

DATA_DIR="${1:?usage: load_data.sh <data_dir> [--views] [--model]}"; shift || true
export PROJECT_ID="$GOOGLE_CLOUD_PROJECT" DATASET="$BQ_DATASET"

for f in "$DATA_DIR"/*.csv "$DATA_DIR"/*.parquet; do
  [ -e "$f" ] || continue
  t="$(basename "${f%.*}")"
  fmt=CSV; [[ "$f" == *.parquet ]] && fmt=PARQUET
  extra=(); [ "$fmt" = CSV ] && extra=(--autodetect --skip_leading_rows=1)
  run bq --project_id="$PROJECT_ID" load --source_format=$fmt --replace "${extra[@]}" "$DATASET.$t" "$f"
  track_undo "bq --project_id=$PROJECT_ID rm -f -t $DATASET.$t"
done

for arg in "$@"; do
  case "$arg" in
    --views) require_env VIEWS_SQL
      envsubst < "$VIEWS_SQL" > /tmp/views.rendered.sql
      run bq --project_id="$PROJECT_ID" query --use_legacy_sql=false < /tmp/views.rendered.sql ;;
    --model) require_env MODEL_SQL
      envsubst < "$MODEL_SQL" > /tmp/model.rendered.sql
      run bq --project_id="$PROJECT_ID" query --use_legacy_sql=false < /tmp/model.rendered.sql ;;
  esac
done

# Column/table descriptions from the domain file (agents read these!)
run python scripts/apply_descriptions.py

log "Load complete. Verify: bq ls $DATASET"
