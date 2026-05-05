#!/usr/bin/env bash
set -euo pipefail

DIR=$(cd "$(dirname "$0")" && pwd)

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <batch_dir> [output_pdf]" >&2
  exit 1
fi

BATCH_DIR=$1
OUT_PDF=${2:-"$DIR/required_effect_clean_10_graph_pack.pdf"}

python3 "$DIR/scripts/required_effect_clean_figure_pack.py" "$BATCH_DIR" "$OUT_PDF"
