#!/bin/bash
set -e

echo "Starting job $1"

echo "Setting up environment"
export PYTHONPATH=$PWD/python_env:$PYTHONPATH

echo "Python path:"
python3 -c "import awkward, uproot, numpy, fsspec_xrootd; print('imports OK')"

echo "Past python path part"

FILES_PER_JOB=5   # ← adjust this

START=$(( $1 * FILES_PER_JOB ))
END=$(( START + FILES_PER_JOB ))

echo "Reading files $START to $END"

# Extract this job's files
FILES=$(sed -n "$((START+1)),$((END))p" filelist_2023D_Muons.txt)

echo "Files for this job:"
echo "$FILES"

# Run your analysis
python3 muonBackgroundEstimateFromNtuples.py \
  --single-muon $FILES \
  --met $FILES \
  --output Muon_2023D_Pveto_all_layers_$1.root

echo "Done job $1"