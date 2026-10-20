"""kit add-data <source> [--table name]

source: local file (csv/json/ndjson/parquet/xlsx/geojson) | https URL | ckan:<dataset-name>
Loads to BigQuery (autodetect, snake_case columns), AI-documents every column, registers undo."""
import io
import re
from pathlib import Path

from kit import ROOT
from kit.common import D, bq, dataset, document_table, project, snake
from kit_core.ops import Ops

DEFAULT_CKAN = "https://ckan0.cf.opendata.inter.prod-toronto.ca"


def _read_bytes(path_or_url: str) -> tuple[bytes, str]:
    if re.match(r"^https?://", path_or_url):
        import requests
        r = requests.get(path_or_url, timeout=120, headers={"User-Agent": "a4i-agent-kit/1.0"})
        r.raise_for_status()
        return r.content, path_or_url.split("?")[0].lower()
    p = Path(path_or_url)
    return p.read_bytes(), p.name.lower()


def _frame(data: bytes, name: str, args):
    import pandas as pd
    if name.endswith((".parquet", ".pq")):
        return pd.read_parquet(io.BytesIO(data))
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(data), sheet_name=args.sheet or 0)
    if name.endswith(".geojson") or (name.endswith(".json") and b'"FeatureCollection"' in data[:2000]):
        import json
        feats = json.loads(data)["features"]
        rows = []
        for f in feats:
            row = dict(f.get("properties") or {})
            g = f.get("geometry") or {}
            if g.get("type") == "Point":
                row["longitude"], row["latitude"] = g["coordinates"][:2]
            else:
                row["geometry_json"] = json.dumps(g)[:100000]
            rows.append(row)
        return pd.DataFrame(rows)
    if name.endswith(".ndjson") or name.endswith(".jsonl"):
        return pd.read_json(io.BytesIO(data), lines=True)
    if name.endswith(".json"):
        import json
        obj = json.loads(data)
        if isinstance(obj, dict):
            obj = next((v for v in obj.values() if isinstance(v, list)), [obj])
        return pd.json_normalize(obj)
    return pd.read_csv(io.BytesIO(data), encoding="utf-8-sig", low_memory=False, on_bad_lines="skip")


def _ckan(name: str, args):
    import requests
    base = (D.load_domain().get("open_data") or {}).get("ckan_base", DEFAULT_CKAN)
    pkg = requests.get(f"{base}/api/3/action/package_show", params={"id": name}, timeout=60).json()["result"]
    res = pkg["resources"]
    pick = None
    if args.resource is not None:
        pick = res[int(args.resource)] if str(args.resource).isdigit() else next(
            r for r in res if args.resource.lower() in (r.get("name") or "").lower())
    else:
        pick = next((r for r in res if r.get("datastore_active")), None) or next(
            (r for r in res if (r.get("format") or "").upper() in ("CSV", "JSON", "GEOJSON", "XLSX")), res[0])
    print(f"CKAN '{pkg['title']}' -> resource '{pick.get('name')}' ({pick.get('format')})")
    url = f"{base}/datastore/dump/{pick['id']}?format=csv" if pick.get("datastore_active") else pick["url"]
    data, nm = _read_bytes(url)
    if pick.get("datastore_active"):
        nm = "x.csv"
    return _frame(data, nm, args), snake(pkg["name"])


def run(args):
    ops = Ops("add-data")
    from google.cloud import bigquery
    src = args.source
    if src.startswith("ckan:"):
        df, default_name = _ckan(src[5:], args)
    else:
        data, nm = _read_bytes(src)
        df = _frame(data, nm, args)
        default_name = snake(Path(nm).stem)
    if args.limit:
        df = df.head(args.limit)
    df.columns = _unique([snake(c) for c in df.columns])
    table = snake(args.table or default_name)
    ops.log(f"Loaded source: {len(df)} rows x {len(df.columns)} cols -> table {table}")
    nulls = (df.isna().mean() * 100).round(1)
    bad = nulls[nulls > 50]
    if len(bad):
        ops.log("WARN >50% null columns: " + ", ".join(f"{c}={v}%" for c, v in bad.items()))

    cache = ROOT / "data_cache"
    cache.mkdir(exist_ok=True)
    df.to_csv(cache / f"{table}.csv", index=False)  # local copy = offline backup

    ref = f"{project()}.{dataset()}.{table}"
    cfg = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE", autodetect=True)
    client = bq()
    try:
        client.load_table_from_dataframe(df, ref, job_config=cfg).result()
    except Exception as e:  # mixed-type object columns: stringify and retry
        ops.log(f"Retrying with stringified object columns ({str(e)[:120]})")
        for c in df.select_dtypes(include="object").columns:
            df[c] = df[c].astype("string")
        client.load_table_from_dataframe(df, ref, job_config=cfg).result()
    ops.undo(f"bq --project_id={project()} rm -f -t {dataset()}.{table}")
    ops.log(f"Loaded {ref}")

    if not args.no_describe:
        document_table(ops, table, df.head(5).to_dict("records"), use_ai=not args.no_ai)
    print(f"\nNext: python -m kit sql --view v_{table} --query \"SELECT ... FROM \\`${{PROJECT_ID}}.${{DATASET}}.{table}\\`\"")


def _unique(cols):
    seen, out = {}, []
    for c in cols:
        n = seen.get(c, 0)
        out.append(c if n == 0 else f"{c}_{n}")
        seen[c] = n + 1
    return out


def add_parser(sub):
    p = sub.add_parser("add-data", help="Load a file/URL/CKAN dataset into BigQuery and auto-document it")
    p.add_argument("source", help="path | https URL | ckan:<dataset-name>")
    p.add_argument("--table", help="table name (default derived from source)")
    p.add_argument("--resource", help="CKAN resource index or name substring")
    p.add_argument("--sheet", help="Excel sheet name")
    p.add_argument("--limit", type=int, help="only first N rows (fast iteration)")
    p.add_argument("--no-describe", action="store_true")
    p.add_argument("--no-ai", action="store_true", help="skip Gemini; write REVIEW placeholders")
    p.set_defaults(fn=run)
