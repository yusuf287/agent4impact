"""kit deploy runtime|a2a   — freezes the active domain into kit_agent/, deploys, unfreezes.
kit web | kit ui | kit cli    — run locally."""
import os
import re
import shutil
import subprocess
import sys

import yaml

from kit import ROOT
from kit.common import D, project
from kit_core.ops import Ops

WIN = os.name == "nt"


def _sh(cmd, ops, capture=False):
    ops.log("RUN: " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=ROOT, shell=WIN, text=True, capture_output=capture)
    if capture:
        ops.log((r.stdout + r.stderr)[-1500:])
    return r


def deploy(args):
    ops = Ops("deploy")
    P, region = project(), os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    name = os.environ.get("AGENT_NAME", "kit-agent")
    dom = D.load_domain()
    dom["_dataset"] = os.environ.get("BQ_DATASET", dom.get("_dataset", ""))
    D.FROZEN.write_text(yaml.safe_dump(dom, sort_keys=False, allow_unicode=True), encoding="utf-8")
    ops.log(f"Froze domain into {D.FROZEN.name} (removed after deploy)")
    # ADK packages ONLY the agent folder and reads requirements.txt / .env from it (the
    # --requirements_file / --staging_bucket flags are deprecated and ignored), so stage them there.
    agent_dir = ROOT / "kit_agent"
    staged = []
    if (ROOT / "requirements.txt").exists() and not (agent_dir / "requirements.txt").exists():
        shutil.copy(ROOT / "requirements.txt", agent_dir / "requirements.txt")
        staged.append(agent_dir / "requirements.txt")
    stale = agent_dir / ".env"
    if stale.exists():  # a leftover kit_agent/.env would be used by ADK instead of ours
        ops.log("Found existing kit_agent/.env; renaming it to kit_agent/.env.bak so the clean one is used")
        stale.replace(agent_dir / ".env.bak")
    if (ROOT / ".env").exists():
        # Agent Runtime rejects env vars with empty values (400 "env[i].value: Required field is not set"),
        # so stage only KEY=value lines that have a value; drop comments and blanks.
        from dotenv import dotenv_values  # parse exactly like ADK does (quotes, comments, no-'=' lines -> None)
        vals = {k: v for k, v in dotenv_values(ROOT / ".env").items() if k and v not in (None, "") and str(v).strip()}
        keep = [f"{k}={v}" for k, v in vals.items()]
        dropped = [k for k, v in dotenv_values(ROOT / ".env").items() if k not in vals]
        if dropped:
            ops.log(f"Not deploying empty settings: {dropped}")
        (agent_dir / ".env").write_text("\n".join(keep) + "\n", encoding="utf-8")
        staged.append(agent_dir / ".env")
        ops.log(f"Staged .env for deploy with {len(keep)} non-empty variables")
    try:
        if args.mode == "runtime":
            pn = subprocess.run(["gcloud", "projects", "describe", P, "--format=value(projectNumber)"],
                                capture_output=True, text=True, shell=WIN).stdout.strip()
            cfg = agent_dir / ".agent_engine_config.json"
            cfg.write_text(f'{{"service_account": "{pn}-compute@developer.gserviceaccount.com"}}', encoding="utf-8")
            staged.append(cfg)
            r = _sh(["adk", "deploy", "agent_engine", f"--project={P}", f"--region={region}",
                     f"--display_name={name}", "--otel_to_cloud", "kit_agent"], ops, True)
            out = r.stdout + r.stderr
            failed = r.returncode != 0 or "Deploy failed" in out or "Failed to deploy" in out
            m = re.findall(r"projects/[^\s]*reasoningEngines/\d+", out)
            if failed:
                ops.log("DEPLOY FAILED (ADK already cleaned up the half-created instance). Read the error above.")
                sys.exit(1)
            if m:
                res = m[-1]
                (ROOT / "logs" / "last_runtime_resource.txt").write_text(res, encoding="utf-8")
                ops.log(f"Agent Runtime resource: {res}  (register it in Gemini Enterprise > Agents > Add agent)")
                ops.undo(f"python -c \"import vertexai;from vertexai import agent_engines as a;"
                         f"vertexai.init(project='{P}',location='{region}');a.get('{res}').delete(force=True)\"")
            print("NOTE: human-approval pauses are not supported on Agent Runtime sessions; demo approval locally "
                  "(kit ui / kit web).")
            sys.exit(r.returncode)
        else:
            r = _sh(["adk", "deploy", "cloud_run", "--project", P, "--region", region, "--service_name", name,
                     "--a2a", "--env", "GOOGLE_CLOUD_LOCATION=global", "kit_agent", "--", "--allow-unauthenticated"],
                    ops, True)
            ops.undo(f"gcloud run services delete {name} --region {region} --project {P} --quiet")
            sys.exit(r.returncode)
    finally:
        D.FROZEN.unlink(missing_ok=True)
        for f in staged:
            f.unlink(missing_ok=True)
        ops.log("Unfroze domain and removed staged deploy files")


def web(args):
    cmd = ["adk", "web", ".", "--allow_origins", "*", "--reload_agents"] + (["--port", str(args.port)] if args.port else [])
    sys.exit(subprocess.run(cmd, cwd=ROOT, shell=WIN).returncode)


def ui(args):
    sys.exit(subprocess.run([sys.executable, "-m", "uvicorn", "ui.server:app", "--port", str(args.port or 8080)],
                            cwd=ROOT).returncode)


def cli(args):
    sys.exit(subprocess.run(["adk", "run", "kit_agent"], cwd=ROOT, shell=WIN).returncode)


def add_parsers(sub):
    p = sub.add_parser("deploy", help="deploy to Agent Runtime or Cloud Run (A2A)")
    p.add_argument("mode", choices=["runtime", "a2a"])
    p.set_defaults(fn=deploy)
    p = sub.add_parser("web", help="adk web dev UI (trace + graph view)")
    p.add_argument("--port", type=int)
    p.set_defaults(fn=web)
    p = sub.add_parser("ui", help="demo UI with visible tool-call trace")
    p.add_argument("--port", type=int)
    p.set_defaults(fn=ui)
    sub.add_parser("cli", help="adk run chat in terminal").set_defaults(fn=cli)
