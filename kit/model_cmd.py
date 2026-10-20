"""kit model <name> --type logistic --source v_x --label y --features auto|a,b,c
          --train-filter "year<=2023" --predict-filter "year=2024" --id-cols name,district

Trains a BigQuery ML model, evaluates it on the held-out slice, registers it for the agent
(run_model_predictions) and writes its description into generated.yaml."""
from kit.common import D, bq, dataset, project, run_sql
from kit_core import sqlgen
from kit_core.ops import Ops

NUMERIC = {"INTEGER", "INT64", "FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"}


def _auto_features(source, exclude):
    t = bq().get_table(f"{project()}.{dataset()}.{source}")
    feats = [f.name for f in t.schema if f.field_type in NUMERIC and f.name not in exclude
             and not f.name.endswith("_id") and f.name not in ("id", "year", "lat", "lon", "latitude", "longitude")]
    if not feats:
        raise SystemExit("No numeric feature columns found; pass --features explicitly")
    return feats


def run(args):
    ops = Ops("model")
    P, DS = project(), dataset()
    ids = [c for c in (args.id_cols or "").split(",") if c]
    feats = ([] if args.type == "arima" else
             _auto_features(args.source, set(ids + [args.label or "", args.time_col or "", args.value_col or ""]))
             if args.features == "auto" else [c for c in (args.features or "").split(",") if c])
    if args.features == "auto" and feats:
        print("Auto-selected features:", ", ".join(feats))
    kw = dict(project=P, dataset=DS, name=args.name, mtype=args.type, source=args.source, label=args.label,
              features=feats)
    train = sqlgen.train_sql(**kw, train_filter=args.train_filter, clusters=args.clusters, time_col=args.time_col,
                             value_col=args.value_col, series_col=args.series_col)
    print("\n--- TRAIN SQL ---\n" + train)
    if args.dry_run:
        return
    ops.log(f"Training model {args.name} ({args.type})")
    run_sql(train)
    ops.undo(f"bq --project_id={P} rm -f -m {DS}.{args.name}")

    metrics = None
    try:
        ev = run_sql(sqlgen.eval_sql(**kw, predict_filter=args.predict_filter))
        if ev:
            metrics = {k: round(v, 3) if isinstance(v, float) else v for k, v in dict(ev[0]).items()
                       if isinstance(v, (int, float))}
            ops.log(f"Evaluation ({'held-out' if args.predict_filter else 'training'}): {metrics}")
            print("Metrics:", metrics)
    except Exception as e:
        ops.log(f"Evaluation skipped: {str(e)[:160]}")

    pred = sqlgen.predict_template(name=args.name, mtype=args.type, source=args.source, label=args.label,
                                   features=feats, predict_filter=args.predict_filter, id_cols=ids,
                                   positive=args.positive, horizon=args.horizon)
    # prove the predict query works before the agent depends on it
    try:
        rows = run_sql(pred.format(project=P, dataset=DS, top_n=5))
        print(f"Predict query OK ({len(rows)} sample rows):")
        for r in rows[:5]:
            print("  ", dict(r))
    except Exception as e:
        ops.log(f"WARN predict query failed: {e}")
    D.save_overlay({"models": {args.name: {
        "type": args.type, "source": args.source, "label": args.label, "features": feats,
        "predict_sql": pred,
        "instructions": sqlgen.describe_model(mtype=args.type, label=args.label, features=feats,
                                              train_filter=args.train_filter, predict_filter=args.predict_filter,
                                              metrics=metrics)}}})
    ops.log(f"Registered model '{args.name}' for the agent. Restart `adk web` (or --reload_agents).")


def add_parser(sub):
    p = sub.add_parser("model", help="Train + evaluate + register a BigQuery ML model")
    p.add_argument("name")
    p.add_argument("--type", required=True, choices=sorted(sqlgen.MODEL_TYPES))
    p.add_argument("--source", required=True, help="table/view in your dataset")
    p.add_argument("--label")
    p.add_argument("--features", default="auto", help="auto | comma-separated columns")
    p.add_argument("--train-filter", help='SQL WHERE for training rows, e.g. "year<=2023"')
    p.add_argument("--predict-filter", help='SQL WHERE for held-out/scored rows, e.g. "year=2024"')
    p.add_argument("--id-cols", help="columns identifying each row in predictions, e.g. name,district")
    p.add_argument("--clusters", type=int, default=5)
    p.add_argument("--positive", default="1", help="positive class value for classifiers (1 or TRUE)")
    p.add_argument("--time-col")
    p.add_argument("--value-col")
    p.add_argument("--series-col")
    p.add_argument("--horizon", type=int, default=14)
    p.add_argument("--dry-run", action="store_true", help="print SQL only")
    p.set_defaults(fn=run)
