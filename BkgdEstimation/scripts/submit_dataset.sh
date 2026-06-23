#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

DATASET=${1:?Usage: submit_dataset.sh DATASET [muon|electron] [electron_fiducial_map] [muon_fiducial_map]}
FLAVOR=${2:-muon}
ELECTRON_FIDUCIAL_MAP_ARG=${3:-${ELECTRON_FIDUCIAL_MAP:-}}
MUON_FIDUCIAL_MAP_ARG=${4:-${MUON_FIDUCIAL_MAP:-}}
FIDUCIAL_THRESHOLD_ARG=${FIDUCIAL_THRESHOLD:-2.0}
MIN_FIDUCIAL_DELTA_R_ARG=${MIN_FIDUCIAL_DELTA_R:-0.05}
FILES_PER_JOB=5

case "$FLAVOR" in
  muon|muons|Muon|Muons)
    FILELIST="filelists/filelist_${DATASET}_Muons.txt"
    JDL="submit_${DATASET}.jdl"
    IS_ELECTRON=false
    ;;
  electron|electrons|Electron|Electrons)
    FILELIST="filelists/filelist_${DATASET}_Electrons.txt"
    JDL="submit_electron.jdl"
    IS_ELECTRON=true
    ;;
  *)
    echo "Unknown flavor '${FLAVOR}'. Use muon or electron." >&2
    exit 2
    ;;
esac

if [[ ! -f "$FILELIST" ]]; then
  echo "Missing filelist: $FILELIST" >&2
  exit 1
fi

if [[ ! -f "$JDL" ]]; then
  echo "Missing Condor submit file: $JDL" >&2
  exit 1
fi

NFILES=$(awk 'NF {count++} END {print count+0}' "$FILELIST")
NJOBS=$(((NFILES + FILES_PER_JOB - 1) / FILES_PER_JOB))

if [[ "$NJOBS" -eq 0 ]]; then
  echo "No input files found in $FILELIST" >&2
  exit 1
fi

if [[ -n "$ELECTRON_FIDUCIAL_MAP_ARG" && ! -f "$ELECTRON_FIDUCIAL_MAP_ARG" ]]; then
  echo "Missing electron fiducial map: $ELECTRON_FIDUCIAL_MAP_ARG" >&2
  exit 1
fi

if [[ -n "$MUON_FIDUCIAL_MAP_ARG" && ! -f "$MUON_FIDUCIAL_MAP_ARG" ]]; then
  echo "Missing muon fiducial map: $MUON_FIDUCIAL_MAP_ARG" >&2
  exit 1
fi

ELECTRON_FIDUCIAL_MAP_JOB=""
MUON_FIDUCIAL_MAP_JOB=""
EXTRA_TRANSFER_INPUT_FILES=""

if [[ -n "$ELECTRON_FIDUCIAL_MAP_ARG" ]]; then
  ELECTRON_FIDUCIAL_MAP_JOB=$(basename "$ELECTRON_FIDUCIAL_MAP_ARG")
  EXTRA_TRANSFER_INPUT_FILES="${EXTRA_TRANSFER_INPUT_FILES},${ELECTRON_FIDUCIAL_MAP_ARG}"
fi

if [[ -n "$MUON_FIDUCIAL_MAP_ARG" ]]; then
  MUON_FIDUCIAL_MAP_JOB=$(basename "$MUON_FIDUCIAL_MAP_ARG")
  EXTRA_TRANSFER_INPUT_FILES="${EXTRA_TRANSFER_INPUT_FILES},${MUON_FIDUCIAL_MAP_ARG}"
fi

mkdir -p "logs/${DATASET}"

SUBMIT_ARGS=(
  -append "n_jobs = ${NJOBS}"
  -append "electron_fiducial_map = ${ELECTRON_FIDUCIAL_MAP_JOB}"
  -append "muon_fiducial_map = ${MUON_FIDUCIAL_MAP_JOB}"
  -append "fiducial_threshold = ${FIDUCIAL_THRESHOLD_ARG}"
  -append "min_fiducial_delta_r = ${MIN_FIDUCIAL_DELTA_R_ARG}"
  -append "extra_transfer_input_files = ${EXTRA_TRANSFER_INPUT_FILES}"
)

if "$IS_ELECTRON"; then
  SUBMIT_ARGS+=(-append "dataset = ${DATASET}")
fi

echo "Submitting ${NJOBS} ${FLAVOR} jobs for ${DATASET}"
if [[ -n "$ELECTRON_FIDUCIAL_MAP_ARG" || -n "$MUON_FIDUCIAL_MAP_ARG" ]]; then
  echo "Using fiducial maps:"
  echo "  electron: ${ELECTRON_FIDUCIAL_MAP_ARG:-none}"
  echo "  muon:     ${MUON_FIDUCIAL_MAP_ARG:-none}"
  echo "  threshold: ${FIDUCIAL_THRESHOLD_ARG}"
  echo "  min dR:    ${MIN_FIDUCIAL_DELTA_R_ARG}"
fi
condor_submit "${SUBMIT_ARGS[@]}" "$JDL"
