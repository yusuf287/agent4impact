---
name: challenge-to-domain
description: Turn the hackathon challenge statement and dataset notes into a filled domains/<name>/ folder (persona, mission, routing, demo questions, team). Use first, right after the challenge is revealed.
---

# Challenge → domain

Input: the challenge text, dataset description, and (if known) the team's chosen user/persona. If the user/decision is not stated, ask at most 3 questions: who is the user, what decision do they make, what data is the hero.

Steps:
1. Run `python -m kit new-domain <short_snake_name>`.
2. Edit `domains/<name>/domain.yaml`:
   - `agent_name`, `description` (when should a router call this agent?), `persona`, `mission` (the decision supported),
     `audience`, `brand.palette`.
   - `routing_rules`: 4–6 lines "question type -> tool/table". Mention which table/view answers what.
   - `demo_questions`: 1 simple, 1 prediction, 1 chart, 1 compound that triggers the team. Add `expect_tools`.
   - `live_api.enabled` / `open_data.enabled` / `vision.enabled` only if they will really be used.
3. Edit `team.yaml`: choose roles that each have a clear reason (`python -m kit roles`). 3–5 agents max. Keep an `approver` step if actions affect people.
4. Run `python -m kit team-check`.
5. Write `docs/DEMO_SCRIPT.md`: the person, the "before", the trigger, the aha moment, why it scales (5 short lines).
6. Print a checklist of data still needed and the exact `kit add-data` commands to get it.

Do not invent data. Do not load data in this skill (use `add-data`).
