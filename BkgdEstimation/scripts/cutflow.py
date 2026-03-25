#!/usr/bin/env python3
from DataFormats.FWLite import Handle, Events

events = Events('electronFiducialFilter.root')

# ── Handles for each cutflow bool ─────────────────────────────────────────────
cut_names = [
    "leptonPt",
    "leptonTriggerMatch",
    "leptonEta",
    "tightID",
    "leptonMETTransverseMass",
    "leptonD0",
    "leptonDZ",
]

handles = {name: Handle('bool') for name in cut_names}
labels  = {name: ('QualityCut', name, 'ZtoEleProbeTrk') for name in cut_names}

# ── Counters ──────────────────────────────────────────────────────────────────
counts = {name: 0 for name in cut_names}
n_total = 0

# ── Event loop ────────────────────────────────────────────────────────────────
for i, event in enumerate(events):
    n_total += 1

    for name in cut_names:
        event.getByLabel(labels[name], handles[name])
        if handles[name].isValid() and handles[name].product():
            counts[name] += 1

    if i % 1000 == 0:
        print(f"Processed {i} events...")

# ── Print cutflow table ───────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"{'Cut':<30} {'Events':>10} {'Abs. Eff.':>12} {'Rel. Eff.':>12}")
print(f"{'-'*60}")
print(f"{'Total events':<30} {n_total:>10}")

prev = n_total
for name in cut_names:
    n       = counts[name]
    abs_eff = 100.0 * n / n_total if n_total > 0 else 0.0
    rel_eff = 100.0 * n / prev    if prev    > 0 else 0.0
    print(f"{name:<30} {n:>10}  {abs_eff:>10.1f}%  {rel_eff:>10.1f}%")
    prev = n

print(f"{'='*60}\n")
