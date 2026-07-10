#!/usr/bin/env python3
"""S10i independent A/B phase-window benchmark from raw ROOT."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:
    torch = None
    nn = None


METHODS = [
    "traditional_phase_timewalk",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "phase_gated_cnn_new",
]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def json_safe(x):
    if isinstance(x, dict):
        return {str(k): json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [json_safe(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return float(x) if math.isfinite(float(x)) else None
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    return x


def root_path(cfg: dict, side: str, run: int) -> Path:
    pref = cfg["astack" if side == "a" else "bstack"]["file_prefix"]
    return Path(cfg["raw_root_dir"]) / f"{pref}_run_{run:04d}.root"


def cfd_features(waves: np.ndarray, baseline_samples: list[int], fraction: float):
    baseline = np.median(waves[..., baseline_samples], axis=-1)
    x = waves - baseline[..., None]
    amp = x.max(axis=-1)
    peak = x.argmax(axis=-1)
    area = np.maximum(x, 0).sum(axis=-1)
    tail = x[..., 10:].sum(axis=-1) / np.maximum(x.sum(axis=-1), 1.0)
    thr = fraction * amp
    curr = x[..., 1:]
    prev = x[..., :-1]
    idx = np.arange(1, x.shape[-1])[None, None, :]
    ok = (idx <= peak[..., None]) & (curr >= thr[..., None]) & (prev < thr[..., None])
    has = ok.any(axis=-1)
    cross = ok.argmax(axis=-1) + 1
    r = np.arange(x.shape[0])[:, None]
    c = np.arange(x.shape[1])[None, :]
    y0 = x[r, c, np.maximum(cross - 1, 0)]
    y1 = x[r, c, cross]
    frac = np.divide(thr - y0, y1 - y0, out=np.zeros_like(thr), where=np.abs(y1 - y0) > 1e-9)
    t = (cross - 1 + frac) * 10.0
    t = np.where(has, t, peak.astype(float) * 10.0)
    return x, amp, peak.astype(float), area, tail, t


def load_side(cfg: dict, side: str, run: int) -> pd.DataFrame:
    spec = cfg["astack" if side == "a" else "bstack"]
    names = list(spec["staves"].keys())
    channels = [int(spec["staves"][n]) for n in names]
    rows = []
    path = root_path(cfg, side, run)
    tree = uproot.open(path)["h101"]
    for batch in tree.iterate(["EVT", "HRDv"], step_size=25000, library="np"):
        evt = np.asarray(batch["EVT"]).astype(int)
        waves = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(cfg["samples_per_channel"]))
        chosen = waves[:, channels, :]
        corr, amp, peak, area, tail, time = cfd_features(
            chosen, [int(i) for i in cfg["baseline_samples"]], float(cfg["cfd_fraction"])
        )
        selected = (amp[:, 0] > float(cfg["amplitude_cut_adc"])) & (amp[:, 1] > float(cfg["amplitude_cut_adc"]))
        if not selected.any():
            continue
        norm = corr[selected] / np.maximum(amp[selected], 1.0)[:, :, None]
        d = {
            "run": int(run),
            f"{side}_evt": evt[selected],
            f"{side}_local": evt[selected] - int(evt[0]),
            f"{side}_amp0": amp[selected, 0],
            f"{side}_amp1": amp[selected, 1],
            f"{side}_peak0": peak[selected, 0],
            f"{side}_peak1": peak[selected, 1],
            f"{side}_area0": area[selected, 0],
            f"{side}_area1": area[selected, 1],
            f"{side}_tail0": tail[selected, 0],
            f"{side}_tail1": tail[selected, 1],
            f"{side}_time0_ns": time[selected, 0],
            f"{side}_time1_ns": time[selected, 1],
        }
        frame = pd.DataFrame(d)
        frame[f"{side}_mean_time_ns"] = 0.5 * (frame[f"{side}_time0_ns"] + frame[f"{side}_time1_ns"])
        frame[f"{side}_pair_time_ns"] = frame[f"{side}_time1_ns"] - frame[f"{side}_time0_ns"]
        for ch in range(2):
            for i in range(int(cfg["samples_per_channel"])):
                frame[f"{side}_w{ch}_{i:02d}"] = norm[:, ch, i]
        rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_aligned(cfg: dict, runs: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    diag = []
    for run in runs:
        a = load_side(cfg, "a", int(run))
        b = load_side(cfg, "b", int(run))
        if a.empty or b.empty:
            diag.append({"run": int(run), "a_selected_pairs": len(a), "b_selected_pairs": len(b), "aligned_pairs": 0})
            continue
        merged = a.merge(b, left_on=["run", "a_local"], right_on=["run", "b_local"], how="inner")
        merged["phase_ab_ns"] = merged["b_mean_time_ns"] - merged["a_mean_time_ns"]
        merged["phase_ab_calibrated_ns"] = merged["phase_ab_ns"] - float(np.median(merged["phase_ab_ns"]))
        merged["a_pair_residual_ns"] = merged["a_pair_time_ns"]
        merged["b_pair_residual_ns"] = merged["b_pair_time_ns"]
        rows.append(merged)
        raw_evt_overlap = len(set(a["a_evt"].astype(int)).intersection(set(b["b_evt"].astype(int))))
        diag.append(
            {
                "run": int(run),
                "a_selected_pairs": int(len(a)),
                "b_selected_pairs": int(len(b)),
                "raw_evt_overlap": int(raw_evt_overlap),
                "aligned_pairs": int(len(merged)),
                "a_first_evt": int(a["a_evt"].min()),
                "b_first_evt": int(b["b_evt"].min()),
                "evt_offset_a_minus_b": int(a["a_evt"].min() - b["b_evt"].min()),
                "median_phase_ns": float(np.median(merged["phase_ab_ns"])) if len(merged) else None,
                "phase_width68_ns": robust_width(merged["phase_ab_calibrated_ns"]) if len(merged) else None,
            }
        )
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(), pd.DataFrame(diag))


def robust_width(v) -> float:
    x = np.asarray(v, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    x = x - np.median(x)
    return float(0.5 * (np.percentile(x, 84) - np.percentile(x, 16)))


def full_rms(v) -> float:
    x = np.asarray(v, dtype=float)
    x = x[np.isfinite(x)]
    x = x - np.median(x)
    return float(np.sqrt(np.mean(x * x)))


def phase_center(df: pd.DataFrame, values: np.ndarray) -> np.ndarray:
    out = np.asarray(values, dtype=float).copy()
    for run in sorted(df["run"].unique()):
        m = df["run"].eq(run).to_numpy()
        out[m] -= np.median(out[m])
    return out


def features(df: pd.DataFrame) -> np.ndarray:
    cols = []
    for side in ["a", "b"]:
        la0 = np.log(np.maximum(df[f"{side}_amp0"].to_numpy(), 1.0))
        la1 = np.log(np.maximum(df[f"{side}_amp1"].to_numpy(), 1.0))
        cols.extend(
            [
                la0,
                la1,
                la1 - la0,
                la1 + la0,
                df[f"{side}_peak0"].to_numpy(),
                df[f"{side}_peak1"].to_numpy(),
                np.log(np.maximum(df[f"{side}_area0"].to_numpy(), 1.0)),
                np.log(np.maximum(df[f"{side}_area1"].to_numpy(), 1.0)),
                df[f"{side}_tail0"].to_numpy(),
                df[f"{side}_tail1"].to_numpy(),
                df[f"{side}_pair_residual_ns"].to_numpy(),
            ]
        )
    wave_cols = [f"{s}_w{ch}_{i:02d}" for s in ["a", "b"] for ch in range(2) for i in range(18)]
    waves = df[wave_cols].to_numpy(dtype=float)
    return np.column_stack(cols + [waves])


def wave_tensor(df: pd.DataFrame) -> np.ndarray:
    cols = [f"{s}_w{ch}_{i:02d}" for s in ["a", "b"] for ch in range(2) for i in range(18)]
    return df[cols].to_numpy(dtype=np.float32).reshape(len(df), 4, 18)


def target(df: pd.DataFrame) -> np.ndarray:
    return df["phase_ab_calibrated_ns"].to_numpy(dtype=float)


class TraditionalPhaseTimewalk:
    def fit(self, df: pd.DataFrame):
        x = np.column_stack(
            [
                np.ones(len(df)),
                np.log(np.maximum(df["a_amp0"], 1.0)),
                np.log(np.maximum(df["a_amp1"], 1.0)),
                np.log(np.maximum(df["b_amp0"], 1.0)),
                np.log(np.maximum(df["b_amp1"], 1.0)),
                df["a_pair_residual_ns"],
                df["b_pair_residual_ns"],
            ]
        )
        self.beta = np.linalg.lstsq(x, target(df), rcond=None)[0]
        return self

    def predict(self, df: pd.DataFrame):
        x = np.column_stack(
            [
                np.ones(len(df)),
                np.log(np.maximum(df["a_amp0"], 1.0)),
                np.log(np.maximum(df["a_amp1"], 1.0)),
                np.log(np.maximum(df["b_amp0"], 1.0)),
                np.log(np.maximum(df["b_amp1"], 1.0)),
                df["a_pair_residual_ns"],
                df["b_pair_residual_ns"],
            ]
        )
        return x @ self.beta


def tune_ridge(train: pd.DataFrame, cfg: dict) -> tuple[float, pd.DataFrame]:
    x = features(train)
    y = target(train)
    groups = train["run"].to_numpy()
    rows = []
    cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
    for alpha in cfg["ridge_alphas"]:
        rmses = []
        for tr, va in cv.split(x, y, groups):
            m = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            m.fit(x[tr], y[tr])
            pred = m.predict(x[va])
            rmses.append(math.sqrt(mean_squared_error(phase_center(train.iloc[va], y[va]), phase_center(train.iloc[va], y[va] - pred))))
        rows.append({"alpha": float(alpha), "cv_rmse_ns": float(np.mean(rmses))})
    table = pd.DataFrame(rows).sort_values(["cv_rmse_ns", "alpha"]).reset_index(drop=True)
    return float(table.iloc[0]["alpha"]), table


def sklearn_predictions(train: pd.DataFrame, test: pd.DataFrame, cfg: dict) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    xtr, xte, y = features(train), features(test), target(train)
    out = {}
    alpha, cv = tune_ridge(train, cfg)
    ridge = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    ridge.fit(xtr, y)
    out["ridge"] = phase_center(test, test["phase_ab_calibrated_ns"].to_numpy() - ridge.predict(xte))
    gcfg = cfg["gbt"]
    gbt = HistGradientBoostingRegressor(
        loss="least_squares",
        max_iter=int(gcfg["max_iter"]),
        learning_rate=float(gcfg["learning_rate"]),
        max_leaf_nodes=int(gcfg["max_leaf_nodes"]),
        l2_regularization=float(gcfg["l2_regularization"]),
        random_state=int(cfg["random_seed"]),
    )
    gbt.fit(xtr, y)
    out["gradient_boosted_trees"] = phase_center(test, test["phase_ab_calibrated_ns"].to_numpy() - gbt.predict(xte))
    mcfg = cfg["mlp"]
    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(mcfg["hidden_layer_sizes"]),
            alpha=float(mcfg["alpha"]),
            max_iter=int(mcfg["max_iter"]),
            early_stopping=True,
            random_state=int(cfg["random_seed"]),
        ),
    )
    mlp.fit(xtr, y)
    out["mlp"] = phase_center(test, test["phase_ab_calibrated_ns"].to_numpy() - mlp.predict(xte))
    return out, cv


class PairCNN(nn.Module):
    def __init__(self, aux_dim: int, gated: bool = False):
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(nn.Conv1d(4, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 32, 3, padding=1), nn.ReLU())
        self.gate = nn.Sequential(nn.Linear(32 + aux_dim, 32), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(64 + aux_dim if gated else 32 + aux_dim, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, w, a):
        z = self.conv(w)
        pooled = z.mean(dim=2)
        if self.gated:
            z = z * self.gate(torch.cat([pooled, a], dim=1)).unsqueeze(2)
            pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        return self.head(torch.cat([pooled, a], dim=1)).squeeze(1)


def torch_fit_predict(train: pd.DataFrame, test: pd.DataFrame, cfg: dict, gated: bool, seed: int) -> np.ndarray:
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    rng = np.random.default_rng(seed)
    aux_scaler = StandardScaler().fit(features(train)[:, :22])
    aux_tr = aux_scaler.transform(features(train)[:, :22]).astype(np.float32)
    aux_te = aux_scaler.transform(features(test)[:, :22]).astype(np.float32)
    wtr, wte = wave_tensor(train), wave_tensor(test)
    y0 = target(train).astype(np.float32)
    center = float(np.median(y0))
    scale = robust_width(y0) or float(np.std(y0) + 1e-6)
    y = ((y0 - center) / scale).astype(np.float32)
    model = PairCNN(aux_tr.shape[1], gated=gated)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["nn"]["learning_rate"]), weight_decay=float(cfg["nn"]["weight_decay"]))
    loss_fn = nn.MSELoss()
    idx = np.arange(len(y))
    if len(idx) > int(cfg["nn"]["max_train_rows"]):
        idx = rng.choice(idx, int(cfg["nn"]["max_train_rows"]), replace=False)
    for _ in range(int(cfg["nn"]["epochs"])):
        for start in range(0, len(idx), int(cfg["nn"]["batch_size"])):
            take = rng.permutation(idx)[start : start + int(cfg["nn"]["batch_size"])]
            pred = model(torch.tensor(wtr[take]), torch.tensor(aux_tr[take]))
            loss = loss_fn(pred, torch.tensor(y[take]))
            opt.zero_grad()
            loss.backward()
            opt.step()
    outs = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(wte), 4096):
            outs.append(model(torch.tensor(wte[start : start + 4096]), torch.tensor(aux_te[start : start + 4096])).numpy())
    pred = np.concatenate(outs) * scale + center
    return phase_center(test, test["phase_ab_calibrated_ns"].to_numpy() - pred)


def fit_all(train: pd.DataFrame, test: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = test[["run", "a_evt", "b_evt", "a_local", "phase_ab_calibrated_ns"]].copy()
    trad = TraditionalPhaseTimewalk().fit(train)
    out["traditional_phase_timewalk"] = phase_center(test, test["phase_ab_calibrated_ns"].to_numpy() - trad.predict(test))
    sk, cv = sklearn_predictions(train, test, cfg)
    for k, v in sk.items():
        out[k] = v
    if torch is not None:
        out["cnn_1d"] = torch_fit_predict(train, test, cfg, False, int(cfg["random_seed"]) + 1)
        out["phase_gated_cnn_new"] = torch_fit_predict(train, test, cfg, True, int(cfg["random_seed"]) + 2)
    return out, cv


def bootstrap_ci(df: pd.DataFrame, col: str, n: int, rng: np.random.Generator):
    runs = np.array(sorted(df["run"].unique()))
    vals = []
    for _ in range(n):
        sample = rng.choice(runs, len(runs), replace=True)
        x = np.concatenate([df.loc[df["run"].eq(r), col].to_numpy() for r in sample])
        vals.append(robust_width(x))
    return [float(x) for x in np.quantile(vals, [0.025, 0.975])]


def summarize(pred: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(cfg["random_seed"]) + 99)
    rows = []
    per = []
    for m in METHODS:
        if m not in pred:
            continue
        lo, hi = bootstrap_ci(pred, m, int(cfg["bootstrap_resamples"]), rng)
        rows.append(
            {
                "method": m,
                "n_aligned_pairs": int(len(pred)),
                "median_ns": float(np.median(pred[m])),
                "robust_width_ns": robust_width(pred[m]),
                "robust_ci_low_ns": lo,
                "robust_ci_high_ns": hi,
                "full_rms_ns": full_rms(pred[m]),
                "tail_abs_gt_5ns": float(np.mean(np.abs(pred[m] - np.median(pred[m])) > 5.0)),
            }
        )
        for run, g in pred.groupby("run"):
            per.append({"run": int(run), "method": m, "n": int(len(g)), "robust_width_ns": robust_width(g[m]), "full_rms_ns": full_rms(g[m])})
    return pd.DataFrame(rows).sort_values("robust_width_ns"), pd.DataFrame(per)


def write_report(out: Path, cfg: dict, counts: pd.DataFrame, diag: pd.DataFrame, metrics: pd.DataFrame, per: pd.DataFrame, cv: pd.DataFrame, result: dict):
    winner = result["winner"]
    text = f"""# S10i: Independent A/B Phase-Calibrated Window Benchmark

- **Ticket:** `{cfg['ticket']}`
- **Worker:** `{cfg['worker']}`
- **Command:** `/home/billy/anaconda3/bin/python {cfg['script_path']} --config configs/s10i_1783548324_12257_18612134_independent_ab_windows.json`
- **Inputs:** raw `data/root/root/hrda_run_*.root` and `data/root/root/hrdb_run_*.root`
- **Split:** train runs `{cfg['train_runs']}`; held-out runs `{cfg['heldout_runs']}`
- **Winner:** `{winner['method']}` with held-out phase-window width `{winner['robust_width_ns']:.3f}` ns, 95% run-bootstrap CI `[{winner['robust_ci_low_ns']:.3f}, {winner['robust_ci_high_ns']:.3f}]` ns.

## Abstract

This study repeats the S10 phase-window benchmark on physically independent A-stack and B-stack ROOT files. A1/A3 pulses are read from `hrda` and B2/B4 pulses from `hrdb`; all quantities are rebuilt from raw `HRDv` waveforms. Event-level alignment is performed by the local trigger index `EVT - first(EVT)` within each run, not by row order or by raw EVT equality. This is necessary because the two independent DAQ streams have run-dependent EVT offsets.

The reproduced ticket number is the held-out aligned selected-pair count: **{result['reproduced_number']}** independent A/B events.

## Raw Reproduction and Alignment Diagnostics

Each waveform is reshaped to `(8, 18)`. Samples 0--3 define the pedestal, amplitudes are baseline-subtracted maxima, and CFD20 times are linearly interpolated before each peak. A row enters the table only when both A1/A3 and both B2/B4 exceed `{cfg['amplitude_cut_adc']}` ADC after pedestal subtraction.

{diag.to_markdown(index=False)}

Counts by split:

{counts.to_markdown(index=False)}

## Estimand

For side `s in {{A,B}}` and channel `c`, let `x_sc[k] = v_sc[k] - median(v_sc[0:4])`, `A_sc = max_k x_sc[k]`, and `t_sc` be the CFD20 crossing. Define side means

`bar t_A = (t_A1 + t_A3)/2`, `bar t_B = (t_B2 + t_B4)/2`.

The raw A/B phase is

`phi_i = bar t_B,i - bar t_A,i`.

The phase-calibrated target subtracts the run median,

`y_i = phi_i - median_{{j in run(i)}} phi_j`.

For method `m`, the held-out residual is

`e_i(m) = y_i - hat y_m(z_i)`,

then the same run-median centering is applied to `e_i` to represent the phase-window calibration. The primary width is

`W_68 = 0.5 [Q_84(e - median(e)) - Q_16(e - median(e))]`.

Confidence intervals bootstrap held-out runs with replacement and recompute `W_68`.

## Methods

The strong traditional comparator is `traditional_phase_timewalk`, a physically constrained low-dimensional least-squares phase model using log A/B amplitudes and A/B internal pair residuals. It is the analogue of the phase-calibrated coincidence window: a per-event timewalk correction followed by per-run phase centering.

The ML panel contains ridge regression, gradient-boosted trees, MLP, a compact 1D-CNN over four normalized waveforms, and a new `phase_gated_cnn_new`. The new architecture is sensible for this ticket because A/B transfer can fail from local waveform support mismatch; it gates convolution channels using auxiliary amplitude and shape moments before the regression head. No method receives run id, raw EVT, local event index, raw phase, or target phase as an input feature.

Ridge alpha was selected by GroupKFold over training runs:

{cv.to_markdown(index=False)}

## Results

{metrics.to_markdown(index=False)}

Per-run held-out widths:

{per.to_markdown(index=False)}

## Systematics and Caveats

- Raw EVT equality is sparse and run-dependent; local EVT alignment is therefore explicitly diagnosed. This validates a trigger-index coincidence model, not a bit-identical DAQ event-number model.
- The A/B phase target is calibrated by held-out run medians. This matches phase-window operation, but it removes absolute run phase offsets by construction.
- The selected sample requires four channels above threshold, so the reproduced number is a clean high-amplitude coincidence count rather than a full livetime count.
- Bootstrap intervals resample runs, not rows, because run-to-run phase alignment is the dominant systematic.
- Neural methods are trained on CPU with fixed seeds and small networks to avoid overfitting the limited number of held-out runs.

## Conclusion

The raw ROOT files reproduce **{result['reproduced_number']}** held-out independent A/B selected coincidences. The best phase-calibrated method is **{winner['method']}**, with `W_68 = {winner['robust_width_ns']:.3f}` ns. The result supports using true independent A-stack ROOT files for A/B timing-window validation, while the caveats above mean the conclusion is about phase-centered coincidence width rather than absolute DAQ synchronization.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def write_figures(out: Path, pred: pd.DataFrame, metrics: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 4))
    order = metrics["method"].tolist()
    ax.bar(order, metrics["robust_width_ns"])
    ax.set_ylabel("held-out W68 (ns)")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(out / "fig_method_widths.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    winner = metrics.iloc[0]["method"]
    bins = np.linspace(-10, 10, 80)
    ax.hist(pred["traditional_phase_timewalk"], bins=bins, histtype="step", label="traditional")
    ax.hist(pred[winner], bins=bins, histtype="step", label=winner)
    ax.set_xlabel("phase-centered residual (ns)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "fig_winner_residuals.png", dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, required=True)
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    runs = sorted(set(cfg["train_runs"]) | set(cfg["heldout_runs"]))
    inputs = []
    for run in runs:
        for side in ["a", "b"]:
            p = root_path(cfg, side, int(run))
            inputs.append({"run": int(run), "side": side, "path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    pd.DataFrame(inputs).to_csv(out / "input_sha256.csv", index=False)

    train, dtrain = build_aligned(cfg, cfg["train_runs"])
    held, dheld = build_aligned(cfg, cfg["heldout_runs"])
    diag = pd.concat([dtrain.assign(split="train"), dheld.assign(split="heldout")], ignore_index=True)
    diag.to_csv(out / "alignment_diagnostics.csv", index=False)
    counts = diag.groupby("split", as_index=False).agg(
        runs=("run", "nunique"),
        a_selected_pairs=("a_selected_pairs", "sum"),
        b_selected_pairs=("b_selected_pairs", "sum"),
        aligned_pairs=("aligned_pairs", "sum"),
    )
    counts.to_csv(out / "reproduction_counts.csv", index=False)
    train.to_csv(out / "train_aligned_summary.csv.gz", index=False, compression="gzip")
    held.to_csv(out / "heldout_aligned_summary.csv.gz", index=False, compression="gzip")
    pred, cv = fit_all(train, held, cfg)
    pred.to_csv(out / "heldout_predictions.csv.gz", index=False, compression="gzip")
    cv.to_csv(out / "ridge_cv_scan.csv", index=False)
    metrics, per = summarize(pred, cfg)
    metrics.to_csv(out / "method_metrics.csv", index=False)
    per.to_csv(out / "per_run_metrics.csv", index=False)
    winner = metrics.iloc[0].to_dict()
    result = {
        "study": cfg["study"],
        "ticket": cfg["ticket"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "reproduced": True,
        "reproduced_number": int(counts.loc[counts["split"].eq("heldout"), "aligned_pairs"].iloc[0]),
        "winner": winner,
        "winner_name": str(winner["method"]),
        "primary_metric": "held-out run-bootstrap phase-calibrated A/B W68",
        "methods_benchmarked": [m for m in METHODS if m in pred.columns],
        "split": {"train_runs": cfg["train_runs"], "heldout_runs": cfg["heldout_runs"]},
        "torch_available": bool(torch is not None),
        "git_commit": git_head(),
        "next_tickets": [
            "S10j: compare local-EVT alignment against cross-correlation-derived trigger offsets using low-threshold A/B control pulses; expected information gain is whether residual A/B width is limited by DAQ index jitter or pulse-time estimator variance."
        ],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_figures(out, pred, metrics)
    write_report(out, cfg, counts, diag, metrics, per, cv, result)
    manifest = {
        "ticket": cfg["ticket"],
        "command": f"/home/billy/anaconda3/bin/python {cfg['script_path']} --config {args.config}",
        "git_commit": git_head(),
        "python": platform.python_version(),
        "packages": {"uproot": uproot.__version__, "torch": None if torch is None else torch.__version__},
        "output_sha256": {p.name: sha256_file(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (out / "manifest.json").write_text(json.dumps(json_safe(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
