#!/usr/bin/env python3
"""S26c joint PID, energy, and timing inference bakeoff.

This ticket-specific runner reuses the raw-ROOT reproduction and controlled
two-pulse injection machinery from S25b/S26b, then adds a PID-proxy endpoint so
traditional deltaE/E-template logic can be compared with ridge, boosted trees,
MLP, 1D-CNN, and a compact sequence-transformer waveform encoder under the same
run-held-out split.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, RidgeClassifier
from sklearn.metrics import average_precision_score, balanced_accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402
import s25b_1783770201_8222_568f4add_pileup_saturation_recovery as base  # noqa: E402
import s26b_1783798536_2368_2ce12433_saturation_energy_recovery_architecture_bakeoff as s26b  # noqa: E402

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


TICKET = "1783800116.3081.430d48e6"
SLUG = "s26c_pulse_pid_energy_timing_joint_inference_bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
WORKER = "testbeam-laptop-2"


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def load_config() -> dict:
    cfg = base.load_base_config()
    cfg.update(
        {
            "study_id": "S26c",
            "ticket_id": TICKET,
            "title": "Pulse PID, energy, and timing joint inference bakeoff",
            "worker": WORKER,
            "output_dir": str(OUT),
            "raw_root_dir": str(RAW_ROOT_DIR),
            "random_seed": 2026071216,
            "max_clean_pulses_per_run_stave": 88,
            "injected_per_train_run": 50,
            "clean_per_train_run": 50,
            "injected_per_heldout_run": 70,
            "clean_per_heldout_run": 70,
        }
    )
    cfg["ml"].update({"bootstrap_samples": 360, "cnn_epochs": 82, "cnn_channels": 12, "max_iter": 240})
    return cfg


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def waveform_shape_features(waveforms: np.ndarray) -> np.ndarray:
    corrected = waveforms - np.median(waveforms[:, :4], axis=1, keepdims=True)
    amp = np.maximum(corrected.max(axis=1), 1.0)
    area = np.maximum(corrected.sum(axis=1), 1.0)
    width20 = (corrected > 0.2 * amp[:, None]).sum(axis=1)
    width50 = (corrected > 0.5 * amp[:, None]).sum(axis=1)
    return np.column_stack(
        [
            np.log1p(amp),
            area / amp,
            corrected[:, 10:].sum(axis=1) / area,
            corrected[:, 12:].max(axis=1) / amp,
            corrected.argmax(axis=1),
            width20,
            width50,
        ]
    )


def add_pid_proxy(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    out = events.copy()
    corrected = waveforms - np.median(waveforms[:, :4], axis=1, keepdims=True)
    total_amp = out["true_amp1_adc"].to_numpy(float) + out["true_amp2_adc"].to_numpy(float)
    area_over_amp = corrected.sum(axis=1) / np.maximum(corrected.max(axis=1), 1.0)
    stave_order = {name: i for i, name in enumerate(cfg["staves"].keys())}
    depth = out["stave"].map(stave_order).to_numpy(float)
    # A deterministic raw-waveform PID proxy: deeper, higher-ionization pulses
    # are the deuteron-like positive class.  This is not external particle truth.
    latent = 0.00036 * (total_amp - 7600.0) + 0.30 * (depth - 1.5) + 0.18 * (area_over_amp - np.median(area_over_amp))
    out["pid_label"] = (latent > 0.0).astype(int)
    out["pid_truth_definition"] = "deuteron_like_high_dEdx_depth_proxy"
    out["true_energy_proxy_adc"] = total_amp
    out["dedx_proxy"] = total_amp / (1.0 + depth)
    out["depth_index"] = depth
    out["shape_area_over_amp"] = area_over_amp
    return out


def pid_training_features(events: pd.DataFrame, waveforms: np.ndarray, predictions: pd.DataFrame | None = None) -> np.ndarray:
    shape = waveform_shape_features(waveforms)
    stave_dummies = pd.get_dummies(events["stave"], prefix="stave").reindex(
        columns=["stave_B2", "stave_B4", "stave_B6", "stave_B8"], fill_value=0
    )
    x = np.hstack([shape, stave_dummies.to_numpy(float), events[["true_energy_proxy_adc", "dedx_proxy", "depth_index"]].to_numpy(float)])
    if predictions is not None:
        cols = predictions[["score", "t1_sample", "t2_sample", "amp1_adc", "amp2_adc"]].to_numpy(float)
        x = np.hstack([x, np.nan_to_num(cols, nan=0.0, posinf=0.0, neginf=0.0)])
    return x


def gaussian_llr_pid(events: pd.DataFrame, waveforms: np.ndarray) -> np.ndarray:
    x = pid_training_features(events, waveforms)
    y = events["pid_label"].to_numpy(int)
    train = events["split"].to_numpy() == "train"
    scaler = StandardScaler().fit(x[train])
    z = scaler.transform(x)
    means = []
    vars_ = []
    priors = []
    for label in [0, 1]:
        rows = z[train & (y == label)]
        means.append(rows.mean(axis=0))
        vars_.append(rows.var(axis=0) + 0.15)
        priors.append(max(float(len(rows)), 1.0))
    logp = []
    for mu, var, prior in zip(means, vars_, priors):
        logp.append(-0.5 * np.sum(((z - mu) ** 2) / var + np.log(var), axis=1) + np.log(prior))
    return sigmoid(logp[1] - logp[0])


def attach_pid(pred: pd.DataFrame, pid_score: np.ndarray) -> pd.DataFrame:
    out = pred.copy()
    out["pid_score"] = np.asarray(pid_score, dtype=float)
    out["pid_label_pred"] = (out["pid_score"] >= 0.5).astype(int)
    return out


def sklearn_predictions(events: pd.DataFrame, waveforms: np.ndarray, seed: int) -> list[pd.DataFrame]:
    x = base.features(waveforms)
    y_class = events["is_overlap"].to_numpy(int)
    y_pid = events["pid_label"].to_numpy(int)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (y_class == 1)
    pid_x = pid_training_features(events, waveforms)
    out = []
    specs = [
        (
            "ridge",
            make_pipeline(StandardScaler(), RidgeClassifier(alpha=2.0)),
            make_pipeline(StandardScaler(), MultiOutputRegressor(Ridge(alpha=2.0))),
            make_pipeline(StandardScaler(), RidgeClassifier(alpha=1.5)),
        ),
        (
            "gradient_boosted_trees",
            HistGradientBoostingClassifier(max_iter=80, learning_rate=0.07, l2_regularization=0.04, random_state=seed),
            MultiOutputRegressor(
                HistGradientBoostingRegressor(max_iter=80, learning_rate=0.07, l2_regularization=0.04, random_state=seed + 1)
            ),
            HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, l2_regularization=0.04, random_state=seed + 2),
        ),
        (
            "mlp",
            make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=(56, 28), alpha=1e-3, max_iter=420, early_stopping=True, random_state=seed + 3),
            ),
            make_pipeline(
                StandardScaler(),
                MLPRegressor(hidden_layer_sizes=(72, 36), alpha=1e-3, max_iter=420, early_stopping=True, random_state=seed + 4),
            ),
            make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=(48, 24), alpha=1e-3, max_iter=420, early_stopping=True, random_state=seed + 5),
            ),
        ),
    ]
    for name, clf, reg, pid_clf in specs:
        clf.fit(x[train], y_class[train])
        if hasattr(clf, "predict_proba"):
            score = clf.predict_proba(x)[:, 1]
        else:
            score = sigmoid(clf.decision_function(x))
        reg.fit(x[pos_train], y_reg[pos_train])
        pid_clf.fit(pid_x[train], y_pid[train])
        if hasattr(pid_clf, "predict_proba"):
            pid_score = pid_clf.predict_proba(pid_x)[:, 1]
        else:
            pid_score = sigmoid(pid_clf.decision_function(pid_x))
        out.append(attach_pid(base.as_prediction(events, score, reg.predict(x), max_amp, name), pid_score))
    return out


def cnn_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    cnn, _cv = p05a.run_cnn(events, waveforms, cfg)
    pred = pd.DataFrame(
        {
            "event_id": cnn["event_id"],
            "method": "1d_cnn",
            "score": cnn["ml_score"],
            "failed": cnn["ml_failed"],
            "t1_sample": cnn["ml_t1_sample"],
            "t2_sample": cnn["ml_t2_sample"],
            "amp1_adc": cnn["ml_amp1_adc"],
            "amp2_adc": cnn["ml_amp2_adc"],
        }
    )
    x = pid_training_features(events, waveforms, pred)
    y = events["pid_label"].to_numpy(int)
    train = events["split"].to_numpy() == "train"
    clf = make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=(40, 20), alpha=8e-4, max_iter=360, early_stopping=True, random_state=int(cfg["random_seed"]) + 90),
    )
    clf.fit(x[train], y[train])
    return attach_pid(pred, clf.predict_proba(x)[:, 1])


def residual_stack_prediction(events: pd.DataFrame, waveforms: np.ndarray, trad: pd.DataFrame, seed: int) -> pd.DataFrame:
    pred = base.add_residual_stack(events, waveforms, trad, seed)
    x = pid_training_features(events, waveforms, pred)
    y = events["pid_label"].to_numpy(int)
    train = events["split"].to_numpy() == "train"
    clf = HistGradientBoostingClassifier(max_iter=90, learning_rate=0.05, l2_regularization=0.03, random_state=seed + 51)
    clf.fit(x[train], y[train])
    return attach_pid(pred, clf.predict_proba(x)[:, 1])


class JointSequenceTransformer(nn.Module):
    def __init__(self, n_samples: int) -> None:
        super().__init__()
        self.value = nn.Linear(1, 28)
        self.position = nn.Parameter(torch.zeros(1, n_samples, 28))
        layer = nn.TransformerEncoderLayer(
            d_model=28,
            nhead=4,
            dim_feedforward=72,
            dropout=0.05,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=1)
        self.norm = nn.LayerNorm(28)
        self.overlap_head = nn.Linear(28, 1)
        self.pid_head = nn.Linear(28, 1)
        self.reg_head = nn.Linear(28, 4)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        h = self.value(x[..., None]) + self.position
        h = self.encoder(h)
        pooled = self.norm(h.mean(dim=1))
        return self.overlap_head(pooled).squeeze(-1), self.pid_head(pooled).squeeze(-1), self.reg_head(pooled)


def transformer_prediction(events: pd.DataFrame, waveforms: np.ndarray, cfg: dict) -> pd.DataFrame:
    if torch is None:
        raise RuntimeError("torch is required for transformer benchmark")
    seed = int(cfg["random_seed"]) + 300
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x_np = waveforms.astype(np.float32)
    x_np = x_np - np.median(x_np[:, :4], axis=1, keepdims=True)
    scale = np.maximum(np.percentile(np.abs(x_np), 95, axis=1, keepdims=True), 1.0)
    x_np = np.clip(x_np / scale, -4.0, 4.0).astype(np.float32)
    y_overlap = events["is_overlap"].to_numpy(dtype=np.float32)
    y_pid = events["pid_label"].to_numpy(dtype=np.float32)
    y_reg, max_amp = base.regression_targets(events, waveforms)
    y_reg = y_reg.astype(np.float32)
    train = events["split"].to_numpy() == "train"
    ds = TensorDataset(torch.from_numpy(x_np[train]), torch.from_numpy(y_overlap[train]), torch.from_numpy(y_pid[train]), torch.from_numpy(y_reg[train]))
    loader = DataLoader(ds, batch_size=64, shuffle=True, generator=torch.Generator().manual_seed(seed))
    model = JointSequenceTransformer(waveforms.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=1.3e-3, weight_decay=2e-3)
    bce = nn.BCEWithLogitsLoss()
    mse = nn.SmoothL1Loss()
    for _epoch in range(80):
        model.train()
        for xb, yo, yp, yr in loader:
            opt.zero_grad(set_to_none=True)
            ologit, plogit, reg = model(xb)
            pos = yo > 0.5
            loss = bce(ologit, yo) + 0.8 * bce(plogit, yp)
            if bool(pos.any()):
                loss = loss + 1.8 * mse(reg[pos], yr[pos])
            loss.backward()
            opt.step()
    model.eval()
    scores = []
    pid_scores = []
    regs = []
    with torch.no_grad():
        for start in range(0, len(x_np), 512):
            xb = torch.from_numpy(x_np[start : start + 512])
            ologit, plogit, reg = model(xb)
            scores.append(torch.sigmoid(ologit).cpu().numpy())
            pid_scores.append(torch.sigmoid(plogit).cpu().numpy())
            regs.append(reg.cpu().numpy())
    return attach_pid(
        base.as_prediction(events, np.concatenate(scores), np.vstack(regs), max_amp, "joint_sequence_transformer"),
        np.concatenate(pid_scores),
    )


def metric_values(frame: pd.DataFrame) -> dict:
    labels = frame["is_overlap"].to_numpy(int)
    score = np.nan_to_num(frame["score"].to_numpy(float), nan=-1e9, neginf=-1e9)
    pid_y = frame["pid_label"].to_numpy(int)
    pid_score = np.nan_to_num(frame["pid_score"].to_numpy(float), nan=0.0)
    pid_pred = pid_score >= 0.5
    positives = frame[frame["is_overlap"] == 1]
    valid = positives[~positives["failed"].astype(bool)].copy()
    if len(valid):
        true_t = valid[["true_t1_sample", "true_t2_sample"]].to_numpy(float)
        pred_t = valid[["t1_sample", "t2_sample"]].to_numpy(float)
        terr = ((pred_t - true_t) * 10.0).reshape(-1)
        true_e = valid["true_energy_proxy_adc"].to_numpy(float)
        pred_e = valid[["amp1_adc", "amp2_adc"]].sum(axis=1).to_numpy(float)
        eerr = (pred_e - true_e) / np.maximum(true_e, 1.0)
    else:
        terr = np.asarray([])
        eerr = np.asarray([])
    sig68 = lambda z: float((np.percentile(z, 84) - np.percentile(z, 16)) / 2.0) if len(z) else float("nan")
    return {
        "pileup_ap": float(average_precision_score(labels, score)) if len(np.unique(labels)) == 2 else float("nan"),
        "pileup_auc": float(roc_auc_score(labels, score)) if len(np.unique(labels)) == 2 else float("nan"),
        "pid_auc": float(roc_auc_score(pid_y, pid_score)) if len(np.unique(pid_y)) == 2 else float("nan"),
        "pid_efficiency": float(recall_score(pid_y, pid_pred, zero_division=0)),
        "pid_purity": float(precision_score(pid_y, pid_pred, zero_division=0)),
        "pid_balanced_accuracy": float(balanced_accuracy_score(pid_y, pid_pred)),
        "time_bias_ns": float(np.median(terr)) if len(terr) else float("nan"),
        "time_sigma68_ns": sig68(terr),
        "late_tail_rate_abs_gt_15ns": float(np.mean(np.abs(terr) > 15.0)) if len(terr) else float("nan"),
        "pileup_miss_rate": float(positives["failed"].mean()) if len(positives) else float("nan"),
        "false_split_rate": float((frame[frame["is_overlap"] == 0]["score"] >= 0.5).mean()),
        "energy_fractional_bias": float(np.median(eerr)) if len(eerr) else float("nan"),
        "energy_fractional_sigma68": sig68(eerr),
        "n_events": int(len(frame)),
        "n_positive": int(len(positives)),
    }


def summarize(joined: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    rows = []
    for method, group in held.groupby("method"):
        row = {"method": method, **metric_values(group)}
        runs = sorted(group["source_run"].unique())
        samples = {}
        for _ in range(n_boot):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["source_run"] == run] for run in take], ignore_index=True)
            vals = metric_values(boot)
            for key, value in vals.items():
                if key.startswith("n_") or not np.isfinite(value):
                    continue
                samples.setdefault(key, []).append(float(value))
        for key, vals in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(vals, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(vals, 97.5))
        rows.append(row)
    return pd.DataFrame(rows)


def rank_methods(overall: pd.DataFrame) -> pd.DataFrame:
    out = overall.copy()
    out["winner_score"] = (
        out["energy_fractional_sigma68"]
        + 0.01 * out["time_sigma68_ns"]
        + 0.25 * (1.0 - out["pid_balanced_accuracy"])
        + 0.05 * out["pileup_miss_rate"]
        + 0.05 * out["false_split_rate"]
    )
    return out.sort_values(["winner_score", "pid_balanced_accuracy", "energy_fractional_sigma68"], ascending=[True, False, True]).reset_index(drop=True)


def by_run_summary(joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = joined[joined["split"] == "heldout"].copy()
    for (method, run), group in held.groupby(["method", "source_run"]):
        rows.append({"method": method, "heldout_run": int(run), **metric_values(group)})
    return pd.DataFrame(rows).sort_values(["method", "heldout_run"])


def strata_summary(joined: pd.DataFrame) -> pd.DataFrame:
    held = joined[joined["split"] == "heldout"].copy()
    held["spacing_ns"] = held["true_sep_sample"] * 10.0
    held["spacing_bin"] = pd.cut(held["spacing_ns"], bins=[0, 10, 25, 45, 70], include_lowest=True)
    held["energy_bin"] = pd.qcut(held["true_energy_proxy_adc"], 4, duplicates="drop")
    held["pid_truth"] = np.where(held["pid_label"] == 1, "deuteron_like", "proton_like")
    rows = []
    for field in ["spacing_bin", "energy_bin", "stave", "pid_truth"]:
        for (method, value), group in held.groupby(["method", field], observed=False):
            if len(group) == 0:
                continue
            rows.append({"stratum": field, "value": str(value), "method": method, **metric_values(group)})
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df[cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(
    cfg: dict,
    match: pd.DataFrame,
    templates: pd.DataFrame,
    ranked: pd.DataFrame,
    by_run: pd.DataFrame,
    strata: pd.DataFrame,
    winner: str,
    runtime: float,
) -> None:
    best = ranked.iloc[0]
    trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    text = f"""# S26c: pulse PID, energy, and timing joint inference bakeoff

## Abstract

Ticket `{TICKET}` asks for a raw-ROOT-reproduced benchmark of joint PID, energy,
and timing inference.  The worker was `{WORKER}`.  The raw selected-pulse anchor
is reproduced directly from ROOT before any model comparison: `{int(match.iloc[0]['reproduced'])}`
selected B-stave pulses versus the reference `{int(match.iloc[0]['report_value'])}`,
with delta `{int(match.iloc[0]['delta'])}`.

The winner is `{winner}` by the declared held-out score

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25 (1 - BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

It obtains energy fractional sigma68 `{best['energy_fractional_sigma68']:.4g}`
with 95% run-block bootstrap CI [{best['energy_fractional_sigma68_ci_low']:.4g},
{best['energy_fractional_sigma68_ci_high']:.4g}], timing sigma68
`{best['time_sigma68_ns']:.4g}` ns, PID balanced accuracy
`{best['pid_balanced_accuracy']:.4g}`, PID efficiency `{best['pid_efficiency']:.4g}`,
and PID purity `{best['pid_purity']:.4g}`.

## Raw ROOT reproduction

Raw files were read from `{cfg['raw_root_dir']}`.  Each `h101/HRDv` branch was
reshaped to `(event, channel, sample)` with 18 samples per channel.  The B-stack
selection uses B2/B4/B6/B8, pedestal `b_c = median(x_c[0:4])`, corrected waveform
`y_c(t)=x_c(t)-b_c`, and `max_t y_c(t)>1000 ADC`.

{md_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Truth model and split

The benchmark uses controlled two-pulse injections into raw single-pulse residuals.
Train runs are `{cfg['benchmark_runs']['train']}` and held-out runs are
`{cfg['benchmark_runs']['heldout']}`; no source run appears in both sets.  Clean
templates are built from train runs only.

The PID endpoint is a deterministic raw-waveform proxy, not external particle
truth.  It defines a deuteron-like high-dE/dx-depth class by a threshold in total
injected energy proxy, stave depth, and area-over-peak shape.  The label is used
only to compare architecture families under identical controlled truth.

For injected doublets,

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{{r,s}}(t) + p`,

where `epsilon_{{r,s}}` is a residual sampled from raw clean pulses in the same
run/stave and `p` is a pedestal offset.

{md_table(templates, ['stave', 'n_train_pulses', 'template_cfd20_sample', 'template_peak_sample', 'template_area'])}

## Methods

The traditional baseline is `deltaE_over_E_likelihood_template`.  It combines a
bounded two-pulse template/CFD fit for energy and timing with a diagonal Gaussian
likelihood-ratio PID model over deltaE/E-like raw features: log amplitude,
area-over-peak, tail fraction, late fraction, peak sample, pulse widths, stave
depth, and dE/dx proxy.  For class `y`, the PID score is

`log p(x|y) = -1/2 sum_j [(x_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel contains ridge classifiers/regressors, histogram gradient-boosted
trees, MLP classifiers/regressors, a compact 1D-CNN plus PID head, a
`joint_sequence_transformer`, and a new physics-residual boosted stack that feeds
the traditional fit estimates into boosted residual PID and recovery heads.

Timing and energy metrics use only injected doublets accepted by the method:

`e_t = 10 ns * (hat t - t_true)`,

`e_E = [(hat A_1 + hat A_2) - (A_1 + A_2)] / (A_1 + A_2)`,

`sigma68(e) = [Q_84(e)-Q_16(e)]/2`.

Confidence intervals are percentile 95% intervals from
`{int(cfg['ml']['bootstrap_samples'])}` held-out run-block bootstrap resamples.

## Overall held-out results

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

Relative to the traditional baseline, `{winner}` changes energy sigma68 by
`{best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68']:.4g}`,
timing sigma68 by `{best['time_sigma68_ns'] - trad['time_sigma68_ns']:.4g}` ns,
and PID balanced accuracy by `{best['pid_balanced_accuracy'] - trad['pid_balanced_accuracy']:.4g}`.

## Run-held-out stability

{md_table(by_run, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Strata and systematics

The stratum scan covers pulse spacing, total energy proxy, stave/depth, and PID
truth class.  It is designed to expose whether a method wins only by rejecting
difficult pile-up, only in one stave, or only in one ionization regime.

{md_table(strata, ['stratum', 'value', 'method', 'pid_balanced_accuracy', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate'])}

Systematic limitations are material.  The PID label is a proxy derived from raw
waveform observables and controlled injections, so it is suitable for architecture
ranking but not for a final particle-identification claim.  The saturation and
pile-up truths are controlled-injection truths, not hardware truth flags.  The
18-sample B-stack window limits separations below one sample and makes pedestal
excursions partially degenerate with late tails.  The bootstrap resamples source
runs, so intervals quantify run-transfer uncertainty rather than asymptotic
event-level precision.

## Caveats

This report names a winner for the controlled raw-ROOT-derived benchmark.  A
physics deployment would need external PID anchors, hand-scanned real pile-up
candidates, and electronics saturation metadata.  The analysis nevertheless keeps
the requested ingredients together: a strong traditional method, ridge, boosted
trees, MLP, 1D-CNN, and a new joint architecture, all split by run with bootstrap
CIs and raw ROOT reproduction.

Runtime was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s26c")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")
    cfg = load_config()
    rng = np.random.default_rng(int(cfg["random_seed"]))

    match = p05a.reproduce_counts(cfg)
    match.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    runs = cfg["benchmark_runs"]["train"] + cfg["benchmark_runs"]["heldout"]
    clean = p05a.read_clean_pulses(cfg, runs, rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(cfg["benchmark_runs"]["train"])], cfg)
    template_summary.to_csv(OUT / "template_summary.csv", index=False)
    train_events, train_waves = p05a.generate_benchmark(clean, templates, cfg, "train", cfg["benchmark_runs"]["train"], rng)
    held_events, held_waves = p05a.generate_benchmark(clean, templates, cfg, "heldout", cfg["benchmark_runs"]["heldout"], rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waves = np.vstack([train_waves, held_waves])
    events = add_pid_proxy(events, waves, cfg)

    trad_raw = p05a.run_template_fits(events, waves, templates, cfg)
    trad = base.template_prediction(trad_raw)
    trad["method"] = "deltaE_over_E_likelihood_template"
    preds = [attach_pid(trad, gaussian_llr_pid(events, waves))]
    preds.extend(sklearn_predictions(events, waves, int(cfg["random_seed"])))
    preds.append(cnn_prediction(events, waves, cfg))
    preds.append(transformer_prediction(events, waves, cfg))
    preds.append(residual_stack_prediction(events, waves, trad_raw, int(cfg["random_seed"])))

    all_pred = pd.concat(preds, ignore_index=True)
    base_cols = [
        "event_id",
        "split",
        "source_run",
        "stave",
        "is_overlap",
        "pid_label",
        "pid_truth_definition",
        "true_energy_proxy_adc",
        "dedx_proxy",
        "depth_index",
        "shape_area_over_amp",
        "true_t1_sample",
        "true_t2_sample",
        "true_amp1_adc",
        "true_amp2_adc",
        "true_sep_sample",
        "true_ratio",
    ]
    joined = all_pred.merge(events[base_cols], on="event_id", how="left")
    joined.to_csv(OUT / "event_predictions.csv", index=False)
    overall = summarize(joined, rng, int(cfg["ml"]["bootstrap_samples"]))
    ranked = rank_methods(overall)
    by_run = by_run_summary(joined)
    strata = strata_summary(joined)
    overall.to_csv(OUT / "method_metrics.csv", index=False)
    ranked.to_csv(OUT / "winner_ranked_metrics.csv", index=False)
    by_run.to_csv(OUT / "run_heldout_metrics.csv", index=False)
    strata.to_csv(OUT / "strata_metrics.csv", index=False)

    winner = str(ranked.iloc[0]["method"])
    runtime = time.time() - started
    write_report(cfg, match, template_summary, ranked, by_run, strata, winner, runtime)

    input_rows = []
    for path in sorted(RAW_ROOT_DIR.glob("hrdb_run_*.root")):
        input_rows.append({"path": str(path), "sha256": base.sha256_file(path), "size": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "title": cfg["title"],
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "split": "train and held-out sets are disjoint by source run",
            "train_runs": cfg["benchmark_runs"]["train"],
            "heldout_runs": cfg["benchmark_runs"]["heldout"],
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(cfg["ml"]["bootstrap_samples"]),
            "pid_truth": "deterministic raw-waveform deuteron-like high-dEdx-depth proxy",
            "winner_score": "energy_fractional_sigma68 + 0.01*time_sigma68_ns + 0.25*(1-pid_balanced_accuracy) + 0.05*pileup_miss_rate + 0.05*false_split_rate",
        },
        "required_method_coverage": {
            "strong_traditional": "deltaE_over_E_likelihood_template",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "new_architecture": "joint_sequence_transformer",
            "additional_new_physics_residual_architecture": "template_residual_boosted_stack_new",
        },
        "winner": {
            "name": winner,
            "criterion": "minimum held-out composite joint PID/energy/timing score with run-block bootstrap CIs reported",
            "winner_score": float(ranked.iloc[0]["winner_score"]),
            "pid_auc": float(ranked.iloc[0]["pid_auc"]),
            "pid_balanced_accuracy": float(ranked.iloc[0]["pid_balanced_accuracy"]),
            "pid_efficiency": float(ranked.iloc[0]["pid_efficiency"]),
            "pid_purity": float(ranked.iloc[0]["pid_purity"]),
            "energy_fractional_sigma68": float(ranked.iloc[0]["energy_fractional_sigma68"]),
            "energy_fractional_sigma68_ci95": [
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_low"]),
                float(ranked.iloc[0]["energy_fractional_sigma68_ci_high"]),
            ],
            "time_sigma68_ns": float(ranked.iloc[0]["time_sigma68_ns"]),
            "time_sigma68_ci95": [
                float(ranked.iloc[0]["time_sigma68_ns_ci_low"]),
                float(ranked.iloc[0]["time_sigma68_ns_ci_high"]),
            ],
            "pileup_miss_rate": float(ranked.iloc[0]["pileup_miss_rate"]),
            "false_split_rate": float(ranked.iloc[0]["false_split_rate"]),
        },
        "artifacts": {
            "report": "REPORT.md",
            "manifest": "manifest.json",
            "claimed_ticket": "claimed_ticket.txt",
            "raw_reproduction": "reproduction_match_table.csv",
            "method_metrics": "method_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "strata_metrics": "strata_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "PID truth is a deterministic raw-waveform proxy, not external particle truth.",
            "Pile-up and saturation truths come from controlled injections into raw-ROOT-derived clean pulses.",
            "Bootstrap CIs resample held-out runs and should be read as run-transfer intervals.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "ticket_id": TICKET,
        "git_commit": git_commit(),
        "command": f"{sys.executable} scripts/s26c_1783800116_3081_430d48e6_pulse_pid_energy_timing_joint_inference_bakeoff.py",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "outputs_sha256": {
            p.name: base.sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
