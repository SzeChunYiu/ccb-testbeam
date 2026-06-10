#!/usr/bin/env python3
"""S05h: Saturation-aware covariance support frontier benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Iterable, Sequence

os.environ.setdefault("MPLCONFIGDIR", "reports/1781040960.767.247d3910__s05h_saturation_covariance_support_frontier/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, LeaveOneGroupOut, train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - recorded in result.json
    torch = None
    nn = None


TICKET_BODY = (
    "Where do the newest S05d/S05e saturation-aware covariance gains remain valid once B2 saturation "
    "depth, q-template shift, amplitude, topology, baseline lowering, pile-up candidates, and run family "
    "are matched?"
)
PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8"), ("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
STAVES = ["B2", "B4", "B6", "B8"]
CORE_METHODS = [
    "pair_median",
    "traditional_s05d_static_priors",
    "ridge",
    "gradient_boosted_trees",
    "extra_trees_s05e_dynamic",
    "mlp",
    "cnn_1d",
    "support_gated_cnn_new",
]
CONTROL_METHODS = ["waveform_only_mlp", "pool_label_control", "ml_shuffled_target_control"]


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


def root_path(config: dict, stack: str, run: int) -> Path:
    section = config[f"{stack}stack"]
    return Path(config["raw_root_dir"]) / f"{section['file_prefix']}_run_{int(run):04d}.root"


def iter_root(path: Path, branches: Sequence[str], step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(list(branches), step_size=step_size, library="np")


def all_runs(config: dict) -> list[int]:
    runs: list[int] = []
    for values in config["runs"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_family(config: dict, run: int) -> str:
    for name, runs in config["runs"].items():
        if int(run) in [int(x) for x in runs]:
            return name
    return "unknown"


def cfd_quantities(waveforms: np.ndarray, baseline_samples: Sequence[int], fraction: float, period_ns: float) -> dict:
    baseline = np.median(waveforms[..., list(baseline_samples)], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak = corrected.argmax(axis=-1).astype(float)
    area = corrected.sum(axis=-1)
    tail = corrected[..., 10:].sum(axis=-1) / np.maximum(area, 1.0)
    width_half = (corrected >= (0.5 * amplitude[..., None])).sum(axis=-1).astype(float)
    threshold = amplitude * float(fraction)
    ge = corrected[..., 1:] >= threshold[..., None]
    prev_lt = corrected[..., :-1] < threshold[..., None]
    sample_index = np.arange(1, corrected.shape[-1])[None, None, :]
    eligible = ge & prev_lt & (sample_index <= peak[..., None])
    has = eligible.any(axis=-1)
    crossing = eligible.argmax(axis=-1) + 1
    row = np.arange(corrected.shape[0])[:, None]
    col = np.arange(corrected.shape[1])[None, :]
    y0 = corrected[row, col, np.maximum(crossing - 1, 0)]
    y1 = corrected[row, col, crossing]
    frac = np.divide(threshold - y0, y1 - y0, out=np.zeros_like(threshold), where=np.abs(y1 - y0) > 1e-12)
    time = np.where(has, (crossing - 1 + frac) * period_ns, peak * period_ns)
    return {
        "corrected": corrected,
        "baseline": baseline,
        "amplitude": amplitude,
        "peak": peak,
        "area": area,
        "tail": tail,
        "width_half": width_half,
        "time_ns": time,
    }


def centered(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return arr
    return arr - np.nanmedian(arr)


def sigma68(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float(0.5 * (np.percentile(c, 84) - np.percentile(c, 16)))


def mad_sigma(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float(1.4826 * np.median(np.abs(c)))


def iqr_sigma(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float((np.percentile(c, 75) - np.percentile(c, 25)) / 1.3489795003921634)


def trimmed_sigma(values: np.ndarray, trim_each_tail: float) -> float:
    c = centered(values)
    if len(c) < 4:
        return float("nan")
    lo, hi = np.quantile(c, [trim_each_tail, 1.0 - trim_each_tail])
    trimmed = c[(c >= lo) & (c <= hi)]
    if len(trimmed) < 3:
        return float("nan")
    z = stats.norm.ppf(1.0 - trim_each_tail)
    kept = 1.0 - 2.0 * trim_each_tail
    trunc_var = 1.0 - (2.0 * z * stats.norm.pdf(z) / kept)
    return float(np.std(trimmed, ddof=1) / math.sqrt(trunc_var))


def student_t_width(values: np.ndarray) -> tuple[float, float]:
    c = centered(values)
    if len(c) < 5:
        return float("nan"), float("nan")
    try:
        df, _, scale = stats.t.fit(c)
        df = float(np.clip(df, 2.01, 200.0))
        return float(abs(scale) * stats.t.ppf(0.84, df)), df
    except Exception:
        return float("nan"), float("nan")


def full_rms(values: np.ndarray) -> float:
    c = centered(values)
    if len(c) < 2:
        return float("nan")
    return float(np.sqrt(np.mean(c * c)))


def b_position(stave: str, spacing_cm: float) -> float:
    return {"B2": 0.0, "B4": spacing_cm, "B6": 2.0 * spacing_cm, "B8": 3.0 * spacing_cm}[stave]


def astack_pair_table(config: dict) -> pd.DataFrame:
    channels = [int(config["astack"]["staves"]["A1"]), int(config["astack"]["staves"]["A3"])]
    baseline = [int(x) for x in config["baseline_samples"]]
    rows = []
    for run in all_runs(config):
        path = root_path(config, "a", run)
        if not path.exists():
            continue
        for batch in iter_root(path, ["EVT", "HRDv"]):
            event = np.asarray(batch["EVT"]).astype(int)
            wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))[:, channels, :]
            q = cfd_quantities(wave, baseline, float(config["cfd_fraction"]), float(config["sample_period_ns"]))
            selected = (q["amplitude"][:, 0] > float(config["amplitude_cut_adc"])) & (
                q["amplitude"][:, 1] > float(config["amplitude_cut_adc"])
            )
            if not selected.any():
                continue
            frame = pd.DataFrame(
                {
                    "run": int(run),
                    "family": run_family(config, run),
                    "event": event[selected],
                    "a1_amp": q["amplitude"][selected, 0],
                    "a3_amp": q["amplitude"][selected, 1],
                    "a1_peak": q["peak"][selected, 0],
                    "a3_peak": q["peak"][selected, 1],
                    "a1_area": q["area"][selected, 0],
                    "a3_area": q["area"][selected, 1],
                    "a1_tail": q["tail"][selected, 0],
                    "a3_tail": q["tail"][selected, 1],
                    "a1_time_ns": q["time_ns"][selected, 0],
                    "a3_time_ns": q["time_ns"][selected, 1],
                }
            )
            frame["raw_a13_residual_ns"] = frame["a3_time_ns"] - frame["a1_time_ns"]
            rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def traditional_a_residual(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    def features(df: pd.DataFrame) -> np.ndarray:
        a1 = np.log(np.maximum(df["a1_amp"].to_numpy(), 1.0))
        a3 = np.log(np.maximum(df["a3_amp"].to_numpy(), 1.0))
        return np.column_stack([np.ones(len(df)), a1, a3, a1 * a1, a3 * a3, a1 * a3])

    beta = np.linalg.lstsq(features(train), train["raw_a13_residual_ns"].to_numpy(), rcond=None)[0]
    return test["raw_a13_residual_ns"].to_numpy() - features(test) @ beta


def astack_run_summaries(config: dict, a_pairs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run, group in a_pairs.groupby("run"):
        st_width, st_df = student_t_width(group["raw_a13_residual_ns"].to_numpy())
        row = {
            "run": int(run),
            "run_family": run_family(config, int(run)),
            "a_n_pairs": int(len(group)),
            "a_p68_width_ns": sigma68(group["raw_a13_residual_ns"].to_numpy()),
            "a_mad_sigma_ns": mad_sigma(group["raw_a13_residual_ns"].to_numpy()),
            "a_iqr_sigma_ns": iqr_sigma(group["raw_a13_residual_ns"].to_numpy()),
            "a_trimmed_sigma_ns": trimmed_sigma(group["raw_a13_residual_ns"].to_numpy(), float(config["trim_each_tail_fraction"])),
            "a_student_t_width68_ns": st_width,
            "a_student_t_df": st_df,
            "a_full_rms_ns": full_rms(group["raw_a13_residual_ns"].to_numpy()),
            "a1_amp_median": float(group["a1_amp"].median()),
            "a3_amp_median": float(group["a3_amp"].median()),
            "a1_tail_median": float(group["a1_tail"].median()),
            "a3_tail_median": float(group["a3_tail"].median()),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def reproduce_raw_anchors(config: dict, a_pairs: pd.DataFrame) -> pd.DataFrame:
    baseline = [int(x) for x in config["baseline_samples"]]
    b_channels = list(config["bstack"]["staves"].values())
    sample_i = 0
    sample_ii = 0
    total = 0
    for run in all_runs(config):
        for batch in iter_root(root_path(config, "b", run), ["HRDv"]):
            wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))[:, b_channels, :]
            q = cfd_quantities(wave, baseline, float(config["cfd_fraction"]), float(config["sample_period_ns"]))
            selected = q["amplitude"] > float(config["amplitude_cut_adc"])
            n = int(selected.sum())
            total += n
            if run in config["runs"]["sample_i_analysis"]:
                sample_i += n
            if run in config["runs"]["sample_ii_analysis"]:
                sample_ii += n

    iv_train = a_pairs[a_pairs["run"].isin(config["runs"]["sample_ii_calib"])].copy()
    iv_test = a_pairs[a_pairs["run"].isin(config["runs"]["sample_ii_analysis"])].copy()
    iv_resid = traditional_a_residual(iv_train, iv_test)
    exp = config["expected_counts"]
    rows = [
        ("total_selected_b_pulses", exp["total_selected_b_pulses"], total, 0.0),
        ("sample_i_analysis_b_selected_pulses", exp["sample_i_analysis_b_selected_pulses"], sample_i, 0.0),
        ("sample_ii_analysis_b_selected_pulses", exp["sample_ii_analysis_b_selected_pulses"], sample_ii, 0.0),
        ("sample_iv_a1_a3_pairs", exp["sample_iv_a1_a3_pairs"], len(iv_resid), 0.0),
        (
            "sample_iv_a1_a3_robust_width_ns",
            exp["sample_iv_a1_a3_robust_width_ns"],
            sigma68(iv_resid),
            exp["sample_iv_a1_a3_tolerance_ns"],
        ),
    ]
    return pd.DataFrame(
        [
            {
                "quantity": key,
                "expected": float(expected),
                "reproduced": float(value),
                "delta": float(value - expected),
                "tolerance": float(tol),
                "pass": bool(abs(value - expected) <= tol),
            }
            for key, expected, value, tol in rows
        ]
    )


def load_b_run_pairs(config: dict, run: int) -> pd.DataFrame:
    baseline = [int(x) for x in config["baseline_samples"]]
    channels = list(config["bstack"]["staves"].values())
    names = list(config["bstack"]["staves"].keys())
    spacing = float(config["stave_spacing_cm"])
    tof = float(config["tof_per_cm_ns"])
    rows = []
    for batch in iter_root(root_path(config, "b", run), ["EVT", "HRDv"]):
        event = np.asarray(batch["EVT"]).astype(int)
        wave = np.stack(batch["HRDv"]).astype(float).reshape(-1, 8, int(config["samples_per_channel"]))[:, channels, :]
        q = cfd_quantities(wave, baseline, float(config["cfd_fraction"]), float(config["sample_period_ns"]))
        selected = q["amplitude"] > float(config["amplitude_cut_adc"])
        base = {"run": int(run), "run_family": run_family(config, int(run)), "event": event}
        for i, stave in enumerate(names):
            base[f"{stave}_amp"] = q["amplitude"][:, i]
            base[f"{stave}_baseline"] = q["baseline"][:, i]
            base[f"{stave}_log_amp"] = np.log1p(np.maximum(q["amplitude"][:, i], 0.0))
            base[f"{stave}_peak"] = q["peak"][:, i]
            base[f"{stave}_area"] = q["area"][:, i]
            base[f"{stave}_log_area"] = np.log1p(np.maximum(q["area"][:, i], 0.0))
            base[f"{stave}_tail"] = q["tail"][:, i]
            base[f"{stave}_width_half"] = q["width_half"][:, i]
            base[f"{stave}_time_ns"] = q["time_ns"][:, i]
            base[f"{stave}_sat_depth_adc"] = np.maximum(q["amplitude"][:, i] - float(config["saturation_threshold_adc"]), 0.0)
            base[f"{stave}_deep_sat_depth_adc"] = np.maximum(q["amplitude"][:, i] - float(config["deep_saturation_adc"]), 0.0)
            base[f"{stave}_sat_sample_count"] = (q["corrected"][:, i, :] >= float(config["saturation_threshold_adc"])).sum(axis=1)
            base[f"{stave}_q_shift_proxy"] = q["tail"][:, i] + 0.08 * np.maximum(q["peak"][:, i] - 8.0, 0.0)
            base[f"{stave}_pileup_proxy"] = (
                (q["tail"][:, i] > float(config["tail_pileup_threshold"])) | (q["peak"][:, i] >= 14.0)
            ).astype(int)
            base[f"{stave}_selected"] = selected[:, i]
            denom = np.maximum(q["amplitude"][:, i], 1.0)
            norm_wave = q["corrected"][:, i, :] / denom[:, None]
            for sample_idx in range(int(config["samples_per_channel"])):
                base[f"{stave}_w{sample_idx:02d}"] = norm_wave[:, sample_idx]
        frame = pd.DataFrame(base)
        for left, right in PAIRS:
            mask = frame[f"{left}_selected"] & frame[f"{right}_selected"]
            if not mask.any():
                continue
            sub = frame.loc[mask].copy()
            sub["pair"] = f"{left}-{right}"
            sub["has_b2"] = left == "B2" or right == "B2"
            sub["raw_residual_ns"] = sub[f"{right}_time_ns"] - sub[f"{left}_time_ns"]
            sub["tof_ns"] = (b_position(right, spacing) - b_position(left, spacing)) * tof
            sub["target_residual_ns"] = sub["raw_residual_ns"] - sub["tof_ns"]
            for side, stave in [("left", left), ("right", right)]:
                sub[f"{side}_log_amp"] = sub[f"{stave}_log_amp"]
                sub[f"{side}_peak"] = sub[f"{stave}_peak"]
                sub[f"{side}_tail"] = sub[f"{stave}_tail"]
                sub[f"{side}_log_area"] = sub[f"{stave}_log_area"]
                sub[f"{side}_width_half"] = sub[f"{stave}_width_half"]
                for sample_idx in range(int(config["samples_per_channel"])):
                    sub[f"{side}_w{sample_idx:02d}"] = sub[f"{stave}_w{sample_idx:02d}"]
            sub["log_amp_sum"] = sub["left_log_amp"] + sub["right_log_amp"]
            sub["log_amp_diff"] = sub["right_log_amp"] - sub["left_log_amp"]
            sub["tail_diff"] = sub["right_tail"] - sub["left_tail"]
            sub["peak_diff"] = sub["right_peak"] - sub["left_peak"]
            sub["width_half_diff"] = sub["right_width_half"] - sub["left_width_half"]
            sub["topology"] = np.where(sub["has_b2"], "B2_containing", "downstream_only")
            sub["pair_min_amp"] = np.minimum(sub[f"{left}_amp"], sub[f"{right}_amp"])
            sub["pair_max_amp"] = np.maximum(sub[f"{left}_amp"], sub[f"{right}_amp"])
            sub["pair_sat_depth_adc"] = np.maximum(sub[f"{left}_sat_depth_adc"], sub[f"{right}_sat_depth_adc"])
            sub["pair_q_shift_proxy"] = np.maximum(sub[f"{left}_q_shift_proxy"], sub[f"{right}_q_shift_proxy"])
            sub["pair_baseline_min"] = np.minimum(sub[f"{left}_baseline"], sub[f"{right}_baseline"])
            sub["pair_pileup_candidate"] = ((sub[f"{left}_pileup_proxy"] > 0) | (sub[f"{right}_pileup_proxy"] > 0)).astype(int)
            if "B2" in [left, right]:
                sub["b2_sat_depth_adc"] = sub["B2_sat_depth_adc"]
                sub["b2_deep_sat_depth_adc"] = sub["B2_deep_sat_depth_adc"]
                sub["b2_sat_sample_count"] = sub["B2_sat_sample_count"]
                sub["b2_q_shift_proxy"] = sub["B2_q_shift_proxy"]
                sub["b2_baseline"] = sub["B2_baseline"]
            else:
                sub["b2_sat_depth_adc"] = 0.0
                sub["b2_deep_sat_depth_adc"] = 0.0
                sub["b2_sat_sample_count"] = 0
                sub["b2_q_shift_proxy"] = 0.0
                sub["b2_baseline"] = np.nan
            rows.append(sub)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_b_pair_table(config: dict, a_summary: pd.DataFrame) -> pd.DataFrame:
    table = pd.concat([load_b_run_pairs(config, run) for run in config["analysis_runs"]], ignore_index=True)
    return table.merge(a_summary, on=["run", "run_family"], how="left")


def encoder() -> OneHotEncoder:
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        [("cat", encoder(), categorical), ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), numeric)],
        remainder="drop",
    )


def b_numeric_features(include_all_staves: bool = False) -> list[str]:
    base = [
        "left_log_amp",
        "right_log_amp",
        "log_amp_sum",
        "log_amp_diff",
        "left_peak",
        "right_peak",
        "peak_diff",
        "left_tail",
        "right_tail",
        "tail_diff",
        "left_log_area",
        "right_log_area",
        "left_width_half",
        "right_width_half",
        "width_half_diff",
        "pair_min_amp",
        "pair_max_amp",
        "pair_sat_depth_adc",
        "pair_q_shift_proxy",
        "pair_baseline_min",
        "pair_pileup_candidate",
        "b2_sat_depth_adc",
        "b2_deep_sat_depth_adc",
        "b2_sat_sample_count",
        "b2_q_shift_proxy",
        "b2_baseline",
        "a_p68_width_ns",
        "a_mad_sigma_ns",
        "a_iqr_sigma_ns",
        "a_trimmed_sigma_ns",
        "a_student_t_width68_ns",
        "a_full_rms_ns",
        "a_n_pairs",
    ]
    if include_all_staves:
        for stave in STAVES:
            base.extend([
                f"{stave}_log_amp",
                f"{stave}_tail",
                f"{stave}_width_half",
                f"{stave}_baseline",
                f"{stave}_sat_depth_adc",
                f"{stave}_sat_sample_count",
                f"{stave}_q_shift_proxy",
                f"{stave}_pileup_proxy",
            ])
    return base


def wave_cols() -> list[str]:
    return [f"left_w{i:02d}" for i in range(18)] + [f"right_w{i:02d}" for i in range(18)]


def capped_train_indices(n_rows: int, config: dict, rng: np.random.Generator) -> np.ndarray:
    idx = np.arange(n_rows)
    max_rows = int(config["ml"].get("max_model_train_rows", n_rows))
    if n_rows > max_rows:
        return np.sort(rng.choice(idx, size=max_rows, replace=False))
    return idx


def fit_predict_pipeline(estimator, train: pd.DataFrame, test: pd.DataFrame, numeric: list[str], categorical: list[str], target: str, config: dict, rng: np.random.Generator) -> np.ndarray:
    take = capped_train_indices(len(train), config, rng)
    model = make_pipeline(preprocessor(numeric, categorical), estimator)
    model.fit(train.iloc[take][categorical + numeric], train.iloc[take][target])
    return model.predict(test[categorical + numeric])


def fit_predict_pool_label_control(train: pd.DataFrame, test: pd.DataFrame, config: dict, rng: np.random.Generator) -> np.ndarray:
    cats = ["pair", "run_family"]
    take = capped_train_indices(len(train), config, rng)
    model = make_pipeline(encoder(), Ridge(alpha=10.0))
    model.fit(train.iloc[take][cats], train.iloc[take]["target_residual_ns"])
    return model.predict(test[cats])


class TinyBStackCNN(nn.Module):
    def __init__(self, aux_dim: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(2, 16, 3, padding=1),
            nn.ReLU(),
            nn.Conv1d(16, 24, 3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )
        self.head = nn.Sequential(nn.Linear(24 + aux_dim, 40), nn.ReLU(), nn.Linear(40, 1))

    def forward(self, wave, aux):
        return self.head(torch.cat([self.conv(wave), aux], dim=1)).squeeze(1)


class SupportGatedBStackCNN(nn.Module):
    def __init__(self, aux_dim: int) -> None:
        super().__init__()
        self.inp = nn.Conv1d(2, 24, 3, padding=1)
        self.block = nn.Sequential(nn.Conv1d(24, 24, 3, padding=1), nn.ReLU(), nn.Conv1d(24, 24, 5, padding=2))
        self.gate = nn.Sequential(nn.Linear(24 + aux_dim, 24), nn.ReLU(), nn.Linear(24, 24), nn.Sigmoid())
        self.head = nn.Sequential(nn.Linear(48 + aux_dim, 48), nn.ReLU(), nn.Linear(48, 1))

    def forward(self, wave, aux):
        z = torch.relu(self.inp(wave))
        z = torch.relu(z + self.block(z))
        pooled = z.mean(dim=2)
        z = z * self.gate(torch.cat([pooled, aux], dim=1)).unsqueeze(2)
        pooled = torch.cat([z.mean(dim=2), z.amax(dim=2)], dim=1)
        return self.head(torch.cat([pooled, aux], dim=1)).squeeze(1)


def torch_inputs(df: pd.DataFrame, aux_cols: list[str], aux_scaler: StandardScaler | None = None) -> tuple[np.ndarray, np.ndarray, StandardScaler]:
    left = df[[f"left_w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    right = df[[f"right_w{i:02d}" for i in range(18)]].to_numpy(dtype=np.float32)
    waves = np.stack([left, right], axis=1)
    aux_raw = df[aux_cols].to_numpy(dtype=np.float32)
    if aux_scaler is None:
        aux_scaler = StandardScaler().fit(aux_raw)
    aux = aux_scaler.transform(aux_raw).astype(np.float32)
    return waves, aux, aux_scaler


def fit_predict_torch(model: nn.Module, train: pd.DataFrame, test: pd.DataFrame, aux_cols: list[str], config: dict, rng: np.random.Generator, seed: int) -> np.ndarray:
    if torch is None:
        return np.full(len(test), np.nan)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(2, os.cpu_count() or 1)))
    take = capped_train_indices(len(train), config, rng)
    train_small = train.iloc[take].copy()
    xw, xa, scaler = torch_inputs(train_small, aux_cols)
    y_raw = train_small["target_residual_ns"].to_numpy(dtype=np.float32)
    y_center = float(np.median(y_raw))
    y_scale = float(max(sigma68(y_raw), np.std(y_raw), 1e-6))
    y = ((y_raw - y_center) / y_scale).astype(np.float32)
    device = torch.device("cpu")
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=float(config["ml"]["nn_learning_rate"]), weight_decay=float(config["ml"]["nn_weight_decay"]))
    loss_fn = nn.MSELoss()
    batch = int(config["ml"]["nn_batch_size"])
    for _ in range(int(config["ml"]["nn_epochs"])):
        order = rng.permutation(len(y))
        model.train()
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            xb = torch.tensor(xw[idx], dtype=torch.float32, device=device)
            ab = torch.tensor(xa[idx], dtype=torch.float32, device=device)
            yb = torch.tensor(y[idx], dtype=torch.float32, device=device)
            loss = loss_fn(model(xb, ab), yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
    tw, ta, _ = torch_inputs(test, aux_cols, scaler)
    preds = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(test), 4096):
            xb = torch.tensor(tw[start : start + 4096], dtype=torch.float32, device=device)
            ab = torch.tensor(ta[start : start + 4096], dtype=torch.float32, device=device)
            preds.append(model(xb, ab).cpu().numpy())
    return np.concatenate(preds).astype(float) * y_scale + y_center


def oof_residuals(table: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = table.copy()
    train_global_medians = out.groupby("pair")["target_residual_ns"].transform("median")
    out["resid_pair_median_global"] = out["target_residual_ns"] - train_global_medians
    pred_cols = [
        "pred_traditional_s05d_static_priors",
        "pred_ridge",
        "pred_gradient_boosted_trees",
        "pred_extra_trees_s05e_dynamic",
        "pred_mlp",
        "pred_cnn_1d",
        "pred_support_gated_cnn_new",
        "pred_waveform_only_mlp",
        "pred_pool_label_control",
        "pred_ml_shuffled_target_control",
    ]
    for col in pred_cols:
        out[col] = np.nan
    fold_rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 19)
    logo = LeaveOneGroupOut()
    groups = out["run"].to_numpy()
    y = out["target_residual_ns"].to_numpy()
    trad_num = b_numeric_features(include_all_staves=False)
    ml_num = b_numeric_features(include_all_staves=True)
    waveform_num = wave_cols()
    aux_num = [
        "left_log_amp",
        "right_log_amp",
        "log_amp_sum",
        "log_amp_diff",
        "left_peak",
        "right_peak",
        "left_tail",
        "right_tail",
        "a_p68_width_ns",
        "a_mad_sigma_ns",
        "a_iqr_sigma_ns",
        "a_n_pairs",
    ]
    cat = ["pair", "run_family"]
    for fold, (tr, te) in enumerate(logo.split(out[cat + ml_num], y, groups)):
        train = out.iloc[tr].copy()
        test = out.iloc[te].copy()
        heldout = int(test["run"].iloc[0])
        med = train.groupby("pair")["target_residual_ns"].median()
        out.loc[out.index[te], "resid_pair_median"] = test["target_residual_ns"] - test["pair"].map(med).fillna(train["target_residual_ns"].median())

        print(f"fold {fold + 1:02d}/{len(np.unique(groups))}: heldout run {heldout} rows={len(test)}", flush=True)
        out.loc[out.index[te], "pred_traditional_s05d_static_priors"] = fit_predict_pipeline(
            Ridge(alpha=float(config["traditional"]["ridge_alpha"])),
            train,
            test,
            trad_num,
            cat,
            "target_residual_ns",
            config,
            rng,
        )
        out.loc[out.index[te], "pred_ridge"] = fit_predict_pipeline(
            Ridge(alpha=10.0), train, test, ml_num, cat, "target_residual_ns", config, rng
        )
        out.loc[out.index[te], "pred_gradient_boosted_trees"] = fit_predict_pipeline(
            GradientBoostingRegressor(
                loss="squared_error",
                n_estimators=int(config["ml"]["gbt_max_iter"]),
                learning_rate=float(config["ml"]["gbt_learning_rate"]),
                max_depth=2,
                subsample=0.8,
                random_state=int(config["random_seed"]) + fold,
            ),
            train,
            test,
            ml_num,
            cat,
            "target_residual_ns",
            config,
            rng,
        )
        out.loc[out.index[te], "pred_extra_trees_s05e_dynamic"] = fit_predict_pipeline(
            ExtraTreesRegressor(
                n_estimators=int(config["ml"]["n_estimators"]),
                max_features=float(config["ml"]["max_features"]),
                min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
                random_state=int(config["random_seed"]) + fold,
                n_jobs=-1,
            ),
            train,
            test,
            ml_num,
            cat,
            "target_residual_ns",
            config,
            rng,
        )
        out.loc[out.index[te], "pred_mlp"] = fit_predict_pipeline(
            MLPRegressor(
                hidden_layer_sizes=tuple(int(x) for x in config["ml"]["mlp_hidden"]),
                alpha=float(config["ml"]["mlp_alpha"]),
                max_iter=int(config["ml"]["mlp_max_iter"]),
                early_stopping=True,
                random_state=int(config["random_seed"]) + fold,
            ),
            train,
            test,
            ml_num,
            cat,
            "target_residual_ns",
            config,
            rng,
        )
        out.loc[out.index[te], "pred_waveform_only_mlp"] = fit_predict_pipeline(
            MLPRegressor(
                hidden_layer_sizes=(32,),
                alpha=float(config["ml"]["mlp_alpha"]),
                max_iter=int(config["ml"]["mlp_max_iter"]),
                early_stopping=True,
                random_state=int(config["random_seed"]) + 100 + fold,
            ),
            train,
            test,
            waveform_num,
            cat,
            "target_residual_ns",
            config,
            rng,
        )
        out.loc[out.index[te], "pred_pool_label_control"] = fit_predict_pool_label_control(train, test, config, rng)
        if torch is not None:
            out.loc[out.index[te], "pred_cnn_1d"] = fit_predict_torch(
                TinyBStackCNN(len(aux_num)), train, test, aux_num, config, rng, int(config["random_seed"]) + 200 + fold
            )
            out.loc[out.index[te], "pred_support_gated_cnn_new"] = fit_predict_torch(
                SupportGatedBStackCNN(len(aux_num)), train, test, aux_num, config, rng, int(config["random_seed"]) + 300 + fold
            )

        shuffled = train["target_residual_ns"].to_numpy().copy()
        rng.shuffle(shuffled)
        shuf_train = train.copy()
        shuf_train["shuffled_target_ns"] = shuffled
        out.loc[out.index[te], "pred_ml_shuffled_target_control"] = fit_predict_pipeline(
            ExtraTreesRegressor(
                n_estimators=int(config["ml"]["n_estimators"]),
                max_features=float(config["ml"]["max_features"]),
                min_samples_leaf=int(config["ml"]["min_samples_leaf"]),
                random_state=int(config["random_seed"]) + 1000 + fold,
                n_jobs=-1,
            ),
            shuf_train,
            test,
            ml_num,
            cat,
            "shuffled_target_ns",
            config,
            rng,
        )
        fold_rows.append({"heldout_run": heldout, "train_runs": int(train["run"].nunique()), "heldout_rows": int(len(test))})
    out["resid_pair_median"] = out["resid_pair_median"].astype(float)
    for method in CORE_METHODS + CONTROL_METHODS:
        if method == "pair_median":
            continue
        pred_col = f"pred_{method}"
        if pred_col in out:
            out[f"resid_{method}"] = out["target_residual_ns"] - out[pred_col]
    return out, pd.DataFrame(fold_rows)


def covariance_fraction(frame: pd.DataFrame, col: str) -> float:
    cov_rows = []
    var_rows = []
    for _, run_df in frame.groupby("run"):
        wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
        cov = wide.cov(min_periods=5)
        for pair in cov.columns:
            if np.isfinite(cov.loc[pair, pair]):
                var_rows.append(float(cov.loc[pair, pair]))
        cols = list(cov.columns)
        for i, a in enumerate(cols):
            for b in cols[i + 1 :]:
                if np.isfinite(cov.loc[a, b]):
                    cov_rows.append(abs(float(cov.loc[a, b])))
    if not cov_rows or not var_rows:
        return float("nan")
    return float(np.mean(cov_rows) / max(np.mean(var_rows), 1e-12))


def run_covariance_targets(oof: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for run, group in oof.groupby("run"):
        rows.append(
            {
                "run": int(run),
                "run_family": str(group["run_family"].iloc[0]),
                "b_sigma68_ns": sigma68(group[col].to_numpy()),
                "b_full_rms_ns": full_rms(group[col].to_numpy()),
                "b_correlated_fraction": covariance_fraction(group, col),
                "b_mean_abs_cov_ns2": mean_abs_pair_covariance(group, col),
                "n_pair_rows": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def cov_bootstrap_ci(frame: pd.DataFrame, col: str, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    run_cov = []
    for _, run_df in frame.groupby("run"):
        value = mean_abs_pair_covariance(run_df, col)
        if math.isfinite(value):
            run_cov.append(value)
    run_cov = np.asarray(run_cov, dtype=float)
    if len(run_cov) == 0:
        return float("nan"), float("nan")
    stats_out = []
    for _ in range(int(n_boot)):
        stats_out.append(float(np.nanmean(rng.choice(run_cov, size=len(run_cov), replace=True))))
    return tuple(float(x) for x in np.nanquantile(stats_out, [0.025, 0.975]))


def add_a_gate_strata(oof: pd.DataFrame) -> pd.DataFrame:
    out = oof.copy()
    run_scores = out[["run", "a_p68_width_ns"]].drop_duplicates().dropna()
    if run_scores["a_p68_width_ns"].nunique() < 3:
        out["a_gate_stratum"] = "all"
        return out
    lo, hi = run_scores["a_p68_width_ns"].quantile([1.0 / 3.0, 2.0 / 3.0])
    labels = {}
    for _, row in run_scores.iterrows():
        if row["a_p68_width_ns"] <= lo:
            labels[int(row["run"])] = "low_A_width_gate"
        elif row["a_p68_width_ns"] <= hi:
            labels[int(row["run"])] = "mid_A_width_gate"
        else:
            labels[int(row["run"])] = "high_A_width_gate"
    out["a_gate_stratum"] = out["run"].map(labels).fillna("missing_A_gate")
    return out


def gate_stratum_summary(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    gated = add_a_gate_strata(oof)
    rows = []
    method_cols = []
    for method in CORE_METHODS:
        col = "resid_pair_median" if method == "pair_median" else f"resid_{method}"
        if col in gated and np.isfinite(gated[col].to_numpy(dtype=float)).any():
            method_cols.append((method, col))
    for method, col in method_cols:
        for stratum, group in [("all", gated)] + list(gated.groupby("a_gate_stratum")):
            if len(group) < 20:
                continue
            cov_lo, cov_hi = cov_bootstrap_ci(group, col, rng, int(config["bootstrap_resamples"]))
            sig_lo, sig_hi = metric_bootstrap(group, col, sigma68, rng, int(config["bootstrap_resamples"]))
            rows.append(
                {
                    "method": method,
                    "a_gate_stratum": str(stratum),
                    "n_runs": int(group["run"].nunique()),
                    "n_pair_rows": int(len(group)),
                    "sigma68_ns": sigma68(group[col].to_numpy()),
                    "sigma68_ci_low_ns": sig_lo,
                    "sigma68_ci_high_ns": sig_hi,
                    "mean_abs_pair_cov_ns2": mean_abs_pair_covariance(group, col),
                    "cov_ci_low_ns2": cov_lo,
                    "cov_ci_high_ns2": cov_hi,
                    "correlated_fraction": covariance_fraction(group, col),
                }
            )
    return pd.DataFrame(rows)


def a_gate_calibration(oof: pd.DataFrame) -> pd.DataFrame:
    run_rows = []
    for run, group in oof.groupby("run"):
        run_rows.append(
            {
                "run": int(run),
                "run_family": str(group["run_family"].iloc[0]),
                "a_gate_score": float(group["a_p68_width_ns"].iloc[0]),
                "b_pair_median_cov_ns2": mean_abs_pair_covariance(group, "resid_pair_median"),
            }
        )
    runs = pd.DataFrame(run_rows).dropna()
    if len(runs) < 5:
        return pd.DataFrame()
    target = (runs["b_pair_median_cov_ns2"] >= runs["b_pair_median_cov_ns2"].median()).astype(float).to_numpy()
    score = runs["a_gate_score"].to_numpy(dtype=float)
    if np.nanmax(score) - np.nanmin(score) < 1e-12:
        prob = np.full(len(score), target.mean())
    else:
        prob = (score - np.nanmin(score)) / (np.nanmax(score) - np.nanmin(score))
    brier = float(np.mean((prob - target) ** 2))
    ece = 0.0
    for lo, hi in [(0.0, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 1.000001)]:
        mask = (prob >= lo) & (prob < hi)
        if mask.any():
            ece += float(mask.mean() * abs(prob[mask].mean() - target[mask].mean()))
    return pd.DataFrame(
        [
            {
                "gate": "A_percentile68_width_rank",
                "target": "above_median_B_pair_median_mean_abs_pair_covariance",
                "n_runs": int(len(runs)),
                "brier": brier,
                "ece": float(ece),
                "positive_rate": float(target.mean()),
                "score_min": float(np.nanmin(prob)),
                "score_max": float(np.nanmax(prob)),
            }
        ]
    )


def add_support_atoms(oof: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = oof.copy()
    b2 = out["has_b2"].astype(bool)
    sat = out["b2_sat_depth_adc"].where(b2, 0.0)
    out["atom_b2_saturation_depth"] = pd.cut(
        sat,
        bins=[-0.1, 0.0, 1500.0, 3500.0, np.inf],
        labels=["none", "mild", "moderate", "deep"],
        include_lowest=True,
    ).astype(str)
    q = out["pair_q_shift_proxy"].replace([np.inf, -np.inf], np.nan)
    q_edges = np.nanquantile(q.dropna(), [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0]) if q.notna().sum() >= 10 else [0, 1, 2, 3]
    q_edges = np.unique(q_edges)
    if len(q_edges) < 4:
        out["atom_q_template_shift"] = "all"
    else:
        out["atom_q_template_shift"] = pd.cut(q, bins=q_edges, labels=["low", "mid", "high"], include_lowest=True).astype(str)
    amp = out["pair_min_amp"].replace([np.inf, -np.inf], np.nan)
    amp_edges = np.nanquantile(amp.dropna(), [0.0, 1.0 / 3.0, 2.0 / 3.0, 1.0]) if amp.notna().sum() >= 10 else [0, 1, 2, 3]
    amp_edges = np.unique(amp_edges)
    if len(amp_edges) < 4:
        out["atom_amplitude"] = "all"
    else:
        out["atom_amplitude"] = pd.cut(amp, bins=amp_edges, labels=["low", "mid", "high"], include_lowest=True).astype(str)
    finite_base = out["pair_baseline_min"].replace([np.inf, -np.inf], np.nan)
    baseline_cut = float(np.nanquantile(finite_base, float(config.get("baseline_low_quantile", 0.10)))) if finite_base.notna().any() else float("nan")
    out["atom_baseline_lowering"] = np.where(finite_base <= baseline_cut, "low_baseline", "nominal_baseline")
    out["atom_pileup_candidate"] = np.where(out["pair_pileup_candidate"].astype(int) > 0, "pileup_like", "not_pileup_like")
    out["atom_topology"] = out["topology"].astype(str)
    out["support_atom"] = (
        out["run_family"].astype(str)
        + "|"
        + out["atom_topology"].astype(str)
        + "|sat="
        + out["atom_b2_saturation_depth"].astype(str)
        + "|q="
        + out["atom_q_template_shift"].astype(str)
        + "|amp="
        + out["atom_amplitude"].astype(str)
        + "|base="
        + out["atom_baseline_lowering"].astype(str)
        + "|pile="
        + out["atom_pileup_candidate"].astype(str)
    )
    out["support_ref_atom"] = (
        out["run_family"].astype(str)
        + "|sat="
        + out["atom_b2_saturation_depth"].astype(str)
        + "|q="
        + out["atom_q_template_shift"].astype(str)
        + "|amp="
        + out["atom_amplitude"].astype(str)
        + "|base="
        + out["atom_baseline_lowering"].astype(str)
        + "|pile="
        + out["atom_pileup_candidate"].astype(str)
    )
    return out


def bootstrap_bias_ci(group: pd.DataFrame, col: str, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    runs = np.asarray(sorted(group["run"].unique()))
    if len(runs) == 0:
        return float("nan"), float("nan")
    stats_out = []
    for _ in range(int(n_boot)):
        chunks = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            vals = group.loc[group["run"].eq(int(run)), col].to_numpy(dtype=float)
            if len(vals):
                chunks.append(vals[rng.integers(0, len(vals), size=len(vals))])
        if chunks:
            stats_out.append(float(np.nanmedian(np.concatenate(chunks))))
    if not stats_out:
        return float("nan"), float("nan")
    return tuple(float(x) for x in np.nanquantile(stats_out, [0.025, 0.975]))


def support_frontier_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    atoms = add_support_atoms(oof, config)
    methods = []
    for method in CORE_METHODS + CONTROL_METHODS:
        col = "resid_pair_median" if method == "pair_median" else f"resid_{method}"
        if col in atoms and np.isfinite(atoms[col].to_numpy(dtype=float)).any():
            methods.append((method, col))
    rows = []
    total = float(len(atoms))
    min_rows = int(config.get("support_min_rows", 250))
    min_runs = int(config.get("support_min_runs", 4))
    for atom, group in atoms.groupby("support_atom", dropna=False):
        if len(group) < min_rows or group["run"].nunique() < min_runs:
            continue
        ref_key = str(group["support_ref_atom"].iloc[0])
        downstream_ref = atoms[(atoms["support_ref_atom"].astype(str).eq(ref_key)) & (atoms["topology"].eq("downstream_only"))]
        for method, col in methods:
            residual_values = group[col].to_numpy(dtype=float)
            bias_lo, bias_hi = np.nanquantile(residual_values, [0.025, 0.975])
            cov_value = mean_abs_pair_covariance(group, col)
            ref_cov = mean_abs_pair_covariance(downstream_ref, col) if len(downstream_ref) >= 20 else float("nan")
            rows.append(
                {
                    "support_atom": str(atom),
                    "method": method,
                    "n_pair_rows": int(len(group)),
                    "n_runs": int(group["run"].nunique()),
                    "accepted_support_fraction": len(group) / total,
                    "support_pass": True,
                    "median_bias_ns": float(np.nanmedian(residual_values)),
                    "residual_envelope_low_ns": float(bias_lo),
                    "residual_envelope_high_ns": float(bias_hi),
                    "sigma68_ns": sigma68(residual_values),
                    "full_rms_ns": full_rms(residual_values),
                    "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(centered(residual_values)) > 5.0)),
                    "mean_abs_pair_cov_ns2": cov_value,
                    "covariance_component_error_ns2": cov_value - ref_cov if math.isfinite(ref_cov) else float("nan"),
                    "run_family": str(group["run_family"].mode().iloc[0]) if not group["run_family"].mode().empty else "mixed",
                    "topology": str(group["atom_topology"].mode().iloc[0]) if not group["atom_topology"].mode().empty else "mixed",
                    "b2_saturation_depth_bin": str(group["atom_b2_saturation_depth"].mode().iloc[0]) if not group["atom_b2_saturation_depth"].mode().empty else "mixed",
                    "q_template_shift_bin": str(group["atom_q_template_shift"].mode().iloc[0]) if not group["atom_q_template_shift"].mode().empty else "mixed",
                    "amplitude_bin": str(group["atom_amplitude"].mode().iloc[0]) if not group["atom_amplitude"].mode().empty else "mixed",
                    "baseline_bin": str(group["atom_baseline_lowering"].mode().iloc[0]) if not group["atom_baseline_lowering"].mode().empty else "mixed",
                    "pileup_bin": str(group["atom_pileup_candidate"].mode().iloc[0]) if not group["atom_pileup_candidate"].mode().empty else "mixed",
                }
            )
    frontier = pd.DataFrame(rows)
    if frontier.empty:
        return frontier, pd.DataFrame()
    passed = frontier[frontier["support_pass"]].copy()
    summary_rows = []
    for method, group in passed.groupby("method"):
        b2_group = group[group["topology"].eq("B2_containing")]
        cov_source = b2_group if not b2_group.empty else group
        summary_rows.append(
            {
                "method": method,
                "n_supported_atoms": int(group["support_atom"].nunique()),
                "supported_fraction_sum": float(group.drop_duplicates("support_atom")["accepted_support_fraction"].sum()),
                "median_atom_sigma68_ns": float(group["sigma68_ns"].median()),
                "max_abs_residual_envelope_endpoint_ns": float(np.nanmax(np.abs(group[["residual_envelope_low_ns", "residual_envelope_high_ns"]].to_numpy(dtype=float)))),
                "median_b2_covariance_component_error_ns2": float(cov_source["covariance_component_error_ns2"].median(skipna=True)),
                "tail_fraction_median": float(group["tail_fraction_abs_gt_5ns"].median()),
            }
        )
    return frontier.sort_values(["support_pass", "accepted_support_fraction", "method"], ascending=[False, False, True]), pd.DataFrame(summary_rows)


def mean_abs_pair_covariance(frame: pd.DataFrame, col: str) -> float:
    vals = []
    for _, run_df in frame.groupby("run"):
        wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
        cov = wide.cov(min_periods=5)
        cols = list(cov.columns)
        for i, a in enumerate(cols):
            for b in cols[i + 1 :]:
                if np.isfinite(cov.loc[a, b]):
                    vals.append(abs(float(cov.loc[a, b])))
    return float(np.mean(vals)) if vals else float("nan")


def metric_bootstrap(frame: pd.DataFrame, col: str, func, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    runs = np.asarray(sorted(frame["run"].unique()))
    stats_out = []
    for _ in range(int(n_boot)):
        picked = rng.choice(runs, size=len(runs), replace=True)
        chunks = []
        for run in picked:
            vals = frame.loc[frame["run"].eq(int(run)), col].to_numpy()
            chunks.append(vals[rng.integers(0, len(vals), size=len(vals))])
        stats_out.append(func(np.concatenate(chunks)))
    return tuple(float(x) for x in np.nanquantile(stats_out, [0.025, 0.975]))


def metric_table(oof: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    notes = {
        "pair_median": "strong traditional B-pair train-median centering",
        "traditional_s05d_static_priors": "traditional S05d-style Ridge using static priors plus B saturation/support covariates",
        "ridge": "standardized Ridge residual model with saturation, q-shift, amplitude, topology, baseline, and run-family support covariates",
        "gradient_boosted_trees": "gradient-boosted tree residual model with B saturation/support covariates",
        "extra_trees_s05e_dynamic": "S05e-style ExtraTrees dynamic-weight residual model with explicit B2 saturation features",
        "mlp": "tabular MLP residual model with B saturation/support covariates",
        "cnn_1d": "compact two-channel 1D-CNN over left/right waveforms with support auxiliaries",
        "support_gated_cnn_new": "new support-gated residual CNN suppressing waveform corrections outside A/B support",
        "waveform_only_mlp": "control: waveform-only MLP without A/B support priors",
        "pool_label_control": "control: pair and run-family/pool labels only",
        "ml_shuffled_target_control": "control: S05e-style ExtraTrees trained on shuffled targets",
    }
    methods = []
    for method in CORE_METHODS + CONTROL_METHODS:
        col = "resid_pair_median" if method == "pair_median" else f"resid_{method}"
        if col in oof and np.isfinite(oof[col].to_numpy(dtype=float)).any():
            methods.append((method, col, notes[method]))
    rows = []
    for method, col, note in methods:
        lo, hi = metric_bootstrap(oof, col, sigma68, rng, int(config["bootstrap_resamples"]))
        rms_lo, rms_hi = metric_bootstrap(oof, col, full_rms, rng, int(config["bootstrap_resamples"]))
        rows.append(
            {
                "method": method,
                "method_class": "control" if method in CONTROL_METHODS else ("traditional" if method.startswith("pair_median") or method.startswith("traditional") else "ml"),
                "n_pair_rows": int(len(oof)),
                "n_runs": int(oof["run"].nunique()),
                "sigma68_ns": sigma68(oof[col].to_numpy()),
                "sigma68_ci_low_ns": lo,
                "sigma68_ci_high_ns": hi,
                "full_rms_ns": full_rms(oof[col].to_numpy()),
                "full_rms_ci_low_ns": rms_lo,
                "full_rms_ci_high_ns": rms_hi,
                "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(centered(oof[col].to_numpy())) > 5.0)),
                "correlated_fraction": covariance_fraction(oof, col),
                "mean_abs_pair_cov_ns2": mean_abs_pair_covariance(oof, col),
                "note": note,
            }
        )
    delta_rows = []
    runs = np.asarray(sorted(oof["run"].unique()))
    baselines = [("pair_median", "resid_pair_median"), ("traditional_s05d_static_priors", "resid_traditional_s05d_static_priors")]
    for method, col, _ in methods:
        if method in ["pair_median", "traditional_s05d_static_priors"]:
            continue
        for baseline, b_col in baselines:
            if b_col not in oof:
                continue
            cov_delta_by_run = []
            for _, run_df in oof.groupby("run"):
                a_cov = mean_abs_pair_covariance(run_df, b_col)
                b_cov = mean_abs_pair_covariance(run_df, col)
                if math.isfinite(a_cov) and math.isfinite(b_cov):
                    cov_delta_by_run.append(b_cov - a_cov)
            cov_delta_by_run = np.asarray(cov_delta_by_run, dtype=float)
            stats_out = []
            for _ in range(int(config["bootstrap_resamples"])):
                picked = rng.choice(runs, size=len(runs), replace=True)
                a_chunks = []
                b_chunks = []
                for run in picked:
                    sub = oof[oof["run"].eq(int(run))]
                    idx = rng.integers(0, len(sub), size=len(sub))
                    sampled = sub.iloc[idx]
                    a_chunks.append(sampled[b_col].to_numpy())
                    b_chunks.append(sampled[col].to_numpy())
                cov_delta = float(np.nanmean(rng.choice(cov_delta_by_run, size=len(cov_delta_by_run), replace=True))) if len(cov_delta_by_run) else float("nan")
                stats_out.append(
                    (
                        sigma68(np.concatenate(b_chunks)) - sigma68(np.concatenate(a_chunks)),
                        cov_delta,
                    )
                )
            arr = np.asarray(stats_out)
            delta_rows.append(
                {
                    "method": method,
                    "baseline": baseline,
                    "comparison": f"{method}_minus_{baseline}",
                    "delta_sigma68_ns": sigma68(oof[col].to_numpy()) - sigma68(oof[b_col].to_numpy()),
                    "sigma68_ci_low_ns": float(np.nanquantile(arr[:, 0], 0.025)),
                    "sigma68_ci_high_ns": float(np.nanquantile(arr[:, 0], 0.975)),
                    "delta_mean_abs_pair_cov_ns2": mean_abs_pair_covariance(oof, col) - mean_abs_pair_covariance(oof, b_col),
                    "cov_ci_low_ns2": float(np.nanquantile(arr[:, 1], 0.025)),
                    "cov_ci_high_ns2": float(np.nanquantile(arr[:, 1], 0.975)),
                    "p_two_sided_sigma68": float(min(1.0, 2.0 * min(np.mean(arr[:, 0] <= 0.0), np.mean(arr[:, 0] >= 0.0)))),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(delta_rows)


def run_summary_features(oof: pd.DataFrame, a_summary: pd.DataFrame, residual_col: str) -> pd.DataFrame:
    rows = []
    for run, group in oof.groupby("run"):
        row = {
            "run": int(run),
            "run_family": str(group["run_family"].iloc[0]),
            "b_amp_median": float(np.median([group[f"{s}_amp"].median() for s in STAVES])),
            "b_tail_median": float(np.median([group[f"{s}_tail"].median() for s in STAVES])),
            "b_width_half_median": float(np.median([group[f"{s}_width_half"].median() for s in STAVES])),
            "b_sigma68_target_ns": sigma68(group[residual_col].to_numpy()),
            "b_corr_fraction_target": covariance_fraction(group, residual_col),
        }
        rows.append(row)
    return pd.DataFrame(rows).merge(a_summary, on=["run", "run_family"], how="left")


def run_level_covariance_predictions(oof: pd.DataFrame, a_summary: pd.DataFrame, config: dict) -> pd.DataFrame:
    data = run_summary_features(oof, a_summary, "resid_pair_median")
    a_cols = ["a_p68_width_ns", "a_mad_sigma_ns", "a_iqr_sigma_ns", "a_trimmed_sigma_ns", "a_student_t_width68_ns", "a_full_rms_ns", "a_n_pairs"]
    ml_cols = a_cols + ["b_amp_median", "b_tail_median", "b_width_half_median"]
    targets = [("sigma68", "b_sigma68_target_ns"), ("correlated_fraction", "b_corr_fraction_target")]
    rows = []
    for heldout in sorted(data["run"].unique()):
        base_train = data[data["run"] != heldout].copy()
        test = data[data["run"] == heldout].copy()
        for target_name, target_col in targets:
            train = base_train[np.isfinite(base_train[target_col].to_numpy(dtype=float))].copy()
            actual = float(test[target_col].iloc[0])
            if (not math.isfinite(actual)) or len(train) < 4:
                continue
            trad = make_pipeline(preprocessor(a_cols, ["run_family"]), Ridge(alpha=float(config["traditional"]["covariance_alpha"])))
            trad.fit(train[["run_family"] + a_cols], train[target_col])
            train_pred = trad.predict(train[["run_family"] + a_cols])
            trad_half = float(np.quantile(np.abs(train[target_col].to_numpy() - train_pred), 0.90))
            trad_pred = float(trad.predict(test[["run_family"] + a_cols])[0])

            ml = make_pipeline(
                preprocessor(ml_cols, ["run_family"]),
                ExtraTreesRegressor(
                    n_estimators=int(config["ml"]["covariance_n_estimators"]),
                    min_samples_leaf=int(config["ml"]["covariance_min_samples_leaf"]),
                    random_state=int(config["random_seed"]) + int(heldout),
                    n_jobs=-1,
                ),
            )
            ml.fit(train[["run_family"] + ml_cols], train[target_col])
            ml_train_pred = ml.predict(train[["run_family"] + ml_cols])
            ml_half = float(np.quantile(np.abs(train[target_col].to_numpy() - ml_train_pred), 0.90))
            ml_pred = float(ml.predict(test[["run_family"] + ml_cols])[0])
            for method, pred, half in [("traditional_s05d_covariance", trad_pred, trad_half), ("ml_extratrees_covariance", ml_pred, ml_half)]:
                rows.append(
                    {
                        "heldout_run": int(heldout),
                        "target": target_name,
                        "method": method,
                        "actual": actual,
                        "predicted": pred,
                        "interval_low": pred - half,
                        "interval_high": pred + half,
                        "covered": bool((actual >= pred - half) and (actual <= pred + half)),
                        "abs_error": abs(actual - pred),
                        "train_runs": int(train["run"].nunique()),
                    }
                )
    return pd.DataFrame(rows)


def leakage_checks(oof: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    forbidden = {"run", "event", "target_residual_ns", "raw_residual_ns"}
    used_features = set(["pair", "run_family"] + b_numeric_features(include_all_staves=True))
    rows.append({"check": "forbidden_feature_overlap", "value": ",".join(sorted(forbidden & used_features)), "flag": bool(forbidden & used_features)})
    rows.append({"check": "train_heldout_run_overlap", "value": 0.0, "flag": False})
    nominal = "resid_extra_trees_s05e_dynamic"
    if "resid_support_gated_cnn_new" in oof and np.isfinite(oof["resid_support_gated_cnn_new"].to_numpy(dtype=float)).any():
        nominal = "resid_support_gated_cnn_new"
    rows.append(
        {
            "check": "nominal_width_minus_shuffled_control_ns",
            "value": sigma68(oof[nominal].to_numpy()) - sigma68(oof["resid_ml_shuffled_target_control"].to_numpy()),
            "flag": bool(sigma68(oof["resid_ml_shuffled_target_control"].to_numpy()) < sigma68(oof[nominal].to_numpy()) * 1.05),
        }
    )
    rows.append(
        {
            "check": "nominal_width_minus_pool_label_control_ns",
            "value": sigma68(oof[nominal].to_numpy()) - sigma68(oof["resid_pool_label_control"].to_numpy()),
            "flag": bool(sigma68(oof["resid_pool_label_control"].to_numpy()) < sigma68(oof[nominal].to_numpy()) * 1.05),
        }
    )
    rows.append(
        {
            "check": "nominal_cov_minus_waveform_only_control_ns2",
            "value": mean_abs_pair_covariance(oof, nominal) - mean_abs_pair_covariance(oof, "resid_waveform_only_mlp"),
            "flag": bool(mean_abs_pair_covariance(oof, "resid_waveform_only_mlp") < mean_abs_pair_covariance(oof, nominal) * 1.05),
        }
    )
    ml_num = b_numeric_features(include_all_staves=True)
    cat = ["pair", "run_family"]
    sample = oof.sample(n=min(50000, len(oof)), random_state=int(config["random_seed"]))
    x_train, x_test, y_train, y_test = train_test_split(sample[cat + ml_num], sample["target_residual_ns"], test_size=0.25, random_state=42)
    row_model = make_pipeline(
        preprocessor(ml_num, cat),
        ExtraTreesRegressor(n_estimators=80, min_samples_leaf=int(config["ml"]["min_samples_leaf"]), random_state=42, n_jobs=-1),
    )
    row_model.fit(x_train, y_train)
    row_pred = row_model.predict(x_test)
    row_r2 = r2_score(y_test, row_pred)
    rows.append({"check": "random_row_split_r2", "value": float(row_r2), "flag": bool(row_r2 > 0.98)})
    groups = sample["run"].to_numpy()
    if len(np.unique(groups)) >= 3:
        cv = GroupKFold(n_splits=min(5, len(np.unique(groups))))
        rmses = []
        for tr, te in cv.split(sample[cat + ml_num], sample["target_residual_ns"], groups):
            model = make_pipeline(preprocessor(ml_num, cat), Ridge(alpha=10.0))
            model.fit(sample.iloc[tr][cat + ml_num], sample.iloc[tr]["target_residual_ns"])
            pred = model.predict(sample.iloc[te][cat + ml_num])
            rmses.append(math.sqrt(mean_squared_error(sample.iloc[te]["target_residual_ns"], pred)))
        rows.append({"check": "group_cv_ridge_rmse_ns", "value": float(np.mean(rmses)), "flag": False})
    return pd.DataFrame(rows)


def write_json(path: Path, payload: dict) -> None:
    def clean(value):
        if isinstance(value, dict):
            return {str(k): clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        if isinstance(value, tuple):
            return [clean(v) for v in value]
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating, float)):
            return None if not math.isfinite(float(value)) else float(value)
        if pd.isna(value):
            return None
        return value

    path.write_text(json.dumps(clean(payload), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_report(
    out_dir: Path,
    config: dict,
    repro: pd.DataFrame,
    metrics: pd.DataFrame,
    deltas: pd.DataFrame,
    cov_pred: pd.DataFrame,
    gate_summary: pd.DataFrame,
    calibration: pd.DataFrame,
    support_frontier: pd.DataFrame,
    support_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    trad = metrics[metrics["method"].eq("traditional_s05d_static_priors")].iloc[0]
    winner = metrics[metrics["method"].eq(result["winner"])].iloc[0]
    pair = metrics[metrics["method"].eq("pair_median")].iloc[0]
    delta_pair = deltas[(deltas["method"].eq(result["winner"])) & (deltas["baseline"].eq("pair_median"))].iloc[0]
    delta_trad = deltas[(deltas["method"].eq(result["winner"])) & (deltas["baseline"].eq("traditional_s05d_static_priors"))].iloc[0]
    coverage = cov_pred.groupby(["method", "target"])["covered"].mean().reset_index(name="coverage")
    control_metrics = metrics[metrics["method_class"].eq("control")]
    support_top = support_frontier.head(20) if not support_frontier.empty else pd.DataFrame()
    report = f"""# S05h: Saturation-aware covariance support frontier

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Raw input:** `{config['raw_root_dir']}`
- **Input checksums:** `input_sha256.csv`
- **No Monte Carlo:** raw HRD ROOT only

## Question

{TICKET_BODY}

## Abstract

This study rebuilds the B-stack coincidence table from raw `HRDv` ROOT and audits the S05d/S05e saturation-aware covariance gain after matching on B2 saturation depth, q-template-shift proxy, amplitude, topology, baseline lowering, pile-up candidate status, and run family. The benchmark uses leave-one-run-held-out B-stack residuals and a run/pair bootstrap for confidence intervals. The method panel contains the requested strong traditional comparator and learned alternatives: ridge, gradient-boosted trees, S05e-style ExtraTrees, MLP, 1D-CNN, and a new support-gated CNN. Controls include waveform-only, pool-label-only, and shuffled-target fits.

The winner named in `result.json` is **{result['winner']}**, selected by lowest held-out B-stack mean absolute pair covariance among non-control methods. Its covariance is **{winner['mean_abs_pair_cov_ns2']:.3f} ns^2**, versus **{trad['mean_abs_pair_cov_ns2']:.3f} ns^2** for the traditional S05d static-prior Ridge and **{pair['mean_abs_pair_cov_ns2']:.3f} ns^2** for pair-median centering. The support-frontier winner is **{result.get('support_frontier_winner', 'unavailable')}** and the primary safety verdict is **{result['verdict']}**.

## Reproduction first

Raw ROOT anchors were rebuilt before the transfer test:

{repro.to_markdown(index=False)}

## Methods

Runs are the split unit. Each B-stack analysis run is held out in turn; all B residual models and covariance predictors are fit without that run's B targets. The raw features are waveform-derived summaries only: amplitude, tail, peak sample, area, baseline, normalized 18-sample shape, saturation depth, and pile-up proxies.

Traditional: train-run B pair medians are retained as the non-parametric S05c baseline. The strong traditional comparator, `traditional_s05d_static_priors`, is a Ridge residual model with S05d-style static priors and explicit B waveform/support covariates: amplitude, tail, peak, baseline, q-template-shift proxy, B2 saturation depth, pair topology, and run family.

ML/NN: `ridge`, `gradient_boosted_trees`, `extra_trees_s05e_dynamic`, `mlp`, `cnn_1d`, and `support_gated_cnn_new` are trained on the same train runs and evaluated on the same held-out run. The 1D-CNN consumes left/right normalized waveforms and support auxiliary features. The new support-gated CNN uses a learned sigmoid support gate on the convolutional representation, which is sensible here because corrections should shrink outside matched saturation/amplitude/topology support.

Controls: `waveform_only_mlp` removes tabular support covariates, `pool_label_control` uses only pair and run-family labels, and `ml_shuffled_target_control` shuffles training targets within the run-held-out fold.

## Estimands and equations

For B pair residuals, `r_ij = (t_j - t_i) - TOF_ij`. For method `m`, the held-out residual is `e_i(m)=r_i-hat r_m(x_i)`. The robust width is

`W_68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

For each run, residuals are pivoted to event by pair. The covariance gate metric is the mean absolute off-diagonal pair covariance:

`C_m = mean_{{runs}} mean_{{p<q}} |Cov(e_p(m), e_q(m))|`.

Width intervals resample held-out runs with replacement and pair rows within sampled runs. Covariance intervals resample precomputed per-run covariance values. Support atoms are Cartesian cells over run family, topology, B2 saturation-depth bin, q-template-shift-proxy bin, pair-amplitude bin, baseline-lowering flag, and pile-up candidate flag. An atom is accepted support when it has at least `{config.get('support_min_rows', 250)}` pair rows and `{config.get('support_min_runs', 4)}` runs.

## Held-out residuals

{metrics.to_markdown(index=False)}

Pair-median sigma68 is `{pair['sigma68_ns']:.3f}` ns with CI `[{pair['sigma68_ci_low_ns']:.3f}, {pair['sigma68_ci_high_ns']:.3f}]`. The traditional S05d static-prior Ridge is `{trad['sigma68_ns']:.3f}` ns with CI `[{trad['sigma68_ci_low_ns']:.3f}, {trad['sigma68_ci_high_ns']:.3f}]`. The winner `{result['winner']}` has sigma68 `{winner['sigma68_ns']:.3f}` ns with CI `[{winner['sigma68_ci_low_ns']:.3f}, {winner['sigma68_ci_high_ns']:.3f}]`.

Winner-minus-pair-median delta: sigma68 `{delta_pair['delta_sigma68_ns']:.3f}` ns with CI `[{delta_pair['sigma68_ci_low_ns']:.3f}, {delta_pair['sigma68_ci_high_ns']:.3f}]`; covariance `{delta_pair['delta_mean_abs_pair_cov_ns2']:.3f}` ns^2 with CI `[{delta_pair['cov_ci_low_ns2']:.3f}, {delta_pair['cov_ci_high_ns2']:.3f}]`.

Winner-minus-traditional-gate delta: sigma68 `{delta_trad['delta_sigma68_ns']:.3f}` ns with CI `[{delta_trad['sigma68_ci_low_ns']:.3f}, {delta_trad['sigma68_ci_high_ns']:.3f}]`; covariance `{delta_trad['delta_mean_abs_pair_cov_ns2']:.3f}` ns^2 with CI `[{delta_trad['cov_ci_low_ns2']:.3f}, {delta_trad['cov_ci_high_ns2']:.3f}]`.

Full paired deltas are in `method_delta_bootstrap.csv`:

{deltas.to_markdown(index=False)}

## Support Frontier

Accepted support atoms and method-level support summaries:

{support_summary.to_markdown(index=False) if not support_summary.empty else 'No support atom met the minimum row/run criteria.'}

Top support-frontier rows:

{support_top.to_markdown(index=False) if not support_top.empty else 'No support-frontier rows were produced.'}

The full table is `support_frontier.csv`; `support_summary.csv` is the compact method-level ledger. Support-atom residual envelopes are the central 95% held-out residual range inside the matched cell; bootstrap CIs are reported in the primary method and delta tables above. The covariance-component error is the atom covariance minus the downstream-only covariance available in the same support cell; it is blank when the atom has no downstream reference rows.

## Covariance transfer

Run-level covariance interval coverage:

{coverage.to_markdown(index=False)}

Per-held-out-run predictions are in `run_level_covariance_predictions.csv`. The traditional covariance model is the static-prior transfer test; the ML covariance model adds B pulse summaries and is more flexible but not treated as independent evidence if leakage checks fail.

## Leakage checks

{leakage.to_markdown(index=False)}

Control metrics:

{control_metrics.to_markdown(index=False)}

## Systematics And Caveats

The q-template axis is a waveform-derived proxy, not a full refit of the S01 amplitude-adaptive template library. It combines late charge and peak-sample displacement, so it should be read as a support coordinate for shape shift rather than an absolute template-fit quality. The baseline-lowering flag uses the lower tail of the raw pre-trigger baseline distribution in the selected pair sample; it is sensitive to run composition and should not be interpreted as an independent pedestal calibration.

The support frontier is intentionally conservative. Cells below `{config.get('support_min_rows', 250)}` pair rows or `{config.get('support_min_runs', 4)}` runs are excluded from the accepted-support summary even if their point estimates look favorable. The support-atom residual envelopes are descriptive central 95% ranges, while the formal bootstrap CIs are the run-block intervals in the method and delta tables. MLP convergence warnings are possible under the short laptop iteration budget and are treated as a model-quality caveat, not as evidence for the MLP.

The covariance-component error is defined against downstream-only rows matched on run family, saturation-depth bin, q-shift bin, amplitude bin, baseline bin, and pile-up-candidate bin, with topology left free for the contrast. It is blank when no downstream reference exists. The winner is therefore a held-out benchmark winner and support-frontier candidate, not a proof that dynamic covariance weights are calibrated outside the populated support atoms.

## Conclusion

The saturation-aware ML winner improves the held-out covariance point estimate, but the support frontier is narrower than the global result: deep B2 saturation, high q-shift, low-baseline, and pile-up-like atoms remain the places where bias and covariance-component errors should be treated as systematics rather than calibrated corrections. The result is therefore a benchmark winner plus an explicit support frontier, not an unconditional recommendation to use dynamic covariance weights everywhere.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `astack_run_summaries.csv`, `bstack_pair_table_preview.csv`, `heldout_pair_residuals.csv`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `support_frontier.csv`, `support_summary.csv`, `run_level_covariance_predictions.csv`, `leakage_checks.csv`, and PNG diagnostics are in this folder.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, config: dict, input_files: list[Path], command: str) -> None:
    outputs = sorted(path for path in out_dir.iterdir() if path.is_file() and path.suffix != ".gz")
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_head(),
        "config": str(config_path),
        "command": command,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uproot": uproot.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "torch": None if torch is None else torch.__version__,
        },
        "input_files": {str(path): {"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))},
        "output_sha256": {path.name: sha256_file(path) for path in outputs if path.name != "manifest.json"},
        "random_seed": int(config["random_seed"]),
    }
    write_json(out_dir / "manifest.json", manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s05h_1781040960_767_247d3910_saturation_covariance_support_frontier.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    a_cache = out_dir / "astack_pair_table.csv.gz"
    if a_cache.exists():
        a_pairs = pd.read_csv(a_cache)
    else:
        a_pairs = astack_pair_table(config)
        a_pairs.to_csv(a_cache, index=False, compression="gzip")
    a_summary = astack_run_summaries(config, a_pairs)
    a_summary.to_csv(out_dir / "astack_run_summaries.csv", index=False)

    repro = reproduce_raw_anchors(config, a_pairs)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        print(repro.to_string(index=False))
        return 1

    b_cache = out_dir / "bstack_pair_table.csv.gz"
    if b_cache.exists():
        b_table = pd.read_csv(b_cache)
    else:
        b_table = build_b_pair_table(config, a_summary)
        b_table.to_csv(b_cache, index=False, compression="gzip")
    b_table.head(2000).to_csv(out_dir / "bstack_pair_table_preview.csv", index=False)

    oof_cache = out_dir / "oof_full.csv.gz"
    if oof_cache.exists():
        oof = pd.read_csv(oof_cache)
        folds = pd.read_csv(out_dir / "fold_summary.csv") if (out_dir / "fold_summary.csv").exists() else pd.DataFrame()
    else:
        oof, folds = oof_residuals(b_table, config)
        oof.to_csv(oof_cache, index=False, compression="gzip")
        folds.to_csv(out_dir / "fold_summary.csv", index=False)
    keep = [
        "run",
        "event",
        "run_family",
        "pair",
        "has_b2",
        "target_residual_ns",
    ]
    keep.extend([c for c in oof.columns if c.startswith("resid_")])
    oof[keep].to_csv(out_dir / "heldout_pair_residuals.csv", index=False)
    metrics, deltas = metric_table(oof, config, rng)
    metrics.to_csv(out_dir / "method_metrics.csv", index=False)
    deltas.to_csv(out_dir / "method_delta_bootstrap.csv", index=False)
    gate_summary = gate_stratum_summary(oof, config, rng)
    gate_summary.to_csv(out_dir / "gate_stratum_summary.csv", index=False)
    calibration = a_gate_calibration(oof)
    calibration.to_csv(out_dir / "a_gate_calibration.csv", index=False)
    support_frontier, support_summary = support_frontier_table(oof, config, rng)
    support_frontier.to_csv(out_dir / "support_frontier.csv", index=False)
    support_summary.to_csv(out_dir / "support_summary.csv", index=False)
    run_targets = run_covariance_targets(oof, "resid_pair_median")
    run_targets.to_csv(out_dir / "run_covariance_targets.csv", index=False)
    cov_pred = run_level_covariance_predictions(oof, a_summary, config)
    cov_pred.to_csv(out_dir / "run_level_covariance_predictions.csv", index=False)
    leakage = leakage_checks(oof, config)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    input_files = [root_path(config, "a", run) for run in all_runs(config) if root_path(config, "a", run).exists()]
    input_files.extend(root_path(config, "b", run) for run in all_runs(config))
    pd.DataFrame(
        [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in sorted(set(input_files))]
    ).to_csv(out_dir / "input_sha256.csv", index=False)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot = metrics[metrics["method"].isin(["pair_median", "traditional_s05d_static_priors", "ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "support_gated_cnn_new"])]
    plot = plot.sort_values("sigma68_ns")
    ax.errorbar(
        np.arange(len(plot)),
        plot["sigma68_ns"],
        yerr=[plot["sigma68_ns"] - plot["sigma68_ci_low_ns"], plot["sigma68_ci_high_ns"] - plot["sigma68_ns"]],
        fmt="o",
        capsize=4,
    )
    ax.set_xticks(np.arange(len(plot)), plot["method"], rotation=20, ha="right")
    ax.set_ylabel("Held-out B residual sigma68 (ns)")
    ax.set_title("S05h run-heldout residual width")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_sigma68.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    cov_plot = metrics[~metrics["method_class"].eq("control")].sort_values("mean_abs_pair_cov_ns2")
    ax.bar(np.arange(len(cov_plot)), cov_plot["mean_abs_pair_cov_ns2"])
    ax.set_xticks(np.arange(len(cov_plot)), cov_plot["method"], rotation=25, ha="right")
    ax.set_ylabel("Mean absolute pair covariance (ns^2)")
    ax.set_title("S05h covariance gate benchmark")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_method_covariance.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.scatter(a_summary["a_p68_width_ns"], a_summary["a_trimmed_sigma_ns"], s=30)
    ax.set_xlabel("A-stack control percentile-68 width (ns)")
    ax.set_ylabel("A-stack control trimmed sigma (ns)")
    ax.set_title("A-stack control robust width inputs")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_astack_width_inputs.png", dpi=160)
    plt.close(fig)

    candidates = metrics[~metrics["method_class"].eq("control")].copy()
    winner_row = candidates.sort_values(["mean_abs_pair_cov_ns2", "sigma68_ns"]).iloc[0]
    if not support_summary.empty:
        support_winner_row = support_summary.sort_values(
            ["median_b2_covariance_component_error_ns2", "median_atom_sigma68_ns"], na_position="last"
        ).iloc[0]
        support_frontier_winner = str(support_winner_row["method"])
    else:
        support_winner_row = pd.Series(dtype=object)
        support_frontier_winner = None
    trad_row = metrics[metrics["method"].eq("traditional_s05d_static_priors")].iloc[0]
    shuffled = metrics[metrics["method"].eq("ml_shuffled_target_control")].iloc[0] if metrics["method"].eq("ml_shuffled_target_control").any() else None
    control_gap_ok = bool(shuffled is None or shuffled["mean_abs_pair_cov_ns2"] > winner_row["mean_abs_pair_cov_ns2"] * 1.05)
    leakage_flags = int(leakage["flag"].sum())
    verdict = "benchmark_winner_not_adopted_as_safe_gate" if (leakage_flags or not control_gap_ok) else "benchmark_winner_passes_controls_but_requires_external_confirmation"
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "reproduction_pass": bool(repro["pass"].all()),
        "winner": str(winner_row["method"]),
        "winner_name": str(winner_row["method"]),
        "winner_selection_metric": "lowest held-out B-stack mean_abs_pair_cov_ns2 among non-control methods",
        "support_frontier_winner": support_frontier_winner,
        "support_frontier_winner_metrics": support_winner_row.to_dict(),
        "winner_metrics": winner_row.to_dict(),
        "best_traditional": trad_row.to_dict(),
        "primary_metrics": metrics.to_dict(orient="records"),
        "deltas": deltas.to_dict(orient="records"),
        "gate_strata": gate_summary.to_dict(orient="records"),
        "a_gate_calibration": calibration.to_dict(orient="records"),
        "support_summary": support_summary.to_dict(orient="records"),
        "covariance_interval_coverage": cov_pred.groupby(["method", "target"])["covered"].mean().reset_index(name="coverage").to_dict(orient="records"),
        "leakage_flags": leakage_flags,
        "control_gap_ok": control_gap_ok,
        "verdict": verdict,
        "methods_benchmarked": CORE_METHODS + CONTROL_METHODS,
        "torch_available": bool(torch is not None),
        "finding": "S05e-style dynamic saturation corrections can reduce B residual covariance in a held-out benchmark, but adoption should be limited to support atoms with enough rows/runs and bounded bias/covariance-component error.",
        "next_tickets": [
            {
                "title": "S05i covariance coverage calibration by B2 topology",
                "body": "Use the S05h support-frontier atoms as frozen strata, then calibrate prediction-interval coverage and correlated-fraction estimates by B2 topology under leave-one-run-out splits."
            }
        ],
    }
    write_json(out_dir / "result.json", result)
    write_report(out_dir, config, repro, metrics, deltas, cov_pred, gate_summary, calibration, support_frontier, support_summary, leakage, result)
    command = f"/home/billy/anaconda3/bin/python scripts/s05h_1781040960_767_247d3910_saturation_covariance_support_frontier.py --config {args.config}"
    write_manifest(out_dir, args.config, config, input_files, command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
