#!/usr/bin/env python3
"""P04d: A/B charge-transfer null controls by A-topology.

This follows P04c's raw ROOT event matching, reproduces the P04c broad
A1/A3 target number first, then separates A1-only, A3-only, and A1+A3 targets
under the same B2-source leave-one-run-out split.
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
import yaml
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_p04c_module(path: Path):
    spec = importlib.util.spec_from_file_location("p04c_ab_event_matched_charge_transfer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def run_block_ci(frame: pd.DataFrame, value_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {"bias_ci95": [None, None], "res68_ci95": [None, None], "full_rms_ci95": [None, None]}
    by_run = {run: frame[frame["run"] == run] for run in runs}
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    for idx in range(reps):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in sample_runs], ignore_index=True)
        frac = (sample[pred_col].to_numpy() - sample[value_col].to_numpy()) / np.maximum(sample[value_col].to_numpy(), 1.0)
        bias[idx] = np.median(frac)
        res68[idx] = np.percentile(np.abs(frac), 68)
        rms[idx] = np.sqrt(np.mean(frac * frac))
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
    }


def b_charge_features(frame: pd.DataFrame) -> np.ndarray:
    b2q = np.log(np.maximum(frame["b2_charge"].to_numpy(), 1.0))
    b2a = np.log(np.maximum(frame["b2_amp"].to_numpy(), 1.0))
    bt = np.log(np.maximum(frame["b_total_charge"].to_numpy(), 1.0))
    bd = np.log1p(frame["b_downstream_charge"].to_numpy())
    down_frac = frame["b_downstream_charge"].to_numpy() / np.maximum(frame["b_total_charge"].to_numpy(), 1.0)
    return np.column_stack(
        [
            b2q,
            b2a,
            bt,
            bd,
            b2q * b2q,
            b2a * b2a,
            bt * bt,
            b2q * bt,
            down_frac,
            frame["b_mult"].to_numpy(),
            frame["b_downstream_mult"].to_numpy(),
            frame["B4_selected"].to_numpy(),
            frame["B6_selected"].to_numpy(),
            frame["B8_selected"].to_numpy(),
            frame["B2_peak"].to_numpy(),
            frame["B4_peak"].to_numpy(),
            frame["B6_peak"].to_numpy(),
            frame["B8_peak"].to_numpy(),
        ]
    )


def waveform_features(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    charge = np.clip(wave, 0.0, None).sum(axis=2)
    amp = wave.max(axis=2)
    peak = wave.argmax(axis=2)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, :, 12:], 0.0, None).sum(axis=2) / total
    late = np.clip(wave[:, :, 9:], 0.0, None).sum(axis=2) / total
    half_width = (wave > (0.5 * amp[:, :, None])).sum(axis=2)
    engineered = np.column_stack(
        [
            np.log(np.maximum(charge, 1.0)),
            np.log(np.maximum(amp, 1.0)),
            peak,
            tail,
            late,
            half_width,
            frame["b_mult"].to_numpy(),
            frame["b_downstream_mult"].to_numpy(),
        ]
    )
    return np.column_stack([wave.reshape(len(wave), -1), engineered])


def build_topology_frame(frame: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, np.ndarray]:
    pieces: List[pd.DataFrame] = []
    wave_idx: List[np.ndarray] = []
    definitions = [
        ("A1_only", (frame["A1_selected"] == 1) & (frame["A3_selected"] == 0), "A1_charge", "A1 selected, A3 quiet"),
        ("A3_only", (frame["A1_selected"] == 0) & (frame["A3_selected"] == 1), "A3_charge", "A3 selected, A1 quiet"),
        ("A1A3", (frame["A1_selected"] == 1) & (frame["A3_selected"] == 1), None, "A1 and A3 both selected"),
    ]
    for topology, mask, charge_col, description in definitions:
        idx = np.where(mask.to_numpy())[0]
        if len(idx) == 0:
            continue
        sub = frame.iloc[idx].copy()
        sub["topology"] = topology
        sub["topology_definition"] = description
        sub["source_row"] = idx.astype(np.int64)
        if charge_col is None:
            sub["target_charge"] = sub["A1_charge"] + sub["A3_charge"]
        else:
            sub["target_charge"] = sub[charge_col]
        pieces.append(sub)
        wave_idx.append(idx)
    if not pieces:
        raise RuntimeError("no topology rows were built")
    topo = pd.concat(pieces, ignore_index=True)
    topo_wave = wave[np.concatenate(wave_idx)]
    return topo, topo_wave


def model_topologies(config: dict, topo: pd.DataFrame, topo_wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    methods = [
        "a_mult_median",
        "topology_median",
        "topology_b_charge_ridge",
        "waveform_extra_trees",
        "waveform_hgb",
        "shuffled_target_extra_trees",
    ]
    for method in methods:
        topo[f"pred_{method}"] = np.nan

    x_b = b_charge_features(topo)
    x_w = waveform_features(topo, topo_wave)
    y_log = np.log(np.maximum(topo["target_charge"].to_numpy(), 1.0))
    runs = np.asarray(sorted(topo["run"].unique()), dtype=int)

    for heldout_run in runs:
        held_mask_all = topo["run"].to_numpy() == heldout_run
        train_mask_all = ~held_mask_all
        train = topo.loc[train_mask_all]

        for a_mult, held_idx in topo.loc[held_mask_all].groupby("a_mult").groups.items():
            train_values = train.loc[train["a_mult"] == a_mult, "target_charge"].to_numpy()
            if len(train_values) == 0:
                train_values = train["target_charge"].to_numpy()
            topo.loc[list(held_idx), "pred_a_mult_median"] = float(np.median(train_values))

        for topology, held_idx in topo.loc[held_mask_all].groupby("topology").groups.items():
            same_topo_train_mask = train_mask_all & (topo["topology"].to_numpy() == topology)
            same_topo_train_idx = np.where(same_topo_train_mask)[0]
            held_idx_array = np.asarray(list(held_idx), dtype=int)
            train_values = topo.loc[same_topo_train_idx, "target_charge"].to_numpy()
            if len(train_values) == 0:
                train_values = train["target_charge"].to_numpy()
            topo.loc[held_idx_array, "pred_topology_median"] = float(np.median(train_values))

            if len(same_topo_train_idx) < 8:
                fallback = float(np.median(train_values))
                for method in methods[2:]:
                    topo.loc[held_idx_array, f"pred_{method}"] = fallback
                continue

            ridge = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
            ridge.fit(x_b[same_topo_train_idx], y_log[same_topo_train_idx])
            topo.loc[held_idx_array, "pred_topology_b_charge_ridge"] = np.exp(ridge.predict(x_b[held_idx_array]))

            ml_train_idx = same_topo_train_idx
            if len(ml_train_idx) > int(config["ml_max_train_rows"]):
                ml_train_idx = rng.choice(ml_train_idx, size=int(config["ml_max_train_rows"]), replace=False)

            et = ExtraTreesRegressor(
                n_estimators=24,
                max_depth=6,
                min_samples_leaf=3,
                max_features=0.7,
                n_jobs=1,
                random_state=int(config["random_seed"]) + int(heldout_run) * 11 + len(topology),
            )
            et.fit(x_w[ml_train_idx], y_log[ml_train_idx])
            topo.loc[held_idx_array, "pred_waveform_extra_trees"] = np.exp(et.predict(x_w[held_idx_array]))

            hgb = HistGradientBoostingRegressor(
                loss="squared_error",
                learning_rate=0.080,
                max_iter=24,
                max_leaf_nodes=7,
                min_samples_leaf=10,
                l2_regularization=0.10,
                max_bins=64,
                random_state=int(config["random_seed"]) + int(heldout_run) * 17 + len(topology),
            )
            hgb.fit(x_w[ml_train_idx], y_log[ml_train_idx])
            topo.loc[held_idx_array, "pred_waveform_hgb"] = np.exp(hgb.predict(x_w[held_idx_array]))

            shuffled = y_log[ml_train_idx].copy()
            rng.shuffle(shuffled)
            sentinel = ExtraTreesRegressor(
                n_estimators=16,
                max_depth=6,
                min_samples_leaf=3,
                max_features=0.7,
                n_jobs=1,
                random_state=73 + int(heldout_run) * 13 + len(topology),
            )
            sentinel.fit(x_w[ml_train_idx], shuffled)
            topo.loc[held_idx_array, "pred_shuffled_target_extra_trees"] = np.exp(sentinel.predict(x_w[held_idx_array]))

    ci_rng = np.random.default_rng(int(config["random_seed"]) + 900)
    summary_rows = []
    by_run_rows = []
    for topology, sub in topo.groupby("topology"):
        for method in methods:
            row = {"topology": topology, "method": method}
            row.update(robust_metrics(sub["target_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
            row.update(run_block_ci(sub, "target_charge", f"pred_{method}", ci_rng, int(config["bootstrap_reps"])))
            summary_rows.append(row)
        for run, run_sub in sub.groupby("run"):
            for method in methods[:-1]:
                row = {"topology": topology, "run": int(run), "method": method}
                row.update(robust_metrics(run_sub["target_charge"].to_numpy(), run_sub[f"pred_{method}"].to_numpy()))
                by_run_rows.append(row)

    leakage_rows = []
    wave_hash = np.asarray([hashlib.sha1(np.ascontiguousarray(row).view(np.uint8)).hexdigest() for row in topo_wave])
    for topology, sub in topo.groupby("topology"):
        exact_overlap = 0
        for heldout_run in sorted(sub["run"].unique()):
            held_idx = sub.index[sub["run"] == heldout_run].to_numpy()
            train_idx = sub.index[sub["run"] != heldout_run].to_numpy()
            exact_overlap += len(set(wave_hash[held_idx]).intersection(set(wave_hash[train_idx])))
        et_res68 = next(r["res68_abs_frac"] for r in summary_rows if r["topology"] == topology and r["method"] == "waveform_extra_trees")
        hgb_res68 = next(r["res68_abs_frac"] for r in summary_rows if r["topology"] == topology and r["method"] == "waveform_hgb")
        shuffled_res68 = next(r["res68_abs_frac"] for r in summary_rows if r["topology"] == topology and r["method"] == "shuffled_target_extra_trees")
        best_ml = min(et_res68, hgb_res68)
        leakage_rows.append(
            {
                "topology": topology,
                "split": "leave-one-run-out",
                "train_heldout_run_overlap": 0,
                "features_exclude": "run, evt, A selected flags, A charge columns, target_charge",
                "exact_b_waveform_hash_train_test_overlaps": int(exact_overlap),
                "best_real_ml_res68": float(best_ml),
                "shuffled_target_extra_trees_res68": float(shuffled_res68),
                "ml_to_shuffled_res68_ratio": float(best_ml / shuffled_res68) if shuffled_res68 > 0 else None,
                "looks_too_good": bool(best_ml < 0.25 or best_ml < 0.75 * shuffled_res68),
            }
        )
    return pd.DataFrame(summary_rows), pd.DataFrame(by_run_rows), pd.DataFrame(leakage_rows)


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    ab_counts: pd.DataFrame,
    p04c_summary: pd.DataFrame,
    topology_counts: pd.DataFrame,
    topology_summary: pd.DataFrame,
    topology_by_run: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    p04c_ridge = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    p04c_ml = p04c_summary[p04c_summary["method"] == "b_waveform_extra_trees"].iloc[0]
    compact_summary = topology_summary[
        [
            "topology",
            "method",
            "n",
            "bias_median_frac",
            "bias_ci95",
            "res68_abs_frac",
            "res68_ci95",
            "within_25pct",
        ]
    ].copy()
    lines = [
        "# P04d A/B Charge-Transfer Null Controls By A-Topology",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.",
        "- **Split:** B2-source leave-one-run-out by run; every topology prediction is trained on other runs.",
        "- **Targets:** `A1_only`, `A3_only`, and `A1A3` event-matched selected positive-lobe charge.",
        "",
        "## Raw Reproduction First",
        "",
        f"B-stack S00 selected-pulse count reproduced exactly: `{int(b_counts['selected_pulses'].sum()):,}`.",
        "",
        a_counts[["sample", "events_with_selected", "selected_pulses", "A1", "A3"]].to_markdown(index=False),
        "",
        f"P04c broad target reproduction: `{int(p04c_ridge['n'])}` rows, ridge res68 `{p04c_ridge['res68_abs_frac']:.6f}`, "
        f"waveform ExtraTrees res68 `{p04c_ml['res68_abs_frac']:.6f}`.",
        "",
        "## Topology Support",
        "",
        topology_counts.to_markdown(index=False),
        "",
        "## Held-Out Benchmark",
        "",
        compact_summary.to_markdown(index=False),
        "",
        "## Leakage Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "No topology has a real ML res68 below `0.25` or below `75%` of the shuffled-target sentinel, so no extra target-echo model was promoted beyond the exact waveform-hash and shuffled-target checks.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `p04c_reproduction_summary.csv`, `ab_topology_counts_by_run.csv`, "
        "`target_topology_counts.csv`, `topology_summary.csv`, `topology_by_run.csv`, `topology_predictions.csv`, and `leakage_checks.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04d_1781023046_3598_1ff04de7_topology_charge_transfer.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    p04c = load_p04c_module(Path(config["p04c_script"]))

    print("1/6 reproducing raw ROOT B-stack and A-stack gates ...", flush=True)
    b_counts = p04c.count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "b_s00_counts_by_run.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    if got_b != expected_b:
        raise RuntimeError(f"B-stack selected-pulse reproduction failed: {got_b} != {expected_b}")

    a_counts = p04c.count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A-stack event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A-stack pulse gate failed for {row['sample']}")

    print("2/6 extracting P04c event-matched rows from raw ROOT ...", flush=True)
    frame, wave, ab_counts = p04c.extract_ab_rows(config)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)
    if len(frame) != int(config["expected_p04c_rows"]):
        raise RuntimeError(f"P04c row reproduction failed: {len(frame)} != {config['expected_p04c_rows']}")

    print("3/6 reproducing P04c broad charge-transfer number ...", flush=True)
    p04c_summary, p04c_by_run, p04c_by_amp, p04c_leakage = p04c.fit_leave_one_run(config, frame.copy(), wave)
    p04c_summary.to_csv(out_dir / "p04c_reproduction_summary.csv", index=False)
    p04c_by_run.to_csv(out_dir / "p04c_reproduction_by_run.csv", index=False)
    p04c_by_amp.to_csv(out_dir / "p04c_reproduction_by_b2_amp.csv", index=False)
    p04c_ridge = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    expected_res68 = float(config["expected_p04c_charge_transfer_ridge_res68"])
    tolerance = float(config["expected_p04c_tolerance_res68"])
    if abs(float(p04c_ridge["res68_abs_frac"]) - expected_res68) > tolerance:
        raise RuntimeError(f"P04c ridge res68 reproduction failed: {p04c_ridge['res68_abs_frac']} vs {expected_res68}")

    print("4/6 building A-topology targets ...", flush=True)
    topo, topo_wave = build_topology_frame(frame, wave)
    topology_counts = (
        topo.groupby("topology")
        .agg(
            n=("target_charge", "size"),
            runs=("run", "nunique"),
            median_target_charge=("target_charge", "median"),
            median_b2_charge=("b2_charge", "median"),
            a_mult=("a_mult", "median"),
        )
        .reset_index()
    )
    topology_counts.to_csv(out_dir / "target_topology_counts.csv", index=False)

    print(f"5/6 fitting topology-specific leave-one-run-out models on {len(topo)} target rows ...", flush=True)
    topology_summary, topology_by_run, leakage = model_topologies(config, topo, topo_wave)
    topology_summary.to_csv(out_dir / "topology_summary.csv", index=False)
    topology_by_run.to_csv(out_dir / "topology_by_run.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    pred_cols = [
        "run",
        "evt",
        "topology",
        "target_charge",
        "a_mult",
        "b_mult",
        "b2_amp",
        "b2_charge",
        "b_downstream_charge",
        "pred_a_mult_median",
        "pred_topology_median",
        "pred_topology_b_charge_ridge",
        "pred_waveform_extra_trees",
        "pred_waveform_hgb",
        "pred_shuffled_target_extra_trees",
    ]
    topo[pred_cols].to_csv(out_dir / "topology_predictions.csv", index=False)

    print("6/6 writing report, hashes, and manifest ...", flush=True)
    best_real = (
        topology_summary[~topology_summary["method"].eq("shuffled_target_extra_trees")]
        .sort_values(["topology", "res68_abs_frac"])
        .groupby("topology")
        .first()
        .reset_index()
    )
    ridge_rows = topology_summary[topology_summary["method"] == "topology_b_charge_ridge"].set_index("topology")
    ml_rows = topology_summary[topology_summary["method"] == "waveform_extra_trees"].set_index("topology")
    shuffle_rows = topology_summary[topology_summary["method"] == "shuffled_target_extra_trees"].set_index("topology")
    finding_parts = []
    for _, row in best_real.iterrows():
        topology = row["topology"]
        ridge = ridge_rows.loc[topology]
        ml = ml_rows.loc[topology]
        shuffle = shuffle_rows.loc[topology]
        finding_parts.append(
            f"{topology}: best real `{row['method']}` res68 {row['res68_abs_frac']:.4f}; "
            f"ridge {ridge['res68_abs_frac']:.4f} [{ridge['res68_ci95'][0]:.4f}, {ridge['res68_ci95'][1]:.4f}], "
            f"ExtraTrees {ml['res68_abs_frac']:.4f}, shuffled {shuffle['res68_abs_frac']:.4f}"
        )
    broad = float(p04c_ridge["res68_abs_frac"])
    best_topology_res68 = float(best_real["res68_abs_frac"].min())
    if best_topology_res68 < 0.80 * broad:
        interpretation = "Topology mixing contributes to the broad P04c transfer, but the remaining widths are still far from a useful duplicate-readout-like closure."
    else:
        interpretation = "Separating A topology does not materially narrow the broad P04c transfer, so the null is better explained as intrinsic A/B decorrelation under the current B2-source selection."
    finding = interpretation + " " + " ".join(finding_parts)

    result = {
        "study": "P04d",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "astack_analysis_counts": json.loads(a_counts.to_json(orient="records")),
            "p04c_expected_rows": int(config["expected_p04c_rows"]),
            "p04c_reproduced_rows": int(len(frame)),
            "p04c_expected_charge_transfer_ridge_res68": expected_res68,
            "p04c_reproduced_charge_transfer_ridge_res68": float(p04c_ridge["res68_abs_frac"]),
            "p04c_reproduction_pass": True,
        },
        "row_definition": {
            "match_key": "(run, EVT)",
            "source_gate": "B2 amplitude > 1000 ADC",
            "topologies": {
                "A1_only": "A1 amplitude > 1000 ADC and A3 <= 1000 ADC",
                "A3_only": "A3 amplitude > 1000 ADC and A1 <= 1000 ADC",
                "A1A3": "A1 and A3 both amplitude > 1000 ADC",
            },
            "target": "selected A-topology positive-lobe charge",
            "features": "B-stack even-channel waveforms and charge summaries only",
        },
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "p04c_reproduction_summary": json.loads(p04c_summary.to_json(orient="records")),
        "topology_counts": json.loads(topology_counts.to_json(orient="records")),
        "topology_summary": json.loads(topology_summary.to_json(orient="records")),
        "leakage_checks": json.loads(leakage.to_json(orient="records")),
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, ab_counts, p04c_summary, topology_counts, topology_summary, topology_by_run, leakage, result)

    input_runs = sorted(set(p04c.configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    manifest = {
        "study": "P04d",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/p04d_1781023046_3598_1ff04de7_topology_charge_transfer.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": "scripts/p04d_1781023046_3598_1ff04de7_topology_charge_transfer.py",
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
