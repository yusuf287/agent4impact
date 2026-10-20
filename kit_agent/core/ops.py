"""Operational logging + auto-generated rollback scripts for every CLI action.
Same files the bash scripts use: logs/operations.log (append-only) and rollback/undo_*.sh.
Policy: never auto-deleted."""
import datetime as dt
from pathlib import Path

from .domain import KIT_ROOT

LOG_DIR = KIT_ROOT / "logs"
UNDO_DIR = KIT_ROOT / "rollback"


class Ops:
    def __init__(self, name: str):
        LOG_DIR.mkdir(exist_ok=True)
        UNDO_DIR.mkdir(exist_ok=True)
        self.name = name
        self.run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + name
        self.undo_file = UNDO_DIR / f"undo_{self.run_id}.sh"
        self.log(f"=== start {self.run_id} ===")

    def log(self, msg: str) -> None:
        line = f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} [{self.name}] {msg}"
        print(line)
        with open(LOG_DIR / "operations.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def undo(self, cmd: str) -> None:
        """Register an undo command (newest first when rollback_all.sh runs it)."""
        if self.undo_file.exists():
            lines = self.undo_file.read_text(encoding="utf-8").splitlines()
        else:
            lines = ["#!/usr/bin/env bash", f"# Auto-generated rollback for {self.run_id}"]
        lines.insert(2, cmd)
        self.undo_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.log(f"UNDO registered: {cmd}")
