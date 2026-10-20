# Agents for Impact — Day-of Playbook

Core thesis from every lab: **agent capability = the data it can reach, not the model.**
Every time an agent "hits a wall" it is a data-architecture gap. Your job on the day is to
(1) identify what data answers the challenge, (2) wire the agent to it, (3) show it working.

## 1. Decision tree (2 minutes)

| Challenge needs… | Use | Kit piece |
|---|---|---|
| Answers from documents/policies/PDFs | Gemini Enterprise data store + Agent Designer | (no code) |
| Counts, trends, rankings over tables | ADK + BigQueryToolset | `kit_agent/agent.py` |
| Predictions / risk scores | BQML model + `ML.PREDICT` tool | `domains/*/model.sql`, `run_model_predictions` |
| "Right now" state (weather, status, routes) | Live-API FunctionTool or Maps MCP | `tools/live_api.py`, `ENABLE_MAPS_MCP=1` |
| Search by meaning over text/images | BigQuery vector search (embeddings) or AlloyDB ScaNN | lab 1046 SQL pattern |
| Charts | Isolated visualization agent (BuiltInCodeExecutor) | `visualization_agent` |
| Several specialists collaborating | Sequential / Parallel / Loop agents | `kit_agent/workflow.py` |
| Agent calling another team's agent | A2A | `scripts/deploy.sh a2a`, `RemoteA2aAgent` |
| Shared with non-developers | Deploy to Agent Runtime, register in Gemini Enterprise | `scripts/deploy.sh runtime` |

## 2. Timeline for a one-day sprint

| Time | Do | Done when |
|---|---|---|
| 0:00–0:30 | Read challenge. Write the **one-sentence decision** your agent supports ("Help X decide Y"). Pick data. Start any slow ingestion NOW (document data stores take 15–20 min). | Sentence + data list |
| 0:30–1:00 | `bash scripts/bootstrap.sh`; copy `domains/_template.yaml`; fill `tables:` descriptions | `adk --version` works, dataset exists |
| 1:00–2:00 | Load data (`scripts/load_data.sh <dir> --views`), sanity-query in BigQuery Studio | Row counts verified |
| 2:00–3:00 | Model (`--model`) if prediction fits; write `predict_sql`; run `python scripts/smoke_test.py` | Agent answers 3 real questions |
| 3:00–4:30 | Add the one differentiator: live API / Maps MCP / A2A / pipeline report | Trace shows multi-source answer |
| 4:30–5:30 | Deploy (`deploy.sh runtime`), test in Playground; fallback = `adk web` | Endpoint works |
| 5:30–6:30 | Rehearse demo; screenshot everything; write the 3-slide pitch | 2 clean run-throughs |
| Last 30 | Freeze. No new features. | |

## 3. Replication recipe (new challenge in ~20 min) — see README for the full command table

1. `python -m kit new-domain <name>` then `python -m kit init`.
2. `python -m kit add-data <file|url|ckan:name>` per source (columns are AI-documented; fix wrong ones in `domain.yaml`).
3. `python -m kit sql --view v_<topic> --query "…"`: one pre-joined view with boolean flags (`is_…`).
4. `python -m kit model <name> --type … --source v_<topic> --label … --features auto --train-filter … --predict-filter …` (hold out the latest period).
5. Fill `domain.yaml` (persona, mission, audience, 4–6 `routing_rules`, `demo_questions`) and tune `team.yaml`.
6. `python -m kit doctor`, `team-check`, `rehearse`, then `python -m kit web` / `ui`.
In Antigravity each step is a skill (`/add-data`, `/add-model`, `/add-agent-team`, …) — see `docs/ANTIGRAVITY.md`.

## 4. Demo & pitch (judges love a visible "wall coming down")

1. **Problem** (20s): whose decision, what's at stake, who is underserved.
2. **Wall** (30s): show a plain chatbot failing on a live/computational question.
3. **Your agent** (2 min): one compound question that triggers SQL + ML + live/Maps + chart. Open the **trace** so judges see the tool chain.
4. **Architecture** (30s): one slide — sources → agent → surfaces.
5. **Impact & honesty** (30s): who benefits, numbers, model caveats (name the model's misses, like the Tigers/Reds lesson), data limits, human-in-the-loop.

Compound question template: *"Which [areas] are highest risk next [period], why, what's [live condition] there now, and show me a chart of the top 5?"*

## 5. Gotchas collected from the labs

- `adk web` in Cloud Shell needs `--allow_origins "*"` (blank chat otherwise). Port busy → `--port 8001`.
- New terminal ≠ venv: `source .venv/bin/activate` and `set -a; source .env; set +a` again.
- Agent directory needs `__init__.py` with `from . import agent`, and a variable named `root_agent`.
- Instructions must only mention tools that are actually registered (lab 4.3 error).
- Tool docstring **first sentence** drives routing. Router descriptions (A2A card, Gemini Enterprise) should say when NOT to use the agent.
- `BuiltInCodeExecutor` cannot share an agent with other tools → separate agent wrapped in `AgentTool`.
- Deploy: always pass `--requirements_file`, include `google-cloud-aiplatform[agent_engines,adk]`. Service account needs BigQuery + Vertex roles.
- IAM changes take minutes; "permission denied" right after granting → wait and retry.
- 429 RESOURCE_EXHAUSTED = quota, not your bug. Retry or switch model.
- Gemini Enterprise: disable Google Search on the app when you need grounded-only answers; keep separate data stores per document family.
- BigQuery connection location must match dataset/bucket location.
- Two data sources can disagree (historical vs live). State the data window in every answer.
- Lab temp projects expire — **push code to your own repo/OneDrive folder before the time limit**; screenshots of working traces are your backup.
- Data Engineering Agent output is a draft: check deduplication, casts, all columns.
- Agent-written SQL is read-only by default here (`WriteMode.BLOCKED`). Keep it that way.

## 6. Responsible-AI checklist (cheap points)

Synthetic or public data only; no personal data in prompts; show data window + model caveats; Model Armor callbacks if time (lab Team USA 6.8); audit logs on (`logs/operations.log`, Cloud Logging); human decides, agent recommends.

## 7. If things break

| Symptom | Fix |
|---|---|
| Agent invents numbers | Tighten "every number must come from a tool"; check tool actually registered; look at trace |
| Wrong columns in SQL | Improve `tables:` descriptions, re-run `apply_descriptions.py` |
| Deploy fails | Demo from `adk web`; screenshots of Playground attempt |
| Maps MCP 403 | Check API enabled + header provider; fall back to `fetch_live_json` |
| Out of time | Ship BigQuery + model + chart. That already beats a retrieval-only bot |
