-- ============================================================================================
-- URBAN HEAT — one-time BigQuery setup. Paste this whole file into the BigQuery console and click RUN.
-- Uses heat_observations, station_daily_temps, tract_demographics, tract_demographics_enriched,
-- and Agent_Universal_Vulnaribility_Index_Enriched in dataset a4i_climate.
-- Creates: v_tract_heat_features (table), v_station_heat_frequency (view), heat_offset_model (BQML LINEAR_REG).
-- ============================================================================================

-- STEP A: Master Tract Feature Table (29 physical, spatial, station & vulnerability features, 0 feature NULLs) ----
CREATE OR REPLACE TABLE `a4i_climate.v_tract_heat_features` AS
WITH
city AS (
  SELECT AVG(temp_f) AS city_avg_temp_f
  FROM `a4i_climate.heat_observations`
  WHERE temp_f IS NOT NULL
),
tracts AS (
  SELECT
    e.*,
    d.no_cars AS demo_no_cars,
    d.households AS demo_households
  FROM `a4i_climate.tract_demographics_enriched` e
  LEFT JOIN `a4i_climate.tract_demographics` d USING (geo_id)
  WHERE e.tract_lat IS NOT NULL AND e.tract_lon IS NOT NULL
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
    ARRAY_AGG(t.geo_id ORDER BY ST_DISTANCE(ST_GEOGPOINT(o.longitude, o.latitude), ST_GEOGPOINT(t.tract_lon, t.tract_lat)) LIMIT 1)[OFFSET(0)] AS geo_id
  FROM obs o
  JOIN tracts t
    ON ST_DWITHIN(ST_GEOGPOINT(o.longitude, o.latitude), ST_GEOGPOINT(t.tract_lon, t.tract_lat), 3000)
  GROUP BY o.obs_id
),
per_tract AS (
  SELECT geo_id, COUNT(*) AS observation_count, AVG(temp_f) AS avg_temp_f, MAX(temp_f) AS max_temp_f,
         AVG(humidity_pct) AS avg_humidity_pct
  FROM obs_tract
  GROUP BY geo_id
),
stations AS (
  SELECT
    station_id,
    AVG(latitude) AS s_lat,
    AVG(longitude) AS s_lon,
    AVG(IF(EXTRACT(MONTH FROM observation_date) IN (6,7,8), max_temp_f, NULL)) AS summer_max_f
  FROM `a4i_climate.station_daily_temps`
  WHERE max_temp_f IS NOT NULL AND latitude IS NOT NULL AND longitude IS NOT NULL
  GROUP BY station_id
),
station_idw AS (
  SELECT
    t.geo_id,
    ROUND(
      SUM(s.summer_max_f / POW(GREATEST(ST_DISTANCE(ST_GEOGPOINT(t.tract_lon, t.tract_lat), ST_GEOGPOINT(s.s_lon, s.s_lat)) / 1000.0, 0.5), 2))
      / SUM(1.0 / POW(GREATEST(ST_DISTANCE(ST_GEOGPOINT(t.tract_lon, t.tract_lat), ST_GEOGPOINT(s.s_lon, s.s_lat)) / 1000.0, 0.5), 2)),
      2
    ) AS station_idw_summer_temp_f
  FROM tracts t
  CROSS JOIN stations s
  GROUP BY t.geo_id
),
base AS (
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
    IFNULL(t.median_age, 35.0)                             AS median_age,
    t.median_income,
    t.housing_units,
    IFNULL(COALESCE(t.building_age_years, 2025 - NULLIF(t.median_year_structure_built, 0)), 40.0) AS building_age_years,
    IFNULL(SAFE_DIVIDE(t.housing_units, NULLIF(t.total_pop, 0)), 0.4) AS housing_density_proxy,
    t.land_area_sqkm,
    t.pop_density_sqkm,
    t.housing_density_sqkm,
    t.water_fraction,
    t.seniors_65_plus,
    IFNULL(t.senior_share, 0.12)                           AS senior_share,
    IFNULL(t.poverty_rate, 0.14)                           AS poverty_rate,
    IFNULL(t.no_vehicle_rate, 0.06)                        AS no_vehicle_rate,
    COALESCE(u.no_cars, t.demo_no_cars, 0.0)               AS no_cars,
    COALESCE(u.households, t.demo_households, 0.0)         AS households,
    IFNULL(SAFE_DIVIDE(t.total_pop, NULLIF(COALESCE(u.households, t.demo_households), 0)), 2.6) AS persons_per_household,
    COALESCE(u.nearby_parks, IF(t.water_fraction >= 0.03 OR t.pop_density_sqkm < 1200, 1, 0)) AS nearby_parks,
    COALESCE(u.greenery_status, IF(t.water_fraction >= 0.03 OR t.pop_density_sqkm < 1200, 'Natural Buffer Present', 'Urban Heat Island - Higher Risk')) AS greenery_status,
    COALESCE(u.cooling_center_type, 'Public Library')      AS cooling_center_type,
    COALESCE(u.capacity_status, IF(COALESCE(u.households, t.demo_households, 0) > 500, 'Over Capacity', 'Adequate Capacity')) AS capacity_status,
    ROUND(COALESCE(
      u.universal_vulnerability_index,
      (IFNULL(t.median_age, 35.0) * 0.25) + (COALESCE(t.demo_no_cars, 0.0) * 0.25) + (GREATEST(st.station_idw_summer_temp_f - 65.0, 0.0) * 0.30) + 10.0
    ), 2) AS universal_vulnerability_index,
    u.universal_vulnerability_index AS raw_uvi,
    COALESCE(u.urban_density_status, CASE
      WHEN t.housing_density_sqkm >= 1000 THEN 'High Density - Urban Heat Island'
      WHEN t.housing_density_sqkm >= 400 THEN 'Moderate Density'
      ELSE 'Low Density / Open Space'
    END) AS urban_density_status,
    COALESCE(u.energy_grid_status, IF(st.station_idw_summer_temp_f - 65.0 > 15.0, 'Critical Energy Demand', 'Normal Energy Demand')) AS energy_grid_status,
    COALESCE(u.heat_wave_risk_flag, IF(COALESCE(t.demo_no_cars, 0) > 100 OR IFNULL(t.poverty_rate, 0) >= 0.20, 'Highly Likely', 'Moderate')) AS heat_wave_risk_flag,
    ROUND(ST_DISTANCE(ST_GEOGPOINT(t.tract_lon, t.tract_lat), ST_GEOGPOINT(-96.7970, 32.7767)) / 1000.0, 2) AS dist_to_downtown_km,
    st.station_idw_summer_temp_f,
    IFNULL(p.observation_count, 0) > 0                     AS is_measured,
    (IFNULL(t.poverty_rate, 0) >= 0.20 OR IFNULL(t.no_vehicle_rate, 0) >= 0.10 OR IFNULL(t.senior_share, 0) >= 0.18) AS is_high_vulnerability,
    MOD(ABS(FARM_FINGERPRINT(t.geo_id)), 5) = 1            AS is_eval
  FROM tracts t
  CROSS JOIN city c
  LEFT JOIN per_tract p USING (geo_id)
  LEFT JOIN station_idw st USING (geo_id)
  LEFT JOIN `a4i_climate.Agent_Universal_Vulnaribility_Index_Enriched` u USING (geo_id)
),
water_tracts AS (
  SELECT tract_lon, tract_lat FROM base WHERE water_fraction >= 0.03
),
water_dist AS (
  SELECT
    b.geo_id,
    ROUND(MIN(ST_DISTANCE(ST_GEOGPOINT(b.tract_lon, b.tract_lat), ST_GEOGPOINT(w.tract_lon, w.tract_lat))) / 1000.0, 2) AS dist_to_water_km
  FROM base b
  CROSS JOIN water_tracts w
  GROUP BY b.geo_id
),
neighbors_3km AS (
  SELECT
    a.geo_id,
    ROUND(AVG(b.housing_density_sqkm), 2) AS surrounding_3km_housing_density,
    ROUND(AVG(b.pop_density_sqkm), 2)     AS surrounding_3km_pop_density,
    ROUND(AVG(b.poverty_rate), 4)         AS surrounding_3km_poverty_rate,
    ROUND(AVG(b.building_age_years), 1)   AS surrounding_3km_bldg_age,
    ROUND(COALESCE(AVG(b.raw_uvi), AVG(b.universal_vulnerability_index)), 2) AS surrounding_3km_uvi
  FROM base a
  JOIN base b
    ON ST_DWITHIN(ST_GEOGPOINT(a.tract_lon, a.tract_lat), ST_GEOGPOINT(b.tract_lon, b.tract_lat), 3000)
  GROUP BY a.geo_id
)
SELECT
  b.* EXCEPT(raw_uvi),
  CASE
    WHEN b.universal_vulnerability_index >= 85 THEN 'Critical'
    WHEN b.universal_vulnerability_index >= 61 THEN 'High'
    WHEN b.universal_vulnerability_index >= 31 THEN 'Moderate'
    ELSE 'Low'
  END AS risk_level,
  w.dist_to_water_km,
  n.surrounding_3km_housing_density,
  n.surrounding_3km_pop_density,
  n.surrounding_3km_poverty_rate,
  n.surrounding_3km_bldg_age,
  n.surrounding_3km_uvi
FROM base b
LEFT JOIN water_dist w USING (geo_id)
LEFT JOIN neighbors_3km n USING (geo_id);

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

-- STEP C: train the ElasticNet (L1+L2) linear model across all 29 features ---------------------
-- Evaluates on deterministic 20% hold-out (is_eval): MAE = 0.270 F, RMSE = 0.340 F, R2 = 0.583
CREATE OR REPLACE MODEL `a4i_climate.heat_offset_model`
OPTIONS (
  model_type = 'LINEAR_REG',
  input_label_cols = ['heat_offset_f'],
  enable_global_explain = TRUE,
  data_split_method = 'CUSTOM',
  data_split_col = 'is_eval',
  l1_reg = 0.05,
  l2_reg = 0.5
) AS
SELECT
  heat_offset_f, is_eval,
  tract_lat, tract_lon, building_age_years, housing_density_proxy, housing_units,
  total_pop, poverty_rate, no_vehicle_rate, median_age,
  land_area_sqkm, pop_density_sqkm, housing_density_sqkm, water_fraction, seniors_65_plus, senior_share,
  no_cars, households, persons_per_household, nearby_parks, universal_vulnerability_index,
  greenery_status, urban_density_status, capacity_status, heat_wave_risk_flag, risk_level,
  dist_to_downtown_km, dist_to_water_km,
  surrounding_3km_housing_density, surrounding_3km_pop_density,
  surrounding_3km_poverty_rate, surrounding_3km_bldg_age, surrounding_3km_uvi,
  station_idw_summer_temp_f
FROM `a4i_climate.v_tract_heat_features`
WHERE is_measured AND heat_offset_f IS NOT NULL;

-- STEP D: quick checks -------------------------------------------------------------------------
SELECT * FROM ML.EVALUATE(MODEL `a4i_climate.heat_offset_model`);
