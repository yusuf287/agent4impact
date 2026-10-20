"""Loads the merged domain definition (domain.yaml + generated.yaml + team.yaml,
or the frozen copy when deployed). Everything domain-specific lives in YAML."""
import os

from .core.domain import KIT_ROOT, load_domain, models_of  # noqa: F401

DOMAIN: dict = load_domain()
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DATASET = os.environ.get("BQ_DATASET") or DOMAIN.get("_dataset", "")
MODEL_NAME = os.environ.get("MODEL", "gemini-3-flash-preview")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
