---
name: add-model
description: Train, evaluate and register a BigQuery ML model (classification, regression, clustering, forecasting) so the agent can call it. Use when the challenge needs predictions, risk scores, segments or forecasts.
---

# Add an ML model

Choose the type: yes/no outcome → `logistic` (or `boosted_class` if accuracy matters); a number → `linear`/`boosted_reg`;
groups → `kmeans`; future values over time → `arima`.

1. Pick the source view (one row per entity per period) and the label. Ensure the label is not leaked by a feature.
2. **Hold out the latest period**: `--train-filter "year<=2023" --predict-filter "year=2024"` (or the time split that fits).
3. Run:
   `python -m kit model <name> --type logistic --source v_<topic> --label <col> --features auto --train-filter "..." --predict-filter "..." --id-cols <name_col>,<group_col>`
   For `arima`: `--time-col <date> --value-col <n> [--series-col <id>] --horizon 14`.
   For `kmeans`: omit `--label`, set `--clusters 5`.
4. Read the printed metrics. Report honestly: AUC/accuracy for classifiers, MAE/R² for regression. If weak, try `boosted_class`, drop leaking/noisy features, or say so in the demo.
5. Find 2–3 cases the model got WRONG (compare predicted vs actual) and note why — put the lesson in `domains/<x>/domain.yaml` under `routing_rules` or in the demo script. Honest misses build trust.
6. Verify the agent sees it: restart `python -m kit web`, ask "Which model(s) do you have and what do they predict?".

If BigQuery ML errors on a feature type, cast it in the view (BOOL/INT/FLOAT/STRING are fine; avoid arrays/structs).
