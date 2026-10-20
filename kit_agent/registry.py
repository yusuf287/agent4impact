"""Tool registry: names usable in team.yaml `tools:` lists -> real ADK tools.

  bigquery          generic SQL over the dataset (read-only)
  predictions       list_models + run_model_predictions (BQML)
  semantic_search   vector search (after `kit embed`)
  live_api          allow-listed fetch_live_json
  ec_alerts         Environment Canada alerts
  forecast          Open-Meteo forecast
  open_data         CKAN search (Toronto Open Data by default)
  vision            analyze_image (photo -> structured text)
  approval          human-in-the-loop (pauses for Approve/Reject)
  state             append_to_state
  exit_loop         end a LoopAgent
  google_search     Google Search grounding (must be the ONLY tool on that agent)
  maps              Google Maps MCP (needs ENABLE_MAPS_MCP=1 or listing it)
  viz               chart agent as a tool
"""
import os

from google.adk.tools import FunctionTool, exit_loop
from google.adk.tools.agent_tool import AgentTool

from . import tools as T


def _approval_tool():
    from .tools.approval import request_approval
    try:
        return FunctionTool(func=request_approval, require_confirmation=True)
    except TypeError:  # older ADK without tool confirmation
        return FunctionTool(func=request_approval)


def _maps_tool():
    import google.auth
    import google.auth.transport.requests as gtr
    from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams

    def maps_auth_headers(*_a, **_k) -> dict:
        """Fresh OAuth token for the Maps Grounding Lite MCP server (copy the lab's own header function if this fails)."""
        creds, project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(gtr.Request())
        return {"Authorization": f"Bearer {creds.token}",
                "x-goog-user-project": os.environ.get("GOOGLE_CLOUD_PROJECT", project or "")}

    return MCPToolset(connection_params=StreamableHTTPConnectionParams(
        url="https://mapstools.googleapis.com/mcp", timeout=15), header_provider=maps_auth_headers)


class Registry:
    def __init__(self, bigquery_toolset, viz_agent):
        self._bq, self._viz = bigquery_toolset, viz_agent
        self._cache: dict = {}

    def names(self):
        return ["bigquery", "predictions", "semantic_search", "live_api", "ec_alerts", "forecast", "open_data",
                "vision", "approval", "state", "exit_loop", "google_search", "maps", "viz"]

    def get(self, name: str) -> list:
        """Returns a LIST of tool objects for one registry name."""
        if name in self._cache:
            return self._cache[name]
        f = FunctionTool
        table = {
            "bigquery": lambda: [self._bq],
            "predictions": lambda: [f(func=T.list_models), f(func=T.run_model_predictions)],
            "semantic_search": lambda: [f(func=T.semantic_search)],
            "live_api": lambda: [f(func=T.fetch_live_json)],
            "ec_alerts": lambda: [f(func=T.get_ec_alerts)],
            "forecast": lambda: [f(func=T.get_forecast)],
            "open_data": lambda: [f(func=T.search_open_data)],
            "vision": lambda: [f(func=__import__("kit_agent.tools.vision", fromlist=["x"]).analyze_image)],
            "approval": lambda: [_approval_tool()],
            "state": lambda: [f(func=T.append_to_state)],
            "exit_loop": lambda: [exit_loop],
            "google_search": lambda: [__import__("google.adk.tools", fromlist=["google_search"]).google_search],
            "maps": lambda: [_maps_tool()],
            "viz": lambda: [AgentTool(agent=self._viz)],
        }
        if name not in table:
            raise KeyError(f"Unknown tool '{name}'. Available: {self.names()}")
        self._cache[name] = table[name]()
        return self._cache[name]

    def many(self, names) -> list:
        out = []
        for n in names:
            out.extend(self.get(n))
        return out
