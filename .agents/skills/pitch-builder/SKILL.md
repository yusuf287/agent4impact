---
name: pitch-builder
description: Draft the 3-minute pitch, demo script and one-page README from the working project. Use after features are frozen.
---

# Pitch builder

Read `domains/<x>/domain.yaml`, `team.yaml`, `logs/rehearsal_*.md` and the real model metrics. Only use numbers that appear there.

Produce `docs/PITCH.md`:
1. **The person (30 s):** one named, realistic (synthetic) person, one painful moment, one local statistic that is verified (list the source URL; mark anything unverified `VERIFY`).
2. **Before vs after (15 s).**
3. **Live demo (90 s):** exact click/typing script from `demo_questions`, with where to point at the trace/graph. Include the pre-computed fallback.
4. **How it works (30 s):** sources → agents → surfaces; one sentence per agent saying why it exists; where the human approves.
5. **Impact & honesty (30 s):** who benefits, scale story ("works in any city"), model metrics and one honest miss, data limits, privacy.
6. **Q&A cheat sheet:** 8 likely judge questions with answers (data provenance, accuracy, failure handling, bias, cost, deployability, what's mocked, what's next).

Also write a `README.md` section "What is real vs mocked" and a 6-line "How to run".
