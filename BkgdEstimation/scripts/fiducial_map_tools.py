#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime_warnings import filter_known_runtime_warnings

filter_known_runtime_warnings()

import awkward as ak
import numpy as np
import uproot


@dataclass(frozen=True)
class FiducialHotSpot:
    eta: float
    phi: float
    radius: float
    sigma: float


@dataclass(frozen=True)
class FiducialMap:
    path: str
    before_name: str
    after_name: str
    threshold: float
    mean_inefficiency: float
    stddev_inefficiency: float
    hot_spots: tuple[FiducialHotSpot, ...]


def delta_phi(phi1, phi2):
    return np.arctan2(np.sin(phi1 - phi2), np.cos(phi1 - phi2))


def _hist_to_numpy(root_file, hist_name):
    hist = root_file[hist_name]
    values, x_edges, y_edges = hist.to_numpy()
    return values.astype(float), x_edges.astype(float), y_edges.astype(float)


def load_fiducial_map(
    path,
    before_name="beforeVeto",
    after_name="afterVeto",
    threshold=2.0,
):
    path = str(Path(path))
    with uproot.open(path) as fin:
        before, x_edges, y_edges = _hist_to_numpy(fin, before_name)
        after, after_x_edges, after_y_edges = _hist_to_numpy(fin, after_name)

    if not np.allclose(x_edges, after_x_edges) or not np.allclose(y_edges, after_y_edges):
        raise ValueError(f"{path}: before/after fiducial histograms have different binning")

    occupied = before > 0.0
    if not np.any(occupied):
        raise ValueError(f"{path}: {before_name} has no occupied bins")

    mean = float(np.sum(after[occupied]) / np.sum(before[occupied]))
    inefficiency = np.zeros_like(after, dtype=float)
    inefficiency[occupied] = after[occupied] / before[occupied]

    n_occupied = int(np.count_nonzero(occupied))
    if n_occupied < 2:
        stddev = 0.0
    else:
        stddev = float(np.sqrt(np.sum((inefficiency[occupied] - mean) ** 2) / (n_occupied - 1)))

    hot_spots = []
    for ix, iy in np.argwhere(occupied):
        content = inefficiency[ix, iy]
        if content == 0.0 or stddev == 0.0:
            continue

        sigma = float((content - mean) / stddev)
        if (content - mean) <= threshold * stddev:
            continue

        eta = float(0.5 * (x_edges[ix] + x_edges[ix + 1]))
        phi = float(0.5 * (y_edges[iy] + y_edges[iy + 1]))
        radius = float(np.hypot(0.5 * (x_edges[ix + 1] - x_edges[ix]), 0.5 * (y_edges[iy + 1] - y_edges[iy])))
        hot_spots.append(FiducialHotSpot(eta, phi, radius, sigma))

    return FiducialMap(
        path=path,
        before_name=before_name,
        after_name=after_name,
        threshold=float(threshold),
        mean_inefficiency=mean,
        stddev_inefficiency=stddev,
        hot_spots=tuple(hot_spots),
    )


def fiducial_map_mask(arrays, fiducial_map, min_delta_r=0.05):
    mask = ak.ones_like(arrays["trk_eta"], dtype=bool)
    if fiducial_map is None:
        return mask

    for hot_spot in fiducial_map.hot_spots:
        radius = max(float(min_delta_r), hot_spot.radius)
        dr = np.sqrt(
            (arrays["trk_eta"] - hot_spot.eta) ** 2
            + delta_phi(arrays["trk_phi"], hot_spot.phi) ** 2
        )
        mask = mask & (dr >= radius)

    return mask


def combined_fiducial_map_mask(
    arrays,
    electron_map=None,
    muon_map=None,
    min_delta_r=0.05,
):
    mask = fiducial_map_mask(arrays, electron_map, min_delta_r)
    mask = mask & fiducial_map_mask(arrays, muon_map, min_delta_r)
    return mask
