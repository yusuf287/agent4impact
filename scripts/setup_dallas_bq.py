"""Pure-Python BigQuery loader, validator, view builder, and BQML model trainer for Challenge 1 (Dallas).

Works anywhere Python + google-cloud-bigquery + Application Default Credentials are available
(Cloud Shell, Qwiklabs Remote Browser VM, or local machine after `gcloud auth application-default login`),
without requiring `bash` or the `bq` CLI.

Usage:
    python scripts/setup_dallas_bq.py [--city dallas] [--skip-load] [--skip-model]
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


def ensure_dataset(client: bigquery.Client, project_id: str, dataset_id: str) -> None:
    ds_ref = bigquery.Dataset(f"{project_id}.{dataset_id}")
    ds_ref.location = "US"
    client.create_dataset(ds_ref, exists_ok=True)
    print(f"[1/5] Dataset `{project_id}.{dataset_id}` ready (location=US).")


def load_parquet_tables(client: bigquery.Client, project_id: str, dataset_id: str, city: str) -> None:
    print(f"[2/5] Loading pre-staged Parquet tables for city='{city}' from {SNAPSHOT_BUCKET}/{city}/ ...")
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
    print("[3/5] Running Challenge 1 data validation checks ...")
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


def create_views(client: bigquery.Client, project_id: str, dataset_id: str) -> None:
    print("[4/5] Creating analytical views `v_station_heat_frequency` and `v_tract_heat_features` ...")

    sql_station_view = f"""
    CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.v_station_heat_frequency` AS
    SELECT
      EXTRACT(YEAR FROM observation_date) AS year,
      station_id,
      station_name,
      COUNT(*) AS days_observed,
      COUNTIF(max_temp_f >= 95.0) AS days_95f_plus,
      COUNTIF(max_temp_f >= 100.0) AS days_100f_plus,
      COUNTIF(max_temp_f >= 105.0) AS days_105f_plus,
      ROUND(AVG(CASE WHEN EXTRACT(MONTH FROM observation_date) IN (6, 7, 8) THEN max_temp_f END), 1) AS avg_summer_max_temp_f,
      ROUND(MAX(max_temp_f), 1) AS peak_temp_f
    FROM `{project_id}.{dataset_id}.station_daily_temps`
    GROUP BY year, station_id, station_name
    ORDER BY year DESC, days_100f_plus DESC
    """
    client.query(sql_station_view).result()
    print("  ✓ View `v_station_heat_frequency` created.")

    sql_tract_view = f"""
    CREATE OR REPLACE VIEW `{project_id}.{dataset_id}.v_tract_heat_features` AS
    WITH city_baseline AS (
      SELECT
        AVG(temp_f) AS city_avg_temp_f,
        AVG(heat_index_f) AS city_avg_heat_index_f
      FROM `{project_id}.{dataset_id}.heat_observations`
    ),
    obs_matched_tract AS (
      SELECT
        o.temp_f,
        o.heat_index_f,
        o.humidity_pct,
        ARRAY_AGG(
          t.geo_id
          ORDER BY ST_DISTANCE(
            ST_GEOGPOINT(o.longitude, o.latitude),
            ST_GEOGPOINT(t.tract_lon, t.tract_lat)
          ) ASC
          LIMIT 1
        )[OFFSET(0)] AS nearest_geo_id
      FROM `{project_id}.{dataset_id}.heat_observations` AS o
      CROSS JOIN `{project_id}.{dataset_id}.tract_demographics` AS t
      WHERE ABS(o.latitude - t.tract_lat) <= 0.035
        AND ABS(o.longitude - t.tract_lon) <= 0.035
      GROUP BY o.longitude, o.latitude, o.temp_f, o.heat_index_f, o.humidity_pct
    ),
    tract_heat AS (
      SELECT
        nearest_geo_id AS geo_id,
        COUNT(*) AS observation_count,
        AVG(temp_f) AS avg_temp_f,
        MAX(temp_f) AS max_temp_f,
        AVG(heat_index_f) AS avg_heat_index_f,
        AVG(humidity_pct) AS avg_humidity_pct
      FROM obs_matched_tract
      GROUP BY nearest_geo_id
    )
    SELECT
      t.geo_id,
      t.tract_lat,
      t.tract_lon,
      COALESCE(h.observation_count, 0) AS observation_count,
      ROUND(h.avg_temp_f, 2) AS avg_temp_f,
      ROUND(h.max_temp_f, 2) AS max_temp_f,
      ROUND(b.city_avg_temp_f, 2) AS city_avg_temp_f,
      ROUND(h.avg_temp_f - b.city_avg_temp_f, 2) AS heat_offset_f,
      ROUND(h.avg_humidity_pct, 1) AS avg_humidity_pct,
      t.total_pop,
      t.median_age,
      t.median_income,
      t.housing_units,
      t.median_year_structure_built,
      CAST(2025 - COALESCE(NULLIF(t.median_year_structure_built, 0), 1980) AS FLOAT64) AS building_age_years,
      SAFE_DIVIDE(t.housing_units, NULLIF(t.total_pop, 0)) AS housing_density_proxy,
      t.no_cars,
      t.households,
      t.poverty_rate,
      t.no_vehicle_rate,
      (COALESCE(h.observation_count, 0) > 0) AS is_measured,
      (COALESCE(t.poverty_rate, 0) >= 0.20 OR COALESCE(t.no_vehicle_rate, 0) >= 0.10) AS is_high_vulnerability
    FROM `{project_id}.{dataset_id}.tract_demographics` AS t
    CROSS JOIN city_baseline AS b
    LEFT JOIN tract_heat AS h
      ON t.geo_id = h.geo_id
    WHERE t.total_pop > 0
    """
    client.query(sql_tract_view).result()
    print("  ✓ View `v_tract_heat_features` created.")


def train_and_verify_model(client: bigquery.Client, project_id: str, dataset_id: str) -> None:
    print("[5/5] Training BQML model `heat_offset_model` (LINEAR_REG on `heat_offset_f`, race excluded) ...")
    sql_train = f"""
    CREATE OR REPLACE MODEL `{project_id}.{dataset_id}.heat_offset_model`
    OPTIONS(
      model_type = 'LINEAR_REG',
      input_label_cols = ['heat_offset_f'],
      calculate_p_values = TRUE
    ) AS
    SELECT
      heat_offset_f,
      tract_lat,
      tract_lon,
      building_age_years,
      housing_density_proxy,
      housing_units,
      total_pop,
      median_income,
      poverty_rate,
      no_vehicle_rate,
      median_age
    FROM `{project_id}.{dataset_id}.v_tract_heat_features`
    WHERE is_measured = TRUE
      AND heat_offset_f IS NOT NULL
      AND total_pop > 100
    """
    client.query(sql_train).result()
    print("  ✓ Model `heat_offset_model` trained.")

    eval_rows = [
        dict(r)
        for r in client.query(
            f"SELECT * FROM ML.EVALUATE(MODEL `{project_id}.{dataset_id}.heat_offset_model`)"
        ).result()
    ]
    print(f"  ✓ ML.EVALUATE metrics: {eval_rows}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Setup Dallas Urban Heat BigQuery dataset, views, and BQML model.")
    ap.add_argument("--city", default="dallas", help="City slug (default: dallas)")
    ap.add_argument("--skip-load", action="store_true", help="Skip loading Parquet files if already loaded")
    ap.add_argument("--skip-model", action="store_true", help="Skip training BQML model")
    args = ap.parse_args()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    dataset_id = os.environ.get("BQ_DATASET", "a4i_climate").strip()
    if not project_id:
        raise SystemExit("ERROR: GOOGLE_CLOUD_PROJECT is not set in .env or environment.")

    client = bigquery.Client(project=project_id)
    ensure_dataset(client, project_id, dataset_id)
    if not args.skip_load:
        load_parquet_tables(client, project_id, dataset_id, args.city)
    run_validation_checks(client, project_id, dataset_id)
    create_views(client, project_id, dataset_id)
    if not args.skip_model:
        train_and_verify_model(client, project_id, dataset_id)
    print("\nAll Done! Run `python -m kit doctor --llm` and `python -m kit rehearse` next.")


if __name__ == "__main__":
    main()
