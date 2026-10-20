#!/usr/bin/env bash
# Deploy the agent. Usage: bash scripts/deploy.sh <runtime|a2a>
#   runtime : managed Agent Runtime (Agent Engine) -> then register in Gemini Enterprise
#   a2a     : Cloud Run A2A server (other agents call it via RemoteA2aAgent)
set -euo pipefail
source "$(dirname "$0")/lib.sh"
cd "$KIT_ROOT"
set -a; source .env; set +a
require_env GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_REGION AGENT_NAME
MODE="${1:?usage: deploy.sh <runtime|a2a>}"
BUCKET="gs://${GOOGLE_CLOUD_PROJECT}-agent-staging"

case "$MODE" in
  runtime)
    gsutil ls "$BUCKET" >/dev/null 2>&1 || { run gcloud storage buckets create "$BUCKET" --location="$GOOGLE_CLOUD_REGION"; track_undo "gcloud storage rm -r $BUCKET"; }
    # Engine runs as the compute default SA in lab projects (already has BigQuery access)
    PN="$(gcloud projects describe "$GOOGLE_CLOUD_PROJECT" --format='value(projectNumber)')"
    echo "{\"service_account\": \"${PN}-compute@developer.gserviceaccount.com\"}" > kit_agent/.agent_engine_config.json
    OUT="$(adk deploy agent_engine --project="$GOOGLE_CLOUD_PROJECT" --region="$GOOGLE_CLOUD_REGION" \
      --staging_bucket="$BUCKET" --display_name="$AGENT_NAME" \
      --requirements_file=./requirements.txt --otel_to_cloud kit_agent 2>&1 | tee -a "$OPLOG")"
    RES="$(echo "$OUT" | grep -o 'projects/[^ ]*reasoningEngines/[0-9]*' | tail -1 || true)"
    log "Agent Runtime resource: ${RES:-<not captured, copy from console>}"
    echo "$RES" > "$LOG_DIR/last_runtime_resource.txt"
    [ -n "$RES" ] && track_undo "python -c \"import vertexai; from vertexai import agent_engines as a; vertexai.init(project='$GOOGLE_CLOUD_PROJECT', location='$GOOGLE_CLOUD_REGION'); a.get('$RES').delete(force=True)\""
    ;;
  a2a)
    run adk deploy cloud_run --project "$GOOGLE_CLOUD_PROJECT" --region "$GOOGLE_CLOUD_REGION" \
      --service_name "$AGENT_NAME" --a2a kit_agent -- --allow-unauthenticated \
      --set-env-vars="GOOGLE_CLOUD_LOCATION=global"
    track_undo "gcloud run services delete $AGENT_NAME --region $GOOGLE_CLOUD_REGION --project $GOOGLE_CLOUD_PROJECT --quiet"
    log "Now edit scripts/agent_card.template.json (url!) and copy to your caller as agent-card.json"
    ;;
  *) echo "mode must be runtime|a2a"; exit 1 ;;
esac
log "Deploy ($MODE) finished. Undo scripts live in rollback/."
