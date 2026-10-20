# Ideas, decision rule and fact-check list

## 1. Decision rule at 9:25 AM
1. Read the statement + dataset. Underline: **user, decision, hero data**.
2. Is the challenge about emergencies, resilience, vulnerable people or infrastructure? → **Lights Out** (thin slice).
   Heat / building conditions / tenants? → **26°C**. Food access/supply? → **Pantry Forecast** or **Dignity Pantry**-style (use the event data). Anything else / unclear → **SurgeDesk**.
3. If the event dataset is rich, make **it** the hero and use our open data as the second layer — do not force the building registry.
4. Agree with the team on **one** idea by 9:55. Don't merge ideas.
5. Write the demo script first (person, before, trigger, aha, scale).

## My overall ranking (opinion, not fact)
1. Lights Out — best story, medium risk; scope hard.
2. 26°C — most real data, simplest, narrower.
3. SurgeDesk — safest fallback.
Everything else = modules or parked.

## 2. All ideas

Legend — Status: ⭐ lead · 🔁 fallback · 🧩 module (add-on) · ❌ drop · 💤 parked. Scores are my judgement (1–5): Fit-with-themes / Real-data / Feasible-in-6h / Stage-wow / Originality.

## Lead and fallbacks
| Idea | Theme | One line | F | R | B | W | O | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| **Lights Out** | all 3 | One clock for food spoilage, medical power and stuck elevators in an outage | 5 | 3 | 3 | 5 | 4 | ⭐ if challenge is emergency/resilience | see `lights_out.md` |
| **26°C** (tenant heat-law enforcement) | health | Finds buildings where the new cooling-room rule is invisible; evidence from tenants | 3 | 5 | 4 | 4 | 4 | 🔁 if health/heat | real data, narrow; synthetic tenant reports |
| **SurgeDesk** | any | Triage copilot for a surge of requests; human approves | 4 | 2 | 5 | 3 | 2 | 🔁 generic fallback | safest, least original |
| **Heat & Smoke Guardian / TowerWatch** | health | Building-level heat outreach list from registry data | 3 | 5 | 4 | 3 | 3 | 🔁/🧩 | merge with 26°C data |
| **EvacPilot** | evacuation | Hazard zone → vulnerable residents → routes → approve | 3 | 3 | 3 | 4 | 3 | 🔁 if evacuation | needs Maps MCP |
| **Pantry Forecast + Rescue Match** | food | Forecast pantry shortfalls; match surplus donors | 3 | 3 | 4 | 3 | 3 | 🔁 if food | |
| **Next Meal Navigator** | food | Resident-facing multilingual meal/benefit planner | 3 | 3 | 4 | 3 | 2 | 💤 | many similar bots |

## Modules (add one only if the core works)
| Module | One line | Status | Notes |
|---|---|---|---|
| **Hot Pills** | Photo of pill bottles + forecast → personal heat plan | 🧩 | feasible; medical guardrails: no dose advice |
| **Pill Bottle Passport** | Photo → medication card + nearest open pharmacy | 🧩 | multimodal wow |
| **Voice front door** | Gemini Live voice agent in front of any tools | 🧩 | browser demo only; recorded fallback |
| **Rumor Control Room** | Cluster questions, detect rumours, verify against official sources | 🧩 | |
| **One Message, Every Language** | One alert → spoken messages in 20+ languages | 🧩 | |
| **Silent Neighbours** | Escalating check-in loop (LoopAgent) with human approvals | 🧩 | pairs with Lights Out medical agent |

## Other concepts (parked or prior art found)
| Idea | Why parked |
|---|---|
| Heat Shield (AI check-in calls) | Naver CareCall exists; only the *targeting* is new → folded into Lights Out / 26°C |
| Ground Truth | Ushahidi / ReliefQueue exist |
| Break the Plan / Dress Rehearsal | WhatIf research exists; heavy to build; audience-shout moment is fun |
| The Unseen (hours × transit access) | exists as analysis; maybe a live tool angle |
| Lifeline Interpreter | translation apps common; good as a module |
| Ripple (service-cut consequences) | interesting, hard to prove with data in a day |
| Guardian Voice / Quiet Map / T-Minus 72 / Nobody Left Behind / Agent War Room | stage ideas; fold pieces into the lead if needed (T-Minus 72 countdown ≈ Lights Out clock; Nobody Left Behind ≈ stair-assist) |
| Unclaimed Dollars / Dignity Pantry / Evacuee Medicine & Meal Match / Host-City Surge | niche or mostly simulated data |

## Patterns that keep winning (from your research)
Triage during a surge · early warning from real data · accessible multilingual navigator · matching supply to need.
Winning shape: **coordinator tool for responders + resident-facing outputs**, a visible agent loop, a human approval step, honest limits.

## 3. Lights Out (lead candidate)

Status: **STRONG CANDIDATE (needs scoping + data verification)** · Themes: all three · Source: brainstorm of Oct 19 · Evaluated: Oct 19–20

### One line
When the power fails, food spoils, medical devices run down and elevators trap people upstairs. Lights Out runs those three clocks as one plan for responders; a human approves every dispatch.

### My evaluation (honest)

**What is genuinely strong**
- It is the only idea so far that covers food equity, public health and evacuation *without forcing it* — one event, three failures.
- The **"clock"** is a built-in demo structure and a built-in story (hour 0 → hour 6).
- **Proactive, not reactive**: it finds people who would never call. "Air-traffic controller for a crisis" is a good pitch line.
- Level 0 needs **no personal data** (open building registry only) — a strong answer to the privacy question.
- It reuses what you already have: kit, building data, Environment Canada alerts, approval step, skeptic role.

**What worries me**
1. **Most of the demo is simulated** (the outage zone, the residents, the calls, the oxygen battery). The only real thing is the building registry. If the hero moment is the fake 22nd-floor call, judges see a mock. **Make the real-data ranking the hero**: "these towers, in this order, because X" — and keep the call as a garnish.
2. **Too many parts for strangers in ~6 hours**: 6–7 agents + voice + map + phone + clock. Build the thin vertical slice (below), not the whole story.
3. **Two numbers in the pitch are unverified by me**: 905 buildings / ~84,000 homes without emergency power, and 240 buildings of 10–36 storeys. Also **what `IS_THERE_EMERGENCY_POWER` actually covers** — emergency power for lighting only is not the same as powering elevators. If the field means lights/fire systems, "no emergency power = elevators stop" is an inference; say so.
4. **Medical safety.** The agent must never give medical advice or triage a life-threatening call. Rule: life-threatening or "battery < X" → "call 911" + escalate to a human immediately. Put this in the instructions and the demo.
5. **Food timing claim** ("about 4 hours") needs a Health Canada / CFIA source. Cite it or soften it.
6. **Fit depends on the challenge.** If the revealed statement is narrowly about food access or about public-health surveillance, Lights Out is a stretch. It fits best if the challenge is about emergencies/resilience/vulnerable people. Don't pre-commit.
7. **The event dataset may not include buildings.** Judges favour the provided dataset. Be ready to make the provided data the hero and use the registry as the extra layer.
8. **Privacy law** (PIPEDA / Ontario PHIPA): health info about residents needs explicit opt-in consent. Your four-level plan handles this well — keep it as a slide ("Path to real").

### Verdict
Best *story* of everything so far. Medium *feasibility* unless scoped. Pursue it **if** the challenge is about emergency resilience or vulnerable people. Otherwise fall back (see `README.md`). Do not mix it with 26°C, Hot Pills or voice-calling tomorrow; mention heat as "another trigger" only.

### The thin vertical slice (what to actually build)
1. **Real data, Level 0:** load the building registry (+ evaluation file for lat/lon). View `v_tower_risk`: storeys, units, elevators, `emergency_power` flag, barrier-free units, ward, owner type (TCHC/private/social), year built → a **risk score** (BigQuery ML or simple weighted SQL; explain it).
2. **Simulated outage:** one clearly labelled SYNTHETIC outage polygon/ward list (Environment Canada alert text can set the "trigger" for real).
3. **Clock:** hour-offsets table (`hour, what_breaks, who_is_affected`) — e.g. elevators at h0, fridge food ~h4 (verify), device batteries h2–h8 — turns the ranking into "who first, by when".
4. **Team (3 specialists + coordinator + skeptic + approver):** `scout` (towers in zone), `medical_agent` (power-dependent devices, opt-in registry only), `food_agent` (who loses food, nearest open food bank), `coordinator`, `skeptic`, `approver`. Drafted in `domains/lights_out/team.yaml`.
5. **Demo UI:** `python -m kit ui` (trace visible) + a map if time allows. Voice call = browser demo only; phone integration is "next step".
6. **Honesty slide:** what is real (registry, alerts, clock rules), what is simulated (outage, residents, calls), and "Path to real" (partners: Toronto Hydro, Paramedics, food banks; opt-in via lobby QR; consent).

### Resident contact — four levels (keep this; it is your best answer)
L0 no personal data (open data → towers/floors to check) · L1 hotline, residents call in · L2 opt-in sign-up by QR before the storm · L3 partner lists with agreements. Agent always announces it is automated; humans approve dispatch.

### Build plan with the kit (≈ 90 min to a working slice)
```
python -m kit new-domain lights_out        # already drafted: domains/lights_out (copy over / `kit use lights_out`)
python -m kit add-data ckan:apartment-building-registration --table buildings
python -m kit add-data ckan:apartment-building-evaluation   --table building_eval
python -m kit sql --view v_tower_risk --query "SELECT ... FROM buildings JOIN building_eval USING (rsn) ..."
python -m kit add-data samples/outage_zone.csv        # SYNTHETIC (you create: ward list or building ids)
python -m kit add-data samples/opt_in_residents.csv   # SYNTHETIC, labelled
python -m kit model tower_risk --type boosted_reg --source v_tower_risk --label risk_score ...   # optional; weighted SQL is fine
python -m kit team-check ; python -m kit rehearse ; python -m kit ui
```
(CKAN package names above are guesses — use `search_open_data` / the portal to find the exact names.)

### Pitch skeleton
Opener (their draft, after verification) → the clock → live: storm alert → outage zone → ranked towers (real) → plan → skeptic changes one decision → human approves → "Path to real" → scale ("any city with a building registry and weather alerts").

### Open questions for tomorrow
- Exactly what does `IS_THERE_EMERGENCY_POWER` mean in the data dictionary? Does any field say elevators are covered?
- Which food-safety source gives the fridge/freezer hours?
- Can we get power-outage data (Toronto Hydro) — or is simulation the only option? (Say so either way.)
- Which data does the event provide? Can it replace the registry as the hero?
- Who on the team owns the map/UI?

## 4. Verify before pitching

Mark each: ✅ verified (source + date) · ⚠️ soften · ❌ remove.

| # | Claim in the brainstorm | How to verify | Status |
|---|---|---|---|
| 1 | 905 apartment buildings with elevators have no emergency power (~84,000 homes) | Load the registry with `kit add-data`; SQL: count where elevators > 0 and emergency power = no; sum units | |
| 2 | 240 of them are 10–36 storeys | same query, filter storeys ≥ 10 | |
| 3 | What does `IS_THERE_EMERGENCY_POWER` cover (lights only vs elevators)? | Toronto Open Data data dictionary / resource description for the registry | |
| 4 | 2,962 buildings no AC; 2,770 no AC and no cooling room (~218,327 units); only 18 heat-related 311 requests; law effective June 1 2026 (26°C) | same registry + 311 file; city bylaw page | |
| 5 | Fridge food unsafe after ~4 h without power | Health Canada / CFIA "power outage food safety" guidance | |
| 6 | emPOWER (US) is health-only, ZIP-level counts | HHS emPOWER documentation | |
| 7 | Toronto Hydro outage map is not open data | Toronto Hydro / Toronto Open Data search | |
| 8 | Toronto food-bank stats (4.1M visits; +340% since 2019; 1 in 4 children) | Daily Bread "Who's Hungry" report | |
| 9 | 85,000+ Canadians evacuated in 2025; Toronto among most polluted cities (smoke) | Natural Resources Canada / Canadian Interagency Forest Fire Centre; IQAir | |
| 10 | CareCall used in 70+ Korean local governments (~15,000 households) | Naver announcements | |
| 11 | Heat Seek / JustFix capabilities as described | their websites | |
| 12 | Medication–heat guidance (CDC table), DIN / RxNav lookups | CDC page; Health Canada DPD; RxNav | |

Rules: only state a number in the pitch if its row is ✅. Keep sources in `docs/PITCH.md`. Label simulated data on every slide that uses it.

## 5. New idea template
Copy the fields: name, status, themes · one line · the person and painful moment · decision and approver · hero/extra/simulated data · agents · demo (trigger→aha→scale) · prior art · risks · score (fit, real data, feasibility, wow, originality) · kit commands · open questions.
