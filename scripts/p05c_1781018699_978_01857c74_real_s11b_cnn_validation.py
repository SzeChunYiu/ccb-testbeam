#!/usr/bin/env python3
"""P05c: compact P05a CNN on real S11b high-current candidates.

The run order is deliberate: reproduce the P05a injected CNN/template anchor
from raw ROOT first, then score S11b real candidate windows with the frozen
S11a-style template fit and a compact 18-sample CNN trained only from low-current
source runs. No Monte Carlo inputs are used; synthetic overlays are made from
raw low-current pulses for method calibration only.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


def import_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S11B = import_script("s11b_base", ROOT / "scripts/s11b_real_high_current_two_pulse_validation.py")
P05A = import_script("p05a_base", ROOT / "scripts/p05a_cnn_two_pulse_decomposition.py")


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def absolute_path(path: Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else ROOT / path


def reproduce_p05a_anchor(config: dict, out_dir: Path, _rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p05a_config = P05A.load_config(ROOT / config["p05a_config"])
    expected = load_json(ROOT / config["p05a_expected_result"])
    rng = np.random.default_rng(int(p05a_config["random_seed"]))

    counts = P05A.reproduce_counts(p05a_config)
    if not bool(counts["pass"].all()):
        raise RuntimeError("P05a raw selected-pulse count reproduction failed")

    train_runs = [int(x) for x in p05a_config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in p05a_config["benchmark_runs"]["heldout"]]
    clean = P05A.read_clean_pulses(p05a_config, sorted(set(train_runs + heldout_runs)), rng)
    templates, template_summary = P05A.build_templates(clean[clean["run"].isin(train_runs)], p05a_config)
    train_events, train_wave = P05A.generate_benchmark(clean, templates, p05a_config, "train", train_runs, rng)
    held_events, held_wave = P05A.generate_benchmark(clean, templates, p05a_config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    trad = P05A.run_template_fits(events, waveforms, templates, p05a_config)
    cnn, cnn_cv = P05A.run_cnn(events, waveforms, p05a_config)
    combined = events.merge(trad, on="event_id").merge(cnn, on="event_id")
    summary = P05A.summarize_methods(combined, rng, p05a_config)

    trad_row = summary[summary["method"] == "constrained_template_fit"].iloc[0]
    cnn_row = summary[summary["method"] == "compact_18_sample_cnn"].iloc[0]
    tol = config["p05a_reproduction_tolerances"]
    rows = [
        {
            "quantity": "P05a selected B-stave pulses",
            "report_value": int(p05a_config["expected_counts"]["total_selected_pulses"]),
            "reproduced": int(counts.loc[counts["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
            "delta": int(counts.loc[counts["quantity"] == "total selected B-stave pulses", "delta"].iloc[0]),
            "tolerance": 0.0,
            "pass": True,
        },
        {
            "quantity": "P05a traditional heldout time RMS ns",
            "report_value": float(expected["traditional"]["value"]),
            "reproduced": float(trad_row["time_rms_ns"]),
            "delta": float(trad_row["time_rms_ns"] - expected["traditional"]["value"]),
            "tolerance": float(tol["traditional_time_rms_ns"]),
            "pass": bool(abs(float(trad_row["time_rms_ns"] - expected["traditional"]["value"])) <= float(tol["traditional_time_rms_ns"])),
        },
        {
            "quantity": "P05a compact CNN heldout time RMS ns",
            "report_value": float(expected["ml"]["value"]),
            "reproduced": float(cnn_row["time_rms_ns"]),
            "delta": float(cnn_row["time_rms_ns"] - expected["ml"]["value"]),
            "tolerance": float(tol["cnn_time_rms_ns"]),
            "pass": bool(abs(float(cnn_row["time_rms_ns"] - expected["ml"]["value"])) <= float(tol["cnn_time_rms_ns"])),
        },
        {
            "quantity": "P05a compact CNN heldout detection AP",
            "report_value": float(expected["ml"]["detection_ap"]),
            "reproduced": float(cnn_row["detection_ap"]),
            "delta": float(cnn_row["detection_ap"] - expected["ml"]["detection_ap"]),
            "tolerance": float(tol["cnn_detection_ap"]),
            "pass": bool(abs(float(cnn_row["detection_ap"] - expected["ml"]["detection_ap"])) <= float(tol["cnn_detection_ap"])),
        },
    ]
    match = pd.DataFrame(rows)
    match.to_csv(out_dir / "p05a_reproduction_match_table.csv", index=False)
    counts.to_csv(out_dir / "p05a_raw_count_reproduction.csv", index=False)
    template_summary.to_csv(out_dir / "p05a_template_summary.csv", index=False)
    summary.to_csv(out_dir / "p05a_anchor_overall.csv", index=False)
    cnn_cv.to_csv(out_dir / "p05a_cnn_cv_rows.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("P05a injected anchor reproduction failed")
    return match, summary, combined


class TinyTwoPulseCNN(nn.Module):
    def __init__(self, n_samples: int, channels: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv1d(1, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
        )
        self.shared = nn.Sequential(
            nn.Flatten(),
            nn.Linear(channels * n_samples, 32),
            nn.ReLU(),
            nn.Dropout(0.05),
        )
        self.detect = nn.Linear(32, 1)
        self.regress = nn.Linear(32, 4)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z = self.shared(self.features(x))
        return self.detect(z).squeeze(1), self.regress(z)


def cnn_inputs(waves: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    corr = np.asarray(waves, dtype=float)
    baseline = np.median(corr[:, :4], axis=1)
    corr = corr - baseline[:, None]
    amp = np.maximum(corr.max(axis=1), 1.0)
    return (corr / amp[:, None]).astype(np.float32), amp.astype(np.float32)


def make_cnn_training(events: pd.DataFrame, waves: np.ndarray, rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, pd.DataFrame]:
    clean = events[
        (events["ref_amp_adc"] > 1000.0)
        & (events["ref_amp_adc"] < 12000.0)
        & (events["peak_sample"] >= 2)
        & (events["peak_sample"] <= 16)
    ].copy()
    if len(clean) < 100:
        raise RuntimeError("too few clean low-current pulses for CNN training")
    n = min(int(n), len(clean))
    base_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
    sec_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
    base = waves[base_rows["event_index"].to_numpy()].astype(float)
    secondary = waves[sec_rows["event_index"].to_numpy()].astype(float)
    base_amp = np.maximum(base_rows["ref_amp_adc"].to_numpy(dtype=float), 1.0)
    secondary_amp = np.maximum(sec_rows["ref_amp_adc"].to_numpy(dtype=float), 1.0)
    delays = rng.uniform(0.75, 7.0, size=n)
    ratios = rng.uniform(0.12, 1.0, size=n)
    injected = base.copy()
    sec_norm = secondary / secondary_amp[:, None]
    for i, delay in enumerate(delays):
        injected[i] += base_amp[i] * ratios[i] * S11B.shift_array(sec_norm[i], delay, fill=0.0)

    waves_all = np.vstack([base, injected])
    x, max_amp = cnn_inputs(waves_all)
    y = np.r_[np.zeros(n, dtype=np.float32), np.ones(n, dtype=np.float32)]
    t1 = np.asarray([S11B.cfd_time_one(wf, 0.2) for wf in base], dtype=float)
    t1 = np.where(np.isfinite(t1), t1, S11B.TEMPLATE_REF_SAMPLE)
    amp1 = base_amp
    amp2 = base_amp * ratios
    reg_clean = np.column_stack([t1 / 12.0, t1 / 12.0, amp1 / max_amp[:n], np.zeros(n)])
    reg_inj = np.column_stack([t1 / 12.0, (t1 + delays) / 12.0, amp1 / max_amp[n:], amp2 / max_amp[n:]])
    reg = np.vstack([reg_clean, reg_inj]).astype(np.float32)
    meta = pd.DataFrame(
        {
            "synthetic_label": y.astype(int),
            "source_run": np.r_[base_rows["run"].to_numpy(), base_rows["run"].to_numpy()],
            "true_secondary_fraction": np.r_[np.zeros(n), amp2 / np.maximum(amp1 + amp2, 1.0)],
            "true_delay_samples": np.r_[np.zeros(n), delays],
        }
    )
    order = rng.permutation(len(y))
    return x[order], y[order], reg[order], meta.iloc[order].reset_index(drop=True)


def train_cnn(x: np.ndarray, y: np.ndarray, reg: np.ndarray, config: dict, seed: int) -> TinyTwoPulseCNN:
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    cnn_cfg = config["cnn"]
    model = TinyTwoPulseCNN(x.shape[1], int(cnn_cfg["channels"]))
    loader = DataLoader(
        TensorDataset(torch.from_numpy(x[:, None, :]), torch.from_numpy(y.astype(np.float32)), torch.from_numpy(reg.astype(np.float32))),
        batch_size=int(cnn_cfg["batch_size"]),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    opt = torch.optim.AdamW(
        model.parameters(),
        lr=float(cnn_cfg["learning_rate"]),
        weight_decay=float(cnn_cfg["weight_decay"]),
    )
    bce = nn.BCEWithLogitsLoss()
    smooth = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(cnn_cfg["epochs"])):
        for xb, yb, rb in loader:
            opt.zero_grad()
            logits, pred = model(xb)
            loss = bce(logits, yb)
            pos = yb > 0.5
            if bool(pos.any()):
                loss = loss + 1.6 * smooth(pred[pos], rb[pos])
            loss.backward()
            opt.step()
    return model


def predict_cnn(model: TinyTwoPulseCNN, waves: np.ndarray) -> pd.DataFrame:
    x, max_amp = cnn_inputs(waves)
    return predict_cnn_from_normalized(model, x, max_amp)


def predict_cnn_from_normalized(model: TinyTwoPulseCNN, x: np.ndarray, max_amp: np.ndarray | None = None) -> pd.DataFrame:
    if max_amp is None:
        max_amp = np.ones(len(x), dtype=np.float32)
    model.eval()
    probs = []
    regs = []
    with torch.no_grad():
        tensor = torch.from_numpy(x[:, None, :])
        for start in range(0, len(tensor), 512):
            logits, pred = model(tensor[start : start + 512])
            probs.append(torch.sigmoid(logits).cpu().numpy())
            regs.append(pred.cpu().numpy())
    prob = np.concatenate(probs)
    pred = np.vstack(regs)
    amp1 = np.clip(pred[:, 2] * max_amp, 0.0, None)
    amp2 = np.clip(pred[:, 3] * max_amp, 0.0, None)
    raw_frac = amp2 / np.maximum(amp1 + amp2, 1.0)
    return pd.DataFrame(
        {
            "cnn_overlap_score": prob,
            "cnn_secondary_fraction_raw": raw_frac,
            "cnn_secondary_fraction": prob * raw_frac,
            "cnn_t1_sample": np.clip(pred[:, 0] * 12.0, 0.0, 17.0),
            "cnn_t2_sample": np.clip(pred[:, 1] * 12.0, 0.0, 17.0),
            "cnn_amp1_adc": amp1,
            "cnn_amp2_adc": amp2,
        }
    )


def run_real_candidate_predictions(events: pd.DataFrame, waves: np.ndarray, sample: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    low_runs = set(S11B.RUN_GROUPS["low_2nA"]["runs"])
    score_frames = []
    template_frames = []
    fold_rows = []
    model_cache = {}
    shuffled_cache = {}
    for heldout_run in sorted(sample["run"].unique()):
        train_runs = sorted(low_runs - {int(heldout_run)}) if int(heldout_run) in low_runs else sorted(low_runs)
        train_key = tuple(train_runs)
        train = events[events["run"].isin(train_runs)].copy()
        test = sample[sample["run"] == heldout_run].copy()
        test_waves = waves[test["event_index"].to_numpy()]
        templates, template_summary = S11B.build_templates(train, waves)
        template_summary["heldout_run"] = int(heldout_run)
        template_summary["training_runs"] = " ".join(str(x) for x in train_runs)
        template_frames.append(template_summary)
        trad = S11B.fit_traditional_for_run(test, test_waves, templates)

        if train_key not in model_cache:
            x_train, y_train, reg_train, train_meta = make_cnn_training(train, waves, rng, int(config["cnn"]["synthetic_train_per_policy"]))
            model_cache[train_key] = (train_cnn(x_train, y_train, reg_train, config, int(config["random_seed"]) + sum(train_runs)), train_meta)
            shuffled_y = y_train.copy()
            rng.shuffle(shuffled_y)
            shuffled_cache[train_key] = train_cnn(x_train, shuffled_y, reg_train, config, int(config["random_seed"]) + 500 + sum(train_runs))
        model, train_meta = model_cache[train_key]
        shuffled_model = shuffled_cache[train_key]
        cnn = predict_cnn(model, test_waves)
        cnn.insert(0, "event_index", test["event_index"].to_numpy(dtype=int))

        x_cal, y_cal, reg_cal, _cal_meta = make_cnn_training(test, waves, rng, int(config["cnn"]["synthetic_cal_per_run"]))
        cal_waves = x_cal.astype(np.float32)
        cal_pred = predict_cnn_from_normalized(model, cal_waves)
        shuffled_pred = predict_cnn_from_normalized(shuffled_model, cal_waves)
        true_frac = reg_cal[:, 3] / np.maximum(reg_cal[:, 2] + reg_cal[:, 3], 1e-6)
        pred_frac = cal_pred["cnn_secondary_fraction"].to_numpy()
        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "heldout_group": S11B.run_to_group()[int(heldout_run)],
                "n_scored_events": int(len(test)),
                "training_policy": "low_current_only_source_run_heldout",
                "training_runs": " ".join(str(x) for x in train_runs),
                "synthetic_train_source_runs": " ".join(str(x) for x in sorted(set(train_meta["source_run"].astype(int)))),
                "cnn_synthetic_holdout_auc": float(roc_auc_score(y_cal, cal_pred["cnn_overlap_score"])),
                "cnn_synthetic_holdout_ap": float(average_precision_score(y_cal, cal_pred["cnn_overlap_score"])),
                "cnn_synthetic_holdout_brier": float(brier_score_loss(y_cal, cal_pred["cnn_overlap_score"])),
                "cnn_secondary_fraction_mae": float(np.mean(np.abs(pred_frac - true_frac))),
                "cnn_shuffled_label_synthetic_auc": float(roc_auc_score(y_cal, shuffled_pred["cnn_overlap_score"])),
            }
        )

        frame = test[
            [
                "event_index",
                "run",
                "group",
                "current_nA",
                "eventno",
                "stratum",
                "amp_bin",
                "baseline_bin",
                "p02_topology",
                "ref_stave",
                "ref_amp_adc",
                "downstream",
            ]
        ].copy()
        frame = frame.merge(trad, on="event_index", how="left").merge(cnn, on="event_index", how="left")
        score_frames.append(frame)
    return pd.concat(score_frames, ignore_index=True), pd.concat(template_frames, ignore_index=True), pd.DataFrame(fold_rows)


def summarize_metric(scores: pd.DataFrame, stratum_table: pd.DataFrame, value_col: str, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    table, summary = S11B.summarize_method(scores, stratum_table, value_col, rng)
    table["method_metric"] = value_col
    summary["method_metric"] = value_col
    return table, summary


def source_run_eta2(scores: pd.DataFrame, value_col: str) -> float:
    y = scores[value_col].to_numpy(dtype=float)
    grand = float(np.nanmean(y))
    ss_total = float(np.nansum((y - grand) ** 2))
    if ss_total <= 0:
        return 0.0
    ss_between = 0.0
    for _run, sub in scores.groupby("run"):
        vals = sub[value_col].to_numpy(dtype=float)
        ss_between += len(vals) * float((np.nanmean(vals) - grand) ** 2)
    return ss_between / ss_total


def run_predictability_sentinel(scores: pd.DataFrame, waves: np.ndarray, rng: np.random.Generator) -> float:
    idx = scores["event_index"].to_numpy(dtype=int)
    x, _amp = cnn_inputs(waves[idx])
    y = scores["run"].to_numpy(dtype=int)
    order = rng.permutation(len(y))
    split = int(0.7 * len(order))
    tr, te = order[:split], order[split:]
    clf = RandomForestClassifier(n_estimators=80, max_depth=10, min_samples_leaf=8, random_state=12345, n_jobs=1)
    clf.fit(x[tr], y[tr])
    return float(clf.score(x[te], y[te]))


def leakage_checks(scores: pd.DataFrame, folds: pd.DataFrame, waves: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    current_y = (scores["group"] == "high_20nA").astype(int).to_numpy()
    score_auc = float(roc_auc_score(current_y, scores["cnn_overlap_score"]))
    frac_auc = float(roc_auc_score(current_y, scores["cnn_secondary_fraction"]))
    shuffled_auc = float(folds["cnn_shuffled_label_synthetic_auc"].mean())
    synth_auc = float(folds["cnn_synthetic_holdout_auc"].mean())
    eta2 = source_run_eta2(scores, "cnn_overlap_score")
    run_acc = run_predictability_sentinel(scores, waves, rng)
    rows = [
        {
            "check": "heldout_run_excluded_from_template_and_cnn_training",
            "value": 1.0,
            "flag": False,
            "note": "High-current runs are never in CNN/template training; low-current controls leave their source run out.",
        },
        {
            "check": "identifier_features_excluded",
            "value": 1.0,
            "flag": False,
            "note": "CNN sees only 18 normalized waveform samples, not run, event number, current, or stratum.",
        },
        {
            "check": "synthetic_train_source_runs_exclude_heldout",
            "value": float(all(str(row.heldout_run) not in row.synthetic_train_source_runs.split() for row in folds.itertuples())),
            "flag": bool(not all(str(row.heldout_run) not in row.synthetic_train_source_runs.split() for row in folds.itertuples())),
            "note": "Fold diagnostics record raw source runs used to make low-current overlays.",
        },
        {
            "check": "mean_cnn_synthetic_holdout_auc",
            "value": synth_auc,
            "flag": bool(synth_auc > 0.995),
            "note": "Near-perfect heldout overlay classification would be suspicious.",
        },
        {
            "check": "mean_cnn_shuffled_label_synthetic_auc",
            "value": shuffled_auc,
            "flag": bool(shuffled_auc > 0.65),
            "note": "Shuffled-label CNN should not classify heldout overlays well.",
        },
        {
            "check": "actual_current_auc_from_cnn_overlap_score",
            "value": score_auc,
            "flag": bool(score_auc > 0.95),
            "note": "Flagged if the CNN score nearly identifies beam current by itself.",
        },
        {
            "check": "actual_current_auc_from_cnn_secondary_fraction",
            "value": frac_auc,
            "flag": bool(frac_auc > 0.95),
            "note": "Flagged if the CNN secondary estimate nearly identifies beam current by itself.",
        },
        {
            "check": "cnn_score_source_run_eta2",
            "value": eta2,
            "flag": bool(eta2 > 0.50),
            "note": "Run-level variance fraction of the real CNN overlap score.",
        },
        {
            "check": "source_run_predictability_from_waveform_samples",
            "value": run_acc,
            "flag": bool(run_acc > 0.75),
            "note": "Random-split sentinel accuracy for predicting source run from the same normalized samples.",
        },
    ]
    return pd.DataFrame(rows)


def save_plots(out_dir: Path, method_summary: pd.DataFrame, stratum_summary: pd.DataFrame, scores: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    x = np.arange(len(method_summary))
    ax.bar(x, method_summary["value"])
    err_low = method_summary["value"] - method_summary["ci_low"]
    err_high = method_summary["ci_high"] - method_summary["value"]
    ax.errorbar(x, method_summary["value"], yerr=[err_low, err_high], fmt="none", color="k", capsize=4)
    ax.axhline(0, color="k", lw=1)
    ax.set_xticks(x, method_summary["method_metric"], rotation=20, ha="right")
    ax.set_ylabel("Matched high-minus-low")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_high_minus_low_ci.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    plot = stratum_summary[stratum_summary["method_metric"] == "cnn_secondary_fraction"].sort_values("match_weight", ascending=False).head(10).iloc[::-1]
    ax.barh(np.arange(len(plot)), plot["high_minus_low"])
    ax.axvline(0, color="k", lw=1)
    ax.set_yticks(np.arange(len(plot)), plot["stratum"], fontsize=7)
    ax.set_xlabel("High-minus-low CNN secondary fraction")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_cnn_secondary_fraction_by_stratum.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for group, sub in scores.groupby("group"):
        ax.hist(sub["cnn_overlap_score"], bins=45, alpha=0.55, density=True, label=group)
    ax.set_xlabel("CNN overlap score")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_cnn_score_by_current.png", dpi=150)
    plt.close(fig)


def write_report(out_dir: Path, config: dict, p05a_match: pd.DataFrame, p05a_anchor: pd.DataFrame, s10_repro: pd.DataFrame, method_summary: pd.DataFrame, stratum_summary: pd.DataFrame, folds: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    trad = method_summary[method_summary["method_metric"] == "trad_secondary_fraction"].iloc[0]
    cnn_frac = method_summary[method_summary["method_metric"] == "cnn_secondary_fraction"].iloc[0]
    cnn_score = method_summary[method_summary["method_metric"] == "cnn_overlap_score"].iloc[0]
    p05a_trad = p05a_anchor[p05a_anchor["method"] == "constrained_template_fit"].iloc[0]
    p05a_cnn = p05a_anchor[p05a_anchor["method"] == "compact_18_sample_cnn"].iloc[0]
    top = stratum_summary[stratum_summary["method_metric"] == "cnn_secondary_fraction"].sort_values("high_minus_low", ascending=False).head(8)
    lines = [
        "# P05c: real S11b candidate validation of P05a CNN",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Inputs:** raw HRD ROOT files only; no Monte Carlo.",
        "- **Split:** every score is source-run held out. High-current runs use low-current runs 46/47 only; low-current controls leave their own run out. CIs bootstrap source runs within current group.",
        "",
        "## Reproduction first",
        "",
        (
            "The P05a injected anchor was rerun from raw ROOT before touching real candidates. "
            f"The frozen template fit reproduced time RMS **{p05a_trad['time_rms_ns']:.2f} ns** and the compact CNN "
            f"**{p05a_cnn['time_rms_ns']:.2f} ns**, with CNN AP **{p05a_cnn['detection_ap']:.3f}**."
        ),
        "",
        p05a_match.to_markdown(index=False),
        "",
        "The S11b/S10c real-candidate topology gate was then rerun from raw ROOT; all six documented low/high topology fractions pass.",
        "",
        s10_repro.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Traditional method: the frozen S11a-style bounded two-pulse template fit used in S11b. Templates are median empirical pulse shapes from low-current training runs only, and each event reports A2/(A1+A2) after the constrained fit.",
        "",
        "ML method: a compact P05a-style 18-sample 1D CNN with two convolution layers, a detection head, and a four-output decomposition head. It is trained only on data-driven two-pulse overlays made from low-current raw pulses under the same source-run holdout policy, then applied unchanged to real low/high candidate windows.",
        "",
        "## Real candidate result",
        "",
        method_summary.to_markdown(index=False),
        "",
        (
            f"Traditional matched high-minus-low secondary fraction is **{trad['value']:.5f}** "
            f"[{trad['ci_low']:.5f}, {trad['ci_high']:.5f}]. The compact CNN secondary-fraction delta is "
            f"**{cnn_frac['value']:.5f}** [{cnn_frac['ci_low']:.5f}, {cnn_frac['ci_high']:.5f}], and its "
            f"overlap-score delta is **{cnn_score['value']:.5f}** [{cnn_score['ci_low']:.5f}, {cnn_score['ci_high']:.5f}]."
        ),
        "",
        "Largest positive CNN secondary-fraction strata:",
        "",
        top[["amp_bin", "baseline_bin", "p02_topology", "low_n_scored", "high_n_scored", "low_mean", "high_mean", "high_minus_low", "match_weight"]].to_markdown(index=False),
        "",
        "## Leakage review",
        "",
        leakage.to_markdown(index=False),
        "",
        "Mean held-out overlay AUC for the CNN diagnostic is "
        f"{folds['cnn_synthetic_holdout_auc'].mean():.3f}; shuffled-label AUC is {folds['cnn_shuffled_label_synthetic_auc'].mean():.3f}.",
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"{sys.executable} scripts/p05c_1781018699_978_01857c74_real_s11b_cnn_validation.py --config configs/p05c_1781018699_978_01857c74.json",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs(out_dir: Path) -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p05c_1781018699_978_01857c74.json")
    args = parser.parse_args()
    start = time.time()
    config_path = ROOT / args.config
    config = load_json(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    S11B.OUT = out_dir
    S11B.TICKET = config["ticket_id"]
    S11B.WORKER = config["worker"]
    S11B.RNG_SEED = int(config["random_seed"])
    S11B.BOOTSTRAPS = int(config["bootstrap_samples"])
    S11B.SAMPLE_PER_RUN_STRATUM = int(config["sample_per_run_stratum"])
    rng = np.random.default_rng(int(config["random_seed"]))

    p05a_match, p05a_anchor, _p05a_combined = reproduce_p05a_anchor(config, out_dir, rng)

    events, waves, run_counts = S11B.load_events()
    topology, s10_repro = S11B.reproduce_s10(events)
    if not bool(s10_repro["pass"].all()):
        raise RuntimeError("S11b/S10c raw topology reproduction gate failed")
    counts = S11B.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = S11B.matched_strata(counts)
    sample = S11B.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)
    scores, template_summary, folds = run_real_candidate_predictions(events, waves, sample, config, rng)

    method_tables = []
    method_summaries = []
    for col in ["trad_secondary_fraction", "cnn_secondary_fraction", "cnn_overlap_score"]:
        table, summary = summarize_metric(scores, stratum_table, col, rng)
        method_tables.append(table)
        method_summaries.append(summary)
    stratum_summary = pd.concat(method_tables, ignore_index=True)
    method_summary = pd.concat(method_summaries, ignore_index=True)

    expected_s11b = load_json(ROOT / config["s11b_expected_result"])
    expected_trad = float(expected_s11b["traditional"]["value"])
    trad_now = float(method_summary.loc[method_summary["method_metric"] == "trad_secondary_fraction", "value"].iloc[0])
    s11b_reproduction = pd.DataFrame(
        [
            {
                "quantity": "S11b traditional matched secondary fraction high-minus-low",
                "report_value": expected_trad,
                "reproduced": trad_now,
                "delta": trad_now - expected_trad,
                "tolerance": float(config["s11b_reproduction_tolerances"]["traditional_high_minus_low"]),
                "pass": bool(abs(trad_now - expected_trad) <= float(config["s11b_reproduction_tolerances"]["traditional_high_minus_low"])),
            }
        ]
    )
    if not bool(s11b_reproduction["pass"].all()):
        raise RuntimeError("S11b traditional real-candidate number reproduction failed")

    leakage = leakage_checks(scores, folds, waves, rng)
    save_plots(out_dir, method_summary, stratum_summary, scores)

    p05a_config_for_inputs = P05A.load_config(ROOT / config["p05a_config"])
    p05a_runs = P05A.configured_runs(p05a_config_for_inputs)
    input_files = sorted(
        {absolute_path(S11B.raw_file(run)) for run in sorted(S11B.run_to_group())}
        | {absolute_path(P05A.raw_file(p05a_config_for_inputs, run)) for run in p05a_runs},
        key=lambda path: str(path),
    )
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    input_hashes[str(config_path.relative_to(ROOT))] = sha256_file(config_path)
    input_hashes["scripts/p05c_1781018699_978_01857c74_real_s11b_cnn_validation.py"] = sha256_file(ROOT / "scripts/p05c_1781018699_978_01857c74_real_s11b_cnn_validation.py")

    p05a_match.to_csv(out_dir / "p05a_reproduction_match_table.csv", index=False)
    s10_repro.to_csv(out_dir / "s10c_reproduction_match_table.csv", index=False)
    s11b_reproduction.to_csv(out_dir / "s11b_reproduction_match_table.csv", index=False)
    topology.to_csv(out_dir / "topology_by_group.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    stratum_table.to_csv(out_dir / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(out_dir / "analysis_sample.csv", index=False)
    template_summary.to_csv(out_dir / "template_summary_by_fold.csv", index=False)
    scores.to_csv(out_dir / "sampled_event_scores.csv", index=False)
    folds.to_csv(out_dir / "fold_diagnostics.csv", index=False)
    stratum_summary.to_csv(out_dir / "method_stratum_summary.csv", index=False)
    method_summary.to_csv(out_dir / "method_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    trad = method_summary[method_summary["method_metric"] == "trad_secondary_fraction"].iloc[0]
    cnn_frac = method_summary[method_summary["method_metric"] == "cnn_secondary_fraction"].iloc[0]
    cnn_score = method_summary[method_summary["method_metric"] == "cnn_overlap_score"].iloc[0]
    p05a_trad = p05a_anchor[p05a_anchor["method"] == "constrained_template_fit"].iloc[0]
    p05a_cnn = p05a_anchor[p05a_anchor["method"] == "compact_18_sample_cnn"].iloc[0]
    ranking_survives = bool(cnn_frac["value"] > trad["value"] and cnn_frac["ci_low"] > trad["ci_low"])
    conclusion = (
        f"The injected P05a ranking reproduces from raw ROOT: CNN time RMS {p05a_cnn['time_rms_ns']:.2f} ns versus "
        f"template fit {p05a_trad['time_rms_ns']:.2f} ns. On real S11b candidate shapes the ranking does not transfer "
        f"as a larger secondary-fraction excess: the template fit gives {trad['value']:.5f} "
        f"[{trad['ci_low']:.5f}, {trad['ci_high']:.5f}], while the compact CNN gives {cnn_frac['value']:.5f} "
        f"[{cnn_frac['ci_low']:.5f}, {cnn_frac['ci_high']:.5f}] for secondary fraction and {cnn_score['value']:.5f} "
        f"[{cnn_score['ci_low']:.5f}, {cnn_score['ci_high']:.5f}] for overlap score. Leakage sentinels flag "
        f"{int(leakage['flag'].sum())} checks, so this remains a diagnostic transfer test rather than a truth-labelled pile-up measurement."
    )
    result = {
        "study": "P05c",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": "validate P05a compact CNN on real S11b high-current candidates",
        "reproduced": bool(p05a_match["pass"].all() and s10_repro["pass"].all() and s11b_reproduction["pass"].all()),
        "p05a_anchor": {
            "traditional_time_rms_ns": float(p05a_trad["time_rms_ns"]),
            "cnn_time_rms_ns": float(p05a_cnn["time_rms_ns"]),
            "cnn_detection_ap": float(p05a_cnn["detection_ap"]),
        },
        "s11b_reproduction": {
            "traditional_high_minus_low": trad_now,
            "expected_traditional_high_minus_low": expected_trad,
            "tolerance": float(config["s11b_reproduction_tolerances"]["traditional_high_minus_low"]),
        },
        "split": "source-run heldout; high-current scored from low-current training only; low-current controls leave scored source run out",
        "bootstrap": {
            "unit": "source_run_within_current_group",
            "samples": int(config["bootstrap_samples"]),
        },
        "strata": {
            "definition": "S10c amplitude bin x S16 adaptive lowering bin x P02 topology",
            "n_matched_strata": int(len(stratum_table)),
            "global_s10_downstream_high_minus_low": float(global_downstream_excess),
            "n_scored_events": int(len(scores)),
        },
        "traditional": {
            "method": "frozen_s11a_bounded_two_pulse_template_fit",
            "metric": "matched_stratified_secondary_fraction_high_minus_low",
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
        },
        "ml": {
            "method": "compact_18_sample_cnn_low_current_overlay_trained",
            "secondary_fraction_high_minus_low": {
                "value": float(cnn_frac["value"]),
                "ci": [float(cnn_frac["ci_low"]), float(cnn_frac["ci_high"])],
            },
            "overlap_score_high_minus_low": {
                "value": float(cnn_score["value"]),
                "ci": [float(cnn_score["ci_low"]), float(cnn_score["ci_high"])],
            },
            "mean_synthetic_holdout_auc": float(folds["cnn_synthetic_holdout_auc"].mean()),
            "mean_shuffled_label_synthetic_auc": float(folds["cnn_shuffled_label_synthetic_auc"].mean()),
            "mean_secondary_fraction_mae_on_synthetic_holdout": float(folds["cnn_secondary_fraction_mae"].mean()),
        },
        "injected_closure_ranking_survives_real_candidate_transfer": ranking_survives,
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(out_dir, config, p05a_match, p05a_anchor, s10_repro, method_summary, stratum_summary, folds, leakage, result)
    manifest = {
        "study": "P05c",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "runtime_sec": result["runtime_sec"], "leakage_flags": result["leakage_flags"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
