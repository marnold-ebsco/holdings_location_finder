#!/usr/bin/env bash
# Install the migration holdings tools on an Ubuntu EC2 instance.
# Run from a clone of the repo:
#     ./install_ec2.sh
# It checks that Python 3.12+ and git exist (it does not install them), makes
# sure /working/migration/scripts exists, uses the repo in
# /working/migration/scripts/holdings_migration_finder (cloning it there if
# you ran this from somewhere else), then runs setup.sh to build .venv.
# /working/migration/iterations and mapping_files are expected to exist already.
set -euo pipefail

SCRIPTS_DIR=/working/migration/scripts
TARGET="$SCRIPTS_DIR/holdings_migration_finder"  # folder name; the GitHub repo is holdings_location_finder
HERE="$(cd "$(dirname "$0")" && pwd)"

if ! command -v git >/dev/null 2>&1; then
    echo "git not found. Install it (sudo apt-get install -y git) and re-run." >&2
    exit 1
fi
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1 \
        || ! "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
    echo "Python 3.12+ not found (looked for: $PYTHON)." >&2
    echo "Install it, or run: PYTHON=/path/to/python3.12 ./install_ec2.sh" >&2
    exit 1
fi
if ! "$PYTHON" -c 'import venv, ensurepip' >/dev/null 2>&1; then
    echo "The venv module is missing. Run: sudo apt-get install -y python3-venv" >&2
    exit 1
fi
if [ ! -d /working/migration ]; then
    echo "/working/migration does not exist; it is expected to be there already." >&2
    exit 1
fi

mkdir -p "$SCRIPTS_DIR"

if [ "$(dirname "$HERE")" = "$SCRIPTS_DIR" ]; then
    TARGET="$HERE"   # already inside scripts/: install in place
else
    if [ -e "$TARGET" ]; then
        echo "$TARGET already exists. cd there and run ./install_ec2.sh instead." >&2
        exit 1
    fi
    git clone "$(git -C "$HERE" remote get-url origin)" "$TARGET"
fi

cd "$TARGET"
PYTHON="$PYTHON" ./setup.sh
echo
echo "Installed in $TARGET. Run:"
echo "  cd $TARGET"
echo "  .venv/bin/python migration_holdings.py        # MARC version"
echo "  python3 migration_holdings_tsv.py             # TSV version"
