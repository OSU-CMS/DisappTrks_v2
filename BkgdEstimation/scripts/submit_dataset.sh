#!/bin/bash

DATASET=$1
FILES_PER_JOB=5

FILELIST="filelists/filelist_${DATASET}_Muons.txt"

NFILES=$(wc -l < "$FILELIST")

NJOBS=$(( (NFILES + FILES_PER_JOB - 1) / FILES_PER_JOB ))

echo "Submitting $NJOBS jobs for $DATASET"

condor_submit submit_${DATASET}.jdl queue=$NJOBS