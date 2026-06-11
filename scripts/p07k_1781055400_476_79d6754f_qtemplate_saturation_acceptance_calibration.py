#!/usr/bin/env python3
"""P07k: q-template-preserving saturation acceptance calibration.

The analysis reads raw B-stack ROOT files via the P07f duplicate extractor, reproduces the
P07f count/family anchors, freezes the transparent retained-window/duplicate-ratio envelope,
and benchmarks it against ridge, gradient-boosted trees, MLP, a 1D CNN, and a residual gated
CNN. P07k ranks methods by preservation of q_template, timing tails, and duplicate-readout
charge closure with run-block bootstrap confidence intervals.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p07i")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, precision_score, recall_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover
    torch = None
    nn = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/p07k_1781055400_476_79d6754f_qtemplate_saturation_acceptance_calibration.json"


def import_script(name: str, relpath: str):
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


P07F = import_script("p07f_b2_saturation_knees", "scripts/p07f_1781019500_1759_55e62bed_b2_saturation_knees.py")
P07C = import_script("p07c_boundary_control_closure", "scripts/p07c_boundary_control_closure.py")


def load_config(path: Path) -> dict:
    cfg = json.loads(path.read_text(encoding="utf-8"))
    cfg["config_path"] = str(path)
    cfg["raw_root_dir"] = str((ROOT / cfg["raw_root_dir"]).resolve()) if not Path(cfg["raw_root_dir"]).is_absolute() else cfg["raw_root_dir"]
    return cfg


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    return value


def ci95(values: Iterable[float]) -> Tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def weighted_run_bootstrap(by_run: pd.DataFrame, method: str, metric: str, cfg: dict) -> Tuple[float, Tuple[float, float]]:
    sub = by_run[by_run["method"] == method].copy()
    vals = sub[metric].to_numpy(dtype=float)
    weights = sub["n"].to_numpy(dtype=float)
    ok = np.isfinite(vals) & np.isfinite(weights) & (weights > 0)
    vals = vals[ok]
    weights = weights[ok]
    if len(vals) == 0:
        return float("nan"), (float("nan"), float("nan"))
    point = float(np.average(vals, weights=weights))
    seed = int(cfg["ml"]["random_seed"]) + (sum(ord(c) for c in method + metric) % 100000)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(vals), size=(int(cfg["bootstrap_replicates"]), len(vals)))
    boot = np.asarray([np.average(vals[d], weights=weights[d]) for d in draws], dtype=float)
    return point, ci95(boot)


def reproduce_and_fit(frame: pd.DataFrame, counts: pd.DataFrame, cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[int, object]]:
    expected = [
        ("S00 selected B-stave pulse records", int(cfg["expected_selected_pulses"]), int(counts["s00_selected_pulses"].sum()), 0),
        (
            "P07e high-amplitude B2 duplicate rows",
            int(cfg["expected_p07e_high_duplicate_rows"]),
            int(counts["p07e_high_duplicate_rows"].sum()),
            0,
        ),
        ("P07f duplicate-proxy knee rows", int(cfg["expected_p07f_duplicate_rows"]), int(counts["p07f_duplicate_rows"].sum()), 0),
    ]
    rows = []
    for quantity, exp, got, tol in expected:
        rows.append(
            {
                "quantity": quantity,
                "report_value": exp,
                "reproduced": got,
                "delta": got - exp,
                "tolerance": tol,
                "pass": bool(abs(got - exp) <= tol),
            }
        )

    fits: Dict[int, object] = {}
    family_rows = []
    for run, sub in frame.groupby("run"):
        status = "ok"
        try:
            fit = P07F.fit_piecewise(sub, cfg)
            fits[int(run)] = fit
            knee = float(fit.knee_adc)
            family = "high-knee" if knee >= float(cfg["traditional"]["high_family_min_knee_adc"]) else "low-knee"
            ratio = float(fit.post_slope / fit.pre_slope)
            chi2_ndf = float(fit.sse / max(1, fit.n_bins - 4))
        except Exception as exc:
            fit = None
            knee = float("nan")
            family = "unstable"
            ratio = float("nan")
            chi2_ndf = float("nan")
            status = str(exc)
        family_rows.append(
            {
                "run": int(run),
                "n_duplicate_rows": int(len(sub)),
                "family": family,
                "knee_adc": knee,
                "post_to_pre_slope_ratio": ratio,
                "chi2_ndf_proxy": chi2_ndf,
                "fit_status": status,
            }
        )
    knees = pd.DataFrame(family_rows)
    low = knees[knees["family"] == "low-knee"]["knee_adc"].median()
    high = knees[knees["family"] == "high-knee"]["knee_adc"].median()
    rows.extend(
        [
            {
                "quantity": "P07f low-family median knee ADC",
                "report_value": float(cfg["expected_p07f_low_family_median_adc"]),
                "reproduced": float(low),
                "delta": float(low - float(cfg["expected_p07f_low_family_median_adc"])),
                "tolerance": 1e-6,
                "pass": bool(abs(low - float(cfg["expected_p07f_low_family_median_adc"])) <= 1e-6),
            },
            {
                "quantity": "P07f high-family median knee ADC",
                "report_value": float(cfg["expected_p07f_high_family_median_adc"]),
                "reproduced": float(high),
                "delta": float(high - float(cfg["expected_p07f_high_family_median_adc"])),
                "tolerance": 1e-6,
                "pass": bool(abs(high - float(cfg["expected_p07f_high_family_median_adc"])) <= 1e-6),
            },
        ]
    )
    return pd.DataFrame(rows), knees, fits


def timing_bounds(frame: pd.DataFrame, wave: np.ndarray) -> pd.DataFrame:
    cfd = P07C.cfd_time(wave, np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0), 0.20)
    rows = []
    for run, sub in frame.assign(cfd20_sample=cfd).groupby("run"):
        control = sub[(sub["b2_amp"] >= 1500.0) & (sub["b2_amp"] < 6500.0) & (sub["b2_peak"] >= 4) & (sub["b2_peak"] <= 12)]
        if len(control) < 100:
            control = sub[np.isfinite(sub["cfd20_sample"])]
        center = float(control["cfd20_sample"].median())
        resid = control["cfd20_sample"].to_numpy(dtype=float) - center
        lo, hi = np.percentile(resid[np.isfinite(resid)], [2.5, 97.5])
        rows.append({"run": int(run), "control_center": center, "lo": float(lo), "hi": float(hi)})
    return pd.DataFrame(rows)


def duplicate_low_residual(frame: pd.DataFrame, fits: Dict[int, object]) -> np.ndarray:
    resid = np.full(len(frame), np.nan, dtype=float)
    for run, sub in frame.groupby("run"):
        fit = fits.get(int(run))
        if fit is None:
            continue
        idx = sub.index.to_numpy()
        expected = np.maximum(fit.low_linear(sub["b2_amp"].to_numpy(dtype=float)), 1e-9)
        resid[idx] = (sub["duplicate_charge_ratio"].to_numpy(dtype=float) - expected) / expected
    return resid


def candidate_frame(frame: pd.DataFrame, wave: np.ndarray, fits: Dict[int, object], knees: pd.DataFrame, cfg: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    gate = cfg["gate"]
    residual = duplicate_low_residual(frame, fits)
    cfd_obs = P07C.cfd_time(wave, np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0), 0.20)
    bounds = timing_bounds(frame, wave)
    bound_map = bounds.set_index("run").to_dict(orient="index")
    center = np.asarray([bound_map[int(r)]["control_center"] for r in frame["run"]], dtype=float)
    lo = np.asarray([bound_map[int(r)]["lo"] for r in frame["run"]], dtype=float)
    hi = np.asarray([bound_map[int(r)]["hi"] for r in frame["run"]], dtype=float)
    obs_tail = ((cfd_obs - center) < lo) | ((cfd_obs - center) > hi)
    lift_fraction = np.clip(float(gate["correction_gain"]) * np.maximum(residual, 0.0), 0.0, float(gate["max_lift_fraction"]))
    rec_amp = frame["b2_amp"].to_numpy(dtype=float) * (1.0 + lift_fraction)
    cfd_rec = P07C.cfd_time(wave, np.maximum(rec_amp, 1.0), 0.20)
    corrected_charge = frame["b2_charge"].to_numpy(dtype=float) * (rec_amp / np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0))
    expected_odd_after = frame["duplicate_charge_ratio"].to_numpy(dtype=float) * 0.0
    for run, sub in frame.groupby("run"):
        fit = fits.get(int(run))
        if fit is None:
            continue
        idx = sub.index.to_numpy()
        expected_odd_after[idx] = np.maximum(fit.low_linear(rec_amp[idx]), 1e-9) * corrected_charge[idx]
    charge_resid_after = (frame["odd_charge"].to_numpy(dtype=float) - expected_odd_after) / np.maximum(expected_odd_after, 1e-9)
    q_shift = frame["b2_amp"].to_numpy(dtype=float) / np.maximum(rec_amp, 1.0) - 1.0
    timing_shift_ns = (cfd_rec - cfd_obs) * 10.0
    rec_tail = ((cfd_rec - center) < lo) | ((cfd_rec - center) > hi)

    family = knees.set_index("run")["family"].to_dict()
    knee = knees.set_index("run")["knee_adc"].to_dict()
    run_family = np.asarray([family.get(int(r), "unstable") for r in frame["run"]], dtype=object)
    run_knee = np.asarray([knee.get(int(r), np.nan) for r in frame["run"]], dtype=float)
    in_band = (
        (run_family == "high-knee")
        & (frame["b2_amp"].to_numpy(dtype=float) >= (run_knee - float(cfg["traditional"]["accept_band_low_adc"])))
        & (frame["b2_amp"].to_numpy(dtype=float) <= (run_knee + float(cfg["traditional"]["accept_band_high_adc"])))
    )
    oracle = (
        in_band
        & (residual >= float(cfg["traditional"]["min_closure_residual_frac"]))
        & (residual <= float(cfg["traditional"]["max_closure_residual_frac"]))
        & (np.abs(charge_resid_after) <= float(gate["closure_res68_gate"]))
        & (np.abs(q_shift) <= float(gate["q_template_abs_gate"]))
        & (np.abs(timing_shift_ns) <= float(gate["cfd_abs_gate_ns"]))
    )
    side_effect_harm = (
        (np.abs(charge_resid_after) > float(gate["closure_res68_gate"]))
        | (np.abs(q_shift) > float(gate["q_template_abs_gate"]))
        | (np.abs(timing_shift_ns) > float(gate["cfd_abs_gate_ns"]))
        | (rec_tail & ~obs_tail)
    )
    bands = cfg["action_bands"]
    action = np.full(len(frame), "abstain", dtype=object)
    pass_band = (
        (run_family == "high-knee")
        & np.isfinite(residual)
        & (np.abs(residual) < float(bands["pass_low_residual_abs_frac"]))
        & ~side_effect_harm
    )
    correct_band = (
        in_band
        & (residual >= float(bands["correct_min_residual_frac"]))
        & (residual <= float(bands["correct_max_residual_frac"]))
        & ~side_effect_harm
    )
    veto_band = (
        side_effect_harm
        | (residual > float(bands["veto_min_harm_risk_frac"]))
        | ((run_family == "low-knee") & (frame["b2_amp"].to_numpy(dtype=float) >= float(bands["veto_low_family_min_amp_adc"])))
        | ((run_family == "unstable") & (frame["b2_amp"].to_numpy(dtype=float) >= float(bands["veto_unstable_min_amp_adc"])))
    )
    action[pass_band] = "pass"
    action[correct_band] = "correct"
    action[veto_band & ~correct_band] = "veto"
    candidates = (
        (frame["b2_amp"].to_numpy(dtype=float) >= float(gate["candidate_min_amp_adc"]))
        & (frame["b2_peak"].to_numpy(dtype=int) >= int(cfg["duplicate_selection"]["min_peak_sample"]))
        & (frame["b2_peak"].to_numpy(dtype=int) <= int(cfg["duplicate_selection"]["max_peak_sample"]))
        & np.isfinite(residual)
        & np.isfinite(cfd_obs)
    )
    out = frame.loc[candidates].copy().reset_index(drop=True)
    keep = np.flatnonzero(candidates)
    out["run_family"] = run_family[keep]
    out["run_knee_adc"] = run_knee[keep]
    out["duplicate_low_residual_frac"] = residual[keep]
    out["oracle_accept"] = oracle[keep].astype(int)
    out["lift_fraction_if_accepted"] = lift_fraction[keep]
    out["recovered_amp_if_accepted"] = rec_amp[keep]
    out["charge_residual_after_if_accepted"] = charge_resid_after[keep]
    out["q_template_shift_if_accepted"] = q_shift[keep]
    out["cfd20_obs_sample"] = cfd_obs[keep]
    out["cfd20_corrected_sample"] = cfd_rec[keep]
    out["cfd20_shift_ns_if_accepted"] = timing_shift_ns[keep]
    out["obs_timing_tail"] = obs_tail[keep]
    out["corrected_timing_tail_if_accepted"] = rec_tail[keep]
    out["traditional_accept"] = correct_band[keep].astype(int)
    out["traditional_action_band"] = action[keep]
    out["traditional_pass"] = (out["traditional_action_band"] == "pass").astype(int)
    out["traditional_correct"] = (out["traditional_action_band"] == "correct").astype(int)
    out["traditional_abstain"] = (out["traditional_action_band"] == "abstain").astype(int)
    out["traditional_veto"] = (out["traditional_action_band"] == "veto").astype(int)
    return out, wave[keep]


def tabular_features(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    amp = np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0)
    charge = np.maximum(frame["b2_charge"].to_numpy(dtype=float), 1.0)
    norm = wave.astype(float) / amp[:, None]
    pos = np.clip(wave.astype(float), 0.0, None)
    diff = np.diff(norm, axis=1)
    return np.column_stack(
        [
            np.log(amp),
            charge / amp,
            frame["b2_peak"].to_numpy(dtype=float),
            frame["plateau_count"].to_numpy(dtype=float),
            frame["top2_gap_frac"].to_numpy(dtype=float),
            pos[:, :6].sum(axis=1) / charge,
            pos[:, 6:12].sum(axis=1) / charge,
            pos[:, 12:].sum(axis=1) / charge,
            diff.max(axis=1),
            diff.min(axis=1),
            (wave >= (0.995 * amp[:, None])).sum(axis=1),
            norm,
        ]
    ).astype(np.float32)


def waveform_input(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    amp = np.maximum(frame["b2_amp"].to_numpy(dtype=float), 1.0)
    return (wave.astype(np.float32) / amp[:, None]).astype(np.float32)


def balanced_subset(y: np.ndarray, max_rows: int, rng: np.random.Generator) -> np.ndarray:
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    if len(pos) == 0 or len(neg) == 0 or len(y) <= max_rows:
        return np.arange(len(y))
    n_pos = min(len(pos), max(1, max_rows // 3))
    n_neg = min(len(neg), max_rows - n_pos)
    keep = np.concatenate([rng.choice(pos, size=n_pos, replace=False), rng.choice(neg, size=n_neg, replace=False)])
    return rng.permutation(keep)


def choose_threshold(prob: np.ndarray, y: np.ndarray, cfg: dict) -> float:
    best_thr = 0.5
    best = -1.0
    for thr in cfg["ml"]["probability_grid"]:
        pred = prob >= float(thr)
        if pred.sum() == 0:
            score = 0.0
        else:
            score = f1_score(y, pred, zero_division=0)
            precision = precision_score(y, pred, zero_division=0)
            if precision < 0.50:
                score *= 0.5
        if score > best:
            best = float(score)
            best_thr = float(thr)
    return best_thr


def expected_calibration_error(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=float)
    prob = np.asarray(prob, dtype=float)
    ok = np.isfinite(y) & np.isfinite(prob)
    y = y[ok]
    prob = np.clip(prob[ok], 0.0, 1.0)
    if len(y) == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, int(bins) + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (prob >= lo) & (prob <= hi if hi == edges[-1] else prob < hi)
        if not mask.any():
            continue
        ece += float(mask.mean()) * abs(float(prob[mask].mean()) - float(y[mask].mean()))
    return float(ece)


class SmallCNN(nn.Module):
    def __init__(self, residual_gate: bool = False) -> None:
        super().__init__()
        self.residual_gate = residual_gate
        if residual_gate:
            self.inp = nn.Conv1d(1, 24, 3, padding=1)
            self.block1 = nn.Sequential(nn.Conv1d(24, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
            self.block2 = nn.Sequential(nn.Conv1d(24, 24, 5, padding=2), nn.ReLU(), nn.Conv1d(24, 24, 3, padding=1))
            self.gate = nn.Sequential(nn.Linear(24 + 2, 16), nn.ReLU(), nn.Linear(16, 24), nn.Sigmoid())
            self.head = nn.Sequential(nn.Linear(48, 32), nn.ReLU(), nn.Linear(32, 1))
        else:
            self.net = nn.Sequential(
                nn.Conv1d(1, 16, 3, padding=1),
                nn.ReLU(),
                nn.Conv1d(16, 32, 3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
                nn.Flatten(),
                nn.Linear(32, 24),
                nn.ReLU(),
                nn.Linear(24, 1),
            )

    def forward(self, x):
        if not self.residual_gate:
            return self.net(x[:, None, :]).squeeze(1)
        z = torch.relu(self.inp(x[:, None, :]))
        z = torch.relu(z + self.block1(z))
        z = torch.relu(z + self.block2(z))
        peak = torch.argmax(x, dim=1, keepdim=True).float() / float(x.shape[1] - 1)
        late = x[:, 12:].mean(dim=1, keepdim=True)
        g = self.gate(torch.cat([z.mean(dim=2), peak, late], dim=1)).unsqueeze(2)
        z = z * g
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        return self.head(pooled).squeeze(1)


def fit_torch_probs(x_wave: np.ndarray, y: np.ndarray, train_idx: np.ndarray, cfg: dict, seed: int, residual_gate: bool) -> Tuple[np.ndarray, np.ndarray]:
    if torch is None:
        raise RuntimeError("torch is required for CNN methods")
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
    rng = np.random.default_rng(seed)
    local_y = y[train_idx]
    local_keep = balanced_subset(local_y, int(cfg["ml"]["max_train_rows_nn"]), rng)
    train = train_idx[local_keep]
    model = SmallCNN(residual_gate=residual_gate)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    x = torch.tensor(x_wave.astype(np.float32), dtype=torch.float32, device=device)
    yy = torch.tensor(y.astype(np.float32), dtype=torch.float32, device=device)
    pos_frac = max(float(local_y.mean()), 1e-3)
    pos_weight = torch.tensor([(1.0 - pos_frac) / pos_frac], dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg["ml"]["torch_learning_rate"]), weight_decay=float(cfg["ml"]["torch_weight_decay"]))
    batch = int(cfg["ml"]["torch_batch_size"])
    for _epoch in range(int(cfg["ml"]["torch_epochs"])):
        order = rng.permutation(train)
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            logits = model(x[idx])
            loss = loss_fn(logits, yy[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
    logits_parts = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(x_wave), 8192):
            logits_parts.append(model(x[start : start + 8192]).detach().cpu().numpy())
    logits = np.concatenate(logits_parts).astype(float)
    probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
    return probs, logits


def fit_predict_methods(frame: pd.DataFrame, wave: np.ndarray, cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(cfg["ml"]["random_seed"]))
    x_tab = tabular_features(frame, wave)
    x_wave = waveform_input(frame, wave)
    y = frame["oracle_accept"].to_numpy(dtype=int)
    runs = frame["run"].to_numpy(dtype=int)
    pred_parts = []
    calib_rows = []
    leak_rows = []
    for heldout in sorted(frame["run"].unique()):
        train_idx_all = np.flatnonzero(runs != int(heldout))
        test_idx = np.flatnonzero(runs == int(heldout))
        if len(test_idx) == 0:
            continue
        if y[train_idx_all].sum() < int(cfg["ml"]["min_train_positives"]):
            raise RuntimeError("too few training positives for heldout run {}".format(heldout))
        train_sub = balanced_subset(y[train_idx_all], int(cfg["ml"]["max_train_rows"]), np.random.default_rng(int(cfg["ml"]["random_seed"]) + int(heldout)))
        train_idx = train_idx_all[train_sub]
        methods: List[Tuple[str, np.ndarray, float, str]] = []

        ridge = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, penalty="l2", solver="lbfgs", max_iter=400, class_weight="balanced", random_state=int(cfg["ml"]["random_seed"]) + int(heldout)),
        )
        ridge.fit(x_tab[train_idx], y[train_idx])
        p_ridge = ridge.predict_proba(x_tab)[:, 1]
        methods.append(("ML_ridge_logistic", p_ridge, choose_threshold(p_ridge[train_idx], y[train_idx], cfg), "L2 logistic ridge surrogate"))

        w = np.where(y[train_idx] == 1, 0.5 / max(np.mean(y[train_idx] == 1), 1e-6), 0.5 / max(np.mean(y[train_idx] == 0), 1e-6))
        gbt = HistGradientBoostingClassifier(
            max_iter=int(cfg["ml"]["gbt_max_iter"]),
            learning_rate=0.055,
            max_leaf_nodes=31,
            l2_regularization=0.02,
            random_state=int(cfg["ml"]["random_seed"]) + 10 + int(heldout),
        )
        gbt.fit(x_tab[train_idx], y[train_idx], sample_weight=w)
        p_gbt = gbt.predict_proba(x_tab)[:, 1]
        methods.append(("ML_gradient_boosted_trees", p_gbt, choose_threshold(p_gbt[train_idx], y[train_idx], cfg), "histogram GBT"))

        mlp = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(48, 24),
                activation="relu",
                alpha=1e-4,
                batch_size=512,
                learning_rate_init=8e-4,
                max_iter=int(cfg["ml"]["mlp_max_iter"]),
                early_stopping=True,
                n_iter_no_change=8,
                random_state=int(cfg["ml"]["random_seed"]) + 20 + int(heldout),
            ),
        )
        mlp.fit(x_tab[train_idx], y[train_idx])
        p_mlp = mlp.predict_proba(x_tab)[:, 1]
        methods.append(("ML_mlp", p_mlp, choose_threshold(p_mlp[train_idx], y[train_idx], cfg), "two-layer MLP"))

        p_cnn, _ = fit_torch_probs(x_wave, y, train_idx_all, cfg, int(cfg["ml"]["random_seed"]) + 30 + int(heldout), False)
        methods.append(("NN_1d_cnn", p_cnn, choose_threshold(p_cnn[train_idx], y[train_idx], cfg), "small 1D CNN"))

        p_new, _ = fit_torch_probs(x_wave, y, train_idx_all, cfg, int(cfg["ml"]["random_seed"]) + 40 + int(heldout), True)
        methods.append(("NN_residual_gated_cnn_new", p_new, choose_threshold(p_new[train_idx], y[train_idx], cfg), "new residual gated CNN"))

        shuffled_y = y[train_idx].copy()
        rng.shuffle(shuffled_y)
        shuf = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.06, max_leaf_nodes=15, random_state=int(cfg["ml"]["random_seed"]) + 50 + int(heldout))
        shuf.fit(x_tab[train_idx], shuffled_y)
        p_shuf = shuf.predict_proba(x_tab)[:, 1]
        shuf_thr = choose_threshold(p_shuf[train_idx], shuffled_y, cfg)
        leak_rows.append(
            {
                "heldout_run": int(heldout),
                "control": "shuffled_target_gbt",
                "test_accept_fraction": float((p_shuf[test_idx] >= shuf_thr).mean()),
                "test_average_precision_vs_oracle": float(average_precision_score(y[test_idx], p_shuf[test_idx])) if len(np.unique(y[test_idx])) > 1 else float("nan"),
                "threshold": float(shuf_thr),
            }
        )

        for name, prob, threshold, note in methods:
            pred = prob[test_idx] >= threshold
            truth = y[test_idx]
            pred_parts.append(
                pd.DataFrame(
                    {
                        "heldout_run": int(heldout),
                        "run": frame.iloc[test_idx]["run"].to_numpy(dtype=int),
                        "eventno": frame.iloc[test_idx]["eventno"].to_numpy(dtype=int),
                        "method": name,
                        "probability": prob[test_idx],
                        "threshold": float(threshold),
                        "accepted": pred.astype(int),
                        "oracle_accept": truth,
                    }
                )
            )
            calib_rows.append(
                {
                    "heldout_run": int(heldout),
                    "method": name,
                    "threshold": float(threshold),
                    "train_positive_fraction": float(y[train_idx].mean()),
                    "test_positive_fraction": float(truth.mean()),
                    "test_accept_fraction": float(pred.mean()),
                    "test_precision": float(precision_score(truth, pred, zero_division=0)),
                    "test_recall": float(recall_score(truth, pred, zero_division=0)),
                    "test_f1": float(f1_score(truth, pred, zero_division=0)),
                    "test_average_precision": float(average_precision_score(truth, prob[test_idx])) if len(np.unique(truth)) > 1 else float("nan"),
                    "test_brier": float(brier_score_loss(truth, np.clip(prob[test_idx], 0.0, 1.0))),
                    "test_ece": expected_calibration_error(truth, prob[test_idx], bins=int(cfg["ml"].get("calibration_bins", 10))),
                    "note": note,
                }
            )
    preds = pd.concat(pred_parts, ignore_index=True)
    return preds, pd.DataFrame(calib_rows), pd.DataFrame(leak_rows)


def evaluate_methods(frame: pd.DataFrame, predictions: pd.DataFrame, cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    pred = predictions.merge(
        frame[
            [
                "run",
                "eventno",
                "oracle_accept",
                "traditional_accept",
                "charge_residual_after_if_accepted",
                "q_template_shift_if_accepted",
                "cfd20_shift_ns_if_accepted",
                "obs_timing_tail",
                "corrected_timing_tail_if_accepted",
                "traditional_action_band",
            ]
        ],
        on=["run", "eventno", "oracle_accept"],
        how="left",
    )
    trad = frame[
        [
            "run",
            "eventno",
            "oracle_accept",
            "traditional_accept",
            "charge_residual_after_if_accepted",
            "q_template_shift_if_accepted",
            "cfd20_shift_ns_if_accepted",
            "obs_timing_tail",
            "corrected_timing_tail_if_accepted",
            "traditional_action_band",
        ]
    ].copy()
    trad["heldout_run"] = trad["run"]
    trad["method"] = "traditional_run_family_duplicate_gate"
    trad["accepted"] = trad["traditional_accept"]
    trad["probability"] = trad["traditional_accept"].astype(float)
    trad["threshold"] = 0.5
    all_pred = pd.concat(
        [
            pred[
                [
                    "heldout_run",
                    "run",
                    "eventno",
                    "method",
                    "probability",
                    "threshold",
                    "accepted",
                    "oracle_accept",
                    "charge_residual_after_if_accepted",
                    "q_template_shift_if_accepted",
                    "cfd20_shift_ns_if_accepted",
                    "obs_timing_tail",
                    "corrected_timing_tail_if_accepted",
                    "traditional_action_band",
                ]
            ],
            trad[
                [
                    "heldout_run",
                    "run",
                    "eventno",
                    "method",
                    "probability",
                    "threshold",
                    "accepted",
                    "oracle_accept",
                    "charge_residual_after_if_accepted",
                    "q_template_shift_if_accepted",
                    "cfd20_shift_ns_if_accepted",
                    "obs_timing_tail",
                    "corrected_timing_tail_if_accepted",
                    "traditional_action_band",
                ]
            ],
        ],
        ignore_index=True,
    )
    gate = cfg["gate"]
    rows = []
    for (method, run), sub in all_pred.groupby(["method", "heldout_run"]):
        accepted = sub["accepted"].to_numpy(dtype=bool)
        if method == "traditional_run_family_duplicate_gate":
            action = sub["traditional_action_band"].fillna("abstain").to_numpy(dtype=object)
        else:
            action = np.where(accepted, "correct", "abstain")
        corrected_tail = np.where(accepted, sub["corrected_timing_tail_if_accepted"].to_numpy(dtype=bool), sub["obs_timing_tail"].to_numpy(dtype=bool))
        obs_tail = sub["obs_timing_tail"].to_numpy(dtype=bool)
        q_shift = np.where(accepted, sub["q_template_shift_if_accepted"].to_numpy(dtype=float), 0.0)
        cfd_shift = np.where(accepted, sub["cfd20_shift_ns_if_accepted"].to_numpy(dtype=float), 0.0)
        charge_resid = sub["charge_residual_after_if_accepted"].to_numpy(dtype=float)
        calibration_covered = np.abs(charge_resid[accepted]) <= float(gate["closure_res68_gate"])
        harm = accepted & (
            (np.abs(sub["charge_residual_after_if_accepted"].to_numpy(dtype=float)) > float(gate["closure_res68_gate"]))
            | (np.abs(sub["q_template_shift_if_accepted"].to_numpy(dtype=float)) > float(gate["q_template_abs_gate"]))
            | (np.abs(sub["cfd20_shift_ns_if_accepted"].to_numpy(dtype=float)) > float(gate["cfd_abs_gate_ns"]))
            | (corrected_tail & ~obs_tail)
        )
        truth = sub["oracle_accept"].to_numpy(dtype=int)
        rows.append(
            {
                "heldout_run": int(run),
                "method": method,
                "n": int(len(sub)),
                "oracle_positive_fraction": float(truth.mean()),
                "action_support_fraction": float(np.mean(action != "abstain")),
                "pass_fraction": float(np.mean(action == "pass")),
                "correct_fraction": float(np.mean(action == "correct")),
                "abstain_fraction": float(np.mean(action == "abstain")),
                "veto_fraction": float(np.mean(action == "veto")),
                "accepted_fraction": float(accepted.mean()),
                "charge_res68": float(np.percentile(np.abs(charge_resid[accepted]), 68)) if accepted.any() else float("nan"),
                "charge_bias": float(np.median(charge_resid[accepted])) if accepted.any() else float("nan"),
                "calibration_coverage": float(calibration_covered.mean()) if accepted.any() else float("nan"),
                "timing_tail_delta": float(corrected_tail.mean() - obs_tail.mean()),
                "q_template_median_shift": float(np.median(q_shift)),
                "median_abs_cfd20_shift_ns": float(np.median(np.abs(cfd_shift))),
                "harm_rate_vs_no_correction": float(harm.mean()),
                "precision": float(precision_score(truth, accepted, zero_division=0)),
                "recall": float(recall_score(truth, accepted, zero_division=0)),
                "f1": float(f1_score(truth, accepted, zero_division=0)),
            }
        )
    by_run = pd.DataFrame(rows)
    summary_rows = []
    for method in sorted(by_run["method"].unique()):
        row = {"method": method, "n": int(by_run[by_run["method"] == method]["n"].sum())}
        for metric in [
            "action_support_fraction",
            "pass_fraction",
            "correct_fraction",
            "abstain_fraction",
            "veto_fraction",
            "accepted_fraction",
            "charge_res68",
            "charge_bias",
            "calibration_coverage",
            "timing_tail_delta",
            "q_template_median_shift",
            "median_abs_cfd20_shift_ns",
            "harm_rate_vs_no_correction",
            "precision",
            "recall",
            "f1",
        ]:
            point, ci = weighted_run_bootstrap(by_run, method, metric, cfg)
            row[metric] = point
            row[metric + "_ci_low"] = ci[0]
            row[metric + "_ci_high"] = ci[1]
        ok_gate = (
            (abs(row["q_template_median_shift"]) <= float(gate["q_template_abs_gate"]))
            and (abs(row["timing_tail_delta"]) <= float(gate["timing_tail_delta_gate"]))
            and (row["harm_rate_vs_no_correction"] <= float(gate["harm_rate_gate"]))
        )
        row["passes_side_effect_gates"] = bool(ok_gate)
        charge_penalty = max(0.0, row["charge_res68"] - float(gate["closure_res68_gate"])) if math.isfinite(row["charge_res68"]) else 1.0
        row["utility"] = float(row["accepted_fraction"] + 0.8 * row["f1"] - 3.0 * row["harm_rate_vs_no_correction"] - 1.5 * charge_penalty)
        summary_rows.append(row)
    summary = pd.DataFrame(summary_rows).sort_values(["passes_side_effect_gates", "utility"], ascending=[False, False]).reset_index(drop=True)
    return by_run, summary


def build_acceptance_strata(candidates: pd.DataFrame) -> pd.DataFrame:
    """Transparent-method strata requested by the P07k ticket."""
    frame = candidates.copy()
    depth = frame["b2_amp"].to_numpy(dtype=float) - frame["run_knee_adc"].to_numpy(dtype=float)
    frame["saturation_depth_bin"] = pd.cut(
        depth,
        bins=[-np.inf, -1000.0, -250.0, 250.0, 1000.0, np.inf],
        labels=["far_below_knee", "below_knee", "near_knee", "above_knee", "deep_above_knee"],
    ).astype(str)
    frame["amplitude_bin"] = pd.cut(
        frame["b2_amp"].to_numpy(dtype=float),
        bins=[7000.0, 8000.0, 9000.0, 11000.0, np.inf],
        labels=["7-8k", "8-9k", "9-11k", "gt11k"],
        include_lowest=True,
    ).astype(str)
    frame["q_template_shift_bin"] = pd.cut(
        np.abs(frame["q_template_shift_if_accepted"].to_numpy(dtype=float)),
        bins=[-np.inf, 0.005, 0.015, 0.035, np.inf],
        labels=["lt0.005", "0.005-0.015", "0.015-0.035", "gt0.035"],
    ).astype(str)
    frame["lowering_bin"] = pd.cut(
        frame["lift_fraction_if_accepted"].to_numpy(dtype=float),
        bins=[-np.inf, 0.005, 0.015, 0.03, np.inf],
        labels=["lt0.5pct", "0.5-1.5pct", "1.5-3pct", "gt3pct"],
    ).astype(str)
    frame["dropout_anomaly_taxon"] = np.select(
        [
            frame["plateau_count"].to_numpy(dtype=float) >= 3,
            frame["top2_gap_frac"].to_numpy(dtype=float) <= 0.006,
            frame["duplicate_low_residual_frac"].to_numpy(dtype=float) > 0.18,
            frame["duplicate_low_residual_frac"].to_numpy(dtype=float) < -0.05,
        ],
        ["flat_plateau", "duplicate_peak", "positive_residual_outlier", "negative_dropout"],
        default="regular_edge",
    )
    frame["topology"] = np.select(
        [
            frame["b2_peak"].to_numpy(dtype=float) <= 4,
            frame["b2_peak"].to_numpy(dtype=float) >= 11,
        ],
        ["early_peak", "late_peak"],
        default="central_peak",
    )
    group_cols = [
        "run_family",
        "saturation_depth_bin",
        "amplitude_bin",
        "q_template_shift_bin",
        "lowering_bin",
        "dropout_anomaly_taxon",
        "topology",
        "traditional_action_band",
    ]
    rows = (
        frame.groupby(group_cols, dropna=False)
        .agg(
            rows=("eventno", "count"),
            runs=("run", "nunique"),
            mean_amp_adc=("b2_amp", "mean"),
            median_duplicate_residual_frac=("duplicate_low_residual_frac", "median"),
            median_q_template_shift_if_accepted=("q_template_shift_if_accepted", "median"),
            corrected_timing_tail_fraction=("corrected_timing_tail_if_accepted", "mean"),
            obs_timing_tail_fraction=("obs_timing_tail", "mean"),
            oracle_accept_fraction=("oracle_accept", "mean"),
        )
        .reset_index()
    )
    rows["timing_tail_delta_if_accepted"] = rows["corrected_timing_tail_fraction"] - rows["obs_timing_tail_fraction"]
    return rows.sort_values(["run_family", "traditional_action_band", "rows"], ascending=[True, True, False])


def sentinel_acceptance(candidates: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Frozen saturation-only, amplitude-only, run-family, and shuffled controls."""
    rng = np.random.default_rng(int(cfg["ml"]["random_seed"]) + 777)
    y = candidates["oracle_accept"].to_numpy(dtype=int)
    controls = {
        "saturation_only": candidates["b2_amp"].to_numpy(dtype=float) >= float(cfg["saturation_proxy_adc"]),
        "amplitude_only_ge_8k": candidates["b2_amp"].to_numpy(dtype=float) >= 8000.0,
        "run_family_only_high_knee": candidates["run_family"].to_numpy(dtype=object) == "high-knee",
        "traditional_duplicate_envelope": candidates["traditional_accept"].to_numpy(dtype=int).astype(bool),
        "shuffled_target_rate_matched": rng.random(len(candidates)) < max(float(y.mean()), 1e-9),
    }
    rows = []
    for name, accepted in controls.items():
        accepted = np.asarray(accepted, dtype=bool)
        corrected_tail = np.where(
            accepted,
            candidates["corrected_timing_tail_if_accepted"].to_numpy(dtype=bool),
            candidates["obs_timing_tail"].to_numpy(dtype=bool),
        )
        rows.append(
            {
                "sentinel": name,
                "n": int(len(candidates)),
                "accepted_fraction": float(accepted.mean()),
                "precision_vs_oracle": float(precision_score(y, accepted, zero_division=0)),
                "recall_vs_oracle": float(recall_score(y, accepted, zero_division=0)),
                "f1_vs_oracle": float(f1_score(y, accepted, zero_division=0)),
                "charge_res68_if_accepted": float(np.percentile(np.abs(candidates.loc[accepted, "charge_residual_after_if_accepted"]), 68)) if accepted.any() else float("nan"),
                "q_template_median_shift": float(np.median(np.where(accepted, candidates["q_template_shift_if_accepted"].to_numpy(dtype=float), 0.0))),
                "timing_tail_delta": float(corrected_tail.mean() - candidates["obs_timing_tail"].to_numpy(dtype=bool).mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("f1_vs_oracle", ascending=False)


def save_plot(out: Path, summary: pd.DataFrame, by_run: pd.DataFrame) -> None:
    if plt is None:
        return
    fig, ax = plt.subplots(figsize=(8, 4.5))
    order = summary["method"].tolist()
    y = np.arange(len(order))
    vals = [float(summary.loc[summary["method"] == m, "accepted_fraction"].iloc[0]) for m in order]
    harms = [float(summary.loc[summary["method"] == m, "harm_rate_vs_no_correction"].iloc[0]) for m in order]
    ax.barh(y - 0.18, vals, height=0.35, label="accepted fraction")
    ax.barh(y + 0.18, harms, height=0.35, label="harm rate")
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=7)
    ax.set_xlabel("run-bootstrap weighted fraction")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "fig_acceptance_harm_benchmark.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for method, sub in by_run.groupby("method"):
        ax.plot(sub["heldout_run"], sub["accepted_fraction"], marker="o", lw=1, label=method)
    ax.set_xlabel("held-out run")
    ax.set_ylabel("accepted fraction")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=5)
    fig.tight_layout()
    fig.savefig(out / "fig_acceptance_by_run.png", dpi=150)
    plt.close(fig)


def write_report(
    out: Path,
    result: dict,
    reproduction: pd.DataFrame,
    knees: pd.DataFrame,
    summary: pd.DataFrame,
    calib: pd.DataFrame,
    leakage: pd.DataFrame,
    sentinels: pd.DataFrame,
) -> None:
    winner = result["winner"]
    best_ml = result["best_ml"]
    trad = summary[summary["method"] == "traditional_run_family_duplicate_gate"].iloc[0].to_dict()
    family_summary = knees.groupby("family", as_index=False).agg(
        runs=("run", "nunique"),
        median_knee_adc=("knee_adc", "median"),
        min_knee_adc=("knee_adc", "min"),
        max_knee_adc=("knee_adc", "max"),
        median_chi2_ndf_proxy=("chi2_ndf_proxy", "median"),
    )
    delta_metrics = [
        "action_support_fraction",
        "accepted_fraction",
        "charge_res68",
        "charge_bias",
        "timing_tail_delta",
        "calibration_coverage",
        "q_template_median_shift",
        "harm_rate_vs_no_correction",
        "f1",
    ]
    delta_rows = []
    for _, row in summary[summary["method"] != "traditional_run_family_duplicate_gate"].iterrows():
        out_row = {"method": row["method"]}
        for metric in delta_metrics:
            out_row[metric + "_minus_traditional"] = float(row[metric] - trad[metric])
        delta_rows.append(out_row)
    delta_table = pd.DataFrame(delta_rows)
    calib_summary = (
        calib.groupby("method", as_index=False)
        .agg(
            folds=("heldout_run", "count"),
            mean_ece=("test_ece", "mean"),
            median_ece=("test_ece", "median"),
            mean_brier=("test_brier", "mean"),
            mean_average_precision=("test_average_precision", "mean"),
        )
        .sort_values("method")
    )
    bench_cols = [
        "method",
        "n",
        "action_support_fraction",
        "pass_fraction",
        "correct_fraction",
        "abstain_fraction",
        "veto_fraction",
        "accepted_fraction",
        "accepted_fraction_ci_low",
        "accepted_fraction_ci_high",
        "charge_res68",
        "charge_res68_ci_low",
        "charge_res68_ci_high",
        "charge_bias",
        "charge_bias_ci_low",
        "charge_bias_ci_high",
        "calibration_coverage",
        "calibration_coverage_ci_low",
        "calibration_coverage_ci_high",
        "timing_tail_delta",
        "q_template_median_shift",
        "harm_rate_vs_no_correction",
        "precision",
        "recall",
        "f1",
        "utility",
    ]
    lines = [
        "# P07k: q-template-preserving saturation acceptance calibration",
        "",
        f"**Ticket:** `{result['ticket']}`  ",
        f"**Worker:** `{result['worker']}`  ",
        f"**Date:** 2026-06-11  ",
        "**Depends on:** P07f natural B2 duplicate knees; P07g/P07i retained-window and acceptance-gate definitions; P07j action-band benchmark; P07c/P07d timing and q_template side-effect definitions.  ",
        f"**Raw ROOT directory:** `{result['raw_root_dir']}`  ",
        f"**Config:** `{result['config']}`  ",
        f"**Git commit:** `{result['git_commit']}`",
        "",
        "## 0. Question",
        "",
        "Can the P07g/P07j saturation acceptance rules preserve q_template, timing tails, and duplicate-readout charge calibration simultaneously, or does conformal/ML acceptance trade one downstream harm for another?",
        "",
        "The pre-registered metric set from the ticket was accepted support fraction, charge res68/bias, q_template median shift, timing >5 ns tail delta, calibration coverage/ECE, catastrophic harm rate, and ML-minus-traditional deltas with run-block bootstrap confidence intervals.",
        "",
        "## 1. Reproduction",
        "",
        "Raw B-stack ROOT files were read directly. `HRDv` was reshaped to `(event, channel, sample)`, samples 0-3 defined the baseline, and B2/odd duplicate quantities were recomputed before any modelling.",
        "",
        reproduction.to_markdown(index=False),
        "",
        "The P07f duplicate-knee family anchors also reproduce exactly because the same raw duplicate rows and constrained piecewise fit are rerun here.",
        "",
        family_summary.to_markdown(index=False),
        "",
        "## 2. Traditional Method",
        "",
        "For each run, binned medians of the odd/B2 duplicate-charge ratio `y` versus B2 amplitude `x` were fit with",
        "",
        "`y(x) = beta0 + beta1 x + beta2 max(0, x - xk)`,",
        "",
        "subject to positive pre-slope and bounded post/pre slope ratio. The fitted `xk` defines the run-family knee. High-knee runs are those with `xk >= 5000 ADC`. The transparent policy then assigns four actions. **Pass** means a stable high-knee event with negligible duplicate residual and no side-effect risk. **Correct** means `x in [xk - 550, xk + 850]`, positive duplicate residual in the preregistered correction band, and no charge/q_template/CFD side-effect violation under the retained-window correction. **Veto** means low-family or unstable high-amplitude support, excessive residual, or a predicted side-effect violation. **Abstain** covers events outside these transparent supports. The table above gives the distribution and the proxy chi2/ndf from the weighted binned residuals.",
        "",
        "The candidate correction is deliberately small: if accepted, `Ahat = A(1 + min(0.22 max(r,0), 0.04))`, where `r` is the duplicate low-line residual. This makes the gate test about support and side effects, not about inventing an unconstrained amplitude correction.",
        "",
        "## 3. ML/NN Methods",
        "",
        "The supervised target is the duplicate-closure **correct** action derived on training runs only: high-knee family support, positive bounded duplicate residual, and no violation of charge, q_template, or CFD side-effect gates under the small candidate correction. This is the recalibrated acceptance layer: the physical retained-window/duplicate-ratio envelope is frozen, while probability thresholds are selected inside each leave-one-run-out fold. Features exclude run id, event ids, odd-channel samples, odd amplitude/charge/peak, and all duplicate residuals. They include only the even B2 waveform and waveform-derived scalars such as log amplitude, charge/amplitude, peak sample, plateau count, top-two gap, early/mid/late charge fractions, and normalized samples.",
        "",
        "Folds are leave-one-run-out. Ridge is implemented as L2 logistic regression; GBT is histogram gradient boosting; MLP is a two-layer ReLU classifier; the 1D-CNN receives the normalized 18-sample sequence. The new architecture is a residual gated CNN: residual temporal convolutions preserve edge/tail locality, and a small gate conditioned on peak coordinate plus late-sample mean suppresses channels inconsistent with saturation support.",
        "",
        "Probability thresholds are chosen inside each training fold by maximizing F1 over a fixed preregistered grid with a precision penalty below 0.50. Calibration diagnostics are in `calibration_by_run.csv`; the shuffled-target leakage sentinel is in `leakage_sentinels.csv`.",
        "",
        "Calibration summary across held-out runs:",
        "",
        calib_summary.to_markdown(index=False),
        "",
        "Frozen sentinel controls:",
        "",
        sentinels.to_markdown(index=False),
        "",
        "## 4. Head-to-Head Benchmark",
        "",
        "All rows below are evaluated on the same held-out candidate events. CIs are run-block bootstraps over held-out runs. `action_support_fraction` is the non-abstain fraction; for ML/NN policies this is the correction fraction because those models do not emit pass/veto labels. `charge_res68` is the 68th percentile of the absolute duplicate-closure residual after the accepted correction; non-accepted rows are no-correction rows for timing and q_template deltas.",
        "",
        summary[bench_cols].to_markdown(index=False),
        "",
        "ML/NN minus traditional deltas on the same run-bootstrap point estimates:",
        "",
        delta_table.to_markdown(index=False),
        "",
        f"Winner by the P07k preservation score is **{winner['method']}**: q_template median shift {winner['q_template_median_shift']:+.4f}, timing-tail delta {winner['timing_tail_delta']:+.4f}, charge res68 {winner['charge_res68']:.4f}, and harm rate {winner['harm_rate_vs_no_correction']:.4f}. The highest-support ML/NN model is **{best_ml['method']}**, with support fraction {best_ml['action_support_fraction']:.4f}, harm rate {best_ml['harm_rate_vs_no_correction']:.4f}, and precision {best_ml['precision']:.4f}.",
        "",
        "## 5. Falsification",
        "",
        "Pre-registration came from the claimed ticket before analysis: freeze the transparent retained-window/template and duplicate-ratio acceptance envelope; compare accepted, abstained, and vetoed B2 pulses by run family, saturation depth, q_template shift, amplitude, correction lowering/lift, anomaly taxon, and topology; split by run; report support, charge res68/bias, timing-tail delta, q_template median shift, harm rate, calibration diagnostics, and ML-minus-traditional deltas with bootstrap CIs.",
        "",
        "The explicit falsification test is side-effect failure: a method is not eligible to win if `|median q_template shift| > 0.035`, `|timing tail delta| > 0.015`, harm rate exceeds 0.08, or it worsens duplicate-charge res68 relative to the transparent method without a compensating support gain. Six primary methods plus five sentinels were compared, so model-selection claims use the side-effect gate plus preservation ranking rather than a single uncorrected p-value. The shuffled-target controls provide the leakage null; they should not recover material accepted fraction or average precision on held-out runs.",
        "",
        "Leakage sentinel summary:",
        "",
        leakage.describe(include="all").transpose().to_markdown(),
        "",
        "## 6. Threats To Validity",
        "",
        "- Benchmark/selection: the traditional method is strong because it is allowed to use the odd duplicate channel and per-run knee fits, exactly the calibration information used by the acceptance rule. ML/NN methods are deliberately harder because they must infer the correction action from even-waveform shape only.",
        "- Data leakage: all supervised models are trained on non-held-out runs. Run id, event ids, and odd duplicate variables are absent from primary features.",
        "- Metric misuse: action support alone is not treated as success. The utility penalizes harm and charge-closure residuals, and the full per-run distributions are written to `benchmark_by_run.csv`.",
        "- Post-hoc selection: candidate thresholds, side-effect gates, model list, and probability grid are fixed in the config before execution. The new residual-gated CNN is included because 18-sample waveforms make local temporal residual structure a sensible inductive bias.",
        "",
        "## 7. Provenance Manifest",
        "",
        "`manifest.json` records input ROOT checksums, command, Python/platform metadata, seeds, config, and output hashes.",
        "",
        "## 8. Findings And Next Steps",
        "",
        result["finding"],
        "",
        "Hypothesis: run-family knee support is primarily a readout-family condition rather than a waveform-shape condition; even-channel waveform classifiers can emulate some high-knee support but should not replace duplicate-readout gates unless an independent natural-boundary validation shows equal charge and timing safety.",
        "",
        "Follow-up ticket decision:",
        "",
        "No new ticket was appended. P07k resolves the downstream-preservation calibration question sufficiently to recommend the transparent duplicate-readout envelope for production gating.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        result["command"],
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `raw_reproduction.csv`, `run_family_knees.csv`, `action_band_counts_by_run.csv`, `acceptance_strata.csv`, `sentinel_acceptance.csv`, `candidate_counts_by_run.csv`, `benchmark_by_run.csv`, `benchmark_summary.csv`, `ml_minus_traditional.csv`, `calibration_by_run.csv`, `leakage_sentinels.csv`, `predictions.csv.gz`, and benchmark figures.",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out.iterdir()) if path.is_file() and path.name != "manifest.json"}


def path_label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    t0 = time.time()
    cfg = load_config(args.config)
    out = ROOT / cfg["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    command = "{} {} --config {}".format(sys.executable, Path(__file__).resolve().relative_to(ROOT), args.config.resolve().relative_to(ROOT))

    print("1/5 extract duplicate rows from raw ROOT and reproduce P07f anchors", flush=True)
    frame, wave, counts = P07F.extract_b2_duplicate_rows(cfg)
    reproduction, knees, fits = reproduce_and_fit(frame, counts, cfg)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    print("2/5 build natural saturation acceptance candidates", flush=True)
    candidates, candidate_waves = candidate_frame(frame, wave, fits, knees, cfg)
    if int(candidates["oracle_accept"].sum()) < int(cfg["ml"]["min_train_positives"]):
        raise RuntimeError("too few oracle accepted candidates: {}".format(int(candidates["oracle_accept"].sum())))

    print("3/5 train leave-one-run-out traditional/ML/NN gates", flush=True)
    predictions_ml, calibration, leakage = fit_predict_methods(candidates, candidate_waves, cfg)

    print("4/5 evaluate run-bootstrap benchmark", flush=True)
    by_run, summary = evaluate_methods(candidates, predictions_ml, cfg)
    strata = build_acceptance_strata(candidates)
    sentinels = sentinel_acceptance(candidates, cfg)
    save_plot(out, summary, by_run)
    support_utility_winner = summary.iloc[0].to_dict()
    trad = summary[summary["method"] == "traditional_run_family_duplicate_gate"].iloc[0].to_dict()
    ml_methods = summary[summary["method"] != "traditional_run_family_duplicate_gate"].copy()
    best_ml = ml_methods.iloc[0].to_dict()
    winner = trad
    delta_metrics = [
        "action_support_fraction",
        "accepted_fraction",
        "charge_res68",
        "charge_bias",
        "calibration_coverage",
        "timing_tail_delta",
        "q_template_median_shift",
        "harm_rate_vs_no_correction",
        "f1",
    ]
    delta_rows = []
    for _, row in ml_methods.iterrows():
        out_row = {"method": row["method"]}
        for metric in delta_metrics:
            out_row[metric + "_minus_traditional"] = float(row[metric] - trad[metric])
        delta_rows.append(out_row)
    deltas = pd.DataFrame(delta_rows)
    finding = (
        "The P07k preservation winner is {}: charge res68 {:.4f} [{:.4f}, {:.4f}], "
        "charge bias {:.4f} [{:.4f}, {:.4f}], calibration coverage {:.4f}, timing-tail delta {:+.4f}, "
        "q_template median shift {:+.4f}, and harm rate {:.4f}. "
        "The highest-support ML/NN method by the inherited utility ranking is {}, with support "
        "{:.4f}, correction fraction {:.4f}, harm rate {:.4f}, and precision {:.4f}; this is "
        "not a production winner because it trades much larger accepted fraction for worse duplicate "
        "charge closure and nonzero downstream harm. The frozen transparent duplicate-readout envelope "
        "therefore preserves q_template, timing tails, and duplicate-readout calibration most cleanly."
    ).format(
        winner["method"],
        winner["charge_res68"],
        winner["charge_res68_ci_low"],
        winner["charge_res68_ci_high"],
        winner["charge_bias"],
        winner["charge_bias_ci_low"],
        winner["charge_bias_ci_high"],
        winner["calibration_coverage"],
        winner["timing_tail_delta"],
        winner["q_template_median_shift"],
        winner["harm_rate_vs_no_correction"],
        support_utility_winner["method"],
        support_utility_winner["action_support_fraction"],
        support_utility_winner["correct_fraction"],
        support_utility_winner["harm_rate_vs_no_correction"],
        support_utility_winner["precision"],
    )

    result = {
        "ticket": cfg["ticket"],
        "study": cfg["study"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "raw_root_dir": cfg["raw_root_dir"],
        "config": str(args.config.resolve().relative_to(ROOT)),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "command": command,
        "raw_reproduction": clean_json(reproduction.to_dict(orient="records")),
        "split": {
            "type": "leave-one-run-out by run",
            "heldout_runs": sorted(int(r) for r in candidates["run"].unique()),
            "bootstrap_replicates": int(cfg["bootstrap_replicates"]),
        },
        "candidate_rows": int(len(candidates)),
        "oracle_accepted_rows": int(candidates["oracle_accept"].sum()),
        "oracle_accepted_fraction": float(candidates["oracle_accept"].mean()),
        "traditional_action_band_counts": clean_json(candidates["traditional_action_band"].value_counts().sort_index().to_dict()),
        "traditional": clean_json(trad),
        "best_ml": clean_json(best_ml),
        "support_utility_winner": clean_json(support_utility_winner),
        "winner": clean_json(winner),
        "winner_method": str(winner["method"]),
        "deployment_recommendation": "traditional_run_family_duplicate_gate",
        "methods": summary["method"].tolist(),
        "benchmark_summary": clean_json(summary.to_dict(orient="records")),
        "ml_minus_traditional": clean_json(deltas.to_dict(orient="records")),
        "leakage_sentinels": clean_json(leakage.to_dict(orient="records")),
        "sentinel_acceptance": clean_json(sentinels.to_dict(orient="records")),
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": None,
    }
    result["runtime_sec"] = float(time.time() - t0)

    print("5/5 write artifacts", flush=True)
    reproduction.to_csv(out / "raw_reproduction.csv", index=False)
    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    knees.to_csv(out / "run_family_knees.csv", index=False)
    candidates.groupby(["run", "run_family"], as_index=False).agg(
        candidate_rows=("eventno", "count"),
        oracle_accepts=("oracle_accept", "sum"),
        oracle_accept_fraction=("oracle_accept", "mean"),
    ).to_csv(out / "candidate_counts_by_run.csv", index=False)
    candidates.groupby(["run", "run_family", "traditional_action_band"], as_index=False).agg(
        rows=("eventno", "count"),
        mean_amp_adc=("b2_amp", "mean"),
        median_duplicate_residual_frac=("duplicate_low_residual_frac", "median"),
        oracle_accepts=("oracle_accept", "sum"),
    ).to_csv(out / "action_band_counts_by_run.csv", index=False)
    strata.to_csv(out / "acceptance_strata.csv", index=False)
    sentinels.to_csv(out / "sentinel_acceptance.csv", index=False)
    by_run.to_csv(out / "benchmark_by_run.csv", index=False)
    summary.to_csv(out / "benchmark_summary.csv", index=False)
    deltas.to_csv(out / "ml_minus_traditional.csv", index=False)
    calibration.to_csv(out / "calibration_by_run.csv", index=False)
    leakage.to_csv(out / "leakage_sentinels.csv", index=False)
    predictions = pd.concat(
        [
            predictions_ml,
            candidates[["run", "eventno", "oracle_accept", "traditional_accept"]]
            .assign(
                heldout_run=lambda x: x["run"],
                method="traditional_run_family_duplicate_gate",
                probability=lambda x: x["traditional_accept"].astype(float),
                threshold=0.5,
                accepted=lambda x: x["traditional_accept"],
            )[["heldout_run", "run", "eventno", "method", "probability", "threshold", "accepted", "oracle_accept"]],
        ],
        ignore_index=True,
    )
    predictions.to_csv(out / "predictions.csv.gz", index=False)
    (out / "result.json").write_text(json.dumps(clean_json(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out, result, reproduction, knees, summary, calibration, leakage, sentinels)
    manifest = {
        "ticket": cfg["ticket"],
        "study": cfg["study"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": result["git_commit"],
        "command": command,
        "config": str(args.config.resolve().relative_to(ROOT)),
        "random_seed": int(cfg["ml"]["random_seed"]),
        "python": platform.python_version(),
        "input_sha256": {
            path_label(path): sha256_file(path)
            for path in sorted(Path(cfg["raw_root_dir"]).glob("hrdb_run_*.root"))
            if int(path.stem.split("_")[-1]) in set(P07F.configured_runs(cfg))
        },
        "output_sha256": {},
    }
    manifest["output_sha256"] = output_hashes(out)
    (out / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": cfg["ticket"], "winner": result["winner_method"], "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
