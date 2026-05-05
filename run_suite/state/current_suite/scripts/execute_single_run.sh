#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
PACKAGE_ROOT=$(cd "${PROJECT_ROOT}/../../.." && pwd)
source "${SCRIPT_DIR}/common.sh"

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <run_dir>" >&2
  exit 2
fi

RUN_DIR=$(cd "$1" && pwd)
RUN_ID=$(basename "${RUN_DIR}")
RUNTIME_ENV_FILE="${RUN_DIR}/scenario.env"
ARTIFACTS_DIR="${RUN_DIR}/artifacts"
LOGS_DIR="${RUN_DIR}/logs"
LOG_FILE="${RUN_DIR}/execution_log.txt"
MANIFEST_FILE="${RUN_DIR}/execution_manifest.json"
RUN_SPEC_FILE="${ARTIFACTS_DIR}/run_spec.json"

[[ -f "${RUNTIME_ENV_FILE}" ]] || { echo "Missing runtime env: ${RUNTIME_ENV_FILE}" >&2; exit 1; }

PROJECT_NAME=$(awk -F= '/^PROJECT_NAME=/{print $2}' "${RUNTIME_ENV_FILE}")
RUN_TIMEOUT_SECONDS=$(awk -F= '/^RUN_TIMEOUT_SECONDS=/{print $2}' "${RUNTIME_ENV_FILE}")
PRODUCER_START_TIMEOUT_SECONDS=$(awk -F= '/^PRODUCER_START_TIMEOUT_SECONDS=/{print $2}' "${RUNTIME_ENV_FILE}")
PRODUCER_COMPLETE_TIMEOUT_SECONDS=$(awk -F= '/^PRODUCER_COMPLETE_TIMEOUT_SECONDS=/{print $2}' "${RUNTIME_ENV_FILE}")

PRODUCER_STARTED_FILE="${ARTIFACTS_DIR}/producer_started.json"
PRODUCER_SENTINEL_FILE="${ARTIFACTS_DIR}/producer_complete.json"
RUN_SENTINEL_FILE="${ARTIFACTS_DIR}/run_complete.json"
SUMMARY_FILE="${LOGS_DIR}/consumer_summary.json"
RUN_STATUS_FILE="${RUN_DIR}/run_status.json"

reset_run_dir "${RUN_DIR}"
mkdir -p "${ARTIFACTS_DIR}" "${LOGS_DIR}"
: > "${LOG_FILE}"
python3 "${SCRIPT_DIR}/render_run_spec.py" "${RUNTIME_ENV_FILE}" "${RUN_SPEC_FILE}"

export HOST_RUN_DIR="${RUN_DIR}"
export RUN_ENV_FILE="${RUNTIME_ENV_FILE}"

cat > "${MANIFEST_FILE}" <<JSON
{
  "run_id": "${RUN_ID}",
  "project_name": "${PROJECT_NAME}",
  "started_at": "$(timestamp)",
  "host_run_dir": "${RUN_DIR}",
  "runtime_env_file": "${RUNTIME_ENV_FILE}"
}
JSON

cat > "${RUN_STATUS_FILE}" <<JSON
{
  "run_id": "${RUN_ID}",
  "status": "started",
  "started_at": "$(timestamp)",
  "project_name": "${PROJECT_NAME}"
}
JSON

mark_failed() {
  local reason="$1"
  cat > "${RUN_STATUS_FILE}" <<JSON
{
  "run_id": "${RUN_ID}",
  "status": "failed",
  "failure_reason": "${reason}",
  "finished_at": "$(timestamp)",
  "project_name": "${PROJECT_NAME}"
}
JSON
}

mark_completed() {
  cat > "${RUN_STATUS_FILE}" <<JSON
{
  "run_id": "${RUN_ID}",
  "status": "completed",
  "finished_at": "$(timestamp)",
  "project_name": "${PROJECT_NAME}"
}
JSON
}

log_step() {
  local message="$1"
  echo "[$(timestamp)] ${message}" | tee -a "${LOG_FILE}"
}

run_cmd() {
  local label="$1"
  shift
  log_step "${label}"
  {
    echo
    echo "=== ${label} ==="
    echo "COMMAND: $*"
  } >> "${LOG_FILE}"
  "$@" < /dev/null 2>&1 | tee -a "${LOG_FILE}"
}

capture_failure_context() {
  run_cmd "COMPOSE_PS" compose -f "${PROJECT_ROOT}/compose/docker-compose.yml" --project-name "${PROJECT_NAME}" ps -a || true
  run_cmd "COMPOSE_LOGS" compose -f "${PROJECT_ROOT}/compose/docker-compose.yml" --project-name "${PROJECT_NAME}" logs --no-color || true
}

cleanup() {
  run_cmd "COMPOSE_DOWN" compose -f "${PROJECT_ROOT}/compose/docker-compose.yml" --project-name "${PROJECT_NAME}" down -v --remove-orphans || true
}
trap cleanup EXIT

wait_for_file() {
  local label="$1"
  local file_path="$2"
  local timeout_seconds="$3"
  local start_ts now_ts elapsed

  log_step "${label}"
  echo "path=${file_path}" >> "${LOG_FILE}"
  start_ts=$(date +%s)

  while true; do
    if [[ -f "${file_path}" ]]; then
      log_step "${label}_detected"
      return 0
    fi
    now_ts=$(date +%s)
    elapsed=$((now_ts - start_ts))
    if (( elapsed > timeout_seconds )); then
      return 1
    fi
    sleep 1
  done
}

run_cmd "PRE_COMPOSE_DOWN" compose -f "${PROJECT_ROOT}/compose/docker-compose.yml" --project-name "${PROJECT_NAME}" down -v --remove-orphans || true
run_cmd "COMPOSE_UP_SERVICES" compose -f "${PROJECT_ROOT}/compose/docker-compose.yml" --project-name "${PROJECT_NAME}" up -d --build redis consumer producer

if ! wait_for_file "WAIT_FOR_PRODUCER_START" "${PRODUCER_STARTED_FILE}" "${PRODUCER_START_TIMEOUT_SECONDS}"; then
  capture_failure_context
  echo "Producer start sentinel did not appear after ${PRODUCER_START_TIMEOUT_SECONDS} seconds: ${PRODUCER_STARTED_FILE}" | tee -a "${LOG_FILE}"
  mark_failed "producer_start_timeout"
  exit 1
fi

if ! wait_for_file "WAIT_FOR_PRODUCER_COMPLETION" "${PRODUCER_SENTINEL_FILE}" "${PRODUCER_COMPLETE_TIMEOUT_SECONDS}"; then
  capture_failure_context
  echo "Producer completion sentinel did not appear after ${PRODUCER_COMPLETE_TIMEOUT_SECONDS} seconds: ${PRODUCER_SENTINEL_FILE}" | tee -a "${LOG_FILE}"
  mark_failed "producer_completion_timeout"
  exit 1
fi

log_step "WAIT_FOR_RUN_COMPLETION"
echo "sentinel_path=${RUN_SENTINEL_FILE}" >> "${LOG_FILE}"
echo "summary_path=${SUMMARY_FILE}" >> "${LOG_FILE}"

start_ts=$(date +%s)
while true; do
  if [[ -f "${RUN_SENTINEL_FILE}" || -f "${SUMMARY_FILE}" ]]; then
    log_step "completion_detected"
    break
  fi
  now_ts=$(date +%s)
  elapsed=$((now_ts - start_ts))
  if (( elapsed > RUN_TIMEOUT_SECONDS )); then
    capture_failure_context
    echo "Timed out waiting for completion after ${RUN_TIMEOUT_SECONDS} seconds" | tee -a "${LOG_FILE}"
    mark_failed "run_timeout"
    exit 1
  fi
  sleep 2
done

run_cmd "COMPOSE_LOGS" compose -f "${PROJECT_ROOT}/compose/docker-compose.yml" --project-name "${PROJECT_NAME}" logs --no-color
if ! run_cmd "VERIFY_RUN_INTEGRITY" python3 "${PACKAGE_ROOT}/scripts/validate_run_integrity.py" "${RUN_DIR}"; then
  capture_failure_context
  echo "Run integrity validation failed" | tee -a "${LOG_FILE}"
  mark_failed "run_integrity_failed"
  exit 1
fi
mark_completed
log_step "run_finished"
