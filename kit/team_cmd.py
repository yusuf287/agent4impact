"""kit team-check | kit roles"""
from kit.common import D
from kit_core import teamspec

ROLE_NAMES_FILE = "kit_agent/roles.py"
TOOL_NAMES = ["bigquery", "predictions", "semantic_search", "live_api", "ec_alerts", "forecast", "open_data",
              "vision", "approval", "state", "exit_loop", "google_search", "maps", "viz"]


def _roles_and_schemas():
    """Import roles/schemas by file path so we don't import ADK."""
    import ast
    import importlib.util
    from kit import ROOT
    spec = importlib.util.spec_from_file_location("_k_roles", ROOT / "kit_agent" / "roles.py")
    roles = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(roles)
    # read SCHEMAS keys with ast so pydantic/ADK need not be installed
    tree = ast.parse((ROOT / "kit_agent" / "schemas.py").read_text(encoding="utf-8"))
    names = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SCHEMAS":
            names = {k.value: True for k in node.value.keys}
    return roles.ROLES, names


def problems() -> list:
    team = D.load_domain().get("team")
    if not team:
        return []
    roles, schemas = _roles_and_schemas()
    return teamspec.validate(team, roles, TOOL_NAMES, schemas)


def check(args):
    errs = problems()
    if not D.load_domain().get("team"):
        print("No team.yaml in the active domain (the default deep-dive pipeline will be used).")
        return
    print("team.yaml OK" if not errs else "PROBLEMS:\n - " + "\n - ".join(errs))
    raise SystemExit(1 if errs else 0)


def roles(args):
    r, _ = _roles_and_schemas()
    for k, v in r.items():
        print(f"{k:13} tools={v.get('tools', [])}  {v['description']}")
    print("\nTools available in team.yaml:", ", ".join(TOOL_NAMES))


def add_parsers(sub):
    sub.add_parser("team-check", help="validate team.yaml").set_defaults(fn=check)
    sub.add_parser("roles", help="list reusable agent roles and tools").set_defaults(fn=roles)
