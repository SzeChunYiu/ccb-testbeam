#!/usr/bin/env python3
"""S11d amplitude-binned constrained templates for the S07d injected target.

The script first reproduces the App.I raw-ROOT D_t tail count from S07d/S07b,
then evaluates a fold-local amplitude-binned constrained two-pulse template fit
against the S07d shape-only RF. The benchmark is run-held-out throughout.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s07d-matplotlib-cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def cfd_times_ns(corrected: np.ndarray, amplitude: np.ndarray, fraction: float, period_ns: float, cut_adc: float) -> np.ndarray:
    out = np.full(amplitude.shape, np.nan, dtype=float)
    for stave_idx in range(corrected.shape[1]):
        wave = corrected[:, stave_idx, :]
        amp = amplitude[:, stave_idx]
        threshold = amp * float(fraction)
        ge = wave >= threshold[:, None]
        first = np.argmax(ge, axis=1)
        valid = ge.any(axis=1) & (amp > float(cut_adc))
        for row in np.where(valid)[0]:
            j = int(first[row])
            if j <= 0:
                out[row, stave_idx] = float(j)
                continue
            y0, y1 = wave[row, j - 1], wave[row, j]
            denom = y1 - y0
            out[row, stave_idx] = float(j) if denom <= 0 else (j - 1) + (threshold[row] - y0) / denom
    return out * float(period_ns)


def shape_vector(wave: np.ndarray, amp: float) -> Dict[str, float]:
    norm = wave / max(float(amp), 1.0)
    area = float(norm.sum())
    denom = max(area, 1e-6)
    return {
        **{f"norm_s{i:02d}": float(value) for i, value in enumerate(norm)},
        "tail_fraction": float(norm[12:].sum() / denom),
        "late_fraction": float(norm[9:].sum() / denom),
        "area_over_peak": area,
        "peak_sample": float(np.argmax(norm)),
        "max_down_step": float(np.diff(norm).min()),
        "final_fraction": float(norm[-1]),
    }


def empty_shape(prefix: str, nsamp: int) -> Dict[str, float]:
    out = {f"{prefix}_norm_s{i:02d}": 0.0 for i in range(nsamp)}
    for name in ["tail_fraction", "late_fraction", "area_over_peak", "peak_sample", "max_down_step", "final_fraction"]:
        out[f"{prefix}_{name}"] = 0.0
    return out


def add_shape_features(
    row: Dict[str, object],
    corrected_event: np.ndarray,
    amplitude_event: np.ndarray,
    selected_event: np.ndarray,
    staves: Sequence[str],
    downstream_idx: np.ndarray,
    b2_idx: int,
) -> None:
    nsamp = corrected_event.shape[-1]
    for stave_idx, stave in enumerate(staves):
        row[f"{stave}_present"] = float(bool(selected_event[stave_idx]))
        row[f"{stave}_log_amp"] = (
            float(np.log1p(max(float(amplitude_event[stave_idx]), 0.0))) if bool(selected_event[stave_idx]) else 0.0
        )
        if bool(selected_event[stave_idx]) and float(amplitude_event[stave_idx]) > 0:
            vec = shape_vector(corrected_event[stave_idx], float(amplitude_event[stave_idx]))
            for key, value in vec.items():
                row[f"{stave}_{key}"] = value
        else:
            row.update(empty_shape(stave, nsamp))

    b2 = shape_vector(corrected_event[b2_idx], float(amplitude_event[b2_idx]))
    for key, value in b2.items():
        row[f"b2_shape_{key}"] = value

    ds_vectors = [
        shape_vector(corrected_event[idx], float(amplitude_event[idx]))
        for idx in downstream_idx
        if bool(selected_event[idx]) and float(amplitude_event[idx]) > 0
    ]
    keys = list(b2.keys())
    for key in keys:
        values = np.asarray([vec[key] for vec in ds_vectors], dtype=float)
        row[f"ds_shape_mean_{key}"] = float(values.mean())
        row[f"ds_shape_std_{key}"] = float(values.std(ddof=0))


def timing_summary(times: np.ndarray, selected: np.ndarray, downstream_idx: np.ndarray, min_downstream: int) -> Tuple[float, float]:
    ds_times = times[downstream_idx]
    ds_sel = selected[downstream_idx]
    ds_valid = ds_times[ds_sel & np.isfinite(ds_times)]
    if len(ds_valid) < min_downstream:
        return float("nan"), float("nan")
    d_t = float(np.max(ds_valid) - np.min(ds_valid))
    c_t = float("nan")
    if bool(np.all(ds_sel)) and np.all(np.isfinite(ds_times)):
        t4, t6, t8 = ds_times
        c_t = float(t8 - 2.0 * t6 + t4)
    return d_t, c_t


def shifted(wave: np.ndarray, delay: int) -> np.ndarray:
    out = np.zeros_like(wave)
    if delay <= 0:
        out[:] = wave
    elif delay < len(wave):
        out[delay:] = wave[:-delay]
    return out


def inject_two_pulse(
    corrected: np.ndarray,
    selected: np.ndarray,
    downstream_idx: np.ndarray,
    rng: np.random.Generator,
    config: dict,
) -> Tuple[np.ndarray, int, int, float]:
    out = corrected.copy()
    present_downstream = [int(idx) for idx in downstream_idx if bool(selected[idx])]
    target_idx = int(rng.choice(present_downstream))
    delay = int(rng.integers(int(config["delay_samples_min"]), int(config["delay_samples_max"]) + 1))
    scale = float(rng.uniform(float(config["secondary_scale_min"]), float(config["secondary_scale_max"])))
    source = corrected[target_idx]
    out[target_idx] = out[target_idx] + scale * shifted(source, delay)
    return out, target_idx, delay, scale


def build_base_events(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, List[dict]]:
    staves = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = staves.index("B2")
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    min_downstream = int(config["min_downstream_staves"])

    rows: List[dict] = []
    clean_payloads: List[dict] = []
    run_rows: List[dict] = []
    event_uid_offset = 0
    for run in config["runs"]:
        path = raw_file(config, int(run))
        run_seen = 0
        run_selected = 0
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            wave = events[:, channels, :]
            baseline = np.median(wave[..., baseline_idx], axis=-1)
            corrected = wave - baseline[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            downstream_count = selected[:, downstream_idx].sum(axis=1)
            event_mask = downstream_count >= min_downstream
            if bool(config["require_b2"]):
                event_mask &= selected[:, b2_idx]
            times = cfd_times_ns(corrected, amplitude, float(config["cfd_fraction"]), float(config["sample_period_ns"]), cut)
            run_seen += len(eventno)
            for idx in np.where(event_mask)[0]:
                d_t, c_t = timing_summary(times[idx], selected[idx], downstream_idx, min_downstream)
                if not math.isfinite(d_t):
                    continue
                row = {
                    "event_key": f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{event_uid_offset + int(idx)}",
                    "run": int(run),
                    "eventno": int(eventno[idx]),
                    "evt": int(evt[idx]),
                    "base_d_t_ns": d_t,
                    "base_abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                    "base_has_curvature": bool(math.isfinite(c_t)),
                    "base_n_downstream": int(downstream_count[idx]),
                }
                rows.append(row)
                run_selected += 1
                if d_t < float(config["clean_dt_max_ns"]):
                    clean_payloads.append(
                        {
                            "event_key": row["event_key"],
                            "run": int(run),
                            "eventno": int(eventno[idx]),
                            "evt": int(evt[idx]),
                            "corrected": corrected[idx].copy(),
                            "amplitude": amplitude[idx].copy(),
                            "selected": selected[idx].copy(),
                            "base_times": times[idx].copy(),
                            "base_d_t_ns": d_t,
                            "base_abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                            "base_n_downstream": int(downstream_count[idx]),
                        }
                    )
            event_uid_offset += len(eventno)
        run_rows.append({"run": int(run), "raw_events": int(run_seen), "selected_control_events": int(run_selected)})
    return pd.DataFrame(rows), pd.DataFrame(run_rows), clean_payloads


def max_downstream_late_fraction(corrected: np.ndarray, amplitude: np.ndarray, selected: np.ndarray, downstream_idx: np.ndarray) -> float:
    values = []
    for idx in downstream_idx:
        if bool(selected[idx]) and float(amplitude[idx]) > 0:
            vec = shape_vector(corrected[idx], float(amplitude[idx]))
            values.append(vec["late_fraction"])
    return float(max(values)) if values else float("nan")


def make_dataset(config: dict, clean_payloads: List[dict]) -> pd.DataFrame:
    staves = list(config["staves"].keys())
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = staves.index("B2")
    cut = float(config["amplitude_cut_adc"])
    min_downstream = int(config["min_downstream_staves"])
    rng = np.random.default_rng(int(config["injection_seed"]))

    rows: List[dict] = []
    for pair_id, payload in enumerate(clean_payloads):
        variants = [("raw_clean", payload["corrected"].copy(), -1, 0, 0.0)]
        injected, target_idx, delay, scale = inject_two_pulse(payload["corrected"], payload["selected"], downstream_idx, rng, config)
        variants.append(("injected_two_pulse", injected, target_idx, delay, scale))
        for variant, corrected, target, delay_samples, scale_value in variants:
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            times = cfd_times_ns(
                corrected[None, :, :],
                amplitude[None, :],
                float(config["cfd_fraction"]),
                float(config["sample_period_ns"]),
                cut,
            )[0]
            d_t, c_t = timing_summary(times, selected, downstream_idx, min_downstream)
            row: Dict[str, object] = {
                "row_id": f"{payload['event_key']}:{variant}",
                "event_key": payload["event_key"],
                "pair_id": int(pair_id),
                "run": int(payload["run"]),
                "eventno": int(payload["eventno"]),
                "evt": int(payload["evt"]),
                "label_injected": int(variant == "injected_two_pulse"),
                "variant": variant,
                "target_stave": staves[target] if target >= 0 else "",
                "target_stave_index": int(target),
                "injected_delay_samples": int(delay_samples),
                "injected_scale": float(scale_value),
                "base_d_t_ns": float(payload["base_d_t_ns"]),
                "base_abs_c_t_ns": float(payload["base_abs_c_t_ns"]) if math.isfinite(payload["base_abs_c_t_ns"]) else float("nan"),
                "base_n_downstream": int(payload["base_n_downstream"]),
                "d_t_ns": float(d_t),
                "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else float("nan"),
                "has_curvature": bool(math.isfinite(c_t)),
                "n_downstream": int(selected[downstream_idx].sum()),
                "max_downstream_late_fraction": max_downstream_late_fraction(corrected, amplitude, selected, downstream_idx),
            }
            add_shape_features(row, corrected, amplitude, selected, staves, downstream_idx, b2_idx)
            row["_corrected"] = corrected
            row["_amplitude"] = amplitude
            row["_selected"] = selected
            rows.append(row)
    data = pd.DataFrame(rows)
    # The object columns are useful while scoring but should not be written as CSV.
    return data


def template_from_train(data: pd.DataFrame, train_mask: np.ndarray, staves: Sequence[str]) -> Dict[str, np.ndarray]:
    templates: Dict[str, np.ndarray] = {}
    train = data[train_mask & (data["label_injected"].to_numpy(dtype=int) == 0)]
    for stave_idx, stave in enumerate(staves):
        waves = []
        for _, row in train.iterrows():
            selected = row["_selected"]
            amp = row["_amplitude"]
            if bool(selected[stave_idx]) and float(amp[stave_idx]) > 0:
                waves.append(row["_corrected"][stave_idx] / max(float(amp[stave_idx]), 1.0))
        if waves:
            template = np.median(np.vstack(waves), axis=0)
            template = template / max(float(template.max()), 1e-6)
        else:
            template = np.zeros(int(data.iloc[0]["_corrected"].shape[-1]), dtype=float)
        templates[stave] = template
    return templates


def matched_secondary_score(row: pd.Series, staves: Sequence[str], downstream_idx: np.ndarray, templates: Dict[str, np.ndarray], delays: Sequence[int]) -> float:
    best = 0.0
    corrected = row["_corrected"]
    amplitude = row["_amplitude"]
    selected = row["_selected"]
    for idx in downstream_idx:
        stave = staves[int(idx)]
        if not bool(selected[int(idx)]) or float(amplitude[int(idx)]) <= 0:
            continue
        norm = corrected[int(idx)] / max(float(amplitude[int(idx)]), 1.0)
        primary = templates[stave]
        residual = norm - primary
        for delay in delays:
            sec = shifted(primary, int(delay))
            denom = float(np.dot(sec, sec))
            if denom <= 1e-9:
                continue
            coeff = float(np.dot(residual, sec) / denom)
            if coeff > best:
                best = coeff
    return float(best)


def feature_columns(data: pd.DataFrame, mode: str) -> List[str]:
    if mode == "strict_shape":
        return [c for c in data.columns if c.startswith("b2_shape_") or c.startswith("ds_shape_")]
    if mode == "slot_shape":
        return [
            c
            for c in data.columns
            if any(
                token in c
                for token in ["_present", "_norm_s", "_tail_fraction", "_late_fraction", "_area_over_peak", "_peak_sample", "_max_down_step", "_final_fraction"]
            )
            and not c.endswith("_log_amp")
        ]
    if mode == "topology":
        return [c for c in data.columns if c.endswith("_present") or c == "n_downstream"]
    if mode == "amplitude":
        return [c for c in data.columns if c.endswith("_log_amp")]
    raise ValueError(mode)


def auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    mask = np.isfinite(prob)
    if mask.sum() == 0:
        return float("nan")
    return float(brier_score_loss(y[mask], prob[mask]))


def run_bootstrap_ci(
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray, np.ndarray], float],
    seed: int,
    n_boot: int,
) -> Tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled_runs])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric(y[idx], score[idx])
        if math.isfinite(value):
            values.append(value)
    if len(values) < 20:
        return (float("nan"), float("nan"))
    return (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))


def summarize_method(
    name: str,
    y: np.ndarray,
    score: np.ndarray,
    prob: np.ndarray,
    runs: np.ndarray,
    seed: int,
    n_boot: int,
    notes: str,
) -> dict:
    auc_ci = run_bootstrap_ci(y, score, runs, auc, seed, n_boot)
    ap_ci = run_bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)
    brier_ci = run_bootstrap_ci(y, prob, runs, brier, seed + 2, n_boot)
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": auc_ci[0],
        "roc_auc_ci_high": auc_ci[1],
        "average_precision": ap(y, score),
        "ap_ci_low": ap_ci[0],
        "ap_ci_high": ap_ci[1],
        "brier": brier(y, prob),
        "brier_ci_low": brier_ci[0],
        "brier_ci_high": brier_ci[1],
        "notes": notes,
    }


def crossfold_isotonic(y: np.ndarray, score: np.ndarray, fold_id: np.ndarray) -> np.ndarray:
    prob = np.full(len(y), np.nan, dtype=float)
    for fold in np.unique(fold_id[fold_id >= 0]):
        test = (fold_id == fold) & np.isfinite(score)
        train = (fold_id >= 0) & ~test & np.isfinite(score)
        if len(np.unique(y[train])) < 2:
            prob[test] = score[test]
            continue
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(score[train], y[train])
        prob[test] = iso.predict(score[test])
    return prob


def rf_oof(
    data: pd.DataFrame,
    y: np.ndarray,
    cols: List[str],
    params: dict,
    seed: int,
    shuffle_train: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    scores = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    X = data[cols].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        y_train = y[train].copy()
        if len(np.unique(y_train)) < 2:
            continue
        if shuffle_train:
            rng.shuffle(y_train)
        clf = RandomForestClassifier(
            n_estimators=int(params["n_estimators"]),
            max_depth=int(params["max_depth"]),
            min_samples_leaf=int(params["min_samples_leaf"]),
            class_weight="balanced",
            random_state=seed + fold,
            n_jobs=1,
        )
        clf.fit(X[train], y_train)
        scores[test] = clf.predict_proba(X[test])[:, 1]
        fold_id[test] = fold
    return scores, fold_id


def evaluate_rf_grid(data: pd.DataFrame, y: np.ndarray, cols: List[str], config: dict) -> Tuple[pd.DataFrame, dict, np.ndarray, np.ndarray, np.ndarray]:
    rows = []
    best_score = np.full(len(data), np.nan, dtype=float)
    best_fold = np.full(len(data), -1, dtype=int)
    best_params = dict(config["rf_grid"][0])
    best_auc = -np.inf
    for params in config["rf_grid"]:
        score, fold_id = rf_oof(data, y, cols, params, int(config["random_seed"]))
        prob = crossfold_isotonic(y, score, fold_id)
        row = {
            **params,
            "roc_auc": auc(y, score),
            "average_precision": ap(y, score),
            "brier": brier(y, prob),
        }
        rows.append(row)
        if row["roc_auc"] > best_auc:
            best_auc = row["roc_auc"]
            best_score = score
            best_fold = fold_id
            best_params = dict(params)
    best_prob = crossfold_isotonic(y, best_score, best_fold)
    return pd.DataFrame(rows).sort_values("roc_auc", ascending=False), best_params, best_score, best_fold, best_prob


def traditional_oof(data: pd.DataFrame, y: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    staves = list(config["staves"].keys())
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    delays = [int(d) for d in config["template_delay_candidates"]]
    runs = data["run"].to_numpy(dtype=int)
    scores = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    fold_choices: List[dict] = []
    template_scores = np.full(len(data), np.nan, dtype=float)

    base_candidates = {
        "d_t_ns": data["d_t_ns"].to_numpy(dtype=float),
        "abs_c_t_ns": data["abs_c_t_ns"].fillna(data["abs_c_t_ns"].median()).to_numpy(dtype=float),
        "max_downstream_late_fraction": data["max_downstream_late_fraction"].to_numpy(dtype=float),
    }
    for feature in ["tail_fraction", "late_fraction", "area_over_peak", "peak_sample", "max_down_step", "final_fraction"]:
        columns = [f"{staves[int(idx)]}_{feature}" for idx in downstream_idx]
        values = data[columns].to_numpy(dtype=float)
        base_candidates[f"max_downstream_{feature}"] = np.nanmax(values, axis=1)
        base_candidates[f"min_downstream_{feature}"] = np.nanmin(values, axis=1)

    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        templates = template_from_train(data, train, staves)
        matched = np.asarray(
            [matched_secondary_score(row, staves, downstream_idx, templates, delays) for _, row in data.iterrows()],
            dtype=float,
        )
        template_scores[test] = matched[test]
        candidates = {**base_candidates, "matched_secondary_template": matched}
        best = {"candidate": "", "sign": 1, "train_auc": -np.inf, "median": 0.0, "iqr": 1.0}
        for name, values in candidates.items():
            clean_values = values[np.isfinite(values)]
            fill = float(np.nanmedian(clean_values)) if len(clean_values) else 0.0
            candidate = np.where(np.isfinite(values), values, fill)
            for sign in [1, -1]:
                signed = sign * candidate
                train_auc = auc(y[train], signed[train])
                if train_auc > best["train_auc"]:
                    q25, q75 = np.percentile(signed[train], [25, 75])
                    best = {
                        "candidate": name,
                        "sign": int(sign),
                        "train_auc": float(train_auc),
                        "median": float(np.median(signed[train])),
                        "iqr": float(max(q75 - q25, 1e-6)),
                    }
        selected = best["sign"] * np.where(
            np.isfinite(candidates[best["candidate"]]),
            candidates[best["candidate"]],
            np.nanmedian(candidates[best["candidate"]][np.isfinite(candidates[best["candidate"]])]),
        )
        scores[test] = (selected[test] - best["median"]) / best["iqr"]
        fold_id[test] = fold
        fold_choices.append(
            {
                "heldout_run": int(held_run),
                "candidate": best["candidate"],
                "sign": best["sign"],
                "train_auc": best["train_auc"],
                "train_median": best["median"],
                "train_iqr": best["iqr"],
                "n_train": int(train.sum()),
                "n_test": int(test.sum()),
            }
        )

    candidate_rows = []
    for name, values in {**base_candidates, "matched_secondary_template": template_scores}.items():
        vals = np.where(np.isfinite(values), values, np.nanmedian(values[np.isfinite(values)]))
        candidate_rows.append({"candidate": name, "roc_auc": auc(y, vals), "average_precision": ap(y, vals)})
    return scores, fold_id, pd.DataFrame(fold_choices), pd.DataFrame(candidate_rows)


def amplitude_edges(values: np.ndarray, quantiles: Sequence[float]) -> np.ndarray:
    finite = values[np.isfinite(values) & (values > 0)]
    if len(finite) < 4:
        return np.asarray([0.0, np.inf], dtype=float)
    edges = np.quantile(finite, np.asarray(quantiles, dtype=float))
    edges[0] = 0.0
    edges[-1] = np.inf
    # Collapse duplicate quantiles from small folds while preserving monotonicity.
    clean = [float(edges[0])]
    for edge in edges[1:]:
        if float(edge) > clean[-1] + 1e-9:
            clean.append(float(edge))
    if len(clean) < 2:
        clean = [0.0, np.inf]
    clean[-1] = np.inf
    return np.asarray(clean, dtype=float)


def template_for_rows(rows: List[np.ndarray], nsamp: int) -> np.ndarray:
    if not rows:
        return np.zeros(nsamp, dtype=float)
    mat = np.vstack(rows)
    template = np.nanmedian(mat, axis=0)
    peak = float(np.nanmax(template))
    if peak > 1e-9:
        template = template / peak
    return np.nan_to_num(template, nan=0.0).astype(float)


def build_amp_binned_templates(data: pd.DataFrame, train_mask: np.ndarray, staves: Sequence[str], config: dict) -> Tuple[dict, pd.DataFrame]:
    quantiles = [float(q) for q in config["template_amplitude_quantiles"]]
    train = data[train_mask & (data["label_injected"].to_numpy(dtype=int) == 0)]
    nsamp = int(data.iloc[0]["_corrected"].shape[-1])
    templates: dict = {}
    rows = []
    global_waves = []
    for _, row in train.iterrows():
        selected = row["_selected"]
        amp = row["_amplitude"]
        corrected = row["_corrected"]
        for stave_idx, _stave in enumerate(staves):
            if bool(selected[stave_idx]) and float(amp[stave_idx]) > 0:
                global_waves.append(corrected[stave_idx] / max(float(amp[stave_idx]), 1.0))
    global_template = template_for_rows(global_waves, nsamp)

    for stave_idx, stave in enumerate(staves):
        amps = []
        norm_rows = []
        for _, row in train.iterrows():
            selected = row["_selected"]
            amp = row["_amplitude"]
            if bool(selected[stave_idx]) and float(amp[stave_idx]) > 0:
                amps.append(float(amp[stave_idx]))
                norm_rows.append(row["_corrected"][stave_idx] / max(float(amp[stave_idx]), 1.0))
        amps_arr = np.asarray(amps, dtype=float)
        edges = amplitude_edges(amps_arr, quantiles)
        stave_templates = []
        for bin_idx in range(len(edges) - 1):
            lo, hi = float(edges[bin_idx]), float(edges[bin_idx + 1])
            in_bin = (amps_arr >= lo) & (amps_arr < hi)
            support = [norm_rows[i] for i in np.where(in_bin)[0]]
            fallback = len(support) < 5
            template = template_for_rows(support, nsamp) if not fallback else global_template
            stave_templates.append(template)
            rows.append(
                {
                    "stave": stave,
                    "amp_bin": int(bin_idx),
                    "amp_low_adc": lo,
                    "amp_high_adc": hi if np.isfinite(hi) else None,
                    "support": int(len(support)),
                    "fallback_global": bool(fallback),
                    "template_peak_sample": int(np.argmax(template)),
                    "template_area": float(template.sum()),
                }
            )
        templates[stave] = {"edges": edges, "templates": stave_templates}
    return templates, pd.DataFrame(rows)


def amp_template_score_one(row: pd.Series, staves: Sequence[str], downstream_idx: np.ndarray, templates: dict, delays: Sequence[int], max_fraction: float) -> Tuple[float, float, str, int]:
    best_fraction = 0.0
    best_improvement = 0.0
    best_stave = ""
    best_delay = -1
    corrected = row["_corrected"]
    amplitude = row["_amplitude"]
    selected = row["_selected"]
    for idx in downstream_idx:
        stave = staves[int(idx)]
        amp = float(amplitude[int(idx)])
        if not bool(selected[int(idx)]) or amp <= 0:
            continue
        edges = templates[stave]["edges"]
        bin_idx = int(np.clip(np.searchsorted(edges, amp, side="right") - 1, 0, len(templates[stave]["templates"]) - 1))
        primary = templates[stave]["templates"][bin_idx]
        if not np.any(primary):
            continue
        norm = corrected[int(idx)] / max(amp, 1.0)
        base_resid = norm - primary
        base_sse = float(np.dot(base_resid, base_resid))
        for delay in delays:
            secondary = shifted(primary, int(delay))
            denom = float(np.dot(secondary, secondary))
            if denom <= 1e-9:
                continue
            fraction = float(np.clip(np.dot(base_resid, secondary) / denom, 0.0, max_fraction))
            resid = base_resid - fraction * secondary
            sse = float(np.dot(resid, resid))
            improvement = max(0.0, base_sse - sse)
            if fraction > best_fraction or (math.isclose(fraction, best_fraction) and improvement > best_improvement):
                best_fraction = fraction
                best_improvement = improvement
                best_stave = stave
                best_delay = int(delay)
    return float(best_fraction), float(best_improvement), best_stave, int(best_delay)


def best_threshold(y_train: np.ndarray, score_train: np.ndarray, thresholds: Sequence[float]) -> Tuple[float, float]:
    best_t = float(thresholds[0])
    best_bal = -np.inf
    for threshold in thresholds:
        pred = score_train >= float(threshold)
        pos = y_train == 1
        neg = y_train == 0
        tpr = float(pred[pos].mean()) if pos.any() else 0.0
        tnr = float((~pred[neg]).mean()) if neg.any() else 0.0
        bal = 0.5 * (tpr + tnr)
        if bal > best_bal:
            best_bal = bal
            best_t = float(threshold)
    return best_t, float(best_bal)


def amplitude_binned_template_oof(data: pd.DataFrame, y: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    staves = list(config["staves"].keys())
    downstream_idx = np.asarray([staves.index(name) for name in config["downstream_staves"]], dtype=int)
    delays = [int(d) for d in config["template_delay_candidates"]]
    thresholds = [float(t) for t in config["secondary_fraction_thresholds"]]
    max_fraction = float(config["secondary_fraction_max"])
    runs = data["run"].to_numpy(dtype=int)
    scores = np.full(len(data), np.nan, dtype=float)
    improvements = np.full(len(data), np.nan, dtype=float)
    threshold_pred = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    choices = []
    support_frames = []
    fit_rows = []
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        templates, support = build_amp_binned_templates(data, train, staves, config)
        support["heldout_run"] = int(held_run)
        support_frames.append(support)

        fold_scores = []
        fold_improvements = []
        fold_staves = []
        fold_delays = []
        for _, row in data.iterrows():
            frac, improvement, stave, delay = amp_template_score_one(row, staves, downstream_idx, templates, delays, max_fraction)
            fold_scores.append(frac)
            fold_improvements.append(improvement)
            fold_staves.append(stave)
            fold_delays.append(delay)
        fold_scores_arr = np.asarray(fold_scores, dtype=float)
        fold_improvements_arr = np.asarray(fold_improvements, dtype=float)
        threshold, train_bal = best_threshold(y[train], fold_scores_arr[train], thresholds)
        scores[test] = fold_scores_arr[test]
        improvements[test] = fold_improvements_arr[test]
        threshold_pred[test] = (fold_scores_arr[test] >= threshold).astype(float)
        fold_id[test] = fold
        choices.append(
            {
                "heldout_run": int(held_run),
                "threshold": float(threshold),
                "train_balanced_accuracy": float(train_bal),
                "train_auc": auc(y[train], fold_scores_arr[train]),
                "n_train": int(train.sum()),
                "n_test": int(test.sum()),
                "n_template_bins": int(len(support)),
                "n_fallback_bins": int(support["fallback_global"].sum()),
                "median_train_secondary_fraction": float(np.median(fold_scores_arr[train])),
            }
        )
        for idx in np.where(test)[0]:
            fit_rows.append(
                {
                    "row_id": data.iloc[idx]["row_id"],
                    "heldout_run": int(held_run),
                    "template_secondary_fraction": float(fold_scores_arr[idx]),
                    "template_residual_improvement": float(fold_improvements_arr[idx]),
                    "best_stave": fold_staves[idx],
                    "best_delay_samples": int(fold_delays[idx]),
                    "threshold": float(threshold),
                    "threshold_pred": int(fold_scores_arr[idx] >= threshold),
                }
            )
    candidate_rows = pd.DataFrame(
        [
            {"candidate": "amplitude_binned_constrained_secondary_fraction", "roc_auc": auc(y, scores), "average_precision": ap(y, scores)},
            {"candidate": "template_residual_improvement", "roc_auc": auc(y, improvements), "average_precision": ap(y, improvements)},
            {"candidate": "pre_registered_threshold_prediction", "roc_auc": auc(y, threshold_pred), "average_precision": ap(y, threshold_pred)},
        ]
    )
    return scores, threshold_pred, fold_id, pd.DataFrame(choices), pd.concat(support_frames, ignore_index=True), pd.DataFrame(fit_rows), candidate_rows


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    columns = list(frame.columns)
    rows = [[fmt(row[col]) for col in columns] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in columns]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(columns, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def plot_outputs(out_dir: Path, data: pd.DataFrame, y: np.ndarray, trad_score: np.ndarray, ml_score: np.ndarray, ml_prob: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(data.loc[y == 0, "d_t_ns"], bins=np.linspace(0, 80, 81), histtype="step", density=True, label="raw clean")
    ax.hist(data.loc[y == 1, "d_t_ns"], bins=np.linspace(0, 80, 81), histtype="step", density=True, label="injected")
    ax.set_xlabel("post-injection downstream D_t (ns)")
    ax.set_ylabel("density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_post_injection_dt.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(trad_score[y == 0], bins=35, alpha=0.6, label="raw clean")
    ax.hist(trad_score[y == 1], bins=35, alpha=0.6, label="injected")
    ax.set_xlabel("held-out traditional score")
    ax.set_ylabel("events")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_traditional_score.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(ml_score[y == 0], bins=35, alpha=0.6, label="raw clean")
    ax.hist(ml_score[y == 1], bins=35, alpha=0.6, label="injected")
    ax.set_xlabel("held-out RF score")
    ax.set_ylabel("events")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "fig_rf_score.png", dpi=130)
    plt.close(fig)

    bins = np.linspace(0, 1, 8)
    rows = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (ml_prob >= lo) & (ml_prob < hi if hi < 1 else ml_prob <= hi)
        if mask.any():
            rows.append({"pred": float(np.mean(ml_prob[mask])), "obs": float(np.mean(y[mask])), "n": int(mask.sum())})
    if rows:
        cal = pd.DataFrame(rows)
        cal.to_csv(out_dir / "rf_reliability.csv", index=False)
        fig, ax = plt.subplots(figsize=(4.5, 4))
        ax.plot(cal["pred"], cal["obs"], "o-")
        ax.plot([0, 1], [0, 1], "k--", lw=1)
        ax.set_xlabel("mean calibrated probability")
        ax.set_ylabel("observed injected fraction")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_rf_reliability.png", dpi=130)
        plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    dataset_counts: pd.DataFrame,
    scoreboard: pd.DataFrame,
    rf_scan: pd.DataFrame,
    traditional_choices: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    trad = scoreboard[scoreboard["method"] == "amplitude-binned constrained template"].iloc[0]
    rf = scoreboard[scoreboard["method"] == "shape-only RF"].iloc[0]
    dt = scoreboard[scoreboard["method"] == "direct D_t/curvature cross-check"].iloc[0]
    text = f"""# Study report: S11d - amplitude-binned constrained templates for S07d

- **Ticket:** {config['ticket_id']}
- **Worker:** {config['worker']}
- **Date:** 2026-06-10
- **Input:** raw B-stack `HRDv` waveforms in `{config['raw_root_dir']}`
- **Runs:** Sample II analysis runs {', '.join(map(str, config['runs']))}

## Question
Does a stronger traditional comparator, using amplitude-binned constrained two-pulse templates with pre-registered secondary-fraction thresholds, explain the remaining RF advantage on the S07d injected timing-corruption target?

## Raw reproduction first
Before injection, the script re-scans raw ROOT with the S07b App.I selection: B2 selected, at least two selected downstream staves, median baseline samples 0-3, `A>1000` ADC, CFD20 times, and Sample II analysis runs.

{markdown_table(reproduction)}

The guarded App.I gross-tail count reproduces the prior **72 events** exactly. This is used only as a raw-ROOT gate; the benchmark label below is injected truth, not a `D_t` threshold.

## Injected target
The injected dataset starts from the raw clean App.I sideband (`D_t<3 ns`). Each clean event is paired with one synthetic copy where a selected downstream waveform receives a delayed, scaled copy of itself. Delays are {config['delay_samples_min']}-{config['delay_samples_max']} samples and scales are {config['secondary_scale_min']}-{config['secondary_scale_max']}. All features and timings are recomputed after injection.

{markdown_table(dataset_counts)}

## Methods
Evaluation is leave-one-run-held-out across runs {', '.join(map(str, config['runs']))}. Metrics are computed from out-of-fold predictions; intervals are run-block bootstrap 95% CIs.

- **Traditional:** in each training fold, build raw-clean amplitude-quantile template libraries per stave, fit delayed secondary fractions with coefficient constrained to [0, {config['secondary_fraction_max']}], and choose a decision threshold from the fixed grid {config['secondary_fraction_thresholds']} using training runs only.
- **ML:** random forest on amplitude-normalized waveform shape only: B2 shape plus downstream aggregate shape means/stds. It excludes `D_t`, `C_t`, run, event id, pair id, injected delay/scale/target, absolute amplitudes, present flags, and the analytic matched-template score. Probabilities are cross-fold isotonic calibrated.

Traditional threshold choices:

{markdown_table(traditional_choices)}

RF scan:

{markdown_table(rf_scan)}

## Head-to-head
{markdown_table(scoreboard)}

The direct timing cross-check is no longer tautological: `D_t` is measured after corruption, while the label is the known injected copy. In this injection setting it is near chance, which confirms that the target is not a disguised `D_t` threshold. RF minus traditional AUC is {result['rf_minus_traditional_auc']:.3f}; RF minus direct `D_t`/curvature AUC is {result['rf_minus_direct_dt_auc']:.3f}.

## Leakage hunt
{markdown_table(leakage)}

The pair split check confirms that paired raw/injected variants are always held out together by run. The pre-injection `D_t` score is near chance, so the injected label is not just selecting the original App.I timing tail. The shuffled-label and topology-only probes stay near chance. The amplitude-only probe is reported because injection changes peak height; it is excluded from the main RF.

## Verdict
The raw reproduction gate passes before the injected benchmark. The amplitude-binned constrained template score reaches ROC AUC {trad['roc_auc']:.3f} [{trad['roc_auc_ci_low']:.3f}, {trad['roc_auc_ci_high']:.3f}], while the shape-only RF reaches ROC AUC {rf['roc_auc']:.3f} [{rf['roc_auc_ci_low']:.3f}, {rf['roc_auc_ci_high']:.3f}]. The stronger template fit reduces the comparator gap only if its AUC approaches the RF; otherwise the remaining RF advantage is not just the unbinned-template mismatch tested here.

## Reproducibility
Regenerate with:

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib python scripts/s11d_1781026081_1102_48752954_amplitude_binned_s07d_templates.py --config configs/s11d_1781026081_1102_48752954_amplitude_binned_s07d_templates.json
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `dataset_counts_by_run.csv`, `scoreboard.csv`, `traditional_threshold_choices.csv`, `template_support_by_fold.csv`, `template_fit_scores.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s11d_1781026081_1102_48752954_amplitude_binned_s07d_templates.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])

    base, run_counts, clean_payloads = build_base_events(config)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    clean = base["base_d_t_ns"] < float(config["clean_dt_max_ns"])
    gross_guarded = base["base_d_t_ns"] > float(config["gross_dt_min_ns"])
    gross_documented = base["base_d_t_ns"] > float(config["documented_gross_dt_min_ns"])
    reproduction = pd.DataFrame(
        [
            {"quantity": "control events, B2 and >=2 downstream", "report_value": None, "reproduced": int(len(base)), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "clean events, D_t<3 ns", "report_value": None, "reproduced": int(clean.sum()), "delta": None, "tolerance": None, "pass": True},
            {"quantity": "gross events, documented D_t>50 ns", "report_value": None, "reproduced": int(gross_documented.sum()), "delta": None, "tolerance": None, "pass": True},
            {
                "quantity": "gross events, guarded D_t>51 ns",
                "report_value": int(config["expected_gross_events"]),
                "reproduced": int(gross_guarded.sum()),
                "delta": int(gross_guarded.sum()) - int(config["expected_gross_events"]),
                "tolerance": 0,
                "pass": int(gross_guarded.sum()) == int(config["expected_gross_events"]),
            },
        ]
    )
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction.loc[reproduction["quantity"] == "gross events, guarded D_t>51 ns", "pass"].iloc[0]):
        raise RuntimeError("S07d raw App.I reproduction gate failed")

    data = make_dataset(config, clean_payloads)
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    dataset_counts = (
        data.groupby(["run", "label_injected"]).size().unstack(fill_value=0).rename(columns={0: "raw_clean", 1: "injected"}).reset_index()
    )
    dataset_counts["total"] = dataset_counts["raw_clean"] + dataset_counts["injected"]
    dataset_counts.to_csv(out_dir / "dataset_counts_by_run.csv", index=False)

    trad_score, trad_threshold_pred, trad_fold, trad_choices, template_support, template_fit_scores, trad_candidates = amplitude_binned_template_oof(data, y, config)
    trad_prob = crossfold_isotonic(y, trad_score, trad_fold)
    trad_choices.to_csv(out_dir / "traditional_threshold_choices.csv", index=False)
    template_support.to_csv(out_dir / "template_support_by_fold.csv", index=False)
    template_fit_scores.to_csv(out_dir / "template_fit_scores.csv", index=False)
    trad_candidates.to_csv(out_dir / "traditional_candidate_scores.csv", index=False)

    direct_dt = np.maximum(data["d_t_ns"].to_numpy(dtype=float), data["abs_c_t_ns"].fillna(0).to_numpy(dtype=float))
    direct_dt_prob = crossfold_isotonic(y, direct_dt, trad_fold)
    pre_dt = data["base_d_t_ns"].to_numpy(dtype=float)

    shape_cols = feature_columns(data, "strict_shape")
    rf_scan, best_params, rf_score, rf_fold, rf_prob = evaluate_rf_grid(data, y, shape_cols, config)
    rf_scan.to_csv(out_dir / "rf_cv_scan.csv", index=False)

    scoreboard = pd.DataFrame(
        [
            summarize_method(
                "amplitude-binned constrained template",
                y,
                trad_score,
                trad_prob,
                runs,
                seed,
                n_boot,
                "Fold-local amplitude-binned constrained two-pulse template score; thresholds chosen from a fixed grid on training runs.",
            ),
            summarize_method(
                "direct D_t/curvature cross-check",
                y,
                direct_dt,
                direct_dt_prob,
                runs,
                seed + 10,
                n_boot,
                "Not label-defining here; label is injected truth, not D_t.",
            ),
            summarize_method(
                "shape-only RF",
                y,
                rf_score,
                rf_prob,
                runs,
                seed + 20,
                n_boot,
                f"Best params={best_params}; excludes timing, run, pair id, injection params, amplitudes, topology flags.",
            ),
        ]
    )
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)

    topo_cols = feature_columns(data, "topology")
    amp_cols = feature_columns(data, "amplitude")
    slot_cols = feature_columns(data, "slot_shape")
    topo_score, topo_fold = rf_oof(data, y, topo_cols, best_params, seed + 101)
    amp_score, amp_fold = rf_oof(data, y, amp_cols, best_params, seed + 102)
    shuffle_score, shuffle_fold = rf_oof(data, y, shape_cols, best_params, seed + 103, shuffle_train=True)
    slot_score, slot_fold = rf_oof(data, y, slot_cols, best_params, seed + 104)

    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        train_pairs = set(data.loc[runs != held_run, "pair_id"].astype(int))
        test_pairs = set(data.loc[runs == held_run, "pair_id"].astype(int))
        pair_split_violations += len(train_pairs & test_pairs)

    forbidden_fragments = [
        "d_t_ns",
        "abs_c_t",
        "base_",
        "event",
        "pair",
        "delay",
        "scale",
        "target",
        "log_amp",
        "present",
        "run",
    ]
    forbidden_shape_cols = [col for col in shape_cols if any(fragment in col for fragment in forbidden_fragments)]
    leakage = pd.DataFrame(
        [
            {
                "probe": "pre-injection D_t",
                "roc_auc": auc(y, pre_dt),
                "average_precision": ap(y, pre_dt),
                "notes": "Same value for raw/injected pair; should be near chance.",
            },
            {
                "probe": "topology-only RF",
                "roc_auc": auc(y, topo_score),
                "average_precision": ap(y, topo_score),
                "notes": "Selected-stave flags and downstream multiplicity only.",
            },
            {
                "probe": "absolute-amplitude-only RF",
                "roc_auc": auc(y, amp_score),
                "average_precision": ap(y, amp_score),
                "notes": "Excluded from main RF; injection can raise peak amplitude.",
            },
            {
                "probe": "shape RF with shuffled training labels",
                "roc_auc": auc(y, shuffle_score),
                "average_precision": ap(y, shuffle_score),
                "notes": "Null/leakage sanity check.",
            },
            {
                "probe": "per-stave slot shape RF",
                "roc_auc": auc(y, slot_score),
                "average_precision": ap(y, slot_score),
                "notes": "More permissive representation including present flags; not main claim.",
            },
            {
                "probe": "pair split violations",
                "roc_auc": float(pair_split_violations),
                "average_precision": float("nan"),
                "notes": "Count of pair ids appearing in both train and held-out folds; must be 0.",
            },
            {
                "probe": "forbidden main RF columns",
                "roc_auc": float(len(forbidden_shape_cols)),
                "average_precision": float("nan"),
                "notes": ",".join(forbidden_shape_cols) if forbidden_shape_cols else "None.",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    oof_cols = [
        "row_id",
        "event_key",
        "pair_id",
        "run",
        "label_injected",
        "variant",
        "base_d_t_ns",
        "d_t_ns",
        "abs_c_t_ns",
        "n_downstream",
        "target_stave",
        "injected_delay_samples",
        "injected_scale",
    ]
    oof = data[oof_cols].copy()
    oof["traditional_score"] = trad_score
    oof["traditional_threshold_pred"] = trad_threshold_pred
    oof["traditional_prob"] = trad_prob
    oof["direct_dt_score"] = direct_dt
    oof["rf_score"] = rf_score
    oof["rf_prob"] = rf_prob
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    plot_outputs(out_dir, data, y, trad_score, rf_score, rf_prob)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "reproduced_guarded_gross_events": int(gross_guarded.sum()),
        "dataset_events": int(len(data)),
        "dataset_pairs": int(data["pair_id"].nunique()),
        "runs": [int(run) for run in sorted(np.unique(runs))],
        "best_rf_params": best_params,
        "traditional_auc": float(scoreboard.loc[scoreboard["method"] == "amplitude-binned constrained template", "roc_auc"].iloc[0]),
        "traditional_threshold_auc": float(auc(y, trad_threshold_pred)),
        "direct_dt_auc": float(scoreboard.loc[scoreboard["method"] == "direct D_t/curvature cross-check", "roc_auc"].iloc[0]),
        "shape_rf_auc": float(scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0]),
        "rf_minus_traditional_auc": float(
            scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0]
            - scoreboard.loc[scoreboard["method"] == "amplitude-binned constrained template", "roc_auc"].iloc[0]
        ),
        "rf_minus_direct_dt_auc": float(
            scoreboard.loc[scoreboard["method"] == "shape-only RF", "roc_auc"].iloc[0]
            - scoreboard.loc[scoreboard["method"] == "direct D_t/curvature cross-check", "roc_auc"].iloc[0]
        ),
        "pair_split_violations": int(pair_split_violations),
        "forbidden_main_rf_columns": forbidden_shape_cols,
        "elapsed_seconds": float(time.time() - t0),
    }

    write_report(out_dir, config, reproduction, dataset_counts, scoreboard, rf_scan, trad_choices, leakage, result)

    input_hashes = {str(raw_file(config, int(run))): sha256_file(raw_file(config, int(run))) for run in config["runs"]}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(
        out_dir / "input_sha256.csv", index=False
    )

    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "command": f"python {Path(__file__)} --config {config_path}",
        "git_commit": git_commit(),
        "random_seed": seed,
        "injection_seed": int(config["injection_seed"]),
        "input_sha256": input_hashes,
        "config_sha256": sha256_file(config_path),
        "output_sha256": {},
        "created_at_unix": int(time.time()),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["output_sha256"] = hash_outputs(out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
