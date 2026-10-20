---
name: rehearse-demo
description: Run and harden the demo path - preflight, scripted questions, trace check, failure cases, cached fallbacks. Use from midday onward and before every freeze.
---

# Rehearse and harden

1. `python -m kit doctor --llm` → fix every FAIL.
2. Ensure `domain.yaml` → `demo_questions` has: simple, prediction, chart, compound (with `expect_tools`), and one **out-of-scope** question the agent must decline honestly.
3. `python -m kit rehearse` → read `logs/rehearsal_*.md`. For each FAIL: open the trace in `python -m kit web`, find the wrong tool/SQL, fix the YAML description or routing rule first.
4. Time each question. Over ~25 s on stage = cache/pre-run: save its output and keep a screenshot; say so honestly ("pre-computed for the demo").
5. Failure drill: unplug Wi-Fi/skip a live API → confirm the agent falls back with a clear message, not a stack trace.
6. Check the 90-second path: open `python -m kit ui`, paste question 1 → answer; question 2 → trace shows tool calls.
7. Record the screen (backup video) once everything passes. Save screenshots of the trace and graph view.
8. After the freeze (3:30 PM) only fix demo-path bugs; re-run `rehearse` after any change.
