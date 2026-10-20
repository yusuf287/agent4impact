#!/usr/bin/env bash
# Run auto-generated undo scripts, newest first. Usage: bash scripts/rollback_all.sh [run_id_substring]
# Undo scripts are kept after running (renamed .done) -- nothing is auto-deleted.
set -uo pipefail
source "$(dirname "$0")/lib.sh"
FILTER="${1:-}"
for f in $(ls -1r "$ROLLBACK_DIR"/undo_*"$FILTER"*.sh 2>/dev/null); do
  log "ROLLBACK: running $f"
  bash "$f" 2>&1 | tee -a "$OPLOG"
  mv "$f" "$f.done"
done
log "Rollback complete."
