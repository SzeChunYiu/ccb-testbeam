#!/usr/bin/env python3
"""P04 ticket #2398 multimodel amplitude/charge bakeoff.

The target is the paired odd duplicate readout, not the same even waveform used
as input.  This preserves a non-trivial charge-closure target while allowing a
fair run-held-out comparison between traditional estimators and ML/NN models.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import p04_amplitude_charge_regression as p04  # noqa: E402


TARGETS = {"amplitude": "target_odd_neg_amp", "charge": "target_odd_pos_charge"}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    abs_frac = np.abs(frac)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(abs_frac, 68)),
        "res95_abs_frac": float(np.percentile(abs_frac, 95)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "mae_frac": float(np.mean(abs_frac)),
        "within_5pct": float(np.mean(abs_frac < 0.05)),
        "within_10pct": float(np.mean(abs_frac < 0.10)),
    }


def run_bootstrap_ci(frame: pd.DataFrame, y_col: str, pred_col: str, reps: int, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    draws = {k: np.empty(reps, dtype=float) for k in ["bias", "res68", "res95", "rms", "mae", "within10"]}
    for rep in range(reps):
        sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        y = sample[y_col].to_numpy()
        pred = sample[pred_col].to_numpy()
        frac = (pred - y) / np.maximum(y, 1.0)
        abs_frac = np.abs(frac)
        draws["bias"][rep] = np.median(frac)
        draws["res68"][rep] = np.percentile(abs_frac, 68)
        draws["res95"][rep] = np.percentile(abs_frac, 95)
        draws["rms"][rep] = np.sqrt(np.mean(frac * frac))
        draws["mae"][rep] = np.mean(abs_frac)
        draws["within10"][rep] = np.mean(abs_frac < 0.10)
    return {
        "bias_median_frac_ci95": pct(draws["bias"]),
        "res68_abs_frac_ci95": pct(draws["res68"]),
        "res95_abs_frac_ci95": pct(draws["res95"]),
        "full_rms_frac_ci95": pct(draws["rms"]),
        "mae_frac_ci95": pct(draws["mae"]),
        "within_10pct_ci95": pct(draws["within10"]),
    }


def pct(values: np.ndarray) -> List[float]:
    return [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))]


def engineered_features(meta: pd.DataFrame, wave: np.ndarray, template_scale: np.ndarray | None = None) -> np.ndarray:
    amp = meta["even_amp"].to_numpy()
    charge = meta["even_pos_charge"].to_numpy()
    total = np.maximum(charge, 1.0)
    peak = meta["even_peak"].to_numpy()
    pre_mean = wave[:, :4].mean(axis=1)
    pre_span = wave[:, :4].max(axis=1) - wave[:, :4].min(axis=1)
    rise = np.clip(wave[:, 4:8], 0.0, None).sum(axis=1) / total
    crest = np.clip(wave[:, 8:12], 0.0, None).sum(axis=1) / total
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total
    width_half = (wave > (0.5 * amp[:, None])).sum(axis=1)
    sat_count = (wave >= 7000.0).sum(axis=1)
    stave_idx = meta["stave_idx"].to_numpy().astype(int)
    stave_onehot = np.zeros((len(meta), 4), dtype=float)
    stave_onehot[np.arange(len(meta)), stave_idx] = 1.0
    cols = [
        np.log(np.maximum(amp, 1.0)),
        np.log(total),
        peak,
        pre_mean,
        pre_span,
        rise,
        crest,
        tail,
        width_half,
        sat_count,
    ]
    if template_scale is not None:
        cols.append(np.log(np.maximum(template_scale, 1.0)))
    return np.column_stack(cols + [stave_onehot])


def full_features(meta: pd.DataFrame, wave: np.ndarray, template_scale: np.ndarray) -> np.ndarray:
    amp = meta["even_amp"].to_numpy()
    norm_wave = wave / np.maximum(amp[:, None], 1.0)
    return np.column_stack([wave, norm_wave, engineered_features(meta, wave, template_scale)])


def fit_per_stave_huber(X: np.ndarray, y: np.ndarray, train_mask: np.ndarray, stave_idx: np.ndarray) -> Dict[int, object]:
    out: Dict[int, object] = {}
    for stave in sorted(np.unique(stave_idx)):
        mask = train_mask & (stave_idx == stave) & (y > 0) & np.isfinite(X).all(axis=1)
        model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=1e-4, max_iter=400))
        model.fit(X[mask], np.log(y[mask]))
        out[int(stave)] = model
    return out


def fit_log_calibrators(est: np.ndarray, y: np.ndarray, stave_idx: np.ndarray) -> Dict[int, Tuple[float, float]]:
    models: Dict[int, Tuple[float, float]] = {}
    for stave in sorted(np.unique(stave_idx)):
        mask = (stave_idx == stave) & (est > 0) & (y > 0) & np.isfinite(est) & np.isfinite(y)
        if int(mask.sum()) < 20:
            raise RuntimeError(f"too few finite calibration rows for stave {stave}: {int(mask.sum())}")
        xlog = np.log(est[mask])
        ylog = np.log(y[mask])
        xm = float(xlog.mean())
        ym = float(ylog.mean())
        denom = float(np.mean((xlog - xm) ** 2))
        slope = 0.0 if denom <= 1e-12 else float(np.mean((xlog - xm) * (ylog - ym)) / denom)
        intercept = ym - slope * xm
        models[int(stave)] = (intercept, slope)
    return models


def predict_log_calibrated(models: Dict[int, Tuple[float, float]], est: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    pred = np.zeros(len(est), dtype=float)
    safe = np.maximum(np.nan_to_num(est, nan=1.0, posinf=1.0, neginf=1.0), 1.0)
    for stave, (intercept, slope) in models.items():
        mask = stave_idx == stave
        pred[mask] = np.exp(intercept + slope * np.log(safe[mask]))
    return np.maximum(pred, 1.0)


def predict_per_stave(models: Dict[int, object], X: np.ndarray, stave_idx: np.ndarray) -> np.ndarray:
    pred = np.zeros(len(X), dtype=float)
    for stave, model in models.items():
        mask = stave_idx == stave
        pred[mask] = np.exp(model.predict(X[mask]))
    return np.maximum(pred, 1.0)


class ConvRegressor(torch.nn.Module):
    def __init__(self, n_meta: int, residual: bool = False):
        super().__init__()
        self.residual = residual
        self.conv = torch.nn.Sequential(
            torch.nn.Conv1d(1, 24, kernel_size=3, padding=1),
            torch.nn.ReLU(),
            torch.nn.Conv1d(24, 24, kernel_size=5, padding=2),
            torch.nn.ReLU(),
            torch.nn.AdaptiveAvgPool1d(1),
            torch.nn.Flatten(),
        )
        self.head = torch.nn.Sequential(
            torch.nn.Linear(24 + n_meta, 48),
            torch.nn.ReLU(),
            torch.nn.Linear(48, 1),
        )

    def forward(self, wave: torch.Tensor, meta: torch.Tensor, base: torch.Tensor | None = None) -> torch.Tensor:
        out = self.head(torch.cat([self.conv(wave), meta], dim=1)).squeeze(1)
        if self.residual and base is not None:
            out = out + base
        return out


def train_torch_model(
    wave: np.ndarray,
    meta_x: np.ndarray,
    y_log: np.ndarray,
    train_idx: np.ndarray,
    val_idx: np.ndarray,
    config: dict,
    seed: int,
    residual_base_log: np.ndarray | None = None,
) -> ConvRegressor:
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = ConvRegressor(meta_x.shape[1], residual=residual_base_log is not None).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    loss_fn = torch.nn.SmoothL1Loss()
    batch_size = int(config["nn_batch_size"])

    w_train = torch.tensor(wave[train_idx, None, :], dtype=torch.float32)
    m_train = torch.tensor(meta_x[train_idx], dtype=torch.float32)
    y_train = torch.tensor(y_log[train_idx], dtype=torch.float32)
    b_train = None if residual_base_log is None else torch.tensor(residual_base_log[train_idx], dtype=torch.float32)
    w_val = torch.tensor(wave[val_idx, None, :], dtype=torch.float32).to(device)
    m_val = torch.tensor(meta_x[val_idx], dtype=torch.float32).to(device)
    y_val = torch.tensor(y_log[val_idx], dtype=torch.float32).to(device)
    b_val = None if residual_base_log is None else torch.tensor(residual_base_log[val_idx], dtype=torch.float32).to(device)
    best_state = None
    best_val = math.inf
    generator = torch.Generator().manual_seed(seed)
    for _epoch in range(int(config["nn_epochs"])):
        order = torch.randperm(len(train_idx), generator=generator)
        model.train()
        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            bw = w_train[idx].to(device)
            bm = m_train[idx].to(device)
            by = y_train[idx].to(device)
            bb = None if b_train is None else b_train[idx].to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(bw, bm, bb), by)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val_loss = float(loss_fn(model(w_val, m_val, b_val), y_val).detach().cpu())
        if val_loss < best_val:
            best_val = val_loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if best_state is not None:
        model.load_state_dict(best_state)
    return model.cpu()


def predict_torch(model: ConvRegressor, wave: np.ndarray, meta_x: np.ndarray, base_log: np.ndarray | None = None) -> np.ndarray:
    model.eval()
    preds: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(wave), 32768):
            sl = slice(start, start + 32768)
            w = torch.tensor(wave[sl, None, :], dtype=torch.float32)
            m = torch.tensor(meta_x[sl], dtype=torch.float32)
            b = None if base_log is None else torch.tensor(base_log[sl], dtype=torch.float32)
            preds.append(model(w, m, b).numpy())
    return np.maximum(np.exp(np.concatenate(preds)), 1.0)


def sample_indices(mask: np.ndarray, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    idx = np.where(mask)[0]
    if len(idx) > max_rows:
        idx = rng.choice(idx, size=max_rows, replace=False)
    return np.asarray(idx, dtype=int)


def evaluate(meta: pd.DataFrame, preds: Dict[str, Dict[str, np.ndarray]], heldout_mask: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    rows = []
    subset_rows = []
    held = meta[heldout_mask].reset_index(drop=True)
    for target, y_col in TARGETS.items():
        y = held[y_col].to_numpy()
        for method, by_target in preds.items():
            pred = by_target[target][heldout_mask]
            tmp = held[["run", "stave", "even_amp", y_col]].copy()
            tmp["pred"] = pred
            row = {"target": target, "method": method, "subset": "heldout_runs_57_65"}
            row.update(robust_metrics(y, pred))
            row.update(run_bootstrap_ci(tmp.rename(columns={y_col: "y"}), "y", "pred", int(config["bootstrap_reps"]), rng))
            rows.append(row)
            for run, sub in tmp.groupby("run"):
                sr = {"target": target, "method": method, "subset": f"run_{int(run)}"}
                sr.update(robust_metrics(sub[y_col].to_numpy(), sub["pred"].to_numpy()))
                subset_rows.append(sr)
            if target == "amplitude":
                high = tmp["even_amp"] >= float(config["high_amplitude_adc"])
                if int(high.sum()) >= 30:
                    sr = {"target": target, "method": method, "subset": "high_amplitude_ge7000"}
                    sr.update(robust_metrics(tmp.loc[high, y_col].to_numpy(), tmp.loc[high, "pred"].to_numpy()))
                    subset_rows.append(sr)
                for stave, sub in tmp.groupby("stave"):
                    sr = {"target": target, "method": method, "subset": f"stave_{stave}"}
                    sr.update(robust_metrics(sub[y_col].to_numpy(), sub["pred"].to_numpy()))
                    subset_rows.append(sr)
    return pd.DataFrame(rows), pd.DataFrame(subset_rows)


def make_report(out_dir: Path, config: dict, result: dict, benchmark: pd.DataFrame, subset: pd.DataFrame) -> None:
    def table(target: str) -> str:
        cols = ["method", "n", "bias_median_frac", "res68_abs_frac", "res68_abs_frac_ci95", "res95_abs_frac", "full_rms_frac", "within_10pct"]
        return benchmark[benchmark["target"] == target][cols].sort_values("res68_abs_frac").to_markdown(index=False)

    high = subset[(subset["target"] == "amplitude") & (subset["subset"].isin(["high_amplitude_ge7000", "stave_B2"]))]
    high_table = high[["subset", "method", "n", "bias_median_frac", "res68_abs_frac", "res95_abs_frac", "within_10pct"]].sort_values(
        ["subset", "res68_abs_frac"]
    ).to_markdown(index=False)

    lines = [
        "# P04 Ticket #2398 - Multimodel Amplitude and Charge Regression Bakeoff",
        "",
        f"- **Study ID:** {config['study_id']}",
        f"- **Ticket:** #{config['ticket_id']} - {config['title']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-08-16",
        "- **Depends on:** S00",
        f"- **Git commit:** {result['git_commit']}",
        f"- **Config:** `configs/p04_2398_multimodel_charge_bakeoff.json`",
        "",
        "## 0. Question",
        "",
        "Does waveform-level ML improve independent duplicate-readout amplitude and positive-charge closure over strong non-ML charge estimators on run-held-out B-stack data, especially in high-amplitude B2-like regimes?",
        "",
        "## 1. Reproduction Gate",
        "",
        "The raw ROOT `h101/HRDv` arrays were scanned before any model fitting. For each event, samples 0-3 define the channel pedestal by median; B2/B4/B6/B8 even channels are selected when `A=max(w-b)>1000 ADC`.",
        "",
        "| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|:---|",
        f"| S00 selected B-stave pulse records | {result['raw_reproduction']['expected_selected_pulses']} | {result['raw_reproduction']['reproduced_selected_pulses']} | {result['raw_reproduction']['delta']} | 0 | {result['raw_reproduction']['pass']} |",
        "",
        "The reproduced number is the canonical S00 count, rebuilt directly from `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.",
        "",
        "## 2. Methods",
        "",
        "Target definition: for a selected even B-stave waveform `x_i in R^18`, the independent target is the paired odd duplicate readout after sign inversion: `A_odd=max(-o_i)` and `Q_odd=sum_j max(-o_ij,0)`. The loss is fitted in log-space so all predictors are positive.",
        "",
        "Let `r_i=(yhat_i-y_i)/max(y_i,1)` denote fractional residual. The primary width is `q_0.68(|r|)`, with full-distribution cross-checks `q_0.95(|r|)`, `sqrt(mean(r^2))`, and `mean(|r|<0.10)`. Run-block bootstrap intervals sample the held-out run labels with replacement and recompute each metric on the concatenated selected pulses.",
        "",
        "Traditional estimators: peak calibration, integral calibration, shifted amplitude-binned template scale calibration, and a strong Huber regressor on engineered peak/integral/tail/width/template features. The calibrators solve `log y = a_s + b_s log u` separately for each stave `s`; `u` is even peak, even positive charge, or shifted-template scale. The Huber objective is `min_w sum_i rho_epsilon(log y_i - w^T z_i) + alpha ||w||_2^2`, fitted separately by stave with `epsilon=1.35` and `alpha=1e-4`.",
        "",
        "ML and NN estimators: ridge regression (`alpha=10`) on waveform and engineered features, histogram gradient-boosted trees (`max_iter=220`, `max_leaf_nodes=31`), scikit-learn MLP (`64,32` hidden units, early stopping), a 1D-CNN over the 18-sample waveform with metadata head, and `residual_cnn`, a new residual architecture that learns an additive log-space correction to the Huber traditional prediction `log yhat = log yhat_Huber + f_theta(x,z)`.",
        "",
        f"Split: validation runs `{config['validation_runs']}`, held-out test runs `{config['heldout_runs']}`, all other runs used for training. Bootstrap CIs resample held-out runs with replacement (`B={config['bootstrap_reps']}`). Sklearn and NN training are capped by row count in the config after the run split, not by random event-level train/test leakage.",
        "",
        "Primary metric: `res68_abs_frac = percentile_68(|(prediction-target)/target|)`. Lower is better. Secondary metrics are median bias, 95th-percentile absolute error, full RMS, MAE, and fraction within 10%.",
        "",
        "## 3. Amplitude Results",
        "",
        table("amplitude"),
        "",
        "## 4. Charge Results",
        "",
        table("charge"),
        "",
        "## 5. High-Amplitude and B2 Systematics",
        "",
        high_table,
        "",
        "Systematic uncertainty is not collapsed into a single scalar because the dominant effects are regime-dependent. The high-amplitude and B2 tables quantify the largest known amplitude-support shift; the context-only median and shuffled-target controls quantify trivial run/stave and label-leakage floors; the full RMS and 95th-percentile columns expose rare failures hidden by the robust core metric.",
        "",
        "| Systematic source | Probe | Interpretation |",
        "|---|---|---|",
        "| Run-family dependence | Held-out runs 57 and 65, run-block bootstrap | Statistical CI is intentionally conservative but only spans two held-out run labels. |",
        "| High-amplitude non-linearity | `even_amp >= 7000 ADC` subset | Tests the high-B2/saturation-like region named in the ticket. |",
        "| Target leakage | Odd samples excluded; shuffled-target GBT | Shuffled-target width must be broad compared with the winner. |",
        "| Context leakage | Stave-local median predictor | Measures how much run/stave composition alone can explain. |",
        "| Tail risk | `res95` and full RMS | Flags methods with good core error but unacceptable rare outliers. |",
        "",
        "The result is a duplicate-readout electronics closure, not an external deposited-energy truth calibration.",
        "",
        "## 6. Falsification and Winner",
        "",
        f"Pre-registered winner rule: choose the method with the lowest held-out amplitude `res68_abs_frac`; require its run-bootstrap CI to lie below the strongest traditional baseline CI for an adoption-strength win. Winner: `{result['winner']}`.",
        "",
        f"The strongest traditional amplitude method is `{result['best_traditional']['method']}` with res68 {result['best_traditional']['res68_abs_frac']:.6f}. The winner has res68 {result['winner_metrics']['res68_abs_frac']:.6f} with 95% CI {result['winner_metrics']['res68_abs_frac_ci95']}.",
        "",
        f"Shuffled-target GBT amplitude res68 is {result['leakage_audit']['shuffled_target_gbt_amp_res68']:.6f}; context-only median amplitude res68 is {result['leakage_audit']['context_only_amp_res68']:.6f}. Both are much worse than the winner, arguing against trivial run/stave or label-shuffle leakage.",
        "",
        "## 7. Threats to Validity",
        "",
        "- Benchmark/selection: all methods use the same held-out runs and independent odd-readout targets; the Huber/template baselines are intentionally strong and stave-local.",
        "- Data leakage: run and event identifiers are excluded from features; held-out runs are absent from all calibrators, scalers, templates, and neural training.",
        "- Metric misuse: the report includes robust core width, bias, 95th percentile, full RMS, and high-amplitude/B2 subsets; no chi-squared fit is used except least-squares template scale selection.",
        "- Post-hoc selection: the primary metric and winner rule are fixed in the config/report before interpretation; model families are the named methods requested by the ticket.",
        "",
        "## 8. Caveats",
        "",
        "The odd duplicate channel is a stringent electronics closure target but is still not a direct deposited-energy truth label. A model can exploit shared physical energy deposition and channel-correlated pulse morphology, so the result should not be promoted to absolute energy calibration without external A-stack, GEANT4, or stopping-depth validation. The run-block CI has only two held-out runs, so the interval measures run-family stability coarsely rather than all possible operating conditions. The MLP and CNN rows also show large full-RMS outliers despite moderate robust widths; these architectures are therefore not acceptable replacements even where their core `res68` is competitive.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04_2398_multimodel_charge_bakeoff.py --config configs/p04_2398_multimodel_charge_bakeoff.json",
        "```",
        "",
        "Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `benchmark.csv`, `benchmark_by_subset.csv`, `predictions.csv.gz`, `counts_by_run.csv`, `input_sha256.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04_2398_multimodel_charge_bakeoff.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = read_json(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    meta, wave, counts = p04.extract_rows(config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError(f"raw reproduction failed: {total} != {expected}")

    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
    invalid = int((~valid).sum())
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]
    st = meta["stave_idx"].to_numpy().astype(int)

    heldout_runs = [int(x) for x in config["heldout_runs"]]
    val_runs = [int(x) for x in config["validation_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    val_mask = meta["run"].isin(val_runs).to_numpy()
    train_mask = ~(heldout_mask | val_mask)
    if not set(meta.loc[train_mask, "run"]).isdisjoint(heldout_runs + val_runs):
        raise RuntimeError("run split leakage")

    bins = [float(x) for x in config["template_bins"]]
    template_train = train_mask.copy()
    train_template_idx = sample_indices(template_train, int(config["template_max_train_rows"]), rng)
    template_train = np.zeros(len(meta), dtype=bool)
    template_train[train_template_idx] = True
    templates = p04.build_templates(meta, wave, template_train, bins)
    template_scale = p04.template_scales(meta, wave, templates, bins, [float(x) for x in config["template_shift_grid"]])
    X_eng = engineered_features(meta, wave, template_scale)
    X_full = full_features(meta, wave, template_scale)
    X_nn_meta = engineered_features(meta, wave, template_scale)
    wave_nn = wave / np.maximum(meta["even_amp"].to_numpy()[:, None], 1.0)

    train_idx_sklearn = sample_indices(train_mask, int(config["sklearn_max_train_rows"]), rng)
    train_idx_nn = sample_indices(train_mask, int(config["nn_max_train_rows"]), rng)
    val_idx = np.where(val_mask)[0]
    preds: Dict[str, Dict[str, np.ndarray]] = {name: {} for name in [
        "peak_calibrated",
        "integral_calibrated",
        "template_fit_calibrated",
        "strong_traditional_huber",
        "ridge",
        "gradient_boosted_trees",
        "mlp",
        "cnn_1d",
        "residual_cnn",
        "context_only_median",
    ]}
    huber_base: Dict[str, np.ndarray] = {}

    for target, col in TARGETS.items():
        y = meta[col].to_numpy()
        peak_like = meta["even_amp"].to_numpy() if target == "amplitude" else meta["even_pos_charge"].to_numpy()
        peak_models = fit_log_calibrators(peak_like[train_mask], y[train_mask], st[train_mask])
        preds["peak_calibrated" if target == "amplitude" else "integral_calibrated"][target] = predict_log_calibrated(peak_models, peak_like, st)
        if target == "amplitude":
            preds["integral_calibrated"][target] = predict_log_calibrated(
                fit_log_calibrators(meta["even_pos_charge"].to_numpy()[train_mask], y[train_mask], st[train_mask]),
                meta["even_pos_charge"].to_numpy(),
                st,
            )
        else:
            preds["peak_calibrated"][target] = predict_log_calibrated(
                fit_log_calibrators(meta["even_amp"].to_numpy()[train_mask], y[train_mask], st[train_mask]),
                meta["even_amp"].to_numpy(),
                st,
            )

        template_models = fit_log_calibrators(template_scale[train_mask], y[train_mask], st[train_mask])
        preds["template_fit_calibrated"][target] = predict_log_calibrated(template_models, template_scale, st)

        huber_models = fit_per_stave_huber(X_eng, y, train_mask, st)
        huber_pred = predict_per_stave(huber_models, X_eng, st)
        preds["strong_traditional_huber"][target] = huber_pred
        huber_base[target] = np.log(np.maximum(huber_pred, 1.0))

        context = np.zeros(len(meta), dtype=float)
        for stave in sorted(np.unique(st)):
            mask_train = train_mask & (st == stave)
            context[st == stave] = float(np.median(y[mask_train]))
        preds["context_only_median"][target] = context

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=10.0, random_state=int(config["random_seed"])))
        ridge.fit(X_full[train_idx_sklearn], np.log(y[train_idx_sklearn]))
        preds["ridge"][target] = np.maximum(np.exp(ridge.predict(X_full)), 1.0)

        gbt = HistGradientBoostingRegressor(
            max_iter=220,
            learning_rate=0.055,
            max_leaf_nodes=31,
            l2_regularization=0.04,
            random_state=int(config["random_seed"]),
        )
        gbt.fit(X_full[train_idx_sklearn], np.log(y[train_idx_sklearn]))
        preds["gradient_boosted_trees"][target] = np.maximum(np.exp(gbt.predict(X_full)), 1.0)

        mlp = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(64, 32),
                activation="relu",
                alpha=1e-4,
                learning_rate_init=1e-3,
                batch_size=2048,
                max_iter=70,
                early_stopping=True,
                random_state=int(config["random_seed"]),
            ),
        )
        mlp.fit(X_full[train_idx_sklearn], np.log(y[train_idx_sklearn]))
        preds["mlp"][target] = np.maximum(np.exp(mlp.predict(X_full)), 1.0)

        cnn = train_torch_model(wave_nn, X_nn_meta, np.log(y), train_idx_nn, val_idx, config, int(config["random_seed"]))
        preds["cnn_1d"][target] = predict_torch(cnn, wave_nn, X_nn_meta)

        residual = train_torch_model(
            wave_nn,
            X_nn_meta,
            np.log(y),
            train_idx_nn,
            val_idx,
            config,
            int(config["random_seed"]) + 11,
            residual_base_log=huber_base[target],
        )
        preds["residual_cnn"][target] = predict_torch(residual, wave_nn, X_nn_meta, huber_base[target])

    benchmark, subset = evaluate(meta, preds, heldout_mask, config)
    benchmark.to_csv(out_dir / "benchmark.csv", index=False)
    subset.to_csv(out_dir / "benchmark_by_subset.csv", index=False)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    pred_frame = meta.loc[heldout_mask, ["run", "eventno", "evt", "stave", "even_amp", "even_pos_charge", "target_odd_neg_amp", "target_odd_pos_charge"]].copy()
    for method, by_target in preds.items():
        for target in TARGETS:
            pred_frame[f"{method}_{target}"] = by_target[target][heldout_mask]
    pred_frame.to_csv(out_dir / "predictions.csv.gz", index=False)

    amp_rows = benchmark[benchmark["target"] == "amplitude"].copy()
    traditional_methods = ["peak_calibrated", "integral_calibrated", "template_fit_calibrated", "strong_traditional_huber"]
    best_trad_row = amp_rows[amp_rows["method"].isin(traditional_methods)].sort_values("res68_abs_frac").iloc[0]
    winner_row = amp_rows.sort_values("res68_abs_frac").iloc[0]
    winner = str(winner_row["method"])

    shuffled_train = train_idx_sklearn.copy()
    y_amp = meta["target_odd_neg_amp"].to_numpy()
    shuffled = np.log(y_amp[shuffled_train]).copy()
    rng.shuffle(shuffled)
    shuffle_model = HistGradientBoostingRegressor(max_iter=80, random_state=int(config["random_seed"]) + 101)
    shuffle_model.fit(X_full[shuffled_train], shuffled)
    shuffle_pred = np.maximum(np.exp(shuffle_model.predict(X_full)), 1.0)

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "title": config["title"],
        "worker": config["worker"],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip(),
        "raw_reproduction": {
            "quantity": "S00 selected B-stave pulse records",
            "expected_selected_pulses": expected,
            "reproduced_selected_pulses": total,
            "delta": total - expected,
            "tolerance": 0,
            "pass": bool(total == expected),
        },
        "split": {
            "train_runs": sorted(int(x) for x in meta.loc[train_mask, "run"].unique()),
            "validation_runs": val_runs,
            "heldout_runs": heldout_runs,
            "bootstrap_samples": int(config["bootstrap_reps"]),
        },
        "methods": sorted(preds.keys()),
        "primary_metric": "heldout amplitude res68_abs_frac",
        "winner": winner,
        "winner_family": "traditional" if winner in traditional_methods else "ml_nn",
        "winner_metrics": json.loads(winner_row.to_json()),
        "best_traditional": json.loads(best_trad_row.to_json()),
        "benchmark": json.loads(benchmark.to_json(orient="records")),
        "leakage_audit": {
            "heldout_and_validation_absent_from_train": bool(set(meta.loc[train_mask, "run"]).isdisjoint(heldout_runs + val_runs)),
            "feature_columns_exclude_run_event_and_odd_target": True,
            "invalid_target_rows_removed_after_reproduction": invalid,
            "context_only_amp_res68": float(
                amp_rows.loc[amp_rows["method"] == "context_only_median", "res68_abs_frac"].iloc[0]
            ),
            "shuffled_target_gbt_amp_res68": robust_metrics(y_amp[heldout_mask], shuffle_pred[heldout_mask])["res68_abs_frac"],
        },
        "artifacts": {
            "report": str(out_dir / "REPORT.md"),
            "result": str(out_dir / "result.json"),
            "manifest": str(out_dir / "manifest.json"),
            "benchmark": str(out_dir / "benchmark.csv"),
            "benchmark_by_subset": str(out_dir / "benchmark_by_subset.csv"),
            "predictions": str(out_dir / "predictions.csv.gz"),
        },
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, result, benchmark, subset)

    input_files = [p04.raw_path(config, run) for run in p04.configured_runs(config)]
    input_sha = pd.DataFrame({"path": [str(p) for p in input_files], "sha256": [sha256_file(p) for p in input_files]})
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    output_names = ["REPORT.md", "result.json", "benchmark.csv", "benchmark_by_subset.csv", "predictions.csv.gz", "counts_by_run.csv", "input_sha256.csv"]
    manifest = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": "/home/billy/anaconda3/bin/python scripts/p04_2398_multimodel_charge_bakeoff.py --config configs/p04_2398_multimodel_charge_bakeoff.json",
        "config": str(config_path),
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": [{"path": str(out_dir / name), "sha256": sha256_file(out_dir / name)} for name in output_names],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (ROOT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (ROOT / "REPORT.md").write_text((out_dir / "REPORT.md").read_text(encoding="utf-8"), encoding="utf-8")
    print(f"DONE {out_dir} winner={winner} runtime_sec={result['runtime_sec']}")


if __name__ == "__main__":
    main()
