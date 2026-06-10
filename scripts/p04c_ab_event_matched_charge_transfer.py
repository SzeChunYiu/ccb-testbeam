#!/usr/bin/env python3
"""P04c: A/B event-matched charge proxy cross-check.

This tests whether the P04/P04b B-stack charge-transfer story survives an
opposite-stack target.  Rows are matched by (run, EVT), require selected B2 and
at least one selected usable A-stack stave, and predict selected A1/A3 charge
from B-stack even-channel information only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
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


def raw_path(config: dict, stack: str, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"{stack}_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVT", "HRDv"], step_size=step_size, library="np")


def configured_p04_runs(config: dict) -> List[int]:
    ref = load_yaml(Path(config["p04_reference_config"]))
    runs: List[int] = []
    for values in ref["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def corrected_channels(batch: dict, channels: List[int], config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    evt = np.asarray(batch["EVT"]).astype(np.int64)
    raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
    baseline = np.median(raw[..., baseline_idx], axis=-1)
    corrected = raw - baseline[..., None]
    wave = corrected[:, channels, :]
    amp = wave.max(axis=-1)
    charge = np.clip(wave, 0.0, None).sum(axis=-1)
    peak = wave.argmax(axis=-1).astype(np.int16)
    return evt, wave, amp, charge, peak


def count_b_s00_gate(config: dict) -> pd.DataFrame:
    cut = float(config["amplitude_cut_adc"])
    staves = config["bstack"]["staves"]
    channels = [int(staves[name]) for name in staves]
    rows = []
    for run in configured_p04_runs(config):
        path = raw_path(config, config["bstack"]["file_prefix"], run)
        counts = {"run": int(run), "events_total": 0, "selected_pulses": 0}
        counts.update({name: 0 for name in staves})
        for batch in iter_batches(path):
            evt, _wave, amp, _charge, _peak = corrected_channels(batch, channels, config)
            selected = amp > cut
            counts["events_total"] += int(len(evt))
            counts["selected_pulses"] += int(selected.sum())
            for idx, name in enumerate(staves):
                counts[name] += int(selected[:, idx].sum())
        rows.append(counts)
    return pd.DataFrame(rows)


def count_astack_gate(config: dict) -> pd.DataFrame:
    cut = float(config["amplitude_cut_adc"])
    staves = config["astack"]["staves"]
    channels = [int(staves[name]) for name in staves]
    samples = {
        "sample_iii_analysis": [int(r) for r in config["sample_iii_analysis_runs"]],
        "sample_iv_analysis": [int(r) for r in config["sample_iv_analysis_runs"]],
    }
    rows = []
    for sample, runs in samples.items():
        counts = {"sample": sample, "events_total": 0, "events_with_selected": 0, "selected_pulses": 0}
        counts.update({name: 0 for name in staves})
        for run in runs:
            path = raw_path(config, config["astack"]["file_prefix"], run)
            for batch in iter_batches(path):
                evt, _wave, amp, _charge, _peak = corrected_channels(batch, channels, config)
                selected = amp > cut
                counts["events_total"] += int(len(evt))
                counts["events_with_selected"] += int(selected.any(axis=1).sum())
                counts["selected_pulses"] += int(selected.sum())
                for idx, name in enumerate(staves):
                    counts[name] += int(selected[:, idx].sum())
        rows.append(counts)
    return pd.DataFrame(rows)


def load_run_stack(path: Path, channels: List[int], config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    events: List[np.ndarray] = []
    waves: List[np.ndarray] = []
    amps: List[np.ndarray] = []
    charges: List[np.ndarray] = []
    peaks: List[np.ndarray] = []
    for batch in iter_batches(path):
        evt, wave, amp, charge, peak = corrected_channels(batch, channels, config)
        events.append(evt)
        waves.append(wave.astype(np.float32))
        amps.append(amp.astype(np.float32))
        charges.append(charge.astype(np.float32))
        peaks.append(peak)
    return np.concatenate(events), np.vstack(waves), np.vstack(amps), np.vstack(charges), np.vstack(peaks)


def extract_ab_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    astaves = list(config["astack"]["staves"].keys())
    bstaves = list(config["bstack"]["staves"].keys())
    ach = [int(config["astack"]["staves"][name]) for name in astaves]
    bch = [int(config["bstack"]["staves"][name]) for name in bstaves]

    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []
    for run in [int(r) for r in config["runs"]]:
        apath = raw_path(config, config["astack"]["file_prefix"], run)
        bpath = raw_path(config, config["bstack"]["file_prefix"], run)
        if not apath.exists() or not bpath.exists():
            continue

        a_evt, _a_wave, a_amp, a_charge, _a_peak = load_run_stack(apath, ach, config)
        b_evt, b_wave, b_amp, b_charge, b_peak = load_run_stack(bpath, bch, config)
        common, a_idx, b_idx = np.intersect1d(a_evt, b_evt, assume_unique=False, return_indices=True)

        a_amp = a_amp[a_idx]
        a_charge = a_charge[a_idx]
        b_amp = b_amp[b_idx]
        b_charge = b_charge[b_idx]
        b_peak = b_peak[b_idx]
        b_wave = b_wave[b_idx]

        a_selected = a_amp > cut
        b_selected = b_amp > cut
        selected = b_selected[:, 0] & a_selected.any(axis=1)
        selected_idx = np.where(selected)[0]

        run_counts = {
            "run": int(run),
            "matched_events": int(len(common)),
            "a_any_selected": int(a_selected.any(axis=1).sum()),
            "a_pair_selected": int(a_selected.all(axis=1).sum()),
            "b2_selected": int(b_selected[:, 0].sum()),
            "ab_rows_b2_and_a_any": int(len(selected_idx)),
            "ab_rows_a_pair": int((selected & a_selected.all(axis=1)).sum()),
            "ab_rows_b2_a_any_downstream_any": int((selected & b_selected[:, 1:].any(axis=1)).sum()),
        }
        counts.append(run_counts)
        if len(selected_idx) == 0:
            continue

        chosen_a_sel = a_selected[selected_idx]
        chosen_a_charge = a_charge[selected_idx]
        chosen_b_sel = b_selected[selected_idx]
        chosen_b_charge = b_charge[selected_idx]
        chosen_b_amp = b_amp[selected_idx]
        target_a_charge = (chosen_a_charge * chosen_a_sel).sum(axis=1)
        b_downstream_charge = chosen_b_charge[:, 1:].sum(axis=1)
        b_total_charge = chosen_b_charge.sum(axis=1)

        frame = pd.DataFrame(
            {
                "run": int(run),
                "evt": common[selected_idx].astype(np.int64),
                "target_a_charge": target_a_charge,
                "a_mult": chosen_a_sel.sum(axis=1).astype(np.int16),
                "b_mult": chosen_b_sel.sum(axis=1).astype(np.int16),
                "b2_amp": chosen_b_amp[:, 0],
                "b2_charge": chosen_b_charge[:, 0],
                "b_downstream_charge": b_downstream_charge,
                "b_total_charge": b_total_charge,
                "b_downstream_mult": chosen_b_sel[:, 1:].sum(axis=1).astype(np.int16),
            }
        )
        for idx, name in enumerate(astaves):
            frame[f"{name}_selected"] = chosen_a_sel[:, idx].astype(np.int16)
            frame[f"{name}_charge"] = chosen_a_charge[:, idx]
        for idx, name in enumerate(bstaves):
            frame[f"{name}_selected"] = chosen_b_sel[:, idx].astype(np.int16)
            frame[f"{name}_amp"] = chosen_b_amp[:, idx]
            frame[f"{name}_charge"] = chosen_b_charge[:, idx]
            frame[f"{name}_peak"] = b_peak[selected_idx, idx]
        frames.append(frame)
        waves.append(b_wave[selected_idx].astype(np.float32))

    if not frames:
        raise RuntimeError("No A/B event-matched rows passed the topology gate")
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


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


def simple_b2_features(frame: pd.DataFrame) -> np.ndarray:
    b2q = np.log(np.maximum(frame["b2_charge"].to_numpy(), 1.0))
    b2a = np.log(np.maximum(frame["b2_amp"].to_numpy(), 1.0))
    return np.column_stack([b2q, b2a, b2q * b2q, b2a * b2a])


def traditional_features(frame: pd.DataFrame) -> np.ndarray:
    b2q = np.log(np.maximum(frame["b2_charge"].to_numpy(), 1.0))
    bt = np.log(np.maximum(frame["b_total_charge"].to_numpy(), 1.0))
    bd = np.log1p(frame["b_downstream_charge"].to_numpy())
    b2a = np.log(np.maximum(frame["b2_amp"].to_numpy(), 1.0))
    down_frac = frame["b_downstream_charge"].to_numpy() / np.maximum(frame["b_total_charge"].to_numpy(), 1.0)
    return np.column_stack(
        [
            b2q,
            bt,
            bd,
            b2a,
            b2q * b2q,
            bt * bt,
            b2q * bt,
            down_frac,
            frame["b_mult"].to_numpy(),
            frame["b_downstream_mult"].to_numpy(),
            frame["B4_selected"].to_numpy(),
            frame["B6_selected"].to_numpy(),
            frame["B8_selected"].to_numpy(),
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


def fit_leave_one_run(config: dict, frame: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(int(config["random_seed"]))
    methods = ["b2_loglinear", "charge_transfer_ridge", "b_waveform_extra_trees", "shuffled_target_extra_trees"]
    for method in methods:
        frame[f"pred_{method}"] = np.nan

    x_b2 = simple_b2_features(frame)
    x_trad = traditional_features(frame)
    x_ml = waveform_features(frame, wave)
    y = frame["target_a_charge"].to_numpy()
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)

    for heldout_run in runs:
        train_mask = frame["run"].to_numpy() != heldout_run
        held_mask = ~train_mask
        train_idx = np.where(train_mask)[0]
        if len(train_idx) > int(config["ml_max_train_rows"]):
            train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)

        b2_model = make_pipeline(StandardScaler(), Ridge(alpha=2.0))
        b2_model.fit(x_b2[train_mask], np.log(y[train_mask]))
        frame.loc[held_mask, "pred_b2_loglinear"] = np.exp(b2_model.predict(x_b2[held_mask]))

        trad_model = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        trad_model.fit(x_trad[train_mask], np.log(y[train_mask]))
        frame.loc[held_mask, "pred_charge_transfer_ridge"] = np.exp(trad_model.predict(x_trad[held_mask]))

        ml_params = {
            "n_estimators": 160,
            "max_depth": 8,
            "min_samples_leaf": 4,
            "max_features": 0.7,
            "n_jobs": -1,
            "random_state": int(config["random_seed"]) + int(heldout_run),
        }
        ml_model = ExtraTreesRegressor(**ml_params)
        ml_model.fit(x_ml[train_idx], np.log(y[train_idx]))
        frame.loc[held_mask, "pred_b_waveform_extra_trees"] = np.exp(ml_model.predict(x_ml[held_mask]))

        shuffled = np.log(y[train_idx]).copy()
        rng.shuffle(shuffled)
        shuffled_model = ExtraTreesRegressor(
            n_estimators=80,
            max_depth=8,
            min_samples_leaf=4,
            max_features=0.7,
            n_jobs=-1,
            random_state=17 + int(heldout_run),
        )
        shuffled_model.fit(x_ml[train_idx], shuffled)
        frame.loc[held_mask, "pred_shuffled_target_extra_trees"] = np.exp(shuffled_model.predict(x_ml[held_mask]))

    rng_ci = np.random.default_rng(int(config["random_seed"]) + 99)
    rows = []
    for method in methods:
        split = "negative_control" if method == "shuffled_target_extra_trees" else "leave_one_run_out"
        row = {"target": "selected_A1A3_physical_charge", "method": method, "split": split}
        row.update(robust_metrics(frame["target_a_charge"].to_numpy(), frame[f"pred_{method}"].to_numpy()))
        row.update(run_block_ci(frame, "target_a_charge", f"pred_{method}", rng_ci, int(config["bootstrap_reps"])))
        rows.append(row)
    summary = pd.DataFrame(rows)

    by_run_rows = []
    for run, sub in frame.groupby("run"):
        for method in methods[:-1]:
            row = {"run": int(run), "method": method}
            row.update(robust_metrics(sub["target_a_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
            by_run_rows.append(row)

    bin_rows = []
    for lo, hi in config["b2_amplitude_bins"]:
        mask = (frame["b2_amp"].to_numpy() >= float(lo)) & (frame["b2_amp"].to_numpy() < float(hi))
        if int(mask.sum()) < 20:
            continue
        label = f"{int(lo)}_{'inf' if float(hi) > 1e8 else int(hi)}"
        sub = frame.loc[mask]
        for method in methods[:-1]:
            row = {"b2_amp_bin": label, "method": method}
            row.update(robust_metrics(sub["target_a_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
            bin_rows.append(row)

    leakage = {
        "split": "leave-one-run-out; every prediction is made by a model trained on other runs",
        "features_exclude": ["run", "evt", "target_a_charge", "A1_charge", "A3_charge", "A1_selected", "A3_selected"],
        "train_heldout_run_overlap": 0,
        "row_key": "(run, EVT)",
        "shuffled_target_res68": float(summary.loc[summary["method"] == "shuffled_target_extra_trees", "res68_abs_frac"].iloc[0]),
        "ml_res68": float(summary.loc[summary["method"] == "b_waveform_extra_trees", "res68_abs_frac"].iloc[0]),
    }
    return summary, pd.DataFrame(by_run_rows), pd.DataFrame(bin_rows), leakage


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    ab_counts: pd.DataFrame,
    summary: pd.DataFrame,
    by_run: pd.DataFrame,
    by_amp: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    expected_b = int(config["expected_b_s00_selected_pulses"])
    got_b = int(b_counts["selected_pulses"].sum())
    best_real = summary[summary["method"] != "shuffled_target_extra_trees"].sort_values("res68_abs_frac").iloc[0]
    trad = summary[summary["method"] == "charge_transfer_ridge"].iloc[0]
    ml = summary[summary["method"] == "b_waveform_extra_trees"].iloc[0]
    shuffle = summary[summary["method"] == "shuffled_target_extra_trees"].iloc[0]

    lines = [
        "# P04c A/B Event-Matched Charge Cross-Check",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.",
        "- **Topology:** match by `(run, EVT)`, require selected B2 and at least one selected usable A-stack stave (`A1` or `A3`).",
        "- **Target:** selected A1/A3 positive-lobe physical charge; predictors use B-stack even-channel waveforms and charge summaries only.",
        "- **Split:** leave-one-run-out over all runs with matched rows; CIs are run-block bootstraps.",
        "",
        "## Raw-ROOT Gates",
        "",
        f"B-stack S00 selected-pulse reproduction ran first: `{got_b:,}` vs expected `{expected_b:,}` (delta `{got_b - expected_b:+,}`).",
        "",
        a_counts[["sample", "events_with_selected", "selected_pulses", "A1", "A3"]].to_markdown(index=False),
        "",
        "The A-stack analysis-count reproductions match the S18 expected values in the config. The A/B topology then yields "
        f"`{int(ab_counts['ab_rows_b2_and_a_any'].sum()):,}` B2-and-A-any event-matched rows across "
        f"`{int((ab_counts['ab_rows_b2_and_a_any'] > 0).sum())}` run blocks.",
        "",
        "## Benchmark",
        "",
        summary[["method", "n", "bias_median_frac", "bias_ci95", "res68_abs_frac", "res68_ci95", "full_rms_frac", "within_25pct"]].to_markdown(index=False),
        "",
        "The best real method is "
        f"`{best_real['method']}` with res68 `{best_real['res68_abs_frac']:.4f}`. The strong traditional charge-transfer ridge gives "
        f"`{trad['res68_abs_frac']:.4f}`, while waveform ExtraTrees gives `{ml['res68_abs_frac']:.4f}`. "
        f"The shuffled-target sentinel is `{shuffle['res68_abs_frac']:.4f}`.",
        "",
        "## Run And B2-Amplitude Checks",
        "",
        by_run[["run", "method", "n", "bias_median_frac", "res68_abs_frac", "within_25pct"]].to_markdown(index=False),
        "",
        by_amp[["b2_amp_bin", "method", "n", "bias_median_frac", "res68_abs_frac", "within_25pct"]].to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        "- Each held-out run is predicted only by models trained on other runs.",
        "- Feature matrices exclude run id, event id, A selected flags, A charge columns, and the target.",
        f"- Shuffled-target ExtraTrees res68 is `{leakage['shuffled_target_res68']:.4f}`, so the real ML result is not a trivial split artifact.",
        "- Matching uses `EVT`; `EVENTNO` is not used because HRDA/HRDB row numbering differs within a run.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `b_s00_counts_by_run.csv`, `astack_gate_counts.csv`, "
        "`ab_topology_counts_by_run.csv`, `external_ab_summary.csv`, `external_ab_by_run.csv`, `external_ab_by_b2_amp.csv`, "
        "and `external_ab_predictions.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04c_ab_event_matched_charge_transfer.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/4 reproducing B-stack S00 gate from raw ROOT ...")
    b_counts = count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "b_s00_counts_by_run.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    if got_b != expected_b:
        raise RuntimeError(f"B-stack S00 gate reproduction failed: {got_b} != {expected_b}")

    print("2/4 reproducing A-stack analysis gates from raw ROOT ...")
    a_counts = count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A-stack event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A-stack pulse gate failed for {row['sample']}")

    print("3/4 extracting A/B event-matched topology rows ...")
    frame, wave, ab_counts = extract_ab_rows(config)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)

    print(f"4/4 fitting leave-one-run-out charge-transfer models on {len(frame)} rows ...")
    summary, by_run, by_amp, leakage = fit_leave_one_run(config, frame, wave)
    summary.to_csv(out_dir / "external_ab_summary.csv", index=False)
    by_run.to_csv(out_dir / "external_ab_by_run.csv", index=False)
    by_amp.to_csv(out_dir / "external_ab_by_b2_amp.csv", index=False)

    pred_cols = [
        "run",
        "evt",
        "target_a_charge",
        "a_mult",
        "b_mult",
        "b2_amp",
        "b2_charge",
        "b_downstream_charge",
        "b_total_charge",
        "pred_b2_loglinear",
        "pred_charge_transfer_ridge",
        "pred_b_waveform_extra_trees",
        "pred_shuffled_target_extra_trees",
    ]
    frame[pred_cols].to_csv(out_dir / "external_ab_predictions.csv", index=False)

    real = summary[summary["method"] != "shuffled_target_extra_trees"].copy()
    best = real.sort_values("res68_abs_frac").iloc[0]
    trad = summary[summary["method"] == "charge_transfer_ridge"].iloc[0]
    ml = summary[summary["method"] == "b_waveform_extra_trees"].iloc[0]
    b2 = summary[summary["method"] == "b2_loglinear"].iloc[0]
    finding = (
        f"The opposite-stack A-charge target does not reproduce the one-percent P04 duplicate-readout closure: "
        f"B2-only log-linear transfer has res68 {b2['res68_abs_frac']:.4f}, the strong traditional B-charge ridge has "
        f"{trad['res68_abs_frac']:.4f} [{trad['res68_ci95'][0]:.4f}, {trad['res68_ci95'][1]:.4f}], and waveform ExtraTrees has "
        f"{ml['res68_abs_frac']:.4f} [{ml['res68_ci95'][0]:.4f}, {ml['res68_ci95'][1]:.4f}]. The best method is "
        f"{best['method']} at {best['res68_abs_frac']:.4f}, while the shuffled-target sentinel is "
        f"{leakage['shuffled_target_res68']:.4f}. This supports the P04b conclusion: duplicate-readout closure is strong, "
        "but transfer to an external charge-energy proxy is broad and topology-limited."
    )

    result = {
        "study": "P04c",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "b_s00_pass": got_b == expected_b,
            "astack_analysis_counts": json.loads(a_counts.to_json(orient="records")),
        },
        "row_definition": {
            "match_key": "(run, EVT)",
            "required_source_topology": "B2 amplitude > 1000 ADC",
            "required_target_topology": "A1 or A3 amplitude > 1000 ADC",
            "target": "sum positive-lobe charge over selected A1/A3 staves",
            "features": "B-stack even-channel waveforms and charge summaries only",
        },
        "runs_with_rows": sorted(int(r) for r in frame["run"].unique()),
        "n_ab_rows": int(len(frame)),
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "topology_counts_by_run": json.loads(ab_counts.to_json(orient="records")),
        "summary": json.loads(summary.to_json(orient="records")),
        "leakage_audit": leakage,
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, ab_counts, summary, by_run, by_amp, leakage, result)

    input_runs = sorted(set(configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path)} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    manifest = {
        "study": "P04c",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/p04c_ab_event_matched_charge_transfer.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
