#!/usr/bin/env python3
"""S11h: delay/scale recovery frontier for the all-three injected target."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

os.environ.setdefault("MPLCONFIGDIR", "/tmp/ccb-testbeam-s11h-1781063906-mpl")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


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
    return float(brier_score_loss(y[mask], np.clip(prob[mask], 0.0, 1.0)))


def run_bootstrap_ci(
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray, np.ndarray], float],
    seed: int,
    n_boot: int,
) -> tuple[float, float]:
    unique_runs = np.unique(runs)
    rng = np.random.default_rng(seed)
    values: list[float] = []
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled_runs])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric(y[idx], score[idx])
        if math.isfinite(value):
            values.append(value)
    if len(values) < 20:
        return float("nan"), float("nan")
    return float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))


def fill_finite(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    finite = np.isfinite(values)
    fill = float(np.nanmedian(values[finite])) if finite.any() else 0.0
    return np.where(finite, values, fill)


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


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


def crossfold_minmax_prob(score: np.ndarray, fold_id: np.ndarray) -> np.ndarray:
    prob = np.full(len(score), np.nan, dtype=float)
    for fold in np.unique(fold_id[fold_id >= 0]):
        train = (fold_id >= 0) & (fold_id != fold) & np.isfinite(score)
        test = (fold_id == fold) & np.isfinite(score)
        if not test.any():
            continue
        lo, hi = np.percentile(score[train], [2.0, 98.0]) if train.any() else (np.nanmin(score[test]), np.nanmax(score[test]))
        prob[test] = np.clip((score[test] - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
    return prob


def feature_matrix(data: pd.DataFrame, utils) -> tuple[list[str], np.ndarray]:
    cols = sorted(set(utils.feature_columns(data, "strict_shape") + utils.feature_columns(data, "slot_shape")))
    forbidden = ["d_t_ns", "abs_c_t", "base_", "event", "pair", "delay", "scale", "target", "run", "chi2", "secondary", "sse"]
    cols = [col for col in cols if not any(fragment in col for fragment in forbidden) and not col.endswith("_log_amp")]
    return cols, data[cols].to_numpy(dtype=np.float32)


def waveform_tensor(data: pd.DataFrame) -> np.ndarray:
    waves = []
    for _, row in data.iterrows():
        corrected = np.asarray(row["_corrected"], dtype=np.float32)
        amp = np.maximum(np.asarray(row["_amplitude"], dtype=np.float32), 1.0)
        waves.append(corrected / amp[:, None])
    return np.stack(waves).astype(np.float32)


def sklearn_oof(data: pd.DataFrame, y: np.ndarray, X: np.ndarray, model_name: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    runs = data["run"].to_numpy(dtype=int)
    score = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        test = runs == held_run
        train = ~test
        if model_name == "ridge":
            clf = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), RidgeClassifier(alpha=2.0, class_weight="balanced"))
        elif model_name == "hgb":
            clf = make_pipeline(
                SimpleImputer(strategy="median"),
                HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, max_leaf_nodes=11, l2_regularization=0.08, random_state=seed + fold),
            )
        elif model_name == "mlp":
            clf = make_pipeline(
                SimpleImputer(strategy="median"),
                StandardScaler(),
                MLPClassifier(
                    hidden_layer_sizes=(48, 24),
                    activation="relu",
                    alpha=0.02,
                    learning_rate_init=0.003,
                    max_iter=160,
                    early_stopping=True,
                    n_iter_no_change=25,
                    random_state=seed + fold,
                ),
            )
        else:
            raise ValueError(model_name)
        clf.fit(X[train], y[train])
        if hasattr(clf[-1], "predict_proba"):
            score[test] = clf.predict_proba(X[test])[:, 1]
        else:
            score[test] = clf.decision_function(X[test])
        fold_id[test] = fold
    return score, fold_id


class SimpleCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(4, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(24, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class ChannelAttentionCNN(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(4, 24, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(24, 24, kernel_size=5, padding=2),
            nn.ReLU(),
        )
        self.gate = nn.Sequential(nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(24, 8), nn.ReLU(), nn.Linear(8, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.AdaptiveMaxPool1d(1), nn.Flatten(), nn.Linear(24, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.conv(x)
        gate = self.gate(z).unsqueeze(-1)
        return self.head(z * gate).squeeze(-1)


def torch_oof(data: pd.DataFrame, y: np.ndarray, X: np.ndarray, model_kind: str, config: dict, seed: int) -> tuple[np.ndarray, np.ndarray]:
    runs = data["run"].to_numpy(dtype=int)
    score = np.full(len(data), np.nan, dtype=float)
    fold_id = np.full(len(data), -1, dtype=int)
    epochs = int(config["nn_epochs"])
    batch_size = int(config["nn_batch_size"])
    torch.set_num_threads(1)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        torch.manual_seed(seed + fold)
        test = runs == held_run
        train = ~test
        mu = X[train].mean(axis=(0, 2), keepdims=True)
        sigma = X[train].std(axis=(0, 2), keepdims=True)
        sigma = np.where(sigma > 1e-6, sigma, 1.0)
        X_train = (X[train] - mu) / sigma
        X_test = (X[test] - mu) / sigma
        y_train = y[train].astype(np.float32)
        model: nn.Module = SimpleCNN() if model_kind == "cnn" else ChannelAttentionCNN()
        pos = max(float(y_train.sum()), 1.0)
        neg = max(float(len(y_train) - y_train.sum()), 1.0)
        loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([neg / pos], dtype=torch.float32))
        opt = torch.optim.AdamW(model.parameters(), lr=0.004, weight_decay=0.02)
        ds = TensorDataset(torch.tensor(X_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
        gen = torch.Generator().manual_seed(seed + 1000 + fold)
        loader = DataLoader(ds, batch_size=batch_size, shuffle=True, generator=gen)
        model.train()
        for _ in range(epochs):
            for xb, yb in loader:
                opt.zero_grad()
                loss = loss_fn(model(xb), yb)
                loss.backward()
                opt.step()
        model.eval()
        with torch.no_grad():
            logits = model(torch.tensor(X_test, dtype=torch.float32)).numpy()
        score[test] = 1.0 / (1.0 + np.exp(-logits))
        fold_id[test] = fold
    return score, fold_id


def fixed_95_clean_rejection(y: np.ndarray, score: np.ndarray) -> float:
    clean = score[y == 0]
    injected = score[y == 1]
    clean = clean[np.isfinite(clean)]
    injected = injected[np.isfinite(injected)]
    if len(clean) == 0 or len(injected) == 0:
        return float("nan")
    threshold = float(np.percentile(clean, 95.0))
    return float(np.mean(injected > threshold))


def add_cell_labels(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    injected = out[out["label_injected"] == 1].set_index("pair_id")
    delay_map = injected["injected_delay_samples"].to_dict()
    scale_map = injected["injected_scale"].to_dict()
    out["cell_delay"] = out["pair_id"].map(delay_map).astype(int)
    out["cell_scale"] = out["pair_id"].map(scale_map).astype(float)
    bins = [0.12, 0.20, 0.29, 0.38 + 1e-9]
    labels = ["low", "mid", "high"]
    out["cell_scale_bin"] = pd.cut(out["cell_scale"], bins=bins, labels=labels, include_lowest=True).astype(str)
    return out


def cell_metrics(data: pd.DataFrame, method_scores: dict[str, np.ndarray], fit_oof: pd.DataFrame, shuffled_score: np.ndarray, config: dict) -> pd.DataFrame:
    rows: list[dict] = []
    y = data["label_injected"].to_numpy(dtype=int)
    for method, score in method_scores.items():
        for (delay, scale_bin), group in data.groupby(["cell_delay", "cell_scale_bin"], sort=True):
            idx = group.index.to_numpy()
            yy = y[idx]
            if len(np.unique(yy)) < 2:
                continue
            inj_idx = group.index[group["label_injected"] == 1].to_numpy()
            delay_err = fit_oof.loc[inj_idx, "delay_samples"].to_numpy(dtype=float) - data.loc[inj_idx, "injected_delay_samples"].to_numpy(dtype=float)
            valid = fit_oof.loc[inj_idx, "valid"].astype(bool).to_numpy()
            method_auc = auc(yy, score[idx])
            shuffle_auc = auc(yy, shuffled_score[idx])
            coverage = fixed_95_clean_rejection(yy, score[idx])
            rows.append(
                {
                    "method": method,
                    "delay_samples": int(delay),
                    "scale_bin": str(scale_bin),
                    "n": int(len(idx)),
                    "n_injected": int(yy.sum()),
                    "roc_auc": method_auc,
                    "average_precision": ap(yy, score[idx]),
                    "fixed_95_clean_rejection": coverage,
                    "real_minus_shuffled_auc": float(method_auc - shuffle_auc) if math.isfinite(method_auc) and math.isfinite(shuffle_auc) else float("nan"),
                    "frontier_pass": bool(
                        math.isfinite(method_auc)
                        and math.isfinite(shuffle_auc)
                        and method_auc - shuffle_auc > float(config["frontier_auc_margin_over_shuffle"])
                        and math.isfinite(coverage)
                        and coverage >= float(config["frontier_min_coverage"])
                    ),
                    "fit_delay_bias_samples": float(np.nanmean(delay_err)),
                    "fit_delay_rms_samples": float(np.sqrt(np.nanmean(delay_err**2))),
                    "fit_failure_rate": float(1.0 - np.mean(valid)),
                }
            )
    return pd.DataFrame(rows).sort_values(["method", "delay_samples", "scale_bin"])


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    counts: pd.DataFrame,
    fit_choices: pd.DataFrame,
    scoreboard: pd.DataFrame,
    cells: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner_method"]
    top_cells = cells[cells["method"] == winner][
        ["delay_samples", "scale_bin", "n_injected", "roc_auc", "average_precision", "fixed_95_clean_rejection", "real_minus_shuffled_auc", "frontier_pass", "fit_delay_bias_samples", "fit_delay_rms_samples", "fit_failure_rate"]
    ]
    head = scoreboard[["method", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision", "ap_ci_low", "ap_ci_high", "brier", "brier_ci_low", "brier_ci_high"]]
    text = f"""# S11h: all-three delay-scale recovery frontier

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT `HRDv` from the S07f configuration.
- **Target:** S07f/S11e all-three injected two-pulse truth, Sample-II analysis runs, B2+B4+B6+B8 selected, `A>1000` ADC, clean sideband `D_t<3 ns`.
- **Split:** leave-one-run-out. All intervals in the global table are run-block bootstrap 95% CIs.
- **Winner recorded in `result.json`:** `{winner}`.

## Raw ROOT Reproduction

The first gate re-reads the ROOT files and rebuilds the all-three control population before any model is trained.

{markdown_table(reproduction)}

The exact-count gates reproduce the parent App.I gross tail, the all-three control sample, and the all-three guarded gross tail. The S07f traditional and RF AUC reproductions verify that this ticket uses the same injected target as the earlier all-three validation.

## Data Set

{markdown_table(counts)}

Each clean event `i` is paired with one injected copy. If `x[i,c,s]` is channel `c`, sample `s`, and `k_i` is the selected downstream channel, the injected waveform is

`x_prime[i,k,s] = x[i,k,s] + alpha_i * x[i,k,s-d_i]`,

with delay `d_i` in `{config['template_delay_candidates']}` samples and secondary scale `alpha_i` in the S07f range. Pair members share the same run and are therefore always held out together.

## Methods

The strong traditional method is the S11e constrained one-pulse versus two-pulse fit. For a normalized downstream waveform \(z\), each training-run template \(t\), and candidate delay \(d\), the one-pulse model is `z = a t + b 1 + eps`; the two-pulse model is `z = a t + c shift_d(t) + b 1 + eps`, constrained to positive amplitudes and bounded secondary fraction. The fold-local score is selected from secondary fraction, secondary amplitude, delay, chi2/ndf, SSE improvement, and related fit outputs using training runs only.

The ML/NN competitors use only waveform-shape features or normalized waveforms: shape-only random forest, ridge classifier, gradient-boosted trees, MLP, 1D-CNN, and a channel-attention CNN. Timing values, run/event identifiers, pair identifiers, injected delay/scale/target, absolute amplitudes, and fit outputs are excluded from the ML/NN feature sets. Scores are out-of-fold; probabilities use either model probabilities or fold-local score scaling for methods without calibrated probabilities.

Traditional fit fold choices:

{markdown_table(fit_choices)}

## Global Results

{markdown_table(head)}

The winner by preregistered global ROC AUC is `{winner}` with AUC {result['winner_roc_auc']:.3f}. The best traditional-fit AUC is {result['traditional_auc']:.3f}; the winner-minus-traditional AUC difference is {result['winner_minus_traditional_auc']:.3f}.

## Delay/Scale Frontier

Frontier pass is defined per delay/scale cell as `(AUC_real - AUC_shuffled) > {config['frontier_auc_margin_over_shuffle']}` and fixed-95%-clean injected rejection at least {config['frontier_min_coverage']:.2f}. The fixed-clean threshold is the 95th percentile of clean scores in the same cell, so the reported rejection is the fraction of injected events above that threshold.

{markdown_table(top_cells)}

The fit-delay columns are evaluated on injected events in the same cells. They show whether the traditional fit recovers the injected delay, not merely whether a classifier separates injected from clean.

## Leakage And Systematics

{markdown_table(leakage)}

Run-block bootstrap addresses the limited number of independent runs, but it cannot create more run diversity than exists in the Sample-II all-three sideband. The smallest cells, especially run 58 and run 65 contributions, should be treated as frontier hints rather than precision measurements. The amplitude-only sentinel is reported because injection changes peak height; it is excluded from the main ML/NN comparisons. The shuffled-label sentinel is the null used in the frontier rule.

## Caveats

This is an injected-recovery study, not a direct beam pile-up rate measurement. The injected second pulse is a delayed scaled copy of the same waveform, so it under-represents independent pulse-shape variation and electronics correlations that would appear in real overlapping particles. Neural models are intentionally small to keep leave-one-run-out training deterministic on CPU; larger architectures would need a separate pre-registered capacity scan. CIs are run-block intervals and are therefore sensitive to the seven-run support.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s11h_1781063906_413_7e4c6b5c_delay_scale_recovery_frontier.py --config configs/s11h_1781063906_413_7e4c6b5c_delay_scale_recovery_frontier.json
```

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `dataset_counts_by_run.csv`, `global_scoreboard.csv`, `method_cell_metrics.csv`, `fit_output_fold_choices.csv`, `two_pulse_fit_oof.csv`, `leakage_checks.csv`, and `oof_predictions.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s11h_1781063906_413_7e4c6b5c_delay_scale_recovery_frontier.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = (ROOT / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    config = load_json(config_path)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    print("1/8 loading modules and raw ROOT target ...", flush=True)

    s07f = load_module("s07f_source_for_s11h", ROOT / config["s07f_script"])
    s11e = load_module("s11e_source_for_s11h", ROOT / config["s11e_script"])
    fitmod = load_module("s11b_fit_source_for_s11h", ROOT / config["s11b_fit_script"])
    s07f_config = load_json(ROOT / config["s07f_config"])
    s07f_config["ticket_id"] = config["ticket_id"]
    s07f_config["worker"] = config["worker"]
    s07f_config["output_dir"] = config["output_dir"]
    utils = s07f.load_s07d_utils(ROOT / s07f_config["utility_script"])
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])

    parent, all_three, run_counts, clean_payloads = s07f.collect_parent_and_all_three(s07f_config, utils)
    parent_guarded = int((parent["d_t_ns"] > float(s07f_config["gross_dt_min_ns"])).sum())
    all_three_guarded = int((all_three["d_t_ns"] > float(s07f_config["gross_dt_min_ns"])).sum())
    all_three_clean = int((all_three["d_t_ns"] < float(s07f_config["clean_dt_max_ns"])).sum())
    reproduction = pd.DataFrame(
        [
            {"quantity": "parent App.I guarded gross D_t>51 ns", "report_value": int(s07f_config["expected_parent_gross_events"]), "reproduced": parent_guarded, "delta": parent_guarded - int(s07f_config["expected_parent_gross_events"]), "tolerance": 0, "pass": parent_guarded == int(s07f_config["expected_parent_gross_events"])},
            {"quantity": "all-three control events", "report_value": int(s07f_config["expected_all_three_control_events"]), "reproduced": int(len(all_three)), "delta": int(len(all_three)) - int(s07f_config["expected_all_three_control_events"]), "tolerance": 0, "pass": int(len(all_three)) == int(s07f_config["expected_all_three_control_events"])},
            {"quantity": "all-three clean events D_t<3 ns", "report_value": None, "reproduced": all_three_clean, "delta": None, "tolerance": None, "pass": True},
            {"quantity": "all-three guarded gross D_t>51 ns", "report_value": int(s07f_config["expected_all_three_guarded_gross_events"]), "reproduced": all_three_guarded, "delta": all_three_guarded - int(s07f_config["expected_all_three_guarded_gross_events"]), "tolerance": 0, "pass": all_three_guarded == int(s07f_config["expected_all_three_guarded_gross_events"])},
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw-ROOT all-three reproduction gate failed")

    print("2/8 reproducing S07f injected benchmark ...", flush=True)
    counts, s07f_score, s07f_rf_scan, s07f_choices, s07f_leakage, s07f_oof, s07f_details = s07f.independent_injection_benchmark(
        s07f_config, utils, clean_payloads
    )
    s07f_trad_auc = float(s07f_score.loc[s07f_score["method"] == "traditional fold-selected timing/template", "roc_auc"].iloc[0])
    s07f_rf_auc = float(s07f_score.loc[s07f_score["method"] == "all-three shape-only RF", "roc_auc"].iloc[0])
    reproduction = pd.concat(
        [
            reproduction,
            pd.DataFrame(
                [
                    {
                        "quantity": "S07f traditional injected ROC AUC",
                        "report_value": float(config["expected_s07f_traditional_auc"]),
                        "reproduced": s07f_trad_auc,
                        "delta": s07f_trad_auc - float(config["expected_s07f_traditional_auc"]),
                        "tolerance": float(config["s07f_reproduction_auc_tolerance"]),
                        "pass": abs(s07f_trad_auc - float(config["expected_s07f_traditional_auc"])) <= float(config["s07f_reproduction_auc_tolerance"]),
                    },
                    {
                        "quantity": "S07f shape-only RF injected ROC AUC",
                        "report_value": float(config["expected_s07f_shape_rf_auc"]),
                        "reproduced": s07f_rf_auc,
                        "delta": s07f_rf_auc - float(config["expected_s07f_shape_rf_auc"]),
                        "tolerance": float(config["s07f_reproduction_auc_tolerance"]),
                        "pass": abs(s07f_rf_auc - float(config["expected_s07f_shape_rf_auc"])) <= float(config["s07f_reproduction_auc_tolerance"]),
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("S07f reproduction gate failed")

    print("3/8 constructing S11h dataset and traditional fit ...", flush=True)
    data = add_cell_labels(utils.make_dataset(s07f_config, clean_payloads))
    y = data["label_injected"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    fit_score, fit_fold, fit_choices, fit_oof = s11e.constrained_fit_only_oof(data, y, config, s07f_config, utils, fitmod)
    fit_prob = fitmod.crossfold_isotonic(y, fit_score, fit_fold)

    print("4/8 training RF and tabular ML baselines ...", flush=True)
    shape_cols = utils.feature_columns(data, "strict_shape")
    rf_scan, best_rf_params, rf_score, rf_fold, rf_prob = utils.evaluate_rf_grid(data, y, shape_cols, config)
    X_cols, X = feature_matrix(data, utils)
    ridge_score, ridge_fold = sklearn_oof(data, y, X, "ridge", seed + 10)
    hgb_score, hgb_fold = sklearn_oof(data, y, X, "hgb", seed + 20)
    mlp_score, mlp_fold = sklearn_oof(data, y, X, "mlp", seed + 30)
    print("5/8 training waveform neural baselines ...", flush=True)
    waves = waveform_tensor(data)
    cnn_score, cnn_fold = torch_oof(data, y, waves, "cnn", config, seed + 40)
    attn_score, attn_fold = torch_oof(data, y, waves, "attention", config, seed + 50)
    shuffle_score, _ = utils.rf_oof(data, y, shape_cols, best_rf_params, seed + 60, shuffle_train=True)

    print("6/8 summarizing global and cell metrics ...", flush=True)
    method_scores = {
        "bounded two-pulse fit": fit_score,
        "shape-only RF": rf_score,
        "ridge": ridge_score,
        "gradient-boosted trees": hgb_score,
        "MLP": mlp_score,
        "1D-CNN": cnn_score,
        "channel-attention CNN": attn_score,
    }
    method_probs = {
        "bounded two-pulse fit": fit_prob,
        "shape-only RF": rf_prob,
        "ridge": crossfold_minmax_prob(ridge_score, ridge_fold),
        "gradient-boosted trees": crossfold_minmax_prob(hgb_score, hgb_fold),
        "MLP": crossfold_minmax_prob(mlp_score, mlp_fold),
        "1D-CNN": crossfold_minmax_prob(cnn_score, cnn_fold),
        "channel-attention CNN": crossfold_minmax_prob(attn_score, attn_fold),
    }
    notes = {
        "bounded two-pulse fit": "Strong traditional constrained template fit; score chosen from fit outputs on training runs only.",
        "shape-only RF": f"Best params={best_rf_params}; strict shape features only.",
        "ridge": "L2 ridge linear classifier on normalized waveform-shape features.",
        "gradient-boosted trees": "Histogram gradient-boosted trees on the same shape-only feature table.",
        "MLP": "Small regularized multilayer perceptron on the same shape-only feature table.",
        "1D-CNN": "Convolutional net on four amplitude-normalized 18-sample waveforms.",
        "channel-attention CNN": "New architecture: channel-attention CNN on normalized waveform tensors.",
    }
    scoreboard = pd.DataFrame(
        [
            summarize_method(method, y, method_scores[method], method_probs[method], runs, seed + 100 * i, n_boot, notes[method])
            for i, method in enumerate(method_scores, start=1)
        ]
    ).sort_values("roc_auc", ascending=False)
    cells = cell_metrics(data, method_scores, fit_oof, shuffle_score, config)
    topo_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "topology"), best_rf_params, seed + 501)
    amp_score, _ = utils.rf_oof(data, y, utils.feature_columns(data, "amplitude"), best_rf_params, seed + 502)
    pair_split_violations = 0
    for held_run in sorted(np.unique(runs)):
        pair_split_violations += len(set(data.loc[runs != held_run, "pair_id"].astype(int)) & set(data.loc[runs == held_run, "pair_id"].astype(int)))
    leakage = pd.DataFrame(
        [
            {"probe": "pre-injection D_t", "roc_auc": auc(y, data["base_d_t_ns"].to_numpy(dtype=float)), "average_precision": ap(y, data["base_d_t_ns"].to_numpy(dtype=float)), "notes": "Same for clean/injected pairs; should be chance."},
            {"probe": "topology-only RF", "roc_auc": auc(y, topo_score), "average_precision": ap(y, topo_score), "notes": "All-three topology should carry no label information."},
            {"probe": "absolute-amplitude-only RF", "roc_auc": auc(y, amp_score), "average_precision": ap(y, amp_score), "notes": "Excluded nuisance; injection changes peak height."},
            {"probe": "shape RF with shuffled training labels", "roc_auc": auc(y, shuffle_score), "average_precision": ap(y, shuffle_score), "notes": "Null for frontier pass rule."},
            {"probe": "pair split violations", "roc_auc": float(pair_split_violations), "average_precision": float("nan"), "notes": "Must be 0."},
            {"probe": "main feature count", "roc_auc": float(len(X_cols)), "average_precision": float("nan"), "notes": "Shape-only tabular features used by ridge/HGB/MLP."},
        ]
    )

    print("7/8 writing artifacts ...", flush=True)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    counts.to_csv(out_dir / "dataset_counts_by_run.csv", index=False)
    s07f_score.to_csv(out_dir / "s07f_reproduction_scoreboard.csv", index=False)
    s07f_rf_scan.to_csv(out_dir / "s07f_reproduction_rf_cv_scan.csv", index=False)
    s07f_choices.to_csv(out_dir / "s07f_traditional_fold_choices.csv", index=False)
    s07f_leakage.to_csv(out_dir / "s07f_reproduction_leakage_checks.csv", index=False)
    fit_choices.to_csv(out_dir / "fit_output_fold_choices.csv", index=False)
    fit_oof.to_csv(out_dir / "two_pulse_fit_oof.csv", index=False)
    rf_scan.to_csv(out_dir / "rf_cv_scan.csv", index=False)
    pd.DataFrame({"feature": X_cols}).to_csv(out_dir / "shape_feature_columns.csv", index=False)
    scoreboard.to_csv(out_dir / "global_scoreboard.csv", index=False)
    cells.to_csv(out_dir / "method_cell_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    oof_cols = ["row_id", "event_key", "pair_id", "run", "label_injected", "variant", "base_d_t_ns", "d_t_ns", "abs_c_t_ns", "target_stave", "injected_delay_samples", "injected_scale", "cell_delay", "cell_scale_bin"]
    oof = data[oof_cols].copy().reset_index(drop=True)
    for method, score in method_scores.items():
        safe = method.lower().replace("-", "").replace(" ", "_")
        oof[f"{safe}_score"] = score
        oof[f"{safe}_prob"] = method_probs[method]
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    winner_row = scoreboard.iloc[0]
    traditional_auc = float(scoreboard.loc[scoreboard["method"] == "bounded two-pulse fit", "roc_auc"].iloc[0])
    winner = str(winner_row["method"])
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "parent_guarded_gross_events": int(parent_guarded),
        "all_three_control_events": int(len(all_three)),
        "all_three_clean_events": int(all_three_clean),
        "all_three_guarded_gross_events": int(all_three_guarded),
        "dataset_events": int(len(data)),
        "dataset_pairs": int(data["pair_id"].nunique()),
        "winner_method": winner,
        "winner_roc_auc": float(winner_row["roc_auc"]),
        "winner_roc_auc_ci": [float(winner_row["roc_auc_ci_low"]), float(winner_row["roc_auc_ci_high"])],
        "winner_average_precision": float(winner_row["average_precision"]),
        "traditional_auc": traditional_auc,
        "winner_minus_traditional_auc": float(winner_row["roc_auc"] - traditional_auc),
        "best_rf_params": best_rf_params,
        "frontier_passed_cells_for_winner": int(cells[(cells["method"] == winner) & (cells["frontier_pass"])].shape[0]),
        "total_frontier_cells": int(cells[cells["method"] == winner].shape[0]),
        "pair_split_violations": int(pair_split_violations),
        "next_tickets": config.get("next_tickets", []),
        "elapsed_seconds": float(time.time() - t0),
    }
    write_report(out_dir, config, reproduction, counts, fit_choices, scoreboard, cells, leakage, result)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    input_rows = []
    for run in s07f_config["runs"]:
        path = s07f.raw_file(s07f_config, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    for path in [config_path, ROOT / config["s07f_config"], ROOT / config["s07f_script"], ROOT / config["s11e_script"], ROOT / config["s11b_fit_script"], ROOT / s07f_config["utility_script"]]:
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": sys.version,
        "command": f"/home/billy/anaconda3/bin/python scripts/s11h_1781063906_413_7e4c6b5c_delay_scale_recovery_frontier.py --config {config_path.relative_to(ROOT)}",
        "inputs": input_rows,
        "outputs": {},
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = sha256_file(path)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("8/8 done.", flush=True)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
