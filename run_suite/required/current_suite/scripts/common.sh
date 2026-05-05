#!/usr/bin/env bash
set -euo pipefail

timestamp() {
  date --iso-8601=seconds
}

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi
  echo "Could not find docker compose or docker-compose" >&2
  return 1
}

reset_run_dir() {
  local run_dir="$1"
  local logs_dir="${run_dir}/logs"
  local artifacts_dir="${run_dir}/artifacts"

  mkdir -p "${logs_dir}" "${artifacts_dir}"
  find "${logs_dir}" -mindepth 1 -maxdepth 1 -type f -delete 2>/dev/null || true
  find "${artifacts_dir}" -mindepth 1 -maxdepth 1 -type f -delete 2>/dev/null || true
  rm -f "${run_dir}/execution_log.txt" "${run_dir}/execution_manifest.json"
}
