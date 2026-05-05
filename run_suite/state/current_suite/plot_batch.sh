#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <batch_dir>" >&2
  exit 2
fi
python3 scripts/plot_batch.py "$1"
