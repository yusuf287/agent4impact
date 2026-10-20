# AGENTS.md — rules for AI coding agents (Antigravity, agy, Gemini CLI)

We are building a **heat-response planning assistant** for Challenge 1 (Urban Heat). Read `docs/CHALLENGE.md` first.
Humans make the decisions (city, track, what to cut); you do the wiring.

## How the project works
- `domains/urban_heat/domain.yaml` (hand-written) + `team.yaml` (agent team) + `generated.yaml` (written by the CLI)
  drive the agent's prompt and tools. **Change YAML first; edit Python only when YAML can't express it.**
- `kit_agent/` is the ADK agent. `kit/` is the CLI (`python -m kit <command>`): it logs every action and writes undo scripts.
- Data lives in BigQuery dataset `a4i_climate` (loaded by the challenge notebook or `bash scripts/load.sh <city>` in the team repo).

## Commands (repo root, venv active)
| Need | Command |
|---|---|
| Setup | `python -m kit init` · `python -m kit doctor --llm` |
| SQL / views | `python -m kit sql --view v_x --query "SELECT … FROM \`${PROJECT_ID}.${DATASET}.t\`"` or `--file f.sql` |
| Train model | `python -m kit model NAME --type linear --source v_x --label offset_f --features auto …` |
| Extra data | `python -m kit add-data <file\|url> [--table t]` (check the license first) |
| Agent team | edit `team.yaml` · `python -m kit roles` · `python -m kit team-check` |
| Run | `python -m kit web` · `python -m kit ui` · `python -m kit cli` |
| Rehearse | `python -m kit rehearse` |
| Deploy | `python -m kit deploy runtime` (or `a2a` for Cloud Run) |
| Undo | `bash scripts/rollback_all.sh` |

## Rules
1. Plan, then ask before deploying, deleting, enabling APIs, IAM changes or anything that costs money.
2. After YAML/code changes: `kit team-check`, `kit doctor`; after agent changes: `kit rehearse`.
3. The model predicts an **offset** (degrees above the city average), never a temperature. Keep one unit (°F or °C) everywhere.
4. The agent must **call** the BigQuery ML model (ML.EXPLAIN_PREDICT) for any "where/why" answer, not describe raw readings.
5. No race or individual-level data as model input. Equity audit happens on the output only.
6. Every number traces to a tool result. No invented figures.
7. Agent SQL is read-only (`WriteMode.BLOCKED`). Never commit secrets (`.env`).
8. Human approval: the `approver` role prepares; the ROOT agent's `request_approval` pauses. Never put `approval` inside the team.
9. `logs/` and `rollback/` are append-only; never delete or auto-expire them.
10. After 3:30 PM: bug fixes only. Small diffs; the demo path must always work.
11. No literal curly braces in `team.yaml` instructions (ADK state templating).

## Skills (`.agents/skills/`)
`add-data`, `add-model`, `add-agent-team`, `rehearse-demo`, `deploy-and-backup`, `pitch-builder`.
