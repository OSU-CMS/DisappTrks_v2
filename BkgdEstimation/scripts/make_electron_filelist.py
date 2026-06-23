#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path

XRD = "root://cmseosmgm01.fnal.gov:1094"
XRDFS = "root://cmseosmgm01.fnal.gov"

DATASETS = {
    "2023_C": [
        "EGamma0/2023_C_v1_EGamma0_v4",
        "EGamma0/2023_C_v2_EGamma0_v4",
        "EGamma0/2023_C_v3_EGamma0_v4",
        "EGamma0/2023_C_v4_EGamma0_v4",

        "EGamma1/2023_C_v1_EGamma1_v4",
        "EGamma1/2023_C_v2_EGamma1_v4",
        "EGamma1/2023_C_v3_EGamma1_v4",
        "EGamma1/2023_C_v4_EGamma1_v4",
    ],

    "2023_D": [
        "EGamma0/2023_D_v1_EGamma0_v4",
        "EGamma0/2023_D_v2_EGamma0_v4",
        "EGamma1/2023_D_v1_EGamma1_v4",
        "EGamma1/2023_D_v2_EGamma1_v4",
    ],

    "2024": [
        "EGamma0/2024_C_v1_EGamma0_v3",
        "EGamma0/2024_D_v1_EGamma0_v3",
        "EGamma0/2024_E_v1_EGamma0_v3",
        "EGamma0/2024_F_v1_EGamma0_v3",
        "EGamma0/2024_G_v1_EGamma0_v3",
        "EGamma0/2024_H_v1_EGamma0_v3",
        "EGamma0/2024_I_v1_EGamma0_v3",
        "EGamma0/2024_I_v2_EGamma0_v3",
        "EGamma1/2024_C_v1_EGamma1_v3",
        "EGamma1/2024_D_v1_EGamma1_v3",
        "EGamma1/2024_E_v1_EGamma1_v3",
        "EGamma1/2024_F_v1_EGamma1_v3",
        "EGamma1/2024_G_v1_EGamma1_v3",
        "EGamma1/2024_H_v1_EGamma1_v3",
        "EGamma1/2024_I_v1_EGamma1_v3",
        "EGamma1/2024_I_v2_EGamma1_v3",
    ],
    "2025": [
        "EGamma0/2025_C_v1_EGamma0_v4",
        "EGamma0/2025_C_v2_EGamma0_v4",
        "EGamma0/2025_D_v1_EGamma0_v4",
        "EGamma0/2025_E_v1_EGamma0_v4",
        "EGamma0/2025_F_v1_EGamma0_v4",
        "EGamma0/2025_F_v2_EGamma0_v4",
        "EGamma0/2025_G_v1_EGamma0_v4",
        "EGamma1/2025_C_v1_EGamma1_v4",
        "EGamma1/2025_C_v2_EGamma1_v4",
        "EGamma1/2025_D_v1_EGamma1_v4",
        "EGamma1/2025_E_v1_EGamma1_v4",
        "EGamma1/2025_F_v1_EGamma1_v4",
        "EGamma1/2025_F_v2_EGamma1_v4",
        "EGamma1/2025_G_v1_EGamma1_v4",
        "EGamma2/2025_C_v1_EGamma2_v4",
        "EGamma2/2025_C_v2_EGamma2_v4",
        "EGamma2/2025_D_v1_EGamma2_v4",
        "EGamma2/2025_E_v1_EGamma2_v4",
        "EGamma2/2025_F_v1_EGamma2_v4",
        "EGamma2/2025_F_v2_EGamma2_v4",
        "EGamma2/2025_G_v1_EGamma2_v4",
        "EGamma3/2025_C_v1_EGamma3_v4",
        "EGamma3/2025_C_v2_EGamma3_v4",
        "EGamma3/2025_D_v1_EGamma3_v4",
        "EGamma3/2025_E_v1_EGamma3_v4",
        "EGamma3/2025_F_v1_EGamma3_v4",
        "EGamma3/2025_F_v2_EGamma3_v4",
        "EGamma3/2025_G_v1_EGamma3_v4",
    ],
}

BASE = "/store/group/lpcdisapptrks/ntuplizer/"


def list_root_files(eos_dir):
    cmd = ["xrdfs", XRDFS, "ls", "-R", eos_dir]
    result = subprocess.run(cmd, text=True, capture_output=True, check=True)

    files = []
    for line in result.stdout.splitlines():
        path = line.strip()
        if path.endswith(".root"):
            files.append(f"{XRD}/{path}")

    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", choices=["2023_C", "2023_D", "2024", "2025", "all"], default="all")
    parser.add_argument("--outdir", default="filelists")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    years = DATASETS if args.year == "all" else {args.year: DATASETS[args.year]}

    for year, datasets in years.items():
        all_files = []

        for ds in datasets:
            eos_dir = f"{BASE}/{ds}"
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