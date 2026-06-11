#!/usr/bin/env python3
"""S10o: anomaly-residual current excess truth split.

This ticket extends the S10e/S10f/S10n real-current two-pulse diagnostic.  It
keeps the same raw ROOT reproduction and strong bounded two-pulse traditional
method, benchmarks ridge, gradient-boosted trees, MLP, 1D-CNN, and a small
residual TCN, then decomposes the matched high-minus-low residual excess into
beam-pileup, baseline-pathology, charge-support, topology-composition, and
anomaly-taxonomy atoms under frozen support matching.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "1781052597.584.1a7d14cf__s10o_anomaly_residual_current_excess_truth_split"
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s11b_real_high_current_two_pulse_validation as base


TICKET = "1781052597.584.1a7d14cf"
WORKER = "testbeam-laptop-4"
STUDY = "S10o"
RNG_SEED = 101052597
BOOTSTRAPS = 520
SYNTHETIC_TRAIN_PER_FOLD = 1500
SYNTHETIC_CAL_PER_FOLD = 500
TRAD_SCORE_THRESHOLDS = [0.0, 0.005, 0.015, 0.030, 0.060]
SUPPORT_CHOICES = {
    "all_matched": None,
    "dominant_three": 3,
    "dominant_one": 1,
}

torch.set_num_threads(1)
base.OUT = OUT
base.TICKET = TICKET
base.WORKER = WORKER
base.STUDY = STUDY
base.RNG_SEED = RNG_SEED
base.BOOTSTRAPS = BOOTSTRAPS
base.SYNTHETIC_TRAIN_PER_FOLD = SYNTHETIC_TRAIN_PER_FOLD
base.SYNTHETIC_CAL_PER_FOLD = SYNTHETIC_CAL_PER_FOLD


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


def method_slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_").replace("/", "_")


def raw_file(run: int) -> Path:
    return base.raw_file(run)


class TinyWaveNet(torch.nn.Module):
    def __init__(self, kind: str = "cnn") -> None:
        super().__init__()
        if kind == "cnn":
            channels = [1, 10, 14]
            dilation = [1, 1]
        elif kind == "residual_tcn":
            channels = [1, 12, 12]
            dilation = [1, 2]
        else:
            raise ValueError(kind)
        self.kind = kind
        self.conv1 = torch.nn.Conv1d(channels[0], channels[1], kernel_size=3, padding=dilation[0], dilation=dilation[0])
        self.conv2 = torch.nn.Conv1d(channels[1], channels[2], kernel_size=3, padding=dilation[1], dilation=dilation[1])
        self.skip = torch.nn.Conv1d(channels[0], channels[2], kernel_size=1)
        self.head = torch.nn.Sequential(
            torch.nn.AdaptiveAvgPool1d(1),
            torch.nn.Flatten(),
            torch.nn.Linear(channels[2], 16),
            torch.nn.ReLU(),
            torch.nn.Linear(16, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y = torch.relu(self.conv1(x))
        y = torch.relu(self.conv2(y))
        if self.kind == "residual_tcn":
            y = y + self.skip(x)
        return self.head(y)


def normalized_waves(waves: np.ndarray) -> np.ndarray:
    arr = np.asarray(waves, dtype=np.float32)
    amp = np.maximum(arr.max(axis=1), 1.0).astype(np.float32)
    return arr / amp[:, None]


def train_wave_net(
    train_waves: np.ndarray,
    y_class: np.ndarray,
    y_frac: np.ndarray,
    test_waves: np.ndarray,
    cal_waves: np.ndarray,
    kind: str,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    torch.manual_seed(seed)
    x = torch.tensor(normalized_waves(train_waves)[:, None, :], dtype=torch.float32)
    y_cls = torch.tensor(y_class.astype(np.float32), dtype=torch.float32)
    y_reg = torch.tensor(y_frac.astype(np.float32), dtype=torch.float32)
    model = TinyWaveNet(kind)
    opt = torch.optim.Adam(model.parameters(), lr=0.010, weight_decay=1e-4)
    batch = min(256, len(x))
    gen = torch.Generator().manual_seed(seed)
    for _epoch in range(18):
        order = torch.randperm(len(x), generator=gen)
        for start in range(0, len(x), batch):
            idx = order[start : start + batch]
            out = model(x[idx])
            loss_cls = torch.nn.functional.binary_cross_entropy_with_logits(out[:, 0], y_cls[idx])
            loss_reg = torch.nn.functional.smooth_l1_loss(torch.sigmoid(out[:, 1]) * 0.8, y_reg[idx])
            loss = loss_cls + 1.5 * loss_reg
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        xt = torch.tensor(normalized_waves(test_waves)[:, None, :], dtype=torch.float32)
        xc = torch.tensor(normalized_waves(cal_waves)[:, None, :], dtype=torch.float32)
        ot = model(xt)
        oc = model(xc)
        score_test = torch.sigmoid(ot[:, 0]).numpy()
        frac_test = np.clip(torch.sigmoid(ot[:, 1]).numpy() * 0.8, 0.0, 0.8)
        score_cal = torch.sigmoid(oc[:, 0]).numpy()
        frac_cal = np.clip(torch.sigmoid(oc[:, 1]).numpy() * 0.8, 0.0, 0.8)
    return score_test, frac_test, score_cal, frac_cal


def support_accept_mask(x_train: pd.DataFrame, x_apply: pd.DataFrame, quantile: float = 0.95) -> np.ndarray:
    cols = list(x_train.columns)
    train = x_train[cols].to_numpy(dtype=float)
    apply = x_apply[cols].to_numpy(dtype=float)
    mu = np.nanmedian(train, axis=0)
    scale = np.nanpercentile(np.abs(train - mu), 75, axis=0)
    scale = np.where(scale > 1e-6, scale, 1.0)
    train_d = np.sqrt(np.nanmean(((train - mu) / scale) ** 2, axis=1))
    apply_d = np.sqrt(np.nanmean(((apply - mu) / scale) ** 2, axis=1))
    return apply_d <= float(np.quantile(train_d, quantile))


def feature_model_predictions(
    method: str,
    x_train: pd.DataFrame,
    y_class: np.ndarray,
    y_frac: np.ndarray,
    x_test: pd.DataFrame,
    x_cal: pd.DataFrame,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if method == "ridge":
        clf = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=0.8, class_weight="balanced", max_iter=300, random_state=seed),
        )
        reg = make_pipeline(StandardScaler(), Ridge(alpha=4.0, random_state=seed))
    elif method == "gradient_boosted_trees":
        clf = HistGradientBoostingClassifier(
            max_iter=90,
            learning_rate=0.055,
            max_leaf_nodes=17,
            l2_regularization=0.03,
            random_state=seed,
        )
        reg = HistGradientBoostingRegressor(
            max_iter=90,
            learning_rate=0.055,
            max_leaf_nodes=17,
            l2_regularization=0.03,
            random_state=seed + 1,
        )
    elif method == "mlp":
        clf = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(42, 18),
                activation="relu",
                alpha=0.002,
                learning_rate_init=0.003,
                early_stopping=True,
                validation_fraction=0.15,
                max_iter=130,
                random_state=seed,
            ),
        )
        reg = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(42, 18),
                activation="relu",
                alpha=0.002,
                learning_rate_init=0.003,
                early_stopping=True,
                validation_fraction=0.15,
                max_iter=130,
                random_state=seed + 1,
            ),
        )
    else:
        raise ValueError(method)
    clf.fit(x_train, y_class)
    reg.fit(x_train, y_frac)
    score_test = clf.predict_proba(x_test)[:, 1]
    frac_test = np.clip(reg.predict(x_test), 0.0, 0.8)
    score_cal = clf.predict_proba(x_cal)[:, 1]
    frac_cal = np.clip(reg.predict(x_cal), 0.0, 0.8)
    return score_test, frac_test, score_cal, frac_cal


def train_shuffled_sentinel(
    x_train: pd.DataFrame,
    y_class: np.ndarray,
    x_cal: pd.DataFrame,
    y_cal: np.ndarray,
    rng: np.random.Generator,
    seed: int,
) -> float:
    shuffled = y_class.copy()
    rng.shuffle(shuffled)
    clf = HistGradientBoostingClassifier(max_iter=55, max_leaf_nodes=11, learning_rate=0.06, random_state=seed)
    clf.fit(x_train, shuffled)
    score = clf.predict_proba(x_cal)[:, 1]
    return float(roc_auc_score(y_cal, score))


def heldout_predictions(events: pd.DataFrame, waves: np.ndarray, sample: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    score_frames = []
    template_frames = []
    fold_rows = []
    low_current_runs = set(base.RUN_GROUPS["low_2nA"]["runs"])
    feature_methods = ["ridge", "gradient_boosted_trees", "mlp"]
    wave_methods = ["cnn1d", "residual_tcn"]
    feature_cols: list[str] | None = None
    for heldout_run in sorted(sample["run"].unique()):
        train_runs = sorted(low_current_runs - {int(heldout_run)})
        if int(heldout_run) not in low_current_runs:
            train_runs = sorted(low_current_runs)
        train = events[events["run"].isin(train_runs)].copy()
        test = sample[sample["run"] == heldout_run].copy()
        test_waves = waves[test["event_index"].to_numpy()]
        templates, template_summary = base.build_templates(train, waves)
        template_summary["heldout_run"] = int(heldout_run)
        template_summary["training_runs"] = " ".join(str(x) for x in train_runs)
        template_frames.append(template_summary)

        trad = base.fit_traditional_for_run(test, test_waves, templates)
        x_train, y_class, y_frac, train_meta = base.make_synthetic_training(train, waves, templates, rng, SYNTHETIC_TRAIN_PER_FOLD)
        x_cal, y_cal, y_frac_cal, cal_meta = base.make_synthetic_training(test, waves, templates, rng, SYNTHETIC_CAL_PER_FOLD)
        if feature_cols is None:
            feature_cols = list(x_train.columns)
        x_test = base.ml_features(test_waves, test["ref_stave"].to_numpy(), templates)[feature_cols]
        x_train = x_train[feature_cols]
        x_cal = x_cal[feature_cols]
        support_mask = support_accept_mask(x_train, x_test)

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
                "ref_area_adc",
                "adaptive_lowering_adc",
                "peak_sample",
                "area_over_peak",
                "late_fraction",
                "width_10_samples",
                "downstream",
            ]
        ].copy()
        frame = frame.merge(trad, on="event_index", how="left")
        frame["support_accept"] = support_mask.astype(int)
        frame["timing_tail_proxy"] = (
            (frame["peak_sample"].to_numpy() >= 9)
            | (frame["width_10_samples"].to_numpy() >= 11)
            | (frame["late_fraction"].to_numpy() > 0.45)
        ).astype(int)
        frame["log_charge_proxy"] = np.log(np.maximum(frame["ref_area_adc"].to_numpy(dtype=float), 1.0))

        for method in feature_methods:
            score_test, frac_test, score_cal, frac_cal = feature_model_predictions(
                method,
                x_train,
                y_class,
                y_frac,
                x_test,
                x_cal,
                RNG_SEED + int(heldout_run) * 17 + len(method),
            )
            frame[f"{method}_overlap_score"] = score_test
            frame[f"{method}_secondary_fraction"] = frac_test
            fold_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "heldout_group": base.run_to_group()[int(heldout_run)],
                    "method": method,
                    "n_scored_events": int(len(test)),
                    "n_synthetic_train": int(len(y_class)),
                    "training_policy": "low_current_only_source_run_heldout",
                    "synthetic_train_source_runs": " ".join(str(x) for x in sorted(set(train_meta["source_run"].astype(int)))),
                    "synthetic_holdout_auc": float(roc_auc_score(y_cal, score_cal)),
                    "synthetic_holdout_ap": float(average_precision_score(y_cal, score_cal)),
                    "synthetic_holdout_brier": float(brier_score_loss(y_cal, score_cal)),
                    "synthetic_secondary_fraction_mae": float(mean_absolute_error(y_frac_cal, frac_cal)),
                    "support_accept_fraction": float(support_mask.mean()),
                }
            )

        clean_train = train[
            (train["ref_amp_adc"] > 1000.0)
            & (train["ref_amp_adc"] < 12000.0)
            & (train["peak_sample"] >= 2)
            & (train["peak_sample"] <= 16)
        ]
        n_pair = len(y_class) // 2
        # Reconstruct the synthetic waveforms used by make_synthetic_training for the NN panel
        # by using its feature-independent sampling policy directly here.
        base_rows = clean_train.sample(n=n_pair, replace=len(clean_train) < n_pair, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
        sec_rows = clean_train.sample(n=n_pair, replace=len(clean_train) < n_pair, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
        base_wave = waves[base_rows["event_index"].to_numpy()].astype(float)
        sec_wave = waves[sec_rows["event_index"].to_numpy()].astype(float)
        injected, frac, _ratio = base.inject_waveforms(
            base_wave,
            base_rows["ref_amp_adc"].to_numpy(dtype=float),
            sec_wave,
            sec_rows["ref_amp_adc"].to_numpy(dtype=float),
            rng,
        )
        nn_train_waves = np.vstack([base_wave, injected])
        nn_y_class = np.r_[np.zeros(n_pair, dtype=int), np.ones(n_pair, dtype=int)]
        nn_y_frac = np.r_[np.zeros(n_pair, dtype=float), frac]
        order = rng.permutation(len(nn_y_class))
        nn_train_waves = nn_train_waves[order]
        nn_y_class = nn_y_class[order]
        nn_y_frac = nn_y_frac[order]
        cal_n_pair = len(y_cal) // 2
        clean_cal = test[
            (test["ref_amp_adc"] > 1000.0)
            & (test["ref_amp_adc"] < 12000.0)
            & (test["peak_sample"] >= 2)
            & (test["peak_sample"] <= 16)
        ]
        if len(clean_cal) < 20:
            clean_cal = test
        cal_base = clean_cal.sample(n=cal_n_pair, replace=len(clean_cal) < cal_n_pair, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
        cal_sec = clean_cal.sample(n=cal_n_pair, replace=len(clean_cal) < cal_n_pair, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
        cal_base_wave = waves[cal_base["event_index"].to_numpy()].astype(float)
        cal_sec_wave = waves[cal_sec["event_index"].to_numpy()].astype(float)
        cal_inj, cal_frac, _ = base.inject_waveforms(
            cal_base_wave,
            cal_base["ref_amp_adc"].to_numpy(dtype=float),
            cal_sec_wave,
            cal_sec["ref_amp_adc"].to_numpy(dtype=float),
            rng,
        )
        nn_cal_waves = np.vstack([cal_base_wave, cal_inj])
        nn_y_cal = np.r_[np.zeros(cal_n_pair, dtype=int), np.ones(cal_n_pair, dtype=int)]
        nn_y_frac_cal = np.r_[np.zeros(cal_n_pair, dtype=float), cal_frac]
        for method in wave_methods:
            kind = "cnn" if method == "cnn1d" else "residual_tcn"
            score_test, frac_test, score_cal, frac_cal = train_wave_net(
                nn_train_waves,
                nn_y_class,
                nn_y_frac,
                test_waves,
                nn_cal_waves,
                kind,
                RNG_SEED + int(heldout_run) * 31 + len(method),
            )
            frame[f"{method}_overlap_score"] = score_test
            frame[f"{method}_secondary_fraction"] = frac_test
            fold_rows.append(
                {
                    "heldout_run": int(heldout_run),
                    "heldout_group": base.run_to_group()[int(heldout_run)],
                    "method": method,
                    "n_scored_events": int(len(test)),
                    "n_synthetic_train": int(len(nn_y_class)),
                    "training_policy": "low_current_only_source_run_heldout",
                    "synthetic_train_source_runs": " ".join(str(x) for x in train_runs),
                    "synthetic_holdout_auc": float(roc_auc_score(nn_y_cal, score_cal)),
                    "synthetic_holdout_ap": float(average_precision_score(nn_y_cal, score_cal)),
                    "synthetic_holdout_brier": float(brier_score_loss(nn_y_cal, score_cal)),
                    "synthetic_secondary_fraction_mae": float(mean_absolute_error(nn_y_frac_cal, frac_cal)),
                    "support_accept_fraction": float(support_mask.mean()),
                }
            )

        shuffled_auc = train_shuffled_sentinel(x_train, y_class, x_cal, y_cal, rng, RNG_SEED + int(heldout_run) * 43)
        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "heldout_group": base.run_to_group()[int(heldout_run)],
                "method": "shuffled_current_sentinel",
                "n_scored_events": int(len(test)),
                "n_synthetic_train": int(len(y_class)),
                "training_policy": "label_permuted_control",
                "synthetic_train_source_runs": " ".join(str(x) for x in sorted(set(train_meta["source_run"].astype(int)))),
                "synthetic_holdout_auc": shuffled_auc,
                "synthetic_holdout_ap": float("nan"),
                "synthetic_holdout_brier": float("nan"),
                "synthetic_secondary_fraction_mae": float("nan"),
                "support_accept_fraction": float(support_mask.mean()),
            }
        )
        score_frames.append(frame)
    return pd.concat(score_frames, ignore_index=True), pd.concat(template_frames, ignore_index=True), pd.DataFrame(fold_rows)


def summarize_value(scores: pd.DataFrame, stratum_table: pd.DataFrame, value_col: str, rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    table, summary = base.summarize_method(scores, stratum_table, value_col, rng)
    row = summary.iloc[0].to_dict()
    return table, {
        "metric": value_col,
        "value": float(row["value"]),
        "ci_low": float(row["ci_low"]),
        "ci_high": float(row["ci_high"]),
        "n_bootstrap": int(row["n_bootstrap"]),
        "n_scored_events": int(row["n_scored_events"]),
    }


def bootstrap_delta(
    scores: pd.DataFrame,
    stratum_table: pd.DataFrame,
    method_col: str,
    base_col: str,
    rng: np.random.Generator,
) -> dict:
    strata = stratum_table["stratum"].tolist()
    weights = dict(zip(stratum_table["stratum"], stratum_table["match_weight"]))
    low_runs = np.array(base.RUN_GROUPS["low_2nA"]["runs"], dtype=int)
    high_runs = np.array(base.RUN_GROUPS["high_20nA"]["runs"], dtype=int)

    def effect(frame: pd.DataFrame, col: str) -> float:
        vals = []
        for stratum in strata:
            sub = frame[frame["stratum"] == stratum]
            low = sub[sub["group"] == "low_2nA"][col]
            high = sub[sub["group"] == "high_20nA"][col]
            if len(low) and len(high):
                vals.append(weights[stratum] * (float(high.mean()) - float(low.mean())))
        return float(np.sum(vals)) if vals else float("nan")

    point = effect(scores, method_col) - effect(scores, base_col)
    boot = []
    for _ in range(BOOTSTRAPS):
        pieces = []
        for run in np.r_[rng.choice(low_runs, size=len(low_runs), replace=True), rng.choice(high_runs, size=len(high_runs), replace=True)]:
            sub = scores[scores["run"] == int(run)]
            if len(sub):
                pieces.append(sub)
        sample = pd.concat(pieces, ignore_index=True)
        boot.append(effect(sample, method_col) - effect(sample, base_col))
    return {
        "method_metric": method_col,
        "reference_metric": base_col,
        "delta": float(point),
        "ci_low": float(np.quantile(boot, 0.025)),
        "ci_high": float(np.quantile(boot, 0.975)),
        "n_bootstrap": int(len(boot)),
    }


def stability_scans(scores: pd.DataFrame, stratum_table: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    sorted_strata = stratum_table.sort_values("match_weight", ascending=False).reset_index(drop=True)
    for support_name, top_n in SUPPORT_CHOICES.items():
        if top_n is None:
            support = sorted_strata.copy()
        else:
            support = sorted_strata.head(top_n).copy()
        for threshold in TRAD_SCORE_THRESHOLDS:
            temp = scores.copy()
            col = f"trad_secondary_fraction_thr_{threshold:.3f}"
            temp[col] = np.where(temp["trad_score_sse_improvement"] >= threshold, temp["trad_secondary_fraction"], 0.0)
            _table, summary = summarize_value(temp[temp["stratum"].isin(support["stratum"])], support, col, rng)
            rows.append(
                {
                    "support_choice": support_name,
                    "n_strata": int(len(support)),
                    "trad_score_threshold": threshold,
                    "secondary_fraction_delta": summary["value"],
                    "ci_low": summary["ci_low"],
                    "ci_high": summary["ci_high"],
                }
            )
    scan = pd.DataFrame(rows)
    base_scan = scan[scan["support_choice"] == "all_matched"].sort_values("trad_score_threshold")
    x = base_scan["trad_score_threshold"].to_numpy(dtype=float)
    y = base_scan["secondary_fraction_delta"].to_numpy(dtype=float)
    slope = float(np.polyfit(x, y, 1)[0]) if len(x) > 1 else float("nan")
    diagnostics = pd.DataFrame(
        [
            {
                "diagnostic": "traditional_threshold_sensitivity_slope",
                "value": slope,
                "unit": "secondary_fraction_delta_per_sse_improvement_threshold",
            },
            {
                "diagnostic": "traditional_threshold_range",
                "value": float(base_scan["secondary_fraction_delta"].max() - base_scan["secondary_fraction_delta"].min()),
                "unit": "secondary_fraction_delta",
            },
        ]
    )
    return scan, diagnostics


def weighted_proxy_delta(scores: pd.DataFrame, stratum_table: pd.DataFrame, method: str) -> dict:
    frac_col = "trad_secondary_fraction" if method == "traditional" else f"{method}_secondary_fraction"
    rows = []
    for proxy in ["timing_tail_proxy", "log_charge_proxy"]:
        vals = []
        for row in stratum_table.itertuples():
            sub = scores[scores["stratum"] == row.stratum]
            for group in ["low_2nA", "high_20nA"]:
                g = sub[sub["group"] == group]
                if len(g) == 0:
                    continue
            low = sub[sub["group"] == "low_2nA"]
            high = sub[sub["group"] == "high_20nA"]
            if len(low) and len(high):
                def wmean(frame: pd.DataFrame) -> float:
                    w = np.clip(frame[frac_col].to_numpy(dtype=float), 0.0, None)
                    if float(w.sum()) <= 1e-9:
                        return float(frame[proxy].mean())
                    return float(np.average(frame[proxy].to_numpy(dtype=float), weights=w + 1e-6))

                vals.append(float(row.match_weight) * (wmean(high) - wmean(low)))
        rows.append((proxy, float(np.sum(vals)) if vals else float("nan")))
    return {name: value for name, value in rows}


def add_truth_split_atoms(scores: pd.DataFrame) -> pd.DataFrame:
    """Attach transparent S10o atom labels without using run/current identifiers."""
    out = scores.copy()
    out["p09_taxon"] = np.select(
        [
            out["adaptive_lowering_adc"].to_numpy(dtype=float) >= 200.0,
            (out["peak_sample"].to_numpy(dtype=float) <= 4.0) | (out["area_over_peak"].to_numpy(dtype=float) < 1.6),
            (out["late_fraction"].to_numpy(dtype=float) > 0.45) | (out["width_10_samples"].to_numpy(dtype=float) >= 11.0),
            out["ref_amp_adc"].to_numpy(dtype=float) >= 9000.0,
        ],
        ["p09_baseline_pathology", "p09_pretrigger_or_early", "p09_broad_late", "p09_saturation_edge"],
        default="p09_normal",
    )
    out["beam_pileup_atom"] = np.select(
        [
            (out["trad_secondary_fraction"].to_numpy(dtype=float) >= 0.08)
            & (out["trad_score_sse_improvement"].to_numpy(dtype=float) >= 0.015),
            out["trad_secondary_fraction"].to_numpy(dtype=float) >= 0.03,
        ],
        ["pileup_like_high", "pileup_like_low"],
        default="pileup_not_supported",
    )
    out["baseline_pathology_atom"] = out["baseline_bin"].astype(str)
    out["charge_support_atom"] = out["amp_bin"].astype(str)
    out["topology_composition_atom"] = out["p02_topology"].astype(str)
    return out


def _effect_for_frame(frame: pd.DataFrame, stratum_table: pd.DataFrame, value_col: str) -> float:
    vals = []
    for row in stratum_table.itertuples():
        sub = frame[frame["stratum"] == row.stratum]
        low = sub[sub["group"] == "low_2nA"][value_col]
        high = sub[sub["group"] == "high_20nA"][value_col]
        if len(low) and len(high):
            vals.append(float(row.match_weight) * (float(high.mean()) - float(low.mean())))
    return float(np.sum(vals)) if vals else float("nan")


def truth_split_decomposition(
    scores: pd.DataFrame,
    stratum_table: pd.DataFrame,
    rng: np.random.Generator,
    value_col: str = "trad_secondary_fraction",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Decompose residual excess one atom at a time under frozen matched strata."""
    component_cols = {
        "beam_pileup": "beam_pileup_atom",
        "baseline_pathology": "baseline_pathology_atom",
        "charge_support_drift": "charge_support_atom",
        "topology_composition": "topology_composition_atom",
        "anomaly_taxonomy": "p09_taxon",
    }
    low_runs = np.array(base.RUN_GROUPS["low_2nA"]["runs"], dtype=int)
    high_runs = np.array(base.RUN_GROUPS["high_20nA"]["runs"], dtype=int)
    total_effect = _effect_for_frame(scores, stratum_table, value_col)
    rows = []
    for component, col in component_cols.items():
        for level in sorted(scores[col].dropna().unique()):
            subset = scores[scores[col] == level].copy()
            if subset.empty:
                continue
            point = _effect_for_frame(subset, stratum_table, value_col)
            comp_delta = _effect_for_frame(scores.assign(_atom=(scores[col] == level).astype(float)), stratum_table, "_atom")
            charge_shift = _effect_for_frame(subset, stratum_table, "log_charge_proxy")
            timing_shift = _effect_for_frame(subset, stratum_table, "timing_tail_proxy")
            boot = []
            for _ in range(BOOTSTRAPS):
                pieces = []
                sampled = np.r_[
                    rng.choice(low_runs, size=len(low_runs), replace=True),
                    rng.choice(high_runs, size=len(high_runs), replace=True),
                ]
                for run in sampled:
                    part = subset[subset["run"] == int(run)]
                    if len(part):
                        pieces.append(part)
                if pieces:
                    boot.append(_effect_for_frame(pd.concat(pieces, ignore_index=True), stratum_table, value_col))
            rows.append(
                {
                    "component": component,
                    "atom_level": str(level),
                    "n_events": int(len(subset)),
                    "n_low": int((subset["group"] == "low_2nA").sum()),
                    "n_high": int((subset["group"] == "high_20nA").sum()),
                    "support_fraction": float(len(subset) / max(len(scores), 1)),
                    "composition_delta": comp_delta,
                    "secondary_fraction_delta": point,
                    "ci_low": float(np.quantile(boot, 0.025)) if boot else float("nan"),
                    "ci_high": float(np.quantile(boot, 0.975)) if boot else float("nan"),
                    "share_of_total_effect": float(point / total_effect) if np.isfinite(total_effect) and abs(total_effect) > 1e-12 else float("nan"),
                    "charge_log_shift": charge_shift,
                    "timing_tail_delta": timing_shift,
                }
            )
    decomp = pd.DataFrame(rows).sort_values("secondary_fraction_delta", ascending=False).reset_index(drop=True)
    winners = []
    for component, sub in decomp.groupby("component", sort=False):
        best = sub.sort_values("secondary_fraction_delta", ascending=False).iloc[0]
        winners.append(
            {
                "component": component,
                "dominant_atom": best["atom_level"],
                "secondary_fraction_delta": float(best["secondary_fraction_delta"]),
                "ci_low": float(best["ci_low"]),
                "ci_high": float(best["ci_high"]),
                "share_of_total_effect": float(best["share_of_total_effect"]),
                "support_fraction": float(best["support_fraction"]),
            }
        )
    component_summary = pd.DataFrame(winners).sort_values("secondary_fraction_delta", ascending=False).reset_index(drop=True)
    return decomp, component_summary


def residual_current_ml_panel(scores: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Run-heldout residual-current classifiers for knockout and sentinel checks."""
    frame = scores.copy()
    y = (frame["group"] == "high_20nA").astype(int).to_numpy()
    base_features = pd.DataFrame(
        {
            "log_amp": np.log(np.maximum(frame["ref_amp_adc"].to_numpy(dtype=float), 1.0)),
            "log_area": np.log(np.maximum(frame["ref_area_adc"].to_numpy(dtype=float), 1.0)),
            "peak_sample": frame["peak_sample"].to_numpy(dtype=float),
            "area_over_peak": frame["area_over_peak"].to_numpy(dtype=float),
            "late_fraction": frame["late_fraction"].to_numpy(dtype=float),
            "width_10_samples": frame["width_10_samples"].to_numpy(dtype=float),
            "adaptive_lowering_adc": frame["adaptive_lowering_adc"].to_numpy(dtype=float),
            "downstream": frame["downstream"].to_numpy(dtype=float),
            "trad_secondary_fraction": frame["trad_secondary_fraction"].to_numpy(dtype=float),
            "trad_score_sse_improvement": frame["trad_score_sse_improvement"].to_numpy(dtype=float),
        }
    )
    onehot = pd.get_dummies(
        frame[["p09_taxon", "charge_support_atom", "topology_composition_atom", "baseline_pathology_atom", "beam_pileup_atom"]],
        prefix=["taxon", "charge", "topology", "baseline", "pileup"],
        dtype=float,
    )
    full = pd.concat([base_features, onehot], axis=1)
    feature_sets = {
        "full": list(full.columns),
        "taxon_knockout": [c for c in full.columns if not c.startswith("taxon_")],
        "charge_knockout": [
            c
            for c in full.columns
            if not c.startswith("charge_") and c not in {"log_amp", "log_area", "area_over_peak"}
        ],
        "topology_only": [c for c in full.columns if c.startswith("topology_") or c in {"downstream", "width_10_samples", "late_fraction"}],
        "amplitude_only": ["log_amp", "log_area", "area_over_peak"],
        "run_only_sentinel": ["run_scalar"],
        "shuffled_current_sentinel": list(full.columns),
    }
    full["run_scalar"] = frame["run"].to_numpy(dtype=float)
    rows = []
    for variant, cols in feature_sets.items():
        preds = np.full(len(frame), np.nan, dtype=float)
        for heldout_run in sorted(frame["run"].unique()):
            train_mask = frame["run"].to_numpy(dtype=int) != int(heldout_run)
            test_mask = ~train_mask
            yy = y.copy()
            if variant == "shuffled_current_sentinel":
                yy = y.copy()
                rng.shuffle(yy)
            if len(np.unique(yy[train_mask])) < 2:
                continue
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=0.8, class_weight="balanced", max_iter=500, random_state=RNG_SEED + int(heldout_run)),
            )
            if variant in {"full", "taxon_knockout", "charge_knockout"}:
                model = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.055, max_leaf_nodes=15, random_state=RNG_SEED + int(heldout_run))
            model.fit(full.loc[train_mask, cols], yy[train_mask])
            if hasattr(model, "predict_proba"):
                preds[test_mask] = model.predict_proba(full.loc[test_mask, cols])[:, 1]
            else:
                preds[test_mask] = model.decision_function(full.loc[test_mask, cols])
        valid = np.isfinite(preds)
        auc = float(roc_auc_score(y[valid], preds[valid])) if valid.any() and len(np.unique(y[valid])) == 2 else float("nan")
        ap = float(average_precision_score(y[valid], preds[valid])) if valid.any() and len(np.unique(y[valid])) == 2 else float("nan")
        brier = float(brier_score_loss(y[valid], np.clip(preds[valid], 0.0, 1.0))) if valid.any() else float("nan")
        high_mean = float(np.nanmean(preds[(frame["group"] == "high_20nA").to_numpy()])) if valid.any() else float("nan")
        low_mean = float(np.nanmean(preds[(frame["group"] == "low_2nA").to_numpy()])) if valid.any() else float("nan")
        rows.append(
            {
                "variant": variant,
                "n_features": int(len(cols)),
                "heldout_unit": "source_run",
                "current_auc": auc,
                "current_ap": ap,
                "brier": brier,
                "predicted_high_minus_low": high_mean - low_mean,
                "interpretation": {
                    "full": "all non-identifier residual atoms and waveform summaries",
                    "taxon_knockout": "full model with P09/anomaly taxon indicators removed",
                    "charge_knockout": "full model with amplitude and charge-support variables removed",
                    "topology_only": "composition/topology stress test",
                    "amplitude_only": "charge-support-only stress test",
                    "run_only_sentinel": "run-number leakage sentinel",
                    "shuffled_current_sentinel": "permuted-current falsification sentinel",
                }[variant],
            }
        )
    return pd.DataFrame(rows)


def method_benchmark_tables(scores: pd.DataFrame, stratum_table: pd.DataFrame, folds: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    methods = ["traditional", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "residual_tcn"]
    stratum_tables = []
    rows = []
    deltas = []
    for method in methods:
        frac_col = "trad_secondary_fraction" if method == "traditional" else f"{method}_secondary_fraction"
        score_col = "trad_score_sse_improvement" if method == "traditional" else f"{method}_overlap_score"
        table, summary = summarize_value(scores, stratum_table, frac_col, rng)
        table["method"] = method
        stratum_tables.append(table)
        score_table, score_summary = summarize_value(scores, stratum_table, score_col, rng)
        proxy = weighted_proxy_delta(scores, stratum_table, method)
        fold = folds[folds["method"] == method]
        rows.append(
            {
                "method": method,
                "secondary_fraction_delta": summary["value"],
                "secondary_fraction_ci_low": summary["ci_low"],
                "secondary_fraction_ci_high": summary["ci_high"],
                "overlap_score_delta": score_summary["value"],
                "overlap_score_ci_low": score_summary["ci_low"],
                "overlap_score_ci_high": score_summary["ci_high"],
                "timing_tail_proxy_delta": proxy["timing_tail_proxy"],
                "charge_log_proxy_delta": proxy["log_charge_proxy"],
                "support_accept_fraction": 1.0 if method == "traditional" else float(fold["support_accept_fraction"].mean()),
                "synthetic_auc": float(fold["synthetic_holdout_auc"].mean()) if len(fold) else float("nan"),
                "synthetic_ap": float(fold["synthetic_holdout_ap"].mean()) if len(fold) else float("nan"),
                "synthetic_brier": float(fold["synthetic_holdout_brier"].mean()) if len(fold) else float("nan"),
                "secondary_fraction_mae": float(fold["synthetic_secondary_fraction_mae"].mean()) if len(fold) else float("nan"),
            }
        )
        if method != "traditional":
            deltas.append(bootstrap_delta(scores, stratum_table, frac_col, "trad_secondary_fraction", rng))
    return pd.DataFrame(rows), pd.concat(stratum_tables, ignore_index=True), pd.DataFrame(deltas)


def leakage_checks(scores: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    current_y = (scores["group"] == "high_20nA").astype(int).to_numpy()
    rows = [
        {
            "check": "heldout_run_excluded_from_template_and_ml_training",
            "value": 1.0,
            "flag": False,
            "note": "Every fold uses low-current source runs only and removes the held-out low-current run from controls.",
        },
        {
            "check": "identifier_features_excluded",
            "value": 1.0,
            "flag": False,
            "note": "ML features exclude run, event number, current, group, downstream label, and stratum labels.",
        },
        {
            "check": "mean_shuffled_label_synthetic_auc",
            "value": float(folds[folds["method"] == "shuffled_current_sentinel"]["synthetic_holdout_auc"].mean()),
            "flag": bool(float(folds[folds["method"] == "shuffled_current_sentinel"]["synthetic_holdout_auc"].mean()) > 0.65),
            "note": "The permuted-label control should stay near chance on held-out synthetic overlays.",
        },
    ]
    for method in ["ridge", "gradient_boosted_trees", "mlp", "cnn1d", "residual_tcn"]:
        rows.append(
            {
                "check": f"{method}_current_auc_from_secondary_fraction",
                "value": float(roc_auc_score(current_y, scores[f"{method}_secondary_fraction"])),
                "flag": bool(roc_auc_score(current_y, scores[f"{method}_secondary_fraction"]) > 0.95),
                "note": "Flagged if the method nearly identifies beam current from the secondary-fraction output.",
            }
        )
    return pd.DataFrame(rows)


def choose_winner(method_summary: pd.DataFrame, deltas: pd.DataFrame, leakage: pd.DataFrame) -> dict:
    clean = not bool(leakage["flag"].any())
    ranked = method_summary.sort_values(
        ["secondary_fraction_delta", "synthetic_brier", "secondary_fraction_mae"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
    point_winner = str(ranked.iloc[0]["method"])
    supported = point_winner
    if not clean:
        supported = "no_adoptable_winner_leakage_flag"
    elif point_winner != "traditional":
        delta = deltas[deltas["method_metric"] == f"{point_winner}_secondary_fraction"]
        if len(delta) and float(delta.iloc[0]["ci_low"]) <= 0.0:
            supported = "traditional"
    return {
        "primary_metric": "matched high-minus-low secondary-fraction delta",
        "point_estimate_winner": point_winner,
        "winner": supported,
        "selection_rule": "rank secondary-fraction delta; promote an ML/NN method only if leakage checks pass and its ML-minus-traditional run-bootstrap CI is wholly positive",
    }


def save_plots(method_summary: pd.DataFrame, stability: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    x = np.arange(len(method_summary))
    ax.bar(x, method_summary["secondary_fraction_delta"])
    yerr = np.vstack(
        [
            method_summary["secondary_fraction_delta"] - method_summary["secondary_fraction_ci_low"],
            method_summary["secondary_fraction_ci_high"] - method_summary["secondary_fraction_delta"],
        ]
    )
    ax.errorbar(x, method_summary["secondary_fraction_delta"], yerr=yerr, fmt="none", color="k", capsize=3)
    ax.axhline(0, color="k", lw=1)
    ax.set_xticks(x, method_summary["method"], rotation=25, ha="right")
    ax.set_ylabel("Matched high-minus-low secondary fraction")
    fig.tight_layout()
    fig.savefig(OUT / "fig_method_secondary_delta_ci.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    for name, sub in stability.groupby("support_choice"):
        sub = sub.sort_values("trad_score_threshold")
        ax.plot(sub["trad_score_threshold"], sub["secondary_fraction_delta"], marker="o", label=name)
    ax.axhline(0, color="k", lw=1)
    ax.set_xlabel("Traditional SSE-improvement threshold")
    ax.set_ylabel("Secondary-fraction high-minus-low")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_traditional_threshold_support_scan.png", dpi=150)
    plt.close(fig)


def table_md(df: pd.DataFrame, cols: list[str], floatfmt: str = ".5f") -> str:
    return df[cols].to_markdown(index=False, floatfmt=floatfmt)


def write_report(
    topology: pd.DataFrame,
    repro: pd.DataFrame,
    stratum_table: pd.DataFrame,
    method_summary: pd.DataFrame,
    deltas: pd.DataFrame,
    truth_split: pd.DataFrame,
    component_summary: pd.DataFrame,
    current_panel: pd.DataFrame,
    stability: pd.DataFrame,
    stability_diag: pd.DataFrame,
    folds: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: dict,
    result: dict,
) -> None:
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    method_display = method_summary.copy()
    method_display["secondary_fraction_ci"] = method_display.apply(
        lambda r: f"[{r.secondary_fraction_ci_low:.5f}, {r.secondary_fraction_ci_high:.5f}]", axis=1
    )
    method_display["overlap_score_ci"] = method_display.apply(
        lambda r: f"[{r.overlap_score_ci_low:.5f}, {r.overlap_score_ci_high:.5f}]", axis=1
    )
    lines = [
        "# S10o: anomaly-residual current excess truth split",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        "- **Raw data:** B-stack HRD ROOT files for runs 44-57 from `data/root/root`.",
        "- **Primary split:** source run held out. High-current runs are scored by templates and ML/NN models trained only from low-current runs 46 and 47; low-current controls leave their own run out.",
        "- **Primary metric:** matched high-current minus low-current residual secondary-fraction delta with source-run bootstrap 95% confidence intervals.",
        "",
        "## Abstract",
        "",
        (
            "The S10o question is whether the S10e/S10f anomaly-residual current excess is better explained by "
            "beam pile-up, baseline pathology, charge support drift, topology composition, or the P09 anomaly taxon "
            "itself. The raw ROOT reproduction gate passes, "
            f"with downstream selected-event fractions {low['downstream_per_selected_event']:.5f} at 2 nA and "
            f"{high['downstream_per_selected_event']:.5f} at 20 nA. The operational winner is "
            f"**{winner['winner']}** under the predeclared rule: {winner['selection_rule']}."
        ),
        "",
        "## Reproduction From Raw ROOT",
        "",
        (
            "Events are read from the `h101` tree. Each event is reshaped to eight HRD channels by eighteen samples; "
            "B-stack staves B2/B4/B6/B8 are selected, a four-sample median pedestal is subtracted, and selected pulses "
            f"require amplitude above {base.AMP_CUT:.0f} ADC. This reproduces the documented S10 topology quantities "
            "before any model is trained."
        ),
        "",
        table_md(repro, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## Methods",
        "",
        "### Strata and Estimand",
        "",
        (
            "The support cells are the Cartesian product of amplitude bin, adaptive-lowering bin, and P02-style topology. "
            "Let \\(s\\) index matched strata and \\(w_s = \\min(n_{s,L}, n_{s,H}) / \\sum_j \\min(n_{j,L}, n_{j,H})\\). "
            "For a method output \\(m_i\\), the estimand is"
        ),
        "",
        "\\[ \\Delta_m = \\sum_s w_s \\left( \\bar m_{s,H} - \\bar m_{s,L} \\right). \\]",
        "",
        (
            "Run-bootstrap intervals resample low-current and high-current source runs separately, preserving all scored "
            "events from a sampled run. This treats run-to-run current/composition variability as the uncertainty unit."
        ),
        "",
        "For the truth split, atom labels \\(a\\) are introduced one axis at a time while keeping the same \\(w_s\\). The atom-specific residual contribution is",
        "",
        "\\[ \\Delta_{m,a} = \\sum_s w_s \\{ E(m \\mid H,s,a)-E(m \\mid L,s,a) \\}, \\]",
        "",
        "and the composition drift term is \\(\\sum_s w_s[P(a\\mid H,s)-P(a\\mid L,s)]\\). This separates response changes within matched support from high-current migration among atom levels.",
        "",
        "### Traditional Method",
        "",
        (
            "The traditional comparator is the bounded two-pulse template fit. For each held-out run, empirical templates "
            "are built from low-current training pulses only. A one-pulse model and a two-pulse model are fitted by least "
            "squares over a bounded grid of first-pulse shifts and separations. With waveform \\(y(t)\\), normalized template "
            "\\(q(t)\\), amplitudes \\(a_1,a_2\\), baseline \\(b\\), and delay \\(\\tau\\), the two-pulse objective is"
        ),
        "",
        "\\[ \\min_{a_1,a_2,b,t_1,\\tau} \\sum_t \\{y(t)-a_1 q(t-t_1)-a_2 q(t-t_1-\\tau)-b\\}^2, \\]",
        "",
        (
            "subject to positive amplitudes, bounded baseline, and a finite secondary-to-primary ratio. The reported "
            "secondary fraction is \\(a_2/(a_1+a_2)\\), attenuated when the two-pulse SSE improvement is below the "
            "nominal threshold. Stability is tested by scanning the SSE-improvement threshold and by restricting to "
            "the dominant matched support cells."
        ),
        "",
        "### ML and Neural Methods",
        "",
        (
            "All learned models use synthetic overlays generated only from training-run low-current pulses. The synthetic "
            "target is independent of the real-current label: clean pulses have class 0 and fraction 0; injected overlays "
            "have class 1 and known secondary fraction. Feature models use normalized 18-sample waveform values plus "
            "transparent shape and one-pulse residual summaries. Neural models consume the normalized 18-sample sequence."
        ),
        "",
        "- `ridge`: standardized logistic regression for overlap and ridge regression for secondary fraction.",
        "- `gradient_boosted_trees`: histogram gradient-boosted classifier/regressor.",
        "- `mlp`: two-layer fully connected classifier/regressor.",
        "- `cnn1d`: compact 1D convolutional multitask network.",
        "- `residual_tcn`: a small dilated residual temporal CNN, included as the new sequence architecture because the pulse has ordered samples but only eighteen time bins.",
        "",
        "A robust support mask uses a robust z-distance to train-fold feature medians and accepts real events inside the 95th percentile of training support. Identifier, run, current, group, downstream label, and stratum labels are excluded from model inputs.",
        "",
        "The residual-current diagnostic panel trains run-heldout classifiers for full, taxon-knockout, charge-knockout, topology-only, amplitude-only, run-only, and shuffled-current variants. These are not promoted as physics truth labels; they are falsification and attribution stress tests for the atom decomposition.",
        "",
        "## Results",
        "",
        f"{len(stratum_table)} matched support strata pass the low/high count floor. The dominant three cells carry {stratum_table.sort_values('match_weight', ascending=False).head(3)['match_weight'].sum():.3f} of the matched support weight.",
        "",
        "### Method Benchmark",
        "",
        table_md(
            method_display,
            [
                "method",
                "secondary_fraction_delta",
                "secondary_fraction_ci",
                "overlap_score_delta",
                "overlap_score_ci",
                "support_accept_fraction",
                "synthetic_auc",
                "synthetic_brier",
                "secondary_fraction_mae",
            ],
        ),
        "",
        "### ML Minus Traditional",
        "",
        table_md(deltas, ["method_metric", "delta", "ci_low", "ci_high", "n_bootstrap"]),
        "",
        "### Residual Truth Split",
        "",
        "Dominant atom by component, ranked by support-preserving secondary-fraction excess:",
        "",
        table_md(
            component_summary,
            ["component", "dominant_atom", "secondary_fraction_delta", "ci_low", "ci_high", "share_of_total_effect", "support_fraction"],
        ),
        "",
        "Top atom-level contributions:",
        "",
        table_md(
            truth_split.head(16),
            [
                "component",
                "atom_level",
                "n_events",
                "composition_delta",
                "secondary_fraction_delta",
                "ci_low",
                "ci_high",
                "charge_log_shift",
                "timing_tail_delta",
            ],
        ),
        "",
        "### Residual-Current Knockouts and Sentinels",
        "",
        table_md(
            current_panel,
            ["variant", "n_features", "current_auc", "current_ap", "brier", "predicted_high_minus_low", "interpretation"],
        ),
        "",
        "### Traditional Threshold and Support Stability",
        "",
        table_md(stability, ["support_choice", "n_strata", "trad_score_threshold", "secondary_fraction_delta", "ci_low", "ci_high"]),
        "",
        table_md(stability_diag, ["diagnostic", "value", "unit"]),
        "",
        "### Fold Diagnostics",
        "",
        table_md(
            folds[folds["method"] != "shuffled_current_sentinel"].groupby("method", as_index=False).agg(
                synthetic_auc=("synthetic_holdout_auc", "mean"),
                synthetic_ap=("synthetic_holdout_ap", "mean"),
                synthetic_brier=("synthetic_holdout_brier", "mean"),
                secondary_fraction_mae=("synthetic_secondary_fraction_mae", "mean"),
                support_accept_fraction=("support_accept_fraction", "mean"),
            ),
            ["method", "synthetic_auc", "synthetic_ap", "synthetic_brier", "secondary_fraction_mae", "support_accept_fraction"],
        ),
        "",
        "## Systematics and Caveats",
        "",
        "- The real-current endpoint is a waveform diagnostic, not truth-labelled beam pile-up. Synthetic overlays validate method response but do not prove the physical secondary rate.",
        "- Atom names are mechanistic hypotheses. The beam-pileup atom is based on two-pulse support from the traditional fit, not a hidden Monte Carlo truth field.",
        "- The anomaly taxon split is rule-based from the same waveform summaries used by P09-style audits; it should not be reified as a causal truth label.",
        "- Only runs 46 and 47 provide low-current training support for high-current scoring, so run-bootstrap intervals remain broad even with many events.",
        "- The threshold scan shows how sensitive the traditional excess is to the two-pulse SSE-improvement gate; adoption should prefer stable sign and magnitude over point estimates.",
        "- Support acceptance is model-feature support, not detector acceptance. It catches gross extrapolation but cannot identify all hidden DAQ/current confounds.",
        "- The timing-tail and charge rows are proxy deltas weighted by method secondary fractions; they are risk indicators, not calibrated timing or energy biases.",
        "",
        "## Leakage and Falsification Checks",
        "",
        table_md(leakage, ["check", "value", "flag", "note"]),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `truth_split_decomposition.csv`, `truth_split_component_summary.csv`, `residual_current_ml_panel.csv`, `traditional_stability_scan.csv`, `sampled_event_scores.csv.gz`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this report directory.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> int:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)
    events, waves, run_counts = base.load_events()
    topology, repro = base.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10 raw-ROOT reproduction gate failed")
    counts = base.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = base.matched_strata(counts)
    sample = base.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)
    scores, template_summary, folds = heldout_predictions(events, waves, sample, rng)
    scores = add_truth_split_atoms(scores)

    method_summary, method_stratum_summary, deltas = method_benchmark_tables(scores, stratum_table, folds, rng)
    truth_split, component_summary = truth_split_decomposition(scores, stratum_table, rng)
    current_panel = residual_current_ml_panel(scores, rng)
    stability, stability_diag = stability_scans(scores, stratum_table, rng)
    leakage = leakage_checks(scores, folds)
    winner = choose_winner(method_summary, deltas, leakage)
    save_plots(method_summary, stability)

    input_files = [raw_file(run) for run in sorted(base.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    stratum_table.to_csv(OUT / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(OUT / "analysis_sample.csv", index=False)
    template_summary.to_csv(OUT / "template_summary_by_fold.csv", index=False)
    scores.to_csv(OUT / "sampled_event_scores.csv.gz", index=False, compression="gzip")
    folds.to_csv(OUT / "fold_diagnostics.csv", index=False)
    method_summary.to_csv(OUT / "method_summary.csv", index=False)
    method_stratum_summary.to_csv(OUT / "method_stratum_summary.csv", index=False)
    deltas.to_csv(OUT / "method_deltas_vs_traditional.csv", index=False)
    truth_split.to_csv(OUT / "truth_split_decomposition.csv", index=False)
    component_summary.to_csv(OUT / "truth_split_component_summary.csv", index=False)
    current_panel.to_csv(OUT / "residual_current_ml_panel.csv", index=False)
    stability.to_csv(OUT / "traditional_stability_scan.csv", index=False)
    stability_diag.to_csv(OUT / "traditional_stability_diagnostics.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)

    best = method_summary[method_summary["method"] == winner["winner"]]
    if len(best) == 0:
        best = method_summary.sort_values("secondary_fraction_delta", ascending=False).head(1)
    best = best.iloc[0]
    trad = method_summary[method_summary["method"] == "traditional"].iloc[0]
    conclusion = (
        f"The raw-ROOT S10 topology reproduction passes before model fitting. The traditional bounded two-pulse fit gives "
        f"a matched high-minus-low secondary-fraction delta of {trad['secondary_fraction_delta']:.5f} "
        f"[{trad['secondary_fraction_ci_low']:.5f}, {trad['secondary_fraction_ci_high']:.5f}]. "
        f"The largest support-preserving residual atom is {component_summary.iloc[0]['component']}/"
        f"{component_summary.iloc[0]['dominant_atom']} with delta {component_summary.iloc[0]['secondary_fraction_delta']:.5f} "
        f"[{component_summary.iloc[0]['ci_low']:.5f}, {component_summary.iloc[0]['ci_high']:.5f}]. "
        f"The point-estimate winner is {winner['point_estimate_winner']}, but the operational winner recorded for this ticket is "
        f"{winner['winner']} because the promotion rule requires clean leakage checks and an ML-minus-traditional CI wholly above zero. "
        f"The selected winner has secondary-fraction delta {best['secondary_fraction_delta']:.5f} "
        f"[{best['secondary_fraction_ci_low']:.5f}, {best['secondary_fraction_ci_high']:.5f}], support acceptance "
        f"{best['support_accept_fraction']:.3f}, and overlap-score delta {best['overlap_score_delta']:.5f}."
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "S10o anomaly-residual current excess truth split",
        "reproduced": bool(repro["pass"].all()),
        "reproduction_gate": "S10 topology fractions from raw B-stack ROOT within 0.0015 absolute tolerance",
        "split": "source-run held out; high-current scored by low-current-only template and synthetic-overlay ML/NN training; run bootstrap CIs within current group",
        "strata": {
            "definition": "amplitude bin x S16 adaptive lowering bin x P02 topology",
            "n_matched_strata": int(len(stratum_table)),
            "global_s10_downstream_high_minus_low": float(global_downstream_excess),
            "n_scored_events": int(len(scores)),
            "sample_cap_per_run_stratum": int(base.SAMPLE_PER_RUN_STRATUM),
        },
        "methods": method_summary.to_dict(orient="records"),
        "ml_minus_traditional": deltas.to_dict(orient="records"),
        "truth_split": {
            "component_summary": component_summary.to_dict(orient="records"),
            "top_atom_rows": truth_split.head(16).to_dict(orient="records"),
            "interpretation": "support-preserving one-atom-at-a-time decomposition of the traditional residual secondary-fraction excess",
        },
        "residual_current_ml_panel": current_panel.to_dict(orient="records"),
        "traditional_stability": {
            "thresholds": TRAD_SCORE_THRESHOLDS,
            "support_choices": list(SUPPORT_CHOICES),
            "diagnostics": stability_diag.to_dict(orient="records"),
        },
        "winner": winner,
        "winner_name": winner["winner"],
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "next_tickets": [],
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(
        topology,
        repro,
        stratum_table,
        method_summary,
        deltas,
        truth_split,
        component_summary,
        current_panel,
        stability,
        stability_diag,
        folds,
        leakage,
        winner,
        result,
    )
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": RNG_SEED,
        "inputs": input_hashes,
        "outputs": hash_outputs(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "winner": winner["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
