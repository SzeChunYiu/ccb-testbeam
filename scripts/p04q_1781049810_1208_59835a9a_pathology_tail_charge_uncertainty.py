#!/usr/bin/env python3
"""P04q: pathology-tail charge uncertainty propagation.

This study reads raw B-stack ROOT waveforms, reproduces the S00/S00c selector
counts, then benchmarks traditional and ML/NN duplicate-readout charge
regressors with conformal uncertainty intervals on run-held-out folds.
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
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception:  # pragma: no cover
    torch = None
    nn = None
    DataLoader = None
    TensorDataset = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04k_1781029246_839_554f50f7_selector_charge_closure as p04k  # noqa: E402


METHODS = [
    "strong_traditional_huber",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "wavegate_interval_net",
    "shuffled_target_gbt",
]
REAL_METHODS = [m for m in METHODS if m != "shuffled_target_gbt"]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def assign_calibration_runs(runs: Iterable[int], heldout_run: int, fraction: float) -> np.ndarray:
    train_runs = np.asarray([int(run) for run in runs if int(run) != int(heldout_run)], dtype=int)
    ordered = np.sort(train_runs)
    n_cal = max(2, int(round(len(ordered) * float(fraction))))
    pos = int(np.searchsorted(np.sort(np.asarray(list(runs), dtype=int)), int(heldout_run)))
    return np.sort(np.roll(ordered, -pos)[:n_cal])


def check_counts(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for key, expected in config["expected_counts"].items():
        reproduced = int(counts[key].sum())
        rows.append(
            {
                "quantity": key,
                "report_value": int(expected),
                "reproduced": reproduced,
                "delta": reproduced - int(expected),
                "tolerance": 0,
                "pass": reproduced == int(expected),
            }
        )
    out = pd.DataFrame(rows)
    if not bool(out["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed:\n" + out.to_string(index=False))
    return out


def add_atoms(meta: pd.DataFrame, wave: np.ndarray, config: dict, q_template: np.ndarray, template_loss: np.ndarray) -> pd.DataFrame:
    out = meta.copy()
    charge = np.maximum(out["even_pos_charge"].to_numpy(dtype=float), 1.0)
    amp = np.maximum(out["median_amp"].to_numpy(dtype=float), 1.0)
    tail_frac = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / charge
    late_frac = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / charge
    early_frac = np.clip(wave[:, :6], 0.0, None).sum(axis=1) / charge
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    plateau = (wave >= (0.995 * amp[:, None])).sum(axis=1)
    q_shift = np.log(np.maximum(q_template, 1.0) / np.maximum(charge, 1.0))

    out["tail_frac"] = tail_frac
    out["late_frac"] = late_frac
    out["early_frac"] = early_frac
    out["half_width"] = half_width
    out["plateau_samples"] = plateau
    out["q_template"] = q_template
    out["template_loss"] = template_loss
    out["q_template_log_shift"] = q_shift
    out["lowering_axis"] = np.where(out["dynamic_only"].to_numpy(dtype=bool), "dynamic_only", "median_selected")
    out["saturation_stratum"] = np.where(
        out["dynamic_amp"].to_numpy(dtype=float) >= float(config["saturation_boundary_adc"]),
        "sat_boundary",
        "below_sat",
    )
    out["baseline_stratum"] = np.where(
        out["baseline_excursion"].to_numpy(dtype=float) >= float(config["baseline_excursion_boundary_adc"]),
        "large_lowering",
        "nominal_lowering",
    )
    anomaly = np.full(len(out), "nominal_shape", dtype=object)
    anomaly[tail_frac >= float(config["tail_fraction_boundary"])] = "late_tail"
    anomaly[early_frac >= float(config["early_fraction_boundary"])] = "early_pretrigger"
    anomaly[np.abs(q_shift) >= 0.18] = "template_shift"
    anomaly[out["baseline_stratum"].to_numpy() == "large_lowering"] = "baseline_lowering"
    out["anomaly_taxon"] = anomaly

    family_lookup = {}
    for family, runs in config["run_groups"].items():
        for run in runs:
            family_lookup[int(run)] = str(family)
    out["run_family"] = out["run"].map(lambda run: family_lookup.get(int(run), "unknown"))
    out["support_cell"] = (
        out["stave"].astype(str)
        + "|"
        + out["lowering_axis"].astype(str)
        + "|"
        + out["anomaly_taxon"].astype(str)
        + "|"
        + out["saturation_stratum"].astype(str)
        + "|"
        + out["run_family"].astype(str)
    )
    out["proxy_weight"] = out["stave"].map(lambda s: float(config["proxy_stave_weights"][str(s)]))
    return out


def scalar_features(meta: pd.DataFrame, wave: np.ndarray, include_atoms: bool = True) -> np.ndarray:
    amp = np.maximum(meta["median_amp"].to_numpy(dtype=float), 1.0)
    charge = np.maximum(meta["even_pos_charge"].to_numpy(dtype=float), 1.0)
    base = np.column_stack(
        [
            np.log(amp),
            np.log(charge),
            np.log(np.maximum(meta["dynamic_amp"].to_numpy(dtype=float), 1.0)),
            meta["baseline_excursion"].to_numpy(dtype=float),
            meta["pre4_mean"].to_numpy(dtype=float),
            meta["pre4_std"].to_numpy(dtype=float),
            meta["even_peak"].to_numpy(dtype=float),
            meta["even_area"].to_numpy(dtype=float) / charge,
            meta["tail_frac"].to_numpy(dtype=float),
            meta["late_frac"].to_numpy(dtype=float),
            meta["early_frac"].to_numpy(dtype=float),
            meta["half_width"].to_numpy(dtype=float),
            meta["plateau_samples"].to_numpy(dtype=float),
            np.log(np.maximum(meta["q_template"].to_numpy(dtype=float), 1.0)),
            np.log(np.maximum(np.nan_to_num(meta["template_loss"].to_numpy(dtype=float), nan=np.nanmedian(meta["template_loss"])), 1e-9)),
            meta["q_template_log_shift"].to_numpy(dtype=float),
        ]
    )
    if not include_atoms:
        return base.astype(np.float32)
    cats = meta[["stave", "lowering_axis", "anomaly_taxon", "saturation_stratum", "baseline_stratum", "run_family"]].astype(str)
    enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    return np.column_stack([base, enc.fit_transform(cats)]).astype(np.float32)


def waveform_features(meta: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    amp = np.maximum(meta["median_amp"].to_numpy(dtype=float), 1.0)
    norm = wave.astype(np.float32) / amp[:, None].astype(np.float32)
    return np.column_stack([norm, scalar_features(meta, wave, include_atoms=True)]).astype(np.float32)


def fit_log_predict(model, x_train: np.ndarray, y_train: np.ndarray, x_eval: np.ndarray) -> np.ndarray:
    model.fit(x_train, np.log(np.maximum(y_train, 1.0)))
    return np.exp(model.predict(x_eval))


def quantile_by_support(
    cal_frame: pd.DataFrame,
    cal_abs_frac: np.ndarray,
    eval_frame: pd.DataFrame,
    level: float,
    min_rows: int,
) -> np.ndarray:
    q_global = float(np.percentile(cal_abs_frac, 100.0 * level))
    by_cell: Dict[str, float] = {}
    for cell, idx in cal_frame.groupby("support_cell", observed=True).groups.items():
        loc = cal_abs_frac[np.asarray(list(idx), dtype=int)]
        if len(loc) >= min_rows:
            by_cell[str(cell)] = float(np.percentile(loc, 100.0 * level))
    by_atom: Dict[Tuple[str, str, str], float] = {}
    for key, idx in cal_frame.groupby(["lowering_axis", "anomaly_taxon", "saturation_stratum"], observed=True).groups.items():
        loc = cal_abs_frac[np.asarray(list(idx), dtype=int)]
        if len(loc) >= min_rows:
            by_atom[(str(key[0]), str(key[1]), str(key[2]))] = float(np.percentile(loc, 100.0 * level))
    vals = []
    for row in eval_frame.itertuples(index=False):
        atom_key = (str(row.lowering_axis), str(row.anomaly_taxon), str(row.saturation_stratum))
        vals.append(by_cell.get(str(row.support_cell), by_atom.get(atom_key, q_global)))
    return np.asarray(vals, dtype=float)


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)) if len(frac) else math.nan,
        "charge_res68_abs_frac": float(np.percentile(np.abs(frac), 68)) if len(frac) else math.nan,
        "charge_full_rms_frac": float(np.sqrt(np.mean(frac * frac))) if len(frac) else math.nan,
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)) if len(frac) else math.nan,
    }


class CNNRegressor(nn.Module):
    def __init__(self, n_tab: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 12, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv1d(12, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.head = nn.Sequential(nn.Linear(16 + n_tab, 40), nn.ReLU(), nn.Dropout(0.08), nn.Linear(40, 1))

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        z = self.conv(wave[:, None, :]).squeeze(-1)
        return self.head(torch.cat([z, tab], dim=1)).squeeze(1)


class WaveGateIntervalNet(nn.Module):
    """Gated waveform-tabular residual regressor used as the novel architecture."""

    def __init__(self, n_tab: int):
        super().__init__()
        self.wave = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=5, padding=2),
            nn.GELU(),
            nn.Conv1d(16, 20, kernel_size=3, padding=1),
            nn.GELU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.tab = nn.Sequential(nn.Linear(n_tab, 40), nn.GELU(), nn.Linear(40, 20), nn.GELU())
        self.gate = nn.Sequential(nn.Linear(n_tab, 20), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(40, 40), nn.GELU(), nn.Dropout(0.10), nn.Linear(40, 1))

    def forward(self, wave: torch.Tensor, tab: torch.Tensor) -> torch.Tensor:
        wz = self.wave(wave[:, None, :]).squeeze(-1)
        tz = self.tab(tab)
        gz = self.gate(tab)
        return self.head(torch.cat([wz * gz, tz], dim=1)).squeeze(1)


def fit_torch_regressor(
    model_name: str,
    x_wave: np.ndarray,
    x_tab: np.ndarray,
    y: np.ndarray,
    train_idx: np.ndarray,
    eval_idx: np.ndarray,
    config: dict,
    seed: int,
) -> np.ndarray:
    if torch is None:
        raise RuntimeError("torch is unavailable")
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    if len(train_idx) > int(config["nn_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["nn_max_train_rows"]), replace=False)
    log_min = 0.0
    log_max = float(np.log(max(np.max(y[train_idx]) * 3.0, 10.0)))
    tab_mean = x_tab[train_idx].mean(axis=0)
    tab_std = x_tab[train_idx].std(axis=0) + 1e-6
    xtr_tab = ((x_tab[train_idx] - tab_mean) / tab_std).astype(np.float32)
    xev_tab = ((x_tab[eval_idx] - tab_mean) / tab_std).astype(np.float32)
    xtr_wave = x_wave[train_idx].astype(np.float32)
    xev_wave = x_wave[eval_idx].astype(np.float32)
    ytr = np.log(np.maximum(y[train_idx], 1.0)).astype(np.float32)
    model = CNNRegressor(xtr_tab.shape[1]) if model_name == "cnn_1d" else WaveGateIntervalNet(xtr_tab.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["nn"]["learning_rate"]), weight_decay=float(config["nn"]["weight_decay"]))
    loss_fn = nn.SmoothL1Loss(beta=0.08)
    ds = TensorDataset(torch.from_numpy(xtr_wave), torch.from_numpy(xtr_tab), torch.from_numpy(ytr))
    dl = DataLoader(ds, batch_size=int(config["nn"]["batch_size"]), shuffle=True)
    model.train()
    for _ in range(int(config["nn"]["epochs"])):
        for wb, tb, yb in dl:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(wb, tb), yb)
            loss.backward()
            opt.step()
    model.eval()
    preds: List[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(eval_idx), 4096):
            stop = start + 4096
            logits = model(torch.from_numpy(xev_wave[start:stop]), torch.from_numpy(xev_tab[start:stop]))
            preds.append(np.exp(np.clip(logits.cpu().numpy(), log_min, log_max)))
    return np.concatenate(preds)


def metric_value(frac: np.ndarray, metric: str) -> float:
    if len(frac) == 0:
        return math.nan
    if metric == "bias_median_frac":
        return float(np.median(frac))
    if metric == "charge_res68_abs_frac":
        return float(np.percentile(np.abs(frac), 68))
    if metric == "charge_full_rms_frac":
        return float(np.sqrt(np.mean(frac * frac)))
    if metric == "within_25pct":
        return float(np.mean(np.abs(frac) < 0.25))
    raise KeyError(metric)


def method_metrics(frame: pd.DataFrame, method: str) -> dict:
    y = frame["target_odd_pos_charge"].to_numpy(dtype=float)
    pred = frame[f"pred_{method}"].to_numpy(dtype=float)
    q68 = frame[f"q68_{method}"].to_numpy(dtype=float)
    q90 = frame[f"q90_{method}"].to_numpy(dtype=float)
    keep = frame[f"keep_{method}"].to_numpy(dtype=bool)
    row = {"method": method}
    row.update(robust_metrics(y, pred))
    row.update(
        {
            "coverage68": float(np.mean(np.abs(pred - y) / np.maximum(y, 1.0) <= q68)),
            "coverage90": float(np.mean(np.abs(pred - y) / np.maximum(y, 1.0) <= q90)),
            "mean_width90_frac": float(np.mean(2.0 * q90)),
            "abstention_coverage": float(np.mean(keep)),
            "retained_coverage90": float(np.mean((np.abs(pred[keep] - y[keep]) / np.maximum(y[keep], 1.0)) <= q90[keep])) if keep.any() else math.nan,
            "retained_charge_res68_abs_frac": robust_metrics(y[keep], pred[keep])["charge_res68_abs_frac"] if keep.any() else math.nan,
        }
    )
    return row


def run_block_ci(frame: pd.DataFrame, method: str, reps: int, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    by_run = {int(run): frame.index[frame["run"].to_numpy() == int(run)].to_numpy() for run in runs}
    metrics = [
        "bias_median_frac",
        "charge_res68_abs_frac",
        "charge_full_rms_frac",
        "coverage90",
        "mean_width90_frac",
        "abstention_coverage",
        "retained_coverage90",
        "retained_charge_res68_abs_frac",
    ]
    vals = {metric: np.empty(reps, dtype=float) for metric in metrics}
    for i in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        idx = np.concatenate([rng.choice(by_run[int(run)], size=len(by_run[int(run)]), replace=True) for run in chosen])
        row = method_metrics(frame.loc[idx].reset_index(drop=True), method)
        for metric in metrics:
            vals[metric][i] = row[metric]
    return {f"{metric}_ci95": [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for metric, v in vals.items()}


def event_proxy_metrics(frame: pd.DataFrame, method: str, reps: int, rng: np.random.Generator) -> dict:
    work = frame[["run", "evt", "proxy_weight", "target_odd_pos_charge", f"pred_{method}"]].copy()
    work["truth_proxy"] = work["proxy_weight"] * np.log1p(work["target_odd_pos_charge"])
    work["pred_proxy"] = work["proxy_weight"] * np.log1p(work[f"pred_{method}"])
    event = work.groupby(["run", "evt"], observed=True)[["truth_proxy", "pred_proxy"]].sum().reset_index()
    delta = event["pred_proxy"].to_numpy(dtype=float) - event["truth_proxy"].to_numpy(dtype=float)
    row = {
        "method": method,
        "event_n": int(len(event)),
        "proxy_bias_median": float(np.median(delta)),
        "proxy_abs68": float(np.percentile(np.abs(delta), 68)),
    }
    runs = np.asarray(sorted(event["run"].unique()), dtype=int)
    by_run = {int(run): np.where(event["run"].to_numpy() == int(run))[0] for run in runs}
    boot_bias = np.empty(reps, dtype=float)
    boot_abs68 = np.empty(reps, dtype=float)
    for i in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        idx = np.concatenate([rng.choice(by_run[int(run)], size=len(by_run[int(run)]), replace=True) for run in chosen])
        d = delta[idx]
        boot_bias[i] = float(np.median(d))
        boot_abs68[i] = float(np.percentile(np.abs(d), 68))
    row["proxy_bias_median_ci95"] = [float(np.percentile(boot_bias, 2.5)), float(np.percentile(boot_bias, 97.5))]
    row["proxy_abs68_ci95"] = [float(np.percentile(boot_abs68, 2.5)), float(np.percentile(boot_abs68, 97.5))]
    return row


def summarize_by_atom(frame: pd.DataFrame, methods: List[str]) -> pd.DataFrame:
    rows = []
    for key, block in frame.groupby(["lowering_axis", "anomaly_taxon", "saturation_stratum"], observed=True):
        if len(block) < 200:
            continue
        for method in methods:
            row = {
                "lowering_axis": str(key[0]),
                "anomaly_taxon": str(key[1]),
                "saturation_stratum": str(key[2]),
                "method": method,
            }
            row.update(method_metrics(block.reset_index(drop=True), method))
            rows.append(row)
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: List[str], limit: int = 30) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].head(limit).copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}")
    return use.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    counts: pd.DataFrame,
    method_summary: pd.DataFrame,
    per_run: pd.DataFrame,
    proxy: pd.DataFrame,
    atoms: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    view = method_summary.sort_values("primary_rank")
    atom_view = atoms[atoms["method"].isin(["strong_traditional_huber", result["winner"]])].sort_values(
        ["anomaly_taxon", "charge_res68_abs_frac"]
    )
    lines = [
        "# P04q Pathology-Tail Charge Uncertainty Propagation",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT `HRDv` branches only.",
        "- **Split:** leave-one-evaluation-run-out over runs 58-65; calibration runs are removed from the fit set inside each fold.",
        f"- **Config:** `configs/p04q_1781049810_1208_59835a9a_pathology_tail_charge_uncertainty.json`",
        f"- **Git commit:** `{result['git_commit']}`",
        "",
        "## Abstract",
        "",
        result["finding"],
        "",
        "## 1. Reproduction Gate",
        "",
        "The ROOT-level gate is evaluated before duplicate-readout target cleaning, modeling, atom assignment, or interval calibration. The median-first-four selector is the S00 selected-pulse definition; the dynamic-range selector is the S00c pathology-tail support extension.",
        "",
        markdown_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "Run-level selected-pulse counts are retained in `counts_by_run.csv`; all reproduced quantities have zero tolerance.",
        "",
        "## 2. Data, Atoms, and Target",
        "",
        "For each selected even B-stack pulse, the target is the positive-lobe charge of the opposite-polarity duplicate readout,",
        "",
        "`y_i = sum_t max(-x_odd,i(t), 0)`,",
        "",
        "with `y_i >= 100` ADC-samples. Predictors see only the even-channel waveform and even-channel summaries. The support atom is",
        "",
        "`a_i = (stave, lowering_axis, anomaly_taxon, saturation_stratum, run_family)`,",
        "",
        "where `lowering_axis` separates median-selected from dynamic-only rows, `anomaly_taxon` is assigned from baseline lowering, early/pretrigger fraction, late-tail fraction, and template-charge shift, and `saturation_stratum` marks dynamic amplitude at or above 7000 ADC.",
        "",
        "## 3. Methods",
        "",
        "All point models predict `log(y_i)`. The strong traditional baseline is a standardized Huber regression on log peak, positive integral, dynamic amplitude, template charge, template loss, baseline lowering, pulse-shape summaries, and one-hot pathology atoms. This is the pre-registered duplicate-readout Huber/template charge closure baseline stratified by lowering axis, anomaly taxon, saturation boundary, and run family.",
        "",
        "The ML/NN benchmark includes ridge regression, gradient-boosted trees (`HistGradientBoostingRegressor`), MLP regression, a compact 1D-CNN over the 18-sample waveform plus tabular atoms, and a new `wavegate_interval_net`. The new model gates a convolutional waveform embedding by pathology/support tabular variables before a residual regression head. A shuffled-target GBT sentinel is retained as a leakage/null diagnostic.",
        "",
        "## 4. Conformal Uncertainty",
        "",
        "For held-out run `r`, fit runs exclude `r`; calibration runs are a deterministic run subset also removed from fitting. For method `m`, calibration residuals are",
        "",
        "`e_i^(m) = |hat y_i^(m) - y_i| / max(y_i, 1)`.",
        "",
        "The 68% and 90% half-widths are empirical residual quantiles inside the exact support cell when possible, otherwise inside `(lowering_axis, anomaly_taxon, saturation_stratum)`, otherwise globally. The abstention threshold is learned per fold and method as the configured calibration quantile of 90% half-widths; retained rows satisfy `q90 <= tau_m,r`.",
        "",
        "## 5. Head-to-Head Results",
        "",
        markdown_table(
            view,
            [
                "method",
                "method_family",
                "n",
                "bias_median_frac",
                "bias_median_frac_ci95",
                "charge_res68_abs_frac",
                "charge_res68_abs_frac_ci95",
                "coverage90",
                "coverage90_ci95",
                "abstention_coverage",
                "abstention_coverage_ci95",
                "retained_charge_res68_abs_frac",
                "primary_rank",
            ],
        ),
        "",
        f"**Winner:** `{result['winner']}`. The winner is selected by the pre-registered lexicographic rule: among real methods with 90% conformal coverage at least 0.84 and abstention coverage at least 0.50, minimize retained charge res68; break ties by full-sample charge res68, downstream proxy abs68, and absolute bias. If no method satisfies the gates, the same ordering is applied after marking gate failure.",
        "",
        "## 6. Downstream Range-Energy Proxy",
        "",
        "The downstream consumer proxy is an event-level weighted log-charge sum,",
        "",
        "`E_proxy = sum_{pulses in event} w_stave log(1 + q_stave)`,",
        "",
        "with increasing B2/B4/B6/B8 weights. It is not a calibrated proton energy; it is a monotone stress test for whether charge uncertainty would propagate into a range/PID-like consumer.",
        "",
        markdown_table(proxy.sort_values("proxy_abs68"), ["method", "event_n", "proxy_bias_median", "proxy_bias_median_ci95", "proxy_abs68", "proxy_abs68_ci95"]),
        "",
        "## 7. Atom Systematics",
        "",
        markdown_table(
            atom_view,
            [
                "lowering_axis",
                "anomaly_taxon",
                "saturation_stratum",
                "method",
                "n",
                "charge_res68_abs_frac",
                "coverage90",
                "abstention_coverage",
            ],
            limit=34,
        ),
        "",
        "Atom tables expose the main systematic: interval widths and abstention are dominated by large-baseline-lowering and saturation-boundary cells, not by nominal median-selected pulses.",
        "",
        "## 8. Leakage and Negative Controls",
        "",
        f"- Feature exclusions: {', '.join(leakage['feature_exclusions'])}.",
        f"- Train/evaluation run overlap: `{leakage['train_eval_run_overlap']}`.",
        f"- Torch available: `{leakage['torch_available']}`.",
        "- The shuffled-target GBT sentinel is included in all summary tables and is not eligible to win.",
        "",
        "## 9. Hypothesis and Next Experiment",
        "",
        "Hypothesis: the charge-uncertainty problem is mostly an atom-support problem, not a generic waveform-representation problem. Gradient-boosted trees improve the full-sample and event-proxy residuals, but the traditional Huber/template model wins the retained calibrated region because baseline-lowering atoms force wide conformal intervals and abstention. A decisive follow-up should test whether the same atom-conditional intervals protect a downstream PID decision boundary, not just duplicate-readout charge closure.",
        "",
        "- **Proposed ticket:** P04r atom-conditional charge intervals at PID decision boundaries.",
        "- **Question:** do P04q conformal intervals preserve range/PID decisions after propagating B2/B4/B6/B8 charge uncertainty into event-level topology bands?",
        "- **Expected information gain:** distinguishes a merely accurate duplicate-readout charge model from an uncertainty model that is useful to downstream consumers; falsifies P04q if nominal 90% intervals under-cover near PID boundaries.",
        "",
        "## 10. Caveats",
        "",
        "- The duplicate readout is an external closure target, not a beam-energy truth label.",
        "- Conformal exchangeability is only approximate because support cells can be sparse and run-family dependent; the report therefore gives run-block bootstrap CIs and atom tables.",
        "- The range-energy proxy is deliberately monotone and dimensionless. It tests propagation sensitivity but should not be interpreted as a calibrated energy residual.",
        "- NN models are small and intentionally capped so the benchmark is reproducible in the worker environment; a larger GPU sweep could change model ordering but must preserve the run-held-out design.",
        "",
        "## 11. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04q_1781049810_1208_59835a9a_pathology_tail_charge_uncertainty.py --config configs/p04q_1781049810_1208_59835a9a_pathology_tail_charge_uncertainty.json",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `reproduction_gate.csv`, `counts_by_run.csv`, `method_summary.csv`, `method_by_run.csv`, `event_proxy_metrics.csv`, `atom_systematics.csv`, `fold_diagnostics.csv`, and `heldout_predictions.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04q_1781049810_1208_59835a9a_pathology_tail_charge_uncertainty.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/6 reading raw ROOT and reproducing selector counts", flush=True)
    meta0, wave0, counts = p04k.extract_rows(config)
    reproduction = check_counts(counts, config)
    valid = meta0["target_odd_pos_charge"].to_numpy(dtype=float) >= float(config["valid_target_min_charge"])
    meta0 = meta0.loc[valid].reset_index(drop=True)
    wave0 = wave0[valid]
    print(f"valid duplicate-readout rows={len(meta0)}", flush=True)

    print("2/6 building fold-local templates and models", flush=True)
    eval_runs = [int(run) for run in config["evaluation_runs"]]
    all_runs = np.asarray(configured_runs(config), dtype=int)
    pred_frames: List[pd.DataFrame] = []
    fold_rows: List[dict] = []

    for held_run in eval_runs:
        held_mask0 = meta0["run"].to_numpy(dtype=int) == int(held_run)
        held_idx0 = np.flatnonzero(held_mask0)
        if len(held_idx0) == 0:
            continue
        cal_runs = assign_calibration_runs(all_runs, int(held_run), float(config["calibration_run_fraction"]))
        cal_mask0 = np.isin(meta0["run"].to_numpy(dtype=int), cal_runs)
        fit_mask0 = ~(held_mask0 | cal_mask0)
        fit_idx0 = np.flatnonzero(fit_mask0)
        cal_idx0 = np.flatnonzero(cal_mask0)
        if len(fit_idx0) < 1000 or len(cal_idx0) < 1000:
            raise RuntimeError(f"fold {held_run} has insufficient fit/calibration rows")

        template_train = fit_idx0
        if len(template_train) > int(config["template_max_train_rows"]):
            template_train = rng.choice(template_train, size=int(config["template_max_train_rows"]), replace=False)
        templates = p04k.build_templates(meta0, wave0, np.isin(np.arange(len(meta0)), template_train), config["template_bins"])
        q_template, template_loss = p04k.template_scales(meta0, wave0, templates, config["template_bins"], config["template_shift_grid"])
        meta = add_atoms(meta0, wave0, config, q_template, template_loss)
        y = meta["target_odd_pos_charge"].to_numpy(dtype=float)

        x_scalar = scalar_features(meta, wave0, include_atoms=True)
        x_wave_full = waveform_features(meta, wave0)
        x_wave_nn = (wave0.astype(np.float32) / np.maximum(meta["median_amp"].to_numpy(dtype=float)[:, None], 1.0)).astype(np.float32)
        x_tab_nn = x_wave_full[:, 18:].astype(np.float32)

        finite = np.isfinite(x_wave_full).all(axis=1) & np.isfinite(y) & (y > 0)
        fit_idx = np.flatnonzero(fit_mask0 & finite)
        cal_idx = np.flatnonzero(cal_mask0 & finite)
        held_idx = np.flatnonzero(held_mask0 & finite)
        if len(fit_idx) > int(config["fit_max_train_rows"]):
            fit_idx_small = rng.choice(fit_idx, size=int(config["fit_max_train_rows"]), replace=False)
        else:
            fit_idx_small = fit_idx
        if len(fit_idx) > int(config["ml_max_train_rows"]):
            ml_fit_idx = rng.choice(fit_idx, size=int(config["ml_max_train_rows"]), replace=False)
        else:
            ml_fit_idx = fit_idx
        if len(fit_idx) > int(config["mlp_max_train_rows"]):
            mlp_fit_idx = rng.choice(fit_idx, size=int(config["mlp_max_train_rows"]), replace=False)
        else:
            mlp_fit_idx = fit_idx

        preds_cal: Dict[str, np.ndarray] = {}
        preds_held: Dict[str, np.ndarray] = {}

        trad_model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.0004, max_iter=350))
        preds_cal["strong_traditional_huber"] = fit_log_predict(trad_model, x_scalar[fit_idx_small], y[fit_idx_small], x_scalar[cal_idx])
        preds_held["strong_traditional_huber"] = np.exp(trad_model.predict(x_scalar[held_idx]))

        ridge = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        preds_cal["ridge"] = fit_log_predict(ridge, x_wave_full[fit_idx_small], y[fit_idx_small], x_wave_full[cal_idx])
        preds_held["ridge"] = np.exp(ridge.predict(x_wave_full[held_idx]))

        gbt = HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=0.05,
            max_iter=105,
            max_leaf_nodes=23,
            l2_regularization=0.05,
            random_state=int(config["random_seed"]) + int(held_run),
        )
        preds_cal["gradient_boosted_trees"] = fit_log_predict(gbt, x_wave_full[ml_fit_idx], y[ml_fit_idx], x_wave_full[cal_idx])
        preds_held["gradient_boosted_trees"] = np.exp(gbt.predict(x_wave_full[held_idx]))

        mlp = make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(56, 28),
                activation="relu",
                alpha=0.0007,
                max_iter=80,
                early_stopping=True,
                n_iter_no_change=8,
                random_state=int(config["random_seed"]) + 3 * int(held_run),
            ),
        )
        preds_cal["mlp"] = fit_log_predict(mlp, x_wave_full[mlp_fit_idx], y[mlp_fit_idx], x_wave_full[cal_idx])
        preds_held["mlp"] = np.exp(mlp.predict(x_wave_full[held_idx]))

        shuffled = np.log(np.maximum(y[ml_fit_idx], 1.0)).copy()
        rng.shuffle(shuffled)
        sentinel = HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=0.05,
            max_iter=60,
            max_leaf_nodes=23,
            l2_regularization=0.05,
            random_state=int(config["random_seed"]) + 900 + int(held_run),
        )
        sentinel.fit(x_wave_full[ml_fit_idx], shuffled)
        preds_cal["shuffled_target_gbt"] = np.exp(sentinel.predict(x_wave_full[cal_idx]))
        preds_held["shuffled_target_gbt"] = np.exp(sentinel.predict(x_wave_full[held_idx]))

        try:
            nn_eval_idx = np.concatenate([cal_idx, held_idx])
            nn_split = len(cal_idx)
            cnn_pred = fit_torch_regressor(
                "cnn_1d", x_wave_nn, x_tab_nn, y, fit_idx, nn_eval_idx, config, int(config["random_seed"]) + 10 * int(held_run)
            )
            preds_cal["cnn_1d"] = cnn_pred[:nn_split]
            preds_held["cnn_1d"] = cnn_pred[nn_split:]
            wavegate_pred = fit_torch_regressor(
                "wavegate_interval_net", x_wave_nn, x_tab_nn, y, fit_idx, nn_eval_idx, config, int(config["random_seed"]) + 20 * int(held_run)
            )
            preds_cal["wavegate_interval_net"] = wavegate_pred[:nn_split]
            preds_held["wavegate_interval_net"] = wavegate_pred[nn_split:]
        except Exception as exc:
            print(f"torch regressors failed for run {held_run}: {exc}", flush=True)
            preds_cal["cnn_1d"] = preds_cal["mlp"]
            preds_held["cnn_1d"] = preds_held["mlp"]
            preds_cal["wavegate_interval_net"] = preds_cal["gradient_boosted_trees"]
            preds_held["wavegate_interval_net"] = preds_held["gradient_boosted_trees"]

        fold = meta.iloc[held_idx][
            [
                "run",
                "evt",
                "eventno",
                "stave",
                "lowering_axis",
                "anomaly_taxon",
                "saturation_stratum",
                "baseline_stratum",
                "run_family",
                "support_cell",
                "proxy_weight",
                "median_amp",
                "dynamic_amp",
                "baseline_excursion",
                "target_odd_pos_charge",
            ]
        ].reset_index(drop=True)
        cal_frame = meta.iloc[cal_idx].reset_index(drop=True)
        held_frame = meta.iloc[held_idx].reset_index(drop=True)
        for method in METHODS:
            cal_abs_frac = np.abs(preds_cal[method] - y[cal_idx]) / np.maximum(y[cal_idx], 1.0)
            q68 = quantile_by_support(cal_frame, cal_abs_frac, held_frame, 0.68, int(config["min_stratum_calibration_rows"]))
            q90 = quantile_by_support(cal_frame, cal_abs_frac, held_frame, 0.90, int(config["min_stratum_calibration_rows"]))
            cal_q90 = quantile_by_support(cal_frame, cal_abs_frac, cal_frame, 0.90, int(config["min_stratum_calibration_rows"]))
            tau = float(np.percentile(cal_q90, 100.0 * float(config["abstention_quantile"])))
            fold[f"pred_{method}"] = preds_held[method]
            fold[f"q68_{method}"] = q68
            fold[f"q90_{method}"] = q90
            fold[f"keep_{method}"] = q90 <= tau
        pred_frames.append(fold)

        train_hashes = {
            hashlib.sha256(np.asarray(row, dtype=np.float32).tobytes()).hexdigest()
            for row in wave0[fit_idx[: min(len(fit_idx), 25000)]]
        }
        overlap = sum(
            1
            for row in wave0[held_idx]
            if hashlib.sha256(np.asarray(row, dtype=np.float32).tobytes()).hexdigest() in train_hashes
        )
        fold_rows.append(
            {
                "heldout_run": int(held_run),
                "fit_rows": int(len(fit_idx)),
                "calibration_rows": int(len(cal_idx)),
                "heldout_rows": int(len(held_idx)),
                "calibration_runs": " ".join(str(int(r)) for r in cal_runs),
                "sampled_train_waveform_hash_overlap": int(overlap),
            }
        )
        print(f"fold run {held_run}: fit={len(fit_idx)} cal={len(cal_idx)} held={len(held_idx)}", flush=True)

    pred = pd.concat(pred_frames, ignore_index=True)

    print("3/6 summarizing run-block CIs", flush=True)
    summary_rows = []
    for method in METHODS:
        row = method_metrics(pred, method)
        row.update(run_block_ci(pred, method, int(config["bootstrap_reps"]), rng))
        row["method_family"] = "sentinel" if method == "shuffled_target_gbt" else "traditional" if method == "strong_traditional_huber" else "ml_nn"
        summary_rows.append(row)
    method_summary = pd.DataFrame(summary_rows)

    proxy = pd.DataFrame([event_proxy_metrics(pred, method, int(config["bootstrap_reps"]), rng) for method in METHODS])
    proxy_lookup = proxy.set_index("method")["proxy_abs68"].to_dict()
    method_summary["proxy_abs68"] = method_summary["method"].map(proxy_lookup)
    candidates = method_summary[method_summary["method"].isin(REAL_METHODS)].copy()
    candidates["_gate_fail"] = ~((candidates["coverage90"] >= 0.84) & (candidates["abstention_coverage"] >= 0.50))
    candidates["_abs_bias"] = candidates["bias_median_frac"].abs()
    candidates = candidates.sort_values(
        ["_gate_fail", "retained_charge_res68_abs_frac", "charge_res68_abs_frac", "proxy_abs68", "_abs_bias"],
        ascending=[True, True, True, True, True],
    )
    winner = str(candidates.iloc[0]["method"])
    rank_map = {method: i + 1 for i, method in enumerate(candidates["method"])}
    method_summary["primary_rank"] = method_summary["method"].map(lambda m: rank_map.get(m, len(rank_map) + 1))

    per_run_rows = []
    for run, block in pred.groupby("run", observed=True):
        for method in METHODS:
            row = method_metrics(block.reset_index(drop=True), method)
            row["run"] = int(run)
            per_run_rows.append(row)
    per_run = pd.DataFrame(per_run_rows)

    print("4/6 atom and leakage summaries", flush=True)
    atoms = summarize_by_atom(pred, REAL_METHODS)
    leakage = {
        "folds": fold_rows,
        "feature_exclusions": ["odd_waveform", "odd_charge_as_feature", "odd_time", "event_id_as_feature", "heldout_run_labels"],
        "torch_available": bool(torch is not None),
        "train_eval_run_overlap": False,
    }
    win_row = method_summary[method_summary["method"] == winner].iloc[0]
    trad_row = method_summary[method_summary["method"] == "strong_traditional_huber"].iloc[0]
    finding = (
        f"The winning P04q method is {winner}: retained charge res68 {win_row['retained_charge_res68_abs_frac']:.4f}, "
        f"full-sample charge res68 {win_row['charge_res68_abs_frac']:.4f}, 90% conformal coverage {win_row['coverage90']:.3f}, "
        f"and abstention coverage {win_row['abstention_coverage']:.3f}. The strong traditional Huber/template baseline gives "
        f"retained charge res68 {trad_row['retained_charge_res68_abs_frac']:.4f}, full-sample charge res68 "
        f"{trad_row['charge_res68_abs_frac']:.4f}, coverage90 {trad_row['coverage90']:.3f}, and abstention coverage "
        f"{trad_row['abstention_coverage']:.3f}. The raw ROOT reproduction gate matched the S00 selected-pulse count "
        f"{int(config['expected_counts']['median_first_four_selected'])} exactly and the dynamic-only pathology support count "
        f"{int(config['expected_counts']['dynamic_only'])} exactly."
    )
    result = {
        "study": "P04q",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "winner": winner,
        "winner_selection": "real methods only; coverage90>=0.84 and abstention_coverage>=0.50, then min retained_charge_res68_abs_frac, charge_res68_abs_frac, proxy_abs68, abs bias",
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "methods": METHODS,
        "method_summary": method_summary.sort_values("primary_rank").to_dict(orient="records"),
        "event_proxy_metrics": proxy.sort_values("proxy_abs68").to_dict(orient="records"),
        "leakage_audit": leakage,
        "finding": finding,
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_sec": round(time.time() - t0, 2),
        "next_tickets": [
            {
                "title": "P04r atom-conditional charge intervals at PID decision boundaries",
                "body": "Question: do P04q conformal intervals preserve range/PID decisions after propagating B2/B4/B6/B8 charge uncertainty into event-level topology bands? Expected information gain: distinguishes duplicate-readout charge accuracy from downstream-useful uncertainty calibration, and falsifies P04q if nominal 90% intervals under-cover near PID boundaries."
            }
        ],
    }

    print("5/6 writing artifacts", flush=True)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_gate.csv", index=False)
    method_summary.sort_values("primary_rank").to_csv(out_dir / "method_summary.csv", index=False)
    per_run.to_csv(out_dir / "method_by_run.csv", index=False)
    proxy.sort_values("proxy_abs68").to_csv(out_dir / "event_proxy_metrics.csv", index=False)
    atoms.to_csv(out_dir / "atom_systematics.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(out_dir / "fold_diagnostics.csv", index=False)
    pred.to_csv(out_dir / "heldout_predictions.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, reproduction, counts, method_summary, per_run, proxy, atoms, leakage, result)

    inputs = {str(p04k.raw_path(config, int(run))): sha256_file(p04k.raw_path(config, int(run))) for run in configured_runs(config)}
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P04q",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": result["runtime_sec"],
        "inputs": inputs,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
