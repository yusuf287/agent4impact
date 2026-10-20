# Heat Planning Assistant — Agents for Impact 2026, Challenge 1 (Urban Heat)

An ADK agent that helps a city planner decide where to put heat help: predicts how much hotter a location runs
than the city average (BigQuery ML), explains why, shows who lives there, drafts the council proposal, and audits
whether the picks reached the people who need it most. Details: `docs/CHALLENGE.md`.

```
README.md  AGENTS.md            this file · rules for AI coding agents
docs/CHALLENGE.md               objective, must-haves, judging, traps
domains/urban_heat/             domain.yaml (prompt, tables, routing) · team.yaml (agent team)
kit_agent/                      the ADK agent (root agent, tools, team builder)
kit/                            CLI: python -m kit <command>
ui/                             demo UI: chat + live tool trace + Approve/Reject
scripts/                        smoke_test.py · deploy.sh · rollback_all.sh
.agents/skills/                 Antigravity skills
logs/  rollback/                action log + undo scripts (kept)
.archive/                       zipped older material (not used)
```

## Setup (Cloud Shell, from the repo root)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m kit init                 # creates .env (project, region us-east1, dataset a4i_climate), enables APIs
python -m kit doctor --llm         # everything should be OK
python scripts/smoke_test.py "What tables do you have?"
python -m kit web                  # ADK dev UI   ·   python -m kit ui  -> our demo UI on :8080
```
Data comes from the challenge notebook (Colab Enterprise) or `bash scripts/load.sh <city>` in the team repo.

## Commands
| Need | Command |
|---|---|
| View / SQL | `python -m kit sql --view v_x --query "SELECT …"` · `--file f.sql` |
| Train the offset model | `python -m kit model heat_offset --type linear --source v_training --label offset_f --features auto` |
| Extra data (check license) | `python -m kit add-data <file\|url> --table t` |
| Agent team | edit `domains/urban_heat/team.yaml` · `python -m kit team-check` |
| Rehearse demo | `python -m kit rehearse` |
| Deploy | `python -m kit deploy runtime` (Agent Runtime) · `a2a` (Cloud Run) |
| Undo | `bash scripts/rollback_all.sh` |

## Status
Agent code was checked against ADK 2.x source but not yet run against a live project: run the smoke test first.
Still to build: training view + model SQL, the custom `explain_location` tool (ML.EXPLAIN_PREDICT), BigQuery MCP
connection, equity-audit tool.
