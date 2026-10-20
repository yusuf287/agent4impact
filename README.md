# impact-agent — Agents for Impact plug-in kit

Domain-agnostic ADK multi-agent kit. **Plug in data, models, tools and agents with one command or one YAML edit.**
Worked example: **food equity** (`domains/food_equity`, synthetic data). Antigravity-ready (`AGENTS.md`, `.agents/skills/`).

```
impact-agent/
  README.md  AGENTS.md          this file · rules for AI coding agents (Antigravity reads AGENTS.md)
  docs/                         docs/PLAYBOOK.md (event strategy) · ANTIGRAVITY.md (setup + prompts) · IDEAS.md (ideas, decision rule, fact-check list)
  kit/                          the CLI:  python -m kit <command>
  kit_agent/                    ADK agent (root + viz agent + YAML-defined team); core/ is ADK-free
  domains/<name>/               domain.yaml · team.yaml · generated.yaml   (food_equity example, lights_out draft, _template)
  ui/                           demo UI with live tool-call trace
  scripts/                      bash helpers, smoke_test.py, agent_card.template.json
  .agents/skills/               7 Antigravity skills
  logs/  rollback/              action log and undo scripts (kept forever)
  .archive/                     zip of your earlier scaffold (v1)
```

## The plug-in commands
| You want to… | Command |
|---|---|
| start a new challenge | `python -m kit new-domain <name>` · `python -m kit init` |
| add data (file / URL / Toronto Open Data) | `python -m kit add-data <path\|url\|ckan:name>` → loads, snake-cases, **AI-documents every column** |
| build an agent-friendly view | `python -m kit sql --view v_x --query "SELECT …${PROJECT_ID}.${DATASET}.t…"` |
| add an ML model | `python -m kit model NAME --type logistic\|linear\|boosted_class\|boosted_reg\|kmeans\|arima --source v_x --label y --features auto --train-filter … --predict-filter … --id-cols …` → trains, evaluates on hold-out, tests the predict query, registers it for the agent |
| semantic search (experimental) | `python -m kit embed --table t --id-col id --text-col txt` |
| add/modify agents | edit `domains/<x>/team.yaml` (14 roles, 14 tools, sequential/parallel/loop, structured output, human approval); `python -m kit roles` · `team-check` |
| add a live API | copy `get_forecast` in `kit_agent/tools/live_api.py`, register in `registry.py` (or use `fetch_live_json` + `live_api.allowed_hosts`) |
| preflight (8 AM!) | `python -m kit doctor --llm` |
| run | `python -m kit web` (ADK trace/graph) · `python -m kit ui` (demo UI) · `python -m kit cli` |
| rehearse | `python -m kit rehearse` (runs `demo_questions`, checks expected tools, saves transcript) |
| deploy | `python -m kit deploy runtime` / `a2a` |
| undo | `bash scripts/rollback_all.sh` |

Every command appends to `logs/operations.log` and writes an undo script to `rollback/`. Nothing is auto-deleted.

## Built-in agent roles
scout · analyst · investigator · skeptic · planner · triage · translator · designer · writer · critic (exits loops) · verifier · approver (human approval) · formatter (Pydantic `ActionPlan`) · custom.

## Rehearsal (≈30 min, any project incl. lab projects)
```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt   # Windows: .venv\Scripts\activate
python -m kit init && python -m kit doctor --llm
python domains/food_equity/gen_data.py domains/food_equity/data
bash scripts/load_data.sh domains/food_equity/data --views --model      # or: kit add-data each CSV, kit sql --view, kit model
python -m kit rehearse && python -m kit web
python -m kit new-domain scratch && python -m kit add-data <any csv> && python -m kit use food_equity   # test plug-in flow
```

## Honest status
- **Not run against live Google Cloud from here** (no network in my sandbox). Syntax-checked; SQL generators, domain merge, team validation and CLI loading were unit-tested offline. First real run = your rehearsal.
- Most likely breakages: ADK import paths/signatures (labs used 1.30–1.33; event says ADK v2), `FunctionTool(require_confirmation=…)`, BigQuery remote-model/embedding SQL (`kit embed` is experimental), Maps MCP header function. Fix in one place: `registry.py` / `agent.py`.
- Corporate laptops may block tools: use a personal laptop.

## First 15 minutes
1. `python -m venv .venv`, activate, `pip install -r requirements.txt`
2. `gcloud auth application-default login`, `cp .env.example .env`, fill in project
3. `python -m kit doctor`, then read `docs/IDEAS.md`

**Check once ADK is installed:** your v1 scaffold (in `.archive`) was verified on google-adk 2.12 (BigQuery imports under `google.adk.integrations.bigquery`). This kit has not been run against ADK yet: run `python scripts/smoke_test.py` and fix imports in `kit_agent/agent.py` and `registry.py` if needed.
