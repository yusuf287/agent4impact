---
name: add-agent-team
description: Design or modify the multi-agent team in team.yaml (roles, tools, flow with sequential/parallel/loop, structured output, human approval). Use when the demo needs agents that collaborate or disagree.
---

# Design the agent team

Pattern that wins: **Scout → (Skeptic ‖ Planner) → Writer ⇄ Critic loop → [Approver] → Formatter**.
Every agent must have a reason you can say in one sentence. 3–5 agents. If an agent has no tool and no distinct judgement, delete it.

1. `python -m kit roles` to see roles and tools.
2. Edit `domains/<x>/team.yaml`:
   - `agents:` name → `{role, tools?, output_key, reads: [keys], extra: "task-specific text", output_schema?}`
   - `flow:` list; use `- parallel: [a, b]` and `- loop: {agents: [writer, critic], max_iterations: 3}`.
   - Each agent appears once in `flow`. `reads` must name keys produced EARLIER (loop feedback excepted).
   - `google_search` must be the only tool on that agent. `output_schema` agents cannot have tools (put a formatter at the end).
   - Add `approver` (tool `approval`) before any step that sends/dispatches/orders.
   - Custom agent: `role: custom` + `instruction: "..."` (no literal curly braces).
3. To define a new structured output: add a Pydantic class and register it in `SCHEMAS` in `kit_agent/schemas.py`.
4. `python -m kit team-check` until clean, then `python -m kit web` and open the graph/trace view.
5. Run the compound question from `demo_questions` and confirm each agent's `output_key` appears in state and the trace shows distinct tool calls.
6. Disagreement is a feature: make the Skeptic query data independently; show a case where it changed the answer.
