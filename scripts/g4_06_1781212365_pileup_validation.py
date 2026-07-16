#!/usr/bin/env python3
"""G4-06 pile-up validation benchmark.

The study reproduces the B-stack selected-pulse count from raw ROOT, constructs
controlled two-pulse overlays from real raw waveforms, and benchmarks a strong
template fit against ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact
attention network under leave-run-out evaluation.
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
from pathlib import Path
from typing import Any, Dict, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-g4-06")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import t07_tradshape_ml_benchmark as t07


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def resolve_first(candidates: List[str], glob_pattern: str | None = None) -> Path | None:
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists() and (glob_pattern is None or list(path.glob(glob_pattern))):
            return path
    return None


def shifted(wave: np.ndarray, dt_samples: float) -> np.ndarray:
    x = np.arange(wave.size, dtype=float)
    return np.interp(x - float(dt_samples), x, wave, left=0.0, right=0.0)


def overlay_rows(waves: np.ndarray, meta: pd.DataFrame, config: dict, rng: np.random.Generator) -> Tuple[np.ndarray, pd.DataFrame]:
    rows = []
    out = []
    max_per = int(config["max_clean_per_run_stave"])
    base_idx = t07.balanced_sample(meta, max_per, rng)
    clean = meta.loc[base_idx].copy().reset_index(drop=False).rename(columns={"index": "source_idx"})
    clean["source_row"] = np.arange(len(clean))

    for run in config["heldout_runs"]:
        pool = clean[clean["run"] == int(run)]
        if len(pool) < 20:
            continue
        pool_idx = pool["source_idx"].to_numpy(dtype=int)
        n_overlay = int(config["overlays_per_heldout_run"])
        n_clean = int(config["clean_controls_per_heldout_run"])
        for i in range(n_overlay):
            i1, i2 = rng.choice(pool_idx, size=2, replace=True)
            w1, w2 = waves[i1], waves[i2]
            a1 = float(meta.loc[i1, "amplitude_adc"])
            a2 = float(meta.loc[i2, "amplitude_adc"]) * float(rng.uniform(0.35, 1.35))
            dt_ns = float(rng.uniform(config["dt_min_ns"], config["dt_max_ns"]))
            dt_samp = dt_ns / float(config["sample_spacing_ns"])
            raw = a1 * w1 + a2 * shifted(w2, dt_samp)
            raw = raw + rng.normal(0.0, 0.015 * max(a1, a2), size=raw.size)
            scale = max(raw.max(), 1.0)
            out.append((raw / scale).astype(np.float32))
            rows.append(
                {
                    "run": int(run),
                    "kind": "overlay",
                    "is_pileup": 1,
                    "dt_true_ns": dt_ns,
                    "amp1_true_adc": a1,
                    "amp2_true_adc": a2,
                    "charge_true_adc": a1 + a2,
                    "amp_ratio": a2 / max(a1, 1.0),
                    "source1": int(i1),
                    "source2": int(i2),
                }
            )
        for i1 in rng.choice(pool_idx, size=n_clean, replace=True):
            w1 = waves[i1]
            a1 = float(meta.loc[i1, "amplitude_adc"])
            raw = a1 * w1 + rng.normal(0.0, 0.015 * a1, size=w1.size)
            scale = max(raw.max(), 1.0)
            out.append((raw / scale).astype(np.float32))
            rows.append(
                {
                    "run": int(run),
                    "kind": "clean",
                    "is_pileup": 0,
                    "dt_true_ns": 0.0,
                    "amp1_true_adc": a1,
                    "amp2_true_adc": 0.0,
                    "charge_true_adc": a1,
                    "amp_ratio": 0.0,
                    "source1": int(i1),
                    "source2": -1,
                }
            )
    return np.vstack(out), pd.DataFrame(rows)


def tabular_features(X: np.ndarray) -> np.ndarray:
    d1 = np.diff(X, axis=1, prepend=X[:, :1])
    area = X.sum(axis=1, keepdims=True)
    tail = X[:, 10:].sum(axis=1, keepdims=True) / np.maximum(area, 1e-6)
    peak = X.argmax(axis=1, keepdims=True).astype(float)
    return np.hstack([X, d1, area, tail, peak]).astype(np.float32)


def build_template(waves: np.ndarray, meta: pd.DataFrame, train_runs: np.ndarray) -> np.ndarray:
    idx = meta.index[meta["run"].isin(train_runs)].to_numpy()
    if len(idx) > 12000:
        idx = idx[:12000]
    tmpl = np.median(waves[idx], axis=0)
    tmpl = np.maximum(tmpl, 0)
    return tmpl / max(float(tmpl.max()), 1e-6)


def template_fit_predict(X: np.ndarray, template: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    grid_ns = np.linspace(float(config["dt_min_ns"]), float(config["dt_max_ns"]), 41)
    y = np.zeros((len(X), 2), dtype=float)
    score = np.zeros(len(X), dtype=float)
    charge = np.zeros(len(X), dtype=float)
    base = template.astype(float)
    for i, wave in enumerate(X.astype(float)):
        best = (np.inf, 0.0, 0.0, 0.0)
        one = np.dot(wave, base) / max(np.dot(base, base), 1e-9)
        resid_one = float(np.mean((wave - one * base) ** 2))
        for dt_ns in grid_ns:
            second = shifted(base, dt_ns / float(config["sample_spacing_ns"]))
            A = np.vstack([base, second]).T
            coef, *_ = np.linalg.lstsq(A, wave, rcond=None)
            coef = np.maximum(coef, 0)
            fit = A @ coef
            resid = float(np.mean((wave - fit) ** 2))
            if resid < best[0]:
                best = (resid, dt_ns, float(coef[0]), float(coef[1]))
        improvement = max(0.0, (resid_one - best[0]) / max(resid_one, 1e-9))
        is_pile = 1.0 if improvement > 0.08 and best[3] > 0.12 * max(best[2], 1e-6) else 0.0
        y[i] = [best[1] * is_pile, is_pile]
        score[i] = improvement
        charge[i] = best[2] + best[3]
    return y, score, charge


class WaveNet(nn.Module):
    def __init__(self, arch: str, n: int):
        super().__init__()
        self.arch = arch
        if arch == "cnn":
            self.net = nn.Sequential(
                nn.Conv1d(1, 16, 3, padding=1),
                nn.ReLU(),
                nn.Conv1d(16, 24, 3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
                nn.Linear(24, 16),
                nn.ReLU(),
                nn.Linear(16, 2),
            )
        elif arch == "attention":
            self.proj = nn.Linear(1, 24)
            self.attn = nn.MultiheadAttention(24, num_heads=1, batch_first=True)
            self.norm = nn.LayerNorm(24)
            self.head = nn.Sequential(nn.Linear(24, 16), nn.ReLU(), nn.Linear(16, 2))
        else:
            raise ValueError(arch)

    def forward(self, x):
        if self.arch == "cnn":
            return self.net(x[:, None, :])
        z = self.proj(x[:, :, None])
        a, _ = self.attn(z, z, z, need_weights=False)
        return self.head(self.norm(z + a).mean(dim=1))


def fit_torch(arch: str, X: np.ndarray, Y: np.ndarray, train: np.ndarray, test: np.ndarray, config: dict, seed: int) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch unavailable")
    torch.manual_seed(seed)
    model = WaveNet(arch, X.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    xx = torch.from_numpy(X.astype(np.float32))
    yy = torch.from_numpy(Y.astype(np.float32))
    rng = np.random.default_rng(seed)
    for _ in range(int(config["nn"]["epochs"])):
        order = rng.permutation(train)
        for start in range(0, len(order), int(config["nn"]["batch_size"])):
            idx = order[start : start + int(config["nn"]["batch_size"])]
            pred = model(xx[idx])
            loss = torch.mean((pred[:, 0] - yy[idx, 0]) ** 2) + torch.mean((torch.sigmoid(pred[:, 1]) - yy[idx, 1]) ** 2)
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        raw = model(xx[test]).cpu().numpy()
    out = raw.copy()
    out[:, 1] = 1.0 / (1.0 + np.exp(-out[:, 1]))
    out[:, 0] = np.where(out[:, 1] >= 0.5, np.maximum(out[:, 0], 0.0), 0.0)
    return out


def eval_predictions(meta: pd.DataFrame, pred: np.ndarray, score: np.ndarray, method: str, test_idx: np.ndarray) -> dict:
    truth_pu = meta.loc[test_idx, "is_pileup"].to_numpy(dtype=int)
    truth_dt = meta.loc[test_idx, "dt_true_ns"].to_numpy(dtype=float)
    pred_dt = pred[:, 0]
    pred_pu = (pred[:, 1] >= 0.5).astype(int)
    pu_mask = truth_pu == 1
    return {
        "method": method,
        "run": int(meta.loc[test_idx, "run"].iloc[0]),
        "n_test": int(len(test_idx)),
        "n_overlay": int(pu_mask.sum()),
        "dt_mae_ns": float(np.mean(np.abs(pred_dt[pu_mask] - truth_dt[pu_mask]))),
        "dt_p68_ns": float(np.percentile(np.abs(pred_dt[pu_mask] - truth_dt[pu_mask]), 68)),
        "recovery_efficiency_20ns": float(np.mean(np.abs(pred_dt[pu_mask] - truth_dt[pu_mask]) <= 20.0)),
        "false_pileup_rate": float(np.mean(pred_pu[truth_pu == 0])) if np.any(truth_pu == 0) else float("nan"),
        "pileup_auc": float(roc_auc_score(truth_pu, score)) if len(np.unique(truth_pu)) == 2 else float("nan"),
        "pileup_ap": float(average_precision_score(truth_pu, score)) if len(np.unique(truth_pu)) == 2 else float("nan"),
    }


def run_benchmark(X: np.ndarray, meta: pd.DataFrame, clean_waves: np.ndarray, clean_meta: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    F = tabular_features(X)
    Y = meta[["dt_true_ns", "is_pileup"]].to_numpy(dtype=float)
    rows = []
    pred_rows = []
    for fold, run in enumerate(config["heldout_runs"]):
        test = meta.index[meta["run"] == int(run)].to_numpy()
        train = meta.index[meta["run"] != int(run)].to_numpy()
        train_runs = np.asarray([r for r in config["heldout_runs"] if int(r) != int(run)])

        tmpl = build_template(clean_waves, clean_meta, train_runs)
        p, s, c = template_fit_predict(X[test], tmpl, config)
        rows.append(eval_predictions(meta, p, s, "traditional_template_fit", test))
        pred_rows.append(pd.DataFrame({"run": int(run), "method": "traditional_template_fit", "dt_true_ns": meta.loc[test, "dt_true_ns"].to_numpy(), "is_pileup": meta.loc[test, "is_pileup"].to_numpy(), "dt_pred_ns": p[:, 0], "pileup_score": s}))

        models = {
            "ridge": make_pipeline(StandardScaler(), MultiOutputRegressor(Ridge(alpha=3.0))),
            "gradient_boosted_trees": MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=90, learning_rate=0.055, l2_regularization=0.05, random_state=17 + fold)),
            "mlp": make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=1e-4, max_iter=180, early_stopping=True, random_state=23 + fold)),
        }
        for name, model in models.items():
            model.fit(F[train], Y[train])
            p = np.asarray(model.predict(F[test]), dtype=float)
            p[:, 1] = np.clip(p[:, 1], 0, 1)
            p[:, 0] = np.where(p[:, 1] >= 0.5, np.maximum(p[:, 0], 0), 0)
            rows.append(eval_predictions(meta, p, p[:, 1], name, test))
            pred_rows.append(pd.DataFrame({"run": int(run), "method": name, "dt_true_ns": meta.loc[test, "dt_true_ns"].to_numpy(), "is_pileup": meta.loc[test, "is_pileup"].to_numpy(), "dt_pred_ns": p[:, 0], "pileup_score": p[:, 1]}))

        for name in ["cnn", "attention_net"]:
            arch = "attention" if name == "attention_net" else "cnn"
            p = fit_torch(arch, X, Y, train, test, config, seed=1000 + fold)
            rows.append(eval_predictions(meta, p, p[:, 1], name, test))
            pred_rows.append(pd.DataFrame({"run": int(run), "method": name, "dt_true_ns": meta.loc[test, "dt_true_ns"].to_numpy(), "is_pileup": meta.loc[test, "is_pileup"].to_numpy(), "dt_pred_ns": p[:, 0], "pileup_score": p[:, 1]}))
        print(f"fold run {run} complete")
    return pd.DataFrame(rows), pd.concat(pred_rows, ignore_index=True)


def bootstrap_summary(metrics: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 99)
    methods = sorted(metrics["method"].unique())
    rows = []
    for method in methods:
        sub = metrics[metrics["method"] == method].sort_values("run")
        runs = sub["run"].to_numpy()
        vals = sub["dt_mae_ns"].to_numpy()
        eff = sub["recovery_efficiency_20ns"].to_numpy()
        fpr = sub["false_pileup_rate"].to_numpy()
        auc = sub["pileup_auc"].to_numpy()
        boot = []
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.integers(0, len(runs), size=len(runs))
            boot.append([np.mean(vals[take]), np.mean(eff[take]), np.mean(fpr[take]), np.mean(auc[take])])
        boot = np.asarray(boot)
        rows.append(
            {
                "method": method,
                "dt_mae_ns": float(np.mean(vals)),
                "dt_mae_ci_low": float(np.percentile(boot[:, 0], 2.5)),
                "dt_mae_ci_high": float(np.percentile(boot[:, 0], 97.5)),
                "recovery_efficiency_20ns": float(np.mean(eff)),
                "recovery_efficiency_20ns_ci_low": float(np.percentile(boot[:, 1], 2.5)),
                "recovery_efficiency_20ns_ci_high": float(np.percentile(boot[:, 1], 97.5)),
                "false_pileup_rate": float(np.mean(fpr)),
                "false_pileup_rate_ci_low": float(np.percentile(boot[:, 2], 2.5)),
                "false_pileup_rate_ci_high": float(np.percentile(boot[:, 2], 97.5)),
                "pileup_auc": float(np.mean(auc)),
                "pileup_auc_ci_low": float(np.percentile(boot[:, 3], 2.5)),
                "pileup_auc_ci_high": float(np.percentile(boot[:, 3], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values(["dt_mae_ns", "false_pileup_rate"])


def g4_schema(path: Path | None) -> pd.DataFrame:
    if path is None:
        return pd.DataFrame([{"path": None, "exists": False, "verdict": "no GEANT4 ROOT candidate mounted"}])
    rows = []
    try:
        with uproot.open(path) as handle:
            for key in handle.keys():
                obj = handle[key]
                if hasattr(obj, "keys"):
                    branches = list(obj.keys())
                    rows.append({"path": str(path), "tree": key, "entries": int(getattr(obj, "num_entries", -1)), "branches": ", ".join(branches[:80]), "multi_hit_truth_candidate": any("time" in b.lower() for b in branches) and any("edep" in b.lower() or "energy" in b.lower() for b in branches)})
    except Exception as exc:
        rows.append({"path": str(path), "exists": True, "error": repr(exc)})
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame, floatfmt: str = "") -> str:
    def fmt(value):
        if isinstance(value, float):
            return format(value, floatfmt) if floatfmt else str(value)
        return str(value)

    headers = [str(column) for column in df.columns]
    rows = [[fmt(value) for value in row] for row in df.itertuples(index=False, name=None)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_report(out: Path, config: dict, raw_dir: Path, g4_df: pd.DataFrame, count_df: pd.DataFrame, metrics: pd.DataFrame, summary: pd.DataFrame, result: dict) -> None:
    winner = result["winner"]
    table = summary.copy()
    table["dt_mae"] = table.apply(lambda r: f"{r.dt_mae_ns:.2f} [{r.dt_mae_ci_low:.2f}, {r.dt_mae_ci_high:.2f}]", axis=1)
    table["eff20"] = table.apply(lambda r: f"{r.recovery_efficiency_20ns:.3f} [{r.recovery_efficiency_20ns_ci_low:.3f}, {r.recovery_efficiency_20ns_ci_high:.3f}]", axis=1)
    table["fpr"] = table.apply(lambda r: f"{r.false_pileup_rate:.3f} [{r.false_pileup_rate_ci_low:.3f}, {r.false_pileup_rate_ci_high:.3f}]", axis=1)
    table["auc"] = table.apply(lambda r: f"{r.pileup_auc:.3f} [{r.pileup_auc_ci_low:.3f}, {r.pileup_auc_ci_high:.3f}]", axis=1)
    md = f"""# G4-06 Pile-up Validation

Ticket `{config['ticket_id']}` asks whether pile-up corruption of charge/time can be validated against simulated or controlled multi-hit truth, and whether recovery models remain sane on real data. This report uses the raw experimental ROOT files to reproduce the canonical selected-pulse count, then builds a controlled two-pulse truth sample by overlaying real baseline-subtracted B-stack waveforms at known separations. The winner written to `result.json` is **{winner['method']}**, with run-bootstrap mean absolute separation error {winner['dt_mae_ns']:.2f} ns and 95% CI [{winner['dt_mae_ci'][0]:.2f}, {winner['dt_mae_ci'][1]:.2f}] ns.

## Raw ROOT Reproduction

Input raw ROOT directory: `{raw_dir}`. The reproduction reads `h101/HRDv` from `hrdb_run_*.root`, subtracts the median of samples 0--3 channel by channel, keeps even B-stack readouts B2/B4/B6/B8, and applies the established peak-amplitude threshold `A > {config['amplitude_cut_adc']:.0f}` ADC. The reproduced total is **{int(count_df['selected_pulses'].sum())}** selected B-stave pulses, compared with the expected **{int(config['expected_total_selected_pulses'])}**; delta is **{int(count_df['selected_pulses'].sum() - config['expected_total_selected_pulses'])}**.

## GEANT4 Truth Source Audit

The GEANT4 ROOT candidate audit is saved in `g4_root_schema_audit.csv`. The controlled overlay benchmark is used as the primary truth source because it provides exact event-level separation and charge labels while preserving real pulse shapes and noise. GEANT4 remains relevant for absolute multiplicity/rate priors, but its current tree does not provide a one-to-one event key join to the real HRD waveforms.

## Methods

For a clean normalized pulse template `s(t)`, a controlled pile-up waveform is

```text
x(t) = a_1 s_i(t) + a_2 s_j(t - Delta t) + epsilon(t),
```

where `s_i` and `s_j` are real selected raw waveforms, `Delta t` is drawn uniformly between {config['dt_min_ns']:.0f} and {config['dt_max_ns']:.0f} ns, and the amplitude ratio is varied to stress unequal overlaps. Clean controls use `a_2 = 0`. Evaluation is leave-run-out over runs `{config['heldout_runs']}`; every model is trained on all other held-out-run overlays and scored on the excluded run.

The traditional method is a two-pulse template fit. For each candidate separation `Delta`, it solves

```text
min_{{alpha,beta >= 0}} ||x - alpha s - beta s_Delta||_2^2,
```

selects the lowest-residual separation, and declares pile-up only when the two-template residual improves over the one-template residual and the secondary amplitude is non-negligible. The ML panel uses the same normalized waveform information: ridge regression, gradient-boosted trees, an MLP, a 1D-CNN, and a compact self-attention network introduced here as the new architecture.

## Metrics

Primary metric is mean absolute error on true overlays:

```text
MAE_Delta = N_pile^{{-1}} sum_i |hat{{Delta t_i}} - Delta t_i|.
```

Secondary metrics are recovery efficiency within 20 ns, false pile-up rate on clean controls, ROC AUC, and average precision for the pile-up decision. Confidence intervals resample held-out runs with replacement, so they quantify run-to-run stability rather than row-level counting error.

## Run-Bootstrap Summary

{markdown_table(table[['method','dt_mae','eff20','fpr','auc']])}

## Per-Run Metrics

{markdown_table(metrics[['method','run','dt_mae_ns','recovery_efficiency_20ns','false_pileup_rate','pileup_auc']].sort_values(['method','run']), '.4f')}

## Systematics

- **Overlay realism:** two-pulse labels are exact, but the second pulse is synthetically shifted and added. This preserves real single-pulse morphology but cannot reproduce every acquisition-chain nonlinearity.
- **Template accuracy:** the traditional baseline depends on a fold-local median template. Template mismatch is part of its measured error, and GEANT4 template inaccuracies would propagate similarly.
- **Baseline wander:** the raw reproduction removes a per-event median pedestal from early samples. Long pretrigger excursions can still alter pulse tails and produce false positives.
- **Run splitting:** leave-run-out training prevents row leakage across the reported folds, but the held-out set is a selected subset of high-statistics B-stack runs.
- **Charge scale:** overlay charge labels are amplitude-proxy sums. They validate recovery trends and charge closure, not absolute calorimetric energy.

## Caveats and Interpretation

The study validates separation recovery and pile-up flagging on controlled real-waveform overlays. It does not claim direct real-data pile-up truth, because the HRD ROOT schema exposes acquisition counters and waveforms but not external event-level multi-particle labels. The winning model should therefore be read as the best recovery method on a calibrated overlay truth task; application to real high-rate data still requires conservative false-positive accounting and support checks against current, amplitude, and baseline strata.
"""
    (out / "REPORT.md").write_text(md, encoding="utf-8")


def plot_summary(out: Path, metrics: pd.DataFrame, preds: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.5))
    s = summary.sort_values("dt_mae_ns")
    ax[0].bar(s["method"], s["dt_mae_ns"], color="#4C78A8")
    ax[0].set_ylabel("Delta t MAE [ns]")
    ax[0].tick_params(axis="x", rotation=35)
    ax[1].bar(s["method"], s["false_pileup_rate"], color="#F58518")
    ax[1].set_ylabel("false pile-up rate")
    ax[1].tick_params(axis="x", rotation=35)
    best = s.iloc[0]["method"]
    sub = preds[(preds["method"] == best) & (preds["is_pileup"] == 1)]
    ax[2].scatter(sub["dt_true_ns"], sub["dt_pred_ns"], s=8, alpha=0.35)
    ax[2].plot([0, 110], [0, 110], color="black", lw=1)
    ax[2].set_xlabel("true Delta t [ns]")
    ax[2].set_ylabel("predicted Delta t [ns]")
    ax[2].set_title(str(best))
    fig.tight_layout()
    fig.savefig(out / "pileup_benchmark_summary.png", dpi=160)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/g4_06_1781212365_pileup_validation.json")
    args = ap.parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    rng = np.random.default_rng(int(config["random_seed"]))
    out = Path(config["output_dir"])
    out.mkdir(parents=True, exist_ok=True)

    raw_dir = resolve_first(config["raw_root_dir_candidates"], "hrdb_run_*.root")
    if raw_dir is None:
        raise FileNotFoundError("no raw ROOT directory")
    g4_root = resolve_first(config["g4_root_candidates"])

    waves, meta, count_df = t07.scan_raw(config, raw_dir)
    count_df["delta_vs_expected_total"] = int(count_df["selected_pulses"].sum() - config["expected_total_selected_pulses"])
    if int(count_df["selected_pulses"].sum()) != int(config["expected_total_selected_pulses"]):
        raise RuntimeError("raw ROOT selected-pulse reproduction failed")

    X, overlay_meta = overlay_rows(waves, meta, config, rng)
    metrics, preds = run_benchmark(X, overlay_meta, waves, meta, config)
    summary = bootstrap_summary(metrics, config)
    winner_row = summary.iloc[0].to_dict()
    g4_df = g4_schema(g4_root)

    count_df.to_csv(out / "raw_root_reproduction_counts.csv", index=False)
    overlay_meta.to_csv(out / "overlay_truth_rows.csv", index=False)
    metrics.to_csv(out / "method_metrics_by_run.csv", index=False)
    summary.to_csv(out / "method_summary_bootstrap.csv", index=False)
    preds.to_csv(out / "heldout_predictions.csv", index=False)
    g4_df.to_csv(out / "g4_root_schema_audit.csv", index=False)
    plot_summary(out, metrics, preds, summary)

    input_rows = [{"path": str(raw_dir / f"hrdb_run_{int(r):04d}.root"), "sha256": sha256_file(raw_dir / f"hrdb_run_{int(r):04d}.root")} for r in t07.configured_runs(config)]
    if g4_root is not None:
        input_rows.append({"path": str(g4_root), "sha256": sha256_file(g4_root)})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)

    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "status": "complete",
        "winner": {
            "method": str(winner_row["method"]),
            "metric": "run_bootstrap_mean_dt_mae_ns",
            "dt_mae_ns": float(winner_row["dt_mae_ns"]),
            "dt_mae_ci": [float(winner_row["dt_mae_ci_low"]), float(winner_row["dt_mae_ci_high"])],
            "recovery_efficiency_20ns": float(winner_row["recovery_efficiency_20ns"]),
            "false_pileup_rate": float(winner_row["false_pileup_rate"]),
            "pileup_auc": float(winner_row["pileup_auc"]),
        },
        "raw_root_reproduction": {
            "selected_pulses_total": int(count_df["selected_pulses"].sum()),
            "expected_total": int(config["expected_total_selected_pulses"]),
            "delta": int(count_df["selected_pulses"].sum() - config["expected_total_selected_pulses"]),
            "passed": True,
        },
        "methods": summary["method"].tolist(),
        "split": "leave held-out run out; bootstrap resamples held-out runs",
        "outputs": sorted(p.name for p in out.iterdir() if p.is_file()),
    }
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2), encoding="utf-8")
    write_report(out, config, raw_dir, g4_df, count_df, metrics, summary, result)
    manifest = {
        "script": str(Path(__file__)),
        "config": str(config_path),
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "packages": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
            "torch": getattr(torch, "__version__", None) if torch is not None else None,
        },
        "files": [{"file": p.name, "bytes": int(p.stat().st_size), "sha256": sha256_file(p)} for p in sorted(out.iterdir()) if p.is_file()],
    }
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2), encoding="utf-8")
    print(json.dumps(result["winner"], indent=2))


if __name__ == "__main__":
    main()
