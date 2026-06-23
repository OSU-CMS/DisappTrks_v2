#!/usr/bin/env bash
#
# CRAB monitor/resubmit template for LPC.
#
# Usage:
#   1. Copy this file to your LPC workspace.
#   2. Edit CMSSW_SRC below to point at your LPC CMSSW src directory.
#   3. Make it executable:
#        chmod +x crab_monitor_resubmit_template.sh
#   4. Create a long-lived proxy by hand:
#        voms-proxy-init --voms cms --valid 192:00 --out "$HOME/x509up_u$(id -u)"
#   5. Test manually:
#        ./crab_monitor_resubmit_template.sh
#   6. Add to cron with `crontab -e`, for example:
#        0 */3 * * * /path/to/crab_monitor_resubmit_template.sh
#
# This script checks CRAB tasks under:
#   DisappTrks_v2/BkgdEstimation/test/crab_projects/*/*/crab_*
# and resubmits only tasks whose `crab status` output reports failed jobs.

set -u

# ---- Edit this for LPC -------------------------------------------------------
# Example:
#   CMSSW_SRC="/uscms/home/YOURUSER/nobackup/CMSSW_15_0_7/src"
CMSSW_SRC="/uscms/home/mjoyce/nobackup/DisTrks/CMSSW_15_0_10/src"

# Keep the proxy in your home area so cron can find it reliably.
export X509_USER_PROXY="${X509_USER_PROXY:-$HOME/x509up_u$(id -u)}"

# ---- Usually no edits needed below this line --------------------------------
ANALYSIS_DIR="${CMSSW_SRC}/DisappTrks_v2/BkgdEstimation/test"
TASK_GLOBS=(
  "${ANALYSIS_DIR}/crab_projects/*/*/crab_*_v3"
  "${ANALYSIS_DIR}/crab_projects/*/*/crab_*_v4"
)
#TASK_GLOB="${ANALYSIS_DIR}/crab_projects/*/*/crab_*_v3"
LOGDIR="${ANALYSIS_DIR}/crab_monitor_logs"
LOCK="/tmp/${USER}_disapptrks_crab_monitor.lock"

mkdir -p "${LOGDIR}"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG="${LOGDIR}/crab_monitor_${STAMP}.log"

status_count() {
  local label="$1"
  sed -nE "s/^[[:space:]]*${label}[[:space:]].*\\(([0-9]+)\\/[0-9]+\\).*/\\1/p" | head -n 1
}

is_complete_status() {
  grep -Eiq "Status on the CRAB server:[[:space:]]+COMPLETED|Task status:[[:space:]]+COMPLETED|Jobs status:[[:space:]]+finished[[:space:]]+100(\\.0)?%"
}

{
  echo "=== CRAB monitor started: $(date) ==="
  echo "Host: $(hostname)"
  echo "CMSSW_SRC: ${CMSSW_SRC}"
  echo "ANALYSIS_DIR: ${ANALYSIS_DIR}"
  echo "TASK_GLOB: ${TASK_GLOB}"
  echo "X509_USER_PROXY: ${X509_USER_PROXY}"

  exec 9>"${LOCK}"
  if ! flock -n 9; then
    echo "Another monitor instance is already running. Exiting."
    exit 0
  fi

  if [ ! -d "${CMSSW_SRC}" ]; then
    echo "ERROR: CMSSW_SRC does not exist: ${CMSSW_SRC}"
    echo "Edit CMSSW_SRC at the top of this script."
    exit 1
  fi

  if [ ! -d "${ANALYSIS_DIR}" ]; then
    echo "ERROR: analysis directory does not exist: ${ANALYSIS_DIR}"
    echo "Check that CMSSW_SRC points at the src directory containing DisappTrks."
    exit 1
  fi

  source /cvmfs/cms.cern.ch/cmsset_default.sh

  cd "${CMSSW_SRC}" || exit 1
  eval "$(scramv1 runtime -sh)"

  cd "${ANALYSIS_DIR}" || exit 1

  if ! command -v crab >/dev/null 2>&1; then
    echo "ERROR: crab command is not available after CMSSW setup."
    exit 1
  fi

  if ! voms-proxy-info -exists -valid 8:00 >/dev/null 2>&1; then
    echo "ERROR: no valid CMS proxy with at least 8 hours left."
    echo "Create one manually:"
    echo "  voms-proxy-init --voms cms --valid 192:00 --out \"${X509_USER_PROXY}\""
    exit 1
  fi

  shopt -s nullglob
  tasks = ()
  for glob in "${TASK_GLOBS[@]}"; do
    tasks+=( ${glob} )
  done
  #tasks=( ${TASK_GLOB} )

  if [ "${#tasks[@]}" -eq 0 ]; then
    echo "No CRAB task directories found."
    exit 0
  fi

  completed_tasks=()
  failed_tasks=()
  failed_counts=()
  unfinished_tasks=()
  status_error_tasks=()
  
  for task in "${tasks[@]}"; do
    echo
    echo "---- Checking ${task} ----"

    status_out="$(crab status -d "${task}" 2>&1)"
    status_rc=$?

    echo "${status_out}"

    if [ "${status_rc}" -ne 0 ]; then
      echo "crab status failed for ${task}; skipping resubmit."
      status_error_tasks+=( "${task}" )
      continue
    fi

    failed_count="$(echo "${status_out}" | status_count "failed")"
    failed_count="${failed_count:-0}"

    if [ "${failed_count}" -gt 0 ]; then
      failed_tasks+=( "${task}" )
      failed_counts+=( "${failed_count}" )
      echo "Failed jobs detected (${failed_count}). Running crab resubmit..."
      crab resubmit -d "${task}"
    else
      echo "No failed jobs detected."
    fi

    if echo "${status_out}" | is_complete_status; then
      completed_tasks+=( "${task}" )
    elif [ "${failed_count}" -eq 0 ]; then
      unfinished_tasks+=( "${task}" )
    fi

  done

  echo
    echo "=== CRAB monitor summary ==="
  echo "Tasks checked: ${#tasks[@]}"
  echo "Completed tasks: ${#completed_tasks[@]}"
  echo "Tasks with failed jobs: ${#failed_tasks[@]}"
  echo "Tasks not complete yet / no failed jobs seen: ${#unfinished_tasks[@]}"
  echo "Tasks with crab status errors: ${#status_error_tasks[@]}"

  if [ "${#completed_tasks[@]}" -gt 0 ]; then
    echo
    echo "Completed tasks:"
    for task in "${completed_tasks[@]}"; do
      echo "  ${task}"
    done
  fi

  if [ "${#failed_tasks[@]}" -gt 0 ]; then
    echo
    echo "Tasks with failed jobs before resubmit:"
    for i in "${!failed_tasks[@]}"; do
      echo "  ${failed_tasks[$i]}: ${failed_counts[$i]} failed job(s)"
    done
  fi

  if [ "${#unfinished_tasks[@]}" -gt 0 ]; then
    echo
    echo "Tasks not complete yet / no failed jobs seen:"
    for task in "${unfinished_tasks[@]}"; do
      echo "  ${task}"
    done
  fi

  if [ "${#status_error_tasks[@]}" -gt 0 ]; then
    echo
    echo "Tasks where crab status failed:"
    for task in "${status_error_tasks[@]}"; do
      echo "  ${task}"
    done
  fi

  if [ "${#completed_tasks[@]}" -eq "${#tasks[@]}" ]; then
    echo
    echo "All monitored CRAB tasks are complete."
  fi

  echo
  echo "=== CRAB monitor finished: $(date) ==="
} >> "${LOG}" 2>&1
