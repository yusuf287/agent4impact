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
