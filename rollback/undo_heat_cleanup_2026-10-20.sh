#!/usr/bin/env bash
# Restores the files removed in the Urban Heat cleanup (does not overwrite current files).
cd "$(dirname "$0")/.." && python3 -c "import zipfile;zipfile.ZipFile('.archive/pre-heat-cleanup-2026-10-20.zip').extractall('restored_pre_heat')" && echo "see restored_pre_heat/"
