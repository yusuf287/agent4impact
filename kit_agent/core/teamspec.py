"""team.yaml validation (pure Python; used by `kit team-check` and at agent build time).

team:
  name: response_team
  description: "when to call this team"
  agents:
    scout:   {role: scout, output_key: scout_out, tools: [bigquery, predictions]}
    skeptic: {role: skeptic, reads: [scout_out], output_key: skeptic_out}
    planner: {role: planner, reads: [scout_out, skeptic_out], output_key: plan}
    ...
  flow:                       # executed in order
    - scout
    - parallel: [skeptic, planner]
    - loop: {agents: [writer, critic], max_iterations: 3}
    - formatter
"""
import re

NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def flow_names(flow) -> list:
    out = []
    for step in flow or []:
        if isinstance(step, str):
            out.append(step)
        elif isinstance(step, dict):
            if "parallel" in step:
                out += flow_names(step["parallel"])
            elif "loop" in step:
                out += flow_names(step["loop"].get("agents", []))
            elif "sequence" in step:
                out += flow_names(step["sequence"])
            else:
                out.append(f"<bad step {step}>")
        else:
            out.append(f"<bad step {step}>")
    return out


def validate(team: dict, roles: dict, tool_names: list, schemas: dict) -> list:
    """Returns a list of human-readable problems (empty = OK)."""
    errs = []
    if not team:
        return ["no team defined"]
    agents = team.get("agents") or {}
    if not agents:
        errs.append("team.agents is empty")
    if not team.get("flow"):
        errs.append("team.flow is empty")
    produced = {}
    for n, a in agents.items():
        if not NAME.match(n):
            errs.append(f"agent name '{n}' must be letters/digits/underscore")
        if a.get("role", "custom") not in roles:
            errs.append(f"{n}: unknown role '{a.get('role')}'. Roles: {sorted(roles)}")
        if a.get("role", "custom") == "custom" and not a.get("instruction"):
            errs.append(f"{n}: role custom needs an `instruction`")
        for t in a.get("tools", []):
            if t not in tool_names:
                errs.append(f"{n}: unknown tool '{t}'. Tools: {tool_names}")
        tl = a.get("tools", roles.get(a.get("role", "custom"), {}).get("tools", []))
        if "google_search" in tl and len(tl) > 1:
            errs.append(f"{n}: google_search must be the only tool on an agent")
        if a.get("output_schema") and a["output_schema"] not in schemas:
            errs.append(f"{n}: unknown output_schema '{a['output_schema']}'. Schemas: {sorted(schemas)}")
        if "approval" in tl:
            errs.append(f"{n}: the 'approval' tool cannot pause inside the team (it runs as a nested AgentTool). "
                        "Use role 'approver' (prepares the proposal); the root agent asks the human via request_approval")
        if a.get("output_schema") and a.get("tools"):
            errs.append(f"{n}: output_schema agents cannot use tools (ADK limitation) — split into two agents")
        if a.get("output_key"):
            produced[a["output_key"]] = n
    used = flow_names(team.get("flow"))
    for u in used:
        if u not in agents:
            errs.append(f"flow references undefined agent '{u}'")
    dups = {u for u in used if used.count(u) > 1}
    if dups:
        errs.append(f"agents used more than once in flow (ADK requires one parent): {sorted(dups)}")
    for n in agents:
        if n not in used:
            errs.append(f"agent '{n}' is defined but not in flow (unused)")
    # reads must refer to something produced earlier in the flow order
    seen = set()
    for u in used:
        a = agents.get(u, {})
        for r in a.get("reads", []):
            if r not in produced:
                errs.append(f"{u}: reads '{r}' but no agent has output_key '{r}'")
            elif produced[r] not in seen and produced[r] != u and r != "CRITICAL_FEEDBACK":
                errs.append(f"{u}: reads '{r}' produced by '{produced[r]}' which runs later (loops excepted)")
        seen.add(u)
    return errs
