#!/usr/bin/env bash
# Create .venv and install the dependencies from requirements.txt.
# Usage: ./setup.sh   (then run .venv/bin/python migration_holdings.py)
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if ! "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    echo "Python 3.12 or higher is required (found: $("$PYTHON" --version 2>&1))." >&2
    exit 1
fi

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt
echo "Done. Run: .venv/bin/python migration_holdings.py"
