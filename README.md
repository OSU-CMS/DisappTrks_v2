# Run 3 Muon Pveto Workflow

This repository contains the scripts used to calculate the muon background veto probability (`Pveto`) for the disappearing tracks analysis using Run 3 ntuples.

The workflow is:

1. Generate EOS filelists
2. Submit HTCondor jobs
3. Run the Pveto analysis over ntuples
4. Produce per-job ROOT + JSON outputs
5. Merge JSON outputs
6. Produce LaTeX tables for the Analysis Note

---

# Main Scripts

| File | Purpose |
|---|---|
| `MuonBackground_v2_table16_pveto_json_pairfix_taujet.py` | Main Pveto analysis |
| `MergePvetoJsonAndMakeTables_v2.py` | Merge JSON outputs and make LaTeX tables |
| `make_muon_filelists.py` | Generate EOS filelists |
| `run_job.sh` | Condor worker job |
| `submit_dataset.sh` | Helper script for Condor submission |

---

# Environment Setup

Inside CMSSW:

```bash
cmsrel CMSSW_15_0_10
cd CMSSW_15_0_10/src
cmsenv
voms-proxy-init --voms cms --valid=168:00
cd DisappTrks_v2/BkgdEstimation/scripts
```

Create the local python dependency directory:

```bash
mkdir python_env

python3 -m pip install --target python_env \
    awkward \
    uproot \
    vector \
    numpy \
    fsspec-xrootd
```

Test imports:

```bash
PYTHONPATH=$PWD/python_env:$PYTHONPATH python3 -c \
"import awkward, uproot, vector, numpy, fsspec_xrootd; print('imports OK')"
```

---

# Step 1: Generate Filelists

Generate all filelists:

```bash
python3 make_muon_filelists.py --year all
```

Or a specific dataset:

```bash
python3 make_muon_filelists.py --year 2023_D
```

This creates:

```text
filelists/filelist_2023_C_Muons.txt
filelists/filelist_2023_D_Muons.txt
filelists/filelist_2024_Muons.txt
filelists/filelist_2025_Muons.txt
```

---

# Step 2: Prepare Condor Directories

Create log directories:

```bash
mkdir -p logs/2023_C
mkdir -p logs/2023_D
mkdir -p logs/2024
mkdir -p logs/2025
```

Output directories are created automatically by `run_job.sh`.

---

# Step 3: Configure JDL Files

Each dataset has its own JDL:

```text
submit_2023_C.jdl
submit_2023_D.jdl
submit_2024.jdl
submit_2025.jdl
```

The important line is:

```condor
arguments = $(ProcId) 2023_D
```

which specifies the dataset name.

The JDL should also contain:

```condor
should_transfer_files = YES
when_to_transfer_output = ON_EXIT

transfer_output_files = analysis_output
transfer_input_files = \
    MuonBackground_v2_table16_pveto_json_pairfix_taujet.py,\
    helper_functions.py,\
    filelists,\
    python_env
```

Queue size is supplied automatically by the helper script.

---

# Step 4: Submit Jobs

Use the helper script:

```bash
./submit_dataset.sh 2023_D
```

This script:

1. Reads the correct filelist
2. Counts the number of files
3. Computes the number of Condor jobs
4. Submits the jobs automatically

---

# Step 5: Monitor Jobs

Check job status:

```bash
condor_q
```

Check held jobs:

```bash
condor_q -hold
```

Remove jobs:

```bash
condor_rm <clusterid>
```

Release held jobs:

```bash
condor_release -name <schedd> <clusterid>
```

---

# Step 6: Output Files

Per-job outputs are written to:

```text
analysis_output/<dataset>/
```

Example:

```text
analysis_output/2023_D/
```

Each job produces:

```text
Muon_2023_D_Pveto_<job>.root
Muon_2023_D_Pveto_<job>.json
```

---

# Step 7: Merge JSON Outputs

After all jobs finish, merge the JSON outputs:

```bash
python3 MergePvetoJsonAndMakeTables_v2.py \
    --input-dir analysis_output/2023_D \
    --output-dir merged_output/2023_D
```

This produces:

- merged Pveto counts
- cutflow LaTeX tables
- Pveto LaTeX tables

---

# Step 8: Use the LaTeX Tables

The merge script produces `.tex` files suitable for direct inclusion into the Analysis Note.

Example:

```latex
\input{pveto_2023D_muon_v2.tex}
```

---

# Physics Notes

## Pair-Level ΔR Fix

The muon veto must be applied at the pair level:

```python
pair_dr > 0.15
```

This is implemented in:

```python
passes_muon_veto
```

inside the analysis script.

---

## Pveto Definition

The estimate uses:

```math
P_{\mathrm{veto}}
=
\frac{
(N_{\mathrm{OS}}^{\mathrm{veto}} - N_{\mathrm{SS}}^{\mathrm{veto}})
}{
(N_{\mathrm{OS}}^{\mathrm{den}} - N_{\mathrm{SS}}^{\mathrm{den}})
}
```

Negative Pveto values are clipped to zero following the analysis note convention.

---

## Tau Cleaning

Tau cleaning uses DeepTau IDs with:

- VSjet = Needs to be decided/done
- VSe = Needs to be decided/done
- VSmu = Needs to be decide/done

along with:

- decayModeFindingNewDMs
- rejection of decay modes 5 and 6

---

# Recommended .gitignore

```gitignore
python_env/
logs/
analysis_output/
merged_output/

*.root
*.json
*.out
*.err
*.log

filelists/filelist_*.txt
```

---

# Typical Workflow Example

Generate filelists:

```bash
python3 make_muon_filelists.py --year 2023_D
```

Submit jobs:

```bash
bash submit_dataset.sh 2023_D
```

Merge outputs:

```bash
python3 MergePvetoJsonAndMakeTables_v2.py \
    --input-dir analysis_output/2023_D \
    --output-dir merged_output/2023_D
```

Include table in AN:

```latex
\input{pveto_2023D_muon_v2.tex}
```
