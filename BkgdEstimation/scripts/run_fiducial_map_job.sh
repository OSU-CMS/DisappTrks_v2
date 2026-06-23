#!/bin/bash
set -euo pipefail

JOBID=${1:?Usage: run_fiducial_map_job.sh JOBID DATASET FLAVOR TAG}
DATASET=${2:?Usage: run_fiducial_map_job.sh JOBID DATASET FLAVOR TAG}
FLAVOR=${3:?Usage: run_fiducial_map_job.sh JOBID DATASET FLAVOR TAG}
TAG=${4:?Usage: run_fiducial_map_job.sh JOBID DATASET FLAVOR TAG}

case "$FLAVOR" in
  electron|electrons|Electron|Electrons)
    FLAVOR="electron"
    INPUT_ARG="--single-electron"
    FILELIST="filelists/filelist_${DATASET}_Electrons.txt"
    ;;
  muon|muons|Muon|Muons)
    FLAVOR="muon"
    INPUT_ARG="--single-muon"
    FILELIST="filelists/filelist_${DATASET}_Muons.txt"
    ;;
  *)
    echo "Unknown flavor '${FLAVOR}'. Use electron or muon." >&2
    exit 2
    ;;
esac

echo "Starting fiducial-map job ${JOBID} for ${DATASET} ${FLAVOR}"

export PYTHONPATH="$PWD/python_env:${PYTHONPATH:-}"
python3 -c "import awkward, uproot, numpy, vector, fsspec_xrootd; from XRootD import client; print('imports OK')"

FILES_PER_JOB=${FILES_PER_JOB:-5}

if [[ ! -f "$FILELIST" ]]; then
  echo "Missing filelist: $FILELIST" >&2
  exit 1
fi

START=$((JOBID * FILES_PER_JOB))
END=$((START + FILES_PER_JOB))
mapfile -t FILES < <(sed -n "$((START + 1)),${END}p" "$FILELIST")

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No files assigned to job ${JOBID} from ${FILELIST}" >&2
  exit 1
fi

OUTDIR="analysis_output_fiducial/${DATASET}/${FLAVOR}"
mkdir -p "$OUTDIR"

EXTRA_ARGS=()
case "$DATASET" in
  2022_E|2022_F|2022_G|2022_EFG)
    if [[ "$FLAVOR" == "electron" ]]; then
      EXTRA_ARGS+=(--apply-2022-efg-water-leak-veto)
    fi
    ;;
esac

printf 'Using filelist: %s\nFiles:\n' "$FILELIST"
printf '  %s\n' "${FILES[@]}"

python3 make_fiducial_maps_v2.py \
  "$INPUT_ARG" "${FILES[@]}" \
  --flavor "$FLAVOR" \
  --layers "${FIDUCIAL_LAYERS:-combinedBins}" \
  --tag "${TAG}_${JOBID}" \
  --output-dir "$OUTDIR" \
  --json-output "${OUTDIR}/${FLAVOR}FiducialMap_${TAG}_${JOBID}.json" \
  "${EXTRA_ARGS[@]}"

echo "Done fiducial-map job ${JOBID} for ${DATASET} ${FLAVOR}"
