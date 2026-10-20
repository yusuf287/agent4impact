# Demo Script — Challenge 1: Community Climate Resilience (Urban Heat, City of Dallas)

## 5-Line Story Arc (`challenge-to-domain`)
1. **The Person**: Dana in the **City of Dallas City Manager's Office** (City Planning) coordinating with Emergency Management at 3:40 PM on a Tuesday in July—after 11 days over 100 F, with a 102 F forecast for Thursday and a City Council capital budget meeting at 9:00 AM tomorrow.
2. **The "Before"**: Airport weather stations report one uniform temperature for all of Dallas, leaving planners guessing where to site **3 permanent cooling centers** (🏛️ *This Budget Cycle*) and **1 mobile hydration unit** (⚡ *Today*) while street blocks two intersections apart actually differ by 10–15 F.
3. **The Trigger**: Dana asks `dallas_heat_planner`: *"We have funding for 3 permanent cooling centers this budget cycle and 1 mobile hydration unit for Thursday's 102 F heat wave. Where should they go, why are those blocks so much hotter, how often does Dallas hit this threshold, and did our picks reach the neighborhoods that need help most?"*
4. **The Aha Moment**: Instead of querying raw temperatures or giving a black-box score, the agent runs **`ML.EXPLAIN_PREDICT`** on `heat_offset_model` to predict the **temperature offset (`+X.X F` above the Dallas average)** even for unmeasured census tracts, breaks down the exact per-feature attributions (e.g., building age, housing density, vehicle access), pairs it with **7 years of GHCN station history** (`v_station_heat_frequency`), grounds street intersections via **Google Maps MCP**, and runs a **post-hoc Equity Audit** comparing the recommended tracts' poverty and no-vehicle rates against the Dallas citywide baseline before pausing for **human approval** (`request_approval`).
5. **Why It Scales**: Because the model predicts the spatial **offset** (`degrees_above_city_average`) rather than absolute temperature and audits outcomes rather than baking race into model inputs, any of the 68 NOAA Heat Watch cities can swap `CITY` in one command (`bash scripts/load.sh <city>`) and generate council-defensible Placement Recommendations.

---

## The 7 Planner Questions (Live Demo / Rehearsal Sequence)

| # | Question to Ask | Tool(s) Triggered | What Judges See |
|---|---|---|---|
| **1. Baseline & Spread** | *"How many street-level heat observations and census tracts are loaded for Dallas, what is the intra-city temperature spread within the same hour, and how many days per year has Dallas crossed 100 F since 2019?"* | `BigQueryToolset` (`heat_observations`, `v_station_heat_frequency`) | Contrasts intra-city microclimate spread (Heat Watch = *where*) with 7-year GHCN station frequency (GHCN = *when*). |
| **2. Siting & Prediction** | *"We can fund three permanent cooling centers this summer and one mobile hydration unit for Thursday's 102 F forecast. Where should they go?"* | `run_model_predictions` (`ML.EXPLAIN_PREDICT` on `heat_offset_model`), `get_forecast` | Ranks Dallas tracts (including unmeasured tracts) by predicted **heat offset (`+F` above city mean)** + `no_vehicle_pct` + `poverty_pct`. |
| **3. Attribution ("Why?")** | *"Why is our top candidate tract so much hotter than surrounding blocks?"* | `run_model_predictions` (`top_drivers` from `ML.EXPLAIN_PREDICT`) | Reads per-feature attributions in degrees F (`building_age_years`, `housing_density_proxy`, `no_vehicle_rate`, etc.). |
| **4. Demographics & Access** | *"Who lives around those top candidate sites—how many residents, how old, what is the poverty rate, and how many households lack a car? What streets or public facilities are nearby?"* | `BigQueryToolset` (`v_tract_heat_features`), `maps` (Google Maps MCP) | Grounds tract centroids to real Dallas intersections/facilities and distinguishes `no_vehicle_rate` from walk-time isochrones. |
| **5. Visual Comparison** | *"Chart the top 8 Dallas candidate tracts by predicted heat offset (F above city average) alongside their no-vehicle household percentage."* | `visualization_agent` (`BuiltInCodeExecutor`) | Generates a clean horizontal bar chart comparing heat offset and mobility vulnerability. |
| **6. Trade-off & Council Brief** | *"Draft the full Placement Recommendation and City Council Proposal for the 3 permanent cooling centers and 1 mobile hydration unit, including the site-by-site trade-off and the post-hoc Equity Audit."* | `response_team` (`scout` -> `investigator` \|\| `skeptic` -> `planner` -> `writer` <-> `critic` -> `approver` -> `formatter`) + `request_approval` | Runs the multi-agent team, executes the mandatory **Equity Audit** (recommended tracts vs. Dallas citywide average), outputs the structured `ActionPlan`, and pauses for human approval. |
| **7. Guardrail / Refusal Test** | *"What is the street-level heat offset in Phoenix, and how many degrees cooler will Dallas Tract 4811300... get if we plant 200 trees?"* | Agent guardrails (no hallucination) | Refuses cleanly: explains Phoenix is not a NOAA Heat Watch campaign city, and states that while `ML.EXPLAIN_PREDICT` diagnoses drivers, observational data cannot simulate post-planting temperature drops. |

---

## Mandatory Talking Points for the Pitch Video & Deck

- **Offset, Not Temperature**: Our `LINEAR_REG` model predicts `heat_offset_f` (`temp_f - city_avg_temp_f`), holding weather constant so the model learns the spatial microclimate rather than the calendar.
- **`ML.EXPLAIN_PREDICT` as the Argument**: Every siting recommendation carries per-feature attributions in degrees F so Dana can defend *why* a corner was chosen in front of City Council.
- **Strip the Variable, Audit the Outcome**: Race/ethnicity columns were deliberately excluded from `tract_demographics` and model inputs because physical built environment causes heat islands. Instead, our `skeptic` agent runs a mandatory **post-hoc Equity Audit** comparing recommended tracts' poverty rate, no-vehicle rate, median income, and median age against the Dallas citywide baseline.
- **Honest Limitations**:
  1. NOAA Heat Watch is a single-day afternoon campaign snapshot (spatial pattern only, paired with 7-year GHCN station data for frequency).
  2. `no_vehicle_rate` measures household car access at the census tract level, while Google Maps MCP provides street/facility context.
  3. The model diagnoses heat drivers (`ML.EXPLAIN_PREDICT`) and predicts unmeasured locations, but cannot causally simulate the exact temperature drop after an intervention.
