"""Apply table/column descriptions from the domain YAML to BigQuery.

Why: the MLB and F1 labs both showed that agents read BigQuery schema descriptions
to write correct SQL. Vague columns => wrong SQL. This makes it a 10-second step.
"""
import os
import sys
import yaml
from google.cloud import bigquery

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

domain = yaml.safe_load(open(os.environ["DOMAIN_FILE"], encoding="utf-8"))
project = os.environ["GOOGLE_CLOUD_PROJECT"]
dataset = os.environ["BQ_DATASET"]
client = bigquery.Client(project=project)

for name, spec in (domain.get("tables") or {}).items():
    ref = f"{project}.{dataset}.{name}"
    try:
        table = client.get_table(ref)
    except Exception as e:  # table/view may not exist yet
        print(f"skip {name}: {e}")
        continue
    table.description = spec.get("description", table.description)
    cols = spec.get("columns") or {}
    if table.table_type == "TABLE" and cols:
        new_schema = [
            bigquery.SchemaField(f.name, f.field_type, f.mode,
                                 description=cols.get(f.name, f.description),
                                 fields=f.fields)
            for f in table.schema
        ]
        table.schema = new_schema
        client.update_table(table, ["description", "schema"])
    else:
        client.update_table(table, ["description"])
    print(f"described {name} ({len(cols)} columns)")
