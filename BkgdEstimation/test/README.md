# CRAB submission guide — DisappTrks v2 ntuplizer

How to submit, monitor, and resubmit CRAB jobs for background-estimation ntuples.

All commands assume you start from CMSSW and the test directory:

```bash
cd ~/nobackup/CMSSW_15_0_10/src
cmsenv
cd DisappTrks_v2/BkgdEstimation/test
```

Grid proxy (if needed):

```bash
voms-proxy-init -voms cms -valid 192:00
```

---

## Files in this directory

| File | Purpose |
|------|---------|
| `submit.py` | Submit new CRAB tasks from `datasets.toml` |
| `datasets.toml` | Dataset paths per year / era / stream |
| `ntuplizer_cfg.py` | CMSSW config (year, era, trigger passed via CRAB) |
| `scripts/local_test.sh` | Local `cmsRun` sanity check before CRAB |
| `scripts/crab_status_all.sh` | Summary status for all tasks |
| `scripts/crab_resubmit_failed.sh` | Resubmit only tasks with failed jobs |
| `scripts/archive_and_submit.sh` | Archive old project dir + fresh submit |

CRAB project directories: `crab_projects/{year}/{era}/crab_*_v2/`

---

## Dataset types and triggers

| `--dataset-types` | Trigger in `ntuplizer_cfg.py` | Input dataset (2022 example) |
|-------------------|-------------------------------|------------------------------|
| `Muon` | `SingleMuon` | `/Muon/Run2022C-22Sep2023-v1/MINIAOD` |
| `EGamma` | `SingleElectron` | `/EGamma/Run2022C-22Sep2023-v1/MINIAOD` |
| `Tau` | `MET` | `/Muon/Run2022C-22Sep2023-v1/MINIAOD` (same Muon MINIAOD, MET HLT) |
| `JetMET` | `MET` | JetMET datasets in toml |

Note: names like `22Sep2023` in DBS paths are **re-miniAOD version tags**, not the collision year. All 2022 entries use `Run2022*`.

---

## 1. Local test first (recommended)

Always test the config on one file before CRAB:

```bash
./scripts/local_test.sh 2022 C Muon
./scripts/local_test.sh 2022 C EGamma
./scripts/local_test.sh 2022 C Tau
```

Optional: custom file and event count:

```bash
./scripts/local_test.sh 2022 C Muon \
  /store/data/Run2022C/Muon/MINIAOD/22Sep2023-v1/50000/c5509051-eba0-404d-a18d-40f60e42b418.root \
  1000
```

Manual equivalent:

```bash
cmsRun ntuplizer_cfg.py \
  year=2022 era=C trigger=SingleMuon \
  inputFiles=root://cms-xrd-global.cern.ch//store/data/Run2022C/Muon/MINIAOD/22Sep2023-v1/50000/c5509051-eba0-404d-a18d-40f60e42b418.root \
  maxEvents=1000
```

PASS = exit 0, no `Fatal Exception`, no `Failed to retrieve correction`.

---

## 2. Submit new CRAB jobs

Preview what would be submitted:

```bash
python3 submit.py --dry-run --years 2022 --dataset-types Muon
```

Submit:

```bash
# All 2022 muon eras
python3 submit.py --years 2022 --dataset-types Muon

# Single era
python3 submit.py --years 2022 --eras C --dataset-types Muon

# Electron + tau (MET) for all 2022 eras
python3 submit.py --years 2022 --dataset-types EGamma Tau

# Everything in toml for 2022 (Muon + EGamma + Tau)
python3 submit.py --years 2022
```

Output goes to `/store/user/hazheng/DisappTrksV2/` on `T3_US_FNALLPC`.

If submit fails with **"workArea already exists"**, archive the old project and resubmit:

```bash
./scripts/archive_and_submit.sh 2022 C Muon
```

---

## 3. Check job status

One task:

```bash
crab status -d crab_projects/2022/C/crab_2022_C_Muon_v2
```

All active tasks (summary):

```bash
./scripts/crab_status_all.sh
./scripts/crab_status_all.sh 2022
./scripts/crab_status_all.sh 2022 C Muon
```

Verbose errors for a failing task:

```bash
crab status -d crab_projects/2022/C/crab_2022_C_Muon_v2 --verboseErrors
```

Get log from one failed job:

```bash
crab getlog -d crab_projects/2022/C/crab_2022_C_Muon_v2 --jobids=479
```

### Scheduler states

| Status | Meaning |
|--------|---------|
| `SUBMITTED` | Running on grid (idle / running / transferring) |
| `COMPLETED` | All jobs finished successfully |
| `FAILED` | Task failed (often all jobs dead — check errors) |

---

## 4. Resubmit failed jobs

### A. A few jobs failed (task mostly OK)

Typical for exit **8901** (`UnexpectedJobTermination` — transient grid issue).

Resubmit **failed jobs only** for one task:

```bash
crab resubmit -d crab_projects/2022/D/crab_2022_D_EGamma_v2
```

Resubmit all tasks that currently have failures:

```bash
# Preview
./scripts/crab_resubmit_failed.sh --dry-run

# Actually resubmit
./scripts/crab_resubmit_failed.sh

# Filter by year / era / type
./scripts/crab_resubmit_failed.sh 2022 D EGamma
```

Wait until a task is `COMPLETED` or idle before resubmitting again.

### B. All jobs failed (config bug)

Example: exit **8002** with `Failed to retrieve correction "Summer22_..."`.

1. Fix config (e.g. `DisappTrks_v2/data/JecConfigAK4.json` JEC tags).
2. Run `./scripts/local_test.sh` to verify.
3. **Do not** `crab resubmit` on the broken task — submit fresh:

```bash
./scripts/archive_and_submit.sh 2022 C Muon
```

Or manually:

```bash
mv crab_projects/2022/C/crab_2022_C_Muon_v2 crab_projects/2022/C/crab_2022_C_Muon_v2_old
python3 submit.py --years 2022 --eras C --dataset-types Muon
```

### C. Stop a running task

```bash
crab kill -d crab_projects/2022/C/crab_2022_C_Muon_v2
```

---

## 5. Common exit codes

| Code | Meaning | Action |
|------|---------|--------|
| **8002** | CMSSW exception (config/JEC/etc.) | Fix config, local test, **fresh submit** |
| **8901** | Unexpected job termination | `crab resubmit` (transient) |
| **713** / **8028** | Grid / site issues | `crab resubmit` |

Reference: [CMS JobExitCodes](https://twiki.cern.ch/twiki/bin/viewauth/CMSPublic/JobExitCodes)

---

## 6. 2022 project name cheat sheet

| Era | Muon | EGamma | Tau (MET on Muon MINIAOD) |
|-----|------|--------|----------------------------|
| C | `crab_2022_C_Muon_v2` | `crab_2022_C_EGamma_v2` | `crab_2022_C_Tau_v2` |
| D | `crab_2022_D_Muon_v2` | `crab_2022_D_EGamma_v2` | `crab_2022_D_Tau_v2` |
| E | `crab_2022_E_Muon_v2` | `crab_2022_E_EGamma_v2` | `crab_2022_E_Tau_v2` |
| F | `crab_2022_F_v1_Muon0_v2` | `crab_2022_F_EGamma_v2` | `crab_2022_F_Tau_v2` |
| G | `crab_2022_G_Muon_v2` | `crab_2022_G_EGamma_v2` | `crab_2022_G_Tau_v2` |

Example status loop for all 2022 muon:

```bash
for era in C D E F G; do
  case $era in
    F) d=crab_projects/2022/F/crab_2022_F_v1_Muon0_v2 ;;
    *) d=crab_projects/2022/$era/crab_2022_${era}_Muon_v2 ;;
  esac
  echo "=== Muon $era ==="
  crab status -d "$d" 2>&1 | grep -E "scheduler|Jobs status|failed|finished"
  echo
done
```

---

## 7. Typical workflow (2022 example)

```bash
# 1. Setup
cd ~/nobackup/CMSSW_15_0_10/src && cmsenv
cd DisappTrks_v2/BkgdEstimation/test

# 2. Local test each stream you plan to submit
for t in Muon EGamma Tau; do
  ./scripts/local_test.sh 2022 C "$t"
done

# 3. Submit
python3 submit.py --years 2022 --eras C --dataset-types Muon EGamma Tau

# 4. Monitor
./scripts/crab_status_all.sh 2022 C

# 5. After completion, resubmit any stragglers
./scripts/crab_resubmit_failed.sh 2022 C
```

---

## 8. Checkwrite (once per site/LFN)

```bash
export DISAPP_CRAB_STORAGE_SITE=T3_US_FNALLPC
export DISAPP_CRAB_OUTPUT_LFN=/store/user/hazheng/DisappTrksV2/
crab checkwrite --site="$DISAPP_CRAB_STORAGE_SITE" --lfn="$DISAPP_CRAB_OUTPUT_LFN"
```

Make scripts executable after clone:

```bash
chmod +x scripts/*.sh
```
