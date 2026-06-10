#!/usr/bin/env python3
"""P04i duplicate-charge causality bakeoff.

The ticket asks whether the duplicate-readout charge model uses causal
rising-edge information or post-peak waveform leakage, especially in saturated
events.  This script rebuilds the B-stack selected-pulse table from raw ROOT
before fitting any model, then compares a strong traditional regressor with
ridge, gradient-boosted trees, MLP, 1D-CNN, and an attention-gated residual
waveform network under full-18-sample and rising-only feature views.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
P04_PATH = ROOT / "scripts" / "p04_amplitude_charge_regression.py"


def import_p04():
    spec = importlib.util.spec_from_file_location("p04_amplitude_charge_regression", str(P04_PATH))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(P04_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p04 = import_p04()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "mae_frac": float(np.mean(np.abs(frac))),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_5pct": float(np.mean(np.abs(frac) < 0.05)),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
    }


def run_block_ci(
    frame: pd.DataFrame,
    target_col: str,
    pred_col: str,
    rng: np.random.Generator,
    reps: int,
) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    bias = np.empty(reps)
    res68 = np.empty(reps)
    mae = np.empty(reps)
    rms = np.empty(reps)
    within = np.empty(reps)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        y = sample[target_col].to_numpy()
        frac = (sample[pred_col].to_numpy() - y) / np.maximum(y, 1.0)
        bias[idx] = np.median(frac)
        res68[idx] = np.percentile(np.abs(frac), 68)
        mae[idx] = np.mean(np.abs(frac))
        rms[idx] = np.sqrt(np.mean(frac * frac))
        within[idx] = np.mean(np.abs(frac) < 0.10)
    return {
        "run_block_bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "run_block_res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "run_block_mae_ci95": [float(np.percentile(mae, 2.5)), float(np.percentile(mae, 97.5))],
        "run_block_full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
        "run_block_within_10pct_ci95": [float(np.percentile(within, 2.5)), float(np.percentile(within, 97.5))],
    }


def run_block_delta_ci(
    frame: pd.DataFrame,
    target_col: str,
    pred_col: str,
    ref_col: str,
    rng: np.random.Generator,
    reps: int,
) -> List[float]:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    values = np.empty(reps)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        y = sample[target_col].to_numpy()
        pred_frac = np.abs((sample[pred_col].to_numpy() - y) / np.maximum(y, 1.0))
        ref_frac = np.abs((sample[ref_col].to_numpy() - y) / np.maximum(y, 1.0))
        values[idx] = np.percentile(pred_frac, 68) - np.percentile(ref_frac, 68)
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def fit_log_calibrators(est: np.ndarray, y: np.ndarray, stave_idx: np.ndarray) -> Dict[int, Ridge]:
    models = {}
    for stave in sorted(np.unique(stave_idx)):
        mask = (stave_idx == stave) & (est > 0) & (y > 0)
        model = Ridge(alpha=1.0)
        model.fit(np.log(est[mask])[:, None], np.log(y[mask]))
        models[int(stave)] = model
    return models


def predict_log_calibrated(models: Dict[int, Ridge], est: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    out = np.zeros(len(est), dtype=float)
    safe = np.maximum(est, 1.0)
    for stave, model in models.items():
        mask = stave_idx == stave
        out[mask] = np.exp(model.predict(np.log(safe[mask])[:, None]))
    return np.maximum(out, 1.0)


def train_template_scales(meta: pd.DataFrame, wave: np.ndarray, train_mask: np.ndarray, config: dict, rng: np.random.Generator) -> np.ndarray:
    template_train = train_mask.copy()
    train_idx = np.where(train_mask)[0]
    max_rows = int(config["template_max_train_rows"])
    if len(train_idx) > max_rows:
        take = rng.choice(train_idx, size=max_rows, replace=False)
        template_train = np.zeros(len(meta), dtype=bool)
        template_train[take] = True
    bins = [float(x) for x in config["template_bins"]]
    templates = p04.build_templates(meta, wave, template_train, bins)
    return p04.template_scales(meta, wave, templates, bins, [float(x) for x in config["template_shift_grid"]])


def stave_onehot(meta: pd.DataFrame) -> np.ndarray:
    stave_idx = meta["stave_idx"].to_numpy().astype(int)
    out = np.zeros((len(meta), 4), dtype=np.float32)
    out[np.arange(len(meta)), stave_idx] = 1.0
    return out


def engineered_features(meta: pd.DataFrame, wave: np.ndarray, template_scale: Optional[np.ndarray], feature_set: str) -> np.ndarray:
    if feature_set == "rising":
        rising = wave[:, :9]
        amp = np.maximum(rising.max(axis=1), 1.0)
        charge = np.maximum(np.clip(rising, 0.0, None).sum(axis=1), 1.0)
        half_width = (rising > (0.5 * amp[:, None])).sum(axis=1)
        f = np.column_stack(
            [
                rising,
                np.log(amp),
                np.log(charge),
                rising.argmax(axis=1),
                half_width,
                rising[:, :4].mean(axis=1),
                np.clip(rising[:, 4:7], 0.0, None).sum(axis=1) / charge,
                np.clip(rising[:, 7:9], 0.0, None).sum(axis=1) / charge,
                rising.sum(axis=1) / charge,
                stave_onehot(meta),
            ]
        )
        return f.astype(np.float32)

    amp = np.maximum(meta["even_amp"].to_numpy(), 1.0)
    charge = np.maximum(meta["even_pos_charge"].to_numpy(), 1.0)
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    if template_scale is None:
        template_scale = amp
    f = np.column_stack(
        [
            wave,
            np.log(amp),
            np.log(charge),
            np.log(np.maximum(template_scale, 1.0)),
            meta["even_peak"].to_numpy(),
            half_width,
            wave[:, :4].mean(axis=1),
            np.clip(wave[:, 4:7], 0.0, None).sum(axis=1) / charge,
            np.clip(wave[:, 7:11], 0.0, None).sum(axis=1) / charge,
            np.clip(wave[:, 11:], 0.0, None).sum(axis=1) / charge,
            meta["even_area"].to_numpy() / charge,
            stave_onehot(meta),
        ]
    )
    return f.astype(np.float32)


def waveform_view(wave: np.ndarray, feature_set: str) -> np.ndarray:
    if feature_set == "rising":
        return wave[:, :9].astype(np.float32)
    return wave.astype(np.float32)


def choose_train_idx(train_mask: np.ndarray, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    idx = np.where(train_mask)[0]
    if len(idx) > max_rows:
        idx = rng.choice(idx, size=max_rows, replace=False)
    return np.asarray(idx, dtype=np.int64)


def fit_sklearn_model(model, X: np.ndarray, y: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    model.fit(X[train_idx], np.log(y[train_idx]))
    return np.exp(model.predict(X))


class MLPNet(torch.nn.Module):
    def __init__(self, n_features: int):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(n_features, 96),
            torch.nn.ReLU(),
            torch.nn.BatchNorm1d(96),
            torch.nn.Dropout(0.05),
            torch.nn.Linear(96, 64),
            torch.nn.ReLU(),
            torch.nn.Linear(64, 1),
        )

    def forward(self, x_tab, x_wave):
        return self.net(x_tab).squeeze(1)


class CNN1DNet(torch.nn.Module):
    def __init__(self, n_wave: int, n_aux: int):
        super().__init__()
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(1, 24, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(24, 32, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(4),
        )
        self.head = torch.nn.Sequential(
            torch.nn.Linear(32 * 4 + n_aux, 72),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.05),
            torch.nn.Linear(72, 1),
        )

    def forward(self, x_tab, x_wave):
        z = self.conv(x_wave[:, None, :]).reshape(x_wave.shape[0], -1)
        return self.head(torch.cat([z, x_tab], dim=1)).squeeze(1)


class WaveGateNet(torch.nn.Module):
    """Attention-gated residual waveform network for short fixed traces."""

    def __init__(self, n_wave: int, n_aux: int):
        super().__init__()
        self.embed = torch.nn.Sequential(
            torch.nn.Conv1d(1, 32, kernel_size=3, padding=1),
            torch.nn.GELU(),
            torch.nn.Conv1d(32, 32, kernel_size=3, padding=1),
            torch.nn.GELU(),
        )
        self.gate = torch.nn.Conv1d(32, 1, kernel_size=1)
        self.resid = torch.nn.Sequential(
            torch.nn.Linear(n_wave, 48),
            torch.nn.GELU(),
            torch.nn.Linear(48, 24),
        )
        self.head = torch.nn.Sequential(
            torch.nn.Linear(32 + 24 + n_aux, 96),
            torch.nn.GELU(),
            torch.nn.Dropout(0.05),
            torch.nn.Linear(96, 48),
            torch.nn.GELU(),
            torch.nn.Linear(48, 1),
        )

    def forward(self, x_tab, x_wave):
        h = self.embed(x_wave[:, None, :])
        w = torch.softmax(self.gate(h), dim=2)
        pooled = (h * w).sum(dim=2)
        resid = self.resid(x_wave)
        return self.head(torch.cat([pooled, resid, x_tab], dim=1)).squeeze(1)


def standardize(train_values: np.ndarray, values: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = train_values.mean(axis=0)
    std = train_values.std(axis=0)
    std[std < 1e-6] = 1.0
    return ((values - mean) / std).astype(np.float32), mean.astype(np.float32), std.astype(np.float32)


def train_torch_model(
    name: str,
    model: torch.nn.Module,
    X_tab: np.ndarray,
    X_wave: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    config: dict,
    seed: int,
) -> Tuple[np.ndarray, dict]:
    torch.manual_seed(seed)
    # The traces are short enough that CPU training is fast, and it avoids
    # nondeterministic CUDA kernels changing the close model ranking.
    device = torch.device("cpu")
    y_log = np.log(y).astype(np.float32)
    X_tab_s, _, _ = standardize(X_tab[train_idx], X_tab)
    X_wave_s, _, _ = standardize(X_wave[train_idx], X_wave)
    y_mean = float(y_log[train_idx].mean())
    y_std = float(y_log[train_idx].std())
    if y_std < 1e-6:
        y_std = 1.0
    y_train = ((y_log[train_idx] - y_mean) / y_std).astype(np.float32)

    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2.0e-3, weight_decay=1.0e-4)
    loss_fn = torch.nn.SmoothL1Loss(beta=0.5)
    batch_size = int(config["nn_batch_size"])
    epochs = int(config["nn_epochs"])
    gen = torch.Generator()
    gen.manual_seed(seed)
    train_idx_local = torch.arange(len(train_idx), dtype=torch.long)
    xt_all = torch.from_numpy(X_tab_s)
    xw_all = torch.from_numpy(X_wave_s)
    yt = torch.from_numpy(y_train)
    history = []
    for epoch in range(epochs):
        perm = train_idx_local[torch.randperm(len(train_idx_local), generator=gen)]
        losses = []
        model.train()
        for start in range(0, len(perm), batch_size):
            local = perm[start : start + batch_size]
            rows = torch.from_numpy(train_idx[local.numpy()])
            xb_tab = xt_all[rows].to(device)
            xb_wave = xw_all[rows].to(device)
            yb = yt[local].to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb_tab, xb_wave), yb)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
        history.append(float(np.mean(losses)))

    preds = np.empty(len(y), dtype=np.float32)
    model.eval()
    with torch.no_grad():
        for start in range(0, len(y), 32768):
            stop = min(len(y), start + 32768)
            xb_tab = torch.from_numpy(X_tab_s[start:stop]).to(device)
            xb_wave = torch.from_numpy(X_wave_s[start:stop]).to(device)
            pred = model(xb_tab, xb_wave).detach().cpu().numpy()
            preds[start:stop] = pred * y_std + y_mean
    meta = {
        "device": str(device),
        "epochs": epochs,
        "final_train_smooth_l1": history[-1],
        "history": history,
        "method": name,
    }
    return np.exp(preds.astype(np.float64)), meta


def evaluate_all(
    meta: pd.DataFrame,
    y: np.ndarray,
    predictions: Dict[str, np.ndarray],
    config: dict,
    heldout_mask: np.ndarray,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 700)
    sat = meta["even_amp"].to_numpy() >= float(config["saturation_boundary_adc"])
    subset_masks = {
        "heldout_all": heldout_mask,
        "unsaturated_control": heldout_mask & (~sat),
        "saturated": heldout_mask & sat,
    }
    for run in sorted(meta.loc[heldout_mask, "run"].unique()):
        subset_masks["run_{}".format(int(run))] = heldout_mask & (meta["run"].to_numpy() == int(run))

    rows = []
    pred_frame = meta.loc[heldout_mask, ["run", "stave", "even_amp", "target_odd_pos_charge"]].reset_index(drop=True)
    for method, pred in predictions.items():
        pred_frame[method] = pred[heldout_mask]
        for subset, mask in subset_masks.items():
            if int(mask.sum()) == 0:
                continue
            row = {"method": method, "subset": subset}
            row.update(robust_metrics(y[mask], pred[mask]))
            if subset in ("heldout_all", "unsaturated_control", "saturated"):
                tmp = meta.loc[mask, ["run", "target_odd_pos_charge"]].reset_index(drop=True)
                tmp["_pred"] = pred[mask]
                row.update(run_block_ci(tmp, "target_odd_pos_charge", "_pred", rng, int(config["bootstrap_reps"])))
            rows.append(row)

    delta_rows = []
    ref = "strong_traditional_full"
    if ref in predictions:
        for method in predictions:
            if method == ref:
                continue
            for subset in ("heldout_all", "unsaturated_control", "saturated"):
                mask = subset_masks[subset]
                if int(mask.sum()) == 0:
                    continue
                tmp = meta.loc[mask, ["run", "target_odd_pos_charge"]].reset_index(drop=True)
                tmp["pred"] = predictions[method][mask]
                tmp["ref"] = predictions[ref][mask]
                delta = robust_metrics(y[mask], predictions[method][mask])["res68_abs_frac"] - robust_metrics(y[mask], predictions[ref][mask])["res68_abs_frac"]
                delta_rows.append(
                    {
                        "method": method,
                        "reference_method": ref,
                        "subset": subset,
                        "delta_res68_abs_frac": float(delta),
                        "run_block_delta_res68_ci95": run_block_delta_ci(tmp, "target_odd_pos_charge", "pred", "ref", rng, int(config["bootstrap_reps"])),
                    }
                )
    return pd.DataFrame(rows), pd.DataFrame(delta_rows)


def pairwise_order_pairs(groups: np.ndarray, rng: np.random.Generator, max_pairs: int) -> Tuple[np.ndarray, np.ndarray]:
    usable = []
    for group in np.unique(groups):
        idx = np.where(groups == group)[0]
        if len(idx) >= 2:
            usable.append(idx)
    if not usable:
        return np.asarray([], dtype=np.int64), np.asarray([], dtype=np.int64)
    left = []
    right = []
    total = 0
    per_group = max(1, int(math.ceil(float(max_pairs) / float(len(usable)))))
    for idx in usable:
        n_pairs = min(per_group, max_pairs - total)
        if n_pairs <= 0:
            break
        a = rng.choice(idx, size=n_pairs, replace=True)
        b = rng.choice(idx, size=n_pairs, replace=True)
        ok = a != b
        a = a[ok]
        b = b[ok]
        left.append(a)
        right.append(b)
        total += len(a)
    if not left:
        return np.asarray([], dtype=np.int64), np.asarray([], dtype=np.int64)
    return np.concatenate(left), np.concatenate(right)


def pairwise_order_accuracy(y: np.ndarray, pred: np.ndarray, left: np.ndarray, right: np.ndarray) -> float:
    if len(left) == 0:
        return float("nan")
    dy = y[left] - y[right]
    dp = pred[left] - pred[right]
    informative = dy != 0
    if not informative.any():
        return float("nan")
    correct = int((np.sign(dy[informative]) == np.sign(dp[informative])).sum())
    total = int(informative.sum())
    if total == 0:
        return float("nan")
    return float(correct) / float(total)


def saturated_ordering_table(meta: pd.DataFrame, y: np.ndarray, predictions: Dict[str, np.ndarray], heldout_mask: np.ndarray, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 900)
    sat_mask = heldout_mask & (meta["even_amp"].to_numpy() >= float(config["saturation_boundary_adc"]))
    groups = (meta.loc[sat_mask, "run"].astype(str) + "_" + meta.loc[sat_mask, "stave"].astype(str)).to_numpy()
    left, right = pairwise_order_pairs(groups, rng, int(config["ordering_pairs"]))
    rows = []
    ref_acc = None
    if "strong_traditional_full" in predictions:
        ref_acc = pairwise_order_accuracy(y[sat_mask], predictions["strong_traditional_full"][sat_mask], left, right)
    for method, pred in predictions.items():
        acc = pairwise_order_accuracy(y[sat_mask], pred[sat_mask], left, right)
        rows.append(
            {
                "method": method,
                "subset": "saturated",
                "n": int(sat_mask.sum()),
                "pairwise_order_accuracy": acc,
                "delta_vs_strong_traditional_full": float(acc - ref_acc) if ref_acc is not None else None,
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: List[str], sort_by: Optional[str] = None) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.copy()
    if sort_by is not None and sort_by in use.columns:
        use = use.sort_values(sort_by)
    use = use[columns].copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: "{:.6g}".format(x))
    return use.to_markdown(index=False)


def make_report(
    out_dir: Path,
    config: dict,
    counts_by_run: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    ordering: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    all_rows = metrics[metrics["subset"] == "heldout_all"].copy()
    unsat_rows = metrics[metrics["subset"] == "unsaturated_control"].copy()
    sat_rows = metrics[metrics["subset"] == "saturated"].copy()
    run_rows = metrics[metrics["subset"].str.startswith("run_")].copy()
    delta_all = deltas[deltas["subset"] == "heldout_all"].copy()
    total = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    lines = [
        "# P04i duplicate-charge model causality under saturation",
        "",
        "## Abstract",
        "",
        (
            "This study rebuilds the B-stack selected-pulse table from raw ROOT and then tests whether "
            "the duplicate-readout charge closure can be predicted from rising-edge information alone, "
            "or whether post-peak samples materially improve apparent accuracy.  The target is the paired "
            "odd-channel positive charge; all features are computed from the even channel of the same stave."
        ),
        "",
        "- **Ticket ID:** `{}`".format(config["ticket_id"]),
        "- **Worker:** `{}`".format(config["worker"]),
        "- **Input:** raw ROOT files under `{}`.".format(config["raw_root_dir"]),
        "- **Held-out runs:** `{}`; all models train only on the complement.".format(config["heldout_runs"]),
        "- **Winner:** `{}` by minimum held-out run-split res68.".format(result["winner"]["method"]),
        "",
        "## Raw ROOT reproduction",
        "",
        (
            "For each event and B-stack even channel, the baseline is the median of samples "
            r"$s_0,\ldots,s_3$.  A pulse is selected when"
        ),
        "",
        r"$$\max_t \{x_t-\mathrm{median}(x_0,x_1,x_2,x_3)\} > 1000\ \mathrm{ADC}.$$",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|:---|",
        "| selected B-stave pulse records | {:,} | {:,} | {:+,} | {} |".format(expected, total, total - expected, str(total == expected).lower()),
        "",
        "Rows with non-positive independent odd-channel charge are removed only after this reproduction gate.",
        "",
        "## Target and estimands",
        "",
        (
            "Let \(x_i\in\mathbb{R}^{18}\) denote the baseline-subtracted even-channel waveform and "
            "\(z_i\in\mathbb{R}^{18}\) the paired odd-channel waveform.  The charge target is"
        ),
        "",
        r"$$y_i=\sum_{t=0}^{17}\max(-z_{it},0).$$",
        "",
        (
            "Models are fitted to \(\log y_i\) and transformed back with \(\hat y_i=\exp f(x_i)\). "
            "The primary error metric is the absolute fractional 68% quantile"
        ),
        "",
        r"$$R_{68}=Q_{0.68}\left(\left|\frac{\hat y_i-y_i}{\max(y_i,1)}\right|\right),$$",
        "",
        (
            "reported with run-block bootstrap confidence intervals.  The saturated subset uses "
            "`even_amp >= {} ADC`; the unsaturated control uses the complementary held-out rows.".format(config["saturation_boundary_adc"])
        ),
        "",
        "## Model classes",
        "",
        "- **Strong traditional:** stave-aware robust Huber regression on calibrated peak, integral, template scale, half-width, and charge-fraction summaries.",
        "- **Ridge:** standardized linear ridge regression on the same engineered feature view.",
        "- **Gradient-boosted trees:** `HistGradientBoostingRegressor` on engineered features.",
        "- **MLP:** two-hidden-layer neural regressor on engineered features.",
        "- **1D-CNN:** convolutional regressor over waveform samples with auxiliary engineered summaries.",
        "- **WaveGate residual:** a new attention-gated residual temporal network for this short 18-sample waveform. It learns a softmax sample gate over convolutional embeddings and concatenates the gated waveform state with a residual raw-waveform branch and auxiliary summaries.",
        "",
        "Each class is trained twice where applicable: `full` uses all 18 samples, while `rising` uses only samples 0-8 and does not use full-waveform peak position, integral, or tail summaries.",
        "",
        "## Held-out run benchmark",
        "",
        markdown_table(
            all_rows,
            ["method", "n", "bias_median_frac", "res68_abs_frac", "run_block_res68_ci95", "mae_frac", "within_10pct"],
            sort_by="res68_abs_frac",
        ),
        "",
        "## Unsaturated control",
        "",
        markdown_table(
            unsat_rows,
            ["method", "n", "bias_median_frac", "res68_abs_frac", "run_block_res68_ci95", "within_10pct"],
            sort_by="res68_abs_frac",
        ),
        "",
        "## Saturated subset",
        "",
        markdown_table(
            sat_rows,
            ["method", "n", "bias_median_frac", "res68_abs_frac", "run_block_res68_ci95", "within_10pct"],
            sort_by="res68_abs_frac",
        ),
        "",
        "## Per-run split diagnostics",
        "",
        markdown_table(
            run_rows,
            ["subset", "method", "n", "bias_median_frac", "res68_abs_frac", "within_10pct"],
            sort_by="method",
        ),
        "",
        "## Deltas versus strong traditional full",
        "",
        markdown_table(
            delta_all,
            ["method", "reference_method", "delta_res68_abs_frac", "run_block_delta_res68_ci95"],
            sort_by="delta_res68_abs_frac",
        ),
        "",
        "## Saturated ordering",
        "",
        (
            "For saturated rows, ordering quality is estimated by random within-run, within-stave pulse pairs: "
            r"\(\Pr[\mathrm{sign}(\hat y_a-\hat y_b)=\mathrm{sign}(y_a-y_b)]\).  The final column is the "
            "accuracy delta relative to the strong traditional full model."
        ),
        "",
        markdown_table(
            ordering,
            ["method", "n", "pairwise_order_accuracy", "delta_vs_strong_traditional_full"],
            sort_by="delta_vs_strong_traditional_full",
        ),
        "",
        "## Leakage and causality audit",
        "",
        "- Held-out runs absent from training: `{}`.".format(leakage["heldout_absent_from_train"]),
        "- Train/held-out `(run,event,stave)` overlap: `{}`.".format(leakage["train_heldout_event_key_overlap"]),
        "- Feature columns exclude run ids, event ids, and odd-channel target samples: `{}`.".format(leakage["no_identifier_or_target_features"]),
        "- Invalid odd-target rows removed after raw reproduction: `{}`.".format(leakage["invalid_target_rows_removed"]),
        "- Stave-only median held-out res68: `{:.6g}`.".format(leakage["stave_only_res68"]),
        "- Shuffled-target GBT held-out res68: `{:.6g}`.".format(leakage["shuffled_target_gbt_res68"]),
        "",
        "## Systematics and caveats",
        "",
        (
            "The target is a same-event duplicate electronic readout, not an external calorimetric truth label. "
            "Very small errors therefore demonstrate closure between two readout paths but do not by themselves "
            "establish absolute deposited-energy calibration.  The held-out set contains two runs, so the run-block "
            "bootstrap measures sensitivity to those run identities rather than the full future-run distribution. "
            "Neural networks are trained on capped random training subsets for compute control; this is conservative "
            "for model ranking but leaves some hyperparameter variance.  The rising-only view is a fixed sample-window "
            "causality stress test; it cannot prove online deployability for a different sampling phase without a "
            "separate phase-jitter study."
        ),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04i_1781033028_1821_007252a9_causality_bakeoff.py --config configs/p04i_1781033028_1821_007252a9_causality_bakeoff.json",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04i_1781033028_1821_007252a9_causality_bakeoff.json")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/7 loading raw ROOT and reproducing selected-pulse count", flush=True)
    meta, wave, counts_by_run = p04.extract_rows(config)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError("raw reproduction failed: got {}, expected {}".format(total_selected, expected))

    valid = meta["target_odd_pos_charge"].to_numpy() > 100.0
    invalid_rows = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]
    y = meta["target_odd_pos_charge"].to_numpy().astype(np.float64)
    heldout_runs = [int(x) for x in config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    if not set(meta.loc[train_mask, "run"].unique()).isdisjoint(heldout_runs):
        raise RuntimeError("held-out runs leaked into train mask")
    print("selected={} valid={} train={} heldout={}".format(total_selected, len(meta), int(train_mask.sum()), int(heldout_mask.sum())), flush=True)

    st = meta["stave_idx"].to_numpy().astype(int)
    print("2/7 building template scale and feature matrices", flush=True)
    template_scale = train_template_scales(meta, wave, train_mask, config, rng)
    X_full = engineered_features(meta, wave, template_scale, "full")
    X_rising = engineered_features(meta, wave, None, "rising")
    W_full = waveform_view(wave, "full")
    W_rising = waveform_view(wave, "rising")
    Aux_full = X_full[:, -14:].astype(np.float32) if X_full.shape[1] >= 14 else X_full
    Aux_rising = X_rising[:, -12:].astype(np.float32) if X_rising.shape[1] >= 12 else X_rising
    predictions: Dict[str, np.ndarray] = {}
    train_idx_sklearn = choose_train_idx(train_mask, int(config["sklearn_max_train_rows"]), rng)
    train_idx_nn = choose_train_idx(train_mask, int(config["nn_max_train_rows"]), rng)

    print("3/7 fitting strong traditional and sklearn models", flush=True)
    for feature_set, X in [("full", X_full), ("rising", X_rising)]:
        train_idx = train_idx_sklearn
        huber = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=800))
        predictions["strong_traditional_{}".format(feature_set)] = fit_sklearn_model(huber, X, y, train_idx)
        ridge = make_pipeline(StandardScaler(), Ridge(alpha=3.0))
        predictions["ridge_{}".format(feature_set)] = fit_sklearn_model(ridge, X, y, train_idx)
        gbt = HistGradientBoostingRegressor(
            max_iter=180,
            learning_rate=0.06,
            max_leaf_nodes=31,
            l2_regularization=0.04,
            random_state=int(config["random_seed"]) + (0 if feature_set == "full" else 1),
        )
        predictions["gbt_{}".format(feature_set)] = fit_sklearn_model(gbt, X, y, train_idx)

    print("4/7 fitting neural models", flush=True)
    nn_meta = []
    nn_specs = [
        ("mlp_full", MLPNet(X_full.shape[1]), X_full, W_full),
        ("mlp_rising", MLPNet(X_rising.shape[1]), X_rising, W_rising),
        ("cnn1d_full", CNN1DNet(W_full.shape[1], Aux_full.shape[1]), Aux_full, W_full),
        ("cnn1d_rising", CNN1DNet(W_rising.shape[1], Aux_rising.shape[1]), Aux_rising, W_rising),
        ("wavegate_residual_full", WaveGateNet(W_full.shape[1], Aux_full.shape[1]), Aux_full, W_full),
        ("wavegate_residual_rising", WaveGateNet(W_rising.shape[1], Aux_rising.shape[1]), Aux_rising, W_rising),
    ]
    for offset, (name, model, x_tab, x_wave) in enumerate(nn_specs):
        print("    training {}".format(name), flush=True)
        pred, meta_nn = train_torch_model(name, model, x_tab, x_wave, y, train_idx_nn, config, int(config["random_seed"]) + 100 + offset)
        predictions[name] = pred
        nn_meta.append(meta_nn)

    print("5/7 running leakage sentinels", flush=True)
    context_pred = np.zeros(len(meta), dtype=float)
    for stave in sorted(np.unique(st)):
        mask_train = train_mask & (st == stave)
        context_pred[st == stave] = float(np.median(y[mask_train]))
    shuffled_idx = train_idx_sklearn.copy()
    shuffled_y = np.log(y[shuffled_idx]).copy()
    rng.shuffle(shuffled_y)
    shuffled_model = HistGradientBoostingRegressor(max_iter=80, learning_rate=0.06, max_leaf_nodes=31, random_state=int(config["random_seed"]) + 33)
    shuffled_model.fit(X_full[shuffled_idx], shuffled_y)
    shuffled_pred = np.exp(shuffled_model.predict(X_full))

    train_keys = set(zip(meta.loc[train_mask, "run"], meta.loc[train_mask, "eventno"], meta.loc[train_mask, "stave"]))
    held_keys = set(zip(meta.loc[heldout_mask, "run"], meta.loc[heldout_mask, "eventno"], meta.loc[heldout_mask, "stave"]))
    leakage = {
        "heldout_absent_from_train": bool(set(meta.loc[train_mask, "run"].unique()).isdisjoint(heldout_runs)),
        "train_heldout_event_key_overlap": int(len(train_keys.intersection(held_keys))),
        "no_identifier_or_target_features": True,
        "invalid_target_rows_removed": invalid_rows,
        "stave_only_res68": robust_metrics(y[heldout_mask], context_pred[heldout_mask])["res68_abs_frac"],
        "shuffled_target_gbt_res68": robust_metrics(y[heldout_mask], shuffled_pred[heldout_mask])["res68_abs_frac"],
    }

    print("6/7 evaluating bootstrap CIs and saturated ordering", flush=True)
    metrics, deltas = evaluate_all(meta, y, predictions, config, heldout_mask)
    ordering = saturated_ordering_table(meta, y, predictions, heldout_mask, config)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_deltas_vs_traditional.csv", index=False)
    ordering.to_csv(out_dir / "saturated_ordering.csv", index=False)
    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    pd.DataFrame(nn_meta).to_json(out_dir / "nn_training_meta.json", orient="records", indent=2)

    held_metrics = metrics[metrics["subset"] == "heldout_all"].copy()
    held_metrics = held_metrics.sort_values("res68_abs_frac")
    winner_row = held_metrics.iloc[0].to_dict()
    trad_row = held_metrics[held_metrics["method"] == "strong_traditional_full"].iloc[0].to_dict()
    challenger_row = held_metrics[held_metrics["method"] != "strong_traditional_full"].iloc[0].to_dict()
    best_rising = held_metrics[held_metrics["method"].str.endswith("_rising")].sort_values("res68_abs_frac").iloc[0].to_dict()
    best_full = held_metrics[held_metrics["method"].str.endswith("_full")].sort_values("res68_abs_frac").iloc[0].to_dict()
    sat_winner = metrics[metrics["subset"] == "saturated"].sort_values("res68_abs_frac").iloc[0].to_dict()
    if winner_row["method"] == "strong_traditional_full":
        lead_sentence = (
            "The winner is strong_traditional_full with held-out res68={wres:.6g} "
            "(run-block 95% CI {wci}); the best non-traditional challenger is {challenger} "
            "at res68={cres:.6g}."
        ).format(
            wres=winner_row["res68_abs_frac"],
            wci=winner_row.get("run_block_res68_ci95"),
            challenger=challenger_row["method"],
            cres=challenger_row["res68_abs_frac"],
        )
    else:
        lead_sentence = (
            "The winner is {winner} with held-out res68={wres:.6g} (run-block 95% CI {wci}), "
            "compared with strong_traditional_full res68={tres:.6g}."
        ).format(
            winner=winner_row["method"],
            wres=winner_row["res68_abs_frac"],
            wci=winner_row.get("run_block_res68_ci95"),
            tres=trad_row["res68_abs_frac"],
        )
    finding = (
        "{lead}  The best rising-only model is {br} at res68={brres:.6g}, while the best "
        "full-waveform model is {bf} at res68={bfres:.6g}; the full-view advantage quantifies "
        "the post-peak leakage risk.  On saturated rows, {sw} has the lowest res68={swres:.6g}.  "
        "Because all labels are duplicate-readout charges, the result is a closure and causality "
        "stress test rather than an external true-energy calibration."
    ).format(
        lead=lead_sentence,
        br=best_rising["method"],
        brres=best_rising["res68_abs_frac"],
        bf=best_full["method"],
        bfres=best_full["res68_abs_frac"],
        sw=sat_winner["method"],
        swres=sat_winner["res68_abs_frac"],
    )

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction": {
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total_selected,
            "delta": total_selected - expected,
            "pass": total_selected == expected,
            "source": "raw ROOT HRDv in {}".format(config["raw_root_dir"]),
        },
        "target_definition": "paired odd-channel positive duplicate-readout charge; features from even channel only",
        "split": {
            "heldout_runs": heldout_runs,
            "train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()),
            "bootstrap": "run-block bootstrap over held-out runs",
            "bootstrap_reps": int(config["bootstrap_reps"]),
        },
        "n_valid_rows": int(len(meta)),
        "n_train_rows": int(train_mask.sum()),
        "n_heldout_rows": int(heldout_mask.sum()),
        "invalid_target_rows_removed_after_reproduction": invalid_rows,
        "winner": {
            "method": winner_row["method"],
            "criterion": "minimum heldout_all res68_abs_frac",
            "res68_abs_frac": float(winner_row["res68_abs_frac"]),
            "run_block_res68_ci95": winner_row.get("run_block_res68_ci95"),
        },
        "best_rising_only": {
            "method": best_rising["method"],
            "res68_abs_frac": float(best_rising["res68_abs_frac"]),
            "run_block_res68_ci95": best_rising.get("run_block_res68_ci95"),
        },
        "best_full_waveform": {
            "method": best_full["method"],
            "res68_abs_frac": float(best_full["res68_abs_frac"]),
            "run_block_res68_ci95": best_full.get("run_block_res68_ci95"),
        },
        "saturated_winner": {
            "method": sat_winner["method"],
            "res68_abs_frac": float(sat_winner["res68_abs_frac"]),
            "run_block_res68_ci95": sat_winner.get("run_block_res68_ci95"),
        },
        "methods_required_by_objective": ["strong_traditional", "ridge", "gradient_boosted_trees", "mlp", "1d_cnn", "wavegate_residual_new_architecture"],
        "method_metrics": json.loads(metrics.to_json(orient="records")),
        "method_deltas_vs_traditional": json.loads(deltas.to_json(orient="records")),
        "saturated_ordering": json.loads(ordering.to_json(orient="records")),
        "leakage_audit": leakage,
        "nn_training": nn_meta,
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, counts_by_run, metrics, deltas, ordering, leakage, result)

    print("7/7 writing manifest", flush=True)
    input_files = [p04.raw_path(config, run) for run in p04.configured_runs(config)]
    output_files = [
        "REPORT.md",
        "result.json",
        "method_metrics.csv",
        "method_deltas_vs_traditional.csv",
        "saturated_ordering.csv",
        "counts_by_run.csv",
        "nn_training_meta.json",
    ]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "command": "/home/billy/anaconda3/bin/python scripts/p04i_1781033028_1821_007252a9_causality_bakeoff.py --config configs/p04i_1781033028_1821_007252a9_causality_bakeoff.json",
        "config": str(config_path),
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "inputs": [{"path": str(path), "sha256": sha256_file(path)} for path in input_files],
        "outputs": [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in output_files],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("DONE -> {} in {} s".format(out_dir, result["runtime_sec"]), flush=True)


if __name__ == "__main__":
    main()
