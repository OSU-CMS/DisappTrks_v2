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

condor_args=(
  --output-dir "${SNAPSHOT_DIR}"
  --include-history
  --history-limit "${DASHBOARD_CONDOR_HISTORY_LIMIT:-200}"
)

if [[ -n "${DASHBOARD_CONDOR_SCHEDDS:-}" ]]; then
  IFS=',' read -r -a condor_schedds <<< "${DASHBOARD_CONDOR_SCHEDDS}"
  for schedd in "${condor_schedds[@]}"; do
    if [[ -n "${schedd}" ]]; then
      condor_args+=(--schedd "${schedd}")
    fi
  done
fi

python3 "${SCRIPT_DIR}/collect_condor_status.py" "${condor_args[@]}"

crab_args=(
  --output-dir "${SNAPSHOT_DIR}"
  --workers "${DASHBOARD_CRAB_WORKERS:-8}"
  --timeout-sec "${DASHBOARD_CRAB_TIMEOUT_SEC:-120}"
)
crab_task_globs="${DASHBOARD_CRAB_TASK_GLOBS:-${APP_DIR}/../BkgdEstimation/test/crab_projects/*/*/crab_*}"
IFS=',' read -r -a crab_globs <<< "${crab_task_globs}"
for task_glob in "${crab_globs[@]}"; do
  if [[ -n "${task_glob}" ]]; then
    crab_args+=(--task-glob "${task_glob}")
  fi
done
python3 "${SCRIPT_DIR}/collect_crab_status.py" "${crab_args[@]}"

completeness_args=(
  --output-dir "${SNAPSHOT_DIR}"
  --crab-snapshot "${SNAPSHOT_DIR}/crab_latest.json"
  --endpoint "${DASHBOARD_EOS_ENDPOINT:-root://cmseosmgm01.fnal.gov}"
)
mapping_scripts="${DASHBOARD_OUTPUT_MAPPING_SCRIPTS:-${APP_DIR}/../BkgdEstimation/scripts/make_muon_filelist.py,${APP_DIR}/../BkgdEstimation/scripts/make_electron_filelist.py}"
IFS=',' read -r -a configured_mapping_scripts <<< "${mapping_scripts}"
for mapping_script in "${configured_mapping_scripts[@]}"; do
  if [[ -n "${mapping_script}" ]]; then
    completeness_args+=(--mapping-script "${mapping_script}")
  fi
done
python3 "${SCRIPT_DIR}/collect_output_completeness.py" "${completeness_args[@]}"

eos_args=(
  --output-dir "${SNAPSHOT_DIR}"
  --endpoint "${DASHBOARD_EOS_ENDPOINT:-root://cmseosmgm01.fnal.gov}"
)
eos_roots="${DASHBOARD_EOS_ROOTS:-/store/group/lpcdisapptrks/ntuplizer,/store/group/lpcdisapptrks/nano/dev,/store/group/lpcdisapptrks/nano/prod,/store/group/lpcdisapptrks/nano/sample}"
IFS=',' read -r -a configured_eos_roots <<< "${eos_roots}"
for eos_root in "${configured_eos_roots[@]}"; do
  if [[ -n "${eos_root}" ]]; then
    eos_args+=(--root "${eos_root}")
  fi
done
python3 "${SCRIPT_DIR}/collect_eos_outputs.py" "${eos_args[@]}"
