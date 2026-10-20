"""kit sql "<query>" | --file f.sql   run SQL (${PROJECT_ID} and ${DATASET} are substituted)
kit sql --view v_name --query "..."  create/replace a view, then AI-document it"""
from pathlib import Path

from kit.common import dataset, document_table, print_rows, project, render, run_sql
from kit_core.ops import Ops


def run(args):
    ops = Ops("sql")
    text = Path(args.file).read_text(encoding="utf-8") if args.file else (args.query or args.sql or "")
    if not text.strip():
        raise SystemExit("Give a query, --query, or --file")
    sql = render(text)
    if args.view:
        sql = f"CREATE OR REPLACE VIEW `{project()}.{dataset()}.{args.view}` AS\n{sql}"
        ops.log(f"Creating view {args.view}")
        run_sql(sql)
        ops.undo(f"bq --project_id={project()} rm -f -t {dataset()}.{args.view}")
        rows = run_sql(f"SELECT * FROM `{project()}.{dataset()}.{args.view}` LIMIT 5")
        print_rows(rows)
        if not args.no_describe:
            document_table(ops, args.view, [dict(r) for r in rows], use_ai=not args.no_ai)
        return
    ops.log("SQL: " + " ".join(sql.split())[:300])
    print_rows(run_sql(sql), args.limit)


def add_parser(sub):
    p = sub.add_parser("sql", help="Run SQL or create a documented view")
    p.add_argument("sql", nargs="?", help="query text")
    p.add_argument("--query")
    p.add_argument("--file")
    p.add_argument("--view", help="create/replace this view from the query")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--no-describe", action="store_true")
    p.add_argument("--no-ai", action="store_true")
    p.set_defaults(fn=run)
