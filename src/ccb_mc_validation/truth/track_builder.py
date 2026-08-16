"""Per-track truth records grouped from ``hibeam`` Sci_bar hits."""

from __future__ import annotations

from typing import Any

import numpy as np

from ccb_mc_validation.constants import B_ARM, NB_LAYERS
from ccb_mc_validation.truth.pdg import (
    DEFAULT_MOMENTUM_UNIT,
    is_charged,
    kinetic_energy_from_branch_momentum,
)

# ``tracklen_sum`` is the sum of per-hit ``Sci_bar_TrackLength`` values for the
# track within the B arm. Geant4 may store step length or cumulative path length
# depending on production settings; treat this field as an observable whose
# physical meaning must be validated against simulation metadata.

#: Branch carrying the per-primary MC event weight (issue #880; PR #897 wired
#: this into scripts/mc01 + compare_data_mc).  The canonical builder inherits
#: the same convention: per-event weight = first primary's weight (beam primary).
PRIMARY_WEIGHT_BRANCH: str = "PrimaryWeight"

#: Below this residual kinetic energy [MeV] a charged particle is considered to
#: have ranged out (sub-mm range in BC-408 scintillator for nuclei/protons).
#: This is a *kinetic-energy stopping criterion* used only to infer the
#: ``stop`` termination flag -- never to fit a result.
STOP_KE_THRESHOLD_MEV_DEFAULT: float = 1.0


def build_track_records(
    chunk: dict[str, np.ndarray],
    *,
    b_arm: int = B_ARM,
    n_b_layers: int = NB_LAYERS,
    momentum_unit: str = DEFAULT_MOMENTUM_UNIT,
    weight_branch: str | None = PRIMARY_WEIGHT_BRANCH,
    source: str = "",
    entry_offset: int = 0,
    stop_ke_threshold_mev: float = STOP_KE_THRESHOLD_MEV_DEFAULT,
) -> list[dict[str, Any]]:
    """Build charged B-arm track records from one ``hibeam`` chunk.

    Each record corresponds to one ``Sci_bar_TrackID`` within the B arm of one
    event.  Hits are aggregated per layer; entry kinetic energy uses momentum at
    the lowest-``LayerID`` hit, with the raw branch momentum converted from
    ``momentum_unit`` (krakow default GeV/c) to MeV/c exactly once.

    Stopping vs escape is **inferred**, never equated with the deepest observed
    layer: ``last_observed_layer`` is the observable; ``stop_layer`` is set only
    when the residual KE at the last hit is below ``stop_ke_threshold_mev``
    (``termination == "stop"``) and is ``None`` otherwise
    (``"escape"`` / ``"censored"``).

    Event/track weights are propagated from ``weight_branch`` (default
    ``PrimaryWeight``) so downstream estimands can be declared weighted; when the
    branch is absent the record is explicitly marked ``weighted=False`` with
    unit weight rather than silently dropping the weight.
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

    has_weights = weight_branch is not None and weight_branch in chunk
    weight_chunks = chunk[weight_branch] if has_weights else None

    outermost_layer = int(n_b_layers) - 1
    records: list[dict[str, Any]] = []
    for i in range(len(layer)):
        layer_i = np.asarray(layer[i])
        event_index = int(entry_offset + i)
        # Per-event (beam-primary) MC weight, matching mc01 / compare_data_mc.
        if has_weights:
            pw_i = np.asarray(weight_chunks[i]).reshape(-1)
            w_evt = float(pw_i[0]) if pw_i.size and np.isfinite(float(pw_i[0])) else 1.0
        else:
            w_evt = 1.0

        if layer_i.size == 0:
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
        event_layers = layer_i

        for track_id in np.unique(event_tid[is_b]):
            mask = is_b & (event_tid == track_id)
            p0 = int(event_pdg[mask][0])
            if not is_charged(p0):
                continue

            layers = event_layers[mask]
            eds = event_edep[mask]
            order = np.argsort(layers)
            sorted_idx = np.where(mask)[0][order]
            entry_idx = int(sorted_idx[0])
            last_idx = int(sorted_idx[-1])
            px, py, pz = event_mx[entry_idx], event_my[entry_idx], event_mz[entry_idx]
            pmag_entry = float(np.sqrt(px * px + py * py + pz * pz))
            ekin = kinetic_energy_from_branch_momentum(pmag_entry, p0, momentum_unit=momentum_unit)

            # Residual KE at the last observed hit drives stop-vs-escape.
            plx, ply, plz = event_mx[last_idx], event_my[last_idx], event_mz[last_idx]
            pmag_last = float(np.sqrt(plx * plx + ply * ply + plz * plz))
            ekin_last = kinetic_energy_from_branch_momentum(
                pmag_last, p0, momentum_unit=momentum_unit
            )

            last_observed_layer = int(layers.max())
            if ekin_last <= float(stop_ke_threshold_mev):
                termination = "stop"
                stop_layer: int | None = last_observed_layer
            elif last_observed_layer >= outermost_layer:
                termination = "escape"
                stop_layer = None
            else:
                termination = "censored"
                stop_layer = None

            edep_by_layer: dict[int, float] = {}
            for lay, e in zip(layers, eds):
                lid = int(lay)
                edep_by_layer[lid] = edep_by_layer.get(lid, 0.0) + float(e)

            records.append(
                {
                    # identifiers + provenance (TRU-005: mandatory)
                    "track_id": int(track_id),
                    "event_index": event_index,
                    "source": str(source),
                    # species + kinematics (GeV/c -> MeV/c -> KE, TRU-001)
                    "pdg": p0,
                    "ekin": ekin,
                    "ekin_last_observed": ekin_last,
                    "momentum_unit": str(momentum_unit),
                    # energy deposition
                    "edep_l0": edep_by_layer.get(0, 0.0),
                    "edep_l1": edep_by_layer.get(1, 0.0),
                    "edep_tot": float(eds.sum()),
                    # Per-layer edep vector (MV3-002 occupancy uses this as the actual
                    # per-layer hit mask via >0; unblocks the fail-closed MV3 gate).
                    "edep_per_layer": [edep_by_layer.get(lid, 0.0) for lid in range(int(n_b_layers))],
                    # stopping inference (TRU-003: observed != stopping)
                    "last_observed_layer": last_observed_layer,
                    "stop_layer": stop_layer,
                    "termination": termination,
                    "nlayers": int(len(set(layers.tolist()))),
                    "tracklen_sum": float(event_tracklen[mask].sum()),
                    # weights (TRU-004: propagated, not discarded)
                    "event_weight": float(w_evt),
                    "track_weight": float(w_evt),
                    "weighted": bool(has_weights),
                }
            )
    return records
