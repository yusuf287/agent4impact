"""BigQuery ML SQL generators (pure functions, unit-testable offline).

Model types: logistic | linear | boosted_class | boosted_reg | kmeans | arima
Predict SQL is returned as a TEMPLATE using {project} {dataset} {top_n} placeholders,
which is what the agent's run_model_predictions tool fills in.
"""
import re

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MODEL_TYPES = {
    "logistic": "LOGISTIC_REG",
    "linear": "LINEAR_REG",
    "boosted_class": "BOOSTED_TREE_CLASSIFIER",
    "boosted_reg": "BOOSTED_TREE_REGRESSOR",
    "kmeans": "KMEANS",
    "arima": "ARIMA_PLUS",
}
CLASSIFIERS = {"logistic", "boosted_class"}


def ident(x: str) -> str:
    if not _IDENT.match(x):
        raise ValueError(f"'{x}' is not a safe column/table identifier")
    return x


def fq(project: str, dataset: str, name: str) -> str:
    return f"`{project}.{dataset}.{ident(name)}`"


def train_sql(*, project, dataset, name, mtype, source, label=None, features=(), train_filter=None,
              clusters=5, time_col=None, value_col=None, series_col=None) -> str:
    if mtype not in MODEL_TYPES:
        raise ValueError(f"unknown model type {mtype}; choose from {sorted(MODEL_TYPES)}")
    model, src = fq(project, dataset, name), fq(project, dataset, source)
    where = f"\nWHERE {train_filter}" if train_filter else ""
    feats = ", ".join(ident(f) for f in features)

    if mtype == "arima":
        t, v = ident(time_col), ident(value_col)
        opts = [f"model_type = 'ARIMA_PLUS'", f"time_series_timestamp_col = '{t}'",
                f"time_series_data_col = '{v}'"]
        cols = f"{t}, {v}" + (f", {ident(series_col)}" if series_col else "")
        if series_col:
            opts.append(f"time_series_id_col = '{ident(series_col)}'")
        return f"CREATE OR REPLACE MODEL {model}\nOPTIONS ({', '.join(opts)}) AS\nSELECT {cols}\nFROM {src}{where};"

    if mtype == "kmeans":
        return (f"CREATE OR REPLACE MODEL {model}\nOPTIONS (model_type = 'KMEANS', num_clusters = {int(clusters)}, "
                f"standardize_features = TRUE) AS\nSELECT {feats}\nFROM {src}{where};")

    lab = ident(label)
    opts = [f"model_type = '{MODEL_TYPES[mtype]}'", f"input_label_cols = ['{lab}']"]
    if mtype == "logistic":
        opts.append("auto_class_weights = TRUE")
    if mtype.startswith("boosted"):
        opts.append("max_iterations = 50")
    return (f"CREATE OR REPLACE MODEL {model}\nOPTIONS ({', '.join(opts)}) AS\n"
            f"SELECT {lab}, {feats}\nFROM {src}{where};")


def eval_sql(*, project, dataset, name, mtype, source, label=None, features=(), predict_filter=None) -> str:
    model = fq(project, dataset, name)
    if mtype == "arima":
        return f"SELECT * FROM ML.ARIMA_EVALUATE(MODEL {model})"
    if mtype == "kmeans" or not predict_filter:
        return f"SELECT * FROM ML.EVALUATE(MODEL {model})"
    src = fq(project, dataset, source)
    feats = ", ".join(ident(f) for f in features)
    return (f"SELECT * FROM ML.EVALUATE(MODEL {model}, (SELECT {ident(label)}, {feats} "
            f"FROM {src} WHERE {predict_filter}))")


def predict_template(*, name, mtype, source, label=None, features=(), predict_filter=None,
                     id_cols=(), positive="1", horizon=14) -> str:
    """Returns SQL with {project}/{dataset}/{top_n} placeholders."""
    model = fq("{project}", "{dataset}", name)
    src = fq("{project}", "{dataset}", source)
    where = f" WHERE {predict_filter}" if predict_filter else ""
    ids = ", ".join(ident(i) for i in id_cols)
    ids_c = (ids + ", ") if ids else ""
    feats = ", ".join(ident(f) for f in features)

    if mtype == "arima":
        return (f"SELECT * FROM ML.FORECAST(MODEL {model}, STRUCT({int(horizon)} AS horizon, 0.9 AS confidence_level))\n"
                f"LIMIT {{top_n}}")
    if mtype == "kmeans":
        return (f"SELECT {ids_c}CENTROID_ID AS cluster, {feats}\n"
                f"FROM ML.PREDICT(MODEL {model}, (SELECT {ids_c}{feats} FROM {src}{where}))\n"
                f"ORDER BY cluster\nLIMIT {{top_n}}")
    lab = ident(label)
    inner = f"(SELECT {ids_c}{lab}, {feats} FROM {src}{where})"
    if mtype in CLASSIFIERS:
        return (f"SELECT {ids_c}ROUND(p.prob, 3) AS {lab}_probability, {lab} AS actual_{lab}, {feats}\n"
                f"FROM ML.PREDICT(MODEL {model}, {inner}),\n"
                f"UNNEST(predicted_{lab}_probs) AS p\nWHERE p.label = {positive}\n"
                f"ORDER BY p.prob DESC\nLIMIT {{top_n}}")
    return (f"SELECT {ids_c}ROUND(predicted_{lab}, 3) AS predicted_{lab}, {lab} AS actual_{lab}, {feats}\n"
            f"FROM ML.PREDICT(MODEL {model}, {inner})\nORDER BY predicted_{lab} DESC\nLIMIT {{top_n}}")


def describe_model(*, mtype, label, features, train_filter, predict_filter, metrics=None) -> str:
    kind = {"logistic": "logistic-regression classifier", "boosted_class": "boosted-tree classifier",
            "linear": "linear regression", "boosted_reg": "boosted-tree regression",
            "kmeans": "k-means clustering", "arima": "ARIMA_PLUS time-series forecast"}[mtype]
    s = f"A {kind}"
    if label:
        s += f" predicting `{label}`"
    if features:
        s += f" from {', '.join(features)}"
    if train_filter:
        s += f". Trained on rows where {train_filter}"
    if predict_filter:
        s += f"; scored/evaluated on held-out rows where {predict_filter}"
    if metrics:
        s += f". Held-out metrics: {metrics}"
    return s + ". Present outputs as model estimates, not facts; mention known misses."
