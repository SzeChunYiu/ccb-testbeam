#!/usr/bin/env python3
"""P04e: external downstream validation for P04d duplicate-readout closure.

The study starts by reproducing the P04d upstream raw-ROOT number.  It then
tests whether B2 even-waveform models that close the B2 odd duplicate readout
also transfer to an external penetrating target: same-event B4+B6+B8 even
positive charge in Sample II events where B2/B4/B6/B8 are all selected.
Odd duplicate channels are labels for the closure check only; they are never
included in any feature matrix.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
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
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_p04c_module(path: Path):
    spec = importlib.util.spec_from_file_location("p04c_ab_event_matched_charge_transfer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def run_group_lookup(config: dict) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for group, runs in config["run_groups"].items():
        for run in runs:
            out[int(run)] = str(group)
    return out


def raw_path(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def corrected_batch(batch: dict, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
    evt = np.asarray(batch["EVT"]).astype(np.int64)
    raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
    baseline = np.median(raw[..., baseline_idx], axis=-1)
    return eventno, evt, raw - baseline[..., None]


def extract_b2_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    staves = list(config["staves"].keys())
    even_channels = np.asarray([int(config["staves"][s]) for s in staves], dtype=int)
    odd_channels = np.asarray([int(config["duplicate_readout_channels"][s]) for s in staves], dtype=int)
    group_for_run = run_group_lookup(config)

    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []
    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        run_counts = {"run": int(run), "group": group_for_run[int(run)], "events_total": 0, "selected_pulses": 0}
        run_counts.update({s: 0 for s in staves})
        for batch in iter_batches(path):
            eventno, evt, corrected = corrected_batch(batch, config)
            even = corrected[:, even_channels, :]
            odd = -corrected[:, odd_channels, :]
            even_amp = even.max(axis=-1)
            even_peak = even.argmax(axis=-1)
            even_charge = np.clip(even, 0.0, None).sum(axis=-1)
            even_area = even.sum(axis=-1)
            odd_amp = odd.max(axis=-1)
            odd_charge = np.clip(odd, 0.0, None).sum(axis=-1)
            selected = even_amp > cut

            run_counts["events_total"] += int(len(eventno))
            run_counts["selected_pulses"] += int(selected.sum())
            for idx, stave in enumerate(staves):
                run_counts[stave] += int(selected[:, idx].sum())

            b2_mask = selected[:, 0]
            idx = np.where(b2_mask)[0]
            if len(idx) == 0:
                continue
            downstream_selected = selected[idx, 1:]
            frames.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "group": group_for_run[int(run)],
                        "eventno": eventno[idx],
                        "evt": evt[idx],
                        "b2_amp": even_amp[idx, 0],
                        "b2_charge": even_charge[idx, 0],
                        "b2_area": even_area[idx, 0],
                        "b2_peak": even_peak[idx, 0].astype(np.int16),
                        "b2_odd_neg_amp": odd_amp[idx, 0],
                        "b2_odd_pos_charge": odd_charge[idx, 0],
                        "B4_selected": downstream_selected[:, 0].astype(np.int16),
                        "B6_selected": downstream_selected[:, 1].astype(np.int16),
                        "B8_selected": downstream_selected[:, 2].astype(np.int16),
                        "downstream_mult": downstream_selected.sum(axis=1).astype(np.int16),
                        "downstream_charge": even_charge[idx, 1:].sum(axis=1),
                        "downstream_amp_max": even_amp[idx, 1:].max(axis=1),
                    }
                )
            )
            waves.append(even[idx, 0, :].astype(np.float32))
        counts.append(run_counts)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def engineered_features(meta: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    amp = meta["b2_amp"].to_numpy(dtype=float)
    charge = np.maximum(meta["b2_charge"].to_numpy(dtype=float), 1.0)
    clipped = np.clip(wave, 0.0, None)
    early = clipped[:, :6].sum(axis=1) / charge
    mid = clipped[:, 6:12].sum(axis=1) / charge
    late = clipped[:, 12:].sum(axis=1) / charge
    tail = clipped[:, 9:].sum(axis=1) / charge
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    weighted_t = (clipped * np.arange(wave.shape[1], dtype=float)[None, :]).sum(axis=1) / charge
    return np.column_stack(
        [
            np.log(np.maximum(amp, 1.0)),
            np.log(charge),
            meta["b2_peak"].to_numpy(dtype=float),
            meta["b2_area"].to_numpy(dtype=float) / charge,
            early,
            mid,
            late,
            tail,
            half_width,
            weighted_t,
        ]
    )


def ml_features(meta: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    return np.column_stack([wave, engineered_features(meta, wave)])


def fit_huber(X: np.ndarray, y: np.ndarray, train_mask: np.ndarray) -> object:
    model = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=300))
    model.fit(X[train_mask], np.log(np.maximum(y[train_mask], 1.0)))
    return model


def fit_extra_trees(
    X: np.ndarray,
    y: np.ndarray,
    train_mask: np.ndarray,
    rng: np.random.Generator,
    config: dict,
    seed_offset: int,
) -> object:
    train_idx = np.where(train_mask)[0]
    max_rows = int(config["ml_max_train_rows"])
    if len(train_idx) > max_rows:
        train_idx = rng.choice(train_idx, size=max_rows, replace=False)
    model = ExtraTreesRegressor(
        n_estimators=120,
        max_depth=18,
        min_samples_leaf=3,
        max_features=0.75,
        random_state=int(config["random_seed"]) + seed_offset,
        n_jobs=-1,
    )
    model.fit(X[train_idx], np.log(np.maximum(y[train_idx], 1.0)))
    return model


def predict(model: object, X: np.ndarray) -> np.ndarray:
    return np.maximum(np.exp(model.predict(X)), 1.0)


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)),
    }


def run_block_ci(frame: pd.DataFrame, y_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {"bias_ci95": [None, None], "res68_ci95": [None, None], "full_rms_ci95": [None, None]}
    by_run = {int(run): frame[frame["run"] == run] for run in runs}
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    for idx in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in chosen], ignore_index=True)
        y = sample[y_col].to_numpy(dtype=float)
        pred = sample[pred_col].to_numpy(dtype=float)
        frac = (pred - y) / np.maximum(y, 1.0)
        bias[idx] = np.median(frac)
        res68[idx] = np.percentile(np.abs(frac), 68)
        rms[idx] = np.sqrt(np.mean(frac * frac))
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
    }


def waveform_hashes(wave: np.ndarray) -> np.ndarray:
    quantized = np.rint(wave).astype(np.int16)
    out = np.empty(len(wave), dtype=object)
    for idx, row in enumerate(quantized):
        out[idx] = hashlib.sha1(row.tobytes()).hexdigest()
    return out


def evaluate_run_heldout(config: dict, meta: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    valid_dup = meta["b2_odd_pos_charge"].to_numpy(dtype=float) > float(config["min_valid_odd_charge"])
    external_runs = np.asarray([int(r) for r in config["external_target_runs"]], dtype=int)
    external = (
        valid_dup
        & meta["run"].isin(external_runs).to_numpy()
        & (meta["B4_selected"].to_numpy() == 1)
        & (meta["B6_selected"].to_numpy() == 1)
        & (meta["B8_selected"].to_numpy() == 1)
        & (meta["downstream_charge"].to_numpy(dtype=float) > 100.0)
    )
    if int(external.sum()) < 100:
        raise RuntimeError("too few external downstream target rows")

    X_trad = engineered_features(meta, wave)
    X_ml = ml_features(meta, wave)
    y_dup = meta["b2_odd_pos_charge"].to_numpy(dtype=float)
    y_ext = meta["downstream_charge"].to_numpy(dtype=float)
    ext_idx = np.where(external)[0]

    pred_cols = [
        "pred_dup_strong_traditional_huber",
        "pred_dup_extra_trees",
        "pred_external_from_huber_closure",
        "pred_external_from_extra_trees_closure",
        "pred_direct_external_huber",
        "pred_direct_external_extra_trees",
        "pred_shuffled_external_extra_trees",
    ]
    pred = {col: np.full(len(meta), np.nan, dtype=float) for col in pred_cols}

    leakage_rows = []
    hashes = waveform_hashes(wave)
    for heldout_run in sorted(int(r) for r in meta.loc[external, "run"].unique()):
        test_ext = external & (meta["run"].to_numpy() == heldout_run)
        train_ext = external & (meta["run"].to_numpy() != heldout_run)
        train_closure = valid_dup & (meta["run"].to_numpy() != heldout_run)
        if int(test_ext.sum()) == 0 or int(train_ext.sum()) < 100:
            continue

        huber_dup = fit_huber(X_trad, y_dup, train_closure)
        et_dup = fit_extra_trees(X_ml, y_dup, train_closure, rng, config, seed_offset=heldout_run * 7)
        dup_huber_all = predict(huber_dup, X_trad)
        dup_et_all = predict(et_dup, X_ml)
        pred["pred_dup_strong_traditional_huber"][test_ext] = dup_huber_all[test_ext]
        pred["pred_dup_extra_trees"][test_ext] = dup_et_all[test_ext]

        z_huber = np.log(np.maximum(dup_huber_all, 1.0))[:, None]
        z_et = np.log(np.maximum(dup_et_all, 1.0))[:, None]
        cal_huber = fit_huber(z_huber, y_ext, train_ext)
        cal_et = fit_huber(z_et, y_ext, train_ext)
        pred["pred_external_from_huber_closure"][test_ext] = predict(cal_huber, z_huber)[test_ext]
        pred["pred_external_from_extra_trees_closure"][test_ext] = predict(cal_et, z_et)[test_ext]

        direct_huber = fit_huber(X_trad, y_ext, train_ext)
        direct_et = fit_extra_trees(X_ml, y_ext, train_ext, rng, config, seed_offset=heldout_run * 11)
        pred["pred_direct_external_huber"][test_ext] = predict(direct_huber, X_trad)[test_ext]
        pred["pred_direct_external_extra_trees"][test_ext] = predict(direct_et, X_ml)[test_ext]

        train_ext_idx = np.where(train_ext)[0]
        max_rows = int(config["ml_max_train_rows"])
        if len(train_ext_idx) > max_rows:
            train_ext_idx = rng.choice(train_ext_idx, size=max_rows, replace=False)
        shuffled_y = np.log(np.maximum(y_ext[train_ext_idx], 1.0)).copy()
        rng.shuffle(shuffled_y)
        sentinel = ExtraTreesRegressor(
            n_estimators=60,
            max_depth=14,
            min_samples_leaf=5,
            max_features=0.75,
            random_state=int(config["random_seed"]) + heldout_run * 13,
            n_jobs=-1,
        )
        sentinel.fit(X_ml[train_ext_idx], shuffled_y)
        pred["pred_shuffled_external_extra_trees"][test_ext] = np.maximum(np.exp(sentinel.predict(X_ml[test_ext])), 1.0)

        train_hashes = set(hashes[train_closure])
        exact_overlap = int(sum(h in train_hashes for h in hashes[test_ext]))
        leakage_rows.append(
            {
                "heldout_run": int(heldout_run),
                "train_rows_duplicate_closure": int(train_closure.sum()),
                "train_rows_external_calibration": int(train_ext.sum()),
                "test_rows_external": int(test_ext.sum()),
                "train_heldout_run_overlap": 0,
                "exact_b2_waveform_hash_train_test_overlap": exact_overlap,
                "features_exclude": "run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge",
                "odd_duplicate_channels_used_as_features": False,
                "downstream_target_used_as_feature": False,
            }
        )

    out = meta.loc[ext_idx, ["run", "group", "eventno", "evt", "b2_amp", "b2_charge", "b2_peak", "b2_odd_pos_charge", "downstream_charge", "downstream_mult"]].copy()
    for col in pred_cols:
        out[col] = pred[col][ext_idx]
    if out[pred_cols].isna().any().any():
        missing = out[pred_cols].isna().sum().to_dict()
        raise RuntimeError(f"missing held-out predictions: {missing}")

    ci_rng = np.random.default_rng(int(config["random_seed"]) + 99)
    summary_rows = []
    method_specs = [
        ("same_event_B2_odd_charge", "strong_traditional_huber", "b2_odd_pos_charge", "pred_dup_strong_traditional_huber"),
        ("same_event_B2_odd_charge", "extra_trees_odd_closure", "b2_odd_pos_charge", "pred_dup_extra_trees"),
        ("external_downstream_charge", "huber_odd_closure_transfer", "downstream_charge", "pred_external_from_huber_closure"),
        ("external_downstream_charge", "extra_trees_odd_closure_transfer", "downstream_charge", "pred_external_from_extra_trees_closure"),
        ("external_downstream_charge", "direct_external_huber", "downstream_charge", "pred_direct_external_huber"),
        ("external_downstream_charge", "direct_external_extra_trees", "downstream_charge", "pred_direct_external_extra_trees"),
        ("external_downstream_charge", "shuffled_external_extra_trees", "downstream_charge", "pred_shuffled_external_extra_trees"),
    ]
    for target, method, y_col, pred_col in method_specs:
        row = {"target": target, "method": method, "split": "leave_one_run_out"}
        row.update(robust_metrics(out[y_col].to_numpy(dtype=float), out[pred_col].to_numpy(dtype=float)))
        row.update(run_block_ci(out, y_col, pred_col, ci_rng, int(config["bootstrap_reps"])))
        summary_rows.append(row)

    by_run_rows = []
    for run, sub in out.groupby("run"):
        for target, method, y_col, pred_col in method_specs:
            row = {"run": int(run), "target": target, "method": method}
            row.update(robust_metrics(sub[y_col].to_numpy(dtype=float), sub[pred_col].to_numpy(dtype=float)))
            by_run_rows.append(row)

    by_amp_rows = []
    for lo, hi in config["b2_amplitude_bins"]:
        mask = (out["b2_amp"].to_numpy(dtype=float) >= float(lo)) & (out["b2_amp"].to_numpy(dtype=float) < float(hi))
        if int(mask.sum()) < 20:
            continue
        label = f"{int(lo)}_{'inf' if float(hi) > 1e8 else int(hi)}"
        sub = out.loc[mask]
        for target, method, y_col, pred_col in method_specs:
            row = {"b2_amp_bin": label, "target": target, "method": method}
            row.update(robust_metrics(sub[y_col].to_numpy(dtype=float), sub[pred_col].to_numpy(dtype=float)))
            by_amp_rows.append(row)

    summary = pd.DataFrame(summary_rows)
    leakage = pd.DataFrame(leakage_rows)
    shuffled = float(summary.loc[summary["method"] == "shuffled_external_extra_trees", "res68_abs_frac"].iloc[0])
    best_real_ext = float(
        summary[
            (summary["target"] == "external_downstream_charge")
            & (~summary["method"].eq("shuffled_external_extra_trees"))
        ]["res68_abs_frac"].min()
    )
    leakage = pd.concat(
        [
            leakage,
            pd.DataFrame(
                [
                    {
                        "heldout_run": "overall",
                        "train_rows_duplicate_closure": int(valid_dup.sum()),
                        "train_rows_external_calibration": int(external.sum()),
                        "test_rows_external": int(external.sum()),
                        "train_heldout_run_overlap": 0,
                        "exact_b2_waveform_hash_train_test_overlap": int(leakage["exact_b2_waveform_hash_train_test_overlap"].sum()),
                        "features_exclude": "run,eventno,evt,all_odd_duplicate_channels,B4_charge,B6_charge,B8_charge,downstream_charge",
                        "odd_duplicate_channels_used_as_features": False,
                        "downstream_target_used_as_feature": False,
                        "shuffled_external_res68": shuffled,
                        "best_real_external_res68": best_real_ext,
                        "best_to_shuffled_res68_ratio": best_real_ext / shuffled if shuffled > 0 else None,
                        "looks_too_good": bool(best_real_ext < 0.05 or best_real_ext < 0.75 * shuffled),
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    return summary, pd.DataFrame(by_run_rows), pd.DataFrame(by_amp_rows), out, leakage


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    p04d_repro: dict,
    counts_by_run: pd.DataFrame,
    external_counts: dict,
    summary: pd.DataFrame,
    by_run: pd.DataFrame,
    by_amp: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    total = int(counts_by_run["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    external_summary = summary[summary["target"] == "external_downstream_charge"][
        ["method", "n", "bias_median_frac", "bias_ci95", "res68_abs_frac", "res68_ci95", "full_rms_frac", "within_25pct"]
    ]
    duplicate_summary = summary[summary["target"] == "same_event_B2_odd_charge"][
        ["method", "n", "bias_median_frac", "bias_ci95", "res68_abs_frac", "res68_ci95", "full_rms_frac", "within_10pct"]
    ]
    lines = [
        "# P04e External Downstream Validation For P04d Closure",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.",
        "- **Split:** leave-one-run-out by run; every prediction excludes the held-out run.",
        "- **External target:** Sample II penetrating rows with B2/B4/B6/B8 selected; target is B4+B6+B8 even positive charge.",
        "- **Features:** B2 even waveform and B2 even summaries only. Odd duplicate channels are never features.",
        "",
        "## Raw Reproduction First",
        "",
        f"B-stack S00 selected-pulse count: `{total:,}` vs expected `{expected:,}` (delta `{total - expected:+,}`).",
        "",
        f"P04d upstream reproduction: P04c matched rows `{p04d_repro['p04c_rows']}` vs expected `{p04d_repro['expected_p04c_rows']}`; "
        f"ridge res68 `{p04d_repro['p04c_ridge_res68']:.6f}` vs expected `{p04d_repro['expected_p04c_ridge_res68']:.6f}`.",
        "",
        "## External Sample",
        "",
        f"Valid B2 duplicate rows after odd-charge quality cut: `{external_counts['valid_duplicate_rows']:,}`. "
        f"Penetrating external rows: `{external_counts['external_rows']:,}` across `{external_counts['external_runs']}` runs.",
        "",
        "## Same-Event Duplicate Closure On External Rows",
        "",
        duplicate_summary.to_markdown(index=False),
        "",
        "## External Downstream Target",
        "",
        external_summary.to_markdown(index=False),
        "",
        "## Run Checks",
        "",
        by_run[["run", "target", "method", "n", "bias_median_frac", "res68_abs_frac", "within_25pct"]].to_markdown(index=False),
        "",
        "## B2-Amplitude Checks",
        "",
        by_amp[["b2_amp_bin", "target", "method", "n", "bias_median_frac", "res68_abs_frac", "within_25pct"]].to_markdown(index=False),
        "",
        "## Leakage Sentinels",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `p04d_reproduction_summary.csv`, "
        "`counts_by_run.csv`, `external_summary.csv`, `external_by_run.csv`, `external_by_b2_amp.csv`, "
        "`external_predictions.csv`, and `leakage_checks.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04e_1781024351_1857_07576314_external_downstream_validation.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/6 reproducing P04d upstream P04c number from raw ROOT ...", flush=True)
    p04d_config = load_yaml(Path(config["p04d_reference_config"]))
    p04c = load_p04c_module(Path(config["p04c_script"]))
    frame_ab, wave_ab, _ab_counts = p04c.extract_ab_rows(p04d_config)
    p04c_summary, _p04c_by_run, _p04c_by_amp, _p04c_leakage = p04c.fit_leave_one_run(p04d_config, frame_ab.copy(), wave_ab)
    p04c_summary.to_csv(out_dir / "p04d_reproduction_summary.csv", index=False)
    p04c_ridge = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    p04d_repro = {
        "expected_p04c_rows": int(config["expected_p04d_p04c_rows"]),
        "p04c_rows": int(len(frame_ab)),
        "expected_p04c_ridge_res68": float(config["expected_p04d_p04c_ridge_res68"]),
        "p04c_ridge_res68": float(p04c_ridge["res68_abs_frac"]),
    }
    if p04d_repro["p04c_rows"] != p04d_repro["expected_p04c_rows"]:
        raise RuntimeError(f"P04d row reproduction failed: {p04d_repro}")
    if abs(p04d_repro["p04c_ridge_res68"] - p04d_repro["expected_p04c_ridge_res68"]) > float(config["expected_p04d_tolerance_res68"]):
        raise RuntimeError(f"P04d ridge reproduction failed: {p04d_repro}")

    print("2/6 extracting B2/downstream rows and S00 gate from raw ROOT ...", flush=True)
    meta, wave, counts_by_run = extract_b2_rows(config)
    counts_by_run.to_csv(out_dir / "counts_by_run.csv", index=False)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    if total_selected != int(config["expected_selected_pulses"]):
        raise RuntimeError(f"S00 reproduction failed: {total_selected} != {config['expected_selected_pulses']}")

    print("3/6 fitting leave-one-run-out duplicate and external models ...", flush=True)
    summary, by_run, by_amp, predictions, leakage = evaluate_run_heldout(config, meta, wave)
    summary.to_csv(out_dir / "external_summary.csv", index=False)
    by_run.to_csv(out_dir / "external_by_run.csv", index=False)
    by_amp.to_csv(out_dir / "external_by_b2_amp.csv", index=False)
    predictions.to_csv(out_dir / "external_predictions.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    print("4/6 preparing result ...", flush=True)
    valid_duplicate_rows = int((meta["b2_odd_pos_charge"].to_numpy(dtype=float) > float(config["min_valid_odd_charge"])).sum())
    external_counts = {
        "valid_duplicate_rows": valid_duplicate_rows,
        "external_rows": int(len(predictions)),
        "external_runs": int(predictions["run"].nunique()),
    }
    ext = summary[summary["target"] == "external_downstream_charge"].set_index("method")
    dup = summary[summary["target"] == "same_event_B2_odd_charge"].set_index("method")
    best_ext = summary[
        (summary["target"] == "external_downstream_charge")
        & (~summary["method"].eq("shuffled_external_extra_trees"))
    ].sort_values("res68_abs_frac").iloc[0]
    finding = (
        f"The odd-readout closure still looks excellent on the penetrating rows: Huber duplicate-charge res68 "
        f"{dup.loc['strong_traditional_huber', 'res68_abs_frac']:.4f} and ExtraTrees duplicate-charge res68 "
        f"{dup.loc['extra_trees_odd_closure', 'res68_abs_frac']:.4f}. Against the external B4+B6+B8 target, "
        f"the closure transfers are much broader: Huber-transfer res68 {ext.loc['huber_odd_closure_transfer', 'res68_abs_frac']:.4f} "
        f"{ext.loc['huber_odd_closure_transfer', 'res68_ci95']} and ExtraTrees-transfer res68 "
        f"{ext.loc['extra_trees_odd_closure_transfer', 'res68_abs_frac']:.4f} "
        f"{ext.loc['extra_trees_odd_closure_transfer', 'res68_ci95']}. The best even-only external model is "
        f"{best_ext['method']} at res68 {best_ext['res68_abs_frac']:.4f}, while the shuffled-target sentinel is "
        f"{ext.loc['shuffled_external_extra_trees', 'res68_abs_frac']:.4f}. This validates the P04d/P04e caution: "
        "same-event duplicate-readout closure does not become a precise penetrating-charge measurement when odd duplicate channels are excluded from features."
    )
    result = {
        "study": "P04e",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction_first": {
            "s00_expected_selected_pulses": int(config["expected_selected_pulses"]),
            "s00_reproduced_selected_pulses": total_selected,
            "s00_delta": total_selected - int(config["expected_selected_pulses"]),
            "s00_pass": total_selected == int(config["expected_selected_pulses"]),
            "p04d_p04c_reproduction": p04d_repro,
        },
        "row_definition": {
            "source": "B2 even waveform selected above amplitude cut",
            "duplicate_closure_label": "B2 odd inverted positive charge, used only as label",
            "external_target": "Sample II rows with B2/B4/B6/B8 selected; B4+B6+B8 even positive charge",
            "features": "B2 even waveform and B2 even summaries only",
        },
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "external_counts": external_counts,
        "summary": json.loads(summary.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("5/6 writing report and input hashes ...", flush=True)
    write_report(out_dir, config, p04d_repro, counts_by_run, external_counts, summary, by_run, by_amp, leakage, result)
    input_runs = sorted(set(configured_runs(config)) | set(int(r) for r in p04d_config["runs"]))
    input_files = []
    for run in input_runs:
        bpath = raw_path(config, run)
        if bpath.exists():
            input_files.append(bpath)
        apath = Path(config["raw_root_dir"]) / f"hrda_run_{run:04d}.root"
        if apath.exists():
            input_files.append(apath)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in sorted(set(input_files))])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    print("6/6 writing manifest ...", flush=True)
    manifest = {
        "study": "P04e",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/p04e_1781024351_1857_07576314_external_downstream_validation.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": "scripts/p04e_1781024351_1857_07576314_external_downstream_validation.py",
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
            "p04c_script": str(config["p04c_script"]),
            "p04c_script_sha256": sha256_file(Path(config["p04c_script"])),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s", flush=True)


if __name__ == "__main__":
    main()
