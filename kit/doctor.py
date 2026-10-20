"""kit doctor — run at 8 AM on your laptop. Every line is OK / FAIL with the fix."""
import importlib
import os
import shutil
import sys

from kit.common import D, dataset, project  # noqa: F401
from kit_core.ops import Ops


def run(args):
    ops = Ops("doctor")
    bad = []

    def check(label, fn, fix=""):
        try:
            detail = fn()
            ops.log(f"OK   {label}" + (f" — {detail}" if detail else ""))
        except BaseException as e:  # SystemExit too
            msg = str(e)[:160]
            ops.log(f"FAIL {label}: {msg}" + (f"\n       fix: {fix}" if fix else ""))
            bad.append(label)

    def py():
        assert sys.version_info >= (3, 10), sys.version
        return sys.version.split()[0]
    check("Python >= 3.10", py, "install Python 3.11")

    for mod, pipname in [("google.adk", "google-adk"), ("google.cloud.bigquery", "google-cloud-bigquery"),
                         ("yaml", "pyyaml"), ("pandas", "pandas"), ("pyarrow", "pyarrow"), ("requests", "requests")]:
        check(f"import {mod}", lambda m=mod: getattr(importlib.import_module(m), "__version__", ""),
              f"pip install {pipname}")

    check("adk CLI on PATH", lambda: shutil.which("adk") or (_ for _ in ()).throw(RuntimeError("not found")),
          "activate venv / pip install google-adk")
    check("gcloud on PATH", lambda: shutil.which("gcloud") or (_ for _ in ()).throw(RuntimeError("not found")),
          "install Google Cloud SDK, then `gcloud auth login`")
    check("GOOGLE_CLOUD_PROJECT set", project, "edit .env or `python -m kit init`")
    check("BQ_DATASET set", dataset, "edit .env")

    def adc():
        import google.auth
        _, pid = google.auth.default()
        return f"ADC ok (project hint {pid})"
    check("Application Default Credentials", adc, "gcloud auth application-default login")

    def bq_ok():
        from kit.common import run_sql
        run_sql("SELECT 1")
        from kit.common import bq
        try:
            bq().get_dataset(f"{project()}.{dataset()}")
        except Exception:
            raise RuntimeError(f"dataset {dataset()} missing -> python -m kit init")
        return "query + dataset ok"
    check("BigQuery access", bq_ok, "check project, ADC, BigQuery API enabled")

    if args.llm:
        def llm():
            from google import genai
            c = genai.Client(vertexai=True, project=project(),
                             location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
            r = c.models.generate_content(model=os.environ.get("MODEL", "gemini-3-flash-preview"), contents="Say OK")
            return r.text.strip()[:20]
        check("Gemini call (Vertex)", llm, "enable aiplatform API; check MODEL name and GOOGLE_CLOUD_LOCATION=global")

    def domain():
        d = D.load_domain()
        for k in ("agent_name", "description", "persona", "mission", "audience"):
            assert d.get(k) and "REPLACE" not in str(d[k]), f"domain.yaml: '{k}' missing/REPLACE"
        return f"{d['agent_name']}: {len(d.get('tables', {}))} tables, {len(D.models_of(d))} models"
    check("domain.yaml complete", domain, "fill domains/<x>/domain.yaml")

    def team():
        from kit.team_cmd import problems
        errs = problems()
        assert not errs, "; ".join(errs)
        return "team.yaml valid" if D.load_domain().get("team") else "no team.yaml (default pipeline)"
    check("team.yaml valid", team, "python -m kit team-check")

    check("no stale frozen domain", lambda: (not D.FROZEN.exists()) or (_ for _ in ()).throw(
        RuntimeError("kit_agent/_frozen_domain.yaml exists and shadows your YAML edits")), f"delete {D.FROZEN}")

    ops.log("ALL GOOD" if not bad else f"{len(bad)} problem(s): {bad}")
    sys.exit(1 if bad else 0)


def add_parser(sub):
    p = sub.add_parser("doctor", help="preflight check of laptop/cloud/domain setup")
    p.add_argument("--llm", action="store_true", help="also test a Gemini call")
    p.set_defaults(fn=run)
