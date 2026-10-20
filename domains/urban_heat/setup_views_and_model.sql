-- =============================================================================
-- Challenge 1: Urban Heat Resilience (City of Dallas) — Views & BQML Model SQL
-- Dataset: ${PROJECT_ID}.${DATASET} (default: a4i_climate)
-- =============================================================================

-- 1. View: v_station_heat_frequency
--    Summarizes 7 years (2019-2025) of NOAA GHCN-Daily station observations
--    to answer "How often does Dallas cross 95 F / 100 F / 105 F, and is it getting worse?"
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.v_station_heat_frequency` AS
SELECT
  EXTRACT(YEAR FROM observation_date) AS year,
  station_id,
  station_name,
  COUNT(*) AS days_observed,
  COUNTIF(max_temp_f >= 95.0) AS days_95f_plus,
  COUNTIF(max_temp_f >= 100.0) AS days_100f_plus,
  COUNTIF(max_temp_f >= 105.0) AS days_105f_plus,
  ROUND(AVG(IF(EXTRACT(MONTH FROM observation_date) IN (6, 7, 8), max_temp_f, NULL)), 1) AS avg_summer_max_temp_f,
  ROUND(MAX(max_temp_f), 1) AS peak_temp_f
FROM `${PROJECT_ID}.${DATASET}.station_daily_temps`
GROUP BY year, station_id, station_name
ORDER BY year DESC, days_100f_plus DESC;


-- 2. View: v_tract_heat_features
--    Matches each street-level NOAA Heat Watch observation to its nearest Dallas census tract
--    (within 2.5 km) to compute the tract-level temperature offset (`heat_offset_f` = degrees F
--    above/below the Dallas campaign mean), while retaining unmeasured tracts (`is_measured = FALSE`)
--    so our BigQuery ML model can predict heat risk for neighborhoods volunteers never drove through.
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.v_tract_heat_features` AS
WITH city_baseline AS (
  SELECT
    AVG(temp_f) AS city_avg_temp_f
  FROM `${PROJECT_ID}.${DATASET}.heat_observations`
),
obs_nearest_tract AS (
  SELECT
    h.temp_f,
    h.heat_index_f,
    h.humidity_pct,
    ARRAY_AGG(t.geo_id ORDER BY ST_DISTANCE(
      ST_GEOGPOINT(h.longitude, h.latitude),
      ST_GEOGPOINT(t.tract_lon, t.tract_lat)
    ) LIMIT 1)[OFFSET(0)] AS nearest_geo_id,
    MIN(ST_DISTANCE(
      ST_GEOGPOINT(h.longitude, h.latitude),
      ST_GEOGPOINT(t.tract_lon, t.tract_lat)
    )) AS dist_m
  FROM `${PROJECT_ID}.${DATASET}.heat_observations` AS h
  CROSS JOIN `${PROJECT_ID}.${DATASET}.tract_demographics` AS t
  WHERE t.tract_lat IS NOT NULL AND t.tract_lon IS NOT NULL
  GROUP BY h.longitude, h.latitude, h.temp_f, h.heat_index_f, h.humidity_pct
),
tract_heat_agg AS (
  SELECT
    nearest_geo_id AS geo_id,
    COUNT(*) AS observation_count,
    AVG(temp_f) AS avg_temp_f,
    MAX(temp_f) AS max_temp_f,
    AVG(humidity_pct) AS avg_humidity_pct
  FROM obs_nearest_tract
  WHERE dist_m <= 2500
  GROUP BY nearest_geo_id
)
SELECT
  t.geo_id,
  t.tract_lat,
  t.tract_lon,
  COALESCE(a.observation_count, 0) AS observation_count,
  ROUND(a.avg_temp_f, 2) AS avg_temp_f,
  ROUND(a.max_temp_f, 2) AS max_temp_f,
  ROUND(b.city_avg_temp_f, 2) AS city_avg_temp_f,
  ROUND(a.avg_temp_f - b.city_avg_temp_f, 2) AS heat_offset_f,
  ROUND(a.avg_humidity_pct, 1) AS avg_humidity_pct,
  t.total_pop,
  t.median_age,
  t.median_income,
  t.housing_units,
  GREATEST(0.0, 2025.0 - COALESCE( NULLIF(t.median_year_structure_built, 0), 1980.0 )) AS building_age_years,
  ROUND(SAFE_DIVIDE(t.housing_units, NULLIF(t.total_pop, 0)), 3) AS housing_density_proxy,
  ROUND(t.poverty_rate, 4) AS poverty_rate,
  ROUND(t.no_vehicle_rate, 4) AS no_vehicle_rate,
  (COALESCE(a.observation_count, 0) > 0) AS is_measured,
  (COALESCE(t.poverty_rate, 0) >= 0.20 OR COALESCE(t.no_vehicle_rate, 0) >= 0.10) AS is_high_vulnerability
FROM `${PROJECT_ID}.${DATASET}.tract_demographics` AS t
CROSS JOIN city_baseline AS b
LEFT JOIN tract_heat_agg AS a
  ON t.geo_id = a.geo_id
WHERE t.total_pop > 0;


-- 3. BigQuery ML Model: heat_offset_model (LINEAR_REG — Free Tier & ML.EXPLAIN_PREDICT ready)
--    Trains on measured Dallas census tracts (`is_measured = TRUE AND heat_offset_f IS NOT NULL`)
--    to predict `heat_offset_f` (degrees F above/below the Dallas afternoon average) from spatial
--    and built-environment/demographic features (excluding race).
CREATE OR REPLACE MODEL `${PROJECT_ID}.${DATASET}.heat_offset_model`
OPTIONS (
  model_type = 'LINEAR_REG',
  input_label_cols = ['heat_offset_f'],
  enable_global_explain = TRUE
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
FROM `${PROJECT_ID}.${DATASET}.v_tract_heat_features`
WHERE is_measured = TRUE
  AND heat_offset_f IS NOT NULL;
