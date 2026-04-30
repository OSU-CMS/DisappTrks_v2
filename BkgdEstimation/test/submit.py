#!/usr/bin/env python3
"""
Submit ntuplizer jobs via CRAB3 for all non-tau datasets in datasets.toml.

Usage:
    python submit.py [--dry-run] [--years 2022 2023 2024] [--dataset-types Muon EGamma JetMET]
"""

import os
import argparse
import subprocess
import sys
import tempfile

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli
    except ImportError:
        sys.exit("ERROR: need tomllib (Python 3.11+) or tomli (pip install tomli)")

def base_year(year):
    """Strip Pre/Post suffix: '2023Pre' -> '2023', '2022Post' -> '2022'"""
    return year.replace("Pre", "").replace("Post", "")
# ── Trigger map ───────────────────────────────────────────────────────────────
TRIGGERS = {
   "Muon":   "SingleMuon",
   "EGamma": "SingleElectron",
    # "Muon":   "MET",
    # "EGamma": "MET",
    "JetMET": "MET"

}

# ── Path constants ────────────────────────────────────────────────────────────
# Absolute path to the data directory — used for inputFiles (CRAB needs abs paths)
DATA_DIR_ABS = "DisappTrks_v2/data/"
# CMSSW-relative path to the data directory — used for pyCfgParams / FileInPath
# This must match where the files live under $CMSSW_BASE/src
CMSSW_DATA_DIR = "../../data"

# ── CRAB settings ─────────────────────────────────────────────────────────────
CRAB_STORAGE_SITE = "T3_US_FNALLPC"
CRAB_OUTPUT_BASE  = "/store/group/lpclonglived/DisappTrks/"
CFG_PATH          = "ntuplizer_cfg.py"
LUMI_MASK_BASE    = "https://cms-service-dqmdc.web.cern.ch/CAF/certification"

LUMI_MASKS = {
    "2022": f"{LUMI_MASK_BASE}/Collisions22/Cert_Collisions2022_355100_362760_Golden.json",
    "2023": f"{LUMI_MASK_BASE}/Collisions23/Cert_Collisions2023_366442_370790_Golden.json",
    "2024": f"{LUMI_MASK_BASE}/Collisions24/Cert_Collisions2024_378981_386951_Golden.json",
    "2025": f"{LUMI_MASK_BASE}/Collisions25/Cert_Collisions2025_391658_398903_Golden.json",
}


# ── Fiducial map path helpers ─────────────────────────────────────────────────
def get_fiducial_maps_cmssw(year, era):
    """CMSSW-relative paths for pyCfgParams — used by cms.FileInPath on the grid."""
    tag = f"{year}{era}_data"
    ele = f"{CMSSW_DATA_DIR}/electronFiducialMap_{tag}.root"
    mu  = f"{CMSSW_DATA_DIR}/muonFiducialMap_{tag}.root"
    return ele, mu


def get_fiducial_maps_abs(year, era):
    """Absolute paths for config.JobType.inputFiles — CRAB requires these."""
    tag = f"{year}{era}_data"
    ele = os.path.join(DATA_DIR_ABS, f"electronFiducialMap_{tag}.root")
    mu  = os.path.join(DATA_DIR_ABS, f"muonFiducialMap_{tag}.root")
    return ele, mu


# ── Dataset type detection ────────────────────────────────────────────────────
def get_dataset_type(key):
    """Return 'Muon', 'EGamma', 'JetMET', 'Tau', or None from a toml key."""
    key_upper = key.upper()
    if "TAU"    in key_upper: return "Tau"
    if "MUON"   in key_upper: return "Muon"
    if "EGAMMA" in key_upper: return "EGamma"
    if "JETMET" in key_upper: return "JetMET"
    return None


def is_sim(key):
    return "SIM" in key.upper()


# ── Parse datasets.toml ───────────────────────────────────────────────────────
def parse_datasets(toml_path):
    """
    Returns a list of dicts:
      { key, year, era, dataset_type, dataset }
    Skips Tau and SIM entries.
    """
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    entries = []

    def walk(node, path):
        if isinstance(node, dict):
            if "dataset" in node:
                key   = ".".join(path)
                dtype = get_dataset_type(key)
                if dtype is None or dtype == "Tau" or is_sim(key):
                    return
                year = path[0]
                era  = None
                for part in path[1:]:
                    if part.isalpha() and len(part) == 1:
                        era = part
                        break
                if era is None:
                    print(f"WARNING: could not determine era for {key}, skipping")
                    return
                entries.append({
                    "key":          key,
                    "year":         year,
                    "era":          era,
                    "dataset_type": dtype,
                    "dataset":      node["dataset"],
                })
            else:
                for k, v in node.items():
                    walk(v, path + [k])

    walk(data, [])
    return entries


# ── Submit one job ────────────────────────────────────────────────────────────
def submit_one(entry):
    year    = entry["year"]
    era     = entry["era"]
    dtype   = entry["dataset_type"]
    dataset = entry["dataset"]
    key     = entry["key"]

    # CMSSW-relative paths — passed via pyCfgParams so cms.FileInPath can find them
    #ele_cmssw, mu_cmssw = get_fiducial_maps_cmssw(year, era)

    # Absolute paths — passed via inputFiles so CRAB transfers them to the worker
    #ele_abs, mu_abs = get_fiducial_maps_abs(year, era)

    trigger      = TRIGGERS[dtype]
    lumi_mask    = LUMI_MASKS[base_year(year)]
    request_name = key.replace(".", "_")[-100:]


    input_files = [
        #ele_abs,
        #mu_abs,
        os.path.join(DATA_DIR_ABS, "JecConfigAK4.json"),
        os.path.join(DATA_DIR_ABS, "jer_smear.json.gz"),
        os.path.join(DATA_DIR_ABS, "JvmConfig.json"),
    ]

    cfg_text = f"""
from CRABClient.UserUtilities import config
config = config()

config.General.requestName     = '{request_name}'
config.General.workArea        = 'crab_projects/{year}/{era}'
config.General.transferOutputs = True
config.General.transferLogs    = True

config.JobType.pluginName  = 'Analysis'
config.JobType.psetName    = '{CFG_PATH}'
config.JobType.pyCfgParams = [
    'year={year}',
    'trigger={trigger}',
]
config.JobType.inputFiles = [
    '../../data/JecConfigAK4.json',
    '../../data/jer_smear.json.gz',
    '../../data/JvmConfig.json',
]
config.JobType.maxMemoryMB = 2500

config.Data.inputDataset     = '{dataset}'
config.Data.inputDBS         = 'global'
config.Data.splitting        = 'Automatic'
config.Data.unitsPerJob      = 180
config.Data.lumiMask         = '{lumi_mask}'
config.Data.outLFNDirBase    = '{CRAB_OUTPUT_BASE}'
config.Data.publication      = False
config.Data.outputDatasetTag = '{request_name}'

config.Site.storageSite = '{CRAB_STORAGE_SITE}'
config.Site.blacklist   = ['T2_FR_IPHC', 'T2_FR_GRIF']
"""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="crab_cfg_"
    ) as f:
        tmp_path = f.name
        f.write(cfg_text)

    try:
        result = subprocess.run(["crab", "submit", "--config", tmp_path])
        return result.returncode == 0
    finally:
        os.unlink(tmp_path)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Submit ntuplizer CRAB jobs")
    parser.add_argument("--toml",          default="datasets.toml")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Print what would be submitted without submitting")
    parser.add_argument("--years",         nargs="+", default=None,
                        help="Only submit for these years (e.g. 2022 2024)")
    parser.add_argument("--eras",          nargs="+", default=None,
                        help="Only submit for these eras (e.g. C D)")
    parser.add_argument("--dataset-types", nargs="+", default=None,
                        dest="dataset_types",
                        help="Only submit for these types (Muon EGamma JetMET)")
    args = parser.parse_args()

    entries = parse_datasets(args.toml)

    if args.years:
        entries = [e for e in entries if e["year"] in args.years]
    if args.eras:
        entries = [e for e in entries if e["era"] in args.eras]
    if args.dataset_types:
        entries = [e for e in entries if e["dataset_type"] in args.dataset_types]

    if not entries:
        print("No datasets matched the given filters.")
        return

    print(f"{'DRY RUN — ' if args.dry_run else ''}Submitting {len(entries)} jobs:\n")

    errors = []
    for entry in entries:
        request_name = entry['key'].replace('.', '_')[-100:]
        print(f"  [{entry['year']} Era {entry['era']}] {entry['dataset_type']:8s}  trigger={TRIGGERS.get(entry['dataset_type'], 'N/A'):6s}  request={request_name}")
        if args.dry_run:
            continue
        try:
            if not submit_one(entry):
                raise RuntimeError("crab submit returned non-zero exit code")
        except Exception as e:
            print(f"    ERROR: {e}")
            errors.append((entry["key"], str(e)))

    if errors:
        print(f"\n{len(errors)} submission(s) failed:")
        for key, msg in errors:
            print(f"  {key}: {msg}")
        sys.exit(1)
    elif not args.dry_run:
        print("\nAll jobs submitted successfully.")


if __name__ == "__main__":
    main()
