#!/usr/bin/env bash
# Deploy the agent. Usage: bash scripts/deploy.sh <runtime|a2a>
# Thin wrapper so there is ONE deploy implementation (kit/deploy_cmd.py: logging, undo scripts, staging).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m kit deploy "${1:?usage: deploy.sh <runtime|a2a>}"
