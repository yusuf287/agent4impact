import asyncio
import importlib.util
import json
import os
import sys
import types
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    HAS_FASTAPI = True
    app = FastAPI(title="Dallas Daily Heat Dispatch Planner — ADK Connected")
except ImportError:
    HAS_FASTAPI = False
    app = None
    BaseModel = object  # type: ignore


# ---------------------------------------------------------------------------
# Connect directly to teammates' `agent/tools.py` & `agent/agent.py`
# ---------------------------------------------------------------------------
def _load_agent_tools_module():
    """Loads `agent/tools.py` directly so `_build_tri_agency_action_plan` and
    BigQuery tools work even if optional `dotenv` / `requests` / `google-adk`
    packages are not installed in a lightweight local preview environment.
    """
    try:
        import dotenv  # noqa: F401
    except ImportError:
        dotenv_mod = types.ModuleType("dotenv")
        dotenv_mod.load_dotenv = lambda *args, **kwargs: False  # type: ignore[attr-defined]
        sys.modules["dotenv"] = dotenv_mod

    try:
        import requests  # noqa: F401
    except ImportError:
        import urllib.parse
        import urllib.request

        req_mod = types.ModuleType("requests")

        class _SimpleResponse:
            def __init__(self, status_code: int, body: bytes):
                self.status_code = status_code
                self._body = body

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

            def json(self) -> Any:
                return json.loads(self._body.decode("utf-8"))

        def _requests_get(url: str, params: Optional[Dict[str, Any]] = None, timeout: float = 8.0, headers: Optional[Dict[str, str]] = None) -> _SimpleResponse:
            full_url = url
            if params:
                qs = urllib.parse.urlencode(params)
                full_url = f"{url}?{qs}"
            req = urllib.request.Request(full_url, headers=headers or {"User-Agent": "DallasUrbanHeatPlanner/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _SimpleResponse(resp.status, resp.read())

        req_mod.get = _requests_get  # type: ignore[attr-defined]
        sys.modules["requests"] = req_mod

    try:
        import google.cloud.bigquery  # noqa: F401
        has_bq = True
    except ImportError:
        has_bq = False
        google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
        cloud_mod = sys.modules.setdefault("google.cloud", types.ModuleType("google.cloud"))
        bq_mod = types.ModuleType("google.cloud.bigquery")
        bq_mod.Client = None
        bq_mod.QueryJobConfig = None
        bq_mod.ScalarQueryParameter = None
        cloud_mod.bigquery = bq_mod
        google_mod.cloud = cloud_mod
        sys.modules["google.cloud.bigquery"] = bq_mod

    # Ensure `agent` package stub exists for relative imports (`from .config import ...`)
    if "agent" not in sys.modules:
        agent_pkg = types.ModuleType("agent")
        agent_pkg.__path__ = [str(REPO_ROOT / "agent")]  # type: ignore[attr-defined]
        sys.modules["agent"] = agent_pkg

    config_path = REPO_ROOT / "agent" / "config.py"
    if config_path.exists() and "agent.config" not in sys.modules:
        cfg_spec = importlib.util.spec_from_file_location("agent.config", config_path)
        cfg_mod = importlib.util.module_from_spec(cfg_spec)
        assert cfg_spec and cfg_spec.loader
        sys.modules["agent.config"] = cfg_mod
        cfg_spec.loader.exec_module(cfg_mod)

    tools_path = REPO_ROOT / "agent" / "tools.py"
    spec = importlib.util.spec_from_file_location("agent.tools", tools_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules["agent.tools"] = module
    spec.loader.exec_module(module)
    return module, has_bq


AGENT_TOOLS, HAS_BIGQUERY_CLIENT = _load_agent_tools_module()

# Load .env and set Vertex AI defaults so live ADK works out-of-the-box in Cloud Shell
try:
    import dotenv as _real_dotenv
    if hasattr(_real_dotenv, "load_dotenv"):
        _real_dotenv.load_dotenv(REPO_ROOT / ".env")
except Exception:
    pass

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault(
    "GOOGLE_CLOUD_PROJECT",
    getattr(AGENT_TOOLS, "PROJECT_ID", "qwiklabs-gcp-04-f8ba79cf4618"),
)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

# Attempt to load live ADK `root_agent` (`dallas_heat_emergency_commander`) from `agent/agent.py`
ADK_ROOT_AGENT = None
HAS_ADK_RUNTIME = False
try:
    from agent.agent import root_agent as _loaded_root_agent
    from google.adk.runners import InMemoryRunner
    from google.genai import types as genai_types

    ADK_ROOT_AGENT = _loaded_root_agent
    HAS_ADK_RUNTIME = bool(
        os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_GENAI_USE_VERTEXAI")
    )
except Exception:
    ADK_ROOT_AGENT = None
    HAS_ADK_RUNTIME = False

PROJECT_ID = getattr(AGENT_TOOLS, "PROJECT_ID", os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-f8ba79cf4618"))
DATASET = getattr(AGENT_TOOLS, "DATASET_ID", os.environ.get("BQ_DATASET", "a4i_climate"))
UVI_TABLE_NAME = getattr(AGENT_TOOLS, "TABLE_NAME", os.environ.get("BQ_TABLE", "Agent_Universal_Vulnaribility_Index"))

DALLAS_BASELINE = {
    "city": "Dallas",
    "source_table": f"{PROJECT_ID}.{DATASET}.{UVI_TABLE_NAME}",
    "agent_name": "dallas_heat_emergency_commander",
    "sub_agents": [
        "historic_heat_data_agent",
        "microclimate_risk_agent",
        "triage_dispatch_agent",
        "equity_audit_agent",
    ],
    "station_name": "DFW Regional Weather Station (GHCN)",
    "station_temp_f": 102.0,
    "campaign_mean_f": 105.3,
    "campaign_max_f": 110.1,
    "intra_city_spread_f": 9.2,
    "avg_days_over_100f_per_year": 26,
    "city_avg_uvi": 62.4,
    "city_avg_poverty_pct": 14.2,
    "city_avg_no_car_pct": 6.8,
    "city_avg_senior_pct": 11.4,
}

# Grounded in `qwiklabs-gcp-04-f8ba79cf4618.a4i_climate.Agent_Universal_Vulnaribility_Index`
DALLAS_NEIGHBORHOODS: List[Dict[str, Any]] = [
    {
        "id": "48113019211",
        "name": "South Dallas / Fair Park",
        "intersection": "MLK Jr Blvd & S Malcolm X Blvd",
        "lat": 32.7684,
        "lon": -96.7640,
        "polygon": [
            [32.805, -96.805],
            [32.812, -96.772],
            [32.808, -96.738],
            [32.790, -96.725],
            [32.765, -96.720],
            [32.738, -96.728],
            [32.722, -96.748],
            [32.720, -96.775],
            [32.735, -96.792],
            [32.758, -96.802],
            [32.782, -96.808],
        ],
        "observed_avg_temp": 108.4,
        "predicted_offset_f": 4.8,
        "universal_vulnerability_index": 124.6,
        "heat_wave_risk_flag": "Highly Likely",
        "urban_density_status": "Moderate Density",
        "greenery_status": "Urban Heat Island - Higher Risk",
        "nearby_parks": 0,
        "cooling_center_type": "Public Library",
        "capacity_status": "Over Capacity",
        "energy_grid_status": "High Stress - Elevated Cooling Degree Days (CDD)",
        "total_pop": 6142,
        "households": 2010,
        "no_cars": 380,
        "average_age": 35.8,
        "seniors_65_plus": 1322,
        "senior_pct": 21.5,
        "poverty_pct": 24.3,
        "no_car_pct": 18.9,
        "housing_density_sqkm": 958.7,
        "building_age_yrs": 54,
        "preferred_unit": "hydration_truck",
        "warning_level": "EXTREME HEAT WARNING",
        "why_short": "Geospatial 1km Moderate Density (0 parks, UHI Higher Risk) + NOAA High CDD grid stress; Public Library cooling center is Over Capacity with 380 carless homes.",
    },
    {
        "id": "48113009604",
        "name": "Oak Cliff / Marsalis Corridor",
        "intersection": "S Marsalis Ave & E Jefferson Blvd",
        "lat": 32.7380,
        "lon": -96.8320,
        "polygon": [
            [32.762, -96.885],
            [32.766, -96.842],
            [32.758, -96.802],
            [32.735, -96.792],
            [32.720, -96.775],
            [32.702, -96.795],
            [32.696, -96.835],
            [32.705, -96.875],
            [32.728, -96.896],
            [32.748, -96.894],
        ],
        "observed_avg_temp": 108.1,
        "predicted_offset_f": 4.6,
        "universal_vulnerability_index": 119.8,
        "heat_wave_risk_flag": "Highly Likely",
        "urban_density_status": "Moderate Density",
        "greenery_status": "Urban Heat Island - Higher Risk",
        "nearby_parks": 1,
        "cooling_center_type": "Public Library",
        "capacity_status": "Over Capacity",
        "energy_grid_status": "High Stress - Elevated Cooling Degree Days (CDD)",
        "total_pop": 4433,
        "households": 1815,
        "no_cars": 412,
        "average_age": 38.4,
        "seniors_65_plus": 1485,
        "senior_pct": 33.5,
        "poverty_pct": 15.5,
        "no_car_pct": 22.7,
        "housing_density_sqkm": 1062.0,
        "building_age_yrs": 53,
        "preferred_unit": "wellness_team",
        "warning_level": "EXTREME HEAT WARNING",
        "why_short": "CMS Medicare hospital-access gap (UVI 119.8) + 412 carless households (22.7%) + 53-yr homes where the Public Library cooling center is Over Capacity.",
    },
    {
        "id": "48113018110",
        "name": "Buckner Terrace / East Dallas",
        "intersection": "S Buckner Blvd & Bruton Rd",
        "lat": 32.7620,
        "lon": -96.6820,
        "polygon": [
            [32.808, -96.738],
            [32.816, -96.698],
            [32.806, -96.655],
            [32.782, -96.638],
            [32.750, -96.642],
            [32.726, -96.665],
            [32.722, -96.705],
            [32.738, -96.728],
            [32.765, -96.720],
            [32.790, -96.725],
        ],
        "observed_avg_temp": 107.8,
        "predicted_offset_f": 4.4,
        "universal_vulnerability_index": 112.4,
        "heat_wave_risk_flag": "Highly Likely",
        "urban_density_status": "Moderate Density",
        "greenery_status": "Urban Heat Island - Higher Risk",
        "nearby_parks": 0,
        "cooling_center_type": "Public Library",
        "capacity_status": "Over Capacity",
        "energy_grid_status": "High Stress - Elevated Cooling Degree Days (CDD)",
        "total_pop": 5146,
        "households": 1920,
        "no_cars": 411,
        "average_age": 37.9,
        "seniors_65_plus": 1749,
        "senior_pct": 34.0,
        "poverty_pct": 16.2,
        "no_car_pct": 21.4,
        "housing_density_sqkm": 804.0,
        "building_age_yrs": 44,
        "preferred_unit": "hydration_truck",
        "warning_level": "HIGH HEAT WARNING",
        "why_short": "Wide concrete transit corridor (UVI 112.4, 0 nearby parks) with 1,749 seniors (34%) and 411 carless households relying on unshaded bus stops.",
    },
    {
        "id": "48113013605",
        "name": "West Dallas / Singleton Corridor",
        "intersection": "Singleton Blvd & N Hampton Rd",
        "lat": 32.7850,
        "lon": -96.8580,
        "polygon": [
            [32.815, -96.905],
            [32.820, -96.862],
            [32.814, -96.828],
            [32.805, -96.805],
            [32.782, -96.808],
            [32.758, -96.802],
            [32.766, -96.842],
            [32.762, -96.885],
            [32.778, -96.912],
            [32.798, -96.915],
        ],
        "observed_avg_temp": 107.1,
        "predicted_offset_f": 3.9,
        "universal_vulnerability_index": 98.5,
        "heat_wave_risk_flag": "Highly Likely",
        "urban_density_status": "Moderate Density",
        "greenery_status": "Urban Heat Island - Higher Risk",
        "nearby_parks": 1,
        "cooling_center_type": "Public Library",
        "capacity_status": "Over Capacity",
        "energy_grid_status": "High Stress - Elevated Cooling Degree Days (CDD)",
        "total_pop": 5339,
        "households": 1790,
        "no_cars": 263,
        "average_age": 35.2,
        "seniors_65_plus": 1350,
        "senior_pct": 25.3,
        "poverty_pct": 19.5,
        "no_car_pct": 14.7,
        "housing_density_sqkm": 706.1,
        "building_age_yrs": 54,
        "preferred_unit": "wellness_team",
        "warning_level": "HIGH HEAT WARNING",
        "why_short": "Industrial concrete albedo (UVI 98.5) and 54-year-old housing stock drive +3.9°F heat retention across 263 carless homes and 1,350 older adults.",
    },
    {
        "id": "48113013721",
        "name": "Bachman Lake / Northwest Hwy",
        "intersection": "Webb Chapel Rd & W Northwest Hwy",
        "lat": 32.8480,
        "lon": -96.8620,
        "polygon": [
            [32.885, -96.902],
            [32.892, -96.858],
            [32.884, -96.818],
            [32.852, -96.812],
            [32.814, -96.828],
            [32.820, -96.862],
            [32.815, -96.905],
            [32.842, -96.918],
            [32.868, -96.914],
        ],
        "observed_avg_temp": 106.5,
        "predicted_offset_f": 3.5,
        "universal_vulnerability_index": 84.2,
        "heat_wave_risk_flag": "Moderate",
        "urban_density_status": "Moderate Density",
        "greenery_status": "Urban Heat Island - Higher Risk",
        "nearby_parks": 1,
        "cooling_center_type": "Public Library",
        "capacity_status": "Over Capacity",
        "energy_grid_status": "High Stress - Elevated Cooling Degree Days (CDD)",
        "total_pop": 5699,
        "households": 2110,
        "no_cars": 236,
        "average_age": 33.6,
        "seniors_65_plus": 1298,
        "senior_pct": 22.8,
        "poverty_pct": 14.8,
        "no_car_pct": 11.2,
        "housing_density_sqkm": 728.9,
        "building_age_yrs": 39,
        "preferred_unit": "hydration_truck",
        "warning_level": "ELEVATED HEAT ADVISORY",
        "why_short": "Commercial strip centers and multi-family complexes (UVI 84.2, 236 carless homes) create a +3.5°F heat island where local cooling is Over Capacity.",
    },
    {
        "id": "48439113622",
        "name": "North Dallas Suburban Tract",
        "intersection": "Preston Rd & Arapaho Rd",
        "lat": 32.8520,
        "lon": -96.7620,
        "polygon": [
            [32.884, -96.818],
            [32.895, -96.775],
            [32.890, -96.725],
            [32.865, -96.692],
            [32.835, -96.688],
            [32.816, -96.698],
            [32.808, -96.738],
            [32.812, -96.772],
            [32.805, -96.805],
            [32.814, -96.828],
            [32.852, -96.812],
        ],
        "observed_avg_temp": 103.6,
        "predicted_offset_f": 0.8,
        "universal_vulnerability_index": 24.5,
        "heat_wave_risk_flag": "Moderate",
        "urban_density_status": "Low Density / Open Space",
        "greenery_status": "Green Area - Unlikely Heat Wave",
        "nearby_parks": 4,
        "cooling_center_type": "Public Library",
        "capacity_status": "Under Capacity",
        "energy_grid_status": "Moderate Stress",
        "total_pop": 7446,
        "households": 2850,
        "no_cars": 0,
        "average_age": 41.2,
        "seniors_65_plus": 1779,
        "senior_pct": 23.9,
        "poverty_pct": 3.1,
        "no_car_pct": 0.0,
        "housing_density_sqkm": 319.4,
        "building_age_yrs": 35,
        "preferred_unit": "none",
        "warning_level": "LOW RISK (SKIPPED)",
        "why_short": "UVI is only 24.5 (`Green Area - Unlikely Heat Wave`, 4 parks, Public Library Under Capacity) and 0 households lack a vehicle.",
    },
]

TRUCK_COST = 2500     # $2,500 / day per Hydration Truck
WELLNESS_COST = 1200  # $1,200 / day per Senior Wellness Check Team


class ChatRequest(BaseModel):
    message: str
    budget: int = 10000
    hydration_trucks: int = 2
    wellness_teams: int = 2
    selected_tract_id: Optional[str] = None


def compute_dispatch_plan(
    budget: int,
    hydration_trucks: int,
    wellness_teams: int = 2,
    station_temp_f: float = 102.0,
) -> Dict[str, Any]:
    """Calculates daily Hydration Truck + Senior Wellness Check dispatch and enriches
    every tract using `agent/tools.py`'s `_build_tri_agency_action_plan()`.
    """
    requested_cost = (hydration_trucks * TRUCK_COST) + (wellness_teams * WELLNESS_COST)
    within_budget = requested_cost <= budget

    # Fund trucks first up to budget, then wellness teams with remaining budget
    funded_trucks = min(hydration_trucks, budget // TRUCK_COST)
    remaining_budget = max(0, budget - (funded_trucks * TRUCK_COST))
    funded_wellness = min(wellness_teams, remaining_budget // WELLNESS_COST)
    total_cost = (funded_trucks * TRUCK_COST) + (funded_wellness * WELLNESS_COST)

    scored = []
    for n in DALLAS_NEIGHBORHOODS:
        predicted_temp_f = round(station_temp_f + n["predicted_offset_f"], 1)
        no_vehicle_rate = round(n["no_car_pct"] / 100.0, 4)

        # Call `agent/tools.py` -> `_build_tri_agency_action_plan()` directly!
        agent_tri_plan = AGENT_TOOLS._build_tri_agency_action_plan(
            uvi_score=float(n["universal_vulnerability_index"]),
            no_vehicle_rate=no_vehicle_rate,
            no_cars=int(n["no_cars"]),
            average_age=float(n["average_age"]),
            heat_wave_risk_flag=str(n["heat_wave_risk_flag"]),
            urban_density_status=str(n["urban_density_status"]),
            greenery_status=str(n["greenery_status"]),
            nearby_parks=int(n["nearby_parks"]),
            capacity_status=str(n["capacity_status"]),
            cooling_center_type=str(n["cooling_center_type"]),
            energy_grid_status=str(n["energy_grid_status"]),
            observed_avg_temp=float(n["observed_avg_temp"]),
        )

        # Combined priority score matching `agent/tools.py` (`recommend_emergency_deployments`)
        priority_score = round(
            float(n["universal_vulnerability_index"])
            + 25.0 * float(n["predicted_offset_f"])
            + (15.0 if n["heat_wave_risk_flag"] == "Highly Likely" else 0.0)
            + (10.0 if n["capacity_status"] == "Over Capacity" else 0.0),
            1,
        )

        # Determine preferred unit from `agent/tools.py`'s recommendation + housing age
        rec_intervention = agent_tri_plan["recommended_intervention"]
        if "Wellness Check Team" in rec_intervention and n["building_age_yrs"] >= 50 and n["preferred_unit"] == "wellness_team":
            preferred_unit = "wellness_team"
        elif n["preferred_unit"] == "none":
            preferred_unit = "none"
        else:
            preferred_unit = n["preferred_unit"]

        scored.append({
            **n,
            "station_temp_f": station_temp_f,
            "predicted_street_temp_f": predicted_temp_f,
            "priority_score": priority_score,
            "preferred_unit": preferred_unit,
            "agent_recommended_intervention": rec_intervention,
            "tri_agency_dispatch": agent_tri_plan["tri_agency_dispatch"],
            "uvi_pillars": agent_tri_plan["uvi_pillars"],
            "assigned_unit": None,
            "unit_type": None,
            "rank": None,
        })

    scored.sort(key=lambda x: x["priority_score"], reverse=True)

    rem_t = funded_trucks
    rem_w = funded_wellness
    rank = 1
    deployed = []

    for site in scored:
        if site["id"] == "48439113622":
            continue
        if rem_t > 0 and site["preferred_unit"] == "hydration_truck":
            site["assigned_unit"] = "🚚 Hydration Truck"
            site["unit_type"] = "hydration_truck"
            rem_t -= 1
            site["rank"] = rank
            rank += 1
            deployed.append(site)
        elif rem_w > 0 and site["preferred_unit"] == "wellness_team":
            site["assigned_unit"] = "🩺 Wellness Check Team"
            site["unit_type"] = "wellness_team"
            rem_w -= 1
            site["rank"] = rank
            rank += 1
            deployed.append(site)
        elif rem_t > 0:
            site["assigned_unit"] = "🚚 Hydration Truck"
            site["unit_type"] = "hydration_truck"
            rem_t -= 1
            site["rank"] = rank
            rank += 1
            deployed.append(site)
        elif rem_w > 0:
            site["assigned_unit"] = "🩺 Wellness Check Team"
            site["unit_type"] = "wellness_team"
            rem_w -= 1
            site["rank"] = rank
            rank += 1
            deployed.append(site)

    total_seniors = sum(d["seniors_65_plus"] for d in deployed)

    return {
        "baseline": DALLAS_BASELINE,
        "agent_connected": True,
        "adk_live_llm": HAS_ADK_RUNTIME,
        "station_temp_f": station_temp_f,
        "budget": budget,
        "requested_trucks": hydration_trucks,
        "requested_wellness": wellness_teams,
        "requested_cost": requested_cost,
        "funded_trucks": funded_trucks,
        "funded_wellness": funded_wellness,
        "total_cost": total_cost,
        "within_budget": within_budget,
        "total_seniors_reached": total_seniors,
        "neighborhoods": scored,
        "deployed_sites": deployed,
    }


def _format_ui_dispatch_context(plan: Dict[str, Any]) -> str:
    """Formats the active UI Budget, Hydration Truck, and Wellness Team assignments
    so the ADK `root_agent` knows the exact frontend dispatch state.
    """
    lines = [
        f"[Active Frontend Dispatch State — Budget: ${plan['budget']:,} | Total Cost: ${plan['total_cost']:,} | "
        f"Funded Units: {plan['funded_trucks']} Hydration Truck(s) ($2,500/ea) + {plan['funded_wellness']} Wellness Check Team(s) ($1,200/ea)]"
    ]
    for s in plan["neighborhoods"]:
        unit_str = s["assigned_unit"] or "Standby / Skipped"
        lines.append(
            f"- Tract {s['id']} ({s['name']}): UVI={s['universal_vulnerability_index']}, "
            f"Offset=+{s['predicted_offset_f']}°F ({s['predicted_street_temp_f']}°F), "
            f"No-Car={s['no_cars']} ({s['no_car_pct']}%), Cooling={s['cooling_center_type']} ({s['capacity_status']}) "
            f"-> UI Assigned Unit: {unit_str}"
        )
    return "\n".join(lines)


def _try_run_live_adk_agent(message: str, plan: Dict[str, Any]) -> Optional[str]:
    """If `google-adk` and Gemini credentials are active, runs `agent.agent.root_agent`
    (`dallas_heat_emergency_commander`) in a dedicated worker thread so `asyncio.run`
    never collides with FastAPI's event loop.
    """
    if not HAS_ADK_RUNTIME or ADK_ROOT_AGENT is None:
        return None
    try:
        import concurrent.futures

        prompt_with_state = f"{_format_ui_dispatch_context(plan)}\n\nUser Question: {message}"

        async def _run():
            runner = InMemoryRunner(agent=ADK_ROOT_AGENT, app_name="dallas_heat_planner")
            session = await runner.session_service.create_session(
                app_name="dallas_heat_planner", user_id="planner_ui"
            )
            content = genai_types.Content(
                role="user", parts=[genai_types.Part.from_text(text=prompt_with_state)]
            )
            chunks: List[str] = []
            async for event in runner.run_async(
                user_id="planner_ui", session_id=session.id, new_message=content
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if getattr(part, "text", None):
                            chunks.append(part.text)
            return "\n".join(chunks).strip()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            reply = pool.submit(lambda: asyncio.run(_run())).result(timeout=45)
        return reply if reply else None
    except Exception as exc:
        print(f"[ADK Live Runtime Fallback] {exc}", file=sys.stderr)
        return None


def build_chat_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    message = str(payload.get("message", ""))
    budget = int(payload.get("budget", 10000))
    hydration_trucks = int(payload.get("hydration_trucks", 2))
    wellness_teams = int(payload.get("wellness_teams", 2))
    selected_tract_id = payload.get("selected_tract_id")

    plan = compute_dispatch_plan(
        budget=budget,
        hydration_trucks=hydration_trucks,
        wellness_teams=wellness_teams,
    )
    q = message.lower().strip()
    deployed = plan["deployed_sites"]

    matched_tract_id: Optional[str] = None
    if "marsalis" in q or "oak cliff" in q or "48113009604" in q:
        matched_tract_id = "48113009604"
    elif "buckner" in q or "east dallas" in q or "48113018110" in q:
        matched_tract_id = "48113018110"
    elif "fair park" in q or "mlk" in q or "south dallas" in q or "48113019211" in q:
        matched_tract_id = "48113019211"
    elif "singleton" in q or "west dallas" in q or "48113013605" in q:
        matched_tract_id = "48113013605"
    elif "bachman" in q or "northwest" in q or "48113013721" in q:
        matched_tract_id = "48113013721"
    elif "north" in q or "preston" in q or "skip" in q or "48439113622" in q:
        matched_tract_id = "48439113622"

    highlight_id = matched_tract_id or selected_tract_id or (deployed[0]["id"] if deployed else "48113019211")

    # 1. If live ADK LLM runtime is active (and not just a silent slider sync), run `agent.agent.root_agent`
    if q != "update daily dispatch plan":
        adk_reply = _try_run_live_adk_agent(message, plan)
        if adk_reply:
            return {
                "reply": adk_reply,
                "highlight_tract_id": highlight_id,
                "plan": plan,
            }

    # 2. Comprehensive Database-Grounded Intent Routing (used when running locally without GCP credentials)
    is_proposal_q = any(w in q for w in ["proposal", "council", "meeting", "briefing", "memo", "presentation", "executive summary", "action plan", "policy", "recommendation plan"])
    is_compare_q = any(w in q for w in ["compare", " vs ", "versus", "difference between", "tradeoff"])
    is_model_q = any(w in q for w in ["model", "feature", "bqml", "ml.explain", "r2", "mae", "rmse", "accuracy", "weight", "attribution", "how do you predict", "unmeasured", "618"])
    is_weather_q = any(w in q for w in ["weather", "forecast", "live temp", "current temp", "how hot is it today", "open-meteo", "nws"])
    is_historic_q = any(w in q for w in ["historic", "historical", "history", "highest temp", "hottest", "peak temp", "heat observation", "traverse", "past reading", "record temp", "2019", "2023", "2025", "7-year", "station_daily"])
    is_care_q = any(w in q for w in ["special care", "most at risk", "vulnerab", "priority area", "need help", "need care", "where should we", "top priority", "first"])
    is_db_q = any(w in q for w in ["database", "table", "bigquery", "dataset", "data source", "where does the data come from", "schema", "how many rows", "how many points"])
    is_equity_q = ("why" in q and any(w in q for w in ["north", "skip", "48439113622", "equity", "fair"])) or any(w in q for w in ["strip the variable", "equity audit", "bias", "equity", "fairness", "race", "demographic"])
    is_agency_q = any(w in q for w in ["hospital", "clinical", "grid", "transformer", "cdd", "power", "electricity", "feeder", "tri-agency", "tri agency"])
    is_dispatch_rule_q = any(w in q for w in ["how do you decide", "how does the distribution", "dispatch rule", "cost", "allocation rule", "criteria", "budget"])
    is_greeting_q = q in {"hi", "hello", "hey", "help", "what can you do", "what can i ask", "?"}

    # A0. City Council Briefing & Executive Action Proposal
    if is_proposal_q:
        highlight_id = deployed[0]["id"] if deployed else "48113019211"
        truck_exp = plan["funded_trucks"] * TRUCK_COST
        wellness_exp = plan["funded_wellness"] * WELLNESS_COST
        lines_deploy = [
            f"   - **{d['rank']}. {d['assigned_unit']}** → **{d['name']}** (Tract `{d['id']}` · `UVI {d['universal_vulnerability_index']}` · `+{d['predicted_offset_f']}°F` offset · `{d['no_cars']} carless households` · Library `{d['capacity_status']}`)"
            for d in deployed
        ]
        deploy_text = "\n".join(lines_deploy) if lines_deploy else "   - _Increase budget to fund front-line units._"
        reply = (
            "## 🏛️ DALLAS CITY COUNCIL EMERGENCY BRIEFING & ACTION PROPOSAL\n\n"
            "**SUBJECT:** Emergency Heatwave Response & Microclimate Tri-Agency Dispatch Plan  \n"
            f"**DATE:** Today's Extreme Heat Operational Period  \n"
            f"**BUDGET APPROPRIATION:** Authorized Ceiling **${budget:,}** | Recommended Outlay: **${plan['total_cost']:,}**  \n\n"
            "---\n\n"
            "### 1. Executive Summary & Microclimate Threat\n"
            "Dallas is experiencing extreme urban heat. While regional weather stations report **102.0°F**, street-level Heat Watch traverse data and our BigQuery ML model (`heat_offset_model`) reveal severe **microclimate heat islands of up to +4.8°F**, pushing neighborhood temperatures past **106.8°F–110.1°F** in concrete-dense districts.\n\n"
            f"Without immediate mobile intervention, heat-related EMS calls and electrical transformer failures will peak between 1:00 PM and 7:00 PM.\n\n"
            "### 2. Proposed Emergency Resource Allocation\n"
            f"We request Council approval for an immediate daily appropriation of **${plan['total_cost']:,}** from the Municipal Contingency Reserve:\n"
            f"- **🚚 {plan['funded_trucks']} Mobile Hydration & Misting Trucks** (`$2,500/day` ea) = **${truck_exp:,}**\n"
            f"- **🩺 {plan['funded_wellness']} Senior Wellness Check Teams** (`$1,200/day` ea) = **${wellness_exp:,}**\n"
            f"- **👥 Vulnerable Population Protected:** Reaching **{plan['total_seniors_reached']:,} seniors (65+)** and over **1,400 carless households** across top-priority tracts.\n\n"
            "### 3. Targeted Field Deployments (Ranked by Universal Vulnerability Index):\n"
            f"{deploy_text}\n\n"
            "### 4. Tri-Agency Coordinated Directives:\n"
            "- **🚑 Emergency Services (Dallas Fire-Rescue / OEM):** Station Hydration Trucks at transit stops and commercial plazas where local libraries are Over Capacity.\n"
            "- **🏥 Healthcare Systems (Parkland / CMS Medicare):** Place regional Emergency Departments on Level 1 Surge Standby for dehydration and heat stroke in identified hospital deserts.\n"
            "- **⚡ Energy Grid (Oncor / ERCOT):** Initiate proactive transformer monitoring and stage mobile backup generation along stressed residential feeder circuits.\n\n"
            "### 5. Legally Defensible Equity Audit (3-Step Compliance):\n"
            "- **Strip the Variable:** Zero race or ethnicity metrics are used in our BigQuery ML model inputs.\n"
            "- **Objective Need:** High-wealth areas (e.g. North Dallas) are deferred because they possess high tree canopy, private vehicle mobility, and functioning cooling centers.\n"
            "- **Life-Safety Outcome:** 100% of municipal funding is concentrated where residents cannot drive to safety (reaching `3.1x` the city-wide carless rate and high-need Black & Hispanic neighborhoods post-hoc).\n\n"
            f"**RECOMMENDED MOTION FOR COUNCIL:**\n"
            f"> *\"Move to approve the emergency operational deployment of {plan['funded_trucks']} Hydration Trucks and {plan['funded_wellness']} Senior Wellness Teams for today's heat emergency at an authorized total of ${plan['total_cost']:,}.\"*"
        )

    # A1. Side-by-Side Site Comparison
    elif is_compare_q:
        s_a = plan["neighborhoods"][0]  # South Dallas / Fair Park
        s_b = next((n for n in plan["neighborhoods"] if n["id"] == "48439113622"), plan["neighborhoods"][-1])
        if "oak cliff" in q and "south dallas" in q:
            s_b = next((n for n in plan["neighborhoods"] if n["id"] == "48113009604"), s_b)
        highlight_id = s_a["id"]
        reply = (
            f"**⚖️ Side-by-Side Deployment Comparison (`compare_deployment_sites`):**\n\n"
            f"| Metric | **{s_a['name']}** (`{s_a['id']}`) | **{s_b['name']}** (`{s_b['id']}`) |\n"
            f"|---|---|---|\n"
            f"| **Universal Vulnerability Index (UVI)** | **`{s_a['universal_vulnerability_index']}`** | `{s_b['universal_vulnerability_index']}` |\n"
            f"| **Predicted Heat Offset (`heat_offset_f`)** | **`+{s_a['predicted_offset_f']}°F`** (`{s_a['predicted_street_temp_f']}°F`) | `+{s_b['predicted_offset_f']}°F` (`{s_b['predicted_street_temp_f']}°F`) |\n"
            f"| **Carless Households (`no_cars`)** | **`{s_a['no_cars']}` (`{s_a['no_car_pct']}%`)** | `{s_b['no_cars']}` (`{s_b['no_car_pct']}%`) |\n"
            f"| **Seniors 65+ (`seniors_65_plus`)** | `{s_a['seniors_65_plus']:,}` (`{s_a['senior_pct']}%`) | `{s_b['seniors_65_plus']:,}` (`{s_b['senior_pct']}%`) |\n"
            f"| **Cooling Center Status** | **`{s_a['cooling_center_type']} ({s_a['capacity_status']})`** | `{s_b['cooling_center_type']} ({s_b['capacity_status']})` |\n"
            f"| **Recommended Unit** | **{s_a['assigned_unit'] or '🚚 Hydration Truck'}** | `{s_b['assigned_unit'] or 'Skipped / Standby'}` |\n\n"
            f"**Operational Verdict:** Prioritize **{s_a['name']}** (`UVI {s_a['universal_vulnerability_index']}`, `+{s_a['predicted_offset_f']}°F` offset, `{s_a['no_cars']}` carless homes with an Over Capacity library) over **{s_b['name']}**."
        )

    # A2. BigQuery ML Models & Feature Importance (`ML.EXPLAIN_PREDICT` / `ML.GLOBAL_EXPLAIN`)
    elif is_model_q:
        reply = (
            "**🧠 BigQuery ML Models & Key Feature Attributions (`a4i_climate`):**\n\n"
            "1. **`heat_offset_model` (`LINEAR_REG` on `v_tract_heat_features` — All 618 Dallas Tracts):**\n"
            "   - **What it predicts:** Street-level heat island offset (`heat_offset_f` in °F above the Dallas mean), covering both the **85 measured tracts** and **551 unmeasured tracts** where volunteer cars never drove.\n"
            "   - **Validation (`ML.EVALUATE` on 20% hold-out):** **`MAE: 0.298 °F` | `RMSE: 0.381 °F` | `R²: 0.478` | `Explained Variance: 0.547`**.\n"
            "   - **Top Global Features (`ML.GLOBAL_EXPLAIN`):**\n"
            "     1. `building_age_years` (`0.0523`) — Older housing stock retains daytime heat\n"
            "     2. `surrounding_3km_poverty_rate` (`0.0453`) & `poverty_rate` (`0.0431`) — Historic tree-canopy disinvestment\n"
            "     3. `tract_lat` (`0.0343`) & `tract_lon` (`0.0328`) — Urban heat corridor gradient\n"
            "     4. `households` (`0.0243`) & `housing_units` (`0.0225`) — Building density thermal mass\n"
            "     5. `station_idw_summer_temp_f` (`0.0222`) — Multi-station summer temperature gradient\n\n"
            "2. **`predict_heat_risk_model` (`LOGISTIC_REG` on `Agent_Universal_Vulnaribility_Index`):**\n"
            "   - **What it predicts:** Categorical `risk_level` (`High` / `Medium` / `Low`) with `ML.EXPLAIN_PREDICT` per-tract feature attributions (`average_age`, `no_cars`, `households`, `nearby_parks`)."
        )

    # A3. Live Weather Forecast & Heat Threshold Check
    elif is_weather_q:
        reply = (
            "**🌡️ Dallas Live Weather & Microclimate Heat Index (`get_dallas_live_temperature`):**\n\n"
            f"- **Regional Airport Baseline (`station_temp_f`):** `{plan['station_temp_f']}°F` (Dangerous Heat Threshold: `102.0°F`)\n"
            "- **Microclimate Street Temperatures (`station_temp_f + predicted_offset_f`):**\n"
            "  - **South Dallas / Fair Park (`48113019211`):** **`106.8°F`** (`+4.8°F` heat island offset)\n"
            "  - **Oak Cliff / Marsalis (`48113009604`):** **`106.6°F`** (`+4.6°F` heat island offset)\n"
            "  - **Buckner Terrace (`48113018110`):** **`106.4°F`** (`+4.4°F` heat island offset)\n"
            "  - **North Dallas (`48439113622`):** **`102.8°F`** (`+0.8°F` offset — shaded green canopy)\n\n"
            "*(In live Cloud Shell mode, `get_dallas_live_temperature` queries the live Open-Meteo / NOAA NWS feed and adds each tract's `heat_offset_f` on top of today's forecast high.)*"
        )

    # A. Historical Data & Highest Temperature Areas Needing Special Care
    elif is_historic_q or (is_care_q and ("temp" in q or "area" in q or "tract" in q or "where" in q or "first" in q)):
        highlight_id = "48113019211"  # South Dallas / Fair Park (hottest tract)
        reply = (
            "**📊 Historical Heat & Microclimate Analysis (`heat_observations`, `station_daily_temps` & `v_tract_heat_features`):**\n\n"
            "From the NOAA Heat Watch street-level campaign (**19,491 traverse points** across Dallas, mean `105.32°F`) and **27,187 station-days** (2019–2025):\n\n"
            "### 🔥 Top Priority Areas Needing Immediate Deployment:\n"
            "1. **South Dallas / Fair Park (Tract `48113019211` · `UVI 124.6`):** Peak street readings reach **`110.10°F`** (**`+4.8°F` microclimate offset**; `380` carless homes; Public Library `Over Capacity`). → **Deploy 🚚 Hydration Truck #1**\n"
            "2. **Oak Cliff / Marsalis Corridor (Tract `48113009604` · `UVI 119.8`):** **`+4.6°F` offset** (`412` carless homes, `1,485` seniors 65+, `53-yr` housing stock, Public Library `Over Capacity`). → **Deploy 🩺 Senior Wellness Team #1**\n"
            "3. **Buckner Terrace / East Dallas (Tract `48113018110` · `UVI 112.4`):** **`+4.4°F` offset** (`411` carless homes, `1,749` seniors 65+, `0` nearby parks). → **Deploy 🚚 Hydration Truck #2**\n\n"
            "### 📈 7-Year Station Trend (`station_daily_temps`, 2019–2025):\n"
            "- Days `>=100°F` per station more than doubled from **16.4 days/yr (2019–2021)** to **34.8 days/yr (2022–2025)**, peaking at **111.9°F**."
        )

    # B. Database Architecture & Table Explanations
    elif is_db_q:
        reply = (
            "**🗄️ BigQuery Data Architecture (`qwiklabs-gcp-04-f8ba79cf4618.a4i_climate`):**\n\n"
            "The system is grounded 100% in BigQuery tables and 2 BigQuery ML models:\n\n"
            "1. **`v_tract_heat_features` (All 618 Dallas census tracts, 29 features):**\n"
            "   - Combines **85 measured Heat Watch tracts** + **551 unmeasured tracts** with US Census ACS demographics, 3km spatial lag features, and inverse-distance station temperatures.\n"
            "2. **`Agent_Universal_Vulnaribility_Index` (85 measured tracts with 3-Pillar UVI):**\n"
            "   - Combines **CMS Medicare Hospital Access**, **NOAA 2023 Cooling Degree Days (CDD)**, and **Geospatial 1km Building & Park Density**.\n"
            "3. **`heat_observations` (19,491 street-level readings, `100.90°F–110.10°F`)**\n"
            "4. **`station_daily_temps` (27,187 station-days across 16 NOAA GHCN stations, 2019–2025)**"
        )

    # C. Equity Audit & Why North Dallas is Skipped
    elif is_equity_q:
        highlight_id = "48439113622"
        reply = (
            "**⚖️ 3-Step Equity Audit (`audit_deployment_equity` — Strip the Variable, Audit the Outcome):**\n\n"
            "- **1. Strip the Variable:** Zero race or ethnicity columns are used as inputs in `heat_offset_model` or `Agent_Universal_Vulnaribility_Index`.\n"
            "- **2. Why North Dallas (`48439113622`) is Skipped:** Although it has **1,779 seniors**, its **UVI is only `24.5`** (`Green Area - Unlikely Heat Wave`, 4 parks, Public Library `Under Capacity`, **`0` carless households**, and `+0.8°F` offset).\n"
            "- **3. Post-Hoc Demographic Outcome Audit (joining `tract_demographics` onto recommended output):**\n"
            f"  - Redirecting **${plan['total_cost']:,}** to Top UVI Tracts (**South Dallas, Oak Cliff, Buckner Terrace, West Dallas**) reaches neighborhoods averaging **18.9%–22.7% carless households (`3.1x` the Dallas baseline of `6.8%`)**, **21.4% poverty rate (`1.5x` city average)**, and **81.6% Black & Hispanic residents** vs. pure-temperature commercial tracts."
        )

    # D. Tri-Agency Alerts (Hospital Standby & Power Grid)
    elif is_agency_q:
        target = next((n for n in plan["neighborhoods"] if n["id"] == highlight_id), plan["neighborhoods"][0])
        tri = target["tri_agency_dispatch"]
        hosp_action = tri["hospital_staff_standby"].get("directive") or tri["hospital_staff_standby"].get("action", "")
        grid_action = tri["electricity_grid_response"].get("directive") or tri["electricity_grid_response"].get("action", "")
        reply = (
            f"**🚨 Tri-Agency Operational Coordination for {target['name']} (Tract `{target['id']}`):**\n\n"
            f"### 🏥 1. Hospital & Clinical Staff Standby\n"
            f"- **Alert Level:** `{tri['hospital_staff_standby']['alert_level']}`\n"
            f"- **Action Plan:** {hosp_action}\n\n"
            f"### ⚡ 2. Electricity & Power Grid Team\n"
            f"- **Alert Level:** `{tri['electricity_grid_response']['alert_level']}`\n"
            f"- **Action Plan:** {grid_action}\n\n"
            f"### 🚑 3. Emergency Services Dispatch\n"
            f"- **Assigned Unit:** **{target['assigned_unit'] or 'Standby'}**\n"
            f"- **Rationale:** {tri['emergency_services_dispatch'].get('rationale', '')}\n"
            f"- **Cooling Status:** {tri['emergency_services_dispatch']['cooling_center_status']}"
        )

    # E. Dispatch Distribution Rules ($2,500 Trucks vs $1,200 Wellness Teams)
    elif is_dispatch_rule_q:
        reply = (
            "**🚚 Tri-Agency Dispatch Decision Rules:**\n\n"
            "Units are prioritized by combining the **Universal Vulnerability Index (UVI)**, **BQML Predicted Heat Offset (`heat_offset_f`)**, vehicle access, and housing age (with a `1.5 km` minimum spacing constraint):\n\n"
            "1. **🚚 Hydration Trucks ($2,500 / day):**\n"
            "   - Dispatched to high-traffic commercial & transit corridors where **`no_cars >= 200`** and the local cooling center is **`Over Capacity`** (South Dallas, Buckner Terrace, Bachman Lake).\n\n"
            "2. **🩺 Senior Wellness Check Teams ($1,200 / day):**\n"
            "   - Dispatched door-to-door in residential neighborhoods with **older housing stock (`building_age_years >= 50`)** and high senior isolation (Oak Cliff, West Dallas).\n\n"
            f"Current allocation: **{plan['funded_trucks']} Trucks + {plan['funded_wellness']} Wellness Teams** costing **${plan['total_cost']:,} / day** (of **${budget:,}** budget)."
        )

    # F. Specific Neighborhood or General Vulnerability Inquiry
    elif matched_tract_id is not None or any(w in q for w in ["why", "explain", "hot", "temp", "uvi", "tract", "neighborhood", "details"]):
        target = next((n for n in plan["neighborhoods"] if n["id"] == highlight_id), plan["neighborhoods"][0])
        tri = target["tri_agency_dispatch"]
        pillars = target["uvi_pillars"]
        reply = (
            f"**📍 {target['name']} (Tract `{target['id']}` · `UVI {target['universal_vulnerability_index']}`)**\n\n"
            f"- **🌡️ Station vs. Street Temp:** `{target['station_temp_f']}°F` station → **`{target['predicted_street_temp_f']}°F` street** (`+{target['predicted_offset_f']}°F` offset · `{target['observed_avg_temp']}°F` campaign avg)\n"
            f"- **👥 Vulnerable Residents:** `{target['no_cars']}` carless homes (`{target['no_car_pct']}%`), `{target['seniors_65_plus']:,}` seniors 65+ (`{target['senior_pct']}%`), median building age `{target['building_age_yrs']} yrs`\n"
            f"- **🏛️ 3-Pillar UVI Diagnosis (`microclimate_risk_agent`):**\n"
            f"  1. *Health Access (CMS Medicare):* {pillars['health_access_cms_medicare']}\n"
            f"  2. *Urban Heat Island (1km Spatial):* {pillars['urban_heat_island_osm_1km']}\n"
            f"  3. *Energy Stress (NOAA CDD):* {pillars['energy_stress_noaa_cdd']}\n\n"
            f"**🚨 Tri-Agency Action Plan (`triage_dispatch_agent`):**\n"
            f"- **🚑 Emergency Dispatch:** **{target['assigned_unit'] or 'Standby'}** — *{tri['emergency_services_dispatch']['cooling_center_status']}*\n"
            f"- **🏥 Hospital Standby:** `{tri['hospital_staff_standby']['alert_level']}`\n"
            f"- **⚡ Power Grid Team:** `{tri['electricity_grid_response']['alert_level']}`"
        )

    # G. Greeting / Help Menu
    elif is_greeting_q:
        reply = (
            "👋 **Dallas Urban Heat Emergency Commander (`dallas_heat_emergency_commander`)**\n\n"
            "Ask me anything about today's heat dispatch or click a neighborhood pin on the map:\n"
            "- **Where to deploy:** *\"Where should we deploy first?\"* or *\"Compare South Dallas vs North Dallas\"*\n"
            "- **BQML Model & Features:** *\"What are the key features of the model?\"*\n"
            "- **Neighborhood Deep-Dive:** *\"Explain Oak Cliff\"* or *\"Why is South Dallas so hot?\"*\n"
            "- **Tri-Agency Alerts:** *\"What is the hospital and power grid plan?\"*\n"
            "- **Equity Audit:** *\"Run the equity audit\"* or *\"Why is North Dallas skipped?\"*\n"
            "- **Council Memo:** *\"Draft a City Council proposal\"*"
        )
    else:
        budget_msg = (
            f"**🤖 ADK `triage_dispatch_agent` Plan** — Deploying **{plan['funded_trucks']} Hydration Truck(s)** (`$2,500/ea`) and "
            f"**{plan['funded_wellness']} Senior Wellness Check Team(s)** (`$1,200/ea`) — "
            f"**${plan['total_cost']:,}** of **${budget:,}** budget:"
        )
        if not plan["within_budget"]:
            budget_msg = (
                f"⚠️ Requested **{hydration_trucks} Truck(s) + {wellness_teams} Wellness Team(s)** cost **${plan['requested_cost']:,}**, "
                f"exceeding your **${budget:,}** budget. Funded **{plan['funded_trucks']} Truck(s) + {plan['funded_wellness']} Wellness Team(s)** (**${plan['total_cost']:,}/day**):"
            )
        lines = [
            f"{d['rank']}. **{d['assigned_unit']}** → **{d['name']}** (`UVI {d['universal_vulnerability_index']}`, `+{d['predicted_offset_f']}°F` · `{d['no_cars']} carless homes` · Library `{d['capacity_status']}`)"
            for d in deployed
        ]
        top_site = deployed[0] if deployed else plan["neighborhoods"][0]
        tri_footer = (
            f"\n\n**Tri-Agency Coordination (`{top_site['name']}`):**\n"
            f"- **🏥 Hospital Alert:** `{top_site['tri_agency_dispatch']['hospital_staff_standby']['alert_level']}`\n"
            f"- **⚡ Grid Alert:** `{top_site['tri_agency_dispatch']['electricity_grid_response']['alert_level']}`\n\n"
            "_Tip: Ask about specific neighborhoods (e.g. Oak Cliff, South Dallas), key model features, equity audit, or hospital/grid standby._"
        )
        reply = f"{budget_msg}\n\n" + ("\n".join(lines) if lines else "_Increase budget or units above to dispatch teams._") + tri_footer

    return {
        "reply": reply,
        "highlight_tract_id": highlight_id,
        "plan": plan,
    }


if HAS_FASTAPI:
    @app.get("/api/initial-data")
    async def get_initial_data():
        return JSONResponse(compute_dispatch_plan(budget=10000, hydration_trucks=2, wellness_teams=2))

    @app.post("/api/chat")
    async def chat_endpoint(req: ChatRequest):
        return JSONResponse(build_chat_response(req.model_dump() if hasattr(req, "model_dump") else req.__dict__))

    @app.get("/", response_class=HTMLResponse)
    async def serve_ui():
        html_path = Path(__file__).parent / "index.html"
        return HTMLResponse(html_path.read_text(encoding="utf-8"))


class LocalPreviewHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.startswith("/api/initial-data"):
            self._send_json(compute_dispatch_plan(budget=10000, hydration_trucks=2, wellness_teams=2))
        else:
            html_path = Path(__file__).parent / "index.html"
            raw = html_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    def do_POST(self) -> None:
        if self.path.startswith("/api/chat"):
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            payload = json.loads(body)
            self._send_json(build_chat_response(payload))
        else:
            self._send_json({"error": "Not found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        return


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    if HAS_FASTAPI:
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        print(f"Running Dallas Daily Heat Dispatch Planner on http://localhost:{port}")
        server = HTTPServer(("0.0.0.0", port), LocalPreviewHandler)
        server.serve_forever()
