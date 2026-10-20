-- ============================================================================================
-- URBAN HEAT — one-time BigQuery setup. Paste this whole file into the BigQuery console and click RUN.
-- Needs the 3 challenge tables in dataset a4i_climate (heat_observations, station_daily_temps, tract_demographics).
-- Creates: v_tract_heat_features (table), v_station_heat_frequency (view), heat_offset_model (BQML LINEAR_REG).
-- Takes about 2-5 minutes. Safe to run again (everything is CREATE OR REPLACE).
-- ============================================================================================

-- STEP A: one row per census tract with its heat offset + enriched physical & senior metrics -------
-- Uses tract_demographics_enriched (polygon containment ST_CONTAINS with 3 km centroid fallback)
-- and preserves all original columns plus pop_density_sqkm, housing_density_sqkm, water_fraction,
-- seniors_65_plus, and senior_share. Saved as a TABLE so agent queries run fast.
CREATE OR REPLACE TABLE `a4i_climate.v_tract_heat_features` AS
WITH
city AS (
  SELECT AVG(temp_f) AS city_avg_temp_f
  FROM `a4i_climate.heat_observations`
  WHERE temp_f IS NOT NULL
),
tracts AS (
  SELECT * FROM `a4i_climate.tract_demographics_enriched`
  WHERE tract_lat IS NOT NULL AND tract_lon IS NOT NULL
),
obs AS (
  SELECT ROW_NUMBER() OVER () AS obs_id, latitude, longitude, temp_f, humidity_pct
  FROM `a4i_climate.heat_observations`
  WHERE temp_f IS NOT NULL AND latitude IS NOT NULL AND longitude IS NOT NULL
),
obs_tract AS (
  SELECT
    o.obs_id,
    ANY_VALUE(o.temp_f) AS temp_f,
    ANY_VALUE(o.humidity_pct) AS humidity_pct,
    ARRAY_AGG(
      t.geo_id
      ORDER BY
        IF(t.tract_geom IS NOT NULL AND ST_CONTAINS(t.tract_geom, ST_GEOGPOINT(o.longitude, o.latitude)), 0, 1),
        ST_DISTANCE(ST_GEOGPOINT(o.longitude, o.latitude), ST_GEOGPOINT(t.tract_lon, t.tract_lat))
      LIMIT 1
    )[OFFSET(0)] AS geo_id
  FROM obs o
  JOIN tracts t
    ON ST_DWITHIN(ST_GEOGPOINT(o.longitude, o.latitude), ST_GEOGPOINT(t.tract_lon, t.tract_lat), 3500)
  GROUP BY o.obs_id
),
per_tract AS (
  SELECT geo_id, COUNT(*) AS observation_count, AVG(temp_f) AS avg_temp_f, MAX(temp_f) AS max_temp_f,
         AVG(humidity_pct) AS avg_humidity_pct
  FROM obs_tract
  GROUP BY geo_id
)
SELECT
  t.geo_id,
  t.tract_lat,
  t.tract_lon,
  IFNULL(p.observation_count, 0)                         AS observation_count,
  ROUND(p.avg_temp_f, 2)                                 AS avg_temp_f,
  ROUND(p.max_temp_f, 2)                                 AS max_temp_f,
  ROUND(c.city_avg_temp_f, 2)                            AS city_avg_temp_f,
  ROUND(p.avg_temp_f - c.city_avg_temp_f, 2)             AS heat_offset_f,      -- THE LABEL (NULL if unmeasured)
  ROUND(p.avg_humidity_pct, 1)                           AS avg_humidity_pct,
  t.total_pop,
  t.median_age,
  t.median_income,
  t.housing_units,
  COALESCE(t.building_age_years, 2025 - NULLIF(t.median_year_structure_built, 0)) AS building_age_years,
  SAFE_DIVIDE(t.housing_units, t.total_pop)              AS housing_density_proxy,
  t.land_area_sqkm,
  t.pop_density_sqkm,
  t.housing_density_sqkm,
  t.water_fraction,
  t.seniors_65_plus,
  t.senior_share,
  t.poverty_rate,
  t.no_vehicle_rate,
  IFNULL(p.observation_count, 0) > 0                     AS is_measured,
  (IFNULL(t.poverty_rate, 0) >= 0.20 OR IFNULL(t.no_vehicle_rate, 0) >= 0.10 OR IFNULL(t.senior_share, 0) >= 0.18) AS is_high_vulnerability
FROM tracts t
CROSS JOIN city c
LEFT JOIN per_tract p USING (geo_id);

-- STEP B: how often does the city get dangerously hot, per station per year --------------------
CREATE OR REPLACE VIEW `a4i_climate.v_station_heat_frequency` AS
SELECT
  EXTRACT(YEAR FROM observation_date)                                  AS year,
  station_id,
  ANY_VALUE(station_name)                                              AS station_name,
  COUNT(*)                                                             AS days_observed,
  COUNTIF(max_temp_f >= 95)                                            AS days_95f_plus,
  COUNTIF(max_temp_f >= 100)                                           AS days_100f_plus,
  COUNTIF(max_temp_f >= 105)                                           AS days_105f_plus,
  ROUND(AVG(IF(EXTRACT(MONTH FROM observation_date) IN (6, 7, 8), max_temp_f, NULL)), 1) AS avg_summer_max_temp_f,
  MAX(max_temp_f)                                                      AS peak_temp_f
FROM `a4i_climate.station_daily_temps`
WHERE max_temp_f IS NOT NULL
GROUP BY year, station_id;

-- STEP C: train the model (predicts the OFFSET, trained only on tracts volunteers measured) -----
CREATE OR REPLACE MODEL `a4i_climate.heat_offset_model`
OPTIONS (
  model_type = 'LINEAR_REG',
  input_label_cols = ['heat_offset_f'],
  enable_global_explain = TRUE,
  data_split_method = 'RANDOM',          -- hold out 20% of measured tracts so ML.EVALUATE is honest
  data_split_eval_fraction = 0.2         -- (BigQuery skips the split by default for small tables)
) AS
SELECT
  heat_offset_f,
  -- median_income removed: it is NULL for every measured tract in the loaded data (BigQuery ML cannot use it).
  tract_lat, tract_lon, building_age_years, housing_density_proxy, housing_units,
  pop_density_sqkm, housing_density_sqkm, water_fraction, senior_share,
  total_pop, poverty_rate, no_vehicle_rate, median_age
FROM `a4i_climate.v_tract_heat_features`
WHERE is_measured AND heat_offset_f IS NOT NULL;

-- STEP D: quick checks (look at the results tabs) ----------------------------------------------
SELECT COUNTIF(is_measured) AS measured_tracts, COUNT(*) AS all_tracts,
       ROUND(MIN(heat_offset_f), 1) AS coolest_offset_f, ROUND(MAX(heat_offset_f), 1) AS hottest_offset_f
FROM `a4i_climate.v_tract_heat_features`;

SELECT * FROM ML.EVALUATE(MODEL `a4i_climate.heat_offset_model`);   -- r2_score near 0.9+ = suspicious (leakage)
