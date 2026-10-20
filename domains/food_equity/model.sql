-- BQML logistic regression, trained through 2023; 2024 is held out for honest evaluation.
-- Template for any binary label: change the label, the feature list and the FROM view.
CREATE OR REPLACE MODEL `${PROJECT_ID}.${DATASET}.need_model`
OPTIONS (model_type = 'LOGISTIC_REG', input_label_cols = ['high_need'], auto_class_weights = TRUE) AS
SELECT
  high_need,
  median_income, pct_no_vehicle, pct_seniors, distance_to_grocery_km, outlets_per_1k
FROM `${PROJECT_ID}.${DATASET}.v_neighborhood_features`
WHERE year <= 2023;
