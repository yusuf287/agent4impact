# Challenge 1 — Urban Heat: what we must deliver

Source: team repo template `haggman/A4I2026-challenge-1-walkability` (README + notebook) and the event one-pager.

## The objective (plain words)
Some streets run much hotter than others. A US city has a small budget and must decide **where to put heat help**.
We build an **agent a planner can talk to** that: predicts how much hotter a spot runs than the city average (even
where nobody measured), explains **why**, says **who lives there**, recommends places, drafts the council proposal,
and **audits** whether the picks reached the people who need it most.

## Tracks (pick one)
| Track | Decision | User |
|---|---|---|
| Today | where hydration trucks / wellness checks go tomorrow | emergency management |
| This budget cycle | where 3 permanent cooling centres go | city planning (council) |
| This decade | where tree planting / cool pavement helps most per dollar | urban forestry |

**Our recommendation:** budget cycle, equity audit as the centrepiece. City: Dallas (safest) or Brooklyn (tree census in BigQuery: check license).

## Must-haves checklist
- [ ] ADK agent + Gemini + BigQuery
- [ ] **BigQuery ML** model on the **offset** (`LINEAR_REG` suggested), called via **`ML.EXPLAIN_PREDICT`**
- [ ] **≥1 tool we built** (Python): location → nearest tract features → explained prediction
- [ ] **≥1 managed MCP server consumed** (BigQuery MCP or MCP Toolbox for Databases; Toolbox on Cloud Run with min-instances 1)
- [ ] **Deployed** (Agent Runtime or Cloud Run)
- [ ] Output artifact: **Placement Recommendation** (ranked sites, coordinates, offset, why, who lives there, draft proposal)
- [ ] **Equity audit** with numbers (recommended tracts vs city averages)
- [ ] Submit at https://portal.angelhack.com/a4i-console: repo link, Skills project link, deck, **pitch video**

## Data (dataset `a4i_climate`)
`heat_observations` (one campaign day, street level, °F) · `station_daily_temps` (2019–2025 daily max, °F) ·
`tract_demographics` (ACS by tract; join by nearest tract point). Load: Colab notebook, or `bash scripts/load.sh dallas`.

## Judging (scored after the event from repo + deck + video; no Q&A)
Impact 30 · Technical 30 · Rigor 25 · Craft 15 · Bonus range +10.

## Traps to avoid
1. Say "**+X° above the city average**", never "it will be X°". One unit everywhere (data is °F; ×5/9 for °C offsets).
2. The agent must **call the model**, not describe historical rows.
3. One day of street data: "how often" comes from station history.
4. No race as an input; audit outcomes instead.
5. No OpenStreetMap-derived data (ODbL), no NC/ND/share-alike, no unstated license.
6. ~98% accuracy = leakage. Split train/test by area, not randomly (neighbouring readings are near-identical).
7. Name the limits: single day, volunteer routes, sparse stations, can't simulate the effect of planting.

## Lanes
Data (2–3) · Agent (2–3) · Front end (2) · Story (1–2). One branch per lane; merge early.
