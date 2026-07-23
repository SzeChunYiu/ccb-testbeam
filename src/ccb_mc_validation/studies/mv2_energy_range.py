"""MV2: truth-level range-energy calibration study.

ML discipline (ML-002 / ML-003 / ML-004):

* ekin regression uses a group-disjoint split keyed by ``event_id`` (ML-002).
* Model failure -> FAILED; all-species insufficient uncensored samples ->
  BLOCKED. Never publishes ``_ml_error`` under PRODUCTION (ML-003 fail-closed;
  the validation layer additionally rejects PRODUCTION results carrying
  error/skip markers).
* HistGradientBoostingRegressor carries ``random_state`` and library versions
  are recorded in provenance (ML-004).
"""

from __future__ import annotations

import platform
from typing import Any, Mapping

import numpy as np

from ccb_mc_validation.studies.common import CutflowRecorder, StudyResult, StudyStatus, require_keys
from ccb_mc_validation.studies.splits import SplitRegistry, default_group_split

PROTON_PDG = 2212
DEUTERON_PDG = 1000010020
MIN_REGRESSION_SAMPLES = 2000
DEFAULT_SPLIT_SEED = 171101


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


def _library_versions() -> dict[str, str]:
    out: dict[str, str] = {"python": platform.python_version()}
    try:
        import numpy as _np

        out["numpy"] = _np.__version__
    except Exception:  # pragma: no cover
        pass
    try:
        import sklearn as _sk

        out["scikit-learn"] = _sk.__version__
    except Exception:
        out["scikit-learn"] = "unavailable"
    return out


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
    |pred-truth|/truth) on the held-out group-disjoint test split.

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
    full_groups = np.asarray(records.get("event_id", np.arange(len(pdg))))

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
        "res68 = 68th percentile of |pred-truth|/truth on held-out group-disjoint split (ML-002).",
    ]

    species_status: dict[str, str] = {}
    split_prov: dict[str, Any] = {}
    ml_failed = False
    ml_failure_msg = ""
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor

        for species, msk in (("proton", isp), ("deuteron", isd)):
            uncensored = msk & (records["ekin"] > 0) & (records["stop_layer"] < censored_layer)
            cutflow.record(f"n_{species}_uncensored", int(uncensored.sum()))
            if uncensored.sum() < MIN_REGRESSION_SAMPLES:
                # Per-species precondition unmet: do not publish this species'
                # res68; record the count in cutflow + a note. No skipped_ml
                # marker is emitted (ML-003).
                species_status[species] = "insufficient"
                notes.append(
                    f"{species}: ekin regression not run "
                    f"({int(uncensored.sum())} < {MIN_REGRESSION_SAMPLES} uncensored samples)."
                )
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
            groups_sub = full_groups[uncensored]
            if split is None:
                tr, te = default_group_split(groups_sub, seed=DEFAULT_SPLIT_SEED)
                split_name, split_strategy = "default_group_holdout", "group_holdout"
            else:
                tr, te = split.train_test_masks(len(y), groups=groups_sub)
                split_name, split_strategy = split.name, split.strategy
            reg = HistGradientBoostingRegressor(random_state=0)
            reg.fit(X[tr], y[tr])
            pred = reg.predict(X[te])
            res = (pred - y[te]) / np.clip(y[te], 1e-6, None)
            metrics[f"{species}_ekin_recon_res68"] = _res68(res)
            metrics[f"{species}_ekin_mean_MeV"] = float(y.mean())
            metrics[f"{species}_n_censored_excluded"] = int(
                (msk & (records["stop_layer"] >= censored_layer)).sum()
            )
            metrics[f"{species}_n_train"] = int(tr.sum())
            metrics[f"{species}_n_test"] = int(te.sum())
            species_status[species] = "ok"
            split_prov = {
                "name": split_name,
                "strategy": split_strategy,
                "group_key": "event_id",
            }
    except Exception as exc:
        ml_failed = True
        ml_failure_msg = str(exc)
        notes.append(f"ML model failure (status -> FAILED): {exc}")

    any_ok = any(v == "ok" for v in species_status.values())
    if ml_failed:
        status = StudyStatus.FAILED
        metrics["ml_failure"] = ml_failure_msg
    elif species_status and not any_ok:
        status = StudyStatus.BLOCKED
        metrics["reason"] = "all species had insufficient uncensored samples for ekin regression"
    elif fixture:
        status = StudyStatus.FIXTURE
    else:
        status = StudyStatus.PRODUCTION

    metrics["species_recon_status"] = species_status

    provenance: dict[str, Any] = {
        "estimator": "sklearn.ensemble.HistGradientBoostingRegressor(random_state=0)",
        "versions": _library_versions(),
        "min_regression_samples": MIN_REGRESSION_SAMPLES,
    }
    if split_prov:
        provenance["split"] = split_prov

    return StudyResult(
        study_id="MV2",
        status=status,
        metrics=metrics,
        cutflow=cutflow.as_dict(),
        notes=notes,
        provenance=provenance,
    )
