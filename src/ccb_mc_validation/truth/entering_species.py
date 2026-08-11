"""First-layer entering-species estimators with explicit statistical units (#1046).

Raw Sci_bar hit/step records are NOT interchangeable with unique entering
tracks. This module provides H1 (record), H2 (unique track), H3 (event
presence), and H4 (EDep-weighted) estimators side-by-side.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Mapping, MutableMapping, Optional

import numpy as np

from ccb_mc_validation.truth.pdg import species_label

CONTRACT_VERSION = "2026.0-waveB-lane03-entering-species-v1"


def accumulate_entering_species(
    *,
    pdg: np.ndarray,
    track_id: np.ndarray,
    edep: np.ndarray,
    first_layer_mask: np.ndarray,
    event_weight: float = 1.0,
    record_counts: Optional[MutableMapping[str, float]] = None,
    track_counts: Optional[MutableMapping[str, float]] = None,
    event_presence: Optional[MutableMapping[str, float]] = None,
    edep_weights: Optional[MutableMapping[str, float]] = None,
    multiplicity: Optional[list] = None,
) -> dict[str, Any]:
    """Accumulate H1–H4 counters for one event's first-layer charged hits.

    Parameters
    ----------
    first_layer_mask:
        Boolean mask over hit records selecting charged first-layer entries.
    """
    if record_counts is None:
        record_counts = defaultdict(float)
    if track_counts is None:
        track_counts = defaultdict(float)
    if event_presence is None:
        event_presence = defaultdict(float)
    if edep_weights is None:
        edep_weights = defaultdict(float)
    if multiplicity is None:
        multiplicity = []

    pdg = np.asarray(pdg)
    track_id = np.asarray(track_id)
    edep = np.asarray(edep, dtype=np.float64)
    mask = np.asarray(first_layer_mask, dtype=bool)
    if not mask.any():
        return {
            "record_counts": dict(record_counts),
            "track_counts": dict(track_counts),
            "event_presence": dict(event_presence),
            "edep_weights": dict(edep_weights),
            "multiplicity": multiplicity,
        }

    # H1: every hit/step record
    for p in pdg[mask]:
        record_counts[species_label(int(p))] = (
            record_counts.get(species_label(int(p)), 0.0) + float(event_weight)
        )

    # Unique tracks entering this layer
    tids = track_id[mask]
    present_species = set()
    for trk in np.unique(tids):
        trk_mask = mask & (track_id == trk)
        n_rec = int(trk_mask.sum())
        p0 = int(pdg[trk_mask][0])
        lab = species_label(p0)
        multiplicity.append({"track_id": int(trk), "species": lab, "n_records": n_rec})
        # H2: one count per unique TrackID
        track_counts[lab] = track_counts.get(lab, 0.0) + float(event_weight)
        # H4: EDep contribution
        edep_weights[lab] = edep_weights.get(lab, 0.0) + float(edep[trk_mask].sum()) * float(
            event_weight
        )
        present_species.add(lab)

    # H3: event-presence (one indicator per species per event)
    for lab in present_species:
        event_presence[lab] = event_presence.get(lab, 0.0) + float(event_weight)

    return {
        "record_counts": dict(record_counts),
        "track_counts": dict(track_counts),
        "event_presence": dict(event_presence),
        "edep_weights": dict(edep_weights),
        "multiplicity": multiplicity,
    }


def fractions_from_counts(counts: Mapping[str, float]) -> Dict[str, float]:
    tot = float(sum(counts.values())) or 1.0
    return {k: round(float(v) / tot, 6) for k, v in sorted(counts.items(), key=lambda kv: -kv[1])}


def entering_species_report(
    *,
    record_counts: Mapping[str, float],
    track_counts: Mapping[str, float],
    event_presence: Mapping[str, float],
    edep_weights: Mapping[str, float],
) -> dict[str, Any]:
    """Package H1–H4 with explicit statistical_unit / denominator fields."""
    return {
        "contract_version": CONTRACT_VERSION,
        "first_layer_record_fraction": {
            "statistical_unit": "hit_record",
            "denominator": "sum of first-layer charged hit/step records (weighted)",
            "physics_meaning": "transport-step representation; NOT particle flux",
            "fractions": fractions_from_counts(record_counts),
            "counts": dict(record_counts),
        },
        "enter_pid_fraction": {
            "statistical_unit": "unique_truth_track",
            "denominator": "unique (event, TrackID) entering first layer (weighted)",
            "physics_meaning": "truth particle-flux composition",
            "fractions": fractions_from_counts(track_counts),
            "counts": dict(track_counts),
        },
        "event_presence_fraction": {
            "statistical_unit": "event",
            "denominator": "accepted events with any entering track of species (weighted)",
            "physics_meaning": "probability an accepted event contains species",
            "fractions": fractions_from_counts(event_presence),
            "counts": dict(event_presence),
        },
        "edep_weighted_fraction": {
            "statistical_unit": "deposited_energy",
            "denominator": "sum of first-layer EDep by species (weighted)",
            "physics_meaning": "calorimetric composition, not flux",
            "fractions": fractions_from_counts(edep_weights),
            "counts": dict(edep_weights),
        },
        # Backward-compatible aliases: particle-flux = unique-track (H2).
        "enter_B_pid_fraction_unit": "unique_truth_track",
    }
