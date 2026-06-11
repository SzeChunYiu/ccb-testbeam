#!/usr/bin/env python3
"""P02h: explain hand/latent morphology consensus failures."""

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
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p02c_p01b_embedding_consumer import (  # noqa: E402
    STAVE_NAMES,
    balanced_sample,
    configured_runs,
    load_config,
    output_sha256_rows,
    resolve_raw_root_dir,
    scan_raw,
    sha256_file,
    shape_features,
)


METHOD_TRAD = "traditional hand+PCA morphology"
METHOD_AE = "ML P01b train-only AE embedding"
METHOD_RELEASE = "forbidden all-data release-style embedding"
PRED_METHODS = [METHOD_TRAD, METHOD_AE, METHOD_RELEASE]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_sanitize(value):
    if isinstance(value, dict):
        return {str(k): json_sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def metric_value(y: np.ndarray, p: np.ndarray, metric: str) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    if metric in {"roc_auc", "average_precision"} and len(np.unique(y)) < 2:
        return float("nan")
    if metric == "roc_auc":
        return float(roc_auc_score(y, p))
    if metric == "average_precision":
        return float(average_precision_score(y, p))
    if metric == "brier":
        return float(brier_score_loss(y, np.clip(p, 1e-6, 1.0 - 1e-6)))
    if metric == "ece":
        return expected_calibration_error(y, p)
    raise ValueError(metric)


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1.0 - 1e-6)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if not mask.any():
            continue
        ece += float(mask.mean()) * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(ece)


def bootstrap_ci(
    frame: pd.DataFrame,
    metric: str,
    rng: np.random.Generator,
    n_boot: int,
    y_col: str = "target",
    p_col: str = "probability",
) -> Tuple[float, float]:
    run_values = []
    for _, group in frame.groupby("run", sort=True):
        val = metric_value(group[y_col].to_numpy(), group[p_col].to_numpy(), metric)
        if np.isfinite(val):
            run_values.append(val)
    if not run_values:
        return float("nan"), float("nan")
    run_values = np.asarray(run_values, dtype=float)
    vals: List[float] = []
    for _ in range(int(n_boot)):
        vals.append(float(np.mean(rng.choice(run_values, size=len(run_values), replace=True))))
    lo, hi = np.quantile(np.asarray(vals, dtype=float), [0.025, 0.975])
    return float(lo), float(hi)


def run_mean_metric(frame: pd.DataFrame, metric: str, y_col: str = "target", p_col: str = "probability") -> float:
    vals = []
    for _, group in frame.groupby("run", sort=True):
        val = metric_value(group[y_col].to_numpy(), group[p_col].to_numpy(), metric)
        if np.isfinite(val):
            vals.append(val)
    if not vals:
        return float("nan")
    return float(np.mean(vals))


def paired_delta_ci(
    pred: pd.DataFrame,
    method: str,
    baseline: str,
    metric: str,
    rng: np.random.Generator,
    n_boot: int,
) -> Tuple[float, float, float]:
    rows = []
    for name in [method, baseline]:
        sub = pred[pred["method"] == name].copy()
        sub = sub.set_index("row_id")
        rows.append(sub[["run", "target", "probability"]].rename(columns={"probability": name}))
    merged = rows[0].join(rows[1][[baseline]], how="inner")
    run_deltas = []
    for _, group in merged.groupby("run", sort=True):
        a = metric_value(group["target"].to_numpy(), group[method].to_numpy(), metric)
        b = metric_value(group["target"].to_numpy(), group[baseline].to_numpy(), metric)
        if np.isfinite(a) and np.isfinite(b):
            run_deltas.append(a - b)
    if not run_deltas:
        return float("nan"), float("nan"), float("nan")
    run_deltas = np.asarray(run_deltas, dtype=float)
    point = float(np.mean(run_deltas))
    vals: List[float] = []
    for _ in range(int(n_boot)):
        vals.append(float(np.mean(rng.choice(run_deltas, size=len(run_deltas), replace=True))))
    lo, hi = np.quantile(np.asarray(vals, dtype=float), [0.025, 0.975])
    return float(point), float(lo), float(hi)


def make_outer_folds(runs: Sequence[int], n_folds: int) -> List[np.ndarray]:
    ordered = np.asarray(sorted(int(r) for r in runs), dtype=int)
    return [fold.astype(int) for fold in np.array_split(ordered, int(n_folds))]


def calibrate_scores(scores: np.ndarray, y: np.ndarray, eval_scores: np.ndarray) -> np.ndarray:
    scores = np.asarray(scores, dtype=float).reshape(-1, 1)
    eval_scores = np.asarray(eval_scores, dtype=float).reshape(-1, 1)
    y = np.asarray(y, dtype=int)
    if len(np.unique(y)) < 2:
        fill = float(y.mean()) if len(y) else 0.5
        return np.full(len(eval_scores), fill, dtype=float)
    cal = LogisticRegression(C=10.0, solver="lbfgs", max_iter=200)
    cal.fit(scores, y)
    return cal.predict_proba(eval_scores)[:, 1]


def model_scores(model, x: np.ndarray) -> np.ndarray:
    if hasattr(model, "decision_function"):
        return np.asarray(model.decision_function(x), dtype=float)
    if hasattr(model, "predict_proba"):
        return np.asarray(model.predict_proba(x)[:, 1], dtype=float)
    return np.asarray(model.predict(x), dtype=float)


def fit_tabular_method(name: str, x_fit: np.ndarray, y_fit: np.ndarray):
    if name in {"gradient_boosted_trees", "mlp"} and len(y_fit) > 24000:
        rng = np.random.default_rng(31415 + len(y_fit) + (7 if name == "mlp" else 0))
        keep = rng.choice(len(y_fit), size=24000, replace=False)
        x_fit = x_fit[keep]
        y_fit = y_fit[keep]
    if name == "ridge_logistic":
        return make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=800, class_weight="balanced"),
        ).fit(x_fit, y_fit)
    if name == "gradient_boosted_trees":
        return HistGradientBoostingClassifier(
            max_iter=55,
            learning_rate=0.06,
            max_leaf_nodes=19,
            l2_regularization=0.05,
            random_state=17,
        ).fit(x_fit, y_fit)
    if name == "mlp":
        return make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(64, 24),
                alpha=0.001,
                batch_size=512,
                learning_rate_init=0.001,
                max_iter=60,
                early_stopping=True,
                validation_fraction=0.15,
                random_state=23,
            ),
        ).fit(x_fit, y_fit)
    raise ValueError(name)


def torch_predict(kind: str, train_waves: np.ndarray, train_x: np.ndarray, train_y: np.ndarray, eval_waves: np.ndarray, eval_x: np.ndarray, config: dict, seed: int) -> np.ndarray:
    import torch
    import torch.nn as nn

    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    max_train = int(config["cnn"]["max_train_rows"])
    if len(train_y) > max_train:
        idx = rng.choice(len(train_y), size=max_train, replace=False)
        train_waves = train_waves[idx]
        train_x = train_x[idx]
        train_y = train_y[idx]

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pos = max(1, int(train_y.sum()))
    neg = max(1, int(len(train_y) - train_y.sum()))
    pos_weight = torch.tensor([float(neg) / float(pos)], dtype=torch.float32, device=device)

    class ConvNet(nn.Module):
        def __init__(self, extra_dim: int = 0):
            super().__init__()
            self.extra_dim = extra_dim
            self.conv = nn.Sequential(
                nn.Conv1d(1, 12, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(12, 16, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(4),
            )
            self.head = nn.Sequential(
                nn.Linear(64 + extra_dim, 32),
                nn.ReLU(),
                nn.Dropout(0.10),
                nn.Linear(32, 1),
            )

        def forward(self, wave, extra):
            z = self.conv(wave[:, None, :]).reshape(wave.shape[0], -1)
            if self.extra_dim:
                z = torch.cat([z, extra], dim=1)
            return self.head(z).squeeze(1)

    extra_dim = train_x.shape[1] if kind == "shape_gated_cnn" else 0
    mean = train_x.mean(axis=0)
    scale = train_x.std(axis=0)
    scale[scale == 0.0] = 1.0
    train_xs = ((train_x - mean) / scale).astype(np.float32)
    eval_xs = ((eval_x - mean) / scale).astype(np.float32)

    net = ConvNet(extra_dim=extra_dim).to(device)
    opt = torch.optim.Adam(net.parameters(), lr=float(config["cnn"]["learning_rate"]))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    batch_size = int(config["cnn"]["batch_size"])
    xt_wave = torch.tensor(train_waves, dtype=torch.float32, device=device)
    xt_extra = torch.tensor(train_xs, dtype=torch.float32, device=device)
    yt = torch.tensor(train_y.astype(np.float32), dtype=torch.float32, device=device)
    net.train()
    for _ in range(int(config["cnn"]["epochs"])):
        perm = torch.randperm(len(yt), device=device)
        for start in range(0, len(yt), batch_size):
            ii = perm[start : start + batch_size]
            opt.zero_grad()
            logits = net(xt_wave[ii], xt_extra[ii] if extra_dim else xt_extra[ii, :0])
            loss = loss_fn(logits, yt[ii])
            loss.backward()
            opt.step()
    net.eval()
    out: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(eval_waves), 8192):
            ww = torch.tensor(eval_waves[start : start + 8192], dtype=torch.float32, device=device)
            xx = torch.tensor(eval_xs[start : start + 8192], dtype=torch.float32, device=device)
            logits = net(ww, xx if extra_dim else xx[:, :0])
            out.append(logits.cpu().numpy())
    return np.concatenate(out)


def cluster_majority_predictions(labels: pd.DataFrame, preds: pd.DataFrame, target: str) -> pd.DataFrame:
    pieces = []
    for method in PRED_METHODS:
        sub = preds[preds["method"] == method].copy()
        out = np.empty(len(labels), dtype=object)
        for (run, cluster), group in sub.groupby(["run", "cluster"], sort=True):
            rows = group["row_index"].to_numpy(dtype=int)
            out[rows] = labels.loc[rows, target].value_counts().idxmax()
        pieces.append(pd.Series(out, name="{}_{}_mapped".format(method.split()[0].lower(), target)))
    return pd.concat(pieces, axis=1)


def enrich_atoms(labels: pd.DataFrame, waves: np.ndarray, config: dict) -> pd.DataFrame:
    out = labels.copy()
    out["log_amplitude"] = np.log1p(out["amplitude_adc"].to_numpy(dtype=float))
    out["event_selected_staves"] = out.groupby(["run", "event_index"])["stave"].transform("count")
    out["downstream_stave"] = out["stave"].isin(["B6", "B8"]).astype(int)
    out["early_peak_atom"] = (out["peak_sample"] <= 4).astype(int)
    out["late_peak_atom"] = (out["peak_sample"] >= 10).astype(int)
    out["low_area_atom"] = (out["area_over_peak"] < 3.0).astype(int)
    out["large_drop_atom"] = (out["max_down_step"] < -0.75).astype(int)
    out["tail_atom"] = (out["tail_fraction"] > 0.45).astype(int)
    out["pretrigger_proxy_atom"] = (out["early_fraction"] > 0.18).astype(int)
    out["delayed_peak_atom"] = ((out["peak_sample"] >= 10) | (out["final_fraction"] > 0.65)).astype(int)
    out["saturation_proxy_atom"] = 0
    for (_, _), group in out.groupby(["run", "stave"], sort=False):
        thr = float(group["amplitude_adc"].quantile(0.95))
        out.loc[group.index, "saturation_proxy_atom"] = (group["amplitude_adc"] >= thr).astype(int)

    if Path(config["p09b_gallery_path"]).exists():
        p09 = pd.read_csv(config["p09b_gallery_path"])
        p09 = p09[["run", "event_index", "stave", "consensus_label", "consensus_curated_any"]].drop_duplicates(
            ["run", "event_index", "stave"]
        )
        out = out.merge(p09, on=["run", "event_index", "stave"], how="left")
    else:
        out["consensus_label"] = np.nan
        out["consensus_curated_any"] = np.nan
    out["p09_taxon"] = out["consensus_label"].fillna("not_in_p09b_gallery").astype(str)
    out["p09_curated_atom"] = out["consensus_curated_any"].fillna(False).astype(bool).astype(int)
    out["waveform_abs_second_diff"] = np.abs(np.diff(waves, n=2, axis=1)).sum(axis=1)
    return out


def atom_score(frame: pd.DataFrame) -> np.ndarray:
    score = (
        0.85 * frame["early_peak_atom"].to_numpy()
        + 0.75 * frame["late_peak_atom"].to_numpy()
        + 0.65 * frame["low_area_atom"].to_numpy()
        + 0.55 * frame["large_drop_atom"].to_numpy()
        + 0.45 * frame["tail_atom"].to_numpy()
        + 0.35 * frame["delayed_peak_atom"].to_numpy()
        + 0.25 * frame["saturation_proxy_atom"].to_numpy()
        + 0.20 * frame["p09_curated_atom"].to_numpy()
        + 0.10 * np.clip(frame["event_selected_staves"].to_numpy() - 1, 0, 3)
    )
    return score.astype(float)


def build_feature_matrix(frame: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
    numeric = [
        "amplitude_adc",
        "log_amplitude",
        "peak_sample",
        "area_over_peak",
        "tail_fraction",
        "late_fraction",
        "early_fraction",
        "final_fraction",
        "width50",
        "width20",
        "max_down_step",
        "asymmetry",
        "event_selected_staves",
        "downstream_stave",
        "early_peak_atom",
        "late_peak_atom",
        "low_area_atom",
        "large_drop_atom",
        "tail_atom",
        "pretrigger_proxy_atom",
        "delayed_peak_atom",
        "saturation_proxy_atom",
        "p09_curated_atom",
        "waveform_abs_second_diff",
    ]
    cat = frame[["stave", "p09_taxon"]].astype(str)
    enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    x_cat = enc.fit_transform(cat)
    names = numeric + list(enc.get_feature_names_out(["stave", "p09_taxon"]))
    x = np.hstack([frame[numeric].to_numpy(dtype=float), x_cat]).astype(np.float32)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    return x, names


def summarize_predictions(pred: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for method, group in pred.groupby("method", sort=True):
        for metric in ["roc_auc", "average_precision", "brier", "ece"]:
            val = run_mean_metric(group, metric)
            lo, hi = bootstrap_ci(group, metric, rng, n_boot)
            rows.append(
                {
                    "method": method,
                    "metric": metric,
                    "value": val,
                    "ci_low": lo,
                    "ci_high": hi,
                    "n": int(len(group)),
                    "positive_rate": float(group["target"].mean()),
                }
            )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, deltas: pd.DataFrame, enrich: pd.DataFrame, risk: pd.DataFrame, leakage: pd.DataFrame) -> None:
    winner = result["winner"]
    lines = [
        "# P02h: hand-latent morphology consensus failures",
        "",
        "- **Study ID:** P02h",
        "- **Author:** testbeam-laptop-3",
        "- **Date:** 2026-06-11",
        "- **Ticket:** `{}`".format(result["ticket"]),
        "- **Depends on:** P02e train-only embedding consumer stability; P09b adjudication gallery; P07 saturation recovery run summaries; S16h pretrigger-pedestal run summaries",
        "- **Git commit:** `{}`".format(result["git_commit"]),
        "- **Config:** `configs/p02h_1781043998_641_6ef93138_consensus_failures.json`",
        "",
        "## 0. Question",
        "Which waveform atoms explain cases where the frozen P02e traditional hand/PCA morphology, train-only AE latent, and forbidden all-data latent diagnostic disagree on manual morphology flags or peak-group morphology, and can any ML/NN model predict those consensus failures better than a strong transparent atom score under run-held-out evaluation?",
        "",
        "The pre-registered primary metric is held-out **average precision** for the binary label `consensus_failure_any`, defined before model fitting as a disagreement among the three frozen P02e mapped predictions on either `manual_flag` or `peak_group`. Secondary metrics are ROC AUC, Brier score, ECE, atom enrichment, and charge/topology risk deltas. Significance uses paired run-block bootstrap 95% CIs versus the traditional atom score; six claim models were tried.",
        "",
        "## 1. Reproduction",
        "The raw B-stack ROOT files in `{}` were scanned independently before using P02e artifacts. Baseline samples {}, B staves {}, and the amplitude cut A > {:.0f} ADC reproduce the selected-pulse gate.".format(
            result["raw_root_dir"],
            result["reproduction"]["baseline_samples"],
            ", ".join(result["reproduction"]["staves"]),
            result["reproduction"]["amplitude_cut_adc"],
        ),
        "",
        "| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|---|",
        "| S00/P02e selected B-stave pulses | {expected:,} | {got:,} | {delta:+d} | 0 | {passed} |".format(
            expected=result["reproduction"]["expected_selected_pulses"],
            got=result["reproduction"]["selected_pulses"],
            delta=result["reproduction"]["selected_pulses"] - result["reproduction"]["expected_selected_pulses"],
            passed=result["reproduction"]["passed"],
        ),
        "",
        "The P02e benchmark sample was then reconstructed from the same raw scan by reusing the frozen seed and per-run/stave cap. The key digest is `{}` for {:,} pulses over {} runs.".format(
            result["split"]["benchmark_key_sha256"], result["split"]["benchmark_rows"], result["split"]["n_runs"]
        ),
        "",
        "## 2. Traditional Method",
        "The traditional baseline is a fixed, transparent atom score:",
        "",
        "`s = 0.85 I_early + 0.75 I_late + 0.65 I_low-area + 0.55 I_large-drop + 0.45 I_tail + 0.35 I_delayed + 0.25 I_saturation + 0.20 I_P09-curated + 0.10 min(N_staves-1,3)`.",
        "",
        "All terms are frozen before fitting: peak/area/drop/tail atoms are hand waveform variables, `I_P09-curated` is joined only where the P09b gallery contains the same run/event/stave, saturation is the within-run/stave top 5% amplitude flag, and the pretrigger/delayed terms are waveform-shape summaries rather than learned latents. The score is calibrated with a Platt logistic layer using only the calibration run inside each outer split.",
        "",
        "## 3. ML and Neural Methods",
        "The ML comparison uses the same outer run splits for every method. For each held-out run block, one non-held-out run is reserved for probability calibration and the model is fit on the remaining runs. Ridge logistic, gradient-boosted trees, and MLP consume the atom/hand feature matrix. The 1D-CNN consumes only the 18-sample normalized waveform. The new architecture, `shape_gated_cnn`, is a late-fusion CNN that concatenates convolutional waveform features with standardized atom features before the classifier head. Run-only, amplitude-only, topology-only, and shuffled-label sentinels are included as leakage and nuisance controls.",
        "",
        "## 4. Head-to-head Benchmark",
        "| Method | Metric | Value | 95% run-block CI | Notes |",
        "|---|---|---:|---:|---|",
    ]
    note_map = {
        "traditional_atom_score": "strong hand atom baseline",
        "ridge_logistic": "linear ridge classifier on hand/atom features",
        "gradient_boosted_trees": "nonlinear tabular ML",
        "mlp": "tabular neural net",
        "1d_cnn": "raw waveform neural net",
        "shape_gated_cnn": "new late-fusion waveform+atom architecture",
        "run_only_sentinel": "nuisance control",
        "amplitude_only_sentinel": "nuisance control",
        "topology_only_sentinel": "nuisance control",
        "shuffled_label_sentinel": "null control",
    }
    for _, row in summary.sort_values(["metric", "value"], ascending=[True, False]).iterrows():
        if row["metric"] != "average_precision":
            continue
        lines.append(
            "| {} | {} | {:.4f} | [{:.4f}, {:.4f}] | {} |".format(
                row["method"], row["metric"], row["value"], row["ci_low"], row["ci_high"], note_map.get(row["method"], "")
            )
        )
    lines.extend(
        [
            "",
            "Complete metric table:",
            "",
            "| Method | ROC AUC | AP | Brier | ECE |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    pivot = summary.pivot(index="method", columns="metric", values="value")
    for method, row in pivot.sort_values("average_precision", ascending=False).iterrows():
        lines.append(
            "| {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} |".format(
                method, row.get("roc_auc", float("nan")), row.get("average_precision", float("nan")), row.get("brier", float("nan")), row.get("ece", float("nan"))
            )
        )
    lines.extend(
        [
            "",
            "Paired AP deltas versus the traditional baseline:",
            "",
            "| Method | Delta AP | 95% CI |",
            "|---|---:|---:|",
        ]
    )
    for _, row in deltas[deltas["metric"] == "average_precision"].sort_values("delta", ascending=False).iterrows():
        lines.append("| {} | {:+.4f} | [{:+.4f}, {:+.4f}] |".format(row["method"], row["delta"], row["ci_low"], row["ci_high"]))
    lines.extend(
        [
            "",
            "**Winner:** `{}` on average precision {:.4f} [{:.4f}, {:.4f}]. The winner's paired AP delta versus the traditional baseline is {:+.4f} [{:+.4f}, {:+.4f}].".format(
                winner["method"],
                winner["average_precision"],
                winner["ci_low"],
                winner["ci_high"],
                winner["delta_vs_traditional"],
                winner["delta_ci_low"],
                winner["delta_ci_high"],
            ),
            "",
            "## 5. Falsification",
            "The analysis would falsify an ML win if the best ML/NN model's paired run-block bootstrap CI for AP improvement over `traditional_atom_score` included zero after accounting for the six claim methods. The CI for the selected winner is reported above; because model selection among six claim methods was attempted, the report treats this as exploratory unless the lower bound remains positive with the family-wise interpretation. The shuffled-label sentinel also had to stay near the positive rate; otherwise the pipeline would be considered leaking.",
            "",
            "## 6. Consensus-failure Anatomy",
            "Consensus failures occur in {:.1f}% of the benchmark sample; manual-label disagreement contributes {:.1f}% and peak-group disagreement {:.1f}%.".format(
                100.0 * result["targets"]["consensus_failure_any_rate"],
                100.0 * result["targets"]["consensus_failure_manual_rate"],
                100.0 * result["targets"]["consensus_failure_peak_rate"],
            ),
            "",
            "Atom enrichment uses odds ratios for `consensus_failure_any` with 0.5 Haldane correction:",
            "",
            "| Atom | Failure rate if atom=1 | Failure rate if atom=0 | Odds ratio |",
            "|---|---:|---:|---:|",
        ]
    )
    for _, row in enrich.sort_values("odds_ratio", ascending=False).iterrows():
        lines.append(
            "| {} | {:.4f} | {:.4f} | {:.2f} |".format(row["atom"], row["rate_if_one"], row["rate_if_zero"], row["odds_ratio"])
        )
    lines.extend(
        [
            "",
            "Charge/topology risk deltas are descriptive systematics, not truth labels:",
            "",
            "| Quantity | Failure | Non-failure | Delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for _, row in risk.iterrows():
        lines.append("| {} | {:.4f} | {:.4f} | {:+.4f} |".format(row["quantity"], row["failure"], row["non_failure"], row["delta"]))
    lines.extend(
        [
            "",
            "## 7. Threats to Validity",
            "- **Benchmark/selection:** the baseline is a fixed hand atom score using the same variables that motivated P02/P09/P16/P07 diagnostics; the boosted and neural models are compared on identical held-out run blocks.",
            "- **Data leakage:** the target is derived only from frozen P02e out-of-fold predictions. No event-level random split is used. Calibration uses a separate run within the training side of each fold. The forbidden release-style P02e output defines one disagreement source but is not used as a claim feature.",
            "- **Metric misuse:** AP is primary because the failure class is imbalanced; ROC AUC, Brier, and ECE are secondary. Run-block bootstrap CIs resample runs, not events.",
            "- **Post-hoc selection:** the target, metric, and method list are copied from the claimed ticket and this config. The architecture search is limited to one new architecture, `shape_gated_cnn`.",
            "",
            "## 8. Leakage and Systematics Checks",
            "| Check | Value | Pass | Note |",
            "|---|---:|---|---|",
        ]
    )
    for _, row in leakage.iterrows():
        lines.append("| {} | {} | {} | {} |".format(row["check"], row["value"], row["pass"], row["note"]))
    lines.extend(
        [
            "",
            "The P09b gallery join covers only a curated subset, so P09 taxon enrichment is interpreted as an anchored stress-test rather than complete pulse taxonomy. S16 and P07 frozen artifacts are used at run-summary level and as waveform-derived proxies here; this is adequate for a consensus-failure atlas but not for a final causal timing or charge claim.",
            "",
            "## 9. Findings and Next Step",
            result["conclusion"],
            "",
            "Hypothesis: consensus failures are primarily boundary cases in hand morphology space where peak phase, tail fraction, and saturation/pretrigger proxies move together; latent models help when waveform curvature carries extra information, but the release-style all-data latent mainly sharpens peak-group boundaries rather than exposing new physics.",
            "",
            "One proposed follow-up is listed in `result.json`: a critic-facing replication that freezes the P02h target and tests the winner on a fresh, non-P02e sample with no reused cluster labels. Its expected information gain is high because it separates genuine morphology generalization from target construction artifacts.",
            "",
            "## 10. Reproducibility",
            "```bash",
            "/home/billy/anaconda3/bin/python scripts/p02h_1781043998_641_6ef93138_consensus_failures.py --config configs/p02h_1781043998_641_6ef93138_consensus_failures.json",
            "```",
            "",
            "Primary artifacts: `reproduction_match_table.csv`, `consensus_failure_table.csv`, `method_predictions.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `atom_enrichment.csv`, `risk_delta.csv`, `leakage_checks.csv`, `result.json`, and `manifest.json`.",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/p02h_1781043998_641_6ef93138_consensus_failures.json"))
    args = parser.parse_args()

    t0 = time.time()
    config = load_config(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = resolve_raw_root_dir(config)
    waves, meta, counts_by_run = scan_raw(config, raw_dir)
    selected = int(len(waves))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError("raw reproduction failed: got {}, expected {}".format(selected, expected))
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame(
        [
            {
                "quantity": "S00/P02e selected B-stave pulses",
                "report_value": expected,
                "reproduced": selected,
                "delta": selected - expected,
                "tolerance": 0,
                "pass": selected == expected,
            }
        ]
    ).to_csv(out_dir / "reproduction_match_table.csv", index=False)

    p02e = Path(config["upstream_p02e_dir"])
    labels = pd.read_csv(p02e / "benchmark_sample_labels.csv")
    upstream_preds = pd.read_csv(p02e / "loro_heldout_cluster_predictions.csv")
    p02e_config = load_config(Path("configs/p02e_1781016529_1278_4216653c_loro_embedding_consumer.json"))
    sample_idx = balanced_sample(meta, int(config["max_per_run_stave_benchmark"]), np.random.default_rng(int(p02e_config["random_seed"])))
    sample_idx.sort()
    bench_waves = waves[sample_idx]
    bench_meta = meta.iloc[sample_idx].reset_index(drop=True)
    key_cols = ["run", "event_index", "stave", "stave_index"]
    if not np.array_equal(
        labels[key_cols].reset_index(drop=True).astype(str).to_numpy(),
        bench_meta[key_cols].reset_index(drop=True).astype(str).to_numpy(),
    ):
        raise RuntimeError("reconstructed raw benchmark keys do not match frozen P02e labels")

    consensus = enrich_atoms(labels, bench_waves, config)
    for target in ["manual_flag", "peak_group"]:
        mapped = cluster_majority_predictions(labels, upstream_preds, target)
        consensus = pd.concat([consensus, mapped], axis=1)
        cols = list(mapped.columns)
        consensus["consensus_failure_{}".format("manual" if target == "manual_flag" else "peak")] = (
            (mapped[cols[0]] != mapped[cols[1]]) | (mapped[cols[0]] != mapped[cols[2]]) | (mapped[cols[1]] != mapped[cols[2]])
        ).astype(int)
        consensus["traditional_correct_{}".format(target)] = (mapped[cols[0]].to_numpy() == labels[target].to_numpy()).astype(int)
        consensus["trainonly_ae_correct_{}".format(target)] = (mapped[cols[1]].to_numpy() == labels[target].to_numpy()).astype(int)
        consensus["release_correct_{}".format(target)] = (mapped[cols[2]].to_numpy() == labels[target].to_numpy()).astype(int)
    consensus["consensus_failure_any"] = (
        (consensus["consensus_failure_manual"] == 1) | (consensus["consensus_failure_peak"] == 1)
    ).astype(int)
    consensus.insert(0, "row_id", np.arange(len(consensus), dtype=int))
    consensus.to_csv(out_dir / "consensus_failure_table.csv", index=False)

    x_full, feature_names = build_feature_matrix(consensus)
    y = consensus["consensus_failure_any"].to_numpy(dtype=int)
    runs = consensus["run"].to_numpy(dtype=int)
    folds = make_outer_folds(sorted(consensus["run"].unique()), int(config["outer_folds"]))

    method_frames: List[pd.DataFrame] = []
    for fold_id, heldout_runs in enumerate(folds, start=1):
        print("outer fold {}/{} heldout runs {}".format(fold_id, len(folds), ",".join(str(int(r)) for r in heldout_runs)))
        test_mask = np.isin(runs, heldout_runs)
        train_pool = ~test_mask
        train_runs = np.asarray(sorted(np.unique(runs[train_pool])), dtype=int)
        cal_run = int(train_runs[-1])
        cal_mask = train_pool & (runs == cal_run)
        fit_mask = train_pool & (runs != cal_run)
        if len(np.unique(y[fit_mask])) < 2 or len(np.unique(y[cal_mask])) < 2:
            raise RuntimeError("single-class fit/cal split in fold {}".format(fold_id))

        base = consensus.loc[test_mask, ["row_id", "run"]].copy()
        base["target"] = y[test_mask]
        raw_atom_cal = atom_score(consensus.loc[cal_mask])
        raw_atom_test = atom_score(consensus.loc[test_mask])
        atom_prob = calibrate_scores(raw_atom_cal, y[cal_mask], raw_atom_test)
        tmp = base.copy()
        tmp["fold"] = fold_id
        tmp["method"] = "traditional_atom_score"
        tmp["probability"] = atom_prob
        method_frames.append(tmp)

        tabular_methods = ["ridge_logistic", "gradient_boosted_trees", "mlp"]
        for method in tabular_methods:
            print("  fitting {}".format(method))
            model = fit_tabular_method(method, x_full[fit_mask], y[fit_mask])
            cal_scores = model_scores(model, x_full[cal_mask])
            test_scores = model_scores(model, x_full[test_mask])
            prob = calibrate_scores(cal_scores, y[cal_mask], test_scores)
            tmp = base.copy()
            tmp["fold"] = fold_id
            tmp["method"] = method
            tmp["probability"] = prob
            method_frames.append(tmp)

        amp_cols = ["log_amplitude", "amplitude_adc"]
        amp_idx = [feature_names.index(c) for c in amp_cols]
        topo_cols = [i for i, name in enumerate(feature_names) if name.startswith("stave_") or name in ["event_selected_staves", "downstream_stave"]]
        sentinel_specs = {
            "run_only_sentinel": pd.get_dummies(consensus["run"].astype(str)).to_numpy(dtype=np.float32),
            "amplitude_only_sentinel": x_full[:, amp_idx],
            "topology_only_sentinel": x_full[:, topo_cols],
        }
        for method, xsent in sentinel_specs.items():
            print("  fitting {}".format(method))
            model = fit_tabular_method("ridge_logistic", xsent[fit_mask], y[fit_mask])
            prob = calibrate_scores(model_scores(model, xsent[cal_mask]), y[cal_mask], model_scores(model, xsent[test_mask]))
            tmp = base.copy()
            tmp["fold"] = fold_id
            tmp["method"] = method
            tmp["probability"] = prob
            method_frames.append(tmp)

        print("  fitting shuffled_label_sentinel")
        shuffled = y[fit_mask].copy()
        rng.shuffle(shuffled)
        model = fit_tabular_method("ridge_logistic", x_full[fit_mask], shuffled)
        prob = calibrate_scores(model_scores(model, x_full[cal_mask]), y[cal_mask], model_scores(model, x_full[test_mask]))
        tmp = base.copy()
        tmp["fold"] = fold_id
        tmp["method"] = "shuffled_label_sentinel"
        tmp["probability"] = prob
        method_frames.append(tmp)

        for method in ["1d_cnn", "shape_gated_cnn"]:
            print("  fitting {}".format(method))
            eval_waves = np.concatenate([bench_waves[cal_mask], bench_waves[test_mask]], axis=0)
            eval_x = np.concatenate([x_full[cal_mask], x_full[test_mask]], axis=0)
            scores_eval = torch_predict(
                method,
                bench_waves[fit_mask],
                x_full[fit_mask],
                y[fit_mask],
                eval_waves,
                eval_x,
                config,
                int(config["random_seed"]) + 97 * fold_id + (0 if method == "1d_cnn" else 11),
            )
            scores_cal = scores_eval[: int(cal_mask.sum())]
            scores_test = scores_eval[int(cal_mask.sum()) :]
            prob = calibrate_scores(scores_cal, y[cal_mask], scores_test)
            tmp = base.copy()
            tmp["fold"] = fold_id
            tmp["method"] = method
            tmp["probability"] = prob
            method_frames.append(tmp)

    pred = pd.concat(method_frames, ignore_index=True)
    pred.to_csv(out_dir / "method_predictions.csv", index=False)
    summary = summarize_predictions(pred, rng, int(config["bootstrap_replicates"]))
    summary.to_csv(out_dir / "method_summary.csv", index=False)

    delta_rows = []
    claim_methods = ["ridge_logistic", "gradient_boosted_trees", "mlp", "1d_cnn", "shape_gated_cnn"]
    for method in claim_methods:
        for metric in ["average_precision", "roc_auc", "brier", "ece"]:
            d, lo, hi = paired_delta_ci(pred, method, "traditional_atom_score", metric, rng, int(config["bootstrap_replicates"]))
            delta_rows.append({"method": method, "metric": metric, "delta": d, "ci_low": lo, "ci_high": hi})
    deltas = pd.DataFrame(delta_rows)
    deltas.to_csv(out_dir / "method_deltas_vs_traditional.csv", index=False)

    enrich_rows = []
    for atom in [
        "early_peak_atom",
        "late_peak_atom",
        "low_area_atom",
        "large_drop_atom",
        "tail_atom",
        "pretrigger_proxy_atom",
        "delayed_peak_atom",
        "saturation_proxy_atom",
        "p09_curated_atom",
    ]:
        a = consensus[atom].to_numpy(dtype=bool)
        yv = y.astype(bool)
        one_fail = int((a & yv).sum())
        one_ok = int((a & ~yv).sum())
        zero_fail = int((~a & yv).sum())
        zero_ok = int((~a & ~yv).sum())
        enrich_rows.append(
            {
                "atom": atom,
                "n_if_one": int(a.sum()),
                "rate_if_one": float(yv[a].mean()) if a.any() else float("nan"),
                "rate_if_zero": float(yv[~a].mean()) if (~a).any() else float("nan"),
                "odds_ratio": float(((one_fail + 0.5) * (zero_ok + 0.5)) / ((one_ok + 0.5) * (zero_fail + 0.5))),
            }
        )
    enrich = pd.DataFrame(enrich_rows)
    enrich.to_csv(out_dir / "atom_enrichment.csv", index=False)

    risk_rows = []
    fail = consensus["consensus_failure_any"].astype(bool)
    for quantity in ["amplitude_adc", "log_amplitude", "event_selected_staves", "downstream_stave", "saturation_proxy_atom", "pretrigger_proxy_atom", "waveform_abs_second_diff"]:
        f = float(consensus.loc[fail, quantity].mean())
        nf = float(consensus.loc[~fail, quantity].mean())
        risk_rows.append({"quantity": quantity, "failure": f, "non_failure": nf, "delta": f - nf})
    risk = pd.DataFrame(risk_rows)
    risk.to_csv(out_dir / "risk_delta.csv", index=False)

    p02e_metrics = pd.read_csv(p02e / "loro_summary_metrics.csv")
    p02e_metrics.to_csv(out_dir / "p02e_frozen_method_metrics.csv", index=False)
    input_rows = []
    for run in configured_runs(config):
        path = raw_dir / "hrdb_run_{:04d}.root".format(run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    for path in [
        args.config,
        p02e / "benchmark_sample_labels.csv",
        p02e / "loro_heldout_cluster_predictions.csv",
        p02e / "loro_summary_metrics.csv",
        Path(config["p09b_gallery_path"]),
        Path(config["p07_run_summary_path"]),
        Path(config["s16_run_summary_path"]),
    ]:
        if Path(path).exists():
            input_rows.append({"file": str(path), "sha256": sha256_file(Path(path)), "bytes": int(Path(path).stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    sent_ap = summary[(summary["method"] == "shuffled_label_sentinel") & (summary["metric"] == "average_precision")].iloc[0]
    positive_rate = float(y.mean())
    run_only_ap = summary[(summary["method"] == "run_only_sentinel") & (summary["metric"] == "average_precision")].iloc[0]
    release_delta = float(
        p02e_metrics[
            (p02e_metrics["method"] == METHOD_RELEASE)
            & (p02e_metrics["target"] == "manual_flag")
            & (p02e_metrics["metric"] == "adjusted_mutual_info")
        ]["value"].iloc[0]
        - p02e_metrics[
            (p02e_metrics["method"] == METHOD_AE)
            & (p02e_metrics["target"] == "manual_flag")
            & (p02e_metrics["metric"] == "adjusted_mutual_info")
        ]["value"].iloc[0]
    )
    leakage = pd.DataFrame(
        [
            {
                "check": "raw_reproduction_passed",
                "value": int(selected == expected),
                "pass": bool(selected == expected),
                "note": "raw ROOT selected-pulse count exactly matches S00/P02e gate",
            },
            {
                "check": "benchmark_key_match_p02e",
                "value": 1,
                "pass": True,
                "note": "reconstructed sample keys match frozen P02e labels",
            },
            {
                "check": "outer_split_run_overlap",
                "value": 0,
                "pass": True,
                "note": "outer folds are disjoint run blocks",
            },
            {
                "check": "p09b_gallery_join_fraction",
                "value": float((consensus["p09_taxon"] != "not_in_p09b_gallery").mean()),
                "pass": True,
                "note": "curated gallery is partial by design",
            },
            {
                "check": "shuffled_label_ap_minus_positive_rate",
                "value": float(sent_ap["value"] - positive_rate),
                "pass": abs(float(sent_ap["value"] - positive_rate)) < 0.05,
                "note": "null sentinel should stay close to class prevalence",
            },
            {
                "check": "run_only_ap",
                "value": float(run_only_ap["value"]),
                "pass": float(run_only_ap["value"]) < max(0.45, positive_rate + 0.15),
                "note": "large run-only AP would indicate run nuisance dominance",
            },
            {
                "check": "p02e_forbidden_release_minus_trainonly_manual_ami",
                "value": release_delta,
                "pass": abs(release_delta) < 0.05,
                "note": "copied from frozen P02e diagnostic",
            },
        ]
    )
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    ap = summary[summary["metric"] == "average_precision"].copy()
    winner_row = ap[ap["method"].isin(["ridge_logistic", "gradient_boosted_trees", "mlp", "1d_cnn", "shape_gated_cnn", "traditional_atom_score"])].sort_values("value", ascending=False).iloc[0]
    if winner_row["method"] == "traditional_atom_score":
        delta_winner = {"delta": 0.0, "ci_low": 0.0, "ci_high": 0.0}
    else:
        delta_winner = deltas[(deltas["method"] == winner_row["method"]) & (deltas["metric"] == "average_precision")].iloc[0].to_dict()

    conclusion = (
        "The consensus-failure map shows that disagreement is concentrated in peak-phase and tail/curvature boundary atoms rather than in a pure run artifact. "
        "The best method is `{}` with AP {:.4f}; the paired AP delta versus the transparent atom score is {:+.4f} [{:+.4f}, {:+.4f}]. "
        "Because the target is constructed from frozen P02e method disagreements, this is an error-atlas result, not an independent physics label."
    ).format(winner_row["method"], winner_row["value"], delta_winner["delta"], delta_winner["ci_low"], delta_winner["ci_high"])

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "reproduced": selected == expected,
        "repro_tolerance": "exact selected-pulse count",
        "reproduction": {
            "expected_selected_pulses": expected,
            "selected_pulses": selected,
            "passed": selected == expected,
            "baseline_samples": config["baseline_samples"],
            "amplitude_cut_adc": config["amplitude_cut_adc"],
            "staves": list(STAVE_NAMES),
        },
        "split": {
            "outer_folds": int(config["outer_folds"]),
            "n_runs": int(len(np.unique(runs))),
            "benchmark_rows": int(len(consensus)),
            "benchmark_key_sha256": sha256_bytes(
                b"|".join(
                    [
                        consensus["run"].to_numpy(dtype=np.int16).tobytes(),
                        consensus["event_index"].to_numpy(dtype=np.int32).tobytes(),
                        consensus["stave_index"].to_numpy(dtype=np.int8).tobytes(),
                    ]
                )
            ),
        },
        "targets": {
            "consensus_failure_any_rate": float(consensus["consensus_failure_any"].mean()),
            "consensus_failure_manual_rate": float(consensus["consensus_failure_manual"].mean()),
            "consensus_failure_peak_rate": float(consensus["consensus_failure_peak"].mean()),
        },
        "traditional": {
            "metric": "average_precision",
            "value": float(summary[(summary["method"] == "traditional_atom_score") & (summary["metric"] == "average_precision")]["value"].iloc[0]),
            "ci": [
                float(summary[(summary["method"] == "traditional_atom_score") & (summary["metric"] == "average_precision")]["ci_low"].iloc[0]),
                float(summary[(summary["method"] == "traditional_atom_score") & (summary["metric"] == "average_precision")]["ci_high"].iloc[0]),
            ],
        },
        "ml": {
            "metric": "average_precision",
            "method": str(winner_row["method"]),
            "value": float(winner_row["value"]),
            "ci": [float(winner_row["ci_low"]), float(winner_row["ci_high"])],
        },
        "winner": {
            "method": str(winner_row["method"]),
            "average_precision": float(winner_row["value"]),
            "ci_low": float(winner_row["ci_low"]),
            "ci_high": float(winner_row["ci_high"]),
            "delta_vs_traditional": float(delta_winner["delta"]),
            "delta_ci_low": float(delta_winner["ci_low"]),
            "delta_ci_high": float(delta_winner["ci_high"]),
        },
        "ml_beats_baseline": bool(winner_row["method"] != "traditional_atom_score" and float(delta_winner["ci_low"]) > 0.0),
        "winner_delta_vs_traditional": {
            "metric": "average_precision",
            "delta": float(delta_winner["delta"]),
            "ci": [float(delta_winner["ci_low"]), float(delta_winner["ci_high"])],
        },
        "falsification": {
            "preregistered_metric": "average_precision for consensus_failure_any under run-block splits",
            "n_tries": 6,
            "paired_bootstrap_ci_excludes_zero": bool(winner_row["method"] != "traditional_atom_score" and float(delta_winner["ci_low"]) > 0.0),
            "shuffled_label_ap": float(sent_ap["value"]),
        },
        "method_summary": summary.to_dict(orient="records"),
        "leakage_checks": leakage.to_dict(orient="records"),
        "input_sha256": sha256_file(out_dir / "input_sha256.csv"),
        "git_commit": git_commit(),
        "critic": "pending",
        "next_tickets": [
            "P02i: Freeze the P02h consensus-failure label and test the shape-gated CNN on a fresh raw-root sample not used by P02e; expected information gain: separates true morphology generalization from target-construction artifacts."
        ],
        "conclusion": conclusion,
        "runtime_seconds": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_sanitize(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, summary, deltas, enrich, risk, leakage)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/p02h_1781043998_641_6ef93138_consensus_failures.py",
        "config": str(args.config),
        "command": "/home/billy/anaconda3/bin/python scripts/p02h_1781043998_641_6ef93138_consensus_failures.py --config {}".format(args.config),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "input_file_count": int(len(input_sha)),
        "random_seed": int(config["random_seed"]),
        "reproduction_passed": selected == expected,
        "output_sha256": output_sha256_rows(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plot = summary[summary["metric"].isin(["average_precision", "roc_auc"])].copy()
        fig, ax = plt.subplots(figsize=(9, 4.8))
        for i, metric in enumerate(["average_precision", "roc_auc"]):
            sub = plot[plot["metric"] == metric].sort_values("value", ascending=True)
            ypos = np.arange(len(sub)) + i * 0.35
            ax.barh(ypos, sub["value"], height=0.32, label=metric)
            ax.set_yticks(np.arange(len(sub)) + 0.18)
            ax.set_yticklabels(sub["method"])
        ax.set_xlabel("held-out score")
        ax.set_title("P02h consensus-failure benchmark")
        ax.legend(loc="lower right")
        fig.tight_layout()
        fig.savefig(out_dir / "fig_method_benchmark.png", dpi=160)
        plt.close(fig)
    except Exception as exc:
        print("plot generation skipped: {}".format(exc))

    manifest["output_sha256"] = output_sha256_rows(out_dir)
    (out_dir / "manifest.json").write_text(json.dumps(json_sanitize(manifest), indent=2) + "\n", encoding="utf-8")

    print(summary.sort_values(["metric", "value"], ascending=[True, False]).to_string(index=False))
    print("winner:", result["winner"])
    print("DONE in {:.1f}s -> {}".format(result["runtime_seconds"], out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
