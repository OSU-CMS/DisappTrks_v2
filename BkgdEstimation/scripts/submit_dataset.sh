#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

DATASET=${1:?Usage: submit_dataset.sh DATASET [muon|electron]}
FLAVOR=${2:-muon}
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

mkdir -p "logs/${DATASET}"

if "$IS_ELECTRON"; then
  SUBMIT_ARGS=("$JDL" "dataset=${DATASET}" "queue=${NJOBS}")
else
  SUBMIT_ARGS=("$JDL" "queue=${NJOBS}")
fi

echo "Submitting ${NJOBS} ${FLAVOR} jobs for ${DATASET}"
condor_submit "${SUBMIT_ARGS[@]}"
