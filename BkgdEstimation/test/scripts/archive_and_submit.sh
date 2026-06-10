#!/usr/bin/env bash
# Archive an existing CRAB project directory and submit a fresh task via submit.py.
# Use when crab submit fails with "workArea already exists" or after a config fix.
#
# Usage (from BkgdEstimation/test):
#   ./scripts/archive_and_submit.sh 2022 C Muon
#   ./scripts/archive_and_submit.sh 2022 F Muon
#   ./scripts/archive_and_submit.sh 2022 C EGamma --dry-run

set -euo pipefail

YEAR=${1:?year required}
ERA=${2:?era required}
TYPE=${3:?type required: Muon, EGamma, Tau, or JetMET}
DRY_RUN=()

if [[ "${4:-}" == "--dry-run" ]]; then
  DRY_RUN=(--dry-run)
fi

case "${YEAR}-${ERA}-${TYPE}" in
  2022-F-Muon) proj="crab_projects/2022/F/crab_2022_F_v1_Muon0_v2" ;;
  *)
    case "$TYPE" in
      Muon)   proj="crab_projects/${YEAR}/${ERA}/crab_${YEAR}_${ERA}_Muon_v2" ;;
      EGamma) proj="crab_projects/${YEAR}/${ERA}/crab_${YEAR}_${ERA}_EGamma_v2" ;;
      Tau)    proj="crab_projects/${YEAR}/${ERA}/crab_${YEAR}_${ERA}_Tau_v2" ;;
      *)
        echo "Unknown type: $TYPE" >&2
        exit 1
        ;;
    esac
    ;;
esac

if [[ -d "$proj" ]]; then
  stamp=$(date +%m%d_%H%M)
  mv "$proj" "${proj}_old_${stamp}"
  echo "Archived $proj -> ${proj}_old_${stamp}"
fi

python3 submit.py --years "$YEAR" --eras "$ERA" --dataset-types "$TYPE" "${DRY_RUN[@]}"
