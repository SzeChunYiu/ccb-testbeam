"""MV2: truth-level range-energy calibration study."""

from __future__ import annotations

from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.studies.common import CutflowRecorder, StudyResult, StudyStatus, require_keys
from ccb_mc_validation.studies.splits import SplitRegistry, legacy_parity_split

PROTON_PDG = 2212
DEUTERON_PDG = 1000010020
MIN_REGRESSION_SAMPLES = 2000


def _stoplayer_profile(
    records: Mapping[str, np.ndarray],
    mask: np.ndarray,
    layer_max: int = 7,
    min_count: int = 10,
) -> dict[int, dict[str, float | int]]:
    """Per stop-layer mean observables for species subset."""
    profile: dict[int, dict[str, float | int]] = {}
    stop = records["stop_layer"]
    for lay in range(layer_max + 1):
        mm = mask & (stop == lay)
        if mm.sum() > min_count:
            profile[lay] = {
                "n": int(mm.sum()),
                "mean_ekin_MeV": float(records["ekin"][mm].mean()),
                "mean_edep_tot_MeV": float(records["edep_tot"][mm].mean()),
                "mean_tracklen_mm": float(records["tracklen"][mm].mean()),
            }
    return profile


def _res68(residual_fraction: np.ndarray) -> float:
    return float(np.percentile(np.abs(residual_fraction), 68))


def run_mv2(
    records: Mapping[str, np.ndarray],
    config: dict[str, Any] | None = None,
    *,
    split: SplitRegistry | None = None,
    fixture: bool = False,
) -> StudyResult:
    """
    Run MV2 range-energy study.

    Builds stop_layer vs ekin profiles per species and reconstructs entry Ekin
    with HistGradientBoostingRegressor. Reports res68 (68th percentile of
    |pred-truth|/truth).

    Censored range handling: tracks with stop_layer at the instrument boundary
    (max layer) are excluded from ekin regression because their true range is
    censored — only uncensored stopping depths enter the regressor fit.
    """
    config = config or {}
    require_keys(
        records,
        ("pdg", "ekin", "edep_l0", "edep_tot", "stop_layer", "nlayers", "tracklen"),
    )
    cutflow = CutflowRecorder()
    pdg = np.asarray(records["pdg"])
    cutflow.record("n_tracks", int(pdg.size))

    isp = pdg == PROTON_PDG
    isd = pdg == DEUTERON_PDG
    layer_max = int(config.get("layer_max", 7))
    censored_layer = layer_max

    metrics: dict[str, Any] = {
        "proton_stoplayer_vs_ekin": _stoplayer_profile(records, isp, layer_max=layer_max),
        "deuteron_stoplayer_vs_ekin": _stoplayer_profile(records, isd, layer_max=layer_max),
        "censored_range_note": (
            f"Tracks with stop_layer=={censored_layer} excluded from ekin regression "
            "(range censored at instrument boundary)."
        ),
    }
    notes = [
        metrics["censored_range_note"],
        "res68 = 68th percentile of |pred-truth|/truth on held-out split.",
    ]
    status = StudyStatus.FIXTURE if fixture else StudyStatus.PRODUCTION

    try:
        from sklearn.ensemble import HistGradientBoostingRegressor

        for species, msk in (("proton", isp), ("deuteron", isd)):
            uncensored = msk & (records["ekin"] > 0) & (records["stop_layer"] < censored_layer)
            cutflow.record(f"n_{species}_uncensored", int(uncensored.sum()))
            if uncensored.sum() < MIN_REGRESSION_SAMPLES:
                metrics[f"{species}_ekin_recon_skipped"] = int(uncensored.sum())
                continue
            X = np.column_stack(
                [
                    records["stop_layer"][uncensored].astype(float),
                    records["edep_tot"][uncensored],
                    records["edep_l0"][uncensored],
                    records["nlayers"][uncensored].astype(float),
                ]
            )
            y = records["ekin"][uncensored]
            n = len(y)
            if split is None:
                tr, te = legacy_parity_split(n)
            else:
                tr, te = split.train_test_masks(n)
            reg = HistGradientBoostingRegressor()
            reg.fit(X[tr], y[tr])
            pred = reg.predict(X[te])
            res = (pred - y[te]) / np.clip(y[te], 1e-6, None)
            metrics[f"{species}_ekin_recon_res68"] = _res68(res)
            metrics[f"{species}_ekin_mean_MeV"] = float(y.mean())
            metrics[f"{species}_n_censored_excluded"] = int(
                (msk & (records["stop_layer"] >= censored_layer)).sum()
            )
    except Exception as exc:
        metrics["_ml_error"] = str(exc)

    return StudyResult(
        study_id="MV2",
        status=status,
        metrics=metrics,
        cutflow=cutflow.as_dict(),
        notes=notes,
    )
