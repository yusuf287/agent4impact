"""kit new-domain <name>   copy domains/_template -> domains/<name> and point .env at it
kit use <name>          switch the active domain (+ BQ_DATASET)
kit init                create .env, enable APIs, create the dataset"""
import re
import shutil
import subprocess

from kit import ROOT
from kit.common import dataset, project
from kit_core.ops import Ops


def _set_env(key: str, val: str):
    f = ROOT / ".env"
    text = f.read_text(encoding="utf-8") if f.exists() else ""
    if re.search(rf"^{key}=", text, flags=re.M):
        text = re.sub(rf"^{key}=.*$", f"{key}={val}", text, flags=re.M)
    else:
        text += f"\n{key}={val}\n"
    f.write_text(text, encoding="utf-8")


def new_domain(args):
    ops = Ops("new-domain")
    dst = ROOT / "domains" / args.name
    if dst.exists():
        raise SystemExit(f"{dst} exists")
    shutil.copytree(ROOT / "domains" / "_template", dst)
    ops.undo(f"rm -rf '{dst}'")
    (dst / "data").mkdir(exist_ok=True)
    use(args)
    ops.log(f"Created domains/{args.name}. Edit domain.yaml (persona, mission, routing), then `kit add-data ...`")


def use(args):
    ops = Ops("use")
    name = args.name
    d = ROOT / "domains" / name / "domain.yaml"
    if not d.exists():
        raise SystemExit(f"{d} not found")
    _set_env("DOMAIN_FILE", f"domains/{name}/domain.yaml")
    _set_env("BQ_DATASET", args.dataset or re.sub(r"[^a-z0-9_]", "_", name.lower()))
    _set_env("AGENT_NAME", re.sub(r"[^a-z0-9-]", "-", name.lower()) + "-analyst")
    ops.log(f"Active domain -> {name} (restart adk web / terminals so env reloads)")


def init(args):
    ops = Ops("init")
    env = ROOT / ".env"
    if not env.exists():
        shutil.copy(ROOT / ".env.example", env)
        ops.undo(f"rm -f '{env}'")
        pid = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True,
                             shell=(subprocess.os.name == "nt")).stdout.strip()
        if pid:
            _set_env("GOOGLE_CLOUD_PROJECT", pid)
        ops.log(f"Created .env (project={pid or 'UNSET - edit .env'})")
    import os
    os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
    from kit import common  # reload env
    common.load_env()
    P = project()
    apis = ["aiplatform.googleapis.com", "bigquery.googleapis.com", "run.googleapis.com",
            "cloudbuild.googleapis.com", "storage.googleapis.com"]
    r = subprocess.run(["gcloud", "services", "enable", *apis, "--project", P], capture_output=True, text=True,
                       shell=(subprocess.os.name == "nt"))
    ops.log("APIs: " + ("enabled" if r.returncode == 0 else "WARN " + r.stderr.strip()[:200]))
    from google.cloud import bigquery
    c = bigquery.Client(project=P)
    ds = bigquery.Dataset(f"{P}.{dataset()}")
    ds.location = os.environ.get("BQ_LOCATION", "US")
    c.create_dataset(ds, exists_ok=True)
    ops.undo(f"bq --project_id={P} rm -r -f -d {P}:{dataset()}")
    ops.log(f"Dataset {dataset()} ready. Next: python -m kit doctor")


def add_parsers(sub):
    p = sub.add_parser("new-domain", help="scaffold domains/<name> from the template and activate it")
    p.add_argument("name")
    p.add_argument("--dataset")
    p.set_defaults(fn=new_domain)
    p = sub.add_parser("use", help="switch the active domain")
    p.add_argument("name")
    p.add_argument("--dataset")
    p.set_defaults(fn=use)
    p = sub.add_parser("init", help="create .env, enable APIs, create the BigQuery dataset")
    p.set_defaults(fn=init)
