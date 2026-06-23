"""Per-track truth records grouped from ``hibeam`` Sci_bar hits."""

from __future__ import annotations

from typing import Any

import numpy as np

from ccb_mc_validation.constants import B_ARM
from ccb_mc_validation.truth.pdg import is_charged, kinetic_energy_from_momentum

# ``tracklen_sum`` is the sum of per-hit ``Sci_bar_TrackLength`` values for the
# track within the B arm. Geant4 may store step length or cumulative path length
# depending on production settings; treat this field as an observable whose
# physical meaning must be validated against simulation metadata.


def build_track_records(chunk: dict[str, np.ndarray], *, b_arm: int = B_ARM) -> list[dict[str, Any]]:
    """Build charged B-arm track records from one ``hibeam`` chunk.

    Each record corresponds to one ``Sci_bar_TrackID`` within the B arm of one
    event. Hits are aggregated per layer; entry kinetic energy uses momentum at
    the lowest-``LayerID`` hit.
    """
    required = (
        "Sci_bar_TrackID",
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_TrackLength",
        "Sci_bar_Momentum_X",
        "Sci_bar_Momentum_Y",
        "Sci_bar_Momentum_Z",
    )
    missing = [key for key in required if key not in chunk]
    if missing:
        raise KeyError(f"hibeam chunk missing branches: {missing}")

    tid = chunk["Sci_bar_TrackID"]
    layer = chunk["Sci_bar_LayerID"]
    layer1 = chunk["Sci_bar_LayerID1"]
    pdg_arr = chunk["Sci_bar_PDG"]
    edep = chunk["Sci_bar_EDep"]
    tracklen = chunk["Sci_bar_TrackLength"]
    mx = chunk["Sci_bar_Momentum_X"]
    my = chunk["Sci_bar_Momentum_Y"]
    mz = chunk["Sci_bar_Momentum_Z"]

    records: list[dict[str, Any]] = []
    for i in range(len(layer)):
        l = np.asarray(layer[i])
        if l.size == 0:
            continue
        is_b = np.asarray(layer1[i]) == b_arm
        if not is_b.any():
            continue

        event_tid = np.asarray(tid[i])
        event_pdg = np.asarray(pdg_arr[i])
        event_edep = np.asarray(edep[i])
        event_tracklen = np.asarray(tracklen[i])
        event_mx = np.asarray(mx[i])
        event_my = np.asarray(my[i])
        event_mz = np.asarray(mz[i])
        event_layers = l

        for track_id in np.unique(event_tid[is_b]):
            mask = is_b & (event_tid == track_id)
            p0 = int(event_pdg[mask][0])
            if not is_charged(p0):
                continue

            layers = event_layers[mask]
            eds = event_edep[mask]
            order = np.argsort(layers)
            entry_idx = np.where(mask)[0][order[0]]
            px, py, pz = event_mx[entry_idx], event_my[entry_idx], event_mz[entry_idx]
            pmag = float(np.sqrt(px * px + py * py + pz * pz))
            ekin = kinetic_energy_from_momentum(pmag, p0)

            edep_by_layer: dict[int, float] = {}
            for lay, e in zip(layers, eds):
                lid = int(lay)
                edep_by_layer[lid] = edep_by_layer.get(lid, 0.0) + float(e)

            stop_layer = int(layers.max())
            records.append(
                {
                    "pdg": p0,
                    "ekin": ekin,
                    "edep_l0": edep_by_layer.get(0, 0.0),
                    "edep_l1": edep_by_layer.get(1, 0.0),
                    "edep_tot": float(eds.sum()),
                    "stop_layer": stop_layer,
                    "last_observed_layer": stop_layer,
                    "nlayers": int(len(set(layers.tolist()))),
                    "tracklen_sum": float(event_tracklen[mask].sum()),
                }
            )
    return records
