#!/usr/bin/env bash
# Print a summary of all active CRAB tasks under crab_projects/.
#
# Usage (from BkgdEstimation/test):
#   ./scripts/crab_status_all.sh
#   ./scripts/crab_status_all.sh 2022          # one year only
#   ./scripts/crab_status_all.sh 2022 C Muon   # year era type filters

set -euo pipefail

YEAR_FILTER="${1:-}"
ERA_FILTER="${2:-}"
TYPE_FILTER="${3:-}"

if ! command -v crab >/dev/null 2>&1; then
  echo "ERROR: crab not found. Run: cd \$CMSSW_BASE/src && cmsenv" >&2
  exit 1
fi

shopt -s nullglob
projects=(crab_projects/*/*/*_v2)
if [[ -n "$YEAR_FILTER" ]]; then
  projects=(crab_projects/${YEAR_FILTER}/*/*_v2)
fi

found=0
for proj in "${projects[@]}"; do
  [[ -d "$proj" ]] || continue
  case "$proj" in *_old*|*_old/*) continue ;; esac

  base=$(basename "$proj")
  era=$(basename "$(dirname "$proj")")
  year=$(basename "$(dirname "$(dirname "$proj")")")

  if [[ -n "$ERA_FILTER" && "$era" != "$ERA_FILTER" ]]; then continue; fi
  if [[ -n "$TYPE_FILTER" ]]; then
    shopt -s nocasematch
    [[ "$base" == *"${TYPE_FILTER}"* ]] || continue
    shopt -u nocasematch
  fi

  found=1
  echo "========== $proj =========="
  crab status -d "$proj" 2>&1 | grep -E \
    "Task name|Status on the CRAB server|Status on the scheduler|Jobs status|failed|finished|idle|running|transferring|unsubmitted|Error Summary|exit code" \
    | head -15
  echo
done

if [[ "$found" -eq 0 ]]; then
  echo "No matching CRAB projects found."
  exit 1
fi
