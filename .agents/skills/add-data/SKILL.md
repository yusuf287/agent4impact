---
name: add-data
description: Load a dataset (CSV/JSON/Parquet/Excel/GeoJSON file or URL) into BigQuery, auto-document columns, and build agent-friendly views. Use whenever new data is needed.
---

# Add data to BigQuery

1. Run `python -m kit add-data <source> [--table name] [--limit 5000]`.
   - The core challenge tables come from the challenge notebook / `scripts/load.sh`; use this only for extra data.
   - Check the license first: public domain / CC0 / US Gov only. No OpenStreetMap-derived (ODbL), NC, ND or share-alike data.
2. Read the printed null warnings and the generated column descriptions in `domains/<x>/generated.yaml`.
   Fix any wrong description by writing the correct one in `domain.yaml` (hand-written wins).
3. Build ONE clean view per analytical question: `python -m kit sql --view v_<topic> --query "SELECT ..."`.
   Rules for the view: pre-join facts, human-readable names, boolean flags (`is_...`), no ambiguous column names,
   units in names or descriptions. Join keys: confirm types match before joining.
4. Sanity check: `python -m kit sql "SELECT COUNT(*) FROM \`${PROJECT_ID}.${DATASET}.v_<topic>\`"` and compare to the source row count.
5. Real data vs synthetic: if you generate synthetic rows, label the table description "SYNTHETIC".
6. Add a line to `routing_rules` in `domain.yaml` telling the agent when to use the new view.

Never load personal data. Undo with `rollback/undo_*add-data*.sh`.
