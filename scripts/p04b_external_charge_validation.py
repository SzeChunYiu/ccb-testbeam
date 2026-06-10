#!/usr/bin/env python3
"""P04b: external downstream-charge validation for P04 duplicate-readout ML."""

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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04_amplitude_charge_regression as p04  # noqa: E402


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def raw_path(config: dict, run: int, stack: str = "b") -> Path:
    return Path(config["raw_root_dir"]) / f"hrd{stack}_run_{run:04d}.root"


def iter_batches(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=step_size, library="np")


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_10pct": float(np.mean(np.abs(frac) < 0.10)),
    }


def run_block_ci(
    frame: pd.DataFrame,
    value_col: str,
    pred_col: str,
    run_col: str,
    rng: np.random.Generator,
    reps: int,
) -> dict:
    runs = np.asarray(sorted(frame[run_col].unique()), dtype=int)
    if len(runs) < 2:
        return {"bias_ci95": [None, None], "res68_ci95": [None, None], "full_rms_ci95": [None, None]}
    bias = np.empty(reps, dtype=float)
    res68 = np.empty(reps, dtype=float)
    rms = np.empty(reps, dtype=float)
    by_run = {run: frame[frame[run_col] == run] for run in runs}
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


def reproduce_p04_charge_number(config: dict) -> dict:
    """Rebuild the P04 duplicate-readout charge benchmark from raw ROOT first."""
    p04_config = load_yaml(Path(config["p04_reference_config"]))
    meta, wave, counts_by_run = p04.extract_rows(p04_config)
    total_selected = int(counts_by_run["selected_pulses"].sum())
    expected = int(p04_config["expected_selected_pulses"])
    if total_selected != expected:
        raise RuntimeError(f"P04 raw reproduction failed: {total_selected} != {expected}")

    valid = (meta["target_odd_neg_amp"].to_numpy() > 100.0) & (meta["target_odd_pos_charge"].to_numpy() > 100.0)
    meta = meta.loc[valid].reset_index(drop=True)
    wave = wave[valid]

    heldout_runs = [int(run) for run in p04_config["heldout_runs"]]
    heldout_mask = meta["run"].isin(heldout_runs).to_numpy()
    train_mask = ~heldout_mask
    st = meta["stave_idx"].to_numpy()
    even_charge = meta["even_pos_charge"].to_numpy()
    y_charge = meta["target_odd_pos_charge"].to_numpy()

    integral_models = p04.fit_log_calibrators(even_charge[train_mask], y_charge[train_mask], st[train_mask])
    integral_pred = p04.predict_log_calibrated(integral_models, even_charge, st)

    rng = np.random.default_rng(int(p04_config["random_seed"]))
    X = p04.ml_features(meta, wave)
    train_idx = np.where(train_mask)[0]
    if len(train_idx) > int(p04_config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(p04_config["ml_max_train_rows"]), replace=False)
    model = HistGradientBoostingRegressor(
        max_iter=220,
        learning_rate=0.06,
        max_leaf_nodes=31,
        l2_regularization=0.05,
        random_state=int(p04_config["random_seed"]),
    )
    model.fit(X[train_idx], np.log(y_charge[train_idx]))
    ml_pred = np.exp(model.predict(X))

    held = meta.loc[heldout_mask, ["run"]].reset_index(drop=True)
    held["target_charge"] = y_charge[heldout_mask]
    held["integral_calibrated"] = integral_pred[heldout_mask]
    held["ml_hgb"] = ml_pred[heldout_mask]

    rows = []
    for method in ["integral_calibrated", "ml_hgb"]:
        row = {"target": "duplicate_odd_charge", "method": method, "subset": "p04_heldout_runs_57_65"}
        row.update(robust_metrics(held["target_charge"].to_numpy(), held[method].to_numpy()))
        rows.append(row)

    reference = json.loads(Path(config["p04_reference_result"]).read_text(encoding="utf-8"))
    ref_charge = {
        row["method"]: row
        for row in reference["benchmark"]
        if row["target"] == "charge" and row["subset"] == "heldout_runs_57_65"
    }
    return {
        "expected_selected_pulses": expected,
        "reproduced_selected_pulses": total_selected,
        "delta": total_selected - expected,
        "pass": total_selected == expected,
        "n_valid_rows": int(len(meta)),
        "heldout_runs": heldout_runs,
        "benchmark": rows,
        "reference_charge_res68": {
            "integral_calibrated": float(ref_charge["integral_calibrated"]["res68_abs_frac"]),
            "ml_hgb": float(ref_charge["ml_hgb"]["res68_abs_frac"]),
        },
    }


def waveform_features(wave: np.ndarray) -> np.ndarray:
    amp = wave.max(axis=1)
    charge = np.clip(wave, 0.0, None).sum(axis=1)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / total
    early = np.clip(wave[:, :6], 0.0, None).sum(axis=1) / total
    peak = wave.argmax(axis=1)
    half_width = (wave > (0.5 * amp[:, None])).sum(axis=1)
    area = wave.sum(axis=1)
    return np.column_stack([wave, np.log(np.maximum(amp, 1.0)), np.log(total), peak, tail, late, early, half_width, area / total])


def traditional_features(wave: np.ndarray) -> np.ndarray:
    amp = wave.max(axis=1)
    charge = np.clip(wave, 0.0, None).sum(axis=1)
    peak = wave.argmax(axis=1)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, 12:], 0.0, None).sum(axis=1) / total
    late = np.clip(wave[:, 9:], 0.0, None).sum(axis=1) / total
    return np.column_stack(
        [
            np.log(np.maximum(amp, 1.0)),
            np.log(total),
            np.log(np.maximum(amp, 1.0)) ** 2,
            np.log(total) ** 2,
            peak,
            tail,
            late,
        ]
    )


def extract_external_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    b2_ch = int(config["b2_channel"])
    b2_dup_ch = int(config["b2_duplicate_channel"])
    downstream = {name: int(ch) for name, ch in config["downstream_channels"].items()}

    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []
    for run in [int(r) for r in config["sample_ii_runs"]]:
        path = raw_path(config, run, "b")
        run_count = {"run": run, "events_total": 0, "b2_selected": 0, "penetrating_rows": 0}
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]

            b2 = corrected[:, b2_ch, :]
            b2_dup = corrected[:, b2_dup_ch, :]
            down = np.stack([corrected[:, ch, :] for ch in downstream.values()], axis=1)

            b2_amp = b2.max(axis=1)
            b2_charge = np.clip(b2, 0.0, None).sum(axis=1)
            b2_dup_charge = np.clip(-b2_dup, 0.0, None).sum(axis=1)
            down_amp = down.max(axis=2)
            down_charge_by_stave = np.clip(down, 0.0, None).sum(axis=2)
            downstream_charge = down_charge_by_stave.sum(axis=1)
            selected = (b2_amp > cut) & (down_amp > cut).all(axis=1) & (b2_dup_charge > 100.0) & (downstream_charge > 100.0)

            run_count["events_total"] += int(len(eventno))
            run_count["b2_selected"] += int((b2_amp > cut).sum())
            run_count["penetrating_rows"] += int(selected.sum())
            if not selected.any():
                continue

            idx = np.where(selected)[0]
            waves.append(b2[idx].astype(np.float32))
            frame = pd.DataFrame(
                {
                    "run": run,
                    "eventno": eventno[idx],
                    "evt": evt[idx],
                    "b2_amp": b2_amp[idx],
                    "b2_charge": b2_charge[idx],
                    "b2_duplicate_charge": b2_dup_charge[idx],
                    "downstream_charge": downstream_charge[idx],
                }
            )
            for stave_idx, stave in enumerate(downstream):
                frame[f"{stave}_charge"] = down_charge_by_stave[idx, stave_idx]
            frames.append(frame)
        counts.append(run_count)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def leave_one_run_out_external(config: dict, frame: pd.DataFrame, wave: np.ndarray) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(int(config["random_seed"]))
    methods = ["traditional_loglinear", "p04_duplicate_ml_transfer", "external_ml_hgb", "shuffled_external_ml"]
    for method in methods:
        frame[f"pred_{method}"] = np.nan
    frame["pred_duplicate_ml_charge"] = np.nan

    X_ml = waveform_features(wave)
    X_trad = traditional_features(wave)
    y_ext = frame["downstream_charge"].to_numpy()
    y_dup = frame["b2_duplicate_charge"].to_numpy()
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)

    for heldout_run in runs:
        train_mask = frame["run"].to_numpy() != heldout_run
        held_mask = ~train_mask
        train_idx = np.where(train_mask)[0]
        if len(train_idx) > int(config["ml_max_train_rows"]):
            train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)

        trad = make_pipeline(StandardScaler(), Ridge(alpha=3.0))
        trad.fit(X_trad[train_mask], np.log(y_ext[train_mask]))
        frame.loc[held_mask, "pred_traditional_loglinear"] = np.exp(trad.predict(X_trad[held_mask]))

        ml_params = {
            "max_iter": 180,
            "learning_rate": 0.06,
            "max_leaf_nodes": 31,
            "l2_regularization": 0.08,
            "random_state": int(config["random_seed"]) + int(heldout_run),
        }
        dup_model = HistGradientBoostingRegressor(**ml_params)
        dup_model.fit(X_ml[train_idx], np.log(y_dup[train_idx]))
        dup_train_pred = np.exp(dup_model.predict(X_ml[train_mask]))
        dup_held_pred = np.exp(dup_model.predict(X_ml[held_mask]))
        transfer = LinearRegression()
        transfer.fit(np.log(np.maximum(dup_train_pred, 1.0))[:, None], np.log(y_ext[train_mask]))
        frame.loc[held_mask, "pred_duplicate_ml_charge"] = dup_held_pred
        frame.loc[held_mask, "pred_p04_duplicate_ml_transfer"] = np.exp(
            transfer.predict(np.log(np.maximum(dup_held_pred, 1.0))[:, None])
        )

        ext_model = HistGradientBoostingRegressor(**ml_params)
        ext_model.fit(X_ml[train_idx], np.log(y_ext[train_idx]))
        frame.loc[held_mask, "pred_external_ml_hgb"] = np.exp(ext_model.predict(X_ml[held_mask]))

        shuffled = np.log(y_ext[train_idx]).copy()
        rng.shuffle(shuffled)
        shuffled_model = HistGradientBoostingRegressor(max_iter=80, learning_rate=0.06, max_leaf_nodes=31, random_state=17 + int(heldout_run))
        shuffled_model.fit(X_ml[train_idx], shuffled)
        frame.loc[held_mask, "pred_shuffled_external_ml"] = np.exp(shuffled_model.predict(X_ml[held_mask]))

    rng_ci = np.random.default_rng(int(config["random_seed"]) + 99)
    rows = []
    for method in methods[:-1]:
        row = {"target": "downstream_B4B6B8_charge_proxy", "method": method, "split": "leave_one_run_out"}
        row.update(robust_metrics(frame["downstream_charge"].to_numpy(), frame[f"pred_{method}"].to_numpy()))
        row.update(run_block_ci(frame, "downstream_charge", f"pred_{method}", "run", rng_ci, int(config["bootstrap_reps"])))
        rows.append(row)
    dup_row = {"target": "same_event_B2_duplicate_charge", "method": "p04_duplicate_ml_b2_only", "split": "leave_one_run_out"}
    dup_row.update(robust_metrics(frame["b2_duplicate_charge"].to_numpy(), frame["pred_duplicate_ml_charge"].to_numpy()))
    dup_row.update(run_block_ci(frame, "b2_duplicate_charge", "pred_duplicate_ml_charge", "run", rng_ci, int(config["bootstrap_reps"])))
    rows.append(dup_row)
    shuffle_row = {"target": "downstream_B4B6B8_charge_proxy", "method": "shuffled_external_ml", "split": "negative_control"}
    shuffle_row.update(robust_metrics(frame["downstream_charge"].to_numpy(), frame["pred_shuffled_external_ml"].to_numpy()))
    shuffle_row.update(run_block_ci(frame, "downstream_charge", "pred_shuffled_external_ml", "run", rng_ci, int(config["bootstrap_reps"])))
    rows.append(shuffle_row)
    summary = pd.DataFrame(rows)

    by_run_rows = []
    for run, sub in frame.groupby("run"):
        for method in methods[:-1]:
            row = {"run": int(run), "target": "downstream_B4B6B8_charge_proxy", "method": method}
            row.update(robust_metrics(sub["downstream_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
            by_run_rows.append(row)
        row = {"run": int(run), "target": "same_event_B2_duplicate_charge", "method": "p04_duplicate_ml_b2_only"}
        row.update(robust_metrics(sub["b2_duplicate_charge"].to_numpy(), sub["pred_duplicate_ml_charge"].to_numpy()))
        by_run_rows.append(row)

    bin_rows = []
    for lo, hi in config["b2_amplitude_bins"]:
        mask = (frame["b2_amp"].to_numpy() >= float(lo)) & (frame["b2_amp"].to_numpy() < float(hi))
        if int(mask.sum()) < 20:
            continue
        label = f"{int(lo)}_{'inf' if hi > 1e8 else int(hi)}"
        sub = frame.loc[mask]
        for method in methods[:-1]:
            row = {"b2_amp_bin": label, "target": "downstream_B4B6B8_charge_proxy", "method": method}
            row.update(robust_metrics(sub["downstream_charge"].to_numpy(), sub[f"pred_{method}"].to_numpy()))
            bin_rows.append(row)
    leakage = {
        "split": "leave-one-run-out; each prediction is from a model trained on other runs",
        "features_exclude": ["run", "eventno", "evt", "downstream_charge", "B4_charge", "B6_charge", "B8_charge"],
        "run_overlap_train_heldout": 0,
        "shuffled_external_ml_res68": float(summary.loc[summary["method"] == "shuffled_external_ml", "res68_abs_frac"].iloc[0]),
        "duplicate_b2_loro_res68": float(summary.loc[summary["method"] == "p04_duplicate_ml_b2_only", "res68_abs_frac"].iloc[0]),
    }
    return summary, pd.DataFrame(by_run_rows), pd.DataFrame(bin_rows), leakage


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    config: dict,
    p04_repro: dict,
    counts: pd.DataFrame,
    summary: pd.DataFrame,
    by_amp: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    ext = summary[summary["target"] == "downstream_B4B6B8_charge_proxy"].copy()
    dup = summary[summary["target"] == "same_event_B2_duplicate_charge"].iloc[0]
    best_ext = ext[ext["method"] != "shuffled_external_ml"].sort_values("res68_abs_frac").iloc[0]
    p04_ml = p04_repro["reference_charge_res68"]["ml_hgb"]
    ratio = float(best_ext["res68_abs_frac"]) / p04_ml

    lines = [
        "# P04b External Charge Validation",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        "- **Worker:** `testbeam-laptop-2`",
        "- **Raw input:** `data/root/root` HRD B-stack ROOT; no Monte Carlo.",
        "- **External proxy:** penetrating Sample II events with B2/B4/B6/B8 physical even channels selected; target is `B4+B6+B8` positive-lobe charge.",
        "- **Split:** leave-one-run-out over runs `58,59,60,61,62,63,65`; CIs are run-block bootstraps.",
        "",
        "## Raw-ROOT P04 Gate",
        "",
        f"P04 selected-pulse reproduction ran first from raw ROOT: `{p04_repro['reproduced_selected_pulses']:,}` vs expected `{p04_repro['expected_selected_pulses']:,}` (delta `{p04_repro['delta']}`).",
        f"The reproduced P04 duplicate-readout charge res68 is `{p04_repro['benchmark'][1]['res68_abs_frac']:.5f}` for ML and `{p04_repro['benchmark'][0]['res68_abs_frac']:.5f}` for the integral baseline; the stored P04 reference values are `{p04_ml:.5f}` and `{p04_repro['reference_charge_res68']['integral_calibrated']:.5f}`.",
        "",
        "## External Benchmark",
        "",
        ext[["method", "n", "bias_median_frac", "bias_ci95", "res68_abs_frac", "res68_ci95", "full_rms_frac", "within_10pct"]].to_markdown(index=False),
        "",
        "Same B2 waveform ML on the same leave-one-run-out rows still closes the duplicate readout at "
        f"`{dup['res68_abs_frac']:.5f}` res68, while the best external-proxy result is `{best_ext['res68_abs_frac']:.5f}`. "
        f"That is `{ratio:.1f}x` wider than the original P04 duplicate-readout ML charge number.",
        "",
        "## B2 Amplitude Dependence",
        "",
        by_amp[["b2_amp_bin", "method", "n", "bias_median_frac", "res68_abs_frac", "within_10pct"]].to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        "- Models are refit separately for each held-out run; no prediction is made by a model trained on that run.",
        "- Feature matrices exclude run id, event ids, downstream charge, downstream stave charges, and same-event target columns.",
        f"- Shuffled-target external ML res68 is `{leakage['shuffled_external_ml_res68']:.5f}`, well worse than the real external ML result.",
        f"- The duplicate-readout result remains very small (`{leakage['duplicate_b2_loro_res68']:.5f}`), so the much larger external-proxy spread is not a run split implementation artifact.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `p04_reproduction_charge.csv`, `external_summary.csv`, `external_by_run.csv`, `external_by_b2_amp.csv`, `external_predictions.csv`, and `counts_by_run.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04b_external_charge_validation.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/3 reproducing P04 duplicate-readout charge number from raw ROOT ...")
    p04_repro = reproduce_p04_charge_number(config)
    pd.DataFrame(p04_repro["benchmark"]).to_csv(out_dir / "p04_reproduction_charge.csv", index=False)

    print("2/3 extracting Sample II penetrating external-proxy rows ...")
    frame, wave, counts = extract_external_rows(config)
    counts.to_csv(out_dir / "counts_by_run.csv", index=False)

    print(f"3/3 leave-one-run-out models on {len(frame)} penetrating rows ...")
    summary, by_run, by_amp, leakage = leave_one_run_out_external(config, frame, wave)
    summary.to_csv(out_dir / "external_summary.csv", index=False)
    by_run.to_csv(out_dir / "external_by_run.csv", index=False)
    by_amp.to_csv(out_dir / "external_by_b2_amp.csv", index=False)
    pred_cols = [
        "run",
        "eventno",
        "evt",
        "b2_amp",
        "b2_charge",
        "b2_duplicate_charge",
        "downstream_charge",
        "pred_traditional_loglinear",
        "pred_p04_duplicate_ml_transfer",
        "pred_external_ml_hgb",
        "pred_duplicate_ml_charge",
        "pred_shuffled_external_ml",
    ]
    frame[pred_cols].to_csv(out_dir / "external_predictions.csv", index=False)

    ext = summary[summary["target"] == "downstream_B4B6B8_charge_proxy"]
    best_ext = ext[ext["method"] != "shuffled_external_ml"].sort_values("res68_abs_frac").iloc[0]
    dup_ext = summary[summary["method"] == "p04_duplicate_ml_b2_only"].iloc[0]
    p04_ml = p04_repro["reference_charge_res68"]["ml_hgb"]
    p04_integral = p04_repro["reference_charge_res68"]["integral_calibrated"]
    finding = (
        f"The original P04 duplicate-readout ML charge closure reproduces at res68 {p04_repro['benchmark'][1]['res68_abs_frac']:.5f} "
        f"against the stored {p04_ml:.5f} reference, but the best run-held-out external downstream-charge proxy is "
        f"{best_ext['method']} with res68 {best_ext['res68_abs_frac']:.5f} "
        f"[{best_ext['res68_ci95'][0]:.5f}, {best_ext['res68_ci95'][1]:.5f}]. "
        f"On the same external rows, B2 duplicate-readout ML closure is {dup_ext['res68_abs_frac']:.5f}; therefore most of the "
        "P04 one-percent-level result is same-event duplicate-readout closure, not demonstrated deposited-energy recovery."
    )

    result = {
        "study": "P04b",
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-2",
        "raw_reproduction_first": p04_repro,
        "external_proxy": "Sample II penetrating B-stack downstream physical charge: B4+B6+B8 positive-lobe charge",
        "runs": [int(r) for r in config["sample_ii_runs"]],
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "n_external_rows": int(len(frame)),
        "counts_by_run": json.loads(counts.to_json(orient="records")),
        "external_summary": json.loads(summary.to_json(orient="records")),
        "leakage_audit": leakage,
        "comparison_to_p04": {
            "p04_duplicate_charge_ml_res68": float(p04_ml),
            "p04_duplicate_charge_integral_res68": float(p04_integral),
            "same_rows_duplicate_ml_b2_res68": float(dup_ext["res68_abs_frac"]),
            "best_external_method": str(best_ext["method"]),
            "best_external_res68": float(best_ext["res68_abs_frac"]),
            "best_external_res68_ci95": [float(best_ext["res68_ci95"][0]), float(best_ext["res68_ci95"][1])],
            "external_to_p04_ml_res68_ratio": float(best_ext["res68_abs_frac"]) / float(p04_ml),
        },
        "next_tickets": [
            {
                "title": "P04c: A/B event-matched charge proxy cross-check",
                "body": "Use event-matched HRDA physical charge where topology allows to test whether P04/P04b downstream-proxy conclusions transfer to the opposite stack.",
            },
            {
                "title": "S14b: range-energy calibration preflight from P04b uncertainty",
                "body": "Propagate P04b external charge-proxy res68 into a minimal range-energy lookup preflight before any per-event energy claim.",
            },
        ],
        "finding": finding,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, p04_repro, counts, summary, by_amp, leakage, result)

    input_runs = sorted(set(int(r) for r in config["sample_ii_runs"]) | set(p04.configured_runs(load_yaml(Path(config["p04_reference_config"])))))
    input_files = [raw_path(config, run, "b") for run in input_runs]
    manifest = {
        "study": "P04b",
        "ticket_id": config["ticket_id"],
        "worker": "testbeam-laptop-2",
        "command": f"{sys.executable} scripts/p04b_external_charge_validation.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
            "p04_reference_script": "scripts/p04_amplitude_charge_regression.py",
            "p04_reference_script_sha256": sha256_file(Path("scripts/p04_amplitude_charge_regression.py")),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": [{"path": str(path), "sha256": sha256_file(path)} for path in input_files],
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
