---
name: deploy-and-backup
description: Deploy the agent (Agent Runtime or Cloud Run A2A), register it in Gemini Enterprise, and back everything up (git push + OneDrive copy + screenshots). Use before judging and before the lab project expires.
---

# Deploy and back up

Ask the user to confirm before running any deploy command (cost, time ~6 min).

1. `python -m kit doctor` and `python -m kit rehearse` must pass.
2. `python -m kit deploy runtime` (managed endpoint) — it freezes the domain YAML into the package, deploys, then unfreezes.
   Note the resource name printed and saved in `logs/last_runtime_resource.txt`.
3. Test in Google Cloud console → Agent Platform → Agent Deployments → Playground with the first two demo questions.
4. Optional A2A: `python -m kit deploy a2a`, then fill `scripts/agent_card.template.json`.
5. Optional Gemini Enterprise: Agents → Add agent → Custom agent via Agent Runtime → paste the resource name;
   description must say when to use AND when NOT to use this agent; grant All users → Agent User.
6. If deploy fails: don't debug past 20 minutes — demo from `python -m kit web` and say so.
7. Backup: `git add -A && git commit -m "demo freeze" && git push`; copy the folder (without `.venv`, `.env`) to the OneDrive Documents folder; keep `logs/` and `rollback/`.
8. Do not delete cloud resources until the event is over (rollback scripts exist: `bash scripts/rollback_all.sh`).
