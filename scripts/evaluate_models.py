"""Evaluate the old heat_offset_model vs the upgraded setup.sql model in BigQuery.

Usage (in Cloud Shell):
    python scripts/evaluate_models.py
"""
import os
import pathlib
import re
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-f8ba79cf4618")
DATASET = os.environ.get("BQ_DATASET", "a4i_climate")
client = bigquery.Client(project=PROJECT)


def run_query(sql: str):
    return list(client.query(sql).result())


def print_metrics(label: str, rows):
    if not rows:
        print(f"  {label}: no evaluation rows returned")
        return
    r = rows[0]
    mae = getattr(r, "mean_absolute_error", 0.0)
    rmse = getattr(r, "root_mean_squared_error", 0.0)
    r2 = getattr(r, "r2_score", 0.0)
    print(f"  {label:<34} | MAE: {mae:.3f} °F | RMSE: {rmse:.3f} °F | R²: {r2:.3f}")


def main():
    print(f"=== Evaluating Heat Offset Models in {PROJECT}.{DATASET} ===\n")

    # 1. Score the currently deployed model before touching anything
    print("1. Scoring Current Model (Before Upgrade)...")
    try:
        old_eval = run_query(f"SELECT * FROM ML.EVALUATE(MODEL `{PROJECT}.{DATASET}.heat_offset_model`)")
        print_metrics("BEFORE (9 basic features)", old_eval)
    except Exception as e:
        print(f"  Could not evaluate existing model: {e}")

    # 2. Run domains/urban_heat/setup.sql to upgrade v_tract_heat_features + heat_offset_model
    setup_path = pathlib.Path(__file__).resolve().parent.parent / "domains" / "urban_heat" / "setup.sql"
    setup_sql = setup_path.read_text(encoding="utf-8")
    stmts = [
        s.strip()
        for s in re.split(r";\s*\n", setup_sql)
        if s.strip() and not s.strip().startswith("--")
    ]

    print("\n2. Rebuilding v_tract_heat_features (polygon join + enriched features)...")
    client.query(stmts[0]).result()
    client.query(stmts[1]).result()

    print("3. Training Enriched heat_offset_model (13 features)...")
    client.query(stmts[2]).result()

    # 3. Score the newly trained enriched model
    new_eval = run_query(f"SELECT * FROM ML.EVALUATE(MODEL `{PROJECT}.{DATASET}.heat_offset_model`)")
    print("\n=== Hold-Out Evaluation Summary (20% Unseen Tracts) ===")
    if "old_eval" in locals() and old_eval:
        print_metrics("BEFORE (9 basic features)", old_eval)
    print_metrics("AFTER  (13 enriched features)", new_eval)

    # 4. Print Top Feature Weights
    print("\n=== Top Feature Weights in Enriched Model ===")
    weights = run_query(f"""
        SELECT processed_input, ROUND(weight, 4) AS raw_weight
        FROM ML.WEIGHTS(MODEL `{PROJECT}.{DATASET}.heat_offset_model`)
        WHERE processed_input != '__INTERCEPT__'
        ORDER BY ABS(weight) DESC
    """)
    for w in weights[:10]:
        print(f"  {w.processed_input:<25}: {w.raw_weight:+.4f}")

    # 5. Print Top 3 Residual Misses (for Judges' Rigor Check: "Where is your model most wrong?")
    print("\n=== Biggest Model Residuals (Honest Misses for Pitch/Q&A) ===")
    misses = run_query(f"""
        SELECT
          geo_id,
          ROUND(heat_offset_f, 2) AS actual_offset_f,
          ROUND(predicted_heat_offset_f, 2) AS predicted_offset_f,
          ROUND(heat_offset_f - predicted_heat_offset_f, 2) AS residual_f,
          ROUND(pop_density_sqkm, 0) AS pop_density_sqkm,
          ROUND(water_fraction, 3) AS water_fraction
        FROM ML.PREDICT(
          MODEL `{PROJECT}.{DATASET}.heat_offset_model`,
          (SELECT * FROM `{PROJECT}.{DATASET}.v_tract_heat_features` WHERE is_measured)
        )
        ORDER BY ABS(heat_offset_f - predicted_heat_offset_f) DESC
        LIMIT 4
    """)
    for m in misses:
        print(
            f"  Tract {m.geo_id}: Actual {m.actual_offset_f:+.2f}°F vs Pred {m.predicted_offset_f:+.2f}°F "
            f"(Error: {m.residual_f:+.2f}°F | PopDensity: {m.pop_density_sqkm}/km² | Water: {m.water_fraction})"
        )


if __name__ == "__main__":
    main()
