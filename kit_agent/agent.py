"""Root agent: ONE agent, many tools (the pattern the MLB lab recommends).

  root_agent
   |- BigQueryToolset (read-only)     SQL over structured data
   |- list_models / run_model_predictions   any trained BQML model (kit model)
   |- semantic_search                 vector search (kit embed), if configured
   |- live tools                      fetch_live_json / get_ec_alerts / get_forecast / search_open_data
   |- analyze_image                   multimodal (photo -> structured text)
   |- AgentTool(visualization_agent)  charts via BuiltInCodeExecutor (must be isolated)
   |- AgentTool(team)                 YAML-defined multi-agent team (team.yaml), else default deep dive
   |- Maps MCP                        ENABLE_MAPS_MCP=1
   `- RemoteA2aAgent                  REMOTE_A2A_CARD=path/to/card.json
"""
import os

import google.auth
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset

from .config import DOMAIN
from .model import make_model, shared_config
from .prompts import root_instructions
from .registry import Registry
from .team import build_team
from .viz import build_visualization_agent
from .workflow import build_deep_dive_pipeline

# ---- BigQuery (read-only guardrail when the ADK version supports it) -----
credentials, _ = google.auth.default()
_cred_cfg = BigQueryCredentialsConfig(credentials=credentials)
try:
    from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
    bigquery_toolset = BigQueryToolset(credentials_config=_cred_cfg,
                                       bigquery_tool_config=BigQueryToolConfig(write_mode=WriteMode.BLOCKED))
except Exception:
    bigquery_toolset = BigQueryToolset(credentials_config=_cred_cfg)

visualization_agent = build_visualization_agent()
registry = Registry(bigquery_toolset, visualization_agent)

tools = registry.many(["bigquery", "predictions", "viz"])
if DOMAIN.get("vector_search"):
    tools += registry.get("semantic_search")
if DOMAIN.get("live_api", {}).get("enabled"):
    tools += registry.many(["live_api", "ec_alerts", "forecast"])
if DOMAIN.get("open_data", {}).get("enabled"):
    tools += registry.get("open_data")
if DOMAIN.get("vision", {}).get("enabled"):
    tools += registry.get("vision")
if os.environ.get("ENABLE_MAPS_MCP") == "1":
    tools += registry.get("maps")

# ---- Multi-agent team: YAML if present, else the default pipeline --------
team_agent = build_team(registry) or build_deep_dive_pipeline(bigquery_toolset)
tools.append(AgentTool(agent=team_agent))

# ---- Optional remote A2A specialist --------------------------------------
sub_agents = []
if os.environ.get("REMOTE_A2A_CARD"):
    from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
    sub_agents.append(RemoteA2aAgent(name="remote_specialist",
                                     description=DOMAIN.get("a2a_description", "Remote specialist agent."),
                                     agent_card=os.environ["REMOTE_A2A_CARD"]))

root_agent = Agent(
    name=DOMAIN["agent_name"],
    model=make_model(),
    generate_content_config=shared_config(),
    description=DOMAIN["description"],
    instruction=root_instructions(),
    tools=tools,
    sub_agents=sub_agents,
)
