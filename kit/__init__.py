"""`kit` — plug-in CLI.  Run:  python -m kit <command> -h

Loads kit_agent/core as 'kit_core' WITHOUT importing kit_agent/__init__ (which pulls in ADK),
so data/model commands work even before the agent is runnable."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_core():
    if "kit_core" in sys.modules:
        return
    d = ROOT / "kit_agent" / "core"
    spec = importlib.util.spec_from_file_location("kit_core", d / "__init__.py",
                                                  submodule_search_locations=[str(d)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["kit_core"] = mod
    spec.loader.exec_module(mod)


_load_core()
