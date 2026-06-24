#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR"

DATASET=${1:?Usage: submit_fiducial_maps.sh DATASET [electron|muon|both] TAG}
REQUESTED_FLAVOR=${2:?Usage: submit_fiducial_maps.sh DATASET [electron|muon|both] TAG}
TAG=${3:?Usage: submit_fiducial_maps.sh DATASET [electron|muon|both] TAG}
FILES_PER_JOB=${FILES_PER_JOB:-5}
FIDUCIAL_LAYERS=${FIDUCIAL_LAYERS:-combinedBins}

mkdir -p "logs/${DATASET}"

submit_one() {
  local flavor=$1
  local filelist

  if [[ "$flavor" == "electron" ]]; then
    filelist="filelists/filelist_${DATASET}_Electrons.txt"
  else
    filelist="filelists/filelist_${DATASET}_Muons.txt"
  fi

  if [[ ! -f "$filelist" ]]; then
    echo "Missing filelist: $filelist" >&2
    exit 1
  fi

  local nfiles
  nfiles=$(awk 'NF {count++} END {print count+0}' "$filelist")
  local njobs=$(((nfiles + FILES_PER_JOB - 1) / FILES_PER_JOB))

  if [[ "$njobs" -eq 0 ]]; then
    echo "No input files found in $filelist" >&2
    exit 1
  fi

  echo "Submitting ${njobs} ${flavor} fiducial-map jobs for ${DATASET}"
  condor_submit \
    -append "dataset = ${DATASET}" \
    -append "flavor = ${flavor}" \
    -append "tag = ${TAG}" \
    -append "files_per_job = ${FILES_PER_JOB}" \
    -append "layers = ${FIDUCIAL_LAYERS}" \
    -append "n_jobs = ${njobs}" \
    submit_fiducial_maps.jdl

  cat <<EOF

After the Condor jobs finish, merge the partial maps with:

python3 make_fiducial_maps_v2.py \\
  --flavor ${flavor} \\
  --merge-inputs 'analysis_output_fiducial/${DATASET}/${flavor}/${flavor}FiducialMap_${TAG}_*.root' \\
  --tag ${TAG} \\
  --output-dir . \\
  --plot-dir fiducialMapPlots_${TAG} \\
  --cms-label 'CMS Preliminary' \\
  --lumi-label 'REPLACE_WITH_LUMI fb^{-1} (13.6 TeV)' \\
  --json-output ${flavor}FiducialMap_${TAG}_summary.json

EOF
}

case "$REQUESTED_FLAVOR" in
  electron|electrons|Electron|Electrons)
    submit_one electron
    ;;
  muon|muons|Muon|Muons)
    submit_one muon
    ;;
  both|Both)
    submit_one electron
    submit_one muon
    ;;
  *)
    echo "Unknown flavor '${REQUESTED_FLAVOR}'. Use electron, muon, or both." >&2
    exit 2
    ;;
esac
