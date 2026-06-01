#!/bin/bash
set -e

JOBID=$1
DATASET=$2

echo "Starting job ${JOBID} for ${DATASET}"

export PYTHONPATH=$PWD/python_env:$PYTHONPATH
python3 -c "import awkward, uproot, numpy, vector, fsspec_xrootd; print('imports OK')"

FILES_PER_JOB=5

FILELIST="filelists/filelist_${DATASET}_Muons.txt"

START=$(( JOBID * FILES_PER_JOB ))
END=$(( START + FILES_PER_JOB ))

OUTDIR="analysis_output/${DATASET}"
mkdir -p "$OUTDIR"

FILES=$(sed -n "$((START+1)),$((END))p" "$FILELIST")

echo "Using filelist: $FILELIST"
echo "Files:"
echo "$FILES"

python3 MuonBackground_v2_table16_pveto_json_pairfix_taujet.py \
  --single-muon $FILES \
  --layers all \
  --output "${OUTDIR}/Muon_${DATASET}_Pveto_${JOBID}.root" \
  --json-output "${OUTDIR}/Muon_${DATASET}_Pveto_${JOBID}.json"

echo "Done job ${JOBID} for ${DATASET}"