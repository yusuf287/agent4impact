"""Pre-built, tested BigQuery tools. The generic BigQueryToolset handles ad-hoc SQL; these
hold the fiddly queries (ML.PREDICT, ML.EXPLAIN_PREDICT, equity audit) the LLM should not improvise."""
from google.cloud import bigquery

from ..config import DATASET, DOMAIN, PROJECT_ID, models_of

# APPROXIMATE named Dallas areas (hand-drawn boxes, not official boundaries) -> bounding boxes (lat_min, lat_max, lon_min, lon_max) for "tool you built" spatial resolution
DALLAS_BBOX = (32.55, 33.05, -97.05, -96.50)
DALLAS_AREAS = {
    "south": (32.60, 32.76, -96.95, -96.65),
    "south side": (32.60, 32.76, -96.95, -96.65),
    "south dallas": (32.70, 32.78, -96.79, -96.71),
    "oak cliff": (32.65, 32.76, -96.90, -96.79),
    "west dallas": (32.75, 32.80, -96.92, -96.82),
    "west": (32.72, 32.84, -96.98, -96.82),
    "fair park": (32.76, 32.80, -96.78, -96.73),
    "pleasant grove": (32.68, 32.76, -96.71, -96.61),
    "east": (32.74, 32.86, -96.75, -96.60),
    "east dallas": (32.77, 32.85, -96.78, -96.68),
    "downtown": (32.76, 32.80, -96.82, -96.77),
    "central": (32.75, 32.83, -96.83, -96.75),
    "north": (32.85, 33.02, -96.88, -96.68),
    "north dallas": (32.85, 33.02, -96.88, -96.68),
}


def _client() -> bigquery.Client:
    return bigquery.Client(project=PROJECT_ID)


def list_models() -> dict:
    """List the trained prediction models available, with what each one predicts.

    Use before run_model_predictions when unsure which model to call.

    Returns:
        dict mapping model name to its description.
    """
    return {"models": {k: v.get("instructions", "") for k, v in models_of(DOMAIN).items()}}


def run_model_predictions(model_name: str = "", top_n: int = 10) -> dict:
    """Run a trained BigQuery ML model and return its top-N rows (predictions, risk scores, feature attributions, clusters or forecasts).

    Use whenever the user wants predictions, heat offsets, ML.EXPLAIN_PREDICT attributions, "which X is most likely...", clusters or a forecast.

    Args:
        model_name: name of the model (see list_models). Empty = the first/only model.
        top_n: how many rows to return, highest score first (1-100).

    Returns:
        dict with status, the SQL used, and rows (list of dicts).
    """
    models = models_of(DOMAIN)
    if not models:
        return {"status": "error", "message": "No models configured. Train one with `kit model`."}
    spec = models.get(model_name) or next(iter(models.values()))
    top_n = max(1, min(int(top_n), 100))
    sql = spec["predict_sql"].format(project=PROJECT_ID, dataset=DATASET, top_n=top_n)
    try:
        rows = _client().query(sql).result()
        return {"status": "success", "sql": sql, "rows": [dict(r) for r in rows]}
    except Exception as e:  # return errors so the agent can recover or explain
        return {"status": "error", "message": str(e), "sql": sql}


def explain_location_heat(area_or_direction: str = "", lat: float = 0.0, lon: float = 0.0, top_n: int = 5) -> dict:
    """Predict the street-level heat offset (degrees F above the Dallas city average) and unpack ML.EXPLAIN_PREDICT feature attributions for a specific location, neighborhood, or direction.

    Use whenever the user asks about a specific part of the city (e.g. "south side", "Oak Cliff", "West Dallas", "Downtown"),
    a census tract ID, or coordinates, or asks WHY a site is hotter than surrounding blocks and what placement recommendation applies.

    Args:
        area_or_direction: neighborhood name, cardinal direction (e.g. "south side", "oak cliff", "west dallas", "fair park", "downtown"), or 11-digit tract geo_id.
        lat: optional latitude in decimal degrees (e.g. 32.7767).
        lon: optional longitude in decimal degrees (e.g. -96.7970).
        top_n: number of candidate tracts to return (1-25).

    Returns:
        dict with status, spatial filter applied, ML.EXPLAIN_PREDICT predictions with human-readable feature attributions,
        7-year station heat frequency context, and placement recommendation notes.
    """
    top_n = max(1, min(int(top_n), 25))
    q = (area_or_direction or "").strip().lower()

    # Guardrail: refuse other cities explicitly
    other_cities = ["phoenix", "houston", "chicago", "seattle", "atlanta", "new york", "brooklyn", "manhattan",
                    "los angeles", "miami", "boston", "austin", "san antonio", "denver", "toronto"]
    for oc in other_cities:
        if oc in q:
            note = ("Phoenix is not in the NOAA Heat Watch dataset at all." if oc == "phoenix"
                    else f"{oc.title()} is a separate NOAA Heat Watch campaign not loaded in this Dallas workspace.")
            return {
                "status": "out_of_coverage",
                "message": f"Cannot predict street-level heat offset for {oc.title()}. {note} "
                           f"This planning assistant is calibrated strictly for the City of Dallas (`{PROJECT_ID}.{DATASET}`).",
            }

    lat_min, lat_max, lon_min, lon_max = DALLAS_BBOX
    if (lat != 0.0 or lon != 0.0) and not (lat_min - 0.2 <= lat <= lat_max + 0.2 and lon_min - 0.2 <= lon <= lon_max + 0.2):
        return {
            "status": "out_of_coverage",
            "message": f"Coordinates ({lat}, {lon}) lie outside the City of Dallas campaign footprint "
                       f"({lat_min}..{lat_max} N, {lon_min}..{lon_max} E). Refusing to extrapolate.",
        }

    where_clause = "total_pop > 300"
    filter_desc = "Dallas citywide (all populated tracts)"
    if q.isdigit() and len(q) >= 9:
        geo_id = q.zfill(11)
        where_clause = f"geo_id = '{geo_id}'"
        filter_desc = f"Census tract geo_id = {geo_id}"
    elif lat != 0.0 and lon != 0.0:
        where_clause = (f"ST_DISTANCE(ST_GEOGPOINT(tract_lon, tract_lat), ST_GEOGPOINT({float(lon)}, {float(lat)})) <= 4000")
        filter_desc = f"Within 4 km of ({lat:.4f}, {lon:.4f})"
    else:
        for name, box in sorted(DALLAS_AREAS.items(), key=lambda kv: -len(kv[0])):  # "south dallas" before "south"
            if name in q:
                b_lat_min, b_lat_max, b_lon_min, b_lon_max = box
                where_clause = (f"tract_lat BETWEEN {b_lat_min} AND {b_lat_max} "
                                f"AND tract_lon BETWEEN {b_lon_min} AND {b_lon_max} AND total_pop > 300")
                filter_desc = f"Dallas area '{name}' bounding box ({b_lat_min}..{b_lat_max} N, {b_lon_min}..{b_lon_max} E)"
                break

    sql = f"""
    SELECT
      geo_id,
      ROUND(tract_lat, 4) AS tract_lat,
      ROUND(tract_lon, 4) AS tract_lon,
      is_measured,
      observation_count,
      ROUND(predicted_heat_offset_f, 2) AS predicted_heat_offset_f,
      ROUND(heat_offset_f, 2) AS actual_heat_offset_f,
      ROUND(city_avg_temp_f, 1) AS city_avg_temp_f,
      top_feature_attributions,
      CAST(total_pop AS INT64) AS total_pop,
      ROUND(median_age, 1) AS median_age,
      CAST(median_income AS INT64) AS median_income,
      ROUND(poverty_rate * 100, 1) AS poverty_pct,
      ROUND(no_vehicle_rate * 100, 1) AS no_vehicle_pct,
      ROUND(building_age_years, 0) AS building_age_years
    FROM ML.EXPLAIN_PREDICT(
      MODEL `{PROJECT_ID}.{DATASET}.heat_offset_model`,
      (SELECT * FROM `{PROJECT_ID}.{DATASET}.v_tract_heat_features` WHERE {where_clause}),
      STRUCT(4 AS top_k_features)
    )
    ORDER BY (predicted_heat_offset_f + (COALESCE(no_vehicle_rate, 0) * 10.0) + (COALESCE(poverty_rate, 0) * 5.0)) DESC
    LIMIT {top_n}
    """

    freq_sql = f"""
    SELECT
      COUNT(DISTINCT year) AS years_analyzed,
      ROUND(AVG(days_95f_plus), 1) AS avg_days_95f_plus_per_year,
      ROUND(AVG(days_100f_plus), 1) AS avg_days_100f_plus_per_year,
      MAX(peak_temp_f) AS seven_year_peak_temp_f
    FROM `{PROJECT_ID}.{DATASET}.v_station_heat_frequency`
    """

    try:
        client = _client()
        raw_rows = list(client.query(sql).result())
        if not raw_rows and where_clause != "total_pop > 300":
            # Fallback if bounding box was too tight
            sql = sql.replace(where_clause, "total_pop > 300")
            filter_desc += " (fallback to citywide top tracts — no populated tracts inside initial box)"
            raw_rows = list(client.query(sql).result())

        candidates = []
        for r in raw_rows:
            d = dict(r)
            attrs = d.pop("top_feature_attributions", None) or []
            parts = []
            for a in attrs:
                feat = a.get("feature", "unknown") if isinstance(a, dict) else getattr(a, "feature", "unknown")
                val = a.get("attribution", 0.0) if isinstance(a, dict) else getattr(a, "attribution", 0.0)
                parts.append(f"{feat} ({val:+.2f} F)")
            d["attribution_sentence"] = (
                f"Predicted offset {d['predicted_heat_offset_f']:+.2f} F above the Dallas mean, driven by: "
                + (", ".join(parts) if parts else "baseline spatial features")
            )
            d["measurement_note"] = (
                f"Measured directly by {d['observation_count']} NOAA Heat Watch street readings"
                if d.get("is_measured")
                else "Unmeasured tract (0 Heat Watch readings) — offset predicted by BigQuery ML"
            )
            candidates.append(d)

        freq_info = {}
        try:
            freq_rows = list(client.query(freq_sql).result())
            if freq_rows:
                freq_info = dict(freq_rows[0])
        except Exception:
            pass

        return {
            "status": "success",
            "spatial_filter": filter_desc,
            "unit_note": "predicted_heat_offset_f is a temperature OFFSET (degrees F above/below the Dallas afternoon average), NOT an absolute temperature.",
            "station_frequency_7yr": freq_info,
            "candidates": candidates,
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "sql": sql}


def audit_recommendations_equity(tract_ids_csv: str = "", top_n: int = 10, ranking: str = "heat_only") -> dict:
    """Run the mandatory 3-step post-hoc Equity Audit comparing recommended Dallas census tracts against the Dallas citywide baseline.

    Use whenever the user asks "did we reach the neighborhoods that need this most?", requests an equity audit,
    or prepares a final Placement Recommendation or City Council proposal.

    Args:
        tract_ids_csv: optional comma-separated 11-digit Census tract geo_ids to audit. If empty, audits the top_n tracts from heat_offset_model.
        top_n: number of top model-recommended tracts to audit when tract_ids_csv is empty (default 10).
        ranking: when tract_ids_csv is empty, which ranking to audit: "heat_only" (pure predicted offset; the honest
            test of whether the MODEL finds vulnerable areas) or "blended" (offset + 10*no_vehicle_rate + 5*poverty_rate,
            the ranking explain_location_heat uses). Auditing "blended" is partly circular because it already weights poverty.

    Returns:
        dict comparing recommended tracts vs. Dallas citywide average across poverty rate, no-vehicle household rate,
        median income, median age, and predicted heat offset, with an explicit equity verdict.
    """
    top_n = max(1, min(int(top_n), 50))
    ids = [x.strip().zfill(11) for x in (tract_ids_csv or "").split(",") if x.strip().isdigit()]
    order_by = ("(predicted_heat_offset_f + (COALESCE(no_vehicle_rate, 0) * 10.0) + (COALESCE(poverty_rate, 0) * 5.0))"
                if ranking == "blended" else "predicted_heat_offset_f")

    if ids:
        in_list = ", ".join(f"'{i}'" for i in ids)
        rec_cte = f"""
        SELECT geo_id, predicted_heat_offset_f, total_pop, median_age, median_income, poverty_rate, no_vehicle_rate
        FROM ML.PREDICT(
          MODEL `{PROJECT_ID}.{DATASET}.heat_offset_model`,
          (SELECT * FROM `{PROJECT_ID}.{DATASET}.v_tract_heat_features` WHERE geo_id IN ({in_list}))
        )
        """
    else:
        rec_cte = f"""
        SELECT geo_id, predicted_heat_offset_f, total_pop, median_age, median_income, poverty_rate, no_vehicle_rate
        FROM ML.PREDICT(
          MODEL `{PROJECT_ID}.{DATASET}.heat_offset_model`,
          (SELECT * FROM `{PROJECT_ID}.{DATASET}.v_tract_heat_features` WHERE total_pop > 500)
        )
        ORDER BY {order_by} DESC
        LIMIT {top_n}
        """

    sql = f"""
    WITH recommended AS (
      {rec_cte}
    ),
    rec_summary AS (
      SELECT
        COUNT(*) AS rec_tract_count,
        CAST(SUM(total_pop) AS INT64) AS rec_total_pop,
        ROUND(AVG(predicted_heat_offset_f), 2) AS rec_avg_offset_f,
        ROUND(AVG(poverty_rate) * 100, 1) AS rec_poverty_pct,
        ROUND(AVG(no_vehicle_rate) * 100, 1) AS rec_no_vehicle_pct,
        CAST(ROUND(AVG(median_income), 0) AS INT64) AS rec_median_income_usd,
        ROUND(AVG(median_age), 1) AS rec_median_age,
        ARRAY_TO_STRING(ARRAY_AGG(geo_id), ', ') AS audited_geo_ids
      FROM recommended
    ),
    city_summary AS (
      SELECT
        COUNT(*) AS city_tract_count,
        CAST(SUM(total_pop) AS INT64) AS city_total_pop,
        ROUND(AVG(poverty_rate) * 100, 1) AS city_poverty_pct,
        ROUND(AVG(no_vehicle_rate) * 100, 1) AS city_no_vehicle_pct,
        CAST(ROUND(AVG(median_income), 0) AS INT64) AS city_median_income_usd,
        ROUND(AVG(median_age), 1) AS city_median_age
      FROM `{PROJECT_ID}.{DATASET}.tract_demographics`
      WHERE total_pop > 0
    )
    SELECT
      r.*,
      c.*,
      ROUND(r.rec_poverty_pct - c.city_poverty_pct, 1) AS poverty_delta_pct_pts,
      ROUND(r.rec_no_vehicle_pct - c.city_no_vehicle_pct, 1) AS no_vehicle_delta_pct_pts,
      (r.rec_median_income_usd - c.city_median_income_usd) AS income_delta_usd,
      ROUND(r.rec_median_age - c.city_median_age, 1) AS age_delta_years
    FROM rec_summary AS r
    CROSS JOIN city_summary AS c
    """
    try:
        rows = list(_client().query(sql).result())
        if not rows:
            return {"status": "error", "message": "No tracts returned for equity audit."}
        res = dict(rows[0])
        aligned = ((res.get("poverty_delta_pct_pts") or 0) > 0 and (res.get("no_vehicle_delta_pct_pts") or 0) > 0)
        res["equity_verdict"] = (
            "EQUITY_ALIGNED: Recommended sites prioritize neighborhoods with higher poverty and lower vehicle access than the Dallas average."
            if aligned else
            "NEEDS_REBALANCING: Recommended sites skew toward higher-income or higher-vehicle-access tracts; weight no_vehicle_rate and poverty_rate higher."
        )
        res["methodology_note"] = (
            "Race and ethnicity columns were stripped from model training inputs because physical built environment drives heat islands; "
            "this post-hoc outcome audit verifies that recommendations actually reach vulnerable communities."
        )
        res["ranking_audited"] = "explicit tract list" if ids else ranking
        return {"status": "success", "audit": res, "sql": sql}
    except Exception as e:
        return {"status": "error", "message": str(e), "sql": sql}
