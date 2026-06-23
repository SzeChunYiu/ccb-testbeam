"""MV3: stopping-depth / stave profile and Sample I vs II mapping skeleton."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.studies.common import CutflowRecorder, StudyResult, StudyStatus, require_keys

# B-stack stave mapping hypotheses (LayerID → readout stave label)
DEFAULT_LAYER_TO_STAVE = {
    0: "B2",
    1: "B2",
    2: "B4",
    3: "B4",
    4: "B6",
    5: "B6",
    6: "B8",
    7: "B8",
}


def _layer_occupancy(records: Mapping[str, np.ndarray], mask: np.ndarray, n_layers: int = 8) -> np.ndarray:
    """Fraction of tracks with edep in each layer (occupancy profile)."""
    counts = np.zeros(n_layers, dtype=np.float64)
    stop = records["stop_layer"][mask]
    for lay in range(n_layers):
        counts[lay] = float((stop >= lay).sum())
    total = max(int(mask.sum()), 1)
    return counts / total


def _score_mapping_hypothesis(
    truth_profile: np.ndarray,
    data_profile: np.ndarray,
) -> float:
    """Lower is better: L1 distance between normalized occupancy profiles."""
    t = truth_profile / max(truth_profile.sum(), 1e-9)
    d = data_profile / max(data_profile.sum(), 1e-9)
    return float(np.abs(t - d).sum())


def run_mv3(
    records: Mapping[str, np.ndarray],
    config: dict[str, Any] | None = None,
    *,
    data_profiles: Mapping[str, np.ndarray] | None = None,
    fixture: bool = False,
) -> StudyResult:
    """
    Run MV3 stopping-depth profile study.

    Computes layer occupancy profiles for Sample I vs II (when sample_label present)
    and scores LayerID↔stave mapping hypotheses against optional data reference profiles.
    """
    config = config or {}
    require_keys(records, ("pdg", "stop_layer", "edep_tot"))
    cutflow = CutflowRecorder()
    pdg = np.asarray(records["pdg"])
    cutflow.record("n_tracks", int(pdg.size))

    n_layers = int(config.get("n_layers", 8))
    layer_to_stave = dict(config.get("layer_to_stave", DEFAULT_LAYER_TO_STAVE))

    sample_labels = records.get("sample_label")
    if sample_labels is not None and len(sample_labels) and str(sample_labels[0]):
        labels = np.asarray(sample_labels).astype(str)
        sample_i = labels == "I"
        sample_ii = labels == "II"
    else:
        # Fallback: split by event_id parity as placeholder Sample I/II proxy
        event_id = np.asarray(records.get("event_id", np.arange(len(pdg))))
        sample_i = event_id % 2 == 0
        sample_ii = ~sample_i
        cutflow.record("sample_proxy_event_parity", 1)

    cutflow.record("n_sample_I", int(sample_i.sum()))
    cutflow.record("n_sample_II", int(sample_ii.sum()))

    prof_i = _layer_occupancy(records, sample_i, n_layers=n_layers)
    prof_ii = _layer_occupancy(records, sample_ii, n_layers=n_layers)

    metrics: dict[str, Any] = {
        "layer_occupancy_sample_I": prof_i.tolist(),
        "layer_occupancy_sample_II": prof_ii.tolist(),
        "layer_to_stave_mapping": layer_to_stave,
        "mapping_hypothesis_scores": {},
    }

    # Aggregate truth profile by stave under current mapping hypothesis
    stave_order = sorted(set(layer_to_stave.values()))
    stave_truth = {s: 0.0 for s in stave_order}
    stop = records["stop_layer"]
    for lay, stave in layer_to_stave.items():
        stave_truth[stave] += float((stop == lay).sum())
    metrics["truth_stave_counts"] = stave_truth

    if data_profiles:
        for name, ref in data_profiles.items():
            ref_arr = np.asarray(ref, dtype=float)
            metrics["mapping_hypothesis_scores"][name] = _score_mapping_hypothesis(
                np.array([stave_truth[s] for s in stave_order]),
                ref_arr,
            )

    notes = [
        "Sample I/II from sample_label when present; else event_id parity proxy.",
        "Mapping hypothesis scoring skeleton — lower L1 score is better match to data profile.",
    ]
    status = StudyStatus.FIXTURE if fixture else StudyStatus.PRODUCTION

    return StudyResult(
        study_id="MV3",
        status=status,
        metrics=metrics,
        cutflow=cutflow.as_dict(),
        notes=notes,
    )
