"""Pure-Python BigQuery loader, validator, and setup.sql runner for Challenge 1 (Dallas).

Works anywhere Python + google-cloud-bigquery + Application Default Credentials are available
(Cloud Shell, Qwiklabs Remote Browser VM, or local machine after `gcloud auth application-default login`),
without requiring `bash` or the `bq` CLI.

Usage:
    python scripts/setup_dallas_bq.py [--city dallas] [--check-only] [--skip-load] [--skip-model]
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

SNAPSHOT_BUCKET = "gs://class-demo/a4i-2026/challenge-1-walkability"
TABLES = ("heat_observations", "station_daily_temps", "tract_demographics")
SETUP_SQL = ROOT / "domains" / "urban_heat" / "setup.sql"


def check_existing_state(client: bigquery.Client, project_id: str, dataset_id: str) -> dict:
    """Inspect whether `a4i_climate` and its tables/views/models have already been created in the project."""
    print(f"=== Checking existing BigQuery state in `{project_id}.{dataset_id}` ===")
    state = {"dataset_exists": False, "tables": {}, "models": [], "loaded_city": None}
    try:
        ds = client.get_dataset(f"{project_id}.{dataset_id}")
        state["dataset_exists"] = True
        print(f"  ✓ Dataset `{project_id}.{dataset_id}` EXISTS (location={ds.location}, created={ds.created})")
    except Exception:
        print(f"  ✗ Dataset `{project_id}.{dataset_id}` does NOT exist yet (nobody has run load.sh / setup yet).")
        return state

    for item in client.list_tables(f"{project_id}.{dataset_id}"):
        t_ref = f"{project_id}.{dataset_id}.{item.table_id}"
        tbl = client.get_table(t_ref)
        state["tables"][item.table_id] = {
            "type": tbl.table_type,
            "rows": tbl.num_rows,
            "modified": str(tbl.modified),
        }
        print(f"  • {item.table_id:<28} [{tbl.table_type:<5}] rows={str(tbl.num_rows):<8} modified={tbl.modified}")

    if "heat_observations" in state["tables"]:
        try:
            rows = list(
                client.query(
                    f"SELECT city, COUNT(*) AS row_count FROM `{project_id}.{dataset_id}.heat_observations` GROUP BY city"
                ).result()
            )
            if rows:
                cities_str = ", ".join(f"{r.city} ({r.row_count:,} rows)" for r in rows)
                state["loaded_city"] = rows[0].city
                print(f"  ✓ Loaded city in `heat_observations`: {cities_str}")
        except Exception as exc:
            print(f"  ! Could not query `heat_observations.city`: {exc}")

    try:
        models = list(client.list_models(f"{project_id}.{dataset_id}"))
        for m in models:
            state["models"].append(m.model_id)
            print(f"  • Model `{m.model_id}` EXISTS")
    except Exception:
        pass

    return state


def ensure_dataset(client: bigquery.Client, project_id: str, dataset_id: str) -> None:
    ds_ref = bigquery.Dataset(f"{project_id}.{dataset_id}")
    ds_ref.location = "US"
    client.create_dataset(ds_ref, exists_ok=True)
    print(f"[1/4] Dataset `{project_id}.{dataset_id}` ready (location=US).")


def load_parquet_tables(client: bigquery.Client, project_id: str, dataset_id: str, city: str) -> None:
    print(f"[2/4] Loading pre-staged Parquet tables for city='{city}' from {SNAPSHOT_BUCKET}/{city}/ ...")
    for table in TABLES:
        uri = f"{SNAPSHOT_BUCKET}/{city}/{table}/*.parquet"
        table_id = f"{project_id}.{dataset_id}.{table}"
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        load_job = client.load_table_from_uri(uri, table_id, job_config=job_config)
        load_job.result()
        dest = client.get_table(table_id)
        print(f"  ✓ {table:<22} -> {dest.num_rows:>8,} rows loaded")


def run_validation_checks(client: bigquery.Client, project_id: str, dataset_id: str) -> None:
    print("[3/4] Running Challenge 1 data validation checks ...")
    sql = f"""
    SELECT
      (SELECT COUNT(*) FROM `{project_id}.{dataset_id}.heat_observations`) AS heat_obs_rows,
      (SELECT ROUND(MAX(temp_f) - MIN(temp_f), 2) FROM `{project_id}.{dataset_id}.heat_observations`) AS temp_spread_f,
      (SELECT ROUND(AVG(temp_f), 2) FROM `{project_id}.{dataset_id}.heat_observations`) AS city_avg_temp_f,
      (SELECT COUNT(*) FROM `{project_id}.{dataset_id}.station_daily_temps`) AS station_rows,
      (SELECT COUNT(DISTINCT station_id) FROM `{project_id}.{dataset_id}.station_daily_temps`) AS station_count,
      (SELECT COUNT(*) FROM `{project_id}.{dataset_id}.tract_demographics`) AS tract_rows,
      (SELECT COUNTIF(LENGTH(geo_id) != 11) FROM `{project_id}.{dataset_id}.tract_demographics`) AS bad_geoid_len
    """
    row = list(client.query(sql).result())[0]
    print(
        f"  ✓ heat_observations : {row.heat_obs_rows:,} rows | city mean {row.city_avg_temp_f}°F | spread {row.temp_spread_f}°F\n"
        f"  ✓ station_daily_temps: {row.station_rows:,} rows across {row.station_count} GHCN stations\n"
        f"  ✓ tract_demographics : {row.tract_rows:,} tracts | bad geo_id length count = {row.bad_geoid_len}"
    )


def run_setup_sql(client: bigquery.Client, project_id: str, dataset_id: str, skip_model: bool) -> None:
    print(f"[4/4] Running {SETUP_SQL.relative_to(ROOT)} ...")
    raw = SETUP_SQL.read_text(encoding="utf-8").replace("`a4i_climate.", f"`{project_id}.{dataset_id}.")
    for stmt in [s.strip() for s in raw.split(";") if s.strip()]:
        if skip_model and ("CREATE OR REPLACE MODEL" in stmt or "ML.EVALUATE" in stmt):
            continue
        res = list(client.query(stmt).result())
        if res and not stmt.upper().startswith("CREATE"):
            print("  →", [dict(r) for r in res])
    print("  ✓ setup.sql complete.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Setup Dallas Urban Heat BigQuery dataset, views, and BQML model.")
    ap.add_argument("--city", default="dallas", help="City slug (default: dallas)")
    ap.add_argument("--check-only", action="store_true", help="Only check whether someone already loaded data/views/models")
    ap.add_argument("--skip-load", action="store_true", help="Skip loading Parquet files if already loaded")
    ap.add_argument("--skip-model", action="store_true", help="Skip training BQML model")
    args = ap.parse_args()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    dataset_id = os.environ.get("BQ_DATASET", "a4i_climate").strip()
    if not project_id:
        raise SystemExit("ERROR: GOOGLE_CLOUD_PROJECT is not set in .env or environment.")

    client = bigquery.Client(project=project_id)
    state = check_existing_state(client, project_id, dataset_id)
    if args.check_only:
        return

    ensure_dataset(client, project_id, dataset_id)
    if not args.skip_load:
        if (
            state.get("loaded_city")
            and state["loaded_city"].lower() == args.city.lower()
            and all(t in state["tables"] for t in TABLES)
        ):
            print(f"[2/4] All 3 base tables for '{state['loaded_city']}' are already loaded — skipping Parquet reload.")
        else:
            load_parquet_tables(client, project_id, dataset_id, args.city)
    run_validation_checks(client, project_id, dataset_id)
    run_setup_sql(client, project_id, dataset_id, args.skip_model)
    print("\nAll Done! Run `python -m kit doctor --llm` and `python -m kit rehearse` next.")


if __name__ == "__main__":
    main()
