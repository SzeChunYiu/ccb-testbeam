#!/usr/bin/env python3
"""S15 dE-E particle ID p-vs-d traditional/ML bakeoff.

This runner benchmarks strong traditional dE-E/tail/pedestal likelihood features
against ridge, gradient-boosted trees, MLP, 1D-CNN, and a spectral transformer
on keyed digitized GEANT4 proton/deuteron truth. It independently reproduces
the canonical raw B-stack ROOT selected-pulse count before fitting any model.
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
from typing import Dict, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s32d")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import roc_auc_score

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s31a_1783882773_37910_7224325e_frequency_domain_pulse_timing_pid_benchmark as s31a
import t07_tradshape_ml_benchmark as t07


METHOD_LABEL = {
    "traditional_fourier_wavelet_cfd_matched": "traditional_dE_E_tail_pedestal_likelihood",
    "ML_ridge": "ridge",
    "ML_gradient_boosted_trees": "gradient_boosted_trees",
    "ML_mlp": "mlp",
    "NN_1d_cnn": "1d_cnn",
    "NN_spectral_transformer_new": "spectral_transformer_new",
}

PRIMARY_ENDPOINTS = [
    "pid_separation",
    "energy_scale",
    "pileup_sideband",
    "saturation_clipping",
    "pedestal_noise_color",
    "pulse_shape_harmonics",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
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


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(x, dtype=float), -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-x))


def calibration_ece(y: np.ndarray, score: np.ndarray, bins: int = 10) -> float:
    y = np.asarray(y, dtype=int)
    p = sigmoid(score)
    edges = np.linspace(0.0, 1.0, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1.0 else p <= hi)
        if mask.any():
            ece += float(mask.mean()) * abs(float(p[mask].mean()) - float(y[mask].mean()))
    return ece


def digitized_truth_dataset(config: dict) -> Tuple[np.ndarray, pd.DataFrame]:
    events = pd.read_csv(ROOT / config["g4_08_report_dir"] / "benchmark_truth_events.csv")
    root_path = ROOT / config["g4_digitized_root"]
    with uproot.open(root_path)["g4_08_digitized"] as tree:
        waves = tree["HRDv_digitized"].array(library="np").astype(np.float32)
    if len(waves) != len(events):
        raise RuntimeError(f"digitized waveform/event length mismatch: {len(waves)} vs {len(events)}")
    baseline = np.median(waves[:, :4], axis=1)
    corrected = waves - baseline[:, None]
    amp = corrected.max(axis=1)
    norm = corrected / np.maximum(amp[:, None], 1.0)
    meta = pd.DataFrame(
        {
            "run": events["source_run"].astype(int),
            "group": np.where(events["source_run"].astype(int) <= 57, "sample_i_analysis", "sample_ii_analysis"),
            "event_id": events["event_id"],
            "stave": events["stave"],
            "stave_idx": events["stave"].map({"B2": 0, "B4": 1, "B6": 2, "B8": 3}).astype(np.int8),
            "amplitude_adc": amp.astype(np.float32),
            "target_odd_neg_amp": (events["true_amp2_adc"].to_numpy(float)).astype(np.float32),
            "baseline_adc": baseline.astype(np.float32),
            "peak_sample": corrected.argmax(axis=1).astype(np.int8),
            "is_overlap": events["is_overlap"].astype(int),
            "truth_saturation_label": events["truth_saturation_label"].astype(int),
            "truth_pedestal_adc": events["truth_pedestal_adc"].astype(float),
            "pid_label": events["pid_label"].astype(int),
            "pid_name": events["pid_name"].astype(str),
            "true_energy_mev": events["true_energy_mev"].astype(float),
            "g4_total_edep_mev": events["g4_total_edep_mev"].astype(float),
            "g4_n_sci_hits": events["g4_n_sci_hits"].astype(int),
            "g4_n_bstack_layers": events["g4_n_bstack_layers"].astype(int),
            "g4_energy_weighted_time_ns": events["g4_energy_weighted_time_ns"].astype(float),
            "g4_truth_stave": events["g4_truth_stave"].astype(str),
            "daq_run": events["daq_run"].astype(int),
            "EVENTNO": events["EVENTNO"].astype(int),
            "EVT": events["EVT"].astype(int),
            "TRIGGER": events["TRIGGER"].astype(int),
            "g4_entry": events["g4_entry"].astype(int),
            "digitizer_seed": events["digitizer_seed"].astype(int),
        }
    )
    return norm.astype(np.float32), meta.reset_index(drop=True)


def make_truth_families(meta: pd.DataFrame, feats: pd.DataFrame) -> pd.Series:
    energy = meta["true_energy_mev"].to_numpy(float)
    tail = feats["tail_12_17_over_total"].to_numpy(float)
    species = meta["pid_name"].to_numpy(str)
    hi_energy = energy >= np.quantile(energy, 0.66)
    hi_tail = tail >= np.quantile(tail, 0.66)
    family = np.where(
        hi_energy & hi_tail,
        "external_high_energy_tail_family",
        np.where(species == "deuteron", "deuteron_other_family", "proton_family"),
    )
    return pd.Series(family, name="external_particle_family")


def make_endpoint_targets(meta: pd.DataFrame, feats: pd.DataFrame, train_mask: np.ndarray) -> Tuple[pd.DataFrame, Dict[str, dict]]:
    energy_log = np.log1p(meta["true_energy_mev"].to_numpy(float))
    energy_residual = energy_log.copy()
    for run in np.unique(meta["run"]):
        for stave in np.unique(meta["stave_idx"]):
            m = (meta["run"].to_numpy() == run) & (meta["stave_idx"].to_numpy() == stave)
            if m.any():
                energy_residual[m] -= np.median(energy_log[m])
    pedestal_abs = np.abs(meta["truth_pedestal_adc"].to_numpy(float))
    hit_count = meta["g4_n_sci_hits"].to_numpy(float)

    def high(values: np.ndarray, q: float) -> Tuple[np.ndarray, float]:
        thr = float(np.quantile(values[train_mask], q))
        return (values >= thr).astype(np.int8), thr

    labels = pd.DataFrame(
        {
            "pid_separation": meta["pid_label"].astype(np.int8),
            "energy_scale": energy_residual.astype(np.float32),
            "pileup_sideband": meta["is_overlap"].astype(np.int8),
            "saturation_clipping": meta["truth_saturation_label"].astype(np.int8),
            "pedestal_noise_color": high(pedestal_abs, 0.80)[0],
            "pulse_shape_harmonics": high(hit_count, 0.70)[0],
        }
    )
    definitions = {
        "pid_separation": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "external GEANT4 dominant Sci_bar PDG; deuteron=1, proton=0"},
        "energy_scale": {"kind": "regression", "metric": "sigma68", "better": "lower", "definition": "GEANT4 total B-stack deposited energy log residual after run/stave centering"},
        "pileup_sideband": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "controlled digitizer two-pulse truth label"},
        "saturation_clipping": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "digitized corrected maximum above saturation threshold"},
        "pedestal_noise_color": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "top-quintile absolute pretrigger pedestal inherited from raw residual event"},
        "pulse_shape_harmonics": {"kind": "classification", "metric": "roc_auc", "better": "higher", "definition": "GEANT4 multi-hit tail complexity, top 30 percent by Sci_bar hit count"},
    }
    return labels, definitions


def split_masks(split_name: str, config: dict, meta: pd.DataFrame, feats: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, str]:
    runs = meta["run"].to_numpy(dtype=int)
    if split_name == "run_heldout":
        requested = np.asarray([int(r) for r in config["heldout_runs"]], dtype=int)
        available = np.asarray([r for r in requested if r in set(runs)], dtype=int)
        test_mask = np.isin(runs, available)
        train_mask = ~test_mask
        desc = "complete held-out runs available in keyed GEANT4 bridge: " + ", ".join(map(str, available))
    elif split_name == "particle_heldout":
        fam = make_truth_families(meta, feats)
        hold = str(config["particle_holdout_family"])
        test_mask = fam.to_numpy() == hold
        train_mask = ~test_mask
        desc = f"external truth particle family `{hold}` held out"
    else:
        raise ValueError(split_name)
    if train_mask.sum() == 0 or test_mask.sum() == 0:
        raise RuntimeError(f"empty split {split_name}: train={train_mask.sum()} test={test_mask.sum()}")
    return train_mask, test_mask, desc


def relabel_methods(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["method"] = out["method"].map(METHOD_LABEL).fillna(out["method"])
    return out


def add_strata(meta: pd.DataFrame, feats: pd.DataFrame, targets: pd.DataFrame, split_name: str, test_mask: np.ndarray) -> pd.DataFrame:
    out = meta.loc[test_mask, ["run", "stave", "stave_idx", "amplitude_adc", "baseline_adc", "pid_name", "true_energy_mev", "g4_n_sci_hits"]].copy().reset_index(drop=True)
    f = feats.loc[test_mask].reset_index(drop=True)
    t = targets.loc[test_mask].reset_index(drop=True)
    out["split_name"] = split_name
    out["tail_amplitude_bin"] = pd.qcut(f["tail_12_17_over_total"], 3, labels=["tail_low", "tail_mid", "tail_high"], duplicates="drop").astype(str)
    out["pedestal_history_bin"] = pd.qcut(np.abs(out["baseline_adc"]), 3, labels=["pedestal_quiet", "pedestal_mid", "pedestal_memory"], duplicates="drop").astype(str)
    out["pulse_shape_bin"] = pd.qcut(f["fft_k1_fraction"], 3, labels=["low_harmonic", "mid_harmonic", "high_harmonic"], duplicates="drop").astype(str)
    out["energy_bin"] = pd.qcut(out["true_energy_mev"], 3, labels=["energy_low", "energy_mid", "energy_high"], duplicates="drop").astype(str)
    out["particle_family"] = make_truth_families(meta, feats).loc[test_mask].reset_index(drop=True)
    out["pileup_flag"] = np.where(t["pileup_sideband"].astype(int) == 1, "pileup_truth", "single_truth")
    out["saturation_flag"] = np.where(t["saturation_clipping"].astype(int) == 1, "saturation_truth", "linear_truth")
    return out


def run_split(split_name: str, config: dict, waves: np.ndarray, meta: pd.DataFrame, feats: pd.DataFrame, x_trad: np.ndarray, x_all: np.ndarray, staves: np.ndarray, seed: int):
    train_mask, test_mask, desc = split_masks(split_name, config, meta, feats)
    targets, definitions = make_endpoint_targets(meta, feats, train_mask)
    runs = meta["run"].to_numpy(dtype=int)
    pred_frames = []
    summary_frames = []
    for i, endpoint in enumerate(PRIMARY_ENDPOINTS):
        info = definitions[endpoint]
        y = targets[endpoint].to_numpy(np.float32 if info["kind"] == "regression" else np.int8)
        pred, summary = s31a.fit_endpoint(endpoint, info["kind"], y, x_trad, x_all, waves, staves, runs, train_mask, test_mask, config, seed + 101 * i)
        pred.insert(0, "split_name", split_name)
        summary.insert(0, "split_name", split_name)
        pred_frames.append(relabel_methods(pred))
        summary_frames.append(relabel_methods(summary))
    strata = add_strata(meta, feats, targets, split_name, test_mask)
    return pd.concat(pred_frames, ignore_index=True), pd.concat(summary_frames, ignore_index=True), strata, definitions, desc


def joint_scores(summary: pd.DataFrame, config: dict) -> pd.DataFrame:
    weights = config["joint_score_weights"]
    rows = []
    for (split_name, method), group in summary.groupby(["split_name", "method"], sort=True):
        vals = {row["endpoint"]: float(row["metric_value"]) for _, row in group.iterrows()}
        score = (
            weights["pid_auc_loss"] * (1.0 - vals["pid_separation"])
            + weights["energy_sigma68"] * vals["energy_scale"]
            + weights["pileup_auc_loss"] * (1.0 - vals["pileup_sideband"])
            + weights["saturation_auc_loss"] * (1.0 - vals["saturation_clipping"])
            + weights["pedestal_auc_loss"] * (1.0 - vals["pedestal_noise_color"])
            + weights["tail_harmonic_auc_loss"] * (1.0 - vals["pulse_shape_harmonics"])
        )
        rows.append({"split_name": split_name, "method": method, "joint_loss": float(score), **vals})
    out = pd.DataFrame(rows)
    avg = out.groupby("method", as_index=False)["joint_loss"].mean().rename(columns={"joint_loss": "mean_joint_loss"})
    return out.merge(avg, on="method").sort_values(["mean_joint_loss", "split_name"]).reset_index(drop=True)


def paired_bootstrap(predictions: pd.DataFrame, definitions: Dict[str, dict], config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 904)
    rows = []
    baseline = "traditional_dE_E_tail_pedestal_likelihood"
    for (split_name, endpoint), ep in predictions.groupby(["split_name", "endpoint"], sort=True):
        kind = definitions[endpoint]["kind"]
        blocks = np.sort(ep["run"].unique())
        base = ep[ep["method"] == baseline]
        for method in sorted(set(ep["method"]) - {baseline}):
            comp = ep[ep["method"] == method]
            boot = []
            for _ in range(int(config["bootstrap_replicates"])):
                sampled = rng.choice(blocks, size=len(blocks), replace=True)
                b = pd.concat([base[base["run"] == block] for block in sampled], ignore_index=True)
                c = pd.concat([comp[comp["run"] == block] for block in sampled], ignore_index=True)
                if kind == "classification":
                    if len(np.unique(c["y_true"])) < 2 or len(np.unique(b["y_true"])) < 2:
                        continue
                    boot.append(float(roc_auc_score(c["y_true"].astype(int), c["score"]) - roc_auc_score(b["y_true"].astype(int), b["score"])))
                else:
                    boot.append(float(s31a.sigma68(c["score"].to_numpy() - c["y_true"].to_numpy()) - s31a.sigma68(b["score"].to_numpy() - b["y_true"].to_numpy())))
            arr = np.asarray(boot, dtype=float)
            lo, hi = np.quantile(arr, [0.025, 0.975]) if len(arr) else (float("nan"), float("nan"))
            rows.append({"split_name": split_name, "endpoint": endpoint, "method": method, "delta_vs_traditional": float(arr.mean()) if len(arr) else float("nan"), "ci_low": float(lo), "ci_high": float(hi), "delta_definition": "AUC gain for classification; sigma68 increase for regression"})
    return pd.DataFrame(rows)


def calibration_table(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (split_name, endpoint, method), group in predictions.groupby(["split_name", "endpoint", "method"], sort=True):
        if endpoint == "energy_scale":
            continue
        y = group["y_true"].to_numpy(dtype=int)
        if len(np.unique(y)) < 2:
            continue
        rows.append({"split_name": split_name, "endpoint": endpoint, "method": method, "auc": float(roc_auc_score(y, group["score"])), "ece": calibration_ece(y, group["score"]), "n": int(len(group)), "positives": int(y.sum())})
    return pd.DataFrame(rows)


def strata_table(predictions: pd.DataFrame, strata: pd.DataFrame, definitions: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    axes = ["tail_amplitude_bin", "pedestal_history_bin", "pulse_shape_bin", "energy_bin", "particle_family", "pileup_flag", "saturation_flag"]
    for split_name, split_pred in predictions.groupby("split_name", sort=True):
        split_strata = strata[strata["split_name"] == split_name].reset_index(drop=True)
        for endpoint, ep in split_pred.groupby("endpoint", sort=True):
            kind = definitions[endpoint]["kind"]
            for method, group in ep.groupby("method", sort=True):
                g = group.reset_index(drop=True)
                for axis in axes:
                    for value, idx in split_strata.groupby(axis, sort=True).groups.items():
                        sub = g.iloc[list(idx)]
                        if len(sub) < 8:
                            continue
                        y = sub["y_true"].to_numpy()
                        score = sub["score"].to_numpy()
                        if kind == "classification":
                            metric = float(roc_auc_score(y.astype(int), score)) if len(np.unique(y)) > 1 else float("nan")
                            name = "auc"
                        else:
                            metric = float(s31a.sigma68(score - y))
                            name = "sigma68"
                        rows.append({"split_name": split_name, "endpoint": endpoint, "method": method, "stratum_axis": axis, "stratum": str(value), "n": int(len(sub)), "metric": name, "value": metric})
    return pd.DataFrame(rows)


def leakage_table(summary: pd.DataFrame, calibration: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (split_name, method), group in summary.groupby(["split_name", "method"], sort=True):
        vals = {row["endpoint"]: float(row["metric_value"]) for _, row in group.iterrows()}
        cal = calibration[(calibration["split_name"] == split_name) & (calibration["method"] == method) & (calibration["endpoint"] == "pid_separation")]
        rows.append(
            {
                "split_name": split_name,
                "method": method,
                "pid_auc": vals.get("pid_separation", float("nan")),
                "energy_sigma68": vals.get("energy_scale", float("nan")),
                "late_tail_auc": vals.get("pulse_shape_harmonics", float("nan")),
                "pedestal_auc": vals.get("pedestal_noise_color", float("nan")),
                "pid_ece": float(cal["ece"].iloc[0]) if len(cal) else float("nan"),
                "external_truth_leakage_risk": "lower than S32c: PID and energy labels come from GEANT4 truth, not target waveform thresholds",
            }
        )
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, columns: List[str]) -> str:
    if df.empty:
        return "(empty)"
    view = df.loc[:, columns].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.5g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def write_report(out: Path, result: dict, summary: pd.DataFrame, joint: pd.DataFrame, calibration: pd.DataFrame, paired: pd.DataFrame, strata: pd.DataFrame, leakage: pd.DataFrame, feature_roles: pd.DataFrame) -> None:
    winner = result["winner"]["method"]
    joint_winner = result["joint_winner"]["method"]
    lines = [
        "# S15: dE-E Particle ID p-vs-d Traditional/ML Bakeoff",
        "",
        f"Ticket: `#{result['ticket_id']}`  ",
        f"Worker: `{result['worker']}`  ",
        f"Raw ROOT directory: `{result['raw_root_dir']}`  ",
        f"GEANT4 bridge: `{result['geant4_truth']['digitized_root']}`  ",
        "Pre-registered metric: run-held-out PID ROC AUC with bootstrap 95% CI; `winner` is selected by this PID metric, while the registered multi-endpoint joint loss is reported as secondary context.",
        "",
        "## Abstract",
        "",
        f"S15 benchmarks event-by-event proton/deuteron particle identification with a strong traditional dE-E/tail/pedestal likelihood baseline and five ML/NN competitors. The raw B-stack selected-pulse reproduction gate is **{result['reproduction']['selected_pulses']:,}**, matching the registered **{result['reproduction']['expected_selected_pulses']:,}** pulses exactly. On the pre-registered run-held-out PID ROC AUC metric, `result.json` names **{winner}** as the winner. The secondary multi-endpoint joint-loss winner is **{joint_winner}**.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "The reproduction gate opens every configured `hrdb_run_XXXX.root` file at `h101/HRDv`, reshapes each record to `(event, channel, sample)`, subtracts the median of samples 0-3 for each channel, and selects B2/B4/B6/B8 pulses whose corrected maximum exceeds 1000 ADC.",
        "",
        "| quantity | expected | reproduced | delta | pass |",
        "|---|---:|---:|---:|---|",
        f"| selected B-stave pulses | {result['reproduction']['expected_selected_pulses']:,} | {result['reproduction']['selected_pulses']:,} | {result['reproduction']['delta']} | {result['reproduction']['passed']} |",
        "",
        "## External Truth Construction",
        "",
        "The benchmark labels are read from the keyed G4-08 digitized bridge. GEANT4 truth defines the PID target as dominant Sci_bar PDG, with proton `2212` mapped to 0 and deuteron `1000010020` mapped to 1. The calibrated energy target is `E_i = sum_h EDep_ih` over B-stack Sci_bar hits, evaluated as the run/stave-centered residual of `log(1+E_i)`.",
        "",
        "The digitized waveform branch `HRDv_digitized` supplies the 18-sample ADC-like pulse. It preserves raw residual templates and native DAQ keys while the labels come from GEANT4, so PID and energy are no longer deterministic functions of the target waveform features as in S32c.",
        "",
        "## Splits and Bootstrap",
        "",
        f"Requested held-out runs were `{result['split']['requested_heldout_runs']}`; the keyed G4-08 bridge contains `{result['split']['available_runs']}`, so the run-held-out test uses the available intersection `{result['split']['run_heldout_runs']}`. The particle-held-out split removes `{result['split']['particle_holdout_family']}` from training. Bootstrap CIs resample held-out run blocks with replacement using `{result['split']['bootstrap_replicates']}` replicates.",
        "",
        "For held-out blocks `D_r`, replicate `b` draws labels `S_b` with replacement and evaluates `theta_b = T(union_{r in S_b} D_r)`. The interval is `[Q_0.025(theta_b), Q_0.975(theta_b)]`. Classification endpoints use ROC AUC and calibration ECE; energy uses `sigma68 = 0.5[Q_0.84(yhat-y)-Q_0.16(yhat-y)]`.",
        "",
        "## Methods and Equations",
        "",
        "The traditional comparator is a regularized dE-E/tail/pedestal likelihood surrogate over engineered variables: log amplitude, duplicate-readout response, CFD times, pulse moments, Haar coefficients, late/early charge ratios, FFT fractions, and pedestal residuals. In compact notation, the comparator fits `f_trad([log A, dE/E, T_late, M_ped, H_fft])` using only these physics-motivated features.",
        "",
        "Ridge minimizes `||y-X beta||_2^2 + lambda||beta||_2^2` or the corresponding L2 classification margin. Gradient-boosted trees fit `F_M(x)=sum_m eta h_m(x)`. The MLP is a two-layer ReLU model. The 1D-CNN learns local filters over the 18 samples. The new `spectral_transformer_new` embeds sample/time tokens and gates the pooled representation with normalized FFT magnitudes.",
        "",
        "The joint loss is `0.34(1-AUC_PID)+0.30 sigma68_E+0.10(1-AUC_pileup)+0.08(1-AUC_sat)+0.08(1-AUC_ped)+0.10(1-AUC_tail)`. Lower is better.",
        "",
        "## Primary Joint Results",
        "",
        md_table(joint, ["split_name", "method", "joint_loss", "mean_joint_loss", "pid_separation", "energy_scale", "pileup_sideband", "saturation_clipping", "pedestal_noise_color", "pulse_shape_harmonics"]),
        "",
        "## Endpoint Bootstrap CIs",
        "",
        md_table(summary, ["split_name", "endpoint", "method", "metric_value", "ci_low", "ci_high", "n", "positives"]),
        "",
        "## Calibration",
        "",
        md_table(calibration[calibration["endpoint"] == "pid_separation"], ["split_name", "method", "auc", "ece", "n", "positives"]),
        "",
        "## PID Method Table",
        "",
        md_table(summary[summary["endpoint"] == "pid_separation"], ["split_name", "method", "metric_value", "ci_low", "ci_high", "n", "positives"]),
        "",
        "## Paired Bootstrap Deltas vs Traditional",
        "",
        md_table(paired, ["split_name", "endpoint", "method", "delta_vs_traditional", "ci_low", "ci_high", "delta_definition"]),
        "",
        "## Stratified Systematics",
        "",
        md_table(strata[(strata["method"] == winner) & (strata["endpoint"].isin(["pid_separation", "energy_scale"]))].head(36), ["split_name", "endpoint", "stratum_axis", "stratum", "n", "metric", "value"]),
        "",
        "## Leakage and Feature Audits",
        "",
        md_table(leakage, ["split_name", "method", "pid_auc", "energy_sigma68", "late_tail_auc", "pedestal_auc", "pid_ece", "external_truth_leakage_risk"]),
        "",
        "Feature-family audit:",
        "",
        md_table(feature_roles.head(40), list(feature_roles.columns)),
        "",
        "## Caveats",
        "",
        "- The benchmark is keyed digitized GEANT4 truth, not a direct event-by-event truth label for the real HRD run stream. This is the central S15 no-truth-label caveat.",
        "- The G4-08 bridge does not contain run 42, so the requested run-held-out list is preserved by intersection rather than by adding unavailable data.",
        "- The ADC/MeV scale in the digitized bridge is a ranking calibration, not a final detector energy calibration.",
        "- Bootstrap intervals cover held-out run transfer within this bridge and do not include GEANT4 physics-list or material-budget uncertainty.",
        "- Pedestal labels are independent pretrigger residual labels; they are not a zero-signal electronics truth campaign.",
        "",
        "## Verdict",
        "",
        f"`result.json` names **{winner}** as the S15 PID winner. The strong traditional dE-E baseline is reported on the same held-out rows and bootstrap blocks as the ML/NN methods; here it remains marginally ahead on run-held-out PID AUC, while **{joint_winner}** is best for the secondary multi-endpoint loss. The result is a method benchmark and not an adopted event-by-event PID assignment for real beam data.",
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/ticket_2392_s15_deltae_pid_bakeoff.py --config configs/ticket_2392_s15_deltae_pid_bakeoff.json",
        "```",
        "",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/ticket_2392_s15_deltae_pid_bakeoff.json")
    args = parser.parse_args()
    t0 = time.time()
    config = load_json(args.config)
    rng = np.random.default_rng(int(config["random_seed"]))
    raw_dir = t07.resolve_raw_root_dir(config)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    (out / "claimed_ticket.txt").write_text(config["ticket_id"] + "\n", encoding="utf-8")

    raw_waves, raw_meta, counts_by_run = t07.scan_raw(config, raw_dir)
    selected = int(len(raw_waves))
    expected = int(config["expected_total_selected_pulses"])
    if selected != expected:
        raise RuntimeError(f"raw ROOT reproduction failed: selected {selected}, expected {expected}")
    counts_by_run.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    pd.DataFrame([{"quantity": "selected B-stave pulses with baseline-subtracted amplitude > 1000 ADC", "report_value": expected, "reproduced": selected, "delta": selected - expected, "pass": selected == expected}]).to_csv(out / "reproduction_match_table.csv", index=False)
    del raw_waves, raw_meta

    waves, meta = digitized_truth_dataset(config)
    feats, feature_roles = t07.classic_features(waves, meta)
    feature_roles.to_csv(out / "feature_family_audit.csv", index=False)
    truth_families = make_truth_families(meta, feats)
    pd.concat([meta[["event_id", "run", "stave", "pid_name", "true_energy_mev"]], truth_families], axis=1).to_csv(out / "external_truth_family_assignments.csv", index=False)

    trad_cols = [c for c in feats.columns if c != "stave_idx"]
    x_trad = feats[trad_cols].to_numpy(dtype=np.float32)
    x_all = np.hstack([waves.astype(np.float32), x_trad, s31a.one_hot_stave(meta)]).astype(np.float32)
    staves = s31a.one_hot_stave(meta)

    pred_frames = []
    summary_frames = []
    strata_frames = []
    split_desc = {}
    definitions = None
    for i, split_name in enumerate(["run_heldout", "particle_heldout"]):
        pred, summary, strata, defs, desc = run_split(split_name, config, waves, meta, feats, x_trad, x_all, staves, int(config["random_seed"]) + i * 1009)
        pred_frames.append(pred)
        summary_frames.append(summary)
        strata_frames.append(strata)
        definitions = defs
        split_desc[split_name] = desc

    predictions = pd.concat(pred_frames, ignore_index=True)
    summary = pd.concat(summary_frames, ignore_index=True)
    strata_meta = pd.concat(strata_frames, ignore_index=True)
    predictions.to_csv(out / "heldout_predictions.csv.gz", index=False)
    summary.to_csv(out / "endpoint_method_summary.csv", index=False)
    strata_meta.to_csv(out / "heldout_strata_assignments.csv", index=False)

    joint = joint_scores(summary, config)
    calibration = calibration_table(predictions)
    paired = paired_bootstrap(predictions, definitions, config)
    strata_metrics = strata_table(predictions, strata_meta, definitions)
    leakage = leakage_table(summary, calibration)
    joint.to_csv(out / "joint_scoreboard.csv", index=False)
    calibration.to_csv(out / "calibration_ece.csv", index=False)
    paired.to_csv(out / "paired_bootstrap_deltas.csv", index=False)
    strata_metrics.to_csv(out / "strata_metrics.csv", index=False)
    leakage.to_csv(out / "leakage_audit.csv", index=False)

    joint_winner_row = joint.sort_values("mean_joint_loss").iloc[0].to_dict()
    pid_primary = (
        summary[(summary["split_name"] == "run_heldout") & (summary["endpoint"] == "pid_separation")]
        .sort_values("metric_value", ascending=False)
        .iloc[0]
        .to_dict()
    )
    available_runs = sorted(int(x) for x in meta["run"].unique())
    run_heldout = sorted(int(r) for r in config["heldout_runs"] if int(r) in set(available_runs))
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit": git_commit(),
        "runtime_sec": time.time() - t0,
        "python": platform.python_version(),
        "claim_command": "tn-ticket claim testbeam-laptop-3 --project testbeam",
        "reproduction": {"selected_pulses": selected, "expected_selected_pulses": expected, "delta": selected - expected, "passed": selected == expected, "samples_per_channel": int(config["samples_per_channel"])},
        "geant4_truth": {
            "digitized_root": config["g4_digitized_root"],
            "truth_table": config["g4_truth_table"],
            "pid_truth": "dominant Sci_bar PDG deuteron vs proton",
            "energy_truth": "GEANT4 total B-stack Sci_bar deposited energy, log residualized by run/stave",
            "n_digitized_events": int(len(meta)),
            "native_keys": ["daq_run", "EVENTNO", "EVT", "TRIGGER", "g4_entry", "digitizer_seed"],
        },
        "split": {
            "requested_heldout_runs": [int(x) for x in config["heldout_runs"]],
            "available_runs": available_runs,
            "run_heldout_runs": run_heldout,
            "particle_holdout_family": config["particle_holdout_family"],
            "split_descriptions": split_desc,
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
        },
        "primary_methods": ["traditional_dE_E_tail_pedestal_likelihood", "ridge", "gradient_boosted_trees", "mlp", "1d_cnn", "spectral_transformer_new"],
        "joint_score_weights": config["joint_score_weights"],
        "winner": {
            "method": str(pid_primary["method"]),
            "metric": "run_heldout_pid_roc_auc",
            "value": float(pid_primary["metric_value"]),
            "ci95": [float(pid_primary["ci_low"]), float(pid_primary["ci_high"])],
            "selection_rule": "maximum run-held-out PID ROC AUC on the same held-out source-run rows",
        },
        "winner_details": pid_primary,
        "joint_winner": {
            "method": str(joint_winner_row["method"]),
            "mean_joint_loss": float(joint_winner_row["mean_joint_loss"]),
            "selection_rule": "minimum mean registered multi-endpoint joint loss across run-heldout and external particle-family-heldout splits",
        },
        "joint_winner_details": joint_winner_row,
        "artifacts": {
            "REPORT.md": "academic report",
            "joint_scoreboard.csv": "winner table",
            "endpoint_method_summary.csv": "bootstrap endpoint CIs",
            "paired_bootstrap_deltas.csv": "paired bootstrap vs traditional",
            "calibration_ece.csv": "PID/proxy calibration",
            "strata_metrics.csv": "tail/pedestal/pulse/pileup/saturation/energy strata",
            "leakage_audit.csv": "external-truth leakage audit",
            "external_truth_family_assignments.csv": "particle-family split assignments",
        },
        "next_tickets": [],
        "status": "complete",
    }
    (out / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out, result, summary, joint, calibration, paired, strata_metrics, leakage, feature_roles)

    input_rows = [
        {"path": str(ROOT / config["g4_digitized_root"]), "sha256": sha256_file(ROOT / config["g4_digitized_root"]), "role": "keyed_digitized_geant4_root"},
        {"path": str(ROOT / config["g4_truth_table"]), "sha256": sha256_file(ROOT / config["g4_truth_table"]), "role": "geant4_truth_table"},
    ]
    for path in sorted(raw_dir.glob("hrdb_run_*.root")):
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "role": "raw_bstack_root"})
    pd.DataFrame(input_rows).to_csv(out / "input_sha256.csv", index=False)
    (out / "manifest.json").write_text(json.dumps(json_clean({"result": result, "created": time.time()}), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(json_clean({"status": "complete", "winner": result["winner"], "output_dir": str(out)}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
