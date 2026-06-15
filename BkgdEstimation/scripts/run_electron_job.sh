#!/bin/bash
set -euo pipefail

JOBID=${1:?Usage: run_electron_job.sh JOBID DATASET}
DATASET=${2:?Usage: run_electron_job.sh JOBID DATASET}

echo "Starting electron Pveto job ${JOBID} for ${DATASET}"

export PYTHONPATH="$PWD/python_env:${PYTHONPATH:-}"
python3 -c "import awkward, uproot, numpy, vector, fsspec_xrootd; from XRootD import client; print('imports OK')"

FILES_PER_JOB=${FILES_PER_JOB:-5}
FILELIST="filelists/filelist_${DATASET}_Electrons.txt"

if [[ ! -f "$FILELIST" ]]; then
  echo "Missing electron filelist: $FILELIST" >&2
  exit 1
fi

START=$((JOBID * FILES_PER_JOB))
END=$((START + FILES_PER_JOB))
mapfile -t FILES < <(sed -n "$((START + 1)),${END}p" "$FILELIST")

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No files assigned to job ${JOBID} from ${FILELIST}" >&2
  exit 1
fi

OUTDIR="analysis_output_electron/${DATASET}"
mkdir -p "$OUTDIR"

EXTRA_ARGS=()
case "$DATASET" in
  2022_E|2022_F|2022_G|2022_EFG)
    EXTRA_ARGS+=(--apply-2022-efg-water-leak-veto)
    ;;
esac

printf 'Using filelist: %s\nFiles:\n' "$FILELIST"
printf '  %s\n' "${FILES[@]}"

python3 ElectronBackground_v2_table15_pveto_json_pairfix_taujet.py \
  --single-electron "${FILES[@]}" \
  --layers all \
  --output "${OUTDIR}/Electron_${DATASET}_Pveto_${JOBID}.root" \
  --json-output "${OUTDIR}/Electron_${DATASET}_Pveto_${JOBID}.json" \
  "${EXTRA_ARGS[@]}"

echo "Done electron Pveto job ${JOBID} for ${DATASET}"
