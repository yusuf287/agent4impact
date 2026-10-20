"""Builds a multi-agent team from team.yaml (roles + flow). No Python needed to add agents."""
from google.adk.agents import Agent, LoopAgent, ParallelAgent, SequentialAgent

from .config import DOMAIN
from .core import teamspec
from .model import make_model, shared_config
from .roles import COMMON, LOOP_EXIT_TOOLS, ROLES
from .schemas import SCHEMAS


def _fill(text: str) -> str:
    return (text.replace("<<MISSION>>", DOMAIN.get("mission", ""))
                .replace("<<AUDIENCE>>", DOMAIN.get("audience", "decision makers")))


def _instruction(spec: dict, role: dict) -> str:
    base = spec.get("instruction") or role["instruction"]
    extra = spec.get("extra", "")
    reads = spec.get("reads", [])
    inputs = "".join(f"\n{k.upper()}:\n{{{k}?}}\n" for k in reads)
    if spec.get("role") == "writer" or spec.get("reads_feedback"):
        inputs += "\nCRITICAL_FEEDBACK (address if present):\n{CRITICAL_FEEDBACK?}\n"
    return _fill(base + ("\n" + extra if extra else "") + COMMON) + ("\nYOUR INPUTS:" + inputs if inputs else "")


def build_team(registry):
    team = DOMAIN.get("team")
    if not team:
        return None
    errs = teamspec.validate(team, ROLES, registry.names(), SCHEMAS)
    if errs:
        raise ValueError("team.yaml problems:\n - " + "\n - ".join(errs))
    m, cfg = make_model(), shared_config()
    specs = team["agents"]

    def make(name: str) -> Agent:
        spec = specs[name]
        role = ROLES[spec.get("role", "custom")]
        tool_names = list(spec.get("tools", role.get("tools", [])))
        if role.get("loop_exit"):
            tool_names += [t for t in LOOP_EXIT_TOOLS if t not in tool_names]
        kwargs = dict(name=name, model=spec.get("model") or m, generate_content_config=cfg,
                      description=spec.get("description", role["description"]),
                      instruction=_instruction(spec, role))
        if tool_names:
            kwargs["tools"] = registry.many(tool_names)
        if spec.get("output_key"):
            kwargs["output_key"] = spec["output_key"]
        if spec.get("output_schema"):
            kwargs["output_schema"] = SCHEMAS[spec["output_schema"]]
        return Agent(**kwargs)

    def build_step(step):
        if isinstance(step, str):
            return make(step)
        if "parallel" in step:
            return ParallelAgent(name=step.get("name", "par_" + "_".join(step["parallel"])[:40]),
                                 sub_agents=[build_step(s) for s in step["parallel"]])
        if "loop" in step:
            lp = step["loop"]
            return LoopAgent(name=lp.get("name", "loop_" + "_".join(lp["agents"])[:40]),
                             sub_agents=[build_step(s) for s in lp["agents"]],
                             max_iterations=int(lp.get("max_iterations", 3)))
        if "sequence" in step:
            return SequentialAgent(name=step.get("name", "seq_" + "_".join(step["sequence"])[:40]),
                                   sub_agents=[build_step(s) for s in step["sequence"]])
        raise ValueError(f"bad flow step: {step}")

    return SequentialAgent(name=team.get("name", "agent_team"),
                           description=team.get("description", "Runs the multi-agent team on the request."),
                           sub_agents=[build_step(s) for s in team["flow"]])
