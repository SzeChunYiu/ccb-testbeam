#!/usr/bin/env python3
"""S32a pulse-onset timing benchmark under pedestal, pile-up, and saturation stress."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Iterable, Sequence

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark.json"
METHOD_ORDER = [
    "traditional_cfd_template_timewalk",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "edge_attention_cnn_new",
]


def git_head() -> str:
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


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return None if not math.isfinite(x) else x
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def raw_root_dir(config: dict) -> Path:
    path = Path(config["raw_root_dir"])
    if path.exists():
        return path
    alt = ROOT / path
    if alt.exists():
        return alt
    fallback = Path("/home/billy/ccb-data/extracted/root/root")
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"raw ROOT directory not found: {path}")


def root_path(config: dict, run: int) -> Path:
    return raw_root_dir(config) / f"hrdb_run_{run:04d}.root"


def raw_batches(path: Path, step_size: int = 25000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np")


def all_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def cfd_time(corrected: np.ndarray, amplitude: np.ndarray, peak: np.ndarray, fraction: float) -> np.ndarray:
    threshold = fraction * amplitude
    current = corrected[..., 1:]
    previous = corrected[..., :-1]
    sample_index = np.arange(1, corrected.shape[-1])[None, :]
    eligible = (sample_index <= peak[:, None]) & (current >= threshold[:, None]) & (previous < threshold[:, None])
    has = eligible.any(axis=1)
    crossing = eligible.argmax(axis=1) + 1
    row = np.arange(len(corrected))
    y0 = corrected[row, np.maximum(crossing - 1, 0)]
    y1 = corrected[row, crossing]
    denom = y1 - y0
    frac = np.divide(threshold - y0, denom, out=np.zeros_like(threshold), where=np.abs(denom) > 1e-12)
    return np.where(has, crossing - 1 + frac, peak.astype(float))


def robust_sigma(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.median(values)
    return float(0.5 * (np.percentile(centered, 84) - np.percentile(centered, 16)))


def count_reproduction(config: dict) -> pd.DataFrame:
    staves = {k: int(v) for k, v in config["staves"].items()}
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    rows = []
    total = 0
    for group, runs in config["run_groups"].items():
        selected_pulses = 0
        events_total = 0
        for run in runs:
            for batch in raw_batches(root_path(config, int(run))):
                waves = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
                chosen = waves[:, list(staves.values()), :]
                baseline = np.median(chosen[..., baseline_samples], axis=-1)
                amp = (chosen - baseline[..., None]).max(axis=-1)
                selected_pulses += int((amp > float(config["amplitude_cut_adc"])).sum())
                events_total += int(len(amp))
        expected = int(config["expected_group_counts"][group])
        total += selected_pulses
        rows.append(
            {
                "group": group,
                "events_total": events_total,
                "selected_pulses": selected_pulses,
                "expected_selected_pulses": expected,
                "delta": selected_pulses - expected,
                "pass": bool(selected_pulses == expected),
            }
        )
    rows.append(
        {
            "group": "all_registered_groups",
            "events_total": int(sum(r["events_total"] for r in rows)),
            "selected_pulses": total,
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": total - int(config["expected_selected_pulses"]),
            "pass": bool(total == int(config["expected_selected_pulses"])),
        }
    )
    return pd.DataFrame(rows)


def sample_pulses(config: dict, rng: np.random.Generator) -> pd.DataFrame:
    staves = {k: int(v) for k, v in config["staves"].items()}
    dups = {k: int(v) for k, v in config["duplicate_readout_channels"].items()}
    baseline_samples = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    max_take = int(config["max_per_run_stave"])
    rows = []
    for run in all_runs(config):
        path = root_path(config, run)
        run_frames = []
        for batch in raw_batches(path):
            event = np.asarray(batch["EVT"]).astype(int)
            waves = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
            for stave, ch in staves.items():
                raw = waves[:, ch, :]
                dup = waves[:, dups[stave], :]
                baseline = np.median(raw[:, baseline_samples], axis=1)
                corrected = raw - baseline[:, None]
                amp = corrected.max(axis=1)
                selected = amp > cut
                if not selected.any():
                    continue
                corr = corrected[selected]
                amp_sel = amp[selected]
                peak = corr.argmax(axis=1)
                dup_corr = dup[selected] - np.median(dup[selected][:, baseline_samples], axis=1)[:, None]
                dup_amp = dup_corr.max(axis=1)
                cfd20 = cfd_time(corr, amp_sel, peak, 0.20)
                cfd50 = cfd_time(corr, amp_sel, peak, 0.50)
                cfd80 = cfd_time(corr, amp_sel, peak, 0.80)
                denom = np.maximum(amp_sel[:, None], 1.0)
                norm = corr / denom
                area = corr.sum(axis=1)
                pos_area = np.maximum(corr, 0.0).sum(axis=1)
                tail = corr[:, 12:].sum(axis=1) / np.maximum(pos_area, 1.0)
                pre_slope = corr[:, 3] - corr[:, 0]
                late_max_idx = np.argmax(corr[:, 9:], axis=1) + 9
                late_max = corr[np.arange(len(corr)), late_max_idx]
                second_sep = late_max_idx - peak
                second_prom = late_max / np.maximum(amp_sel, 1.0)
                flat_top = (corr >= 0.985 * amp_sel[:, None]).sum(axis=1)
                frame = pd.DataFrame(
                    {
                        "run": run,
                        "event": event[selected],
                        "stave": stave,
                        "channel": ch,
                        "baseline": baseline[selected],
                        "amplitude": amp_sel,
                        "duplicate_amplitude": dup_amp,
                        "peak_sample": peak,
                        "area": area,
                        "positive_area": pos_area,
                        "tail_fraction": tail,
                        "pretrigger_slope": pre_slope,
                        "cfd20_sample": cfd20,
                        "cfd50_sample": cfd50,
                        "cfd80_sample": cfd80,
                        "rise_time_sample": cfd80 - cfd20,
                        "late_peak_sample": late_max_idx,
                        "pileup_separation_sample": np.where((second_sep > 1) & (second_prom > 0.30), second_sep, 0),
                        "late_peak_prominence": second_prom,
                        "flat_top_samples": flat_top,
                    }
                )
                for i in range(int(config["samples_per_channel"])):
                    frame[f"w{i:02d}"] = norm[:, i]
                run_frames.append(frame)
        if not run_frames:
            continue
        run_df = pd.concat(run_frames, ignore_index=True)
        for stave, group in run_df.groupby("stave"):
            take = min(max_take, len(group))
            chosen = rng.choice(group.index.to_numpy(), size=take, replace=False)
            rows.append(run_df.loc[chosen])
    df = pd.concat(rows, ignore_index=True)
    med = df.groupby(["run", "stave"])["cfd20_sample"].transform("median")
    df["target_onset_residual_ns"] = (df["cfd20_sample"] - med) * 10.0
    df["raw_cfd50_residual_ns"] = (df["cfd50_sample"] - df.groupby(["run", "stave"])["cfd50_sample"].transform("median")) * 10.0
    df["split"] = np.where(df["run"].isin([int(r) for r in config["heldout_runs"]]), "heldout", "train")
    add_strata(df)
    return df.reset_index(drop=True)


def add_strata(df: pd.DataFrame) -> None:
    df["energy_bin"] = pd.qcut(df["amplitude"], q=4, labels=["q1_low", "q2", "q3", "q4_high"], duplicates="drop").astype(str)
    run_base = df.groupby(["run", "stave"])["baseline"].transform("median")
    df["pedestal_drift_abs"] = (df["baseline"] - run_base).abs()
    df["pedestal_drift_bin"] = pd.qcut(df["pedestal_drift_abs"], q=3, labels=["low", "mid", "high"], duplicates="drop").astype(str)
    df["pulse_shape_class"] = pd.qcut(df["tail_fraction"], q=3, labels=["compact", "nominal", "late_tail"], duplicates="drop").astype(str)
    df["pileup_separation_bin"] = pd.cut(
        df["pileup_separation_sample"], bins=[-0.5, 0.5, 3.5, 8.5, 99], labels=["none", "close", "mid", "late"]
    ).astype(str)
    sat = (df["amplitude"] > df["amplitude"].quantile(0.90)) | (df["flat_top_samples"] >= 2)
    df["saturation_onset_bin"] = np.where(sat, "near_saturation", "linear")
    ratio = df["duplicate_amplitude"] / np.maximum(df["amplitude"], 1.0)
    lo, hi = ratio.quantile([0.15, 0.85])
    df["pid_sideband"] = np.select([ratio <= lo, ratio >= hi], ["low_duplicate", "high_duplicate"], default="central")


def feature_columns(df: pd.DataFrame) -> list[str]:
    base = [
        "baseline",
        "amplitude",
        "duplicate_amplitude",
        "peak_sample",
        "area",
        "positive_area",
        "tail_fraction",
        "pretrigger_slope",
        "cfd50_sample",
        "cfd80_sample",
        "rise_time_sample",
        "late_peak_sample",
        "pileup_separation_sample",
        "late_peak_prominence",
        "flat_top_samples",
    ]
    return base + [f"w{i:02d}" for i in range(18)]


def waveform_array(df: pd.DataFrame) -> np.ndarray:
    return df[[f"w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)


def traditional_prediction(df: pd.DataFrame) -> np.ndarray:
    train = df["split"].eq("train").to_numpy()
    y = df["target_onset_residual_ns"].to_numpy(float)
    raw = df["raw_cfd50_residual_ns"].to_numpy(float)
    amp = np.log1p(df["amplitude"].to_numpy(float))
    pred = np.zeros(len(df), dtype=float)
    pred[~train] = raw[~train]
    pred[train] = raw[train]
    residual = y[train] - raw[train]
    order = np.argsort(amp[train])
    iso = IsotonicRegression(increasing=False, out_of_bounds="clip")
    iso.fit(amp[train][order], residual[order])
    correction = iso.predict(amp)
    template_proxy = 10.0 * (df["cfd50_sample"].to_numpy(float) - df["cfd20_sample"].to_numpy(float))
    coef = np.polyfit(template_proxy[train], (y - raw - correction)[train], deg=1)
    return raw + correction + np.polyval(coef, template_proxy)


def fit_tabular_methods(df: pd.DataFrame) -> dict[str, np.ndarray]:
    cols = feature_columns(df)
    x = df[cols].to_numpy(dtype=float)
    y = df["target_onset_residual_ns"].to_numpy(float)
    train = df["split"].eq("train").to_numpy()
    methods = {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=3.0)),
        "gradient_boosted_trees": HistGradientBoostingRegressor(max_iter=170, learning_rate=0.045, l2_regularization=0.02, random_state=73),
        "mlp": make_pipeline(
            StandardScaler(),
            MLPRegressor(hidden_layer_sizes=(64, 32), activation="relu", alpha=1e-3, max_iter=35, random_state=74, early_stopping=True),
        ),
    }
    preds = {}
    for name, model in methods.items():
        model.fit(x[train], y[train])
        preds[name] = model.predict(x)
    return preds


class TinyCNN(nn.Module):
    def __init__(self, gated: bool = False) -> None:
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(
            nn.Conv1d(1, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 16, 3, padding=1),
            nn.ReLU(),
        )
        self.gate = nn.Sequential(nn.Conv1d(1, 16, 5, padding=2), nn.Sigmoid()) if gated else None
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(16 * 18, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.conv(x)
        if self.gated:
            h = h * (1.0 + self.gate(x))
        return self.head(h).squeeze(-1)


def fit_cnn(df: pd.DataFrame, config: dict, name: str, gated: bool, seed: int) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is required for neural waveform methods")
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    x = waveform_array(df)[:, None, :]
    y = df["target_onset_residual_ns"].to_numpy(dtype=np.float32)
    train = df["split"].eq("train").to_numpy()
    ym = float(y[train].mean())
    ys = float(y[train].std() + 1e-6)
    ds = TensorDataset(torch.from_numpy(x[train]), torch.from_numpy(((y[train] - ym) / ys).astype(np.float32)))
    loader = DataLoader(
        ds,
        batch_size=int(config["nn"]["batch_size"]),
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    model = TinyCNN(gated=gated)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(config["nn"]["epochs"])):
        for xb, yb in loader:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
    out = []
    model.eval()
    with torch.no_grad():
        tx = torch.from_numpy(x)
        for start in range(0, len(tx), 2048):
            out.append(model(tx[start : start + 2048]).cpu().numpy())
    return np.concatenate(out) * ys + ym


def metric_values(frame: pd.DataFrame) -> dict[str, float]:
    err = frame["error_ns"].to_numpy(float)
    abs_err = np.abs(err[np.isfinite(err)])
    return {
        "bias_ns": float(np.nanmedian(err)),
        "sigma68_ns": robust_sigma(err),
        "rms_ns": float(np.sqrt(np.nanmean((err - np.nanmedian(err)) ** 2))),
        "tail_fraction_abs_gt_5ns": float((abs_err > 5.0).mean()) if len(abs_err) else float("nan"),
        "tail_fraction_abs_gt_10ns": float((abs_err > 10.0).mean()) if len(abs_err) else float("nan"),
    }


def summarize(predictions: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    held = predictions[predictions["split"].eq("heldout")].copy()
    metric_rows = []
    run_rows = []
    strata_rows = []
    for method, group in held.groupby("method"):
        row = {"method": method, "n": int(len(group)), **metric_values(group)}
        runs = sorted(group["run"].unique())
        samples = {k: [] for k in ["bias_ns", "sigma68_ns", "rms_ns", "tail_fraction_abs_gt_5ns", "tail_fraction_abs_gt_10ns"]}
        for _ in range(int(config["bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            boot = pd.concat([group[group["run"].eq(r)] for r in take], ignore_index=True)
            vals = metric_values(boot)
            for key, value in vals.items():
                if np.isfinite(value):
                    samples[key].append(value)
        for key, values in samples.items():
            row[f"{key}_ci_low"] = float(np.percentile(values, 2.5))
            row[f"{key}_ci_high"] = float(np.percentile(values, 97.5))
        metric_rows.append(row)
        for run, rg in group.groupby("run"):
            run_rows.append({"method": method, "run": int(run), "n": int(len(rg)), **metric_values(rg)})
        for col in ["pedestal_drift_bin", "pulse_shape_class", "pileup_separation_bin", "saturation_onset_bin", "energy_bin", "pid_sideband"]:
            for level, sg in group.groupby(col):
                strata_rows.append({"method": method, "stratum": col, "level": str(level), "n": int(len(sg)), **metric_values(sg)})
    metrics = pd.DataFrame(metric_rows)
    metrics["method"] = pd.Categorical(metrics["method"], METHOD_ORDER, ordered=True)
    return (
        metrics.sort_values("sigma68_ns").reset_index(drop=True),
        pd.DataFrame(run_rows).sort_values(["method", "run"]),
        pd.DataFrame(strata_rows).sort_values(["stratum", "level", "method"]),
    )


def md_table(df: pd.DataFrame, columns: Sequence[str], max_rows: int | None = None) -> str:
    view = df.loc[:, list(columns)].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(config: dict, reproduction: pd.DataFrame, data: pd.DataFrame, metrics: pd.DataFrame, by_run: pd.DataFrame, strata: pd.DataFrame, result: dict, runtime: float) -> None:
    out = Path(config["output_dir"])
    winner = result["winner"]["method"]
    best = metrics[metrics["method"].astype(str).eq(winner)].iloc[0]
    trad = metrics[metrics["method"].astype(str).eq("traditional_cfd_template_timewalk")].iloc[0]
    method_desc = pd.DataFrame(
        [
            ["traditional_cfd_template_timewalk", "traditional", "CFD20/CFD50 template proxy plus monotone log-amplitude time-walk correction"],
            ["ridge", "linear ML", "standardized ridge regression on amplitude, pedestal, CFD, tail, pile-up, saturation, and normalized samples"],
            ["gradient_boosted_trees", "tree ML", "histogram gradient-boosted regression on the same engineered waveform features"],
            ["mlp", "neural tabular", "two-hidden-layer perceptron on engineered waveform and detector-state summaries"],
            ["1d_cnn", "neural waveform", "compact 1D convolutional regressor over the 18 normalized ADC samples"],
            ["edge_attention_cnn_new", "new architecture", "gated 1D-CNN whose learned edge gate emphasizes onset and late-curvature samples"],
        ],
        columns=["method", "family", "description"],
    )
    counts = data.groupby("split").size().reset_index(name="rows")
    text = f"""# S32a: Pulse-Onset Timing Under Pedestal Pile-Up Saturation Benchmark

## Abstract

Ticket `{config['ticket_id']}` requested a run-held-out benchmark for sub-sample
pulse-onset timing under pedestal drift, pile-up, saturation, energy, and
PID-sideband stress.  This study reproduces the registered raw B-stack ROOT pulse
count, constructs an onset-residual benchmark directly from `h101/HRDv`, and
compares one strong traditional method with ridge, gradient-boosted trees, MLP,
1D-CNN, and a new gated edge-attention CNN.  The winner written to `result.json`
is **`{winner}`**, with held-out run-bootstrap sigma68
`{best['sigma68_ns']:.4g} ns [{best['sigma68_ns_ci_low']:.4g}, {best['sigma68_ns_ci_high']:.4g}]`.

## Raw ROOT Reproduction

Input files are `{config['raw_root_dir']}/hrdb_run_*.root`.  For every event the
branch `HRDv` is reshaped as `(8, 18)`.  For stave channel `c`,

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

A selected B-stack pulse satisfies `A_c > {config['amplitude_cut_adc']:.0f} ADC`
for one of B2/B4/B6/B8.  The reproduction is performed before any row sampling
or training:

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

## Estimand and Split

For each selected pulse the CFD time at fraction `f` is the first pre-peak linear
interpolation satisfying

`x(t_f)-b = f A`.

The target is the run/stave-centered CFD20 onset residual,

`y_i = 10 ns * [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

The split is by run: held-out runs are `{config['heldout_runs']}` and all other
registered B-stack runs train the models.  The sampled benchmark contains:

{md_table(counts, ['split', 'rows'])}

Confidence intervals are percentile 95% intervals from
`{config['bootstrap_replicates']}` held-out run-block resamples:

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`.

## Methods

{md_table(method_desc, ['method', 'family', 'description'])}

The traditional comparator is intentionally strong.  It starts from a CFD50
residual, fits a non-increasing isotonic correction in `log(1+A)` on training
runs, and adds a linear template-shape proxy from `(t_0.50 - t_0.20)`.  Formally,

`hat y = r_50 + g(log(1+A)) + alpha + beta (t_0.50 - t_0.20)`,

where `g` is constrained monotone to encode ordinary time walk.

The new `edge_attention_cnn_new` is sensible for this ticket because the
dominant information is local to the leading edge, while late curvature and
flat-top samples carry pile-up and saturation nuisance information.  Its gate is
learned from the waveform and multiplicatively reweights convolutional channels.

No method receives event number or run identifier as a feature.

## Primary Held-Out Results

{md_table(metrics, ['method', 'n', 'bias_ns', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'rms_ns', 'tail_fraction_abs_gt_5ns', 'tail_fraction_abs_gt_10ns'])}

The traditional method has sigma68 `{trad['sigma68_ns']:.4g} ns`; the selected
winner `{winner}` has sigma68 `{best['sigma68_ns']:.4g} ns`.

## Run Stability

{md_table(by_run, ['method', 'run', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=80)}

## Stress-Stratified Results

The requested stress axes are implemented as raw-waveform proxies:
pedestal drift is the absolute baseline displacement from the run/stave median;
pulse-shape class is the late-tail fraction; pile-up separation is the spacing
to a late secondary prominence; saturation onset is high amplitude or flat-top
occupancy; energy proxy is amplitude quartile; PID sideband is the duplicate
readout amplitude ratio sideband.

{md_table(strata, ['stratum', 'level', 'method', 'n', 'bias_ns', 'sigma68_ns', 'tail_fraction_abs_gt_5ns'], max_rows=140)}

## Systematics and Caveats

This is a raw-ROOT, run-held-out timing benchmark, not a beamline truth
measurement.  The onset target is an internally reproducible CFD20 reference; it
does not claim an external picosecond truth label.  Pedestal drift, pile-up
separation, saturation onset, energy, and PID are represented by waveform
sideband proxies because the ticket asks for raw ROOT reproduction and the
available tree does not contain independent particle labels or electronics
saturation flags.  The bootstrap resamples held-out runs, so its interval covers
run-transfer scatter more directly than event-level counting uncertainty.  The
18-sample waveform and 10 ns digitizer spacing impose a hard interpolation floor
shared by every method.

Runtime was `{runtime:.1f} s` on `{platform.platform()}` with Python
`{platform.python_version()}`.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    reproduction = count_reproduction(config)
    reproduction.to_csv(out / "reproduction.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    data = sample_pulses(config, rng)
    data.to_parquet(out / "benchmark_rows.parquet", index=False)
    preds = {"traditional_cfd_template_timewalk": traditional_prediction(data)}
    preds.update(fit_tabular_methods(data))
    preds["1d_cnn"] = fit_cnn(data, config, "1d_cnn", gated=False, seed=int(config["random_seed"]) + 1)
    preds["edge_attention_cnn_new"] = fit_cnn(data, config, "edge_attention_cnn_new", gated=True, seed=int(config["random_seed"]) + 2)

    pred_rows = []
    base_cols = [
        "run",
        "event",
        "stave",
        "split",
        "target_onset_residual_ns",
        "pedestal_drift_bin",
        "pulse_shape_class",
        "pileup_separation_bin",
        "saturation_onset_bin",
        "energy_bin",
        "pid_sideband",
    ]
    for method, pred in preds.items():
        frame = data[base_cols].copy()
        frame["method"] = method
        frame["prediction_ns"] = pred
        frame["error_ns"] = frame["target_onset_residual_ns"] - frame["prediction_ns"]
        pred_rows.append(frame)
    predictions = pd.concat(pred_rows, ignore_index=True)
    predictions.to_parquet(out / "predictions.parquet", index=False)

    metrics, by_run, strata = summarize(predictions, config, rng)
    metrics.to_csv(out / "metrics.csv", index=False)
    by_run.to_csv(out / "by_run.csv", index=False)
    strata.to_csv(out / "strata.csv", index=False)
    winner_row = metrics.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(raw_root_dir(config)),
        "git_commit": git_head(),
        "script_sha256": sha256_file(Path(__file__)),
        "config_sha256": sha256_file(args.config),
        "runtime_sec": time.time() - started,
        "python": platform.python_version(),
        "reproduction": {
            "selected_pulses": int(reproduction.iloc[-1]["selected_pulses"]),
            "expected_selected_pulses": int(config["expected_selected_pulses"]),
            "delta": int(reproduction.iloc[-1]["delta"]),
            "passed": bool(reproduction["pass"].all()),
            "samples_per_channel": int(config["samples_per_channel"]),
        },
        "split": {
            "heldout_runs": [int(r) for r in config["heldout_runs"]],
            "train_rows": int((data["split"] == "train").sum()),
            "heldout_rows": int((data["split"] == "heldout").sum()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "methods": METHOD_ORDER,
        "primary_metric": "held-out run-block bootstrap sigma68_ns of target_onset_residual_ns - prediction_ns; lower is better",
        "winner": {
            "method": str(winner_row["method"]),
            "sigma68_ns": float(winner_row["sigma68_ns"]),
            "sigma68_ns_ci_low": float(winner_row["sigma68_ns_ci_low"]),
            "sigma68_ns_ci_high": float(winner_row["sigma68_ns_ci_high"]),
            "bias_ns": float(winner_row["bias_ns"]),
        },
        "metric_table": json_safe(metrics.to_dict("records")),
        "strata_axes": ["pedestal_drift_bin", "pulse_shape_class", "pileup_separation_bin", "saturation_onset_bin", "energy_bin", "pid_sideband"],
        "next_tickets": [],
    }
    (out / "result.json").write_text(json.dumps(json_safe(result), indent=2) + "\n", encoding="utf-8")
    write_report(config, reproduction, data, metrics, by_run, strata, result, time.time() - started)


if __name__ == "__main__":
    main()
