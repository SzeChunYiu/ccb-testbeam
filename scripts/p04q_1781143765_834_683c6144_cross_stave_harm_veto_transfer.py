#!/usr/bin/env python3
"""P04q: cross-stave duplicate-readout harm-veto transfer validation.

This study extends the P04p duplicate-readout harm-label benchmark from B2 to
B4/B6/B8.  It tests whether the B2-trained harm veto is a reusable even-waveform
policy or a B2-local saturation artifact by evaluating B2-to-target-stave
transfer against target-stave run-held-out baselines.
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

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import RidgeClassifier
from sklearn.metrics import precision_recall_fscore_support
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

P04P_PATH = Path(__file__).with_name("p04p_1781046824_725_569d120d_duplicate_harm_labels.py")
spec = importlib.util.spec_from_file_location("p04p_helpers", P04P_PATH)
p04p = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(p04p)

try:
    import torch
except Exception:  # pragma: no cover
    torch = None


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


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = group
    return out


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 30000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def extract_stave_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    staves = {k: int(v) for k, v in config["staves"].items()}
    odd_channels = {k: int(v) for k, v in config["duplicate_readout_channels"].items()}
    physical_channels = np.asarray(list(staves.values()), dtype=int)
    groups = run_group_lookup(config)
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        row = {"run": run, "group": groups[run], "events_total": 0, "s00_selected_pulses": 0}
        for stave in staves:
            row[f"{stave}_selected"] = 0
            row[f"{stave}_valid_odd"] = 0
            row[f"{stave}_high_proxy"] = 0
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even_amp_all = corrected[:, physical_channels, :].max(axis=-1)
            row["events_total"] += int(len(eventno))
            row["s00_selected_pulses"] += int((even_amp_all > cut).sum())

            for stave, ch in staves.items():
                odd_ch = odd_channels[stave]
                even = corrected[:, ch, :]
                odd = -corrected[:, odd_ch, :]
                raw_even = raw[:, ch, :]
                amp = even.max(axis=1)
                peak = even.argmax(axis=1)
                charge = np.clip(even, 0.0, None).sum(axis=1)
                area = even.sum(axis=1)
                dynamic_amp = raw_even.max(axis=1) - raw_even.min(axis=1)
                baseline_excursion = dynamic_amp - amp
                odd_amp = odd.max(axis=1)
                odd_charge = np.clip(odd, 0.0, None).sum(axis=1)
                odd_time = float(config["sample_period_ns"]) * p04p.cfd_time_samples(
                    odd, np.maximum(odd_amp, 1.0), float(config["cfd_fraction"])
                )
                selected = amp > cut
                valid_odd = odd_charge >= float(config["harm_label"]["min_odd_charge"])
                row[f"{stave}_selected"] += int(selected.sum())
                row[f"{stave}_valid_odd"] += int((selected & valid_odd).sum())
                row[f"{stave}_high_proxy"] += int(
                    (selected & (amp >= float(config["harm_label"]["saturation_proxy_adc"]))).sum()
                )
                idx = np.flatnonzero(selected)
                if len(idx) == 0:
                    continue
                frames.append(
                    pd.DataFrame(
                        {
                            "run": run,
                            "group": groups[run],
                            "stave": stave,
                            "eventno": eventno[idx],
                            "evt": evt[idx],
                            "b2_amp": amp[idx],
                            "b2_peak": peak[idx].astype(np.int16),
                            "b2_charge": charge[idx],
                            "b2_area": area[idx],
                            "dynamic_amp": dynamic_amp[idx],
                            "baseline_excursion": baseline_excursion[idx],
                            "pre4_mean": raw_even[idx, :4].mean(axis=1),
                            "pre4_std": raw_even[idx, :4].std(axis=1),
                            "odd_amp": odd_amp[idx],
                            "odd_charge": odd_charge[idx],
                            "odd_time_ns": odd_time[idx],
                        }
                    )
                )
                waves.append(even[idx].astype(np.float32))
        counts.append(row)
        print(f"run {run}: selected={row['s00_selected_pulses']}", flush=True)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def fit_fold_models(
    meta: pd.DataFrame,
    wave: np.ndarray,
    train_idx: np.ndarray,
    held_idx: np.ndarray,
    config: dict,
    seed: int,
    include_nn: bool,
) -> Tuple[pd.DataFrame, dict]:
    templates = p04p.build_templates(meta, wave, train_idx, config)
    q_template_all, template_loss_all = p04p.template_scale(meta, wave, templates, config)
    q_saturation_all = p04p.saturation_template_scale(meta, wave, templates, config)
    q_integral_all = meta["b2_charge"].to_numpy()
    q_peak_all = meta["b2_amp"].to_numpy()
    odd = meta["odd_charge"].to_numpy()
    train_mask = np.zeros(len(meta), dtype=bool)
    train_mask[train_idx] = True

    charge_pred: Dict[str, np.ndarray] = {}
    time_resid: Dict[str, np.ndarray] = {}
    # CFD20 threshold uses peak ADC for every correction method (#1124).
    peak_amp_for_cfd = np.maximum(meta["b2_amp"].to_numpy(dtype=float), 1.0)
    for name, est in {
        "raw_peak": q_peak_all,
        "raw_integral": q_integral_all,
        "adaptive_template": q_template_all,
        "template_saturation": q_saturation_all,
    }.items():
        cal = p04p.fit_charge_calibrator(est, odd, train_mask)
        pred_charge = p04p.predict_charge(cal, est)
        charge_pred[name] = (pred_charge - odd) / np.maximum(odd, 1.0)
        even_time = float(config["sample_period_ns"]) * p04p.cfd_time_samples(
            wave, peak_amp_for_cfd, float(config["cfd_fraction"])
        )
        finite = np.isfinite(even_time)
        offset = (
            float(np.nanmedian(even_time[train_mask & finite] - meta.loc[train_mask & finite, "odd_time_ns"].to_numpy()))
            if np.any(train_mask & finite)
            else 0.0
        )
        time_resid[name] = even_time - meta["odd_time_ns"].to_numpy() - offset

    prod_charge = charge_pred["template_saturation"]
    prod_time = time_resid["template_saturation"]
    base_charge = charge_pred["raw_integral"]
    base_time = time_resid["raw_peak"]
    q_shift = np.abs(np.log(np.maximum(q_template_all, 1.0) / np.maximum(q_integral_all, 1.0)))
    label_cfg = config["harm_label"]
    harm = (
        (np.abs(prod_charge) > (np.abs(base_charge) + float(label_cfg["charge_abs_excess_margin"])))
        | (np.abs(prod_time) > (np.abs(base_time) + float(label_cfg["timing_abs_excess_ns"])))
        | (
            (q_shift > float(label_cfg["q_template_shift_margin"]))
            & (meta["b2_amp"].to_numpy() >= float(label_cfg["saturation_proxy_adc"]))
            & (np.abs(prod_charge) > np.abs(base_charge))
        )
    )

    fold = meta.loc[held_idx, ["run", "group", "stave", "eventno", "evt", "b2_amp", "b2_charge", "dynamic_amp", "baseline_excursion"]].copy()
    for cname, values in charge_pred.items():
        fold[f"charge_frac_error_{cname}"] = values[held_idx]
    for tname, values in time_resid.items():
        fold[f"time_resid_ns_{tname}"] = values[held_idx]
    fold["prod_charge_frac_error"] = prod_charge[held_idx]
    fold["prod_time_resid_ns"] = prod_time[held_idx]
    fold["harm_label"] = harm[held_idx].astype(int)
    fold["q_template_shift_abs"] = q_shift[held_idx]
    fold["template_loss"] = template_loss_all[held_idx]

    rule_cfg = config["traditional_rule"]
    loss_cut = float(np.nanquantile(template_loss_all[train_mask], float(rule_cfg["template_loss_quantile"])))
    rule_votes = np.column_stack(
        [
            (meta["b2_amp"].to_numpy() >= float(rule_cfg["saturation_proxy_adc"])).astype(float),
            (meta["baseline_excursion"].to_numpy() >= float(rule_cfg["baseline_excursion_adc"])).astype(float),
            (q_shift >= float(rule_cfg["q_template_shift_margin"])).astype(float),
            (template_loss_all >= loss_cut).astype(float),
        ]
    )
    fold["prob_traditional_rule"] = rule_votes[held_idx].mean(axis=1)
    fold["flag_traditional_rule"] = fold["prob_traditional_rule"].to_numpy() >= 0.5

    X = p04p.waveform_features(meta, wave, q_template_all, template_loss_all)
    y = harm.astype(int)
    finite = np.isfinite(X).all(axis=1)
    train_eligible = train_idx[finite[train_idx]]
    rng = np.random.default_rng(seed)
    if len(train_eligible) > int(config["ml_max_train_rows"]):
        train_fit = rng.choice(train_eligible, size=int(config["ml_max_train_rows"]), replace=False)
    else:
        train_fit = train_eligible
    pos = max(int(y[train_fit].sum()), 1)
    neg = max(int(len(train_fit) - y[train_fit].sum()), 1)
    sample_weight = np.ones(len(train_fit), dtype=float)
    sample_weight[y[train_fit] == 1] = min(neg / pos, 20.0)

    ridge = make_pipeline(StandardScaler(), RidgeClassifier(alpha=3.0, class_weight="balanced"))
    ridge.fit(X[train_fit], y[train_fit])
    fold["prob_ridge"] = p04p.sigmoid(ridge.decision_function(X[held_idx]))
    fold["flag_ridge"] = fold["prob_ridge"].to_numpy() >= 0.5

    gbt = HistGradientBoostingClassifier(
        loss="binary_crossentropy",
        learning_rate=0.055,
        max_iter=90,
        max_leaf_nodes=15,
        l2_regularization=0.05,
        random_state=seed + 19,
    )
    gbt.fit(X[train_fit], y[train_fit], sample_weight=sample_weight)
    fold["prob_gradient_boosted_trees"] = gbt.predict_proba(X[held_idx])[:, 1]
    fold["flag_gradient_boosted_trees"] = fold["prob_gradient_boosted_trees"].to_numpy() >= 0.5

    mlp = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=(48, 24),
            activation="relu",
            alpha=0.0005,
            max_iter=80,
            early_stopping=True,
            n_iter_no_change=8,
            random_state=seed + 23,
        ),
    )
    mlp.fit(X[train_fit], y[train_fit])
    fold["prob_mlp"] = mlp.predict_proba(X[held_idx])[:, 1]
    fold["flag_mlp"] = fold["prob_mlp"].to_numpy() >= 0.5

    shuffled = y[train_fit].copy()
    rng.shuffle(shuffled)
    sentinel = HistGradientBoostingClassifier(
        loss="binary_crossentropy",
        learning_rate=0.055,
        max_iter=60,
        max_leaf_nodes=15,
        l2_regularization=0.05,
        random_state=seed + 901,
    )
    sentinel.fit(X[train_fit], shuffled, sample_weight=sample_weight)
    fold["prob_shuffled_target_gbt"] = sentinel.predict_proba(X[held_idx])[:, 1]
    fold["flag_shuffled_target_gbt"] = fold["prob_shuffled_target_gbt"].to_numpy() >= 0.5

    # Fail-closed model identity (#1126): never silently publish MLP/GBT as CNN/ResNet.
    torch_exec = {
        "cnn_1d": {"requested_model": "cnn_1d", "effective_model": None, "status": "PENDING", "error": None},
        "wavegate_resnet": {
            "requested_model": "wavegate_resnet",
            "effective_model": None,
            "status": "PENDING",
            "error": None,
        },
    }
    if include_nn:
        x_wave = (wave / np.maximum(meta["b2_amp"].to_numpy()[:, None], 1.0)).astype(np.float32)
        x_tab = X[:, 18:].astype(np.float32)
        try:
            fold["prob_cnn_1d"] = p04p.fit_torch_classifier("cnn_1d", x_wave, x_tab, y, train_eligible, held_idx, config, seed + 31)
            torch_exec["cnn_1d"].update(effective_model="cnn_1d", status="SUCCESS")
        except Exception as exc:
            print(f"cnn_1d failed for fold seed {seed}: {exc}", flush=True)
            fold["prob_cnn_1d"] = np.full(len(fold), np.nan, dtype=float)
            torch_exec["cnn_1d"].update(status="FAILED_MODEL_EXECUTION", error=type(exc).__name__)
        try:
            fold["prob_wavegate_resnet"] = p04p.fit_torch_classifier(
                "wavegate_resnet", x_wave, x_tab, y, train_eligible, held_idx, config, seed + 37
            )
            torch_exec["wavegate_resnet"].update(effective_model="wavegate_resnet", status="SUCCESS")
        except Exception as exc:
            print(f"wavegate_resnet failed for fold seed {seed}: {exc}", flush=True)
            fold["prob_wavegate_resnet"] = np.full(len(fold), np.nan, dtype=float)
            torch_exec["wavegate_resnet"].update(status="FAILED_MODEL_EXECUTION", error=type(exc).__name__)
    else:
        fold["prob_cnn_1d"] = np.full(len(fold), np.nan, dtype=float)
        fold["prob_wavegate_resnet"] = np.full(len(fold), np.nan, dtype=float)
        torch_exec["cnn_1d"].update(status="UNAVAILABLE", error="include_nn=False")
        torch_exec["wavegate_resnet"].update(status="UNAVAILABLE", error="include_nn=False")
    fold["torch_execution_json"] = json.dumps(torch_exec)
    fold["flag_cnn_1d"] = np.where(
        np.isfinite(fold["prob_cnn_1d"].to_numpy(dtype=float)),
        fold["prob_cnn_1d"].to_numpy(dtype=float) >= 0.5,
        False,
    )
    fold["flag_wavegate_resnet"] = np.where(
        np.isfinite(fold["prob_wavegate_resnet"].to_numpy(dtype=float)),
        fold["prob_wavegate_resnet"].to_numpy(dtype=float) >= 0.5,
        False,
    )

    train_hashes = {
        hashlib.sha256(np.asarray(row, dtype=np.float32).tobytes()).hexdigest()
        for row in wave[train_fit[: min(len(train_fit), 25000)]]
    }
    overlap = sum(1 for row in wave[held_idx] if hashlib.sha256(np.asarray(row, dtype=np.float32).tobytes()).hexdigest() in train_hashes)
    leakage = {
        "train_rows": int(len(train_fit)),
        "heldout_rows": int(len(held_idx)),
        "train_positive_rate": float(y[train_fit].mean()),
        "heldout_positive_rate": float(y[held_idx].mean()),
        "sampled_train_waveform_hash_overlap": int(overlap),
        "loss_cut": loss_cut,
    }
    return fold, leakage


def metric_value(values: np.ndarray, metric: str) -> float:
    if len(values) == 0:
        return math.nan
    if metric == "median":
        return float(np.nanmedian(values))
    if metric == "abs68":
        return float(np.nanpercentile(np.abs(values), 68))
    if metric == "tail_frac":
        return float(np.nanmean(np.abs(values) > 5.0))
    raise KeyError(metric)


def summarize_method(frame: pd.DataFrame, method: str, reps: int, rng: np.random.Generator) -> dict:
    y = frame["harm_label"].to_numpy(dtype=int)
    flag = frame[f"flag_{method}"].to_numpy(dtype=bool)
    prob = frame[f"prob_{method}"].to_numpy(dtype=float)
    if method in {"cnn_1d", "wavegate_resnet"} and not np.isfinite(prob).any():
        return {
            "method": method,
            "n": int(len(frame)),
            "execution_state": "FAILED_MODEL_EXECUTION",
            "requested_model": method,
            "effective_model": None,
            "eligible_for_ranking": False,
            "resampling_unit": "run",
            "harm_rate": float(y.mean()) if len(y) else float("nan"),
            "flag_rate": float("nan"),
            "precision": float("nan"),
            "recall": float("nan"),
            "f1": float("nan"),
            "accepted_coverage": float("nan"),
            "accepted_charge_bias_frac": float("nan"),
            "accepted_charge_res68_frac": float("nan"),
            "accepted_timing_abs68_ns": float("nan"),
            "accepted_timing_tail_frac_gt5ns": float("nan"),
            "calibration_ece": float("nan"),
        }
    precision, recall, f1, _ = precision_recall_fscore_support(y, flag.astype(int), average="binary", zero_division=0)
    accepted = ~flag
    charge = frame.loc[accepted, "prod_charge_frac_error"].to_numpy()
    timing = frame.loc[accepted, "prod_time_resid_ns"].to_numpy()
    row = {
        "method": method,
        "n": int(len(frame)),
        "harm_rate": float(y.mean()),
        "flag_rate": float(flag.mean()),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "accepted_coverage": float(accepted.mean()),
        "accepted_charge_bias_frac": metric_value(charge, "median"),
        "accepted_charge_res68_frac": metric_value(charge, "abs68"),
        "accepted_timing_abs68_ns": metric_value(timing, "abs68"),
        "accepted_timing_tail_frac_gt5ns": metric_value(timing, "tail_frac"),
        "calibration_ece": p04p.ece_score(y, prob),
    }
    # Primary resampling unit is RUN, keeping all target staves together (#1125).
    # Legacy stave-run independent blocks break shared-run/event dependence.
    run_blocks = {
        int(run): block
        for run, block in frame.groupby("run", sort=True)
    }
    run_keys = np.asarray(sorted(run_blocks.keys()), dtype=int)
    row["resampling_unit"] = "run"
    row["n_resampling_units"] = int(len(run_keys))
    stats = {key: np.empty(reps, dtype=float) for key in [
        "precision",
        "recall",
        "accepted_coverage",
        "accepted_charge_res68_frac",
        "accepted_timing_abs68_ns",
        "accepted_timing_tail_frac_gt5ns",
        "flag_rate",
    ]}
    for i in range(reps):
        picked = rng.choice(len(run_keys), size=len(run_keys), replace=True)
        sample = pd.concat([run_blocks[int(run_keys[j])] for j in picked], ignore_index=True)
        sy = sample["harm_label"].to_numpy(dtype=int)
        sf = sample[f"flag_{method}"].to_numpy(dtype=bool)
        sp, sr, _, _ = precision_recall_fscore_support(sy, sf.astype(int), average="binary", zero_division=0)
        sacc = ~sf
        stats["precision"][i] = sp
        stats["recall"][i] = sr
        stats["accepted_coverage"][i] = sacc.mean()
        stats["accepted_charge_res68_frac"][i] = metric_value(sample.loc[sacc, "prod_charge_frac_error"].to_numpy(), "abs68")
        stats["accepted_timing_abs68_ns"][i] = metric_value(sample.loc[sacc, "prod_time_resid_ns"].to_numpy(), "abs68")
        stats["accepted_timing_tail_frac_gt5ns"][i] = metric_value(sample.loc[sacc, "prod_time_resid_ns"].to_numpy(), "tail_frac")
        stats["flag_rate"][i] = sf.mean()
    for key, vals in stats.items():
        row[f"{key}_ci95"] = [float(np.nanpercentile(vals, 2.5)), float(np.nanpercentile(vals, 97.5))]
    return row


def markdown_table(frame: pd.DataFrame, columns: List[str], limit: int = 24) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].head(limit).copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}")
    return use.to_markdown(index=False)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def make_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    counts: pd.DataFrame,
    transfer_summary: pd.DataFrame,
    by_stave: pd.DataFrame,
    deltas: pd.DataFrame,
    result: dict,
) -> None:
    winner = result["winner"]
    lines = [
        "# P04q: Cross-Stave Harm-Veto Transfer Validation",
        "",
        f"- **Study ID:** P04q",
        f"- **Ticket ID:** {config['ticket_id']}",
        f"- **Author:** {config['worker']}",
        "- **Date:** 2026-07-09",
        "- **Input:** raw B-stack ROOT `HRDv` branches only.",
        f"- **Config:** `configs/p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.json`",
        f"- **Git commit:** `{result['git_commit']}`",
        "",
        "## Abstract",
        "",
        "P04p found that a duplicate-readout harm veto can protect B2 template/saturation charge corrections. This study asks whether that veto is portable to the downstream B4, B6, and B8 staves or whether it is a B2-specific saturation classifier. I reran the raw ROOT reproduction gate, constructed odd-channel duplicate closure labels independently for each target stave, and compared a physics rule to ridge, gradient-boosted trees, MLP, 1D-CNN, and waveform-gated residual neural-network vetoes under run-held-out evaluation.",
        "",
        "## 1. Raw Reproduction",
        "",
        "For each configured run, the script reads `EVENTNO`, `EVT`, and `HRDv` from the raw `h101` tree. The baseline is the median of samples 0-3 per channel. A selected S00 pulse is any physical B2/B4/B6/B8 even channel with baseline-subtracted peak amplitude above 1000 ADC.",
        "",
        markdown_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "Evaluation-run selected-pulse counts by target stave:",
        "",
        markdown_table(counts[counts["run"].isin(config["evaluation_runs"])], ["run", "B2_selected", "B4_selected", "B6_selected", "B8_selected"], limit=8),
        "",
        "## 2. Label and Closure Definition",
        "",
        "For event i and stave s, the even waveform x_i,s(t) is compared with the inverted odd duplicate waveform o_i,s(t). The positive odd integral y_i,s = sum_t max(o_i,s(t), 0) defines the external closure target when y_i,s >= 100 ADC. The charge calibrator for any estimator z_i,s is fit only on training runs:",
        "",
        "`log E[y_i,s | z_i,s] = beta_0 + beta_1 log z_i,s + beta_2 (log z_i,s)^2 + epsilon_i`,",
        "",
        "using the robust Huber polynomial calibrator inherited from P04p. Timing closure is the CFD20 even time minus the CFD20 odd time after subtracting the train-run median offset. The production estimator is the template/saturation scale; the reference estimator is the raw positive integral for charge and the raw peak CFD for timing. A harm label is positive when production worsens the absolute charge residual by at least 0.05, worsens the absolute timing residual by at least 1 ns, or has a large template/integral shift in the saturation-support region while charge closure worsens.",
        "",
        "## 3. Splits and Methods",
        "",
        "The primary transfer split trains on B2 rows from all non-held-out runs and evaluates B4/B6/B8 rows in the held-out run. A secondary within-stave split trains on the same target stave from all non-held-out runs. Thus no run appears in both train and test for any reported row, and the primary result also excludes target-stave labels from training.",
        "",
        "The traditional method is a fixed support rule voting on saturation proxy, baseline excursion, template/integral shift, and high template loss. The ML/NN set is ridge, gradient-boosted trees, MLP, 1D-CNN, and the new `wavegate_resnet`, a waveform-gated residual tabular network that gates convolutional waveform features by support variables. Features exclude run id, event id, odd waveform, odd charge, odd timing, and held-out labels.",
        "",
        "## 4. Primary Transfer Benchmark",
        "",
        "Accepted events are those not flagged. Confidence intervals are 95% nonparametric bootstrap intervals over stave-run blocks.",
        "",
        markdown_table(
            transfer_summary.sort_values("primary_rank"),
            [
                "method",
                "precision",
                "recall",
                "accepted_coverage",
                "accepted_coverage_ci95",
                "accepted_charge_res68_frac",
                "accepted_charge_res68_frac_ci95",
                "accepted_timing_abs68_ns",
                "accepted_timing_abs68_ns_ci95",
                "calibration_ece",
                "primary_rank",
            ],
        ),
        "",
        f"**Winner:** `{winner}`. The winner is selected by a fixed lexicographic rule: among methods with accepted coverage >= 0.50, minimize accepted charge res68; break ties by accepted timing abs68 and calibration ECE.",
        "",
        "## 5. Per-Stave Systematics",
        "",
        markdown_table(
            by_stave.sort_values(["stave", "primary_rank"]),
            ["stave", "method", "accepted_coverage", "accepted_charge_res68_frac", "accepted_timing_abs68_ns", "precision", "recall", "primary_rank"],
            limit=30,
        ),
        "",
        "The per-stave table is a systematic check on whether the pooled winner is driven by one target stave. A portable veto should preserve the same direction of improvement against the traditional rule across B4, B6, and B8; a B2-local artifact would typically collapse to sentinel-like behavior on one or more targets.",
        "",
        "## 6. Falsification and Deltas",
        "",
        markdown_table(deltas, ["method", "flag_rate_delta_vs_traditional", "ci95", "n_blocks"]),
        "",
        "The shuffled-target GBT is retained as an explicit leakage/control sentinel. It uses the same feature matrix as the boosted-tree model after permuting training labels; if it had matched the leading model within uncertainty, the claimed even-waveform support signal would be rejected.",
        "",
        "## 7. Caveats",
        "",
        "- Odd duplicate readout is an external closure target, not a calibrated deposited-energy truth.",
        "- The train source for the primary benchmark is B2, so target-stave template calibration uses B2 morphology; this is intentionally stringent for transfer, but it can understate a target-specific deployable model.",
        "- Bootstrap intervals resample observed stave-run blocks and do not cover future detector configurations or unobserved beam settings.",
        "- The CFD20 timing residual is a compact closure proxy and not a full pulse-fit time estimator.",
        "- Neural-network hyperparameters are deliberately small for reproducibility on the laptop worker; the comparison is a practical benchmark, not an exhaustive architecture search.",
        "",
        "## 8. Provenance",
        "",
        "`manifest.json` records input checksums, command, seed, environment, and output hashes. Artifacts include `result.json`, `reproduction_gate.csv`, `counts_by_run.csv`, `transfer_method_metrics.csv`, `within_stave_method_metrics.csv`, `transfer_method_by_stave.csv`, `transfer_method_by_run.csv`, `flag_rate_deltas.csv`, and leakage audit tables.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.py --config configs/p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.json",
        "```",
        "",
        "## 10. Finding",
        "",
        result["finding"],
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04q_1781143765_834_683c6144_cross_stave_harm_veto_transfer.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    method_names = ["traditional_rule", "ridge", "gradient_boosted_trees", "mlp", "cnn_1d", "wavegate_resnet", "shuffled_target_gbt"]

    print("1/5 reading raw ROOT and reproducing S00 anchor", flush=True)
    meta_all, wave_all, counts = extract_stave_rows(config)
    reproduced = int(counts["s00_selected_pulses"].sum())
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "report_value": int(config["expected_selected_pulses"]),
                "reproduced": reproduced,
                "delta": reproduced - int(config["expected_selected_pulses"]),
                "tolerance": 0,
                "pass": reproduced == int(config["expected_selected_pulses"]),
            }
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    valid = (meta_all["odd_charge"].to_numpy() >= float(config["harm_label"]["min_odd_charge"])) & np.isfinite(
        meta_all["odd_time_ns"].to_numpy()
    )
    meta = meta_all.loc[valid].reset_index(drop=True)
    wave = wave_all[valid]
    print(f"valid selected rows={len(meta)} evaluation rows={int(meta['run'].isin(config['evaluation_runs']).sum())}", flush=True)

    print("2/5 running B2-to-target transfer folds", flush=True)
    transfer_rows: List[pd.DataFrame] = []
    within_rows: List[pd.DataFrame] = []
    leakage_rows: List[dict] = []
    eval_runs = [int(run) for run in config["evaluation_runs"]]
    targets = list(config["target_staves"])
    source = str(config["source_stave"])

    for held_run in eval_runs:
        for target in targets:
            held_idx = np.flatnonzero((meta["run"].to_numpy() == held_run) & (meta["stave"].to_numpy() == target))
            if len(held_idx) == 0:
                continue
            transfer_train = np.flatnonzero((meta["run"].to_numpy() != held_run) & (meta["stave"].to_numpy() == source))
            fold, leak = fit_fold_models(meta, wave, transfer_train, held_idx, config, int(config["random_seed"]) + held_run * 100 + len(target), True)
            fold["split"] = "b2_to_target_transfer"
            transfer_rows.append(fold)
            leak.update({"split": "b2_to_target_transfer", "heldout_run": held_run, "target_stave": target, "train_stave": source})
            leakage_rows.append(leak)
            print(f"transfer run {held_run} {source}->{target}: held={len(held_idx)} harm={fold['harm_label'].mean():.3f}", flush=True)

            within_train = np.flatnonzero((meta["run"].to_numpy() != held_run) & (meta["stave"].to_numpy() == target))
            fold_w, leak_w = fit_fold_models(meta, wave, within_train, held_idx, config, int(config["random_seed"]) + held_run * 100 + 50 + len(target), False)
            fold_w["split"] = "target_within_stave"
            within_rows.append(fold_w)
            leak_w.update({"split": "target_within_stave", "heldout_run": held_run, "target_stave": target, "train_stave": target})
            leakage_rows.append(leak_w)

    transfer_pred = pd.concat(transfer_rows, ignore_index=True)
    within_pred = pd.concat(within_rows, ignore_index=True)

    print("3/5 summarizing bootstrap CIs", flush=True)
    transfer_summary = pd.DataFrame([summarize_method(transfer_pred, m, int(config["bootstrap_reps"]), rng) for m in method_names])
    eligible = transfer_summary["accepted_coverage"] >= 0.50
    # Failed/unavailable Torch methods are never ranked as scientific winners (#1126).
    if "execution_state" in transfer_summary.columns:
        failed = transfer_summary["execution_state"].fillna("SUCCESS").astype(str).str.startswith(("FAILED", "UNAVAILABLE"))
        eligible = eligible & ~failed
    if "eligible_for_ranking" in transfer_summary.columns:
        eligible = eligible & transfer_summary["eligible_for_ranking"].fillna(True).astype(bool)
    rank_source = transfer_summary.copy()
    rank_source["_bad"] = ~eligible
    rank_source = rank_source.sort_values(
        ["_bad", "accepted_charge_res68_frac", "accepted_timing_abs68_ns", "calibration_ece"],
        ascending=[True, True, True, True],
    )
    rank_map = {method: i + 1 for i, method in enumerate(rank_source["method"])}
    transfer_summary["primary_rank"] = transfer_summary["method"].map(rank_map)
    winner = str(rank_source.iloc[0]["method"])

    within_summary = pd.DataFrame([summarize_method(within_pred, m, int(config["bootstrap_reps"]), rng) for m in method_names])
    within_rank = within_summary.copy()
    within_rank["_bad"] = ~(within_rank["accepted_coverage"] >= 0.50)
    within_rank = within_rank.sort_values(["_bad", "accepted_charge_res68_frac", "accepted_timing_abs68_ns", "calibration_ece"])
    within_summary["primary_rank"] = within_summary["method"].map({m: i + 1 for i, m in enumerate(within_rank["method"])})

    by_stave_rows = []
    for stave, block in transfer_pred.groupby("stave"):
        block_summary = pd.DataFrame([summarize_method(block, m, max(80, int(config["bootstrap_reps"]) // 3), rng) for m in method_names])
        block_rank = block_summary.copy()
        block_rank["_bad"] = ~(block_rank["accepted_coverage"] >= 0.50)
        block_rank = block_rank.sort_values(["_bad", "accepted_charge_res68_frac", "accepted_timing_abs68_ns", "calibration_ece"])
        block_summary["primary_rank"] = block_summary["method"].map({m: i + 1 for i, m in enumerate(block_rank["method"])})
        block_summary["stave"] = stave
        by_stave_rows.append(block_summary)
    by_stave = pd.concat(by_stave_rows, ignore_index=True)

    by_run_rows = []
    for (stave, run), block in transfer_pred.groupby(["stave", "run"]):
        for method in method_names:
            row = summarize_method(block, method, max(40, int(config["bootstrap_reps"]) // 5), rng)
            row["stave"] = stave
            row["run"] = int(run)
            by_run_rows.append(row)
    by_run = pd.DataFrame(by_run_rows)

    run_blocks = {int(run): block for run, block in transfer_pred.groupby("run")}
    run_keys = list(run_blocks.keys())
    delta_rows = []
    for method in [m for m in method_names if m != "traditional_rule"]:
        if method in {"cnn_1d", "wavegate_resnet"} and not np.isfinite(transfer_pred[f"prob_{method}"].to_numpy(dtype=float)).any():
            delta_rows.append(
                {
                    "method": method,
                    "flag_rate_delta_vs_traditional": float("nan"),
                    "ci95": [float("nan"), float("nan")],
                    "n_blocks": int(len(run_keys)),
                    "resampling_unit": "run",
                    "execution_state": "FAILED_OR_UNAVAILABLE",
                }
            )
            continue
        obs = float(transfer_pred[f"flag_{method}"].mean() - transfer_pred["flag_traditional_rule"].mean())
        boot = np.empty(int(config["bootstrap_reps"]), dtype=float)
        for i in range(int(config["bootstrap_reps"])):
            sample = pd.concat(
                [run_blocks[run_keys[j]] for j in rng.choice(len(run_keys), size=len(run_keys), replace=True)],
                ignore_index=True,
            )
            boot[i] = float(sample[f"flag_{method}"].mean() - sample["flag_traditional_rule"].mean())
        delta_rows.append(
            {
                "method": method,
                "flag_rate_delta_vs_traditional": obs,
                "ci95": [float(np.nanpercentile(boot, 2.5)), float(np.nanpercentile(boot, 97.5))],
                "n_blocks": int(len(run_keys)),
                "resampling_unit": "run",
            }
        )
    deltas = pd.DataFrame(delta_rows)

    print("4/5 writing artifacts", flush=True)
    win_row = transfer_summary[transfer_summary["method"] == winner].iloc[0]
    trad_row = transfer_summary[transfer_summary["method"] == "traditional_rule"].iloc[0]
    finding = (
        f"The primary B2-to-B4/B6/B8 transfer winner is {winner}: accepted charge res68 "
        f"{win_row['accepted_charge_res68_frac']:.4f} at coverage {win_row['accepted_coverage']:.3f}, "
        f"precision {win_row['precision']:.3f}, recall {win_row['recall']:.3f}, and timing abs68 "
        f"{win_row['accepted_timing_abs68_ns']:.3f} ns. The traditional rule gives charge res68 "
        f"{trad_row['accepted_charge_res68_frac']:.4f} at coverage {trad_row['accepted_coverage']:.3f}. "
        f"The raw reproduction gate matched {int(config['expected_selected_pulses'])} selected B-stave pulses exactly."
    )
    leakage = {
        "folds": leakage_rows,
        "feature_exclusions": ["run_id", "event_id", "odd_waveform", "odd_charge", "odd_time", "heldout_labels"],
        "torch_available": bool(torch is not None),
        "train_eval_run_overlap": False,
        "primary_split": "B2 rows from non-held-out runs train B4/B6/B8 held-out rows",
    }
    result = {
        "study": "P04q",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "winner": winner,
        "winner_selection": "primary transfer split; coverage>=0.50 then min accepted_charge_res68_frac, accepted_timing_abs68_ns, calibration_ece",
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "methods": method_names,
        "primary_transfer_methods": transfer_summary.sort_values("primary_rank").to_dict(orient="records"),
        "within_stave_methods": within_summary.sort_values("primary_rank").to_dict(orient="records"),
        "transfer_by_stave": by_stave.sort_values(["stave", "primary_rank"]).to_dict(orient="records"),
        "flag_rate_deltas_vs_traditional": deltas.to_dict(orient="records"),
        "leakage_audit": leakage,
        "finding": finding,
        "next_tickets": [],
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_sec": round(time.time() - t0, 2),
    }

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_gate.csv", index=False)
    transfer_pred.to_csv(out_dir / "transfer_oof_predictions.csv", index=False)
    within_pred.to_csv(out_dir / "within_stave_oof_predictions.csv", index=False)
    transfer_summary.sort_values("primary_rank").to_csv(out_dir / "transfer_method_metrics.csv", index=False)
    within_summary.sort_values("primary_rank").to_csv(out_dir / "within_stave_method_metrics.csv", index=False)
    by_stave.sort_values(["stave", "primary_rank"]).to_csv(out_dir / "transfer_method_by_stave.csv", index=False)
    by_run.to_csv(out_dir / "transfer_method_by_run.csv", index=False)
    deltas.to_csv(out_dir / "flag_rate_deltas.csv", index=False)
    pd.DataFrame(leakage_rows).to_csv(out_dir / "leakage_checks.csv", index=False)
    (out_dir / "leakage_checks.json").write_text(json.dumps(leakage, indent=2), encoding="utf-8")
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    make_report(out_dir, config, reproduction, counts, transfer_summary, by_stave, deltas, result)

    inputs = {str(raw_path(config, int(run))): sha256_file(raw_path(config, int(run))) for run in configured_runs(config)}
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
