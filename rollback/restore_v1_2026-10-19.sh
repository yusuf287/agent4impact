#!/usr/bin/env bash
# Extracts the archived v1 scaffold into ./restored_v1 (does not touch current files).
cd "$(dirname "$0")/.." && python3 -c "import zipfile;zipfile.ZipFile('.archive/impact-agent-v1-and-misc.zip').extractall('restored_v1')" && echo "see restored_v1/"
