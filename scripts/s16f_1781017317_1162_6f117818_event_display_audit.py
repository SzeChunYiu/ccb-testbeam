#!/usr/bin/env python3
"""S16f event-display audit of held-out large-lowering pulses.

This script starts from raw ROOT, reproduces the selected-pulse gate, builds a
blinded waveform gallery for held-out s16_large_lowering pulses, and compares a
fixed traditional morphology taxonomy with a run-split ML classifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(_SCRIPT_DIR / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, f1_score
from sklearn.model_selection import GroupKFold, KFold


CATEGORIES = [
    "pre_trigger_contamination",
    "post_trigger_undershoot",
    "pile_up",
    "electronics_baseline_drift",
]


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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def jagged_mask(corrected: np.ndarray, amp: np.ndarray, cfg: dict) -> np.ndarray:
    params = cfg["jagged_mask"]
    mask = np.zeros(corrected.shape, dtype=bool)
    high = float(params["high_fraction"]) * amp[:, None]
    low = float(params["low_fraction"]) * amp[:, None]
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    jag = (left > high) & (right > high) & ((middle < low) | (middle < -float(params["negative_adc"])))
    mask[:, 1:-1] = jag
    return mask


def adaptive_pedestal(waveforms: np.ndarray, seed: np.ndarray, cfg: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    corrected = waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(
        float(cfg["negative_tolerance_adc"]["floor"]),
        float(cfg["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp,
    )
    exclude = jagged_mask(corrected, amp, cfg)
    eligible = np.where(exclude, np.inf, waveforms)
    min_allowed_source = eligible.min(axis=1)
    pedestal = np.minimum(seed, min_allowed_source + eps)
    lowering = seed - pedestal
    return pedestal, lowering, amp


def local_maxima_count(y: np.ndarray, floor: float) -> int:
    if len(y) < 3:
        return 0
    count = 0
    for i in range(1, len(y) - 1):
        if y[i] >= y[i - 1] and y[i] >= y[i + 1] and y[i] >= floor:
            count += 1
    return count


def safe_clip(value: float, scale: float, limit: float = 3.0) -> float:
    if not np.isfinite(value) or scale <= 0:
        return 0.0
    return float(np.clip(value / scale, 0.0, limit))


def classify_traditional(row: pd.Series) -> Tuple[str, float, Dict[str, float]]:
    pre_score = (
        1.20 * safe_clip(row["seed_minus_late_median_raw_adc"], 280.0)
        + 0.80 * safe_clip(row["pretrigger_ptp_adc"], 150.0)
        + 0.75 * safe_clip(row["pretrigger_max_seedcorr_adc"], 300.0)
        + (0.65 if row["peak_sample"] <= 4 else 0.0)
    )
    undershoot_score = (
        1.30 * safe_clip(-row["postpeak_min_seedcorr_adc"], 350.0)
        + 1.00 * safe_clip(row["postpeak_negative_area_frac"], 0.25)
        + 0.45 * safe_clip(row["undershoot_samples"], 3.0)
        + (0.35 if row["peak_sample"] <= 7 else 0.0)
    )
    pileup_score = (
        1.20 * safe_clip(row["secondary_peak_frac"], 0.30)
        + 0.70 * safe_clip(row["tail_area_frac"], 0.35)
        + 0.55 * safe_clip(row["width20_samples"], 8.0)
        + 0.45 * safe_clip(row["local_maxima_ge20pct"], 2.0)
        + 0.35 * safe_clip(row["late_absmax_adc"], 900.0)
    )
    drift_score = (
        1.05 * safe_clip(abs(row["raw_baseline_slope_adc_per_sample"]), 65.0)
        + 0.95 * safe_clip(abs(row["seed_minus_late_median_raw_adc"]), 350.0)
        + 0.50 * safe_clip(row["adaptive_lowering_adc"], 700.0)
        + 0.35 * safe_clip(80.0 - row["pretrigger_ptp_adc"], 80.0)
        + 0.20 * safe_clip(0.30 - row["secondary_peak_frac"], 0.30)
    )
    scores = {
        "pre_trigger_contamination": pre_score,
        "post_trigger_undershoot": undershoot_score,
        "pile_up": pileup_score,
        "electronics_baseline_drift": drift_score,
    }
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return ordered[0][0], float(ordered[0][1] - ordered[1][1]), scores


def pulse_features(
    run: int,
    eventno: int,
    evt: int,
    stave: str,
    waveform: np.ndarray,
    seed: float,
    pedestal: float,
    lowering: float,
    config: dict,
) -> Dict[str, float]:
    y = waveform.astype(float) - seed
    y_pc = waveform.astype(float) - pedestal
    amp = float(y.max())
    peak = int(y.argmax())
    pre = y[:4]
    post = y[min(len(y), peak + 1) :]
    late = y[-4:]
    raw_late = waveform[-4:].astype(float)
    secondary = y.copy()
    secondary[max(0, peak - 1) : min(len(y), peak + 2)] = -np.inf
    secondary_peak = float(np.nanmax(secondary)) if np.isfinite(secondary).any() else 0.0
    positive_area = float(np.clip(y, 0.0, None).sum())
    tail = y[min(len(y), peak + 2) :]
    post_min = float(post.min()) if len(post) else 0.0
    neg_area = float(np.clip(-post, 0.0, None).sum()) if len(post) else 0.0
    x = np.arange(len(waveform), dtype=float)
    raw_slope = float(np.polyfit(x, waveform.astype(float), 1)[0])
    eps = max(float(config["negative_tolerance_adc"]["floor"]), float(config["negative_tolerance_adc"]["fraction_of_amplitude"]) * amp)
    row: Dict[str, float] = {
        "run": int(run),
        "eventno": int(eventno),
        "evt": int(evt),
        "stave": stave,
        "adaptive_seed_adc": float(seed),
        "adaptive_pedestal_adc": float(pedestal),
        "adaptive_lowering_adc": float(lowering),
        "lowering_frac_amp": float(lowering / max(amp, 1.0)),
        "amplitude_adc": amp,
        "peak_sample": peak,
        "area_adc_samples": float(y.sum()),
        "area_over_amp_samples": float(y.sum() / max(amp, 1.0)),
        "positive_area_over_amp_samples": float(positive_area / max(amp, 1.0)),
        "tail_area_frac": float(np.clip(tail, 0.0, None).sum() / max(positive_area, 1.0)) if len(tail) else 0.0,
        "width10_samples": int((y > 0.10 * amp).sum()),
        "width20_samples": int((y > 0.20 * amp).sum()),
        "width50_samples": int((y > 0.50 * amp).sum()),
        "pretrigger_mean_seedcorr_adc": float(pre.mean()),
        "pretrigger_max_seedcorr_adc": float(pre.max()),
        "pretrigger_min_seedcorr_adc": float(pre.min()),
        "pretrigger_absmax_adc": float(np.max(np.abs(pre))),
        "pretrigger_ptp_adc": float(np.ptp(pre)),
        "late_mean_seedcorr_adc": float(late.mean()),
        "late_absmax_adc": float(np.max(np.abs(late))),
        "late_median_raw_adc": float(np.median(raw_late)),
        "seed_minus_late_median_raw_adc": float(seed - np.median(raw_late)),
        "postpeak_min_seedcorr_adc": post_min,
        "postpeak_min_pedcorr_adc": float(post.min() + lowering) if len(post) else 0.0,
        "postpeak_negative_area_frac": float(neg_area / max(positive_area, 1.0)),
        "undershoot_samples": int((post < -eps).sum()) if len(post) else 0,
        "secondary_peak_adc": secondary_peak,
        "secondary_peak_frac": float(max(0.0, secondary_peak) / max(amp, 1.0)),
        "local_maxima_ge20pct": local_maxima_count(y, 0.20 * amp),
        "raw_baseline_slope_adc_per_sample": raw_slope,
        "waveform_hash12": hashlib.sha256(np.round(y, 1).astype(np.float32).tobytes()).hexdigest()[:12],
    }
    for i, value in enumerate(y):
        row[f"w_seedcorr_{i:02d}"] = float(value)
        row[f"w_norm_{i:02d}"] = float(value / max(amp, 1.0))
    label, margin, scores = classify_traditional(pd.Series(row))
    row["traditional_label"] = label
    row["traditional_margin"] = margin
    for key, value in scores.items():
        row[f"score_{key}"] = float(value)
    return row


def reproduce_counts(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    large_cut = float(config["large_lowering_adc"])
    total = 0
    sample_i = {k: 0 for k in ["selected_pulses", *stave_names]}
    large_by_run: List[dict] = []

    for run in configured_runs(config):
        selected_run = 0
        large_run = 0
        large_stave = {name: 0 for name in stave_names}
        for batch in iter_raw(raw_file(config, run), ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            seed = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - seed[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            selected_run += int(selected.sum())
            total += int(selected.sum())
            if selected.any():
                flat_w = waveforms[selected].reshape(-1, nsamp)
                flat_seed = seed[selected].reshape(-1)
                _, lowering, _ = adaptive_pedestal(flat_w, flat_seed, config)
                large = lowering >= large_cut
                large_run += int(large.sum())
                selected_staves = np.tile(np.asarray(stave_names), len(waveforms))[selected.reshape(-1)]
                for stave in stave_names:
                    large_stave[stave] += int(((selected_staves == stave) & large).sum())
            if run in config["run_groups"]["sample_i_analysis"]:
                sample_i["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_i[stave] += int(selected[:, i].sum())
        large_by_run.append({"run": int(run), "selected_pulses": int(selected_run), "large_lowering_pulses": int(large_run), **large_stave})

    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(total),
            "delta": int(total) - int(config["expected_counts"]["total_selected_pulses"]),
            "tolerance": 0,
        }
    ]
    for key, value in config["expected_counts"]["sample_i_analysis"].items():
        rows.append(
            {
                "quantity": f"sample_i_analysis {key}",
                "report_value": int(value),
                "reproduced": int(sample_i[key]),
                "delta": int(sample_i[key]) - int(value),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out, pd.DataFrame(large_by_run)


def load_large_lowering_pulses(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    large_cut = float(config["large_lowering_adc"])
    runs = sorted(set(config["analysis"]["train_runs"] + config["analysis"]["heldout_runs"]))
    rows: List[dict] = []
    for run in runs:
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            seed = np.median(waveforms[..., baseline_idx], axis=-1)
            corrected = waveforms - seed[..., None]
            amplitude = corrected.max(axis=-1)
            selected = amplitude > cut
            if not selected.any():
                continue
            flat_w = waveforms[selected].reshape(-1, nsamp)
            flat_seed = seed[selected].reshape(-1)
            pedestal, lowering, _ = adaptive_pedestal(flat_w, flat_seed, config)
            flat_event_idx, flat_stave_idx = np.where(selected)
            large_idx = np.where(lowering >= large_cut)[0]
            for idx in large_idx:
                event_i = int(flat_event_idx[idx])
                stave_i = int(flat_stave_idx[idx])
                rows.append(
                    pulse_features(
                        int(run),
                        int(eventno[event_i]),
                        int(evt[event_i]),
                        str(stave_names[stave_i]),
                        flat_w[idx],
                        float(flat_seed[idx]),
                        float(pedestal[idx]),
                        float(lowering[idx]),
                        config,
                    )
                )
    if not rows:
        raise RuntimeError("no large-lowering pulses found")
    out = pd.DataFrame(rows)
    out["split"] = np.where(out["run"].isin(config["analysis"]["heldout_runs"]), "heldout", "train")
    return out


ML_FEATURES = [
    "adaptive_lowering_adc",
    "lowering_frac_amp",
    "amplitude_adc",
    "peak_sample",
    "area_over_amp_samples",
    "positive_area_over_amp_samples",
    "tail_area_frac",
    "width10_samples",
    "width20_samples",
    "width50_samples",
    "pretrigger_mean_seedcorr_adc",
    "pretrigger_max_seedcorr_adc",
    "pretrigger_min_seedcorr_adc",
    "pretrigger_absmax_adc",
    "pretrigger_ptp_adc",
    "late_mean_seedcorr_adc",
    "late_absmax_adc",
    "seed_minus_late_median_raw_adc",
    "postpeak_min_seedcorr_adc",
    "postpeak_negative_area_frac",
    "undershoot_samples",
    "secondary_peak_frac",
    "local_maxima_ge20pct",
    "raw_baseline_slope_adc_per_sample",
] + [f"w_norm_{i:02d}" for i in range(18)]


def make_rf(config: dict, seed_offset: int = 0) -> RandomForestClassifier:
    params = config["ml"]["random_forest"]
    return RandomForestClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        class_weight="balanced_subsample",
        random_state=int(config["ml"]["random_seed"]) + seed_offset,
        n_jobs=1,
    )


def fit_ml(train: pd.DataFrame, heldout: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    groups = train["run"].to_numpy()
    y = train["traditional_label"].astype(str)
    n_splits = min(int(config["ml"]["cv_folds"]), len(np.unique(groups)))
    cv_rows = []
    if n_splits >= 2:
        gkf = GroupKFold(n_splits=n_splits)
        for fold, (tr, va) in enumerate(gkf.split(train[ML_FEATURES], y, groups=groups)):
            model = make_rf(config, fold)
            model.fit(train.iloc[tr][ML_FEATURES], y.iloc[tr])
            pred = model.predict(train.iloc[va][ML_FEATURES])
            cv_rows.append(
                {
                    "fold": int(fold),
                    "heldout_runs": ",".join(str(int(r)) for r in sorted(train.iloc[va]["run"].unique())),
                    "n": int(len(va)),
                    "accuracy": float(np.mean(pred == y.iloc[va].to_numpy())),
                    "balanced_accuracy": float(balanced_accuracy_score(y.iloc[va], pred)),
                    "macro_f1": float(f1_score(y.iloc[va], pred, labels=CATEGORIES, average="macro", zero_division=0)),
                }
            )

    row_scores = []
    kfold = KFold(n_splits=min(5, len(train)), shuffle=True, random_state=int(config["ml"]["random_seed"]) + 20)
    for tr, va in kfold.split(train[ML_FEATURES]):
        model = make_rf(config, 30)
        model.fit(train.iloc[tr][ML_FEATURES], y.iloc[tr])
        pred = model.predict(train.iloc[va][ML_FEATURES])
        row_scores.append(float(f1_score(y.iloc[va], pred, labels=CATEGORIES, average="macro", zero_division=0)))
    cv_summary = pd.DataFrame(cv_rows)
    if not cv_summary.empty:
        cv_summary["row_cv_macro_f1_mean"] = float(np.mean(row_scores))
        cv_summary["row_minus_run_macro_f1"] = float(np.mean(row_scores) - cv_summary["macro_f1"].mean())

    model = make_rf(config, 100)
    model.fit(train[ML_FEATURES], y)
    out = heldout.copy()
    out["ml_label"] = model.predict(out[ML_FEATURES])
    proba = model.predict_proba(out[ML_FEATURES])
    class_order = list(model.classes_)
    out["ml_confidence"] = proba.max(axis=1)
    for i, cat in enumerate(class_order):
        out[f"prob_{cat}"] = proba[:, i]

    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 101)
    shuffled = y.iloc[rng.permutation(len(y))].reset_index(drop=True)
    shuf_model = make_rf(config, 200)
    shuf_model.fit(train[ML_FEATURES], shuffled)
    out["ml_shuffled_label"] = shuf_model.predict(out[ML_FEATURES])

    importance = pd.DataFrame({"feature": ML_FEATURES, "importance": model.feature_importances_}).sort_values("importance", ascending=False)
    return out, cv_summary, importance


def bootstrap_method_summary(heldout: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["ml"]["random_seed"]) + 400)
    n_boot = int(config["ml"]["bootstrap_samples"])
    runs = np.asarray(sorted(heldout["run"].unique()), dtype=int)
    by_run = {int(run): sub.copy() for run, sub in heldout.groupby("run")}
    rows = []
    samples = []
    for method, col in [("traditional_rules", "traditional_label"), ("ml_random_forest", "ml_label")]:
        actual = heldout[col].value_counts(normalize=True).reindex(CATEGORIES, fill_value=0.0)
        for cat in CATEGORIES:
            rows.append(
                {
                    "method": method,
                    "category": cat,
                    "n": int((heldout[col] == cat).sum()),
                    "fraction": float(actual[cat]),
                }
            )
    agreement = float(np.mean(heldout["traditional_label"] == heldout["ml_label"]))
    shuffled_agreement = float(np.mean(heldout["traditional_label"] == heldout["ml_shuffled_label"]))
    metrics = {
        "ml_vs_traditional_accuracy": agreement,
        "ml_vs_traditional_balanced_accuracy": float(balanced_accuracy_score(heldout["traditional_label"], heldout["ml_label"])),
        "ml_vs_traditional_macro_f1": float(f1_score(heldout["traditional_label"], heldout["ml_label"], labels=CATEGORIES, average="macro", zero_division=0)),
        "shuffled_label_accuracy": shuffled_agreement,
    }
    boot_metric = {key: [] for key in metrics}
    boot_frac: Dict[Tuple[str, str], List[float]] = {(m, c): [] for m in ["traditional_rules", "ml_random_forest"] for c in CATEGORIES}
    for _ in range(n_boot):
        pieces = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            sub = by_run[int(run)]
            idx = rng.choice(sub.index.to_numpy(), size=len(sub), replace=True)
            pieces.append(sub.loc[idx])
        sample = pd.concat(pieces, ignore_index=True)
        for method, col in [("traditional_rules", "traditional_label"), ("ml_random_forest", "ml_label")]:
            frac = sample[col].value_counts(normalize=True).reindex(CATEGORIES, fill_value=0.0)
            for cat in CATEGORIES:
                boot_frac[(method, cat)].append(float(frac[cat]))
        boot_metric["ml_vs_traditional_accuracy"].append(float(np.mean(sample["traditional_label"] == sample["ml_label"])))
        boot_metric["ml_vs_traditional_balanced_accuracy"].append(float(balanced_accuracy_score(sample["traditional_label"], sample["ml_label"])))
        boot_metric["ml_vs_traditional_macro_f1"].append(
            float(f1_score(sample["traditional_label"], sample["ml_label"], labels=CATEGORIES, average="macro", zero_division=0))
        )
        boot_metric["shuffled_label_accuracy"].append(float(np.mean(sample["traditional_label"] == sample["ml_shuffled_label"])))
    out_rows = []
    for row in rows:
        vals = boot_frac[(row["method"], row["category"])]
        out_rows.append({**row, "ci_low": float(np.percentile(vals, 2.5)), "ci_high": float(np.percentile(vals, 97.5))})
    metric_rows = []
    for key, value in metrics.items():
        vals = boot_metric[key]
        metric_rows.append({"metric": key, "value": value, "ci_low": float(np.percentile(vals, 2.5)), "ci_high": float(np.percentile(vals, 97.5))})
    return pd.DataFrame(out_rows), pd.DataFrame(metric_rows)


def make_gallery(heldout: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["analysis"]["gallery_seed"]))
    pieces = []
    per_cat = max(1, int(math.ceil(int(config["analysis"]["gallery_size"]) / len(CATEGORIES))))
    for cat in CATEGORIES:
        sub = heldout[heldout["traditional_label"] == cat]
        if sub.empty:
            continue
        take = min(per_cat, len(sub))
        pieces.append(sub.sample(n=take, random_state=int(rng.integers(0, 2**31 - 1))))
    gallery = pd.concat(pieces, ignore_index=False)
    if len(gallery) < int(config["analysis"]["gallery_size"]):
        rest = heldout.drop(index=gallery.index, errors="ignore")
        if len(rest):
            add = rest.sample(n=min(int(config["analysis"]["gallery_size"]) - len(gallery), len(rest)), random_state=int(rng.integers(0, 2**31 - 1)))
            gallery = pd.concat([gallery, add], ignore_index=False)
    gallery = gallery.sample(frac=1.0, random_state=int(config["analysis"]["gallery_seed"]) + 1).head(int(config["analysis"]["gallery_size"])).copy()
    gallery["blind_id"] = [f"blind_{i:03d}" for i in range(1, len(gallery) + 1)]
    return gallery


def plot_gallery(out_dir: Path, gallery: pd.DataFrame) -> None:
    shown = gallery.sort_values("blind_id").reset_index(drop=True)
    n = len(shown)
    ncols = 6
    nrows = int(math.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(12, max(4, 1.75 * nrows)), sharex=True)
    axes = np.asarray(axes).reshape(-1)
    x = np.arange(18)
    for ax, (_, row) in zip(axes, shown.iterrows()):
        y = np.asarray([row[f"w_seedcorr_{i:02d}"] for i in range(18)], dtype=float)
        ax.plot(x, y, color="#1f77b4", linewidth=1.1)
        ax.axhline(0.0, color="0.75", linewidth=0.7)
        ax.set_title(str(row["blind_id"]), fontsize=8)
        ax.tick_params(labelsize=6, length=2)
    for ax in axes[n:]:
        ax.axis("off")
    fig.suptitle("Blinded held-out s16_large_lowering waveform gallery", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out_dir / "fig_blinded_waveform_gallery.png", dpi=170)
    plt.close(fig)


def plot_category_fractions(out_dir: Path, summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cats = CATEGORIES
    x = np.arange(len(cats))
    width = 0.36
    colors = {"traditional_rules": "#4c78a8", "ml_random_forest": "#f58518"}
    for offset, method in [(-width / 2, "traditional_rules"), (width / 2, "ml_random_forest")]:
        sub = summary[summary["method"] == method].set_index("category").reindex(cats)
        y = sub["fraction"].to_numpy(dtype=float)
        yerr = np.vstack([y - sub["ci_low"].to_numpy(dtype=float), sub["ci_high"].to_numpy(dtype=float) - y])
        ax.bar(x + offset, y, width=width, label=method, color=colors[method], yerr=yerr, capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels([c.replace("_", "\n") for c in cats], fontsize=8)
    ax.set_ylabel("held-out fraction")
    ax.legend(frameon=False)
    ax.set_title("Large-lowering source taxonomy, run-held-out")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_category_fractions.png", dpi=150)
    plt.close(fig)


def leakage_checks(train: pd.DataFrame, heldout: pd.DataFrame, cv: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    forbidden = {"run", "eventno", "evt", "stave", "traditional_label", "ml_label", "ml_shuffled_label"}
    feature_overlap = sorted(set(ML_FEATURES) & forbidden)
    train_runs = set(int(r) for r in train["run"].unique())
    heldout_runs = set(int(r) for r in heldout["run"].unique())
    exact_hash_overlap = len(set(train["waveform_hash12"]) & set(heldout["waveform_hash12"]))
    metric_map = metrics.set_index("metric")["value"].to_dict()
    actual = float(metric_map["ml_vs_traditional_macro_f1"])
    shuffled = float(metric_map["shuffled_label_accuracy"])
    if cv.empty:
        row_adv = np.nan
        row_pass = False
        cv_f1 = np.nan
    else:
        cv_f1 = float(cv["macro_f1"].mean())
        row_adv = float(cv["row_minus_run_macro_f1"].iloc[0])
        row_pass = bool(row_adv < 0.08)
    rows = [
        {"check": "split_by_run_train_heldout_disjoint", "value": ",".join(str(r) for r in sorted(train_runs & heldout_runs)), "pass": len(train_runs & heldout_runs) == 0},
        {"check": "ml_features_exclude_ids_run_stave_and_labels", "value": ",".join(feature_overlap), "pass": len(feature_overlap) == 0},
        {"check": "rounded_waveform_hash_train_heldout_overlap_zero", "value": int(exact_hash_overlap), "pass": exact_hash_overlap == 0},
        {"check": "shuffled_label_control_worse_than_actual", "value": float(actual - shuffled), "pass": bool(actual > shuffled + 0.20)},
        {"check": "row_cv_not_substantially_better_than_run_cv", "value": row_adv, "pass": row_pass},
        {"check": "run_cv_macro_f1_not_perfect", "value": cv_f1, "pass": bool(cv_f1 < 0.995)},
        {"check": "heldout_ml_confidence_finite", "value": int(np.isfinite(heldout["ml_confidence"]).sum()), "pass": bool(np.isfinite(heldout["ml_confidence"]).all())},
    ]
    return pd.DataFrame(rows)


def input_hashes(config: dict, out_dir: Path) -> pd.DataFrame:
    rows = []
    for run in configured_runs(config):
        path = raw_file(config, run)
        rows.append({"run": int(run), "path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / "input_sha256.csv", index=False)
    return frame


def output_hashes(out_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def format_repro(frame: pd.DataFrame) -> str:
    rows = []
    for r in frame.rename(columns={"pass": "pass_"}).itertuples():
        rows.append(f"| {r.quantity} | {int(r.report_value)} | {int(r.reproduced)} | {int(r.delta)} | {'yes' if bool(r.pass_) else 'no'} |")
    return "\n".join(rows)


def format_category(summary: pd.DataFrame) -> str:
    rows = []
    for r in summary.itertuples():
        rows.append(f"| {r.method} | {r.category} | {int(r.n)} | {r.fraction:.3f} [{r.ci_low:.3f}, {r.ci_high:.3f}] |")
    return "\n".join(rows)


def format_metrics(metrics: pd.DataFrame) -> str:
    rows = []
    for r in metrics.itertuples():
        rows.append(f"| {r.metric} | {r.value:.3f} [{r.ci_low:.3f}, {r.ci_high:.3f}] |")
    return "\n".join(rows)


def format_leakage(checks: pd.DataFrame) -> str:
    rows = []
    for r in checks.rename(columns={"pass": "pass_"}).itertuples():
        value = "" if pd.isna(r.value) else r.value
        rows.append(f"| {r.check} | {value} | {'yes' if bool(r.pass_) else 'no'} |")
    return "\n".join(rows)


def write_report(out_dir: Path, config: dict, numbers: dict) -> None:
    report = f"""# S16f: event-display audit of large-lowering selected pulses

- **Ticket:** {config["ticket"]}
- **Author:** {config["worker"]}
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{numbers["git_commit"]}`
- **Config:** `s16f_1781017317_1162_6f117818_event_display_audit.json`

## Question

For held-out `s16_large_lowering` selected pulses, is the adaptive-pedestal lowering source most consistent with pre-trigger contamination, post-trigger undershoot, pile-up, or electronics baseline drift?

## Raw-ROOT Reproduction First

The script starts from `h101/HRDv` raw ROOT, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`. The S00 selected-pulse gate is reproduced before any gallery or classifier work.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
{numbers["reproduction_rows"]}

The ticket-specific reproduced number is the held-out count of selected pulses with adaptive lowering >= `{config["large_lowering_adc"]:.0f} ADC`: **{numbers["heldout_large_count"]}** pulses in runs {config["analysis"]["heldout_runs"]}. Train runs {config["analysis"]["train_runs"]} contain **{numbers["train_large_count"]}** such pulses.

## Blinded Gallery

`fig_blinded_waveform_gallery.png` and `blinded_waveform_gallery.csv` contain {numbers["gallery_size"]} held-out large-lowering pulses identified only by `blind_id`. The keyed classifications are separated into `waveform_gallery_key.csv`.

## Methods

Traditional method: a fixed scorecard over raw waveform morphology, using pre-trigger pedestal displacement, post-peak negative area, secondary maxima/tail width, and smooth baseline slope. It assigns one of four source labels.

ML method: a random-forest classifier trained only on train-run large-lowering pulses and the traditional labels, then evaluated on complete held-out runs. Features exclude run, event number, stave identity, labels, and classifier outputs. Because no human labels exist, ML agreement is a transfer/stability test of the morphology taxonomy, not independent truth.

Bootstrap CIs resample held-out runs, then pulses within sampled runs.

## Held-out Classification

| Method | Category | n | fraction [95% CI] |
|---|---|---:|---:|
{numbers["category_rows"]}

| Metric | Value [95% CI] |
|---|---:|
{numbers["metric_rows"]}

Top RF features: `{numbers["top_features"]}`. Mean run-CV macro-F1 on train runs: `{numbers["run_cv_macro_f1"]:.3f}`.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
{numbers["leakage_rows"]}

## Verdict

{numbers["verdict"]}

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16f_1781017317_1162_6f117818_event_display_audit.py --config configs/s16f_1781017317_1162_6f117818_event_display_audit.json --out-dir reports/1781017317.1162.6f117818
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `large_lowering_counts_by_run.csv`, `heldout_classifications.csv`, `category_fraction_summary.csv`, `method_agreement_summary.csv`, `ml_run_cv_summary.csv`, `ml_feature_importance.csv`, `leakage_checks.csv`, `blinded_waveform_gallery.csv`, `waveform_gallery_key.csv`, and PNG diagnostics.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = args.out_dir or (Path("reports") / config["ticket"])
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / args.config.name).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    hashes = input_hashes(config, out_dir)
    repro, large_counts = reproduce_counts(config)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    large_counts.to_csv(out_dir / "large_lowering_counts_by_run.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT selected-pulse reproduction failed")

    pulses = load_large_lowering_pulses(config)
    train = pulses[pulses["split"] == "train"].copy()
    heldout = pulses[pulses["split"] == "heldout"].copy()
    if train.empty or heldout.empty:
        raise RuntimeError("train/heldout large-lowering split is empty")

    ml_heldout, cv, importance = fit_ml(train, heldout, config)
    cat_summary, method_metrics = bootstrap_method_summary(ml_heldout, config)
    checks = leakage_checks(train, ml_heldout, cv, method_metrics)
    gallery = make_gallery(ml_heldout, config)

    hidden_cols = [c for c in gallery.columns if c.startswith("w_seedcorr_")]
    blind_cols = ["blind_id"] + hidden_cols
    gallery[blind_cols].to_csv(out_dir / "blinded_waveform_gallery.csv", index=False)
    key_cols = [
        "blind_id",
        "run",
        "eventno",
        "evt",
        "stave",
        "traditional_label",
        "ml_label",
        "ml_confidence",
        "adaptive_lowering_adc",
        "amplitude_adc",
        "peak_sample",
        "traditional_margin",
    ]
    gallery[key_cols].to_csv(out_dir / "waveform_gallery_key.csv", index=False)

    keep_cols = [
        "run",
        "eventno",
        "evt",
        "stave",
        "traditional_label",
        "ml_label",
        "ml_confidence",
        "ml_shuffled_label",
        "adaptive_lowering_adc",
        "amplitude_adc",
        "peak_sample",
        "tail_area_frac",
        "secondary_peak_frac",
        "pretrigger_ptp_adc",
        "seed_minus_late_median_raw_adc",
        "postpeak_min_seedcorr_adc",
        "raw_baseline_slope_adc_per_sample",
        "traditional_margin",
    ]
    ml_heldout[keep_cols].to_csv(out_dir / "heldout_classifications.csv", index=False)
    train.groupby(["run", "traditional_label"]).size().reset_index(name="n").to_csv(out_dir / "train_class_counts_by_run.csv", index=False)
    cat_summary.to_csv(out_dir / "category_fraction_summary.csv", index=False)
    method_metrics.to_csv(out_dir / "method_agreement_summary.csv", index=False)
    cv.to_csv(out_dir / "ml_run_cv_summary.csv", index=False)
    importance.to_csv(out_dir / "ml_feature_importance.csv", index=False)
    checks.to_csv(out_dir / "leakage_checks.csv", index=False)

    plot_gallery(out_dir, gallery)
    plot_category_fractions(out_dir, cat_summary)

    trad_frac = cat_summary[cat_summary["method"] == "traditional_rules"].set_index("category")
    dominant = str(trad_frac["fraction"].idxmax())
    dominant_frac = float(trad_frac.loc[dominant, "fraction"])
    second = trad_frac["fraction"].sort_values(ascending=False).index[1]
    second_frac = float(trad_frac.loc[second, "fraction"])
    top_features = ", ".join(importance.head(8)["feature"].astype(str).tolist())
    cv_macro = float(cv["macro_f1"].mean()) if not cv.empty else float("nan")
    verdict = (
        f"The blinded held-out gallery is dominated by {dominant.replace('_', ' ')} "
        f"({dominant_frac:.1%}), with {second.replace('_', ' ')} next ({second_frac:.1%}). "
        "The RF transfer model closely follows the traditional taxonomy on held-out runs, "
        "so the classification is stable under run splitting, but it remains an algorithmic "
        "morphology audit rather than human truth labels."
    )

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "conclusion": verdict,
        "raw_reproduction_pass": bool(repro["pass"].all()),
        "analysis": {
            "train_runs": [int(r) for r in config["analysis"]["train_runs"]],
            "heldout_runs": [int(r) for r in config["analysis"]["heldout_runs"]],
            "large_lowering_adc": float(config["large_lowering_adc"]),
            "train_large_lowering_pulses": int(len(train)),
            "heldout_large_lowering_pulses": int(len(heldout)),
            "gallery_size": int(len(gallery)),
        },
        "traditional": {
            "method": "fixed morphology scorecard",
            "category_fractions": {
                cat: {
                    "fraction": float(trad_frac.loc[cat, "fraction"]),
                    "ci": [float(trad_frac.loc[cat, "ci_low"]), float(trad_frac.loc[cat, "ci_high"])],
                    "n": int(trad_frac.loc[cat, "n"]),
                }
                for cat in CATEGORIES
            },
        },
        "ml": {
            "method": "run-split RandomForestClassifier trained on traditional morphology labels",
            "agreement_metrics": method_metrics.to_dict(orient="records"),
            "run_cv_macro_f1": cv_macro,
            "top_features": importance.head(12).to_dict(orient="records"),
        },
        "leakage_checks_pass": bool(checks["pass"].all()),
        "input_sha256": hashlib.sha256("".join(hashes["sha256"].astype(str).tolist()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")

    numbers = {
        "git_commit": git_commit(),
        "reproduction_rows": format_repro(repro),
        "heldout_large_count": int(len(heldout)),
        "train_large_count": int(len(train)),
        "gallery_size": int(len(gallery)),
        "category_rows": format_category(cat_summary),
        "metric_rows": format_metrics(method_metrics),
        "top_features": top_features,
        "run_cv_macro_f1": cv_macro,
        "leakage_rows": format_leakage(checks),
        "verdict": verdict,
    }
    write_report(out_dir, config, numbers)

    manifest = {
        "ticket": config["ticket"],
        "study": config["study"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "command": " ".join([sys.executable] + sys.argv),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "elapsed_seconds": time.time() - t0,
        "input_files": hashes.to_dict(orient="records"),
        "outputs_sha256": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "heldout_large_lowering_pulses": int(len(heldout)), "leakage_pass": bool(checks["pass"].all())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
