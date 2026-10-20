"""Deep-dive pipeline = every workflow-agent pattern from the multi-agent lab:

  SequentialAgent
    1. data_analyst         (tools: BigQuery)         -> state['analysis']
    2. ParallelAgent        fan-out
         risk_assessor      -> state['risks']
         action_planner     -> state['actions']
    3. LoopAgent (max 3)    draft/critique refinement
         report_writer      -> state['report']
         critic             (exit_loop when good, else append feedback)

Swap the roles/instructions in domain.yaml -> `pipeline:` to retarget it.
"""
from google.adk.agents import Agent, LoopAgent, ParallelAgent, SequentialAgent
from google.adk.tools import FunctionTool, exit_loop

from .config import DOMAIN
from .model import make_model, shared_config
from .tools.state_tools import append_to_state


def _p(key: str, default: str) -> str:
    return (DOMAIN.get("pipeline") or {}).get(key, default)


def build_deep_dive_pipeline(bigquery_toolset) -> SequentialAgent:
    m, cfg = make_model(), shared_config()

    data_analyst = Agent(
        name="data_analyst", model=m, generate_content_config=cfg,
        description="Gathers the quantitative evidence for the request.",
        instruction=_p("analyst", "Query BigQuery to gather the key facts and numbers for the user's request. "
                       "Return a compact evidence summary with figures and table names used."),
        tools=[t for t in [bigquery_toolset] if t], output_key="analysis")

    risk_assessor = Agent(
        name="risk_assessor", model=m, generate_content_config=cfg,
        description="Identifies risks, gaps and equity/safety concerns.",
        instruction=_p("risk", "ANALYSIS:\n{analysis?}\n\nList the top risks, data gaps and who is most "
                       "affected. Be specific and cite the numbers in ANALYSIS."),
        output_key="risks")

    action_planner = Agent(
        name="action_planner", model=m, generate_content_config=cfg,
        description="Proposes prioritised actions.",
        instruction=_p("planner", "ANALYSIS:\n{analysis?}\n\nPropose 3-5 prioritised, feasible actions with "
                       "expected impact and what data would confirm success."),
        output_key="actions")

    fan_out = ParallelAgent(name="assessment_team", sub_agents=[risk_assessor, action_planner])

    report_writer = Agent(
        name="report_writer", model=m, generate_content_config=cfg,
        description="Writes the decision brief.",
        instruction=_p("writer", """Write a one-page decision brief: Situation, Evidence, Risks, Recommended actions, Next steps.
ANALYSIS:\n{analysis?}\nRISKS:\n{risks?}\nACTIONS:\n{actions?}\nCRITIC FEEDBACK (address it):\n{CRITICAL_FEEDBACK?}"""),
        output_key="report")

    critic = Agent(
        name="critic", model=m, generate_content_config=cfg,
        description="Reviews the brief and either approves it or requests changes.",
        instruction=_p("critic", """Review REPORT for: every claim backed by ANALYSIS numbers, clear recommendation,
no invented facts, plain language. If it is good, call exit_loop. Otherwise call append_to_state with
field='CRITICAL_FEEDBACK' and concise feedback.\nREPORT:\n{report?}\nANALYSIS:\n{analysis?}"""),
        tools=[FunctionTool(func=append_to_state), exit_loop])

    refine = LoopAgent(name="refine_loop", sub_agents=[report_writer, critic], max_iterations=3)

    return SequentialAgent(
        name="deep_dive_pipeline",
        description="Runs a full analysis: evidence -> risks & actions in parallel -> refined decision brief. "
                    "Use for complex, multi-part questions or when a report is requested.",
        sub_agents=[data_analyst, fan_out, refine])
