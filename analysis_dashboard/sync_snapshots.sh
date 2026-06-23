#!/usr/bin/env bash
set -euo pipefail

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE_HOST="${REMOTE_HOST:-cmslpc}"
REMOTE_DIR="${REMOTE_DIR:-~/DisappTrks_v2/analysis_dashboard}"
REMOTE_COLLECT="${REMOTE_COLLECT:-1}"

mkdir -p "${LOCAL_DIR}/snapshots"

if [[ "${REMOTE_COLLECT}" == "1" ]]; then
  ssh "${REMOTE_HOST}" "cd ${REMOTE_DIR} && DASHBOARD_ENSURE_PROXY='${DASHBOARD_ENSURE_PROXY:-0}' DASHBOARD_PROXY_MIN_VALID='${DASHBOARD_PROXY_MIN_VALID:-4:00}' DASHBOARD_PROXY_VALID='${DASHBOARD_PROXY_VALID:-192:00}' bash collectors/collect_all.sh"
fi

rsync -av "${REMOTE_HOST}:${REMOTE_DIR%/}/snapshots/"*.json "${LOCAL_DIR}/snapshots/"
