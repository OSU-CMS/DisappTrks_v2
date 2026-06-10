#!/usr/bin/env bash
# Resubmit failed jobs for CRAB tasks that report failures.
#
# By default scans all active *_v2 projects. Use --dry-run to preview.
#
# Usage (from BkgdEstimation/test):
#   ./scripts/crab_resubmit_failed.sh --dry-run
#   ./scripts/crab_resubmit_failed.sh
#   ./scripts/crab_resubmit_failed.sh crab_projects/2022/D/crab_2022_D_EGamma_v2
#   ./scripts/crab_resubmit_failed.sh 2022 D EGamma   # year era type filter

set -euo pipefail

DRY_RUN=0
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run|-n) DRY_RUN=1; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

if ! command -v crab >/dev/null 2>&1; then
  echo "ERROR: crab not found. Run: cd \$CMSSW_BASE/src && cmsenv" >&2
  exit 1
fi

collect_projects() {
  if [[ ${#POSITIONAL[@]} -eq 1 && -d "${POSITIONAL[0]}" ]]; then
    echo "${POSITIONAL[0]}"
    return
  fi

  local year="${POSITIONAL[0]:-}"
  local era="${POSITIONAL[1]:-}"
  local typ="${POSITIONAL[2]:-}"

  shopt -s nullglob
  local pattern="crab_projects/*/*/*_v2"
  [[ -n "$year" ]] && pattern="crab_projects/${year}/*/*_v2"

  for proj in $pattern; do
    [[ -d "$proj" ]] || continue
    case "$proj" in *_old*|*_old/*) continue ;; esac
    if [[ -n "$era" && "$(basename "$(dirname "$proj")")" != "$era" ]]; then continue; fi
    if [[ -n "$typ" && "$(basename "$proj")" != *"${typ}"* ]]; then continue; fi
    echo "$proj"
  done
}

has_failures() {
  local proj=$1
  local status
  status=$(crab status -d "$proj" 2>&1) || return 1
  # e.g. Jobs status: ... failed  0.2% (  3/1287)
  echo "$status" | grep -E 'Jobs status:.*failed.*\(\s*[1-9][0-9]*\s*/' -q
}

count_failures() {
  local proj=$1
  crab status -d "$proj" 2>&1 | grep -E 'Jobs status:.*failed' | head -1 || true
}

resubmitted=0
skipped=0

while IFS= read -r proj; do
  [[ -n "$proj" ]] || continue
  if ! has_failures "$proj"; then
    echo "SKIP (no failed jobs): $proj"
    skipped=$((skipped + 1))
    continue
  fi

  fail_line=$(count_failures "$proj")
  echo "RESUBMIT: $proj"
  echo "  $fail_line"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "  [dry-run] crab resubmit -d $proj"
  else
    crab resubmit -d "$proj"
  fi
  resubmitted=$((resubmitted + 1))
  echo
done < <(collect_projects | sort -u)

echo "Done. resubmitted=$resubmitted skipped=$skipped dry_run=$DRY_RUN"
