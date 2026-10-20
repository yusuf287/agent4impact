"""Live-data tools (the MLB Stats API pattern). Each docstring's FIRST SENTENCE is what the
agent routes on — keep it precise. Copy a function to add a new API."""
from urllib.parse import urlparse

import requests

from ..config import DOMAIN

_HEADERS = {"User-Agent": "a4i-agent-kit/1.0"}


def _get(url: str, params: dict | None = None) -> dict:
    try:
        r = requests.get(url, params=params, headers=_HEADERS, timeout=12)
        r.raise_for_status()
        return {"status": "success", "data": r.json()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def fetch_live_json(url: str) -> dict:
    """Fetch current data from an approved public JSON API (live state, not history).

    Use for "right now" questions on hosts allow-listed in domain.yaml (live_api.allowed_hosts).

    Args:
        url: full https URL including query string.

    Returns:
        dict with parsed JSON under 'data', or an error.
    """
    allowed = set(DOMAIN.get("live_api", {}).get("allowed_hosts", []))
    host = urlparse(url).hostname or ""
    if host not in allowed:
        return {"status": "error", "message": f"Host '{host}' not allowed. Allowed: {sorted(allowed)}"}
    return _get(url)


def get_ec_alerts(bbox: str = "-79.7,43.5,-79.0,43.9", limit: int = 20) -> dict:
    """Get current Environment Canada weather alerts (heat, storm, wildfire smoke) inside a bounding box.

    Use for live severe-weather or heat-warning status in Canada. Default box covers Toronto.

    Args:
        bbox: "min_lon,min_lat,max_lon,max_lat".
        limit: max alerts to return.

    Returns:
        dict with alert feature properties (event, headline, onset/expiry, area).
    """
    res = _get("https://api.weather.gc.ca/collections/weather-alerts/items",
               {"f": "json", "bbox": bbox, "limit": limit})
    if res["status"] != "success":
        return res
    feats = res["data"].get("features", [])
    return {"status": "success", "count": len(feats), "alerts": [f.get("properties", {}) for f in feats]}


def get_forecast(latitude: float, longitude: float, days: int = 3) -> dict:
    """Get the daily weather forecast (max/min/feels-like temperature, rain) for a latitude/longitude.

    Use for tomorrow's or this week's conditions anywhere in the world.

    Args:
        latitude: decimal degrees.
        longitude: decimal degrees.
        days: forecast days (1-14).

    Returns:
        dict with daily arrays under 'data'.
    """
    res = _get("https://api.open-meteo.com/v1/forecast", {
        "latitude": latitude, "longitude": longitude, "timezone": "auto",
        "forecast_days": max(1, min(int(days), 14)),
        "daily": "temperature_2m_max,temperature_2m_min,apparent_temperature_max,precipitation_sum"})
    if res["status"] == "success":
        res["data"] = res["data"].get("daily", res["data"])
    return res


def search_open_data(query: str, rows: int = 5) -> dict:
    """Search the city open-data portal (CKAN) for datasets matching a keyword.

    Use to discover extra datasets; returns names and resource URLs the user can load with `kit add-data ckan:<name>`.

    Args:
        query: keywords, e.g. "cooling centres".
        rows: max datasets.

    Returns:
        dict with datasets (name, title, resources).
    """
    base = DOMAIN.get("open_data", {}).get("ckan_base", "https://ckan0.cf.opendata.inter.prod-toronto.ca")
    res = _get(f"{base}/api/3/action/package_search", {"q": query, "rows": max(1, min(int(rows), 10))})
    if res["status"] != "success":
        return res
    out = [{"name": p["name"], "title": p["title"],
            "resources": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url")}
                          for r in p.get("resources", [])[:4]]}
           for p in res["data"].get("result", {}).get("results", [])]
    return {"status": "success", "datasets": out}
