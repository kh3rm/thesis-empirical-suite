#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <profile_name>" >&2
  exit 2
fi
PROFILE="$1"
LATEST=$(python3 - <<PY
from pathlib import Path
root = Path('output/batches')
candidates = sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith('${PROFILE}_')])
print(candidates[-1] if candidates else '')
PY
)
if [[ -z "$LATEST" ]]; then
  echo "No batch found for profile ${PROFILE}" >&2
  exit 1
fi
python3 scripts/plot_batch.py "$LATEST"
echo "$LATEST"
