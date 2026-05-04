#!/usr/bin/env python3
# cutflow.py

import awkward as ak


def print_cutflow(object_cuts, event_cuts=None):
    """
    Print individual and cumulative cutflow tables for arbitrary selections.

    Parameters
    ----------
    object_cuts : list of dict
        Each dict defines one group of per-object cuts applied sequentially.
        Keys:
            "label"  : str  — group heading printed in the table
            "cuts"   : dict[str, ak.Array]  — ordered {cut_name: boolean_mask}
                       masks must be per-object (shape: events x objects)
        Groups are applied in order. An event passes a group if at least one
        object survives all cuts in that group. The surviving-object mask from
        each group is ANDed with the next group's candidates (cross-object
        requirements are not supported; use event_cuts for those).

    event_cuts : dict[str, ak.Array], optional
        Per-event boolean masks (shape: events) applied after all object_cuts.
        These are cumulative with each other and with the object selection.

    Returns
    -------
    int
        Number of events passing the full selection.

    Examples
    --------
    muon_cuts = {
        "muon: isTrigMatched": arrays["muon_isTrigMatched"],
        "muon: pt > 26":       arrays["muon_pt"] > 26,
    }
    track_cuts = {
        "trk: pt > 30":        arrays["trk_pt"] > 30,
        "trk: |eta| < 2.1":   abs(arrays["trk_eta"]) < 2.1,
    }
    n = print_cutflow(
        object_cuts=[
            {"label": "Muon cuts",  "cuts": muon_cuts},
            {"label": "Track cuts", "cuts": track_cuts},
        ],
        event_cuts={"MET > 100": met > 100},
    )
    """

    # Infer total event count from the first mask in the first group
    first_mask = next(iter(object_cuts[0]["cuts"].values()))
    n_total = len(first_mask)

    col = 50  # label column width

    def _header(title):
        print(f"\n{'=' * (col + 24)}")
        print(f"{title:^{col + 24}}")
        print(f"{'=' * (col + 24)}")

    def _divider():
        print(f"{'-' * (col + 24)}")

    def _row(label, n, denom, indent=2):
        pct = f"{n / denom:.2%}" if denom else "N/A"
        print(f"{' ' * indent}{label:<{col - indent}} {n:>8,}  {pct:>10}")

    # ── Individual yields ────────────────────────────────────────────────────
    _header("INDIVIDUAL CUT YIELDS")
    print(f"{'Cut':<{col}} {'Passing':>8}  {'Efficiency':>10}")
    _divider()

    for group in object_cuts:
        print(f"  -- {group['label']} --")
        for name, mask in group["cuts"].items():
            n = ak.sum(ak.any(mask, axis=1))
            _row(name, n, n_total)

    if event_cuts:
        print(f"  -- Event cuts --")
        for name, mask in event_cuts.items():
            _row(name, ak.sum(mask), n_total)

    # ── Cumulative cutflow ───────────────────────────────────────────────────
    _header("CUMULATIVE CUTFLOW")
    print(f"{'Cut':<{col}} {'Passing':>8}  {'Cumul. Eff.':>10}")
    _divider()
    print(f"{'Total events':<{col}} {n_total:>8,}  {'100.00%':>10}")

    cumul_event_mask = ak.Array([True] * n_total)

    for group in object_cuts:
        print(f"  -- {group['label']} --")
        cumul_obj_mask = None
        for name, mask in group["cuts"].items():
            cumul_obj_mask = mask if cumul_obj_mask is None else cumul_obj_mask & mask
            n = ak.sum(cumul_event_mask & ak.any(cumul_obj_mask, axis=1))
            _row(name, n, n_total)
        cumul_event_mask = cumul_event_mask & ak.any(cumul_obj_mask, axis=1)

    if event_cuts:
        print(f"  -- Event cuts --")
        for name, mask in event_cuts.items():
            cumul_event_mask = cumul_event_mask & mask
            _row(name, ak.sum(cumul_event_mask), n_total)

    _divider()
    final = int(ak.sum(cumul_event_mask))
    print(f"{'Final selection':<{col}} {final:>8,}  {final / n_total:>10.2%}")
    print(f"{'=' * (col + 24)}\n")

    return final
