#!/usr/bin/env bash
# Run a local cmsRun test before submitting to CRAB.
#
# Usage (from BkgdEstimation/test, after cmsenv):
#   ./scripts/local_test.sh 2022 C Muon
#   ./scripts/local_test.sh 2022 C EGamma
#   ./scripts/local_test.sh 2022 C Tau
#   ./scripts/local_test.sh 2022 C Muon /store/data/Run2022C/Muon/.../file.root 500

set -euo pipefail

YEAR=${1:?year required (e.g. 2022)}
ERA=${2:?era required (e.g. C)}
TYPE=${3:?type required: Muon, EGamma, or Tau}
FILE=${4:-}
MAX_EVENTS=${5:-1000}

case "$TYPE" in
  Muon)   TRIGGER=SingleMuon ;;
  EGamma) TRIGGER=SingleElectron ;;
  Tau)    TRIGGER=MET ;;
  *)
    echo "Unknown type: $TYPE (use Muon, EGamma, or Tau)" >&2
    exit 1
    ;;
esac

if [[ -z "$FILE" ]]; then
  case "$YEAR-$ERA-$TYPE" in
    2022-C-Muon|2022-C-Tau)
      FILE="/store/data/Run2022C/Muon/MINIAOD/22Sep2023-v1/50000/c5509051-eba0-404d-a18d-40f60e42b418.root" ;;
    2022-C-EGamma)
      FILE="/store/data/Run2022C/EGamma/MINIAOD/22Sep2023-v1/40000/2c40d6b6-6115-4067-89c4-7e9fd9014c27.root" ;;
    2022-D-Muon|2022-D-Tau)
      FILE="/store/data/Run2022D/Muon/MINIAOD/22Sep2023-v1/2520000/77b001b7-7d84-4544-a932-2960748112d1.root" ;;
    2022-D-EGamma)
      FILE="/store/data/Run2022D/EGamma/MINIAOD/22Sep2023-v1/2530000/c82d962f-0ac2-4208-84c2-aee942daec65.root" ;;
    2022-E-Muon|2022-E-Tau)
      FILE="/store/data/Run2022E/Muon/MINIAOD/22Sep2023-v1/30000/77ded161-864a-43e4-8baf-60e51c55e860.root" ;;
    2022-E-EGamma)
      FILE="/store/data/Run2022E/EGamma/MINIAOD/22Sep2023-v1/2530000/caaf0a49-45f5-453b-8f84-f2a26d53d89a.root" ;;
    2022-F-Muon)
      FILE="/store/data/Run2022F/Muon/MINIAOD/PromptReco-v1/000/360/389/00000/ad0997b9-ff20-4b2c-9c51-1d6ef49100f4.root" ;;
    2022-F-Tau)
      FILE="/store/data/Run2022F/Muon/MINIAOD/19Dec2023-v1/2560000/5609936e-1c69-4fef-9b46-a59751b3dfa9.root" ;;
    2022-F-EGamma)
      FILE="/store/data/Run2022F/EGamma/MINIAOD/19Dec2023-v1/2560000/24434309-85ba-44f7-a28c-571596d04404.root" ;;
    2022-G-Muon)
      FILE="/store/data/Run2022G/Muon/MINIAOD/PromptReco-v1/000/362/362/00000/f6126759-0090-43f1-9746-f012d665b19d.root" ;;
    2022-G-Tau)
      FILE="/store/data/Run2022G/Muon/MINIAOD/19Dec2023-v2/80000/6eb480f7-ded6-4774-bdd0-f2c716f1b333.root" ;;
    2022-G-EGamma)
      FILE="/store/data/Run2022G/EGamma/MINIAOD/19Dec2023-v1/2560000/1349d90c-6d25-4354-8cbb-d3ea51b4008c.root" ;;
    *)
      echo "No default file for $YEAR-$ERA-$TYPE. Pass file path as 4th argument or use dasgoclient." >&2
      exit 1
      ;;
  esac
fi

if ! command -v cmsRun >/dev/null 2>&1; then
  echo "ERROR: cmsRun not found. Run: cd \$CMSSW_BASE/src && cmsenv" >&2
  exit 1
fi

LOG="/tmp/cmsRun_${YEAR}_${ERA}_${TYPE}.log"
rm -f ntuple.root

echo "Testing year=$YEAR era=$ERA type=$TYPE trigger=$TRIGGER"
echo "File: $FILE"
echo "maxEvents: $MAX_EVENTS"
echo "Log:  $LOG"

cmsRun ntuplizer_cfg.py \
  year="$YEAR" \
  era="$ERA" \
  trigger="$TRIGGER" \
  inputFiles="root://cms-xrd-global.cern.ch//$FILE" \
  maxEvents="$MAX_EVENTS" > "$LOG" 2>&1

fatal=$(grep -c 'Fatal Exception' "$LOG" || true)
jecerr=$(grep -c 'Failed to retrieve correction' "$LOG" || true)
entries=$(python3 -c "import uproot; print(uproot.open('ntuple.root')['ntuplizer/Events'].num_entries)" 2>/dev/null || echo NA)

if [[ "$fatal" -eq 0 && "$jecerr" -eq 0 ]]; then
  echo "PASS — entries in ntuple: $entries"
else
  echo "FAIL — fatal=$fatal jecerr=$jecerr entries=$entries"
  grep -E 'Fatal Exception|Failed to retrieve|Exception Message' "$LOG" | head -10
  exit 1
fi
