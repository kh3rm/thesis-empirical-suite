#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <batch_dir> <archive_name.tar.gz>" >&2
  exit 2
fi
BATCH_DIR="$1"
ARCHIVE_NAME="$2"
tar -czf "${ARCHIVE_NAME}" -C "$(dirname "${BATCH_DIR}")" "$(basename "${BATCH_DIR}")"
echo "Created ${ARCHIVE_NAME}"
