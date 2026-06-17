#!/usr/bin/env python3
"""Build EOS filelists for electron Pveto Condor jobs.

Usage:
    python3 make_electron_filelist.py --year 2022_C
    python3 make_electron_filelist.py --year all
"""

import argparse
import re
import subprocess
from pathlib import Path

XRD = "root://cmseosmgm01.fnal.gov:1094"
XRDFS = "root://cmseosmgm01.fnal.gov"
CRAB_DIR_RE = re.compile(r"^\d{6}_\d{6}$")
PARTIAL_NTUPE_RE = re.compile(r"ntuple_\d+-\d+\.root$")

# Paths may be relative to BASE (group EOS) or absolute (user EOS).
DATASETS = {
    "2022_C": [
        "/store/user/hazheng/DisappTrksV2/EGamma/2022_C_EGamma_v2",
    ],
    "2022_D": [
        "/store/user/hazheng/DisappTrksV2/EGamma/2022_D_EGamma_v2",
    ],
    "2022_E": [
        "/store/user/hazheng/DisappTrksV2/EGamma/2022_E_EGamma_v2",
    ],
    "2022_F": [
        "/store/user/hazheng/DisappTrksV2/EGamma/2022_F_EGamma_v2",
    ],
    "2022_G": [
        "/store/user/hazheng/DisappTrksV2/EGamma/2022_G_EGamma_v2",
    ],
}

BASE = "/store/group/lpclonglived/DisappTrks"


def xrdfs_ls(path, recursive=False):
    cmd = ["xrdfs", XRDFS, "ls"]
    if recursive:
        cmd.append("-R")
    cmd.append(path)
    result = subprocess.run(cmd, text=True, capture_output=True, check=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def latest_crab_output_dir(eos_dir):
    """Return the newest YYMMDD_HHMMSS subdir when CRAB resubmissions exist."""
    entries = xrdfs_ls(eos_dir)
    crab_dirs = [entry for entry in entries if CRAB_DIR_RE.match(Path(entry).name)]
    if not crab_dirs:
        return eos_dir
    latest = max(crab_dirs, key=lambda entry: Path(entry).name)
    print(f"  using latest CRAB output: {latest}")
    return latest


def list_root_files(eos_dir):
    source_dir = latest_crab_output_dir(eos_dir)
    files = []
    for path in xrdfs_ls(source_dir, recursive=True):
        if not path.endswith(".root"):
            continue
        if PARTIAL_NTUPE_RE.search(path):
            continue
        files.append(f"{XRD}/{path}")

    return files


def main():
    parser = argparse.ArgumentParser()
    years = sorted(DATASETS.keys())
    parser.add_argument("--year", choices=years + ["all"], default="all")
    parser.add_argument("--outdir", default="filelists")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    years = DATASETS if args.year == "all" else {args.year: DATASETS[args.year]}

    for year, datasets in years.items():
        all_files = []

        for ds in datasets:
            eos_dir = ds if ds.startswith("/") else f"{BASE}/{ds}"
            print(f"Listing {eos_dir}")
            files = list_root_files(eos_dir)
            print(f"  found {len(files)} root files")
            all_files.extend(files)

        all_files = sorted(set(all_files))

        output = outdir / f"filelist_{year}_Electrons.txt"
        with open(output, "w") as f:
            for path in all_files:
                f.write(path + "\n")

        print(f"\nWrote {len(all_files)} files to {output}\n")


if __name__ == "__main__":
    main()
