"""kit embed --table t --id-col id --text-col description     (EXPERIMENTAL)
Creates a BigQuery connection + remote embedding model, embeds the text column, registers
`semantic_search` for the agent. Follows the 'Multimodal Vector Search in BigQuery' lab pattern."""
import json
import subprocess

from kit.common import D, bq, dataset, project, run_sql
from kit_core import sqlgen
from kit_core.ops import Ops


def _sh(ops, cmd, check=True):
    ops.log("RUN: " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, shell=(subprocess.os.name == "nt"))
    ops.log((r.stdout + r.stderr).strip()[:400])
    if check and r.returncode:
        raise SystemExit(f"command failed: {' '.join(cmd)}")
    return r


def run(args):
    ops = Ops("embed")
    P, DS = project(), dataset()
    loc = bq().get_dataset(f"{P}.{DS}").location.lower()
    conn = args.connection
    _sh(ops, ["bq", f"--project_id={P}", "mk", "--connection", f"--location={loc}",
              "--connection_type=CLOUD_RESOURCE", conn], check=False)
    info = _sh(ops, ["bq", f"--project_id={P}", "show", "--connection", "--format=json", f"{P}.{loc}.{conn}"])
    sa = json.loads(info.stdout)["cloudResource"]["serviceAccountId"]
    _sh(ops, ["gcloud", "projects", "add-iam-policy-binding", P, f"--member=serviceAccount:{sa}",
              "--role=roles/aiplatform.user", "--condition=None", "--quiet"])
    ops.log("Granted aiplatform.user to the connection service account (IAM can take ~1-2 min to propagate)")

    model, emb = args.model, f"{args.table}_emb"
    sqlgen.ident(args.id_col), sqlgen.ident(args.text_col)
    run_sql(f"CREATE OR REPLACE MODEL `{P}.{DS}.{model}` REMOTE WITH CONNECTION `{P}.{loc}.{conn}` "
            f"OPTIONS (ENDPOINT = '{args.endpoint}')")
    ops.undo(f"bq --project_id={P} rm -f -m {DS}.{model}")
    run_sql(f"""CREATE OR REPLACE TABLE `{P}.{DS}.{emb}` AS
      SELECT * FROM ML.GENERATE_EMBEDDING(MODEL `{P}.{DS}.{model}`,
        (SELECT {args.id_col}, {args.text_col} AS content FROM `{P}.{DS}.{args.table}`
         WHERE {args.text_col} IS NOT NULL LIMIT {args.limit}), STRUCT(TRUE AS flatten_json_output))""")
    ops.undo(f"bq --project_id={P} rm -f -t {DS}.{emb}")
    D.save_overlay({"vector_search": {"embeddings_table": emb, "model": model, "id_col": args.id_col,
                                      "text_col": "content"}})
    ops.log("Registered semantic_search. Test: python -m kit sql \"SELECT COUNT(*) FROM `${PROJECT_ID}.${DATASET}." + emb + "`\"")


def add_parser(sub):
    p = sub.add_parser("embed", help="(experimental) embed a text column and enable semantic_search")
    p.add_argument("--table", required=True)
    p.add_argument("--id-col", required=True)
    p.add_argument("--text-col", required=True)
    p.add_argument("--model", default="embed_model")
    p.add_argument("--connection", default="kit-conn")
    p.add_argument("--endpoint", default="gemini-embedding-001")
    p.add_argument("--limit", type=int, default=20000)
    p.set_defaults(fn=run)
