-- Agent-friendly views: pre-joined, self-documenting column names, boolean flags.
-- (Schema design is prompt engineering for your database.)
CREATE OR REPLACE VIEW `${PROJECT_ID}.${DATASET}.v_neighborhood_features` AS
WITH outlet_counts AS (
  SELECT neighborhood_id,
         COUNT(*) AS outlet_count,
         COUNTIF(accepts_ebt = 1) AS ebt_outlet_count,
         COUNTIF(outlet_type = 'grocery') AS grocery_count
  FROM `${PROJECT_ID}.${DATASET}.food_outlets`
  GROUP BY neighborhood_id
)
SELECT
  s.neighborhood_id,
  n.name AS neighborhood_name,
  n.district,
  s.year,
  n.population,
  n.median_income,
  n.pct_no_vehicle,
  n.pct_seniors,
  n.distance_to_grocery_km,
  n.lat,
  n.lon,
  COALESCE(o.outlet_count, 0) AS outlet_count,
  COALESCE(o.grocery_count, 0) AS grocery_count,
  SAFE_DIVIDE(COALESCE(o.outlet_count, 0), n.population) * 1000 AS outlets_per_1k,
  s.insecurity_rate,
  s.high_need
FROM `${PROJECT_ID}.${DATASET}.food_insecurity_survey` s
JOIN `${PROJECT_ID}.${DATASET}.neighborhoods` n USING (neighborhood_id)
LEFT JOIN outlet_counts o USING (neighborhood_id);
