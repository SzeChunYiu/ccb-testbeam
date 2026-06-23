"""Extract per-track truth records from GEANT4 Sci_bar hits."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

import numpy as np

B_ARM = 1

MASS = {
    2212: 938.272,
    1000010020: 1875.613,
    1000010030: 2808.921,
    1000020030: 2808.391,
    1000020040: 3727.379,
}


def mass_of(pdg: int) -> float:
    pdg = int(pdg)
    if pdg in MASS:
        return MASS[pdg]
    if abs(pdg) > 1_000_000_000:
        a = (abs(pdg) // 10) % 1000
        return a * 931.494
    return 0.511 if abs(pdg) == 11 else 139.57


@lru_cache(maxsize=None)
def charge(pdg: int) -> int:
    pdg = int(pdg)
    a = abs(pdg)
    if a > 1_000_000_000:
        return (a // 10_000) % 1000
    return {2212: 1, 2112: 0, 22: 0, 11: 1, 13: 1, 211: 1, 321: 1}.get(a, 0)


def empty_track_records() -> dict[str, list[Any]]:
    return {
        "pdg": [],
        "ekin": [],
        "edep_l0": [],
        "edep_l1": [],
        "edep_tot": [],
        "stop_layer": [],
        "nlayers": [],
        "tracklen": [],
        "event_id": [],
        "sample_label": [],
    }


def finalize_track_records(rec: dict[str, list[Any]]) -> dict[str, np.ndarray]:
    return {k: np.asarray(v) for k, v in rec.items()}


def extract_tracks_from_chunk(
    chunk: Mapping[str, Any],
    event_offset: int = 0,
    b_arm: int = B_ARM,
) -> dict[str, list[Any]]:
    """Build per-track lists from one uproot/numpy chunk."""
    rec = empty_track_records()
    tid = chunk["Sci_bar_TrackID"]
    layers = chunk["Sci_bar_LayerID"]
    l1 = chunk["Sci_bar_LayerID1"]
    pdg = chunk["Sci_bar_PDG"]
    edep = chunk["Sci_bar_EDep"]
    tracklen = chunk["Sci_bar_TrackLength"]
    mx = chunk["Sci_bar_Momentum_X"]
    my = chunk["Sci_bar_Momentum_Y"]
    mz = chunk["Sci_bar_Momentum_Z"]

    for i in range(len(layers)):
        ll = layers[i]
        if len(ll) == 0:
            continue
        is_b = l1[i] == b_arm
        if not is_b.any():
            continue
        tids = tid[i]
        pds = pdg[i]
        eds = edep[i]
        for tr in np.unique(tids[is_b]):
            mask = is_b & (tids == tr)
            p0 = int(pds[mask][0])
            if charge(p0) < 1:
                continue
            layer_vals = ll[mask]
            ed_vals = eds[mask]
            order = np.argsort(layer_vals)
            entry_idx = np.where(mask)[0][order[0]]
            px, py, pz = mx[i][entry_idx], my[i][entry_idx], mz[i][entry_idx]
            pmag = float(np.sqrt(px * px + py * py + pz * pz))
            mm = mass_of(p0)
            ekin = float(np.sqrt(pmag * pmag + mm * mm) - mm)
            el: dict[int, float] = {}
            for lay, e in zip(layer_vals, ed_vals):
                el[int(lay)] = el.get(int(lay), 0.0) + float(e)
            rec["pdg"].append(p0)
            rec["ekin"].append(ekin)
            rec["edep_l0"].append(el.get(0, 0.0))
            rec["edep_l1"].append(el.get(1, 0.0))
            rec["edep_tot"].append(float(ed_vals.sum()))
            rec["stop_layer"].append(int(layer_vals.max()))
            rec["nlayers"].append(int(len(set(layer_vals.tolist()))))
            rec["tracklen"].append(float(tracklen[i][mask].sum()))
            rec["event_id"].append(event_offset + i)
            rec["sample_label"].append("")
    return rec


def merge_track_records(base: dict[str, list[Any]], extra: dict[str, list[Any]]) -> dict[str, list[Any]]:
    for key in base:
        base[key].extend(extra.get(key, []))
    return base


def load_tracks_from_root(
    mc_path: str,
    tree_name: str = "hibeam",
    branches: list[str] | None = None,
    max_events: int = 0,
    step_size: str = "200 MB",
) -> dict[str, np.ndarray]:
    """Stream MC ROOT and return finalized track record arrays."""
    import uproot

    if branches is None:
        branches = [
            "Sci_bar_TrackID",
            "Sci_bar_LayerID",
            "Sci_bar_LayerID1",
            "Sci_bar_PDG",
            "Sci_bar_EDep",
            "Sci_bar_TrackLength",
            "Sci_bar_Momentum_X",
            "Sci_bar_Momentum_Y",
            "Sci_bar_Momentum_Z",
        ]
    tree = uproot.open(mc_path)[tree_name]
    stop = max_events if max_events > 0 else None
    rec = empty_track_records()
    event_offset = 0
    for chunk in tree.iterate(branches, step_size=step_size, library="np", entry_stop=stop):
        merge_track_records(rec, extract_tracks_from_chunk(chunk, event_offset=event_offset))
        event_offset += len(chunk["Sci_bar_LayerID"])
    return finalize_track_records(rec)
