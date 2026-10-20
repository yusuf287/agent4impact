"""Pre-built, tested BigQuery tools. The generic BigQueryToolset handles ad-hoc SQL; these
hold the fiddly queries (ML.PREDICT, VECTOR_SEARCH) the LLM should not improvise."""
from google.cloud import bigquery

from ..config import DATASET, DOMAIN, PROJECT_ID, models_of


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
    """Run a trained BigQuery ML model and return its top-N rows (predictions, risk scores, clusters or forecasts).

    Use whenever the user wants predictions, probabilities, "which X is most likely...", clusters or a forecast.

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


def semantic_search(query: str, top_k: int = 5) -> dict:
    """Find the records whose text is closest in MEANING to the query (vector search).

    Use for fuzzy lookups: "places like...", "reports about...", matching free text to records.

    Args:
        query: natural-language description to search for.
        top_k: number of matches (1-20).

    Returns:
        dict with matches (id, text, distance) or an error.
    """
    vs = DOMAIN.get("vector_search")
    if not vs:
        return {"status": "error", "message": "No vector_search configured. Run `kit embed`."}
    top_k = max(1, min(int(top_k), 20))
    sql = f"""
    SELECT base.{vs['id_col']} AS id, base.{vs['text_col']} AS text, distance
    FROM VECTOR_SEARCH(
      TABLE `{PROJECT_ID}.{DATASET}.{vs['embeddings_table']}`, 'ml_generate_embedding_result',
      (SELECT ml_generate_embedding_result FROM ML.GENERATE_EMBEDDING(
         MODEL `{PROJECT_ID}.{DATASET}.{vs['model']}`, (SELECT @q AS content),
         STRUCT(TRUE AS flatten_json_output))),
      top_k => {top_k}, distance_type => 'COSINE')"""
    try:
        cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("q", "STRING", query)])
        rows = _client().query(sql, job_config=cfg).result()
        return {"status": "success", "matches": [dict(r) for r in rows]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
