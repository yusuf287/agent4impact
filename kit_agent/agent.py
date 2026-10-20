"""Root agent: ONE agent, many tools (the pattern the MLB lab recommends).

  root_agent
   |- BigQueryToolset (read-only)     SQL over structured data
   |- list_models / run_model_predictions   any trained BQML model (kit model)
   |- live tools                      fetch_live_json / get_forecast (live_api.enabled)
   |- AgentTool(visualization_agent)  charts via BuiltInCodeExecutor (must be isolated)
   |- AgentTool(team)                 YAML-defined multi-agent team (team.yaml), else default deep dive
   |- Maps MCP                        ENABLE_MAPS_MCP=1
   `- RemoteA2aAgent                  REMOTE_A2A_CARD=path/to/card.json
"""
import logging
import os

import google.auth
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

try:  # ADK 2.x location (verified on 2.12)
    from google.adk.integrations.bigquery import BigQueryCredentialsConfig, BigQueryToolset
    from google.adk.integrations.bigquery.config import BigQueryToolConfig, WriteMode
except ImportError:  # ADK 1.x (labs)
    from google.adk.tools.bigquery import BigQueryCredentialsConfig, BigQueryToolset
    from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode

from .config import DATASET, DOMAIN, PROJECT_ID
from .model import make_model, shared_config
from .prompts import as_provider, root_instructions
from .registry import Registry
from .team import build_team
from .viz import build_visualization_agent
from .workflow import build_deep_dive_pipeline

log = logging.getLogger(__name__)


# ---- BigQuery: read-only; agent still loads without credentials (fix with gcloud auth application-default login)
def _bigquery_toolset():
    try:
        creds, _ = google.auth.default()
    except Exception as e:
        log.warning("No Google credentials (%s). BigQuery tools will fail until you run "
                    "`gcloud auth application-default login`.", e)
        return None
    cfg = dict(write_mode=WriteMode.BLOCKED)
    try:
        tool_cfg = BigQueryToolConfig(**cfg, default_project_id=PROJECT_ID or None, default_dataset_id=DATASET or None)
    except Exception:  # older ADK without default ids
        tool_cfg = BigQueryToolConfig(**cfg)
    return BigQueryToolset(credentials_config=BigQueryCredentialsConfig(credentials=creds),
                           bigquery_tool_config=tool_cfg)


bigquery_toolset = _bigquery_toolset()
visualization_agent = build_visualization_agent()
registry = Registry(bigquery_toolset, visualization_agent)

tools = registry.many(["bigquery", "predictions", "viz", "approval"])  # approval lives on the ROOT so it can pause
if DOMAIN.get("live_api", {}).get("enabled"):
    tools += registry.many(["live_api", "forecast"])
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
    instruction=as_provider(root_instructions()),
    tools=tools,
    sub_agents=sub_agents,
)
