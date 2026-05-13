#!/usr/bin/env python3

import uproot
import numpy as np
import math
import argparse

def get_count(f, name):
    h = f[name]
    return h.values()[0]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    args = parser.parse_args()

    with uproot.open(args.input) as f:
        tree = f["summary"]

        num_os = tree["p_veto_num_os_value"].array(library="np")[0]
        num_ss = tree["p_veto_num_ss_value"].array(library="np")[0]
        den_os = tree["p_veto_den_os_value"].array(library="np")[0]
        den_ss = tree["p_veto_den_ss_value"].array(library="np")[0]

    numerator = num_os - num_ss
    denominator = den_os - den_ss

    if denominator <= 0:
        print("ERROR: denominator <= 0")
        return

    pveto = numerator / denominator

    # simple Poisson propagation
    num_var = num_os + num_ss
    den_var = den_os + den_ss

    rel_var = (
        num_var / numerator**2 +
        den_var / denominator**2
    )

    err = pveto * math.sqrt(rel_var)

    print("\nP_veto calculation")
    print("------------------")
    print(f"OS numerator : {num_os}")
    print(f"SS numerator : {num_ss}")
    print(f"OS denominator : {den_os}")
    print(f"SS denominator : {den_ss}")
    print()
    print(f"P_veto = {pveto:.6f} ± {err:.6f}")


if __name__ == "__main__":
    main()