#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SNAPSHOT_DIR="${APP_DIR}/snapshots"

mkdir -p "${SNAPSHOT_DIR}"

if [[ -f /cvmfs/cms.cern.ch/cmsset_default.sh ]]; then
  # shellcheck disable=SC1091
  source /cvmfs/cms.cern.ch/cmsset_default.sh
fi

if [[ "${DASHBOARD_ENSURE_PROXY:-0}" == "1" ]]; then
  if ! command -v voms-proxy-info >/dev/null 2>&1; then
    echo "DASHBOARD_ENSURE_PROXY=1, but voms-proxy-info is not available." >&2
    exit 1
  fi

  if ! voms-proxy-info -exists -valid "${DASHBOARD_PROXY_MIN_VALID:-4:00}"; then
    voms-proxy-init --voms cms --valid "${DASHBOARD_PROXY_VALID:-192:00}"
  fi
fi

python3 "${SCRIPT_DIR}/collect_environment.py" --output-dir "${SNAPSHOT_DIR}"
python3 "${SCRIPT_DIR}/collect_condor_status.py" --output-dir "${SNAPSHOT_DIR}"
