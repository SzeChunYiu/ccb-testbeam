#!/usr/bin/env python3
"""Weighted, selection-matched MV3 stopping-depth diagnostic.

The primary MC result applies exactly one finite, non-negative ``PrimaryWeight``
per event and uses the canonical signed-charge predicate.  Unweighted outputs
are retained only as labelled sensitivities.  A single run is diagnostic: it
cannot upgrade canonical CL-021 without immutable-input reruns, covariance and
parameter scans, and claim-ledger review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shlex
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

COINC_NS = float(os.environ.get("MV3_COINC_NS", "15.0"))
GAIN = float(os.environ.get("MV3_GAIN", "92.0"))
PEAK_FRAC = float(os.environ.get("MV3_PEAK_FRAC", "0.7330"))
THRESHOLD_ADC = float(os.environ.get("MV3_THRESHOLD_ADC", "1000.0"))
STOP_KE_MEV = float(os.environ.get("MV3_STOP_KE_MEV", "1.0"))

STAVES = ("B2", "B4", "B6", "B8")
LAYER_TO_STAVE_IDX = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3}
B_ARM = 1
A_ARM = 2
NB_LAYERS = 8
POLICY = "MV3_SELECTION_WEIGHTED_SIGNED_CHARGE_SAME_TARGET_V2"


class ContractError(RuntimeError):
    """Controlled scientific-input or publication-contract failure."""


def _finite_float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"NONNUMERIC:{label}:{value!r}") from exc
    if not math.isfinite(result):
        raise ContractError(f"NONFINITE:{label}:{value!r}")
    return result


def _event_weight(raw: Any, event_index: int) -> float:
    values = np.asarray(raw, dtype=float).reshape(-1)
    if values.size != 1:
        raise ContractError(
            f"PRIMARYWEIGHT_CARDINALITY:event={event_index}:observed={values.size}:expected=1"
        )
    weight = _finite_float(values[0], f"PrimaryWeight[{event_index}]")
    if weight < 0.0:
        raise ContractError(f"NEGATIVE_PRIMARYWEIGHT:event={event_index}:value={weight}")
    return weight


def _profile_fraction(counts: dict[str, float]) -> dict[str, float]:
    total = math.fsum(float(counts.get(stave, 0.0)) for stave in STAVES)
    if total <= 0.0:
        return {stave: 0.0 for stave in STAVES}
    return {stave: float(counts.get(stave, 0.0)) / total for stave in STAVES}


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    if values.size == 0:
        return float("nan")
    total = math.fsum(float(value) for value in weights)
    if total <= 0.0:
        return float("nan")
    return math.fsum(float(value * weight) for value, weight in zip(values, weights)) / total


def _weighted_corr(x: Iterable[float], y: Iterable[float], w: Iterable[float]) -> float:
    xa = np.asarray(list(x), dtype=float)
    ya = np.asarray(list(y), dtype=float)
    wa = np.asarray(list(w), dtype=float)
    mask = np.isfinite(xa) & np.isfinite(ya) & np.isfinite(wa) & (wa >= 0.0)
    xa = xa[mask]
    ya = ya[mask]
    wa = wa[mask]
    if xa.size < 3 or math.fsum(float(value) for value in wa) <= 0.0:
        return float("nan")
    mx = _weighted_mean(xa, wa)
    my = _weighted_mean(ya, wa)
    cov = math.fsum(float(weight * (xv - mx) * (yv - my)) for xv, yv, weight in zip(xa, ya, wa))
    vx = math.fsum(float(weight * (xv - mx) ** 2) for xv, weight in zip(xa, wa))
    vy = math.fsum(float(weight * (yv - my) ** 2) for yv, weight in zip(ya, wa))
    if vx <= 0.0 or vy <= 0.0:
        return float("nan")
    return cov / math.sqrt(vx * vy)


def _weighted_quantile(values: Iterable[float], weights: Iterable[float], q: float) -> float:
    va = np.asarray(list(values), dtype=float)
    wa = np.asarray(list(weights), dtype=float)
    mask = np.isfinite(va) & np.isfinite(wa) & (wa >= 0.0)
    va = va[mask]
    wa = wa[mask]
    if va.size == 0 or not 0.0 <= q <= 1.0:
        return float("nan")
    order = np.argsort(va, kind="mergesort")
    va = va[order]
    wa = wa[order]
    total = float(wa.sum())
    if total <= 0.0:
        return float("nan")
    cumulative = np.cumsum(wa)
    index = int(np.searchsorted(cumulative, q * total, side="left"))
    return float(va[min(index, va.size - 1)])


def _chi2(mc_frac: dict[str, float], data_counts: dict[str, float]) -> tuple[float, int, float]:
    mc = np.asarray([mc_frac.get(stave, 0.0) for stave in STAVES], dtype=float)
    observed = np.asarray([data_counts.get(stave, 0.0) for stave in STAVES], dtype=float)
    if not np.all(np.isfinite(mc)) or not np.all(np.isfinite(observed)):
        raise ContractError("NONFINITE_CHI2_INPUT")
    if np.any(mc < 0.0) or np.any(observed < 0.0):
        raise ContractError("NEGATIVE_CHI2_INPUT")
    expected = mc * observed.sum()
    # Pearson model support (salvaged from chatgpt PR #933): fail-closed when
    # observed data has counts where the model predicts zero probability, and
    # when model fractions are not normalized.
    if not np.isclose(mc.sum(), 1.0, atol=1e-6):
        raise ContractError(f"UNNORMALIZED_MODEL_FRACTIONS: sum={mc.sum():.6f}")
    unsupported = (expected == 0.0) & (observed > 0.0)
    if np.any(unsupported):
        bad = [STAVES[i] for i in range(len(STAVES)) if unsupported[i]]
        raise ContractError(f"UNSUPPORTED_OBSERVED_CATEGORIES:{bad}")
    positive = expected > 0.0
    ndf = int(positive.sum()) - 1
    if ndf <= 0:
        raise ContractError("NONPOSITIVE_CHI2_NDF")
    chi2 = float(np.sum((observed[positive] - expected[positive]) ** 2 / expected[positive]))
    return chi2, ndf, chi2 / ndf


def _new_bag() -> dict[str, Any]:
    return {
        "n_events": 0,
        "n_no_fire": 0,
        "n_zero_weight": 0,
        "sum_w": 0.0,
        "sum_w2": 0.0,
        "stop_depth_counts": {stave: 0.0 for stave in STAVES},
        "unweighted_stop_depth_counts": {stave: 0 for stave in STAVES},
        "truth_stop_counts": {stave: 0.0 for stave in STAVES},
        "unweighted_truth_stop_counts": {stave: 0 for stave in STAVES},
        "truth_n_stop": 0,
        "truth_n_escape_censored": 0,
        "dE_mev": [],
        "E_mev": [],
        "weights": [],
        "entry_ekin_mev": [],
        "entry_ekin_weights": [],
    }


def _accumulate(
    bag: dict[str, Any],
    *,
    weight: float,
    observable_depth: str | None,
    truth_depth: str | None,
    truth_term: str,
    d_e: float,
    e_res: float,
    entry_ekin: float,
) -> None:
    bag["n_events"] += 1
    bag["sum_w"] += weight
    bag["sum_w2"] += weight * weight
    if weight == 0.0:
        bag["n_zero_weight"] += 1
    if observable_depth is None:
        bag["n_no_fire"] += 1
    else:
        bag["stop_depth_counts"][observable_depth] += weight
        bag["unweighted_stop_depth_counts"][observable_depth] += 1
    bag["dE_mev"].append(d_e)
    bag["E_mev"].append(e_res)
    bag["weights"].append(weight)
    if truth_term == "stop" and truth_depth is not None:
        bag["truth_stop_counts"][truth_depth] += weight
        bag["unweighted_truth_stop_counts"][truth_depth] += 1
        bag["truth_n_stop"] += 1
    else:
        bag["truth_n_escape_censored"] += 1
    if math.isfinite(entry_ekin):
        bag["entry_ekin_mev"].append(entry_ekin)
        bag["entry_ekin_weights"].append(weight)


def _finalize_bag(bag: dict[str, Any]) -> dict[str, Any]:
    sum_w = float(bag["sum_w"])
    sum_w2 = float(bag["sum_w2"])
    if sum_w <= 0.0 or sum_w2 <= 0.0:
        raise ContractError("NONPOSITIVE_SELECTION_WEIGHT_SUM")
    d_e = np.asarray(bag["dE_mev"], dtype=float)
    e_res = np.asarray(bag["E_mev"], dtype=float)
    weights = np.asarray(bag["weights"], dtype=float)
    both = (d_e > 0.0) & (e_res > 0.0)
    entry = bag["entry_ekin_mev"]
    entry_w = bag["entry_ekin_weights"]
    return {
        "n_events": int(bag["n_events"]),
        "n_no_fire": int(bag["n_no_fire"]),
        "n_zero_weight": int(bag["n_zero_weight"]),
        "sum_w": sum_w,
        "sum_w2": sum_w2,
        "effective_sample_size": sum_w * sum_w / sum_w2,
        "stop_depth_counts": {stave: float(bag["stop_depth_counts"][stave]) for stave in STAVES},
        "stop_depth_frac": _profile_fraction(bag["stop_depth_counts"]),
        "unweighted_stop_depth_counts": {
            stave: int(bag["unweighted_stop_depth_counts"][stave]) for stave in STAVES
        },
        "unweighted_stop_depth_frac": _profile_fraction(bag["unweighted_stop_depth_counts"]),
        "truth_stop_counts": {stave: float(bag["truth_stop_counts"][stave]) for stave in STAVES},
        "truth_stop_frac": _profile_fraction(bag["truth_stop_counts"]),
        "unweighted_truth_stop_counts": {
            stave: int(bag["unweighted_truth_stop_counts"][stave]) for stave in STAVES
        },
        "unweighted_truth_stop_frac": _profile_fraction(
            bag["unweighted_truth_stop_counts"]
        ),
        "truth_n_stop": int(bag["truth_n_stop"]),
        "truth_n_escape_censored": int(bag["truth_n_escape_censored"]),
        "dE_E_n_both_fire": int(both.sum()),
        "dE_E_corr_both_fire": _weighted_corr(d_e[both], e_res[both], weights[both]),
        "dE_E_corr_both_fire_unweighted": (
            float(np.corrcoef(d_e[both], e_res[both])[0, 1]) if both.sum() > 2 else float("nan")
        ),
        "entry_ekin_median_mev": _weighted_quantile(entry, entry_w, 0.5),
        "entry_ekin_p10_mev": _weighted_quantile(entry, entry_w, 0.1),
        "entry_ekin_p90_mev": _weighted_quantile(entry, entry_w, 0.9),
    }


def analyze_mc(mc_path: str, tree: str = "hibeam", max_events: int = 0) -> dict[str, Any]:
    """Build weighted physical and unweighted sensitivity profiles per selection."""
    import uproot
    from ccb_mc_validation.truth.pdg import (
        DEFAULT_MOMENTUM_UNIT,
        is_charged,
        kinetic_energy_from_branch_momentum,
    )

    branches = [
        "Sci_bar_LayerID",
        "Sci_bar_LayerID1",
        "Sci_bar_PDG",
        "Sci_bar_EDep",
        "Sci_bar_Time",
        "Sci_bar_TrackID",
        "Sci_bar_Momentum_X",
        "Sci_bar_Momentum_Y",
        "Sci_bar_Momentum_Z",
        "PrimaryWeight",
    ]
    tree_obj = uproot.open(mc_path)[tree]
    entry_stop = max_events if max_events > 0 else None
    bags = {name: _new_bag() for name in ("unselected", "sample_ii", "sample_i")}
    counters = {"n_total_events": 0, "n_enterB": 0, "n_enterA": 0, "n_coincidence": 0}

    for chunk in tree_obj.iterate(
        branches, step_size="200 MB", library="np", entry_stop=entry_stop
    ):
        layer = chunk["Sci_bar_LayerID"]
        arm = chunk["Sci_bar_LayerID1"]
        pdg = chunk["Sci_bar_PDG"]
        edep = chunk["Sci_bar_EDep"]
        time = chunk["Sci_bar_Time"]
        track_id = chunk["Sci_bar_TrackID"]
        mx = chunk["Sci_bar_Momentum_X"]
        my = chunk["Sci_bar_Momentum_Y"]
        mz = chunk["Sci_bar_Momentum_Z"]
        primary_weight = chunk["PrimaryWeight"]
        for index in range(len(layer)):
            counters["n_total_events"] += 1
            arrays = [
                layer[index], arm[index], pdg[index], edep[index], time[index],
                track_id[index], mx[index], my[index], mz[index],
            ]
            lengths = {len(values) for values in arrays}
            if len(lengths) != 1:
                raise ContractError(
                    f"HIT_BRANCH_CARDINALITY:event={index}:lengths={sorted(lengths)}"
                )
            weight = _event_weight(primary_weight[index], counters["n_total_events"] - 1)
            if len(arrays[0]) == 0:
                continue
            l, a, p, e, t, tid, px, py, pz = arrays
            if not np.all(np.isfinite(np.asarray(e, dtype=float))):
                raise ContractError(f"NONFINITE_EDEP:event={index}")
            charged = np.asarray([is_charged(int(value)) for value in p], dtype=bool)
            is_b = np.asarray(a) == B_ARM
            is_a = np.asarray(a) == A_ARM
            first_b = is_b & (np.asarray(l) == 0) & charged
            first_a = is_a & (np.asarray(l) == 0) & charged
            enter_b = bool(first_b.any())
            enter_a = bool(first_a.any())
            t_b = float(np.min(np.asarray(t)[first_b])) if enter_b else float("nan")
            t_a = float(np.min(np.asarray(t)[first_a])) if enter_a else float("nan")
            coinc = enter_b and enter_a and abs(t_a - t_b) < COINC_NS
            counters["n_enterB"] += int(enter_b)
            counters["n_enterA"] += int(enter_a)
            counters["n_coincidence"] += int(coinc)
            selections = ["unselected"]
            if enter_b:
                selections.append("sample_ii")
            if coinc:
                selections.append("sample_i")

            b_charged = is_b & charged
            if not b_charged.any():
                continue
            stave_edep = np.zeros(4, dtype=float)
            for track in np.unique(np.asarray(tid)[b_charged]):
                mask = b_charged & (np.asarray(tid) == track)
                track_edep = np.zeros(4, dtype=float)
                for layer_id, value in zip(np.asarray(l)[mask], np.asarray(e)[mask]):
                    stave_index = LAYER_TO_STAVE_IDX.get(int(layer_id), -1)
                    if stave_index >= 0:
                        track_edep[stave_index] += float(value)
                stave_edep = np.maximum(stave_edep, track_edep)
            above = np.flatnonzero(stave_edep * GAIN * PEAK_FRAC > THRESHOLD_ADC)
            observable_depth = STAVES[int(above.max())] if above.size else None

            truth_depth = None
            truth_term = "escape"
            best_energy = -1.0
            for track in np.unique(np.asarray(tid)[b_charged]):
                mask = b_charged & (np.asarray(tid) == track)
                track_energy = float(np.sum(np.asarray(e)[mask]))
                if track_energy <= best_energy or track_energy <= 0.0:
                    continue
                best_energy = track_energy
                hit_indices = np.flatnonzero(mask)
                last_index = hit_indices[np.argmax(np.asarray(l)[mask])]
                momentum = math.sqrt(float(px[last_index]) ** 2 + float(py[last_index]) ** 2 +
                                     float(pz[last_index]) ** 2)
                last_ke = kinetic_energy_from_branch_momentum(
                    momentum, int(p[last_index]), momentum_unit=DEFAULT_MOMENTUM_UNIT
                )
                last_layer = int(l[last_index])
                if last_ke <= STOP_KE_MEV:
                    truth_term = "stop"
                    truth_depth = STAVES[LAYER_TO_STAVE_IDX[last_layer]]
                elif last_layer >= NB_LAYERS - 1:
                    truth_term = "escape"
                    truth_depth = None
                else:
                    truth_term = "censored"
                    truth_depth = None

            entry_ekin = float("nan")
            if enter_b:
                first_index = int(np.flatnonzero(first_b)[0])
                momentum = math.sqrt(float(px[first_index]) ** 2 + float(py[first_index]) ** 2 +
                                     float(pz[first_index]) ** 2)
                entry_ekin = kinetic_energy_from_branch_momentum(
                    momentum, int(p[first_index]), momentum_unit=DEFAULT_MOMENTUM_UNIT
                )
            for selection in selections:
                _accumulate(
                    bags[selection],
                    weight=weight,
                    observable_depth=observable_depth,
                    truth_depth=truth_depth,
                    truth_term=truth_term,
                    d_e=float(stave_edep[0]),
                    e_res=float(stave_edep[1:].sum()),
                    entry_ekin=entry_ekin,
                )

    output: dict[str, Any] = {
        **counters,
        "mc_file": mc_path,
        "coinc_ns": COINC_NS,
        "gain": GAIN,
        "peak_frac": PEAK_FRAC,
        "threshold_adc": THRESHOLD_ADC,
        "stop_ke_mev": STOP_KE_MEV,
        "threshold_edep_mev": THRESHOLD_ADC / (GAIN * PEAK_FRAC),
        "primaryweight_applied": True,
        "unweighted_outputs_are_sensitivity_only": True,
        "charge_selection": "ccb_mc_validation.truth.pdg.is_charged",
    }
    for name, bag in bags.items():
        output[name] = _finalize_bag(bag)
    return output


def analyze_data(pulse_table: str, event_csv: str | None = None) -> dict[str, Any]:
    """Construct finite event-level data profiles from the canonical pulse table."""
    import pandas as pd

    frame = pd.read_csv(pulse_table)
    required = {"run", "group", "stave", "amplitude_adc"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ContractError(f"DATA_MISSING_COLUMNS:{','.join(missing)}")
    event_column = "evt" if "evt" in frame.columns else "eventno"
    if event_column not in frame.columns:
        raise ContractError("DATA_MISSING_EVENT_COLUMN")
    frame["amplitude_adc"] = pd.to_numeric(frame["amplitude_adc"], errors="coerce")
    if not np.all(np.isfinite(frame["amplitude_adc"].to_numpy(float))):
        raise ContractError("DATA_NONFINITE_AMPLITUDE")
    frame["net_adc"] = frame["amplitude_adc"].abs()
    frame = frame[frame["net_adc"] > THRESHOLD_ADC].copy()
    frame["sample"] = np.where(
        frame["group"].astype(str).str.startswith("sample_i_"),
        "I",
        np.where(frame["group"].astype(str).str.startswith("sample_ii_"), "II", "other"),
    )
    rank = {stave: index for index, stave in enumerate(STAVES)}
    frame["rank"] = frame["stave"].map(rank)
    if frame["rank"].isna().any():
        raise ContractError("DATA_UNKNOWN_STAVE")
    output: dict[str, Any] = {
        "pulse_table": pulse_table,
        "threshold_adc": THRESHOLD_ADC,
        "n_pulses_above_thr": int(len(frame)),
    }
    key_columns = ["run", event_column]
    splits = {
        "all": frame,
        "sample_i": frame[frame["sample"] == "I"],
        "sample_ii": frame[frame["sample"] == "II"],
    }
    for name, subset in splits.items():
        if subset.empty:
            raise ContractError(f"EMPTY_DATA_SELECTION:{name}")
        deepest = subset.groupby(key_columns, sort=False)["rank"].max().to_numpy(dtype=int)
        counts = {stave: int(np.sum(deepest == index)) for index, stave in enumerate(STAVES)}
        output[name] = {
            "n_events": int(deepest.size),
            "stop_depth_counts": counts,
            "stop_depth_frac": _profile_fraction(counts),
        }
    output["deltaE_E"] = {}
    if event_csv:
        events = pd.read_csv(event_csv)
        for column in ("deltaE_data_adc", "E_data_adc"):
            if column not in events.columns:
                raise ContractError(f"EVENT_CSV_MISSING_COLUMN:{column}")
            events[column] = pd.to_numeric(events[column], errors="coerce")
        values = events[["deltaE_data_adc", "E_data_adc"]].to_numpy(float)
        if not np.all(np.isfinite(values)):
            raise ContractError("EVENT_CSV_NONFINITE_VALUE")
        both = (values[:, 0] > 0.0) & (values[:, 1] > 0.0)
        output["deltaE_E"] = {
            "n_both_fire": int(both.sum()),
            "corr_both_fire": (
                float(np.corrcoef(values[both, 0], values[both, 1])[0, 1])
                if both.sum() > 2
                else float("nan")
            ),
        }
    return output


def _same_target_metrics(mc: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    unselected_same = _chi2(
        mc["unselected"]["stop_depth_frac"],
        data["sample_i"]["stop_depth_counts"],
    )
    matched = _chi2(mc["sample_i"]["stop_depth_frac"], data["sample_i"]["stop_depth_counts"])
    data_fraction = data["sample_i"]["stop_depth_frac"]
    mc_fraction = mc["sample_i"]["stop_depth_frac"]
    total_variation = 0.5 * math.fsum(
        abs(data_fraction[stave] - mc_fraction[stave]) for stave in STAVES
    )
    return {
        "comparison_policy": "SAME_DATA_TARGET_FOR_SELECTION_ABLATION",
        "unselected_vs_sample_i": {
            "chi2": unselected_same[0],
            "ndf": unselected_same[1],
            "chi2_per_ndf": unselected_same[2],
        },
        "sample_i_vs_sample_i": {
            "chi2": matched[0],
            "ndf": matched[1],
            "chi2_per_ndf": matched[2],
        },
        "chi2_improvement_factor": unselected_same[2] / matched[2],
        "sample_i_b2_residual_percentage_points": 100.0 * (
            data_fraction["B2"] - mc_fraction["B2"]
        ),
        "sample_i_total_variation_distance": total_variation,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def make_plots(
    out_dir: Path,
    mc: dict[str, Any],
    data: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.arange(len(STAVES))
    fig, ax = plt.subplots(figsize=(10, 5.8))
    series = [
        ("Data Sample-I", data["sample_i"]["stop_depth_frac"], "//"),
        ("MC unselected weighted", mc["unselected"]["stop_depth_frac"], ""),
        ("MC Sample-I weighted", mc["sample_i"]["stop_depth_frac"], ""),
        ("MC Sample-I unweighted sensitivity", mc["sample_i"]["unweighted_stop_depth_frac"], "xx"),
    ]
    width = 0.19
    for index, (label, profile, hatch) in enumerate(series):
        values = [profile[stave] for stave in STAVES]
        ax.bar(x + (index - 1.5) * width, values, width=width, label=label, hatch=hatch,
               edgecolor="black", linewidth=0.5, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(STAVES)
    ax.set_ylabel("Fraction of selected events")
    ax.set_xlabel("Deepest stave above threshold")
    ax.set_ylim(0.0, 1.05)
    ax.set_title(
        "MV3 weighted selection diagnostic\n"
        f"same-target χ²/ndf={metrics['sample_i_vs_sample_i']['chi2_per_ndf']:.2f}; "
        f"TVD={metrics['sample_i_total_variation_distance']:.4f}"
    )
    ax.grid(axis="y", alpha=0.35)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_mv3a_stopping_depth_overlay.png", dpi=160)
    plt.close(fig)


def build_summary(
    *,
    mc_path: Path,
    pulse_path: Path,
    event_path: Path | None,
    output_dir: Path,
    source_commit: str,
    mc: dict[str, Any],
    data: dict[str, Any],
    command: str,
) -> dict[str, Any]:
    metrics = _same_target_metrics(mc, data)
    matched_chi2 = metrics["sample_i_vs_sample_i"]["chi2_per_ndf"]
    tvd = metrics["sample_i_total_variation_distance"]
    if matched_chi2 <= 5.0 and tvd <= 0.02:
        verdict = "CANDIDATE_CLOSURE_REQUIRES_CANONICAL_REVIEW"
    else:
        verdict = "FLAWED_SELECTION_DIAGNOSTIC_RESIDUAL_REMAINS"
    return {
        "schema": "ccb-mv3-selection-matched/2",
        "study_id": "MV3-selection-matched",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "policy": POLICY,
        "claim_authorization": "NON_AUTHORIZING_DIAGNOSTIC",
        "canonical_claim": {
            "claim_id": "CL-021",
            "required_status": "FLAWED",
            "blocked_by": "BLK-MV3-LEGACY-001",
        },
        "parameters": {
            "coinc_ns": COINC_NS,
            "gain": GAIN,
            "peak_frac": PEAK_FRAC,
            "threshold_adc": THRESHOLD_ADC,
            "stop_ke_mev": STOP_KE_MEV,
        },
        "weighting": {
            "primaryweight_applied": True,
            "policy": "EXACTLY_ONE_FINITE_NONNEGATIVE_PRIMARYWEIGHT_PER_EVENT",
            "unweighted_result_role": "SENSITIVITY_ONLY",
            "sum_w": mc["unselected"]["sum_w"],
            "sum_w2": mc["unselected"]["sum_w2"],
            "effective_sample_size": mc["unselected"]["effective_sample_size"],
        },
        "comparison_policy": metrics["comparison_policy"],
        "chi2_improvement_factor": metrics["chi2_improvement_factor"],
        "same_target_metrics": metrics,
        "mc": mc,
        "data": data,
        "verdict": verdict,
        "sensitivity": {
            "status": "NOT_RUN_SINGLE_POINT_ONLY",
            "gain": [GAIN],
            "threshold_adc": [THRESHOLD_ADC],
            "coinc_ns": [COINC_NS],
            "weighting": ["weighted_primary", "unweighted_sensitivity"],
            "required_future_axes": ["aggregation", "material", "scattering_model"],
        },
        "uncertainty": {
            "mc_data_covariance_evaluated": False,
            "status": "NOT_ESTIMATED_PRODUCTION_RERUN_REQUIRED",
        },
        "provenance": {
            "mc_path": str(mc_path),
            "mc_sha256": _sha256(mc_path),
            "data_pulse_path": str(pulse_path),
            "data_pulse_sha256": _sha256(pulse_path),
            "data_event_path": str(event_path) if event_path else None,
            "data_event_sha256": _sha256(event_path) if event_path else None,
            "script_path": str(Path(__file__).resolve()),
            "script_sha256": _sha256(Path(__file__).resolve()),
            "source_commit": source_commit,
            "command": command,
            "output_dir": str(output_dir),
        },
        "scientific_boundary": (
            "A single weighted rerun is diagnostic. Canonical closure requires finite covariance, "
            "preregistered sensitivity scans, immutable inputs, and CL-021 ledger review."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mc", type=Path, required=True)
    parser.add_argument("--data-pulse-table", type=Path, required=True)
    parser.add_argument("--data-event-csv", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tree", default="hibeam")
    parser.add_argument("--max-events", type=int, default=0)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args(argv)
    if len(args.source_commit) != 40 or any(
        char not in "0123456789abcdef" for char in args.source_commit
    ):
        raise ContractError("SOURCE_COMMIT_MUST_BE_FULL_LOWERCASE_SHA1")
    input_paths = [args.mc, args.data_pulse_table]
    if args.data_event_csv is not None:
        input_paths.append(args.data_event_csv)
    summary_path = args.out / "mv3_selection_matched_summary.json"
    if any(
        summary_path.resolve(strict=False) == path.resolve(strict=False)
        for path in input_paths
    ):
        raise ContractError("OUTPUT_ALIASES_INPUT")
    args.out.mkdir(parents=True, exist_ok=True)
    mc = analyze_mc(str(args.mc), args.tree, args.max_events)
    data = analyze_data(
        str(args.data_pulse_table),
        str(args.data_event_csv) if args.data_event_csv is not None else None,
    )
    command = shlex.join([sys.executable, str(Path(__file__).resolve()), *(argv or sys.argv[1:])])
    summary = build_summary(
        mc_path=args.mc,
        pulse_path=args.data_pulse_table,
        event_path=args.data_event_csv,
        output_dir=args.out,
        source_commit=args.source_commit,
        mc=mc,
        data=data,
        command=command,
    )
    _atomic_json(summary_path, summary)
    make_plots(args.out, mc, data, summary["same_target_metrics"])
    print(json.dumps({"status": summary["verdict"], "summary": str(summary_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
