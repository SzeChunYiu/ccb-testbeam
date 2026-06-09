#!/usr/bin/env python3
"""P07e: validate P07d-style B2 saturation correction against odd duplicate readout.

The correction models see only the physical even B2 waveform. The paired odd duplicate channel is
used as a held-out validation target for charge and timing closure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import HuberRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler


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
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
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


def cfd_time_samples(wave: np.ndarray, amp: np.ndarray, fraction: float) -> np.ndarray:
    threshold = amp * float(fraction)
    ge = wave >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(wave), np.nan, dtype=float)
    for idx in np.where(valid)[0]:
        j = int(first[idx])
        if j <= 0:
            out[idx] = float(j)
            continue
        y0, y1 = float(wave[idx, j - 1]), float(wave[idx, j])
        denom = y1 - y0
        out[idx] = float(j) if denom <= 0 else (j - 1) + (threshold[idx] - y0) / denom
    return out


def extract_b2_rows(config: dict) -> Tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    b2_ch = int(config["staves"]["B2"])
    b2_odd_ch = int(config["duplicate_readout_channels"]["B2"])
    physical_channels = np.asarray([int(ch) for ch in config["staves"].values()], dtype=int)
    groups = run_group_lookup(config)
    frames: List[pd.DataFrame] = []
    waves: List[np.ndarray] = []
    counts: List[dict] = []

    for run in configured_runs(config):
        path = raw_path(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        count = {
            "run": run,
            "group": groups[run],
            "events_total": 0,
            "s00_selected_pulses": 0,
            "b2_selected": 0,
            "b2_high": 0,
            "b2_high_odd_ok": 0,
            "b2_clean": 0,
        }
        for batch in iter_batches(path):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            baseline = np.median(raw[..., baseline_idx], axis=-1)
            corrected = raw - baseline[..., None]
            even_all = corrected[:, physical_channels, :]
            even_amp_all = even_all.max(axis=-1)
            b2 = corrected[:, b2_ch, :]
            odd = -corrected[:, b2_odd_ch, :]
            b2_amp = b2.max(axis=1)
            b2_peak = b2.argmax(axis=1)
            b2_charge = np.clip(b2, 0.0, None).sum(axis=1)
            odd_amp = odd.max(axis=1)
            odd_peak = odd.argmax(axis=1)
            odd_charge = np.clip(odd, 0.0, None).sum(axis=1)
            odd_time = float(config["sample_period_ns"]) * cfd_time_samples(odd, np.maximum(odd_amp, 1.0), float(config["cfd_fraction"]))

            clean_cfg = config["clean_selection"]
            high_cfg = config["high_selection"]
            odd_ok = (odd_amp >= float(clean_cfg["min_odd_amp"])) & (odd_charge >= float(clean_cfg["min_odd_charge"]))
            selected = b2_amp > cut
            clean = (
                (b2_amp >= float(clean_cfg["min_amp_adc"]))
                & (b2_amp <= float(clean_cfg["max_amp_adc"]))
                & (b2_peak >= int(clean_cfg["min_peak_sample"]))
                & (b2_peak <= int(clean_cfg["max_peak_sample"]))
                & odd_ok
            )
            high = (
                (b2_amp >= float(high_cfg["min_amp_adc"]))
                & (odd_amp >= float(high_cfg["min_odd_amp"]))
                & (odd_charge >= float(high_cfg["min_odd_charge"]))
            )
            keep = clean | high

            count["events_total"] += int(len(eventno))
            count["s00_selected_pulses"] += int((even_amp_all > cut).sum())
            count["b2_selected"] += int(selected.sum())
            count["b2_high"] += int((b2_amp >= float(high_cfg["min_amp_adc"])).sum())
            count["b2_high_odd_ok"] += int(high.sum())
            count["b2_clean"] += int(clean.sum())
            if not keep.any():
                continue
            idx = np.flatnonzero(keep)
            waves.append(b2[idx].astype(np.float32))
            frames.append(
                pd.DataFrame(
                    {
                        "run": run,
                        "group": groups[run],
                        "eventno": eventno[idx],
                        "evt": evt[idx],
                        "b2_amp": b2_amp[idx],
                        "b2_peak": b2_peak[idx].astype(np.int16),
                        "b2_charge": b2_charge[idx],
                        "odd_amp": odd_amp[idx],
                        "odd_peak": odd_peak[idx].astype(np.int16),
                        "odd_charge": odd_charge[idx],
                        "odd_time_ns": odd_time[idx],
                        "is_clean": clean[idx],
                        "is_high": high[idx],
                    }
                )
            )
        counts.append(count)
    return pd.concat(frames, ignore_index=True), np.vstack(waves), pd.DataFrame(counts)


def build_template(wave: np.ndarray, amp: np.ndarray) -> np.ndarray:
    return np.median(wave / np.maximum(amp[:, None], 1.0), axis=0)


def pseudo_clip_samples(wave: np.ndarray, amp: np.ndarray, config: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    ratios = np.asarray(config["pseudo_saturation"]["ratios"], dtype=float)
    min_ceiling = float(config["pseudo_saturation"]["min_ceiling_adc"])
    clipped, truth, observed = [], [], []
    for ratio in ratios:
        ceiling = amp / ratio
        keep = ceiling >= min_ceiling
        if not keep.any():
            continue
        clipped.append(np.minimum(wave[keep], ceiling[keep, None]))
        truth.append(amp[keep])
        observed.append(ceiling[keep])
    return np.vstack(clipped), np.concatenate(truth), np.concatenate(observed)


def template_recover(wave: np.ndarray, observed_amp: np.ndarray, template: np.ndarray) -> np.ndarray:
    out = np.zeros(len(wave), dtype=float)
    for i in range(len(wave)):
        plateau = wave[i] >= 0.995 * observed_amp[i]
        usable = ~plateau
        if usable.sum() < 5:
            usable = np.arange(wave.shape[1]) <= max(int(np.argmax(wave[i])) - 1, 0)
        s = template[usable]
        y = wave[i, usable]
        denom = float(np.dot(s, s))
        scale = float(np.dot(s, y) / denom) if denom > 1e-9 else float(observed_amp[i])
        out[i] = max(scale, float(observed_amp[i]))
    return out


def ratio_features(wave: np.ndarray, observed_amp: np.ndarray) -> np.ndarray:
    safe = np.maximum(observed_amp, 1.0)
    norm = wave / safe[:, None]
    charge = np.clip(wave, 0.0, None).sum(axis=1)
    plateau = (wave >= 0.995 * observed_amp[:, None]).sum(axis=1)
    return np.column_stack(
        [
            norm,
            plateau,
            charge / safe,
            np.clip(wave[:, 10:], 0.0, None).sum(axis=1) / np.maximum(charge, 1.0),
            wave.argmax(axis=1),
            (wave > 0.5 * safe[:, None]).sum(axis=1),
        ]
    )


def fit_ml(config: dict, wave: np.ndarray, truth: np.ndarray, observed: np.ndarray) -> ExtraTreesRegressor:
    ml = config["ml"]
    model = ExtraTreesRegressor(
        n_estimators=int(ml["n_estimators"]),
        max_depth=int(ml["max_depth"]),
        min_samples_leaf=int(ml["min_samples_leaf"]),
        n_jobs=-1,
        random_state=int(ml["random_seed"]),
    )
    model.fit(ratio_features(wave, observed), np.log(truth / observed))
    return model


def fit_charge_calibrator(amp: np.ndarray, odd_charge: np.ndarray):
    x = np.log(np.maximum(amp, 1.0))[:, None]
    y = np.log(np.maximum(odd_charge, 1.0))
    return make_pipeline(
        PolynomialFeatures(degree=2, include_bias=False),
        StandardScaler(),
        HuberRegressor(epsilon=1.35, alpha=0.0001, max_iter=200),
    ).fit(x, y)


def predict_charge(model, amp: np.ndarray) -> np.ndarray:
    return np.exp(model.predict(np.log(np.maximum(amp, 1.0))[:, None]))


def metric_row(frame: pd.DataFrame, pred_charge: np.ndarray, even_time: np.ndarray, train_time_offset: float) -> dict:
    charge_frac = (pred_charge - frame["odd_charge"].to_numpy()) / np.maximum(frame["odd_charge"].to_numpy(), 1.0)
    time_resid = even_time - frame["odd_time_ns"].to_numpy() - train_time_offset
    finite = np.isfinite(charge_frac) & np.isfinite(time_resid)
    charge_frac = charge_frac[finite]
    time_resid = time_resid[finite]
    return {
        "n": int(len(charge_frac)),
        "charge_bias_median_frac": float(np.median(charge_frac)),
        "charge_res68_abs_frac": float(np.percentile(np.abs(charge_frac), 68)),
        "charge_full_rms_frac": float(np.sqrt(np.mean(charge_frac * charge_frac))),
        "charge_within10_frac": float(np.mean(np.abs(charge_frac) < 0.10)),
        "time_bias_median_ns": float(np.median(time_resid)),
        "time_abs68_ns": float(np.percentile(np.abs(time_resid), 68)),
        "time_full_rms_ns": float(np.sqrt(np.mean(time_resid * time_resid))),
    }


def event_bootstrap_ci(
    frame: pd.DataFrame,
    pred_charge: np.ndarray,
    even_time: np.ndarray,
    train_time_offset: float,
    rng: np.random.Generator,
    reps: int,
) -> dict:
    n = len(frame)
    if n < 20:
        return {}
    stats = {key: [] for key in ["charge_res68_abs_frac", "time_abs68_ns", "charge_bias_median_frac", "time_bias_median_ns"]}
    for _ in range(reps):
        idx = rng.integers(0, n, size=n)
        row = metric_row(frame.iloc[idx], pred_charge[idx], even_time[idx], train_time_offset)
        for key in stats:
            stats[key].append(row[key])
    return {f"{key}_ci95": [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] for key, vals in stats.items()}


def run_block_ci(predictions: pd.DataFrame, rng: np.random.Generator, reps: int) -> List[dict]:
    rows = []
    runs = np.asarray(sorted(predictions["run"].unique()), dtype=int)
    by_run = {run: predictions[predictions["run"] == run] for run in runs}
    for method in sorted(predictions["method"].unique()):
        sub_by_run = {run: by_run[run][by_run[run]["method"] == method] for run in runs}
        values = {key: [] for key in ["charge_res68_abs_frac", "time_abs68_ns", "charge_bias_median_frac", "time_bias_median_ns"]}
        for _ in range(reps):
            sample = pd.concat([sub_by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
            charge_frac = sample["charge_frac_error"].to_numpy()
            time_resid = sample["time_resid_ns"].to_numpy()
            values["charge_res68_abs_frac"].append(np.percentile(np.abs(charge_frac), 68))
            values["time_abs68_ns"].append(np.percentile(np.abs(time_resid), 68))
            values["charge_bias_median_frac"].append(np.median(charge_frac))
            values["time_bias_median_ns"].append(np.median(time_resid))
        row = {"method": method, "n": int(sum(len(v) for v in sub_by_run.values()))}
        sample_all = pd.concat([sub_by_run[int(run)] for run in runs], ignore_index=True)
        row.update(
            {
                "charge_bias_median_frac": float(np.median(sample_all["charge_frac_error"])),
                "charge_res68_abs_frac": float(np.percentile(np.abs(sample_all["charge_frac_error"]), 68)),
                "time_bias_median_ns": float(np.median(sample_all["time_resid_ns"])),
                "time_abs68_ns": float(np.percentile(np.abs(sample_all["time_resid_ns"]), 68)),
            }
        )
        for key, vals in values.items():
            row[f"run_block_{key}_ci95"] = [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
        rows.append(row)
    return rows


def correction_recovery_metrics(truth: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - truth) / np.maximum(truth, 1.0)
    return {
        "n": int(len(frac)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "within10_frac": float(np.mean(np.abs(frac) < 0.10)),
    }


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def write_report(
    out_dir: Path,
    result: dict,
    reproduction: pd.DataFrame,
    summary: pd.DataFrame,
    per_run: pd.DataFrame,
    recovery: pd.DataFrame,
    leakage: dict,
) -> None:
    per_run_brief = (
        per_run.groupby("method")
        .agg(
            runs=("run", "nunique"),
            min_n=("n", "min"),
            median_charge_res68=("charge_res68_abs_frac", "median"),
            worst_charge_res68=("charge_res68_abs_frac", "max"),
            median_time_abs68_ns=("time_abs68_ns", "median"),
            worst_time_abs68_ns=("time_abs68_ns", "max"),
        )
        .reset_index()
    )
    lines = [
        "# P07e: duplicate-channel validation for saturation ratio transfer",
        "",
        f"Ticket `{result['ticket_id']}`. Raw B-stack ROOT was read directly; no Monte Carlo was used.",
        "",
        "## Raw reproduction first",
        "",
        reproduction.to_markdown(index=False),
        "",
        "## Method",
        "",
        "Rows are B2 pulses. The correction models are trained leave-one-run-out on clean even-channel B2 pulses after pseudo-saturation; the paired odd channel is never used as a feature or correction target.",
        "",
        "- `observed_raw`: no saturation correction.",
        "- `traditional_template`: P07d-style train-run median template scale using non-plateau even samples.",
        "- `ml_ratio_transfer`: ExtraTrees regression on normalized even waveform ratio-transfer features.",
        "",
        "Odd duplicate readout is used only for held-out validation. Charge closure predicts odd positive-lobe charge from the corrected even amplitude via a train-run Huber log-polynomial calibration. Timing closure compares corrected even CFD20 time to odd-channel CFD20 time after subtracting the train-run clean B2 even-minus-odd offset.",
        "",
        "## Pseudo-saturation correction check",
        "",
        recovery.to_markdown(index=False),
        "",
        "## Held-out duplicate closure",
        "",
        summary.to_markdown(index=False),
        "",
        "## Per-run closure",
        "",
        per_run_brief.to_markdown(index=False),
        "",
        "The full held-out per-run table, including event-bootstrap CIs for every run and method, is in `duplicate_closure_by_run.csv`.",
        "",
        "## Leakage checks",
        "",
        f"- Split: `{result['split']}`.",
        "- Correction features exclude run id, event id, odd-channel samples, odd charge, odd time, downstream channels, and held-out labels.",
        "- Odd-channel charge calibration uses only training-run clean rows; held-out high-amplitude odd targets are evaluation-only.",
        f"- Exact even-waveform hash overlap between train clean rows and held-out high rows: `{leakage['exact_even_waveform_hash_overlap']}`.",
        f"- Too-good trigger fired: `{leakage['too_good_triggered']}`.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.py --config configs/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.json",
        "```",
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    print("1/4 extracting B2 rows and reproducing raw counts", flush=True)
    meta, waves, counts = extract_b2_rows(config)
    sample_ii = set(int(run) for run in config["run_groups"]["sample_ii_analysis"])
    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "expected": int(config["expected_selected_pulses"]),
                "reproduced": int(counts["s00_selected_pulses"].sum()),
                "delta": int(counts["s00_selected_pulses"].sum()) - int(config["expected_selected_pulses"]),
                "pass": int(counts["s00_selected_pulses"].sum()) == int(config["expected_selected_pulses"]),
            },
            {
                "quantity": "P07d Sample-II analysis B2 selected pulses",
                "expected": int(config["expected_sample_ii_analysis_b2"]),
                "reproduced": int(counts[counts["run"].isin(sample_ii)]["b2_selected"].sum()),
                "delta": int(counts[counts["run"].isin(sample_ii)]["b2_selected"].sum()) - int(config["expected_sample_ii_analysis_b2"]),
                "pass": int(counts[counts["run"].isin(sample_ii)]["b2_selected"].sum()) == int(config["expected_sample_ii_analysis_b2"]),
            },
            {
                "quantity": "B2 high-amplitude odd-duplicate validation rows",
                "expected": "data-derived",
                "reproduced": int(counts["b2_high_odd_ok"].sum()),
                "delta": "",
                "pass": True,
            },
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    clean_mask = meta["is_clean"].to_numpy(dtype=bool)
    high_mask = meta["is_high"].to_numpy(dtype=bool)
    runs = np.asarray(sorted(meta.loc[high_mask, "run"].unique()), dtype=int)
    methods = ["observed_raw", "traditional_template", "ml_ratio_transfer"]
    pred_rows = []
    per_run_rows = []
    recovery_rows = []

    print("2/4 fitting leave-one-run-out correction and duplicate closure", flush=True)
    for run in runs:
        train_mask = clean_mask & (meta["run"].to_numpy() != run)
        held_mask = high_mask & (meta["run"].to_numpy() == run)
        train_idx = np.flatnonzero(train_mask)
        if len(train_idx) > int(config["traditional"]["max_clean_train_rows"]):
            template_idx = rng.choice(train_idx, size=int(config["traditional"]["max_clean_train_rows"]), replace=False)
        else:
            template_idx = train_idx
        template = build_template(waves[template_idx], meta.loc[template_idx, "b2_amp"].to_numpy())

        x_train, y_train, obs_train = pseudo_clip_samples(waves[train_idx], meta.loc[train_idx, "b2_amp"].to_numpy(), config)
        if len(x_train) > int(config["ml"]["max_train_rows"]):
            ml_idx = rng.choice(np.arange(len(x_train)), size=int(config["ml"]["max_train_rows"]), replace=False)
            x_fit, y_fit, obs_fit = x_train[ml_idx], y_train[ml_idx], obs_train[ml_idx]
        else:
            x_fit, y_fit, obs_fit = x_train, y_train, obs_train
        ml_model = fit_ml(config, x_fit, y_fit, obs_fit)

        held_clean_idx = np.flatnonzero(clean_mask & (meta["run"].to_numpy() == run))
        if len(held_clean_idx):
            x_held, y_held, obs_held = pseudo_clip_samples(waves[held_clean_idx], meta.loc[held_clean_idx, "b2_amp"].to_numpy(), config)
            for method, pred in [
                ("traditional_template", template_recover(x_held, obs_held, template)),
                ("ml_ratio_transfer", obs_held * np.exp(ml_model.predict(ratio_features(x_held, obs_held)))),
                ("observed_raw", obs_held),
            ]:
                row = {"run": int(run), "method": method}
                row.update(correction_recovery_metrics(y_held, pred))
                recovery_rows.append(row)

        charge_cal = fit_charge_calibrator(meta.loc[train_mask, "b2_amp"].to_numpy(), meta.loc[train_mask, "odd_charge"].to_numpy())
        train_even_time = float(config["sample_period_ns"]) * cfd_time_samples(
            waves[train_mask], meta.loc[train_mask, "b2_amp"].to_numpy(), float(config["cfd_fraction"])
        )
        train_time_offset = float(np.nanmedian(train_even_time - meta.loc[train_mask, "odd_time_ns"].to_numpy()))

        held = meta.loc[held_mask].reset_index(drop=True)
        held_waves = waves[np.flatnonzero(held_mask)]
        obs_amp = held["b2_amp"].to_numpy()
        pred_amp_by_method = {
            "observed_raw": obs_amp,
            "traditional_template": template_recover(held_waves, obs_amp, template),
        }
        ml_amp = obs_amp * np.exp(ml_model.predict(ratio_features(held_waves, obs_amp)))
        pred_amp_by_method["ml_ratio_transfer"] = np.maximum(ml_amp, obs_amp)

        for method in methods:
            pred_amp = pred_amp_by_method[method]
            pred_charge = predict_charge(charge_cal, pred_amp)
            even_time = float(config["sample_period_ns"]) * cfd_time_samples(held_waves, pred_amp, float(config["cfd_fraction"]))
            row = {"run": int(run), "method": method}
            row.update(metric_row(held, pred_charge, even_time, train_time_offset))
            row.update(event_bootstrap_ci(held, pred_charge, even_time, train_time_offset, rng, int(config["bootstrap_reps"])))
            per_run_rows.append(row)

            charge_frac = (pred_charge - held["odd_charge"].to_numpy()) / np.maximum(held["odd_charge"].to_numpy(), 1.0)
            time_resid = even_time - held["odd_time_ns"].to_numpy() - train_time_offset
            finite = np.isfinite(charge_frac) & np.isfinite(time_resid)
            pred_rows.append(
                pd.DataFrame(
                    {
                        "run": int(run),
                        "method": method,
                        "charge_frac_error": charge_frac[finite],
                        "time_resid_ns": time_resid[finite],
                    }
                )
            )

    predictions = pd.concat(pred_rows, ignore_index=True)
    per_run = pd.DataFrame(per_run_rows).sort_values(["run", "method"])
    recovery = pd.DataFrame(recovery_rows).sort_values(["run", "method"])
    summary = pd.DataFrame(run_block_ci(predictions, rng, int(config["bootstrap_reps"]))).sort_values("method")

    print("3/4 running leakage checks and writing artifacts", flush=True)
    high_waves = waves[high_mask]
    clean_waves = waves[clean_mask]
    clean_hashes = {hashlib.sha256(np.asarray(row, dtype=np.float32).tobytes()).hexdigest() for row in clean_waves}
    overlap = sum(1 for row in high_waves if hashlib.sha256(np.asarray(row, dtype=np.float32).tobytes()).hexdigest() in clean_hashes)
    best_ml = summary[summary["method"] == "ml_ratio_transfer"].iloc[0]
    too_good = bool((best_ml["charge_res68_abs_frac"] < 0.005) or (best_ml["time_abs68_ns"] < 0.05))
    leakage = {
        "exact_even_waveform_hash_overlap": int(overlap),
        "too_good_triggered": too_good,
        "features_excluded": ["run_id", "event_id", "odd_channel_samples", "odd_charge", "odd_time", "downstream_channels", "heldout_labels"],
    }

    observed = summary[summary["method"] == "observed_raw"].iloc[0]
    trad = summary[summary["method"] == "traditional_template"].iloc[0]
    ml = summary[summary["method"] == "ml_ratio_transfer"].iloc[0]
    finding = (
        f"Against {int(observed['n'])} held-out high-amplitude B2 duplicate rows, the P07d-style corrections do not improve odd-channel charge closure: "
        f"raw charge res68 is {observed['charge_res68_abs_frac']:.4f}, traditional is {trad['charge_res68_abs_frac']:.4f}, and ML is {ml['charge_res68_abs_frac']:.4f}. "
        f"Timing closure is also worse after correction: raw abs68 is {observed['time_abs68_ns']:.3f} ns, traditional is {trad['time_abs68_ns']:.3f} ns, and ML is {ml['time_abs68_ns']:.3f} ns. "
        "The duplicate readout therefore does not support applying the ratio-transfer correction to real high-amplitude B2 pulses as a closure improvement."
    )
    result = {
        "study": "P07e",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "split": "leave-one-run-out by run over all B-stack runs with high-amplitude B2 duplicate rows",
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "methods": methods,
        "summary": summary.to_dict(orient="records"),
        "pseudo_saturation_recovery_median_by_method": recovery.groupby("method")[["res68_abs_frac", "bias_median_frac", "within10_frac"]].median().reset_index().to_dict(orient="records"),
        "leakage_audit": leakage,
        "finding": finding,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
    }

    counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_gate.csv", index=False)
    recovery.to_csv(out_dir / "pseudo_saturation_recovery_by_run.csv", index=False)
    per_run.to_csv(out_dir / "duplicate_closure_by_run.csv", index=False)
    summary.to_csv(out_dir / "duplicate_closure_summary.csv", index=False)
    predictions.groupby(["run", "method"]).agg(
        n=("charge_frac_error", "size"),
        charge_frac_median=("charge_frac_error", "median"),
        time_resid_median_ns=("time_resid_ns", "median"),
    ).reset_index().to_csv(out_dir / "prediction_sanity_by_run.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, result, reproduction, summary, per_run, recovery.groupby("method")[["res68_abs_frac", "bias_median_frac", "within10_frac"]].median().reset_index(), leakage)

    inputs = {str(raw_path(config, int(run))): sha256_file(raw_path(config, int(run))) for run in configured_runs(config)}
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P07e",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["ml"]["random_seed"]),
        "runtime_sec": result["runtime_sec"],
        "inputs": inputs,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "finding": finding, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
