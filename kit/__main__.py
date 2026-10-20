"""python -m kit <command>"""
import argparse
import sys

from kit import add_data, deploy_cmd, doctor, model_cmd, rehearse, scaffold, sql_cmd, team_cmd

EPILOG = """
Typical flow:
  kit init                          # .env, APIs  (data itself comes from the challenge notebook / load.sh)
  kit add-data extra.csv            # bring-your-own data (auto-documented)
  kit sql --file domains/urban_heat/views.sql
  kit model heat_offset --type linear --source v_training --label offset_f --features auto
  kit roles; kit team-check         # edit domains/<x>/team.yaml
  kit doctor ; kit rehearse ; kit web ; kit deploy runtime
"""


def main():
    ap = argparse.ArgumentParser(prog="kit", description="Agents-for-Impact plug-in CLI",
                                 epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    add_data.add_parser(sub)
    sql_cmd.add_parser(sub)
    model_cmd.add_parser(sub)
    doctor.add_parser(sub)
    rehearse.add_parser(sub)
    scaffold.add_parsers(sub)
    team_cmd.add_parsers(sub)
    deploy_cmd.add_parsers(sub)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
