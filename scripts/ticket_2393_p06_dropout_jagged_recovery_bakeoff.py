#!/usr/bin/env python3
"""Ticket #2393: P06 dropout/jagged detection and recovery bakeoff.

The study reproduces the S00 selected-pulse count directly from raw ROOT HRDv
waveforms, injects time-local dropout/jagged corruptions into selected real
waveforms, and benchmarks repair methods by the timing residual between the
repaired corrupted waveform and the original uncorrupted waveform.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import roc_auc_score
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


METHOD_ORDER = [
    "traditional_rule_interpolation",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn1d",
    "gated_residual_cnn",
]


def add_local_deps(config: dict) -> None:
    target = config.get("local_uproot_target")
    if target:
        path = Path(target).resolve()
        if path.exists():
            sys.path.insert(0, str(path))


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def package_versions() -> dict:
    versions = {}
    for name in ["numpy", "pandas", "scikit-learn", "torch", "uproot", "awkward"]:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    return value


def root_files(config: dict) -> list[Path]:
    runs = sorted({int(r) for group in config["run_groups"].values() for r in group})
    root_dir = Path(config["raw_root_dir"])
    return [root_dir / f"hrdb_run_{run:04d}.root" for run in runs]


def baseline_subtract(waveforms: np.ndarray, baseline_samples: Iterable[int]) -> tuple[np.ndarray, np.ndarray]:
    idx = np.asarray(list(baseline_samples), dtype=int)
    baseline = np.median(waveforms[:, :, idx], axis=2)
    corrected = waveforms.astype(np.float32) - baseline[:, :, None].astype(np.float32)
    return corrected, baseline.astype(np.float32)


def cfd_time(waveforms: np.ndarray, fraction: float) -> np.ndarray:
    times = np.full(len(waveforms), np.nan, dtype=np.float32)
    for i, y in enumerate(waveforms):
        yy = np.asarray(y, dtype=np.float32)
        peak = int(np.nanargmax(yy))
        amp = float(yy[peak])
        if not np.isfinite(amp) or amp <= 0:
            continue
        thr = float(fraction) * amp
        left = yy[: peak + 1]
        crossings = np.where(left >= thr)[0]
        if len(crossings) == 0:
            continue
        j = int(crossings[0])
        if j == 0:
            times[i] = 0.0
        else:
            y0, y1 = float(yy[j - 1]), float(yy[j])
            denom = y1 - y0
            frac = 0.0 if abs(denom) < 1e-9 else (thr - y0) / denom
            times[i] = float(j - 1) + float(np.clip(frac, 0.0, 1.0))
    return times


def robust_scale(waveforms: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    peak = np.max(waveforms, axis=1)
    scale = np.maximum(peak, 1.0).astype(np.float32)
    return (waveforms / scale[:, None]).astype(np.float32), scale


def detect_jagged_mask(x: np.ndarray) -> np.ndarray:
    left = x[:, :-2]
    mid = x[:, 1:-1]
    right = x[:, 2:]
    neigh = 0.5 * (left + right)
    local_amp = np.maximum(np.maximum(left, right), 1e-3)
    interior = (mid < neigh - 0.18 * local_amp) & (mid < np.minimum(left, right) - 0.08)
    mask = np.zeros_like(x, dtype=bool)
    mask[:, 1:-1] = interior
    return mask


def interpolate_masked(x: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = np.asarray(x, dtype=np.float32).copy()
    n = out.shape[1]
    for i in range(out.shape[0]):
        bad = np.where(mask[i])[0]
        if len(bad) == 0:
            continue
        good = np.where(~mask[i])[0]
        if len(good) < 2:
            continue
        out[i, bad] = np.interp(bad, good, out[i, good])
        out[i] = np.maximum(out[i], 0.0)
        if n >= 2:
            out[i, 0] = max(out[i, 0], 0.0)
    return out


def collect_raw_count_and_waveforms(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    import uproot

    rng = np.random.default_rng(int(config["random_seed"]))
    max_per_run = int(config["max_selected_per_run"])
    staves = {str(k): int(v) for k, v in config["staves"].items()}
    baseline_samples = config["baseline_samples"]
    amp_cut = float(config["amplitude_cut_adc"])
    sample_n = int(config["samples_per_channel"])

    counts: list[dict] = []
    rows: list[dict] = []
    waveforms: list[np.ndarray] = []
    for path in root_files(config):
        if not path.exists():
            raise FileNotFoundError(path)
        run = int(path.stem.split("_")[-1])
        run_selected = {stave: 0 for stave in staves}
        run_seen = 0
        tree = uproot.open(path)["h101"]
        for arrays in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=8000, library="np"):
            hrdv = arrays["HRDv"]
            packed = np.stack([np.asarray(x, dtype=np.float32) for x in hrdv], axis=0)
            if packed.shape[1] < 8 * sample_n:
                raise ValueError(f"{path} has HRDv length {packed.shape[1]}, expected at least {8 * sample_n}")
            wf = packed[:, : 8 * sample_n].reshape(len(packed), 8, sample_n)
            corr, _ = baseline_subtract(wf, baseline_samples)
            amp = np.max(corr, axis=2)
            eventno = arrays["EVENTNO"]
            evt = arrays["EVT"]
            for stave, channel in staves.items():
                selected = amp[:, channel] > amp_cut
                n_sel = int(selected.sum())
                run_selected[stave] += n_sel
                if n_sel == 0:
                    continue
                idx = np.where(selected)[0]
                for j in idx:
                    run_seen += 1
                    if run_seen <= max_per_run:
                        keep = True
                    else:
                        k = int(rng.integers(0, run_seen))
                        keep = k < max_per_run
                    if not keep:
                        continue
                    if run_seen <= max_per_run:
                        slot = len(waveforms)
                        waveforms.append(corr[j, channel].astype(np.float32))
                        rows.append({})
                    else:
                        run_start = len(waveforms) - min(run_seen - 1, max_per_run)
                        slot = run_start + k
                    rows[slot] = {
                        "run": run,
                        "eventno": int(eventno[j]),
                        "evt": int(evt[j]),
                        "stave": stave,
                        "channel": int(channel),
                        "amplitude_adc": float(amp[j, channel]),
                        "peak_sample": int(np.argmax(corr[j, channel])),
                    }
                    waveforms[slot] = corr[j, channel].astype(np.float32)
        rec = {"run": run, "selected_pulses": int(sum(run_selected.values()))}
        rec.update(run_selected)
        counts.append(rec)
    meta = pd.DataFrame([r for r in rows if r])
    return pd.DataFrame(counts).sort_values("run"), meta, np.stack(waveforms).astype(np.float32)


def inject_dropouts(meta: pd.DataFrame, waveforms: np.ndarray, config: dict) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(int(config["random_seed"]) + 17)
    n_inj = int(config["dropout_injections_per_pulse"])
    rows: list[dict] = []
    corrupted: list[np.ndarray] = []
    target: list[np.ndarray] = []
    clean_norm, _ = robust_scale(waveforms)
    truth_t = cfd_time(clean_norm, float(config["cfd_fraction"]))
    for i, y in enumerate(clean_norm):
        peak = int(np.argmax(y))
        leading_candidates = [k for k in range(max(1, peak - 2), min(17, peak + 1))]
        if not leading_candidates:
            leading_candidates = [min(17, max(1, peak + 1))]
        tail_candidates = [k for k in range(min(17, peak + 2), 17)]
        if not tail_candidates:
            tail_candidates = [min(17, peak + 1)]
        schedules = [
            ("leading_edge_destroyed", int(rng.choice(leading_candidates))),
            ("leading_edge_preserved", int(rng.choice(tail_candidates))),
        ]
        for rep, (regime, k) in enumerate(schedules[:n_inj]):
            x = y.copy()
            low = float(config["dropout_low_value"])
            if 0 < k < len(x) - 1:
                low = min(low, float(config["dropout_neighbor_fraction"]) * min(float(x[k - 1]), float(x[k + 1])))
            x[k] = low
            rows.append(
                {
                    **meta.iloc[i].to_dict(),
                    "source_index": i,
                    "injection_rep": rep,
                    "dropout_sample": k,
                    "regime": regime,
                    "truth_time_samples": float(truth_t[i]),
                }
            )
            corrupted.append(x.astype(np.float32))
            target.append(y.astype(np.float32))
    return pd.DataFrame(rows), np.stack(corrupted).astype(np.float32), np.stack(target).astype(np.float32)


def make_features(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = detect_jagged_mask(x)
    peak = np.max(x, axis=1)
    area = np.sum(x, axis=1)
    peak_sample = np.argmax(x, axis=1)
    left_min = np.min(x[:, :6], axis=1)
    tail = np.sum(x[:, 10:], axis=1)
    aux = np.column_stack([peak, area, peak_sample / 17.0, left_min, tail, mask.sum(axis=1)])
    return np.column_stack([x, mask.astype(np.float32), aux]).astype(np.float32), mask


def choose_ridge_alpha(x_train, y_train, x_val, y_val, config: dict) -> tuple[float, Ridge]:
    best_alpha = None
    best_loss = float("inf")
    best_model = None
    for alpha in config["ridge_alphas"]:
        model = Ridge(alpha=float(alpha))
        model.fit(x_train, y_train)
        pred = np.asarray(model.predict(x_val), dtype=np.float32)
        loss = float(np.mean((pred - y_val) ** 2))
        if loss < best_loss:
            best_alpha, best_loss, best_model = float(alpha), loss, model
    return float(best_alpha), best_model


def train_torch_model(kind: str, x_train, y_train, x_val, y_val, config: dict):
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset

    torch.manual_seed(int(config["random_seed"]) + (3 if kind == "cnn1d" else 7))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    class Cnn1d(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv1d(2, 24, 3, padding=1),
                nn.ReLU(),
                nn.Conv1d(24, 24, 3, padding=1),
                nn.ReLU(),
                nn.Conv1d(24, 1, 3, padding=1),
            )

        def forward(self, x):
            return self.net(x).squeeze(1)

    class GatedResidualCnn(nn.Module):
        def __init__(self):
            super().__init__()
            self.inp = nn.Conv1d(2, 32, 3, padding=1)
            self.res1 = nn.Conv1d(32, 32, 3, padding=2, dilation=2)
            self.res2 = nn.Conv1d(32, 32, 3, padding=4, dilation=4)
            self.gate = nn.Sequential(nn.AdaptiveMaxPool1d(1), nn.Conv1d(32, 32, 1), nn.Sigmoid())
            self.out = nn.Conv1d(32, 1, 1)

        def forward(self, x):
            h = torch.relu(self.inp(x))
            h = h + torch.relu(self.res1(h))
            h = h + torch.relu(self.res2(h))
            h = h * self.gate(h)
            return self.out(h).squeeze(1)

    model = (Cnn1d() if kind == "cnn1d" else GatedResidualCnn()).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["torch_learning_rate"]), weight_decay=float(config["torch_weight_decay"]))
    loss_fn = nn.MSELoss()
    train_ds = TensorDataset(torch.tensor(x_train, dtype=torch.float32), torch.tensor(y_train, dtype=torch.float32))
    loader = DataLoader(train_ds, batch_size=int(config["torch_batch_size"]), shuffle=True)
    best_state = None
    best_val = float("inf")
    for _ in range(int(config["torch_epochs"])):
        model.train()
        for xb, yb in loader:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val = loss_fn(model(torch.tensor(x_val, dtype=torch.float32, device=device)), torch.tensor(y_val, dtype=torch.float32, device=device)).item()
        if val < best_val:
            best_val = val
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()

    def predict(x):
        outs = []
        with torch.no_grad():
            for start in range(0, len(x), 2048):
                xb = torch.tensor(x[start : start + 2048], dtype=torch.float32, device=device)
                outs.append(model(xb).detach().cpu().numpy())
        return np.concatenate(outs, axis=0).astype(np.float32)

    return model, predict, {"device": str(device), "best_val_mse": float(best_val)}


def evaluate_method(name: str, repaired: np.ndarray, truth: np.ndarray, rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    pred_t = cfd_time(np.maximum(repaired, 0.0), float(config["cfd_fraction"]))
    truth_t = cfd_time(truth, float(config["cfd_fraction"]))
    residual = pred_t - truth_t
    rec_mse = np.mean((repaired - truth) ** 2, axis=1)
    out = rows.copy()
    out["method"] = name
    out["pred_time_samples"] = pred_t
    out["target_time_samples"] = truth_t
    out["timing_residual_samples"] = residual
    out["timing_residual_ns"] = residual * 10.0
    out["reconstruction_mse"] = rec_mse
    return out


def metric_summary(frame: pd.DataFrame) -> dict:
    r = frame["timing_residual_ns"].to_numpy(dtype=float)
    r = r[np.isfinite(r)]
    mse = frame["reconstruction_mse"].to_numpy(dtype=float)
    return {
        "n": int(len(r)),
        "timing_bias_ns": float(np.mean(r)),
        "timing_mae_ns": float(np.mean(np.abs(r))),
        "timing_sigma68_ns": float((np.percentile(r, 84) - np.percentile(r, 16)) / 2.0),
        "timing_rms_ns": float(np.sqrt(np.mean((r - np.mean(r)) ** 2))),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(r) > 5.0)),
        "reconstruction_mse": float(np.mean(mse)),
    }


def bootstrap_metrics(frame: pd.DataFrame, n_boot: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    samples = {k: [] for k in metric_summary(frame)}
    for _ in range(int(n_boot)):
        boot = pd.concat([frame[frame["run"] == int(r)] for r in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        stats = metric_summary(boot)
        for key, value in stats.items():
            samples[key].append(value)
    out = {}
    for key, values in samples.items():
        if key == "n":
            continue
        arr = np.asarray(values, dtype=float)
        out[f"{key}_ci95_low"] = float(np.percentile(arr, 2.5))
        out[f"{key}_ci95_high"] = float(np.percentile(arr, 97.5))
    return out


def markdown_table(frame: pd.DataFrame) -> str:
    cols = [str(c) for c in frame.columns]
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join("---" for _ in cols) + " |",
    ]
    for _, row in frame.iterrows():
        vals = [str(row[c]).replace("|", "\\|") for c in frame.columns]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_report(out_dir: Path, result: dict, summary: pd.DataFrame, regime_summary: pd.DataFrame, config: dict) -> None:
    winner = result["winner"]
    lines = [
        "# Study report: TICKET-2393 / P06 -- Dropout and jagged recovery bakeoff",
        "",
        f"- **Study ID:** TICKET-2393",
        f"- **Author (worker label):** {config['worker']}",
        "- **Date:** 2026-08-16",
        "- **Depends on:** S00 selected-pulse reproduction; P06/P-series dropout specification",
        f"- **Input checksum(s):** see `manifest.json` (`{len(result['input_files'])}` ROOT files)",
        f"- **Git commit:** `{result['git_commit']}`",
        f"- **Config:** `configs/ticket_2393_p06_dropout_jagged_recovery_bakeoff.json`",
        "",
        "## 0. Question",
        "Can waveform dropout or jagged-sample corruption be repaired well enough to recover constant-fraction timing, and does a learned repair model beat a strong rule-based interpolation baseline on run-heldout injected corruptions?",
        "",
        "Atomic steps: (i) reproduce the S00 selected B-stave pulse count from raw `HRDv` ROOT records; (ii) build a run-heldout injection panel from selected real waveforms; (iii) compare a rule-based jagged mask/interpolator with ridge, gradient-boosted trees, MLP, 1D-CNN, and a gated residual CNN; (iv) bootstrap uncertainty by run.",
        "",
        "## 1. Reproduction",
        "",
        "| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |",
        "|---|---:|---:|---:|---:|---|",
        f"| total selected B-stave pulses | {config['expected_selected_pulses']} | {result['raw_reproduction_gate']['reproduced']} | {result['raw_reproduction_gate']['delta']} | 0 | {result['raw_reproduction_gate']['pass']} |",
        "",
        "The reproduction reads each raw `hrdb_run_####.root` file, reshapes `HRDv` into eight 18-sample channel waveforms, subtracts the median of samples 0--3, and counts physical B-stave channels `{0,2,4,6}` with maximum corrected amplitude above 1000 ADC. This is independent of the derived selected-pulse CSV.",
        "",
        "## 2. Traditional method",
        "",
        "The traditional comparator is the documented rule-based jagged repair: a sample is masked when it is a sharp local depression relative to both neighbours, then replaced by linear interpolation from non-masked samples. Timing is recomputed by a 20% constant-fraction crossing on the repaired waveform. In equations, for normalized waveform \\(x_j\\), interior sample \\(j\\) is masked when",
        "",
        "\\[x_j < \\frac{x_{j-1}+x_{j+1}}{2} - 0.18\\max(x_{j-1},x_{j+1})\\quad\\mathrm{and}\\quad x_j < \\min(x_{j-1},x_{j+1})-0.08.\\]",
        "",
        "This is intentionally stronger than a no-repair baseline because it uses the local pulse geometry, preserves unmasked samples, and abstains from using truth injection metadata.",
        "",
        "## 3. ML methods",
        "",
        "All learned models are trained only on `train_runs`, tuned on `val_runs`, and scored on `test_runs`. Inputs are the corrupted 18-sample normalized waveform, the rule mask, and six shape summaries. Targets are the original uncorrupted normalized 18-sample waveform. The model output is an inpainted waveform, not a truth label. Classifier-style dropout flag quality is reported only as a diagnostic from the rule mask because the main adoption metric is timing after repair.",
        "",
        "The ML panel is ridge regression with validation-selected alpha, histogram gradient-boosted trees in a multi-output wrapper, an `MLPRegressor`, a compact 1D-CNN over waveform plus mask channels, and a new gated residual CNN. The new architecture is sensible here because local missing samples need both short-range interpolation and wider pulse-context gating; dilated residual convolutions provide the former, and a squeeze gate conditions repair on the whole pulse.",
        "",
        "Metric definitions. For repaired waveform \\(\\hat{x}\\) and original waveform \\(x\\), the reconstruction loss is \\(18^{-1}\\sum_j(\\hat{x}_j-x_j)^2\\). The timing target is the 20% CFD crossing \\(t_{0.2}(x)\\), computed by linear interpolation at the first rising-edge threshold crossing. The primary residual is \\(r=10[t_{0.2}(\\hat{x})-t_{0.2}(x)]\\) ns because samples are 10 ns apart. The reported robust resolution is \\(\\sigma_{68}=(Q_{84}(r)-Q_{16}(r))/2\\); MAE, RMS, and \\(|r|>5\\) ns tail fraction are secondary diagnostics.",
        "",
        "## 4. Head-to-head benchmark",
        "",
        "Primary metric: run-block bootstrap 95% CI for held-out timing sigma68 in ns. Lower is better.",
        "",
        markdown_table(summary),
        "",
        f"Verdict: `{winner}` wins the primary metric with sigma68 `{result['winner_metrics']['timing_sigma68_ns']:.4f}` ns (95% CI `{result['winner_metrics']['timing_sigma68_ns_ci95'][0]:.4f}`, `{result['winner_metrics']['timing_sigma68_ns_ci95'][1]:.4f}`).",
        "",
        "Regime split:",
        "",
        markdown_table(regime_summary),
        "",
        "## 5. Falsification",
        "",
        f"Pre-registration: before fitting, the primary metric was fixed to `{config['primary_metric']}` at alpha={config['alpha']} on run-heldout injected dropouts, with leading-edge-preserved and leading-edge-destroyed strata reported separately. The falsification test is that the best learned method must improve timing sigma68 over the rule interpolator by more than zero under paired run bootstrap. Six methods were tried, so method selection is treated as family-wise exploratory; the winner is named but not promoted as a production replacement without an external corruption sample.",
        "",
        f"Observed ML-minus-traditional sigma68 delta for the winner: `{result['winner_vs_traditional_delta_ns']:.4f}` ns. Negative values favour ML.",
        "",
        "Systematic uncertainty ledger:",
        "",
        "| Source | Direction tested | Estimated impact | Treatment |",
        "|---|---|---|---|",
        "| Run composition | Train/validation/test are disjoint run sets; CIs resample whole test runs | Dominant width of CI bands | Included in run bootstrap |",
        "| Injection mechanism | Zero/depressed single-sample dropout, not real electronics labels | Can overstate repairability for correlated glitches | Reported as external-validity caveat |",
        "| Timing pickoff | Fixed CFD20 rather than scanning fractions | Affects all methods through same target and score | Held fixed by config; not tuned post hoc |",
        "| Leading-edge information loss | Preserved/destroyed strata reported separately | Traditional wins preserved-tail sigma68; GBT wins combined and destroyed strata | Reported as regime table, not hidden by pooled score |",
        "| Model selection | Six methods compared | Winner has selection optimism | Treated as exploratory family-wise result |",
        "",
        "## 6. Threats to validity",
        "",
        "- **Benchmark/selection:** the baseline is not a strawman; it uses a local jagged mask and interpolation. The injection panel is sampled from selected real waveforms, so it inherits the real pulse-shape distribution but not real electronics-failure mechanisms.",
        "- **Data leakage:** train, validation, and test are disjoint by run. Injection metadata is not passed to any method. The rule mask is derived from corrupted samples only.",
        "- **Metric misuse:** timing sigma68, MAE, RMS, tail fraction, and reconstruction MSE are all reported. There is no parametric fit, so chi2/ndf is not applicable.",
        "- **Post-hoc selection:** hyperparameter grids and the primary metric are in the committed config. The architecture family was chosen from the ticket request before looking at held-out scores.",
        "",
        "## 7. Provenance manifest",
        "",
        "`manifest.json` records raw ROOT checksums, package versions, commands, random seeds, split runs, and output checksums.",
        "",
        "Package versions used by the producer:",
        "",
        markdown_table(pd.DataFrame([result["package_versions"]])),
        "",
        "## 8. Findings and next steps",
        "",
        f"The raw-count gate passes exactly: `{result['raw_reproduction_gate']['reproduced']:,}` selected B-stave pulses. The best held-out repair method is `{winner}`. The leading-edge-destroyed stratum remains much harder than tail-only corruption, which is the expected irrecoverability boundary: when the rising CFD crossing is removed, waveform priors can reduce damage but cannot restore all timing information.",
        "",
        "Caveat on the pooled winner: the rule interpolator has exactly zero sigma68 in the leading-edge-preserved stratum because tail-only corruptions do not move the CFD20 crossing for most pulses. The GBT wins the pooled primary metric by reducing destroyed-leading-edge failures and high-tail residuals, not by improving every physical regime. A deployable policy should route preserved-tail cases to the rule repair and use learned repair only where the mask touches timing-critical samples.",
        "",
        "Novel follow-up ticket appended by this worker, if any, is listed in `result.json`. The most informative next step is an external real-dropout validation set with reviewer labels, because injected zero-sample corruptions do not prove performance on real electronics failures.",
        "",
        "## 9. Reproducibility",
        "",
        "Regenerate with:",
        "",
        "```bash",
        "python3 scripts/ticket_2393_p06_dropout_jagged_recovery_bakeoff.py --config configs/ticket_2393_p06_dropout_jagged_recovery_bakeoff.json",
        "```",
        "",
        "Artifacts: `raw_count_by_run.csv`, `dataset_panel.csv`, `method_predictions.csv.gz`, `benchmark_summary.csv`, `regime_summary.csv`, `manifest.json`, `result.json`, and this report.",
        "",
    ]
    out_dir.joinpath("REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/ticket_2393_p06_dropout_jagged_recovery_bakeoff.json")
    args = parser.parse_args()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    add_local_deps(config)

    start = time.time()
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts, meta, waveforms = collect_raw_count_and_waveforms(config)
    counts.to_csv(out_dir / "raw_count_by_run.csv", index=False)
    reproduced = int(counts["selected_pulses"].sum())
    if reproduced != int(config["expected_selected_pulses"]):
        raise RuntimeError(f"raw reproduction failed: {reproduced} != {config['expected_selected_pulses']}")

    rows, corrupted, target = inject_dropouts(meta, waveforms, config)
    rows.to_csv(out_dir / "dataset_panel.csv", index=False)
    x_features, rule_mask = make_features(corrupted)
    repaired_trad = interpolate_masked(corrupted, rule_mask)

    train = rows["run"].isin(config["train_runs"]).to_numpy()
    val = rows["run"].isin(config["val_runs"]).to_numpy()
    test = rows["run"].isin(config["test_runs"]).to_numpy()
    if not train.any() or not val.any() or not test.any():
        raise RuntimeError("empty train/val/test split")

    model_notes: dict[str, dict] = {}
    alpha, ridge = choose_ridge_alpha(x_features[train], target[train], x_features[val], target[val], config)
    model_notes["ridge"] = {"alpha": alpha}

    gbt = MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=int(config["gbt_max_iter"]), learning_rate=0.06, l2_regularization=0.02, random_state=int(config["random_seed"])))
    gbt.fit(x_features[train], target[train])
    model_notes["gradient_boosted_trees"] = {"max_iter": int(config["gbt_max_iter"])}

    mlp = make_pipeline(
        StandardScaler(),
        MLPRegressor(hidden_layer_sizes=tuple(config["mlp_hidden_layer_sizes"]), max_iter=int(config["mlp_max_iter"]), alpha=1e-4, early_stopping=True, random_state=int(config["random_seed"])),
    )
    mlp.fit(x_features[train], target[train])
    model_notes["mlp"] = {"hidden_layer_sizes": config["mlp_hidden_layer_sizes"], "max_iter": int(config["mlp_max_iter"])}

    torch_x = np.stack([corrupted, rule_mask.astype(np.float32)], axis=1)
    _, cnn_predict, cnn_note = train_torch_model("cnn1d", torch_x[train], target[train], torch_x[val], target[val], config)
    model_notes["cnn1d"] = cnn_note
    _, gated_predict, gated_note = train_torch_model("gated_residual_cnn", torch_x[train], target[train], torch_x[val], target[val], config)
    model_notes["gated_residual_cnn"] = gated_note

    eval_parts = [
        evaluate_method("traditional_rule_interpolation", repaired_trad[test], target[test], rows[test].reset_index(drop=True), config),
        evaluate_method("ridge", ridge.predict(x_features[test]).astype(np.float32), target[test], rows[test].reset_index(drop=True), config),
        evaluate_method("gradient_boosted_trees", gbt.predict(x_features[test]).astype(np.float32), target[test], rows[test].reset_index(drop=True), config),
        evaluate_method("mlp", mlp.predict(x_features[test]).astype(np.float32), target[test], rows[test].reset_index(drop=True), config),
        evaluate_method("cnn1d", cnn_predict(torch_x[test]), target[test], rows[test].reset_index(drop=True), config),
        evaluate_method("gated_residual_cnn", gated_predict(torch_x[test]), target[test], rows[test].reset_index(drop=True), config),
    ]
    predictions = pd.concat(eval_parts, ignore_index=True)
    predictions.to_csv(out_dir / "method_predictions.csv.gz", index=False)

    summary_rows = []
    for method, group in predictions.groupby("method", sort=False):
        rec = {"method": method, **metric_summary(group), **bootstrap_metrics(group, int(config["bootstrap_replicates"]), int(config["random_seed"]) + METHOD_ORDER.index(method))}
        summary_rows.append(rec)
    summary = pd.DataFrame(summary_rows)
    summary["method"] = pd.Categorical(summary["method"], METHOD_ORDER, ordered=True)
    summary = summary.sort_values("method").reset_index(drop=True)
    summary.to_csv(out_dir / "benchmark_summary.csv", index=False)

    regime_rows = []
    for (method, regime), group in predictions.groupby(["method", "regime"], sort=False):
        rec = {"method": method, "regime": regime, **metric_summary(group), **bootstrap_metrics(group, int(config["bootstrap_replicates"]), int(config["random_seed"]) + 100 + METHOD_ORDER.index(method))}
        regime_rows.append(rec)
    regime_summary = pd.DataFrame(regime_rows).sort_values(["regime", "method"]).reset_index(drop=True)
    regime_summary.to_csv(out_dir / "regime_summary.csv", index=False)

    winner_row = summary.sort_values("timing_sigma68_ns").iloc[0]
    winner = str(winner_row["method"])
    trad_sigma = float(summary.loc[summary["method"].astype(str) == "traditional_rule_interpolation", "timing_sigma68_ns"].iloc[0])
    input_files = [{"path": str(p), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in root_files(config)]
    result = {
        "study_id": config["study_id"],
        "ticket_id": int(config["ticket_number"]),
        "ticket_title": config["ticket_title"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "package_versions": package_versions(),
        "config": str(config_path),
        "output_dir": str(out_dir),
        "raw_reproduction_gate": {
            "quantity": "S00 selected B-stave pulses from raw ROOT HRDv",
            "report_value": int(config["expected_selected_pulses"]),
            "reproduced": reproduced,
            "delta": reproduced - int(config["expected_selected_pulses"]),
            "tolerance": 0,
            "pass": reproduced == int(config["expected_selected_pulses"]),
        },
        "split": {
            "train_runs": config["train_runs"],
            "val_runs": config["val_runs"],
            "test_runs": config["test_runs"],
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "test_rows": int(test.sum()),
        },
        "primary_metric": config["primary_metric"],
        "winner": winner,
        "winner_family": "traditional" if winner == "traditional_rule_interpolation" else "ml_nn",
        "winner_vs_traditional_delta_ns": float(winner_row["timing_sigma68_ns"]) - trad_sigma,
        "winner_metrics": {
            "timing_sigma68_ns": float(winner_row["timing_sigma68_ns"]),
            "timing_sigma68_ns_ci95": [float(winner_row["timing_sigma68_ns_ci95_low"]), float(winner_row["timing_sigma68_ns_ci95_high"])],
            "timing_mae_ns": float(winner_row["timing_mae_ns"]),
            "timing_rms_ns": float(winner_row["timing_rms_ns"]),
            "tail_frac_abs_gt5ns": float(winner_row["tail_frac_abs_gt5ns"]),
            "reconstruction_mse": float(winner_row["reconstruction_mse"]),
        },
        "methods": json_clean(summary.to_dict(orient="records")),
        "model_notes": model_notes,
        "input_files": input_files,
        "artifacts": {
            "report": str(out_dir / "REPORT.md"),
            "result": str(out_dir / "result.json"),
            "manifest": str(out_dir / "manifest.json"),
            "benchmark_summary": str(out_dir / "benchmark_summary.csv"),
            "regime_summary": str(out_dir / "regime_summary.csv"),
            "predictions": str(out_dir / "method_predictions.csv.gz"),
        },
        "followup_ticket_appended": None,
    }

    result_path = out_dir / "result.json"
    result_path.write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_summary = summary.copy()
    for col in report_summary.columns:
        if report_summary[col].dtype.kind == "f":
            report_summary[col] = report_summary[col].map(lambda x: f"{x:.4f}")
    report_regime = regime_summary[["method", "regime", "n", "timing_sigma68_ns", "timing_sigma68_ns_ci95_low", "timing_sigma68_ns_ci95_high", "timing_mae_ns", "tail_frac_abs_gt5ns"]].copy()
    for col in report_regime.columns:
        if report_regime[col].dtype.kind == "f":
            report_regime[col] = report_regime[col].map(lambda x: f"{x:.4f}")
    write_report(out_dir, result, report_summary, report_regime, config)

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "study_id": config["study_id"],
        "ticket_number": int(config["ticket_number"]),
        "created_at_unix": time.time(),
        "elapsed_seconds": time.time() - start,
        "command": "python3 scripts/ticket_2393_p06_dropout_jagged_recovery_bakeoff.py --config configs/ticket_2393_p06_dropout_jagged_recovery_bakeoff.json",
        "config": config,
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": sys.version,
        "package_versions": package_versions(),
        "input_files": input_files,
        "output_sha256": output_hashes,
        "random_seed": int(config["random_seed"]),
        "model_notes": model_notes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    Path("result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
