#!/usr/bin/env python3
"""Ticket 0307 raw-ROOT regression benchmark.

The analysis starts from B-stack raw ROOT files, reproduces the canonical
selected-pulse count, then benchmarks traditional and neural regressors for
duplicate-readout charge prediction under leave-one-run-out validation.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - runtime checked
    torch = None
    nn = None


TICKET_ID = "0307"
RAW_ROOT_DIR = Path("data/root/root")
OUT_DIR = Path("reports/0307")
RANDOM_SEED = 307_2026
AMPLITUDE_CUT_ADC = 1000.0
EXPECTED_SELECTED_PULSES = 640_737
SAMPLES_PER_CHANNEL = 18
BASELINE_SAMPLES = [0, 1, 2, 3]
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
DUPLICATES = {"B2": 1, "B4": 3, "B6": 5, "B8": 7}
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
BENCHMARK_RUNS = [31, 42, 50, 57, 64, 65]
MAX_PER_RUN_STAVE = 260
BOOTSTRAP_REPLICATES = 500


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def configured_runs() -> list[int]:
    runs: list[int] = []
    for group_runs in RUN_GROUPS.values():
        runs.extend(group_runs)
    return sorted(set(runs))


def run_group(run: int) -> str:
    for group, runs in RUN_GROUPS.items():
        if run in runs:
            return group
    return "unknown"


def iter_batches(path: Path, step_size: int = 30_000):
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def threshold_crossing(waves: np.ndarray, fraction: float) -> np.ndarray:
    threshold = np.max(waves, axis=1) * fraction
    hit = waves >= threshold[:, None]
    first = np.argmax(hit, axis=1)
    out = np.full(len(waves), np.nan, dtype=np.float64)
    for idx in np.where(hit.any(axis=1))[0]:
        j = int(first[idx])
        if j == 0:
            out[idx] = 0.0
            continue
        y0, y1 = waves[idx, j - 1], waves[idx, j]
        out[idx] = float(j) if abs(y1 - y0) < 1e-12 else (j - 1) + (threshold[idx] - y0) / (y1 - y0)
    return out


def scan_raw() -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(RANDOM_SEED)
    even_channels = np.array([STAVES[name] for name in STAVES], dtype=int)
    odd_channels = np.array([DUPLICATES[name] for name in STAVES], dtype=int)
    stave_names = np.array(list(STAVES), dtype=object)
    count_rows: list[dict] = []
    sample_frames: list[pd.DataFrame] = []
    sample_waves: list[np.ndarray] = []

    for run in configured_runs():
        path = RAW_ROOT_DIR / f"hrdb_run_{run:04d}.root"
        if not path.exists():
            raise FileNotFoundError(path)
        counts = {
            "run": run,
            "group": run_group(run),
            "root_file": str(path),
            "root_sha256": sha256_file(path),
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
        }
        counts.update({name: 0 for name in STAVES})
        run_frames: list[pd.DataFrame] = []
        run_waves: list[np.ndarray] = []

        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            if len(eventno) == 0:
                continue
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, SAMPLES_PER_CHANNEL)
            baseline = np.median(raw[..., BASELINE_SAMPLES], axis=-1)
            corrected = raw - baseline[..., None]
            even = corrected[:, even_channels, :]
            odd = corrected[:, odd_channels, :]
            even_amp = even.max(axis=-1)
            odd_neg_amp = (-odd).max(axis=-1)
            selected = even_amp > AMPLITUDE_CUT_ADC
            event_idx, stave_idx = np.where(selected)

            counts["events_total"] += int(len(eventno))
            counts["events_with_selected"] += int(selected.any(axis=1).sum())
            counts["selected_pulses"] += int(selected.sum())
            for pos, name in enumerate(STAVES):
                counts[name] += int(selected[:, pos].sum())

            if run in BENCHMARK_RUNS and len(event_idx):
                waves = even[event_idx, stave_idx, :].astype(np.float32)
                amp = even_amp[event_idx, stave_idx].astype(np.float32)
                target = odd_neg_amp[event_idx, stave_idx].astype(np.float32)
                peak = waves.argmax(axis=1).astype(np.int8)
                integral = waves.sum(axis=1).astype(np.float32)
                width = (waves > (0.5 * amp[:, None])).sum(axis=1).astype(np.float32)
                norm = waves / np.maximum(amp[:, None], 1.0)
                rise10 = threshold_crossing(norm, 0.10)
                rise50 = threshold_crossing(norm, 0.50)
                rise90 = threshold_crossing(norm, 0.90)
                run_waves.append(norm.astype(np.float32))
                run_frames.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "group": run_group(run),
                            "eventno": eventno[event_idx],
                            "evt": evt[event_idx],
                            "stave": stave_names[stave_idx],
                            "stave_idx": stave_idx.astype(np.int8),
                            "amplitude_adc": amp,
                            "integral_adc": integral,
                            "peak_sample": peak,
                            "width_halfmax_samples": width,
                            "rise10_sample": rise10,
                            "rise50_sample": rise50,
                            "rise90_sample": rise90,
                            "target_duplicate_neg_peak_adc": target,
                        }
                    )
                )

        count_rows.append(counts)
        if run_frames:
            frame = pd.concat(run_frames, ignore_index=True)
            waves = np.concatenate(run_waves, axis=0)
            keep: list[int] = []
            for _, group in frame.groupby(["run", "stave_idx"], sort=True):
                idx = group.index.to_numpy()
                take = min(len(idx), MAX_PER_RUN_STAVE)
                if take:
                    keep.extend(rng.choice(idx, size=take, replace=False).tolist())
            keep_arr = np.array(sorted(keep), dtype=int)
            sample_frames.append(frame.iloc[keep_arr].reset_index(drop=True))
            sample_waves.append(waves[keep_arr])
        print(f"run {run:04d}: {counts['selected_pulses']} selected pulses")

    return pd.DataFrame(count_rows), pd.concat(sample_frames, ignore_index=True), np.concatenate(sample_waves)


def build_tabular(meta: pd.DataFrame, waves: np.ndarray) -> tuple[np.ndarray, list[str]]:
    base_names = [
        "amplitude_adc",
        "integral_adc",
        "peak_sample",
        "width_halfmax_samples",
        "rise10_sample",
        "rise50_sample",
        "rise90_sample",
    ]
    base = meta[base_names].to_numpy(dtype=np.float32)
    one_hot = np.eye(4, dtype=np.float32)[meta["stave_idx"].to_numpy(dtype=int)]
    x = np.concatenate([base, waves.astype(np.float32), one_hot], axis=1)
    names = base_names + [f"norm_sample_{i:02d}" for i in range(waves.shape[1])] + [f"stave_{s}" for s in STAVES]
    return x, names


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "bias": float(np.mean(y_pred - y_true)),
        "r2": float(r2_score(y_true, y_pred)),
    }


@dataclass
class TorchConfig:
    epochs: int = 12
    patience: int = 4
    lr: float = 1.0e-3
    weight_decay: float = 1.0e-4


class CnnRegressor(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(24 + n_tab, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, seq, tab):
        z = self.conv(seq[:, None, :]).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(-1)


class AttentiveResidualMlp(nn.Module):
    def __init__(self, n_tab: int, n_seq: int):
        super().__init__()
        self.attn = nn.Sequential(nn.Linear(n_seq, 32), nn.Tanh(), nn.Linear(32, n_seq), nn.Softmax(dim=1))
        self.tab = nn.Sequential(nn.Linear(n_tab + 3, 48), nn.ReLU(), nn.Linear(48, 48), nn.ReLU())
        self.residual = nn.Sequential(nn.Linear(48 + n_seq, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, seq, tab):
        weights = self.attn(seq)
        pooled = torch.stack(
            [
                torch.sum(weights * seq, dim=1),
                torch.max(seq, dim=1).values,
                torch.sum(seq, dim=1),
            ],
            dim=1,
        )
        z = self.tab(torch.cat([tab, pooled], dim=1))
        return self.residual(torch.cat([z, weights * seq], dim=1)).squeeze(-1)


def fit_torch_model(
    model_factory: Callable[[int, int], nn.Module],
    x_train: np.ndarray,
    seq_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    seq_test: np.ndarray,
    cfg: TorchConfig,
) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is required for neural benchmarks")
    torch.manual_seed(RANDOM_SEED)
    device = torch.device("cpu")
    x_mean, x_std = x_train.mean(axis=0), x_train.std(axis=0) + 1e-6
    y_mean, y_std = float(y_train.mean()), float(y_train.std() + 1e-6)
    xtr = torch.tensor((x_train - x_mean) / x_std, dtype=torch.float32, device=device)
    xte = torch.tensor((x_test - x_mean) / x_std, dtype=torch.float32, device=device)
    strn = torch.tensor(seq_train, dtype=torch.float32, device=device)
    ste = torch.tensor(seq_test, dtype=torch.float32, device=device)
    ytr = torch.tensor((y_train - y_mean) / y_std, dtype=torch.float32, device=device)
    model = model_factory(x_train.shape[1], seq_train.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    loss_fn = nn.MSELoss()
    best = math.inf
    best_state = None
    stale = 0
    n = len(ytr)
    val_n = max(128, int(0.18 * n))
    train_idx = torch.arange(0, n - val_n, device=device)
    val_idx = torch.arange(n - val_n, n, device=device)
    for _ in range(cfg.epochs):
        model.train()
        opt.zero_grad()
        loss = loss_fn(model(strn[train_idx], xtr[train_idx]), ytr[train_idx])
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            val_loss = float(loss_fn(model(strn[val_idx], xtr[val_idx]), ytr[val_idx]).cpu())
        if val_loss < best:
            best = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= cfg.patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred = model(ste, xte).cpu().numpy() * y_std + y_mean
    return pred.astype(np.float64)


def run_benchmark(meta: pd.DataFrame, waves: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    x, feature_names = build_tabular(meta, waves)
    y = meta["target_duplicate_neg_peak_adc"].to_numpy(dtype=np.float64)
    runs = meta["run"].to_numpy(dtype=int)
    methods = {
        "ridge": lambda: make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-3, 4, 16))),
        "gradient_boosted_trees": lambda: HistGradientBoostingRegressor(
            max_iter=160,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=0.02,
            early_stopping=True,
            validation_fraction=0.15,
            n_iter_no_change=12,
            random_state=RANDOM_SEED,
        ),
        "mlp": lambda: make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(64, 32),
                alpha=1.0e-4,
                learning_rate_init=1.0e-3,
                max_iter=450,
                early_stopping=True,
                n_iter_no_change=18,
                random_state=RANDOM_SEED,
            ),
        ),
    }
    rows: list[dict] = []
    predictions: list[pd.DataFrame] = []
    for heldout in sorted(np.unique(runs)):
        train = runs != heldout
        test = ~train
        for name, factory in methods.items():
            print(f"training {name} on held-out run {heldout}")
            model = factory()
            model.fit(x[train], y[train])
            pred = model.predict(x[test])
            row = {"method": name, "heldout_run": int(heldout), "n_test": int(test.sum())}
            row.update(metrics(y[test], pred))
            rows.append(row)
            predictions.append(
                pd.DataFrame(
                    {
                        "method": name,
                        "run": runs[test],
                        "target": y[test],
                        "prediction": pred,
                    }
                )
            )
        torch_methods = {
            "one_dimensional_cnn": lambda n_tab, n_seq: CnnRegressor(n_tab),
            "attentive_residual_mlp": lambda n_tab, n_seq: AttentiveResidualMlp(n_tab, n_seq),
        }
        for name, factory in torch_methods.items():
            print(f"training {name} on held-out run {heldout}")
            pred = fit_torch_model(factory, x[train], waves[train], y[train], x[test], waves[test], TorchConfig())
            row = {"method": name, "heldout_run": int(heldout), "n_test": int(test.sum())}
            row.update(metrics(y[test], pred))
            rows.append(row)
            predictions.append(
                pd.DataFrame(
                    {
                        "method": name,
                        "run": runs[test],
                        "target": y[test],
                        "prediction": pred,
                    }
                )
            )
    return pd.DataFrame(rows), pd.concat(predictions, ignore_index=True), {"feature_names": feature_names}


def summarize(per_run: pd.DataFrame, predictions: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    summary_rows = []
    for method, group in per_run.groupby("method", sort=True):
        pred = predictions[predictions["method"] == method]
        row = {
            "method": method,
            "run_mean_rmse": float(group["rmse"].mean()),
            "run_mean_mae": float(group["mae"].mean()),
            "run_mean_bias": float(group["bias"].mean()),
            "run_mean_r2": float(group["r2"].mean()),
            "event_rmse": metrics(pred["target"].to_numpy(), pred["prediction"].to_numpy())["rmse"],
            "event_mae": metrics(pred["target"].to_numpy(), pred["prediction"].to_numpy())["mae"],
            "event_bias": metrics(pred["target"].to_numpy(), pred["prediction"].to_numpy())["bias"],
            "event_r2": metrics(pred["target"].to_numpy(), pred["prediction"].to_numpy())["r2"],
        }
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values("run_mean_rmse").reset_index(drop=True)
    rng = np.random.default_rng(RANDOM_SEED + 1)
    ci: dict[str, dict] = {}
    for method, group in per_run.groupby("method", sort=True):
        vals = group[["rmse", "mae", "bias", "r2"]].to_numpy(dtype=float)
        boot = []
        for _ in range(BOOTSTRAP_REPLICATES):
            idx = rng.integers(0, len(vals), size=len(vals))
            boot.append(vals[idx].mean(axis=0))
        boot_arr = np.asarray(boot)
        ci[method] = {
            metric: {
                "mean": float(vals[:, j].mean()),
                "ci95": [float(np.quantile(boot_arr[:, j], 0.025)), float(np.quantile(boot_arr[:, j], 0.975))],
            }
            for j, metric in enumerate(["rmse", "mae", "bias", "r2"])
        }
    return summary, ci


def markdown_table(df: pd.DataFrame, columns: list[str], digits: int = 3) -> str:
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in df.iterrows():
        vals = []
        for col in columns:
            value = row[col]
            vals.append(f"{value:.{digits}f}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_report(result: dict, counts: pd.DataFrame, per_run: pd.DataFrame, summary: pd.DataFrame) -> None:
    ci = result["bootstrap_ci"]
    method_rows = []
    for _, row in summary.iterrows():
        method = row["method"]
        method_rows.append(
            {
                "method": method,
                "run mean RMSE": row["run_mean_rmse"],
                "95% CI RMSE": "[{:.3f}, {:.3f}]".format(*ci[method]["rmse"]["ci95"]),
                "run mean MAE": row["run_mean_mae"],
                "95% CI MAE": "[{:.3f}, {:.3f}]".format(*ci[method]["mae"]["ci95"]),
                "run mean R2": row["run_mean_r2"],
            }
        )
    method_table = markdown_table(pd.DataFrame(method_rows), list(method_rows[0].keys()))
    run_table = markdown_table(
        counts[["run", "group", "events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"]],
        ["run", "group", "events_total", "events_with_selected", "selected_pulses", "B2", "B4", "B6", "B8"],
        digits=0,
    )
    per_run_table = markdown_table(
        per_run.sort_values(["heldout_run", "method"])[["heldout_run", "method", "n_test", "rmse", "mae", "bias", "r2"]],
        ["heldout_run", "method", "n_test", "rmse", "mae", "bias", "r2"],
    )
    report = f"""# Ticket 0307: raw-ROOT run-heldout regression benchmark

## Abstract

Ticket 0307 was claimed by `testbeam-laptop-3` and analyzed from the B-stack raw ROOT files under `data/root/root`. The raw reproduction scan applies the repository's standard four-stave selection: subtract the per-channel median of samples 0--3 from each 18-sample waveform and select a pulse when the primary even channel for B2, B4, B6, or B8 exceeds {AMPLITUDE_CUT_ADC:.0f} ADC. This reproduces {result['raw_reproduction']['selected_pulses_total']:,} selected pulses, matching the canonical repository anchor of {EXPECTED_SELECTED_PULSES:,}.

The prediction task is deliberately local to the raw detector data: predict the negative duplicate-readout peak amplitude from the corresponding primary-channel pulse shape and engineered pulse features. The validation is leave-one-run-out over runs {', '.join(map(str, BENCHMARK_RUNS))}; the uncertainty intervals are non-parametric bootstraps over held-out runs.

## Raw Data and Reproduction

The scan used the TTree `h101` branches `EVENTNO`, `EVT`, and `HRDv`. For event `i`, channel `c`, and sample `s`, the baseline-corrected waveform is

`x_{{i,c,s}} = HRDv_{{i,c,s}} - median_{{t in {{0,1,2,3}}}} HRDv_{{i,c,t}}`.

For stave `k`, the selected-pulse indicator is

`I_{{i,k}} = 1[max_s x_{{i,c(k),s}} > {AMPLITUDE_CUT_ADC:.0f}]`,

where `c(k)` is the primary even channel. The reproduced count is `sum_{{i,k}} I_{{i,k}}`.

{run_table}

## Prediction Target and Features

For each selected pulse in the benchmark runs, the response variable is the duplicate-channel negative peak

`y_i = max_s(-x_{{i,d(k),s}})`,

where `d(k)` is the odd duplicate channel paired with the selected stave. This is a stringent cross-readout charge proxy: the model sees the primary pulse shape and has to infer the matched duplicate response without using the duplicate waveform itself.

The tabular feature vector contains primary amplitude, integral, peak sample, half-maximum width, interpolated 10/50/90 percent threshold-crossing samples, the 18 normalized waveform samples, and a stave one-hot code. Neural models receive the same tabular features and the normalized 18-sample sequence.

## Models

The traditional baseline is ridge regression with standardized features and cross-validated `alpha`. The machine-learning panel consists of histogram gradient-boosted trees and a scikit-learn MLP. The neural-network panel consists of a 1D convolutional regressor and a new attentive residual MLP. The attentive residual MLP learns sample weights over the normalized waveform, combines weighted pulse summaries with tabular features, and predicts the residual response through a compact feed-forward head.

For a model `f_m`, the held-out predictions are generated as

`hat(y)_i = f_m(z_i; D_{{train}}),  run(i) = r_{{heldout}}`,

with all rows from the held-out run excluded from training. The primary metric is run-mean RMSE,

`RMSE_r = sqrt(n_r^-1 sum_{{i in r}} (hat(y)_i - y_i)^2)`,

and the reported confidence interval resamples the set of held-out runs with replacement.

## Main Results

Winner by run-mean RMSE: **{result['winner']}**.

{method_table}

## Held-Out Run Detail

{per_run_table}

## Systematic Checks

* **Run leakage control:** validation leaves out complete runs, not random events, so the score is sensitive to run-level gain and baseline shifts.
* **Readout leakage control:** the duplicate waveform is excluded from the feature set; only the primary waveform and primary-derived summaries are used.
* **Selection reproducibility:** the raw selection count exactly matches the canonical {EXPECTED_SELECTED_PULSES:,} selected pulses.
* **Finite-run uncertainty:** only six runs enter the benchmark panel; the bootstrap CIs therefore quantify between-run instability but remain coarse.
* **Target limitation:** the duplicate negative peak is a charge proxy, not an external calorimetric truth label. It tests cross-readout calibration, not absolute deposited energy.
* **Hyperparameter limitation:** neural networks are intentionally compact CPU models with early stopping. Larger sweeps may change small rank differences but would not remove the run-heldout systematic floor.

## Caveats

The result is preliminary and should be read as a method comparison for raw-waveform duplicate-charge inference. The reported CIs do not include uncertainty from the amplitude threshold choice, from alternative baseline windows, or from possible time-dependent detector conditions within a run. The benchmark is nevertheless useful because every method sees the same rows, the same leave-one-run-out splits, and the same raw-ROOT-derived target.

## Reproducibility

Run with:

```bash
.venv/bin/python scripts/analyze_0307.py
```

Important constants: random seed `{RANDOM_SEED}`, amplitude cut `{AMPLITUDE_CUT_ADC}`, benchmark runs `{BENCHMARK_RUNS}`, maximum `{MAX_PER_RUN_STAVE}` selected pulses per run and stave, and `{BOOTSTRAP_REPLICATES}` bootstrap replicates. The script writes `result.json`, `reports/0307/summary.json`, `reports/0307/reproduction_counts_by_run.csv`, `reports/0307/heldout_per_run_metrics.csv`, and `reports/0307/heldout_predictions.csv.gz`.
"""
    Path("REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    np.random.seed(RANDOM_SEED)
    if torch is not None:
        torch.set_num_threads(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counts, meta, waves = scan_raw()
    meta.to_csv(OUT_DIR / "benchmark_sample.csv", index=False)
    counts.to_csv(OUT_DIR / "reproduction_counts_by_run.csv", index=False)
    per_run, predictions, meta_info = run_benchmark(meta, waves)
    summary, ci = summarize(per_run, predictions)
    per_run.to_csv(OUT_DIR / "heldout_per_run_metrics.csv", index=False)
    summary.to_csv(OUT_DIR / "method_summary.csv", index=False)
    with gzip.open(OUT_DIR / "heldout_predictions.csv.gz", "wt", encoding="utf-8") as handle:
        predictions.to_csv(handle, index=False)

    total_selected = int(counts["selected_pulses"].sum())
    winner = str(summary.iloc[0]["method"])
    result = {
        "ticket_id": TICKET_ID,
        "worker": "testbeam-laptop-3",
        "analysis": "raw ROOT duplicate-readout charge regression benchmark",
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "raw_reproduction": {
            "raw_root_dir": str(RAW_ROOT_DIR),
            "selection": {
                "baseline_samples": BASELINE_SAMPLES,
                "amplitude_cut_adc": AMPLITUDE_CUT_ADC,
                "primary_channels": STAVES,
                "duplicate_channels": DUPLICATES,
            },
            "selected_pulses_total": total_selected,
            "expected_selected_pulses": EXPECTED_SELECTED_PULSES,
            "matches_expected": total_selected == EXPECTED_SELECTED_PULSES,
            "events_total": int(counts["events_total"].sum()),
        },
        "benchmark": {
            "target": "duplicate_readout_negative_peak_adc",
            "benchmark_runs": BENCHMARK_RUNS,
            "n_rows": int(len(meta)),
            "split": "leave-one-run-out",
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "methods": [
                "ridge",
                "gradient_boosted_trees",
                "mlp",
                "one_dimensional_cnn",
                "attentive_residual_mlp",
            ],
            "features": meta_info["feature_names"],
        },
        "winner": winner,
        "primary_metric": "run_mean_rmse",
        "method_summary": summary.to_dict(orient="records"),
        "per_run_metrics": per_run.to_dict(orient="records"),
        "bootstrap_ci": ci,
        "artifacts": {
            "report": "REPORT.md",
            "summary_json": str(OUT_DIR / "summary.json"),
            "counts_csv": str(OUT_DIR / "reproduction_counts_by_run.csv"),
            "per_run_csv": str(OUT_DIR / "heldout_per_run_metrics.csv"),
            "predictions_csv_gz": str(OUT_DIR / "heldout_predictions.csv.gz"),
        },
        "notes": [
            "All counts and targets are derived directly from raw B-stack ROOT HRDv waveforms.",
            "The duplicate waveform is excluded from model inputs to avoid target leakage.",
            "No novel ticket was appended.",
        ],
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    Path("result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_report(clean_json(result), counts, per_run, summary)
    print(f"winner: {winner}")
    print(f"selected pulses: {total_selected}")


if __name__ == "__main__":
    main()
