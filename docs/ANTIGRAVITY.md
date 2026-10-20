# Using this kit with Antigravity (personal laptop)

Antigravity = the agent-first IDE/command centre from the labs. Use it to do the *wiring*; you make the *decisions*.
(Details below follow the intro lab: projects, Local boot mode, slash commands, workspace skills in `.agents/skills`.)

## 0. Tonight (15 min) — laptop setup
1. Install Python 3.11+, Git, and the Google Cloud SDK. `gcloud auth login` then `gcloud auth application-default login`
   (ADC is what BigQuery/ADK use on a laptop — Cloud Shell had it for free, a laptop does not).
2. `git clone` (or copy) this folder to e.g. `Documents\a4i-agent-kit` (OneDrive-synced = backed up).
3. `python -m venv .venv` → activate → `pip install -r requirements.txt`.
4. `python -m kit init` (creates `.env`, enables APIs, creates the dataset) — needs a project you may use tonight; on the day, run it on the event project.
5. `python -m kit doctor --llm` → everything OK. Run `python -m kit web` once to prove the agent starts (food-equity example needs its data: see README rehearsal).
6. Open Antigravity → **Create Project** → Add Folder = this folder → Security preset **Default** → name it `a4i-agent-kit`.
   Boot mode: **Local**. Then start a **new conversation** (skills are indexed per new thread).
7. Check skills registered: type `/` and confirm `challenge-to-domain`, `add-data`, `add-model`, `add-agent-team`, `rehearse-demo`, `deploy-and-backup`, `pitch-builder` appear.

> Security: keep **Default** (review before it runs terminal commands). "Always proceed" is convenient but lets the agent run
> deploy/IAM commands unreviewed. If you switch it on for speed, tell the agent "never deploy, delete, or change IAM without asking".

## 1. Event-day flow (which skill when)

| Moment | Do in Antigravity |
|---|---|
| 9:25 challenge revealed | New thread → `/grill-me` + paste challenge + dataset notes + your idea shortlist. Answer its questions (≤5 min) — it sharpens user/decision/data. |
| ~9:45 decided | `/challenge-to-domain <paste final one-liner>` → fills `domains/<name>/` |
| ~10:00 data | `/add-data` with each source (file, URL, `ckan:<name>`); one thread per source if teammates parallelise |
| ~10:30 first answer | `python -m kit web` (you run it) → ask one question end to end. Ugly is fine |
| ~11:00 prediction | `/add-model` |
| ~11:30–2:00 depth | `/add-agent-team`; optionally Maps MCP (`ENABLE_MAPS_MCP=1`), vision, live alerts |
| 2:00 | `/rehearse-demo` |
| 3:30 | **Freeze.** Bug fixes only |
| 3:30–4:30 | `/pitch-builder`, rehearse out loud ×3 |
| 4:30 | `/deploy-and-backup` (and record backup video) |

Parallel work: each teammate opens their own conversation under the same project (Data lead: `/add-data`, `/add-model`;
Agent lead: `/add-agent-team`). Merge through git; avoid two people editing the same YAML file at once —
data work writes `generated.yaml`, agent work edits `team.yaml`, strategy edits `domain.yaml`.

## 2. Paste-ready prompts

**Kickoff (use with /grill-me):**
> We are in a one-day Google "Agents for Impact" hackathon. Challenge statement: <PASTE>. Dataset notes: <PASTE>.
> Candidate ideas: <PASTE 1–3>. Repo conventions are in AGENTS.md. Interview me to pin down: the single user, the decision they make,
> the hero dataset, what must be live vs historical, the one aha moment, and what we will explicitly NOT build.

**Goal mode for a long build (/goal):**
> /goal Using the kit CLI only, load <sources>, create views v_<a> and v_<b> with documented columns, train a <type> model for <label>
> with held-out <period>, update domain.yaml routing_rules, and make `python -m kit rehearse` pass for my demo_questions. Ask before deploying.

**Debug a bad answer:**
> The agent answered "<question>" wrongly. Open the trace logic (kit_agent/prompts.py output and domain YAML), find whether the failure is
> wrong tool routing, wrong SQL due to unclear column descriptions, or a missing tool. Fix at the YAML layer first, show the diff, re-run `python -m kit rehearse`.

**Add a live API as a tool:**
> Add a function tool `get_<thing>` in kit_agent/tools/live_api.py modelled on `get_forecast`: first docstring sentence says exactly when to use it,
> returns {"status","data"}; register it in kit_agent/registry.py; add it to the right agent's `tools:` in team.yaml; add a routing rule.
> Include a graceful error path and a cached fallback file for the demo.

**Voice/multimodal (stretch):**
> Add a `vision` tool use: set `vision.enabled: true` in domain.yaml, then test `analyze_image` with a sample photo in `samples/`.
> For live voice, check what `adk web` supports for the MODEL we use and propose the smallest change; keep a pre-recorded fallback.

## 3. If Antigravity misbehaves
The CLI works without it: every skill is just `python -m kit …` + editing YAML. Open the repo in any editor and follow AGENTS.md's command table.
