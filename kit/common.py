import json
import os
import re
import sys

from kit import ROOT


def load_env():
    f = ROOT / ".env"
    if not f.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(f, override=False)
    except ImportError:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.replace("export ", "").strip(), v.strip().strip('"'))


load_env()

from kit_core import domain as D  # noqa: E402


def project() -> str:
    p = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not p:
        sys.exit("GOOGLE_CLOUD_PROJECT not set. Run `python -m kit init` or edit .env")
    return p


def dataset() -> str:
    d = os.environ.get("BQ_DATASET")
    if not d:
        sys.exit("BQ_DATASET not set in .env")
    return d


def bq():
    from google.cloud import bigquery
    return bigquery.Client(project=project())


def run_sql(sql: str, params=None):
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(query_parameters=params or [])
    return list(bq().query(sql, job_config=cfg).result())


def render(text: str) -> str:
    """Substitute ${PROJECT_ID} and ${DATASET} in SQL text."""
    from string import Template
    return Template(text).safe_substitute(PROJECT_ID=project(), DATASET=dataset())


def snake(name: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip().lower()).strip("_")
    if not s or s[0].isdigit():
        s = "c_" + s
    return s


def print_rows(rows, limit=20):
    rows = [dict(r) for r in rows]
    if not rows:
        print("(no rows)")
        return
    cols = list(rows[0].keys())
    print(" | ".join(cols))
    for r in rows[:limit]:
        print(" | ".join(str(r[c])[:40] for c in cols))
    if len(rows) > limit:
        print(f"... {len(rows) - limit} more")


def ai_describe(table: str, columns, sample_rows, context: str, use_ai=True) -> dict:
    """Returns {'table_description': str, 'columns': {col: desc}}. Falls back to heuristics offline."""
    fallback = {"table_description": f"REVIEW: table {table}",
                "columns": {c: f"REVIEW: {t}; e.g. " + ", ".join(
                    str(r.get(c))[:20] for r in sample_rows[:3] if r.get(c) is not None) for c, t in columns}}
    if not use_ai:
        return fallback
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(vertexai=True, project=project(),
                              location=os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
        prompt = (
            "You document BigQuery tables so an AI agent can write correct SQL.\n"
            f"Project context: {context}\nTable: {table}\nColumns (name,type): {columns}\n"
            f"Sample rows: {json.dumps(sample_rows[:5], default=str)[:3500]}\n"
            "Return JSON: {\"table_description\": str, \"columns\": {column: description}}. "
            "Each description: meaning, units/range, what NULL means, join-key hints, and how it differs from "
            "similarly named columns. Be concise (<=25 words). Do not invent facts you cannot infer.")
        resp = client.models.generate_content(
            model=os.environ.get("MODEL", "gemini-3-flash-preview"), contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
        data = json.loads(resp.text)
        data.setdefault("columns", {})
        for c, _ in columns:
            data["columns"].setdefault(c, fallback["columns"][c])
        return data
    except Exception as e:
        print(f"(AI description unavailable: {e}; wrote REVIEW placeholders)")
        return fallback


def apply_descriptions(table: str, table_desc: str, col_desc: dict):
    from google.cloud import bigquery
    c = bq()
    t = c.get_table(f"{project()}.{dataset()}.{table}")
    t.description = table_desc or t.description
    if t.table_type == "TABLE":
        t.schema = [bigquery.SchemaField(f.name, f.field_type, f.mode, description=col_desc.get(f.name, f.description),
                                         fields=f.fields) for f in t.schema]
        c.update_table(t, ["description", "schema"])
    else:
        c.update_table(t, ["description"])


def document_table(ops, table: str, sample_rows, use_ai=True):
    """Describe a table/view with AI, store in generated.yaml (never over hand-written entries), push to BigQuery."""
    t = bq().get_table(f"{project()}.{dataset()}.{table}")
    cols = [(f.name, f.field_type) for f in t.schema]
    dom = D.load_domain()
    ctx = f"{dom.get('mission', '')} ({dom.get('persona', '')})"
    desc = ai_describe(table, cols, sample_rows, ctx, use_ai)
    hand = D._read(D.domain_file()).get("tables", {}).get(table, {})
    hand_cols = set((hand.get("columns") or {}).keys())
    new_cols = {c: d for c, d in desc["columns"].items() if c not in hand_cols}
    patch = {"tables": {table: {"columns": new_cols}}}
    if not hand.get("description"):
        patch["tables"][table]["description"] = desc.get("table_description", "")
    path = D.save_overlay(patch)
    apply_descriptions(table, hand.get("description") or desc.get("table_description", ""),
                       {**desc["columns"], **(hand.get("columns") or {})})
    ops.log(f"Documented {table}: {len(new_cols)} AI/placeholder column descriptions -> {path.name} and BigQuery")
