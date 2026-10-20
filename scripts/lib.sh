#!/usr/bin/env bash
# Shared helpers: operation logging + automatic rollback scripts.
# Source this from every script:  source "$(dirname "$0")/lib.sh"
#
# Policy: logs and rollback files are NEVER auto-deleted (infinite retention).

KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$KIT_ROOT/logs"
ROLLBACK_DIR="$KIT_ROOT/rollback"
mkdir -p "$LOG_DIR" "$ROLLBACK_DIR"

SCRIPT_NAME="$(basename "${BASH_SOURCE[1]:-$0}" .sh)"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)_${SCRIPT_NAME}"
OPLOG="$LOG_DIR/operations.log"          # single append-only operational log
UNDO_FILE="$ROLLBACK_DIR/undo_${RUN_ID}.sh"

log() { echo "$(date -u +%FT%TZ) [$SCRIPT_NAME] $*" | tee -a "$OPLOG"; }

# Run a command, logging the command and its exit code.
run() {
  log "RUN: $*"
  "$@" 2>&1 | tee -a "$OPLOG"
  local rc=${PIPESTATUS[0]}
  log "EXIT($rc): $*"
  return $rc
}

# Register an undo command. Undo commands run newest-first via rollback_all.sh.
track_undo() {
  if [ ! -f "$UNDO_FILE" ]; then
    printf '#!/usr/bin/env bash\n# Auto-generated rollback for %s\n' "$RUN_ID" > "$UNDO_FILE"
    chmod +x "$UNDO_FILE"
  fi
  # prepend so the last action is undone first
  { head -n 2 "$UNDO_FILE"; echo "$1"; tail -n +3 "$UNDO_FILE"; } > "$UNDO_FILE.tmp" && mv "$UNDO_FILE.tmp" "$UNDO_FILE"
  log "UNDO registered: $1"
}

require_env() {
  for v in "$@"; do
    if [ -z "${!v:-}" ]; then log "ERROR: env var $v is not set (run: source .env)"; exit 1; fi
  done
}

log "=== start $RUN_ID ==="
