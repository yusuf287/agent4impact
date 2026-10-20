"""Model + retry config in one place. The labs warn about 429 RESOURCE_EXHAUSTED;
retries make demos survive quota blips."""
from google.genai import types

from .config import MODEL_NAME


def make_model():
    try:
        from google.adk.models import Gemini
        return Gemini(model=MODEL_NAME,
                      retry_options=types.HttpRetryOptions(initial_delay=1, attempts=6))
    except Exception:
        return MODEL_NAME  # plain string works everywhere


def shared_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(temperature=0.2)
