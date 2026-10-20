# AGENTS.md — instructions for AI coding agents (Antigravity, Claude Code, Gemini CLI)

This repo is a **plug-in kit** for building multi-agent data apps on Google Cloud for the Agents for Impact
hackathon. Humans drive the *decisions*; you do the *wiring*. Read docs/PLAYBOOK.md for strategy.

## How the project works (read before editing)
- Everything domain-specific lives in `domains/<name>/`: `domain.yaml` (hand-written), `team.yaml` (agent team),
  `generated.yaml` (written by the CLI — never hand-edit unless asked). The agent's prompts are *generated* from them.
- `kit_agent/` is the ADK agent. Core code (`agent.py`, `registry.py`, `team.py`, `roles.py`, `tools/`) is stable —
  **change domain YAML first; edit Python only when YAML cannot express the need.**
- `kit/` is the CLI: `python -m kit <command>`. Prefer these commands over ad-hoc scripts; they log, document and undo.

## Commands (always from repo root, venv active)
| Need | Command |
|---|---|
| New challenge | `python -m kit new-domain <name>` then `python -m kit init` |
| Load data (file/URL/Toronto CKAN) | `python -m kit add-data <path\|url\|ckan:name> [--table t]` |
| View / SQL | `python -m kit sql --view v_x --query "SELECT ... FROM \`${PROJECT_ID}.${DATASET}.t\`"` |
| Train a model | `python -m kit model NAME --type logistic\|linear\|boosted_class\|boosted_reg\|kmeans\|arima --source v_x --label y --features auto --train-filter "..." --predict-filter "..." --id-cols a,b` |
| Embeddings (experimental) | `python -m kit embed --table t --id-col id --text-col txt` |
| Agent team | edit `domains/<x>/team.yaml`; `python -m kit roles`; `python -m kit team-check` |
| Preflight | `python -m kit doctor --llm` |
| Run | `python -m kit web` (ADK trace UI) · `python -m kit ui` (demo UI) · `python -m kit cli` |
| Demo rehearsal | `python -m kit rehearse` |
| Deploy | `python -m kit deploy runtime` or `a2a` |
| Undo everything | `bash scripts/rollback_all.sh` |

## Rules
1. **Plan first, then ask** before: deploying, deleting anything, enabling APIs, touching IAM, or running anything that costs money.
2. After any YAML/code change run `python -m kit team-check` and `python -m kit doctor`. After agent changes run `python -m kit rehearse`.
3. Instructions in `team.yaml` must not contain literal curly braces (ADK state templating). Use `{key?}` only to read state.
4. Every claim an agent makes must trace to a tool result. Never add "fake" numbers to prompts or demos; synthetic data must be labelled synthetic in `domain.yaml` descriptions.
5. Actions affecting people (alerts, evacuations, dispatch) are *proposals*; keep the `approver` role / `request_approval` tool in the flow.
6. SQL from the agent is read-only. Do not change `WriteMode.BLOCKED`.
7. Never print or commit secrets. `.env` is local. No real personal data in prompts, data or logs.
8. Logs (`logs/`) and rollback scripts (`rollback/`) are append-only and must never be deleted or auto-expired.
9. Keep diffs small; the demo path must work at all times. After **3:30 PM on event day: bug fixes only**.
10. The ADK version may be 1.x or 2.x: if an import breaks, check `adk --version`, compare with the lab agent code, fix in one place (`registry.py`/`agent.py`).

## Skills available (`.agents/skills/`)
`challenge-to-domain`, `add-data`, `add-model`, `add-agent-team`, `rehearse-demo`, `deploy-and-backup`, `pitch-builder`.
