#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <profile_name> [--plot]" >&2
  exit 2
fi
python3 scripts/run_profile.py "$@"
