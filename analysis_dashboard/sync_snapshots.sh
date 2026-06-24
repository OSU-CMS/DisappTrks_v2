#!/usr/bin/env bash
set -euo pipefail

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SYNC_CONFIG_FILE:-${LOCAL_DIR}/sync_snapshots.conf}"

if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

REMOTE_HOST="${REMOTE_HOST:-cmslpc}"
REMOTE_DIR="${REMOTE_DIR:-~/DisappTrks_v2/analysis_dashboard}"
REMOTE_COLLECT="${REMOTE_COLLECT:-1}"

mkdir -p "${LOCAL_DIR}/snapshots"

if [[ "${REMOTE_COLLECT}" == "1" ]]; then
  ssh -x "${REMOTE_HOST}" "cd ${REMOTE_DIR}/../.. && eval \"\$(scramv1 runtime -sh)\" && cd ${REMOTE_DIR} && DASHBOARD_ENSURE_PROXY='${DASHBOARD_ENSURE_PROXY:-0}' DASHBOARD_PROXY_MIN_VALID='${DASHBOARD_PROXY_MIN_VALID:-4:00}' DASHBOARD_PROXY_VALID='${DASHBOARD_PROXY_VALID:-192:00}' DASHBOARD_CONDOR_HISTORY_LIMIT='${DASHBOARD_CONDOR_HISTORY_LIMIT:-200}' DASHBOARD_CONDOR_SCHEDDS='${DASHBOARD_CONDOR_SCHEDDS:-}' DASHBOARD_CRAB_TASK_GLOBS='${DASHBOARD_CRAB_TASK_GLOBS:-}' DASHBOARD_OUTPUT_MAPPING_SCRIPTS='${DASHBOARD_OUTPUT_MAPPING_SCRIPTS:-}' DASHBOARD_EOS_ENDPOINT='${DASHBOARD_EOS_ENDPOINT:-root://cmseosmgm01.fnal.gov}' DASHBOARD_EOS_ROOTS='${DASHBOARD_EOS_ROOTS:-}' bash collectors/collect_all.sh"
fi

rsync -av -e "ssh -x" "${REMOTE_HOST}:${REMOTE_DIR%/}/snapshots/"*.json "${LOCAL_DIR}/snapshots/"
