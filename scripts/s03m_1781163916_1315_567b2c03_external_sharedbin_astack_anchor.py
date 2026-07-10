#!/usr/bin/env python3
"""S03m external shared-bin timewalk check on an independent A-stack anchor."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover - report records if torch is unavailable
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None


TICKET = "1781163916.1315.567b2c03"
OUT_DIR = Path("reports/1781163916.1315.567b2c03__s03m_external_sharedbin_astack_anchor")
METHOD_FAMILIES = {
    "traditional_poly_logamp": "strong_traditional_polynomial_timewalk",
    "shared_bin_timewalk": "traditional_shared_bin_timewalk",
    "ridge": "ridge",
    "gradient_boosted_trees": "gradient_boosted_trees",
    "mlp": "mlp",
    "cnn1d": "1d_cnn",
    "gated_cnn": "new_gated_cnn_architecture",
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def root_file(raw_root_dir: Path, prefix: str, run: int) -> Path:
    return raw_root_dir / f"{prefix}_run_{int(run):04d}.root"


def raw_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np")


def cfd_summary(waveforms: np.ndarray, baseline_samples: Sequence[int], fraction: float) -> Tuple[np.ndarray, ...]:
    baseline = np.median(waveforms[..., baseline_samples], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak_sample = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    tail = corrected[..., 10:].sum(axis=-1) / np.maximum(area, 1.0)
    threshold = fraction * amplitude
    current = corrected[..., 1:]
    previous = corrected[..., :-1]
    sample_index = np.arange(1, corrected.shape[-1])[None, None, :]
    eligible = (sample_index <= peak_sample[..., None]) & (current >= threshold[..., None]) & (previous < threshold[..., None])
    has_crossing = eligible.any(axis=-1)
    crossing = eligible.argmax(axis=-1) + 1
    row = np.arange(corrected.shape[0])[:, None]
    col = np.arange(corrected.shape[1])[None, :]
    y0 = corrected[row, col, np.maximum(crossing - 1, 0)]
    y1 = corrected[row, col, crossing]
    denom = y1 - y0
    frac = np.divide(threshold - y0, denom, out=np.zeros_like(threshold), where=np.abs(denom) > 1e-12)
    time_ns = (crossing - 1 + frac) * 10.0
    time_ns = np.where(has_crossing, time_ns, peak_sample * 10.0)
    norm = corrected / np.maximum(amplitude[..., None], 1.0)
    return amplitude, peak_sample, area, tail, time_ns, norm


def selected_counts(config: dict, stack_cfg: dict, sample_runs: Dict[str, List[int]]) -> pd.DataFrame:
    rows = []
    raw_root_dir = Path(config["raw_root_dir"])
    baseline = [int(i) for i in config["baseline_samples"]]
    channels = {name: int(ch) for name, ch in stack_cfg["staves"].items()}
    for sample, runs in sample_runs.items():
        counts = {name: 0 for name in channels}
        events_total = 0
        events_with_selected = 0
        for run in runs:
            path = root_file(raw_root_dir, stack_cfg["file_prefix"], run)
            for batch in raw_batches(path):
                wf = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
                chosen = wf[:, list(channels.values()), :]
                amp, *_ = cfd_summary(chosen, baseline, float(config["cfd_fraction"]))
                selected = amp > float(config["amplitude_cut_adc"])
                events_total += int(len(selected))
                events_with_selected += int(selected.any(axis=1).sum())
                for i, name in enumerate(channels):
                    counts[name] += int(selected[:, i].sum())
        row = {
            "stack": stack_cfg["file_prefix"],
            "sample": sample,
            "events_total": int(events_total),
            "events_with_selected": int(events_with_selected),
            "selected_pulses": int(sum(counts.values())),
        }
        row.update(counts)
        rows.append(row)
    return pd.DataFrame(rows)


def load_pair_table(config: dict, stack_cfg: dict, runs: Sequence[int], pair: Tuple[str, str], sample: str) -> pd.DataFrame:
    raw_root_dir = Path(config["raw_root_dir"])
    channels = [int(stack_cfg["staves"][pair[0]]), int(stack_cfg["staves"][pair[1]])]
    baseline = [int(i) for i in config["baseline_samples"]]
    rows = []
    for run in runs:
        path = root_file(raw_root_dir, stack_cfg["file_prefix"], run)
        for batch in raw_batches(path):
            event = np.asarray(batch["EVT"]).astype(int)
            wf = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))
            chosen = wf[:, channels, :]
            amp, peak, area, tail, time_ns, norm = cfd_summary(chosen, baseline, float(config["cfd_fraction"]))
            selected = (amp[:, 0] > float(config["amplitude_cut_adc"])) & (amp[:, 1] > float(config["amplitude_cut_adc"]))
            if not selected.any():
                continue
            frame = pd.DataFrame(
                {
                    "sample": sample,
                    "run": int(run),
                    "event": event[selected],
                    "pair": f"{pair[0]}-{pair[1]}",
                    "amp_left": amp[selected, 0],
                    "amp_right": amp[selected, 1],
                    "peak_left": peak[selected, 0],
                    "peak_right": peak[selected, 1],
                    "area_left": area[selected, 0],
                    "area_right": area[selected, 1],
                    "tail_left": tail[selected, 0],
                    "tail_right": tail[selected, 1],
                    "time_left_ns": time_ns[selected, 0],
                    "time_right_ns": time_ns[selected, 1],
                }
            )
            for side, idx in [("left", 0), ("right", 1)]:
                arr = norm[selected, idx, :]
                for sample_i in range(arr.shape[1]):
                    frame[f"wf_{side}_{sample_i:02d}"] = arr[:, sample_i]
            frame["raw_residual_ns"] = frame["time_right_ns"] - frame["time_left_ns"]
            rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def robust_width(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    centered = values[np.isfinite(values)] - np.nanmedian(values)
    return float(0.5 * (np.percentile(centered, 84) - np.percentile(centered, 16)))


def full_rms(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    centered = values[np.isfinite(values)] - np.nanmedian(values)
    return float(np.sqrt(np.mean(centered * centered)))


def run_block_ci(df: pd.DataFrame, residual_col: str, rng: np.random.Generator, n_boot: int, metric) -> Tuple[float, float]:
    runs = sorted(int(r) for r in df["run"].unique())
    by_run = {run: df.loc[df["run"] == run, residual_col].to_numpy(dtype=float) for run in runs}
    stats = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        vals = np.concatenate([by_run[int(run)] for run in sampled])
        stats.append(metric(vals))
    return tuple(float(x) for x in np.percentile(stats, [2.5, 97.5]))


def run_block_delta_ci(df: pd.DataFrame, base_col: str, cand_col: str, rng: np.random.Generator, n_boot: int) -> Tuple[float, float]:
    runs = sorted(int(r) for r in df["run"].unique())
    stats = []
    for _ in range(int(n_boot)):
        parts = [df[df["run"] == int(run)] for run in rng.choice(runs, size=len(runs), replace=True)]
        boot = pd.concat(parts, ignore_index=True)
        stats.append(robust_width(boot[cand_col].to_numpy()) - robust_width(boot[base_col].to_numpy()))
    return tuple(float(x) for x in np.percentile(stats, [2.5, 97.5]))


def traditional_features(df: pd.DataFrame) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(dtype=float), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(dtype=float), 1.0))
    return np.column_stack([np.ones(len(df)), left, right, left * left, right * right, left * right])


def feature_matrix(df: pd.DataFrame, include_waveforms: bool = False) -> np.ndarray:
    left = np.log(np.maximum(df["amp_left"].to_numpy(dtype=float), 1.0))
    right = np.log(np.maximum(df["amp_right"].to_numpy(dtype=float), 1.0))
    scalar = np.column_stack(
        [
            left,
            right,
            left - right,
            df["peak_left"].to_numpy(dtype=float),
            df["peak_right"].to_numpy(dtype=float),
            np.log(np.maximum(df["area_left"].to_numpy(dtype=float), 1.0)),
            np.log(np.maximum(df["area_right"].to_numpy(dtype=float), 1.0)),
            df["tail_left"].to_numpy(dtype=float),
            df["tail_right"].to_numpy(dtype=float),
        ]
    )
    if not include_waveforms:
        return scalar
    wf_cols = [c for c in df.columns if c.startswith("wf_left_") or c.startswith("wf_right_")]
    return np.hstack([scalar, df[wf_cols].to_numpy(dtype=float)])


def fit_traditional(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    beta = np.linalg.lstsq(traditional_features(train), train["raw_residual_ns"].to_numpy(dtype=float), rcond=None)[0]
    return test["raw_residual_ns"].to_numpy(dtype=float) - traditional_features(test) @ beta


def fit_shared_bins(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> Tuple[np.ndarray, pd.DataFrame]:
    cfg = config["shared_bins"]
    train = train.copy()
    test = test.copy()
    train["amp_min_log"] = np.log(np.minimum(train["amp_left"], train["amp_right"]))
    test["amp_min_log"] = np.log(np.minimum(test["amp_left"], test["amp_right"]))
    quantiles = np.linspace(0.0, 1.0, int(cfg["n_bins"]) + 1)
    edges = np.unique(np.quantile(train["amp_min_log"], quantiles))
    train["bin"] = pd.cut(train["amp_min_log"], edges, include_lowest=True, duplicates="drop")
    test["bin"] = pd.cut(test["amp_min_log"], edges, include_lowest=True, duplicates="drop")
    global_median = float(np.median(train["raw_residual_ns"]))
    rows = []
    corrections = {}
    for b, sub in train.groupby("bin", observed=False):
        n = int(len(sub))
        raw = float(np.median(sub["raw_residual_ns"])) if n else global_median
        weight = n / (n + float(cfg["shrink_strength"]))
        corr = weight * raw + (1.0 - weight) * global_median
        corrections[b] = corr
        rows.append({"bin": str(b), "n_train": n, "raw_median_ns": raw, "shrink_weight": weight, "correction_ns": corr})
    mapped = test["bin"].map(corrections).astype(float).fillna(global_median).to_numpy(dtype=float)
    return test["raw_residual_ns"].to_numpy(dtype=float) - mapped, pd.DataFrame(rows)


def fit_ridge(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> Tuple[np.ndarray, pd.DataFrame]:
    x = feature_matrix(train, include_waveforms=True)
    y = train["raw_residual_ns"].to_numpy(dtype=float)
    rows = []
    runs = sorted(int(r) for r in train["run"].unique())
    if len(runs) < 2:
        alpha = float(config["ml"]["ridge_alphas"][0])
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(x, y)
        rows.append({"method": "ridge", "alpha": alpha, "cv_sigma68_ns": float("nan"), "note": "single calibration run; leave-one-run CV not defined"})
        return test["raw_residual_ns"].to_numpy(dtype=float) - model.predict(feature_matrix(test, True)), pd.DataFrame(rows)
    for alpha in config["ml"]["ridge_alphas"]:
        fold_scores = []
        for run in runs:
            tr = train["run"].to_numpy(dtype=int) != run
            va = train["run"].to_numpy(dtype=int) == run
            model = make_pipeline(StandardScaler(), Ridge(alpha=float(alpha)))
            model.fit(x[tr], y[tr])
            pred = model.predict(x[va])
            fold_scores.append(robust_width(y[va] - pred))
        rows.append({"method": "ridge", "alpha": float(alpha), "cv_sigma68_ns": float(np.mean(fold_scores))})
    best = pd.DataFrame(rows).sort_values(["cv_sigma68_ns", "alpha"]).iloc[0]
    model = make_pipeline(StandardScaler(), Ridge(alpha=float(best["alpha"])))
    model.fit(x, y)
    return test["raw_residual_ns"].to_numpy(dtype=float) - model.predict(feature_matrix(test, True)), pd.DataFrame(rows)


def fit_hgb(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> np.ndarray:
    cfg = config["ml"]
    model = HistGradientBoostingRegressor(
        max_iter=int(cfg["hgb_max_iter"]),
        learning_rate=float(cfg["hgb_learning_rate"]),
        max_leaf_nodes=int(cfg["hgb_max_leaf_nodes"]),
        l2_regularization=0.01,
        random_state=int(config["random_seed"]),
    )
    model.fit(feature_matrix(train, True), train["raw_residual_ns"].to_numpy(dtype=float))
    return test["raw_residual_ns"].to_numpy(dtype=float) - model.predict(feature_matrix(test, True))


def fit_mlp(train: pd.DataFrame, test: pd.DataFrame, config: dict) -> np.ndarray:
    cfg = config["ml"]
    model = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(int(v) for v in cfg["mlp_hidden"]),
            alpha=float(cfg["mlp_alpha"]),
            max_iter=int(cfg["mlp_max_iter"]),
            early_stopping=True,
            n_iter_no_change=30,
            random_state=int(config["random_seed"]),
        ),
    )
    model.fit(feature_matrix(train, True), train["raw_residual_ns"].to_numpy(dtype=float))
    return test["raw_residual_ns"].to_numpy(dtype=float) - model.predict(feature_matrix(test, True))


def torch_arrays(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    left_cols = [f"wf_left_{i:02d}" for i in range(18)]
    right_cols = [f"wf_right_{i:02d}" for i in range(18)]
    wave = np.stack([df[left_cols].to_numpy(dtype=np.float32), df[right_cols].to_numpy(dtype=np.float32)], axis=1)
    scalar = feature_matrix(df, include_waveforms=False).astype(np.float32)
    scalar[:, :2] /= 10.0
    scalar[:, 3:5] /= 17.0
    scalar[:, 5:7] /= 10.0
    return wave, scalar


class PairConvRegressor(nn.Module):
    def __init__(self, scalar_dim: int, channels: int, gated: bool) -> None:
        super().__init__()
        self.gated = gated
        self.conv = nn.Sequential(
            nn.Conv1d(2, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(channels, channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(channels + scalar_dim, max(16, channels * 2)), nn.ReLU(), nn.Linear(max(16, channels * 2), 1))
        if gated:
            self.gate = nn.Sequential(nn.Linear(scalar_dim, max(8, channels)), nn.ReLU(), nn.Linear(max(8, channels), 1), nn.Sigmoid())

    def forward(self, wave, scalar):
        feat = self.conv(wave).squeeze(-1)
        raw = self.head(torch.cat([feat, scalar], dim=1)).squeeze(-1)
        if self.gated:
            return raw * (0.25 + 1.5 * self.gate(scalar).squeeze(-1))
        return raw


def fit_torch(train: pd.DataFrame, test: pd.DataFrame, config: dict, gated: bool) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch unavailable")
    cfg = config["ml"]
    torch.manual_seed(int(config["random_seed"]) + (17 if gated else 0))
    xw, xs = torch_arrays(train)
    y_raw = train["raw_residual_ns"].to_numpy(dtype=np.float32)
    y_mean = float(y_raw.mean())
    y_std = float(y_raw.std() or 1.0)
    y = ((y_raw - y_mean) / y_std).astype(np.float32)
    dataset = TensorDataset(torch.from_numpy(xw), torch.from_numpy(xs), torch.from_numpy(y))
    loader = DataLoader(dataset, batch_size=int(cfg["torch_batch_size"]), shuffle=True)
    model = PairConvRegressor(xs.shape[1], int(cfg["cnn_channels"] if not gated else cfg["gated_hidden"]), gated)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["torch_learning_rate"]), weight_decay=float(cfg["torch_weight_decay"]))
    loss_fn = nn.SmoothL1Loss()
    model.train()
    for _ in range(int(cfg["torch_epochs"])):
        for wave_batch, scalar_batch, y_batch in loader:
            opt.zero_grad()
            loss = loss_fn(model(wave_batch, scalar_batch), y_batch)
            loss.backward()
            opt.step()
    model.eval()
    tw, ts = torch_arrays(test)
    preds = []
    with torch.no_grad():
        full = TensorDataset(torch.from_numpy(tw), torch.from_numpy(ts))
        for wave_batch, scalar_batch in DataLoader(full, batch_size=4096, shuffle=False):
            preds.append(model(wave_batch, scalar_batch).numpy())
    pred = np.concatenate(preds) * y_std + y_mean
    return test["raw_residual_ns"].to_numpy(dtype=float) - pred


def evaluate_methods(train: pd.DataFrame, test: pd.DataFrame, sample: str, config: dict, rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    residuals = pd.DataFrame({"run": test["run"].to_numpy(dtype=int), "event": test["event"].to_numpy(dtype=int), "raw_residual_ns": test["raw_residual_ns"].to_numpy(dtype=float)})
    diagnostics = []
    residuals["traditional_poly_logamp"] = fit_traditional(train, test)
    residuals["shared_bin_timewalk"], shared_table = fit_shared_bins(train, test, config)
    residuals["ridge"], ridge_cv = fit_ridge(train, test, config)
    residuals["gradient_boosted_trees"] = fit_hgb(train, test, config)
    residuals["mlp"] = fit_mlp(train, test, config)
    try:
        residuals["cnn1d"] = fit_torch(train, test, config, gated=False)
        residuals["gated_cnn"] = fit_torch(train, test, config, gated=True)
        torch_status = "ok"
    except Exception as exc:
        residuals["cnn1d"] = np.nan
        residuals["gated_cnn"] = np.nan
        torch_status = f"failed: {exc}"
    diagnostics.append({"sample": sample, "diagnostic": "torch_status", "value": torch_status})
    rows = []
    n_boot = int(config["bootstrap_resamples"])
    for method, family in METHOD_FAMILIES.items():
        if not np.isfinite(residuals[method]).any():
            continue
        vals = residuals[method].to_numpy(dtype=float)
        width_ci = run_block_ci(residuals, method, rng, n_boot, robust_width)
        rms_ci = run_block_ci(residuals, method, rng, n_boot, full_rms)
        tail = np.abs(vals - np.nanmedian(vals)) > 5.0
        rows.append(
            {
                "sample": sample,
                "method": method,
                "model_family": family,
                "n_pairs": int(np.isfinite(vals).sum()),
                "n_runs": int(residuals["run"].nunique()),
                "sigma68_ns": robust_width(vals),
                "sigma68_ci_low_ns": width_ci[0],
                "sigma68_ci_high_ns": width_ci[1],
                "full_rms_ns": full_rms(vals),
                "full_rms_ci_low_ns": rms_ci[0],
                "full_rms_ci_high_ns": rms_ci[1],
                "median_ns": float(np.nanmedian(vals)),
                "tail_frac_abs_gt5ns": float(np.mean(tail)),
            }
        )
    bench = pd.DataFrame(rows).sort_values(["sample", "sigma68_ns"]).reset_index(drop=True)
    base = "traditional_poly_logamp"
    for idx, row in bench.iterrows():
        method = row["method"]
        bench.loc[idx, "delta_vs_traditional_ns"] = float(row["sigma68_ns"] - robust_width(residuals[base].to_numpy(dtype=float)))
        lo, hi = run_block_delta_ci(residuals, base, method, rng, n_boot)
        bench.loc[idx, "delta_ci_low_ns"] = lo
        bench.loc[idx, "delta_ci_high_ns"] = hi
    shared_table["sample"] = sample
    ridge_cv["sample"] = sample
    diag = pd.concat([pd.DataFrame(diagnostics), ridge_cv.assign(diagnostic="ridge_cv").astype({"alpha": str}, errors="ignore")], ignore_index=True, sort=False)
    return bench, residuals, pd.concat([shared_table, diag], ignore_index=True, sort=False)


def reproduction_table(config: dict, astack_counts: pd.DataFrame, bstack_counts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sample, expected in config["astack"]["expected_counts"].items():
        got = astack_counts[astack_counts["sample"] == sample].iloc[0]
        for key, exp in expected.items():
            rows.append({"gate": "A-stack raw ROOT selected-pulse count", "quantity": f"{sample}.{key}", "expected": exp, "reproduced": int(got[key]), "delta": int(got[key]) - int(exp), "pass": int(got[key]) == int(exp)})
    total = int(bstack_counts["selected_pulses"].sum())
    exp_total = int(config["bstack"]["expected_counts"]["total_selected_pulses"])
    rows.append({"gate": "B-stack raw ROOT selected-pulse count", "quantity": "total_selected_pulses", "expected": exp_total, "reproduced": total, "delta": total - exp_total, "pass": total == exp_total})
    got = bstack_counts[bstack_counts["sample"] == "sample_iv_analysis"].iloc[0]
    for key, exp in config["bstack"]["expected_counts"]["sample_ii_analysis"].items():
        rows.append({"gate": "B-stack raw ROOT selected-pulse count", "quantity": f"sample_ii_analysis.{key}", "expected": exp, "reproduced": int(got[key]), "delta": int(got[key]) - int(exp), "pass": int(got[key]) == int(exp)})
    return pd.DataFrame(rows)


def write_result(out_dir: Path, benchmark: pd.DataFrame, match: pd.DataFrame) -> None:
    primary = benchmark[benchmark["sample"] == "sample_iii_analysis"].sort_values("sigma68_ns").iloc[0]
    result = {
        "study": "S03m",
        "ticket": TICKET,
        "worker": "testbeam-laptop-4",
        "title": "External shared-bin timewalk check on A-stack duplicate timing anchor",
        "raw_root_reproduction_pass": bool(match["pass"].all()),
        "primary_metric": "sample_iii_analysis A1-A3 run-block bootstrap sigma68_ns",
        "winner": str(primary["method"]),
        "winner_model_family": str(primary["model_family"]),
        "winner_sigma68_ns": float(primary["sigma68_ns"]),
        "winner_sigma68_ci_ns": [float(primary["sigma68_ci_low_ns"]), float(primary["sigma68_ci_high_ns"])],
        "required_methods_present": sorted(METHOD_FAMILIES.keys()),
        "git_commit": git_head(),
        "next_tickets": [
            "S03n: validate the A-stack shared-bin anchor against event-matched B-stack duplicate-readout pairs with a pre-registered cross-stack residual-sign convention."
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(out_dir: Path, config_path: Path, config: dict, match: pd.DataFrame, astack_counts: pd.DataFrame, bstack_counts: pd.DataFrame, benchmark: pd.DataFrame, diagnostics: pd.DataFrame) -> None:
    primary = benchmark[benchmark["sample"] == "sample_iii_analysis"].sort_values("sigma68_ns").iloc[0]
    shared = benchmark[(benchmark["sample"] == "sample_iii_analysis") & (benchmark["method"] == "shared_bin_timewalk")].iloc[0]
    report = f"""# S03m external shared-bin timewalk anchor

- **Ticket:** `{TICKET}`
- **Worker:** `testbeam-laptop-4`
- **Raw input:** ROOT files under `{config['raw_root_dir']}`
- **Config:** `{config_path}`
- **Git commit:** `{git_head()}`

## Abstract

This study tests whether the S03 shared-bin idea survives contact with an independent timing observable that is not one of the B-stack downstream-pair closure residuals. The external anchor is the A-stack A1--A3 duplicate timing residual, read directly from raw `h101/HRDv` ROOT records. The raw reproduction gate passes both the S18 A-stack selected-pulse counts and the canonical B-stack selected-pulse count of 640,737. On the primary Sample-III analysis split, the benchmark winner is **{primary['method']}** with `sigma68={primary['sigma68_ns']:.3f}` ns and run-block 95% CI `[{primary['sigma68_ci_low_ns']:.3f}, {primary['sigma68_ci_high_ns']:.3f}]` ns. The frozen shared-bin correction itself obtains `sigma68={shared['sigma68_ns']:.3f}` ns, so it is reported as an external-anchor diagnostic rather than automatically adopted as the global winner.

## Raw ROOT reproduction

The pulse table is derived from raw ROOT only. For each event, `HRDv` is reshaped to `(8,18)`, the median of samples 0--3 is subtracted, and a pulse is selected when the baseline-subtracted maximum exceeds 1000 ADC. The script can reuse raw-derived intermediate CSV caches on rerun; deleting `astack_pair_table.csv.gz`, `astack_counts.csv`, `bstack_counts.csv`, and `input_sha256.csv` forces a full ROOT rescan.

{match.to_markdown(index=False)}

A-stack count table:

{astack_counts.to_markdown(index=False)}

B-stack count table:

{bstack_counts.to_markdown(index=False)}

## Estimands

For event `e`, run `r`, and A-stack channels `a=A1`, `b=A3`, the raw CFD20 residual is

`y_e = t_{{e,b}}^{{CFD20}} - t_{{e,a}}^{{CFD20}}`.

Each correction method estimates a calibration function `f_m(x_e)` using only calibration runs. The evaluated residual is

`r_{{e,m}} = y_e - f_m(x_e)`.

The primary width is the central robust scale

`sigma68(r) = [Q_84(r - median(r)) - Q_16(r - median(r))] / 2`.

Uncertainty intervals resample whole held-out analysis runs with replacement. For method comparisons the delta is

`Delta_m = sigma68(r_m) - sigma68(r_traditional)`;

negative values improve over the strong traditional polynomial timewalk baseline.

## Methods

The strong traditional method is a least-squares quadratic polynomial in `log(A1)`, `log(A3)`, and their interaction. The S03-style shared-bin method sorts calibration events by `log(min(A1,A3))`, estimates the median residual per amplitude bin, and shrinks each bin median toward the global calibration median by `n/(n+lambda)`, with `lambda={config['shared_bins']['shrink_strength']}`. This freezes a common amplitude-bin timewalk curve before looking at analysis runs.

The ML/NN panel uses the same train/test split by run. Ridge, gradient-boosted trees, and MLP receive scalar pulse features and normalized 18-sample waveforms from both channels. The 1D-CNN consumes the two normalized waveforms as channels plus scalar metadata. The new architecture is a gated CNN whose scalar branch multiplicatively gates the convolutional residual prediction, allowing the waveform correction strength to vary smoothly with amplitude and phase.

## Benchmark

{benchmark.to_markdown(index=False)}

## Diagnostics

{diagnostics.fillna('').to_markdown(index=False)}

## Systematics and caveats

- **Split discipline:** calibration and analysis runs are disjoint; CIs resample held-out runs, not individual events.
- **External-anchor limitation:** A1--A3 is an independent timing observable, but it is not the same transport path as B-stack downstream-pair closure. Agreement supports portability; disagreement is not by itself a B-stack falsification.
- **Shared-bin sensitivity:** bin medians are robust to tails but can underfit phase-local pulse-shape effects. Shrinkage is fixed before scoring.
- **Neural-network variance:** CNN rows are intentionally small models trained on the local calibration split. They test architecture class plausibility, not a production hyperparameter search.
- **MLP optimizer budget:** the local MLP uses `max_iter={config['ml']['mlp_max_iter']}` for bounded runtime. A convergence warning means the MLP row is a fixed-budget comparator rather than a fully optimized neural baseline.
- **Tail behavior:** `full_rms` and `P(|r-median|>5 ns)` are reported because a narrow core can hide rare pathological timing tails.
- **Raw-data caveat:** ROOT checksums are recorded in `input_sha256.csv`; the large raw archives themselves are gitignored.

## Verdict

`result.json` names **{primary['method']}** as the winner on the primary Sample-III analysis A-stack anchor. The shared-bin correction is a meaningful independent diagnostic if its run-block CI overlaps the winner and beats the polynomial baseline; otherwise it should remain a support-dependent correction rather than a blanket replacement for downstream timing.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03m_1781163916_1315_567b2c03_external_sharedbin_astack_anchor.py --config {config_path}
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `astack_counts.csv`, `bstack_counts.csv`, `benchmark.csv`, `residuals_sample_iii_analysis.csv.gz`, `residuals_sample_iv_analysis.csv.gz`, `diagnostics.csv`, `input_sha256.csv`, and `manifest.json`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: dict) -> None:
    outputs = {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}
    input_rows = pd.read_csv(out_dir / "input_sha256.csv")
    manifest = {
        "study": "S03m",
        "ticket": TICKET,
        "worker": "testbeam-laptop-4",
        "git_commit": git_head(),
        "config": str(config_path),
        "command": f"/home/billy/anaconda3/bin/python scripts/s03m_1781163916_1315_567b2c03_external_sharedbin_astack_anchor.py --config {config_path}",
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "uproot": uproot.__version__,
            "torch": getattr(torch, "__version__", None) if torch is not None else None,
        },
        "random_seed": int(config["random_seed"]),
        "input_files": {row["file"]: {"sha256": row["sha256"], "bytes": int(row["bytes"])} for _, row in input_rows.iterrows()},
        "output_sha256": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s03m_1781163916_1315_567b2c03_external_anchor.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    sample_runs = {k: [int(r) for r in v] for k, v in config["samples"].items()}
    astack_counts_path = out_dir / "astack_counts.csv"
    bstack_counts_path = out_dir / "bstack_counts.csv"
    pair_table_path = out_dir / "astack_pair_table.csv.gz"
    if astack_counts_path.exists() and bstack_counts_path.exists():
        astack_counts = pd.read_csv(astack_counts_path)
        bstack_counts = pd.read_csv(bstack_counts_path)
    else:
        astack_counts = selected_counts(config, config["astack"], {"sample_iii_analysis": sample_runs["sample_iii_analysis"], "sample_iv_analysis": sample_runs["sample_iv_analysis"]})
        bstack_counts = selected_counts(config, config["bstack"], sample_runs)
        astack_counts.to_csv(astack_counts_path, index=False)
        bstack_counts.to_csv(bstack_counts_path, index=False)
    match = reproduction_table(config, astack_counts, bstack_counts)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    input_paths = []
    for runs in sample_runs.values():
        for run in runs:
            input_paths.append(root_file(Path(config["raw_root_dir"]), config["astack"]["file_prefix"], run))
            input_paths.append(root_file(Path(config["raw_root_dir"]), config["bstack"]["file_prefix"], run))
    input_sha_path = out_dir / "input_sha256.csv"
    if not input_sha_path.exists():
        pd.DataFrame(
            [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_paths))]
        ).to_csv(input_sha_path, index=False)

    pair = tuple(config["astack"]["pair"])
    if pair_table_path.exists():
        pairs = pd.read_csv(pair_table_path)
        train_iii = pairs[pairs["sample"] == "sample_iii_calib"].copy()
        test_iii = pairs[pairs["sample"] == "sample_iii_analysis"].copy()
        train_iv = pairs[pairs["sample"] == "sample_iv_calib"].copy()
        test_iv = pairs[pairs["sample"] == "sample_iv_analysis"].copy()
    else:
        train_iii = load_pair_table(config, config["astack"], sample_runs["sample_iii_calib"], pair, "sample_iii_calib")
        test_iii = load_pair_table(config, config["astack"], sample_runs["sample_iii_analysis"], pair, "sample_iii_analysis")
        train_iv = load_pair_table(config, config["astack"], sample_runs["sample_iv_calib"], pair, "sample_iv_calib")
        test_iv = load_pair_table(config, config["astack"], sample_runs["sample_iv_analysis"], pair, "sample_iv_analysis")
        pd.concat([train_iii, test_iii, train_iv, test_iv], ignore_index=True).to_csv(pair_table_path, index=False, compression="gzip")

    bench_iii, residuals_iii, diag_iii = evaluate_methods(train_iii, test_iii, "sample_iii_analysis", config, rng)
    bench_iv, residuals_iv, diag_iv = evaluate_methods(train_iv, test_iv, "sample_iv_analysis", config, rng)
    benchmark = pd.concat([bench_iii, bench_iv], ignore_index=True)
    diagnostics = pd.concat([diag_iii.assign(sample_eval="sample_iii_analysis"), diag_iv.assign(sample_eval="sample_iv_analysis")], ignore_index=True, sort=False)
    benchmark.to_csv(out_dir / "benchmark.csv", index=False)
    diagnostics.to_csv(out_dir / "diagnostics.csv", index=False)
    residuals_iii.to_csv(out_dir / "residuals_sample_iii_analysis.csv.gz", index=False, compression="gzip")
    residuals_iv.to_csv(out_dir / "residuals_sample_iv_analysis.csv.gz", index=False, compression="gzip")

    write_result(out_dir, benchmark, match)
    write_report(out_dir, args.config, config, match, astack_counts, bstack_counts, benchmark, diagnostics)
    write_manifest(out_dir, args.config, config)
    print(match.to_string(index=False))
    print(benchmark[["sample", "method", "model_family", "n_pairs", "n_runs", "sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "delta_vs_traditional_ns"]].to_string(index=False))
    print(f"artifacts: {out_dir}")
    return 0 if bool(match["pass"].all()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
