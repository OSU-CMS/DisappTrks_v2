#!/bin/bash
set -euo pipefail

DATASET=${1:?Usage: submit_electron_dataset.sh DATASET  (e.g. 2022_C)}
FILES_PER_JOB=${FILES_PER_JOB:-5}

FILELIST="filelists/filelist_${DATASET}_Electrons.txt"

if [[ ! -f "$FILELIST" ]]; then
  echo "Missing filelist: $FILELIST" >&2
  echo "Run: python3 make_electron_filelist.py --year ${DATASET}" >&2
  exit 1
fi

NFILES=$(wc -l < "$FILELIST")
if [[ "$NFILES" -eq 0 ]]; then
  echo "Filelist is empty: $FILELIST" >&2
  exit 1
fi

NJOBS=$(( (NFILES + FILES_PER_JOB - 1) / FILES_PER_JOB ))
mkdir -p "logs/${DATASET}"

echo "Dataset:  $DATASET"
echo "Filelist: $FILELIST ($NFILES files)"
echo "Submitting $NJOBS electron Pveto jobs ($FILES_PER_JOB files/job)"

condor_submit submit_electron.jdl dataset="$DATASET" queue="$NJOBS"
