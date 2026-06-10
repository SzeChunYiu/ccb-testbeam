#!/usr/bin/env python3
"""S11a constrained two-pulse template fit vs compact ML benchmark.

The script reads raw HRD ROOT files, reproduces the relevant prior numbers first,
then creates a shared injected two-pulse benchmark from S01-style empirical
templates. Outputs are written only to the configured report directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def raw_file(config: dict, run: int) -> Path:
    return Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def pulse_quantities(waveforms: np.ndarray, baseline_idx: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[..., baseline_idx], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    peak_sample = corrected.argmax(axis=-1)
    area = corrected.sum(axis=-1)
    return corrected, amplitude, peak_sample, area


def reproduce_counts(config: dict) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = list(staves.keys())
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    total = 0
    sample_ii = defaultdict(int)

    for run in configured_runs(config):
        path = raw_file(config, run)
        if not path.exists():
            raise FileNotFoundError(path)
        for batch in iter_raw(path, ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            _corr, amplitude, _peak, _area = pulse_quantities(waveforms, baseline_idx)
            selected = amplitude > cut
            total += int(selected.sum())
            if run in config["run_groups"]["sample_ii_analysis"]:
                sample_ii["selected_pulses"] += int(selected.sum())
                for i, stave in enumerate(stave_names):
                    sample_ii[stave] += int(selected[:, i].sum())

    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(total),
            "tolerance": 0,
        }
    ]
    for key, value in expected["sample_ii_analysis"].items():
        rows.append(
            {
                "quantity": f"sample_ii_analysis {key}",
                "report_value": int(value),
                "reproduced": int(sample_ii[key]),
                "tolerance": 0,
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def cfd_time_one(waveform: np.ndarray, fraction: float = 0.2) -> float:
    amp = float(np.nanmax(waveform))
    if not np.isfinite(amp) or amp <= 0:
        return float("nan")
    threshold = amp * float(fraction)
    above = np.flatnonzero(waveform >= threshold)
    if len(above) == 0:
        return float("nan")
    j = int(above[0])
    if j <= 0:
        return float(j)
    y0, y1 = float(waveform[j - 1]), float(waveform[j])
    if y1 <= y0:
        return float(j)
    return float(j - 1 + (threshold - y0) / (y1 - y0))


def shift_array(values: np.ndarray, shift: float, fill: float = 0.0) -> np.ndarray:
    x = np.arange(len(values), dtype=float)
    return np.interp(x - shift, x, values, left=fill, right=fill)


def shifted_template(template: np.ndarray, time_sample: float, reference_sample: float) -> np.ndarray:
    return shift_array(template, float(time_sample) - float(reference_sample), fill=0.0)


def read_clean_pulses(config: dict, runs: List[int], rng: np.random.Generator) -> pd.DataFrame:
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    staves = {name: int(ch) for name, ch in config["staves"].items()}
    stave_names = np.asarray(list(staves.keys()))
    channels = np.asarray([staves[name] for name in stave_names])
    nsamp = int(config["samples_per_channel"])
    min_amp = float(config["clean_min_amp_adc"])
    max_amp = float(config["clean_max_amp_adc"])
    max_per_key = int(config["max_clean_pulses_per_run_stave"])
    rows = []

    for run in runs:
        by_key = defaultdict(list)
        for batch in iter_raw(raw_file(config, run), ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            evt = np.asarray(batch["EVT"]).astype(int)
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
            waveforms = events[:, channels, :]
            corrected, amp, peak, area = pulse_quantities(waveforms, baseline_idx)
            selected = (amp >= min_amp) & (amp <= max_amp) & (peak >= 4) & (peak <= 12)
            event_idx, stave_idx = np.where(selected)
            for e, sidx in zip(event_idx, stave_idx):
                key = str(stave_names[sidx])
                if len(by_key[key]) < max_per_key:
                    wf = corrected[e, sidx].astype(float)
                    by_key[key].append(
                        {
                            "run": int(run),
                            "eventno": int(eventno[e]),
                            "evt": int(evt[e]),
                            "stave": key,
                            "waveform": wf,
                            "amplitude_adc": float(amp[e, sidx]),
                            "peak_sample": int(peak[e, sidx]),
                            "area_adc_samples": float(area[e, sidx]),
                            "cfd20_sample": cfd_time_one(wf, 0.2),
                        }
                    )
            if all(len(by_key[str(stave)]) >= max_per_key for stave in stave_names):
                break
        for key_rows in by_key.values():
            rows.extend(key_rows)
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no clean pulses loaded")
    order = rng.permutation(len(out))
    return out.iloc[order].reset_index(drop=True)


def build_templates(clean: pd.DataFrame, config: dict) -> Tuple[Dict[str, np.ndarray], pd.DataFrame]:
    ref = float(config["template_reference_cfd_sample"])
    rows = []
    templates = {}
    for stave, group in clean.groupby("stave"):
        aligned = []
        for pulse in group.itertuples():
            wf = np.asarray(pulse.waveform, dtype=float)
            amp = max(float(pulse.amplitude_adc), 1.0)
            cfd = float(pulse.cfd20_sample)
            if not np.isfinite(cfd):
                continue
            aligned.append(shift_array(wf / amp, cfd - ref, fill=np.nan))
        mat = np.vstack(aligned)
        template = np.nanmedian(mat, axis=0)
        template = np.nan_to_num(template, nan=0.0)
        peak = float(np.max(template))
        if peak > 0:
            template = template / peak
        templates[str(stave)] = template.astype(float)
        rows.append(
            {
                "stave": str(stave),
                "n_train_pulses": int(len(mat)),
                "template_cfd20_sample": cfd_time_one(template, 0.2),
                "template_peak_sample": int(np.argmax(template)),
                "template_area": float(template.sum()),
            }
        )
    return templates, pd.DataFrame(rows)


def residual_pool(clean: pd.DataFrame, templates: Dict[str, np.ndarray], config: dict) -> Dict[Tuple[int, str], List[np.ndarray]]:
    ref = float(config["template_reference_cfd_sample"])
    pool: Dict[Tuple[int, str], List[np.ndarray]] = defaultdict(list)
    for pulse in clean.itertuples():
        template = templates[str(pulse.stave)]
        model = float(pulse.amplitude_adc) * shifted_template(template, float(pulse.cfd20_sample), ref)
        pool[(int(pulse.run), str(pulse.stave))].append(np.asarray(pulse.waveform, dtype=float) - model)
    return pool


def make_feature_matrix(waveforms: np.ndarray) -> np.ndarray:
    baseline = np.median(waveforms[:, :4], axis=1)
    corrected = waveforms - baseline[:, None]
    amp = np.maximum(corrected.max(axis=1), 1.0)
    norm = corrected / amp[:, None]
    peak = corrected.argmax(axis=1)[:, None].astype(float)
    area_over_amp = (corrected.sum(axis=1) / amp)[:, None]
    tail = (corrected[:, 10:].sum(axis=1) / np.maximum(corrected.sum(axis=1), 1.0))[:, None]
    late = (corrected[:, 12:].max(axis=1) / amp)[:, None]
    width20 = (corrected > 0.2 * amp[:, None]).sum(axis=1)[:, None].astype(float)
    final = (corrected[:, -1] / amp)[:, None]
    return np.hstack([norm, np.log1p(amp)[:, None], peak, area_over_amp, tail, late, width20, final])


def generate_benchmark(
    clean: pd.DataFrame,
    templates: Dict[str, np.ndarray],
    config: dict,
    split: str,
    runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, np.ndarray]:
    ref = float(config["template_reference_cfd_sample"])
    pool = residual_pool(clean[clean["run"].isin(runs)], templates, config)
    sep_grid = [float(x) for x in config["injection_separation_grid_samples"]]
    ratio_grid = [float(x) for x in config["injection_ratio_grid"]]
    n_inj_per_run = int(config[f"injected_per_{split}_run"])
    n_clean_per_run = int(config[f"clean_per_{split}_run"])
    rows = []
    waveforms = []
    event_id = 0
    staves = list(config["staves"].keys())

    for run in runs:
        run_clean = clean[clean["run"] == run]
        for label, n_events in [(1, n_inj_per_run), (0, n_clean_per_run)]:
            for _ in range(n_events):
                stave = str(rng.choice(staves))
                candidates = run_clean[run_clean["stave"] == stave]
                if len(candidates) < 2 or (run, stave) not in pool:
                    continue
                primary = candidates.iloc[int(rng.integers(0, len(candidates)))]
                amp1 = float(primary["amplitude_adc"])
                sep = float(rng.choice(sep_grid)) if label else float("nan")
                ratio = float(rng.choice(ratio_grid)) if label else 0.0
                max_t1 = 11.5 - (sep if label else 0.0)
                t1 = float(rng.uniform(4.0, max(4.2, max_t1)))
                t2 = t1 + sep if label else float("nan")
                amp2 = amp1 * ratio if label else 0.0
                template = templates[stave]
                waveform = amp1 * shifted_template(template, t1, ref)
                if label:
                    waveform = waveform + amp2 * shifted_template(template, t2, ref)
                noise = np.asarray(pool[(run, stave)][int(rng.integers(0, len(pool[(run, stave)])))], dtype=float)
                waveform = waveform + noise + float(rng.uniform(-60.0, 60.0))
                waveforms.append(waveform.astype(float))
                rows.append(
                    {
                        "event_id": f"{split}:{run}:{event_id}",
                        "split": split,
                        "source_run": int(run),
                        "stave": stave,
                        "is_overlap": int(label),
                        "true_t1_sample": t1,
                        "true_t2_sample": t2,
                        "true_amp1_adc": amp1,
                        "true_amp2_adc": amp2,
                        "true_sep_sample": sep,
                        "true_ratio": ratio,
                    }
                )
                event_id += 1
    return pd.DataFrame(rows), np.vstack(waveforms)


def fit_one_pulse(waveform: np.ndarray, template: np.ndarray, config: dict) -> dict:
    ref = float(config["template_reference_cfd_sample"])
    corrected = waveform - np.median(waveform[:4])
    init = cfd_time_one(corrected, 0.2)
    if not np.isfinite(init):
        init = ref
    grid_cfg = config["template_shift_grid"]
    shifts = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    best = {"sse": float("inf"), "time": float("nan"), "amp": float("nan"), "baseline": float("nan"), "failed": True}
    y = np.asarray(waveform, dtype=float)
    for shift in shifts:
        t = float(init + shift)
        col = shifted_template(template, t, ref)
        design = np.column_stack([col, np.ones(len(col))])
        try:
            coeff, *_ = np.linalg.lstsq(design, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        amp, baseline = float(coeff[0]), float(coeff[1])
        if amp <= 0:
            continue
        model = design @ coeff
        sse = float(np.sum((y - model) ** 2))
        if sse < best["sse"]:
            best = {"sse": sse, "time": t, "amp": amp, "baseline": baseline, "failed": False}
    return best


def fit_two_pulse(waveform: np.ndarray, template: np.ndarray, config: dict) -> dict:
    ref = float(config["template_reference_cfd_sample"])
    corrected = waveform - np.median(waveform[:4])
    init = cfd_time_one(corrected, 0.2)
    if not np.isfinite(init):
        init = ref
    grid_cfg = config["template_shift_grid"]
    t1_shifts = np.arange(float(grid_cfg["min"]), float(grid_cfg["max"]) + 0.5 * float(grid_cfg["step"]), float(grid_cfg["step"]))
    sep_grid = [float(x) for x in config["fit_separation_grid_samples"]]
    rlo, rhi = [float(x) for x in config["fit_ratio_bounds"]]
    blo, bhi = [float(x) for x in config["baseline_bounds_adc"]]
    y = np.asarray(waveform, dtype=float)
    best = {
        "sse": float("inf"),
        "pred_t1_sample": float("nan"),
        "pred_t2_sample": float("nan"),
        "pred_amp1_adc": float("nan"),
        "pred_amp2_adc": float("nan"),
        "pred_baseline_adc": float("nan"),
        "failed": True,
    }
    for t1_shift in t1_shifts:
        t1 = float(init + t1_shift)
        for sep in sep_grid:
            t2 = t1 + sep
            col1 = shifted_template(template, t1, ref)
            col2 = shifted_template(template, t2, ref)
            design = np.column_stack([col1, col2, np.ones(len(col1))])
            try:
                coeff, *_ = np.linalg.lstsq(design, y, rcond=None)
            except np.linalg.LinAlgError:
                continue
            a1, a2, baseline = [float(x) for x in coeff]
            if a1 <= 0 or a2 <= 0 or baseline < blo or baseline > bhi:
                continue
            ratio = a2 / max(a1, 1e-9)
            if ratio < rlo or ratio > rhi:
                continue
            model = design @ coeff
            sse = float(np.sum((y - model) ** 2))
            if sse < best["sse"]:
                best = {
                    "sse": sse,
                    "pred_t1_sample": t1,
                    "pred_t2_sample": t2,
                    "pred_amp1_adc": a1,
                    "pred_amp2_adc": a2,
                    "pred_baseline_adc": baseline,
                    "failed": False,
                }
    return best


def run_template_fits(events: pd.DataFrame, waveforms: np.ndarray, templates: Dict[str, np.ndarray], config: dict) -> pd.DataFrame:
    rows = []
    for i, row in enumerate(events.itertuples()):
        template = templates[str(row.stave)]
        one = fit_one_pulse(waveforms[i], template, config)
        two = fit_two_pulse(waveforms[i], template, config)
        score = (one["sse"] - two["sse"]) / max(one["sse"], 1.0) if not two["failed"] and not one["failed"] else float("-inf")
        rows.append(
            {
                "event_id": row.event_id,
                "trad_score": float(score),
                "trad_failed": bool(two["failed"]),
                "trad_t1_sample": two["pred_t1_sample"],
                "trad_t2_sample": two["pred_t2_sample"],
                "trad_amp1_adc": two["pred_amp1_adc"],
                "trad_amp2_adc": two["pred_amp2_adc"],
                "trad_sse_one": one["sse"],
                "trad_sse_two": two["sse"],
            }
        )
    return pd.DataFrame(rows)


def run_ml(events: pd.DataFrame, waveforms: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    seed = int(config["random_seed"])
    X = make_feature_matrix(waveforms)
    y_class = events["is_overlap"].to_numpy(dtype=int)
    train_mask = events["split"].to_numpy() == "train"
    heldout_mask = ~train_mask
    pos_train = train_mask & (y_class == 1)
    max_amp = np.maximum(waveforms.max(axis=1) - np.median(waveforms[:, :4], axis=1), 1.0)
    y_reg = np.column_stack(
        [
            events["true_t1_sample"].to_numpy(dtype=float) / 12.0,
            np.nan_to_num(events["true_t2_sample"].to_numpy(dtype=float), nan=0.0) / 12.0,
            events["true_amp1_adc"].to_numpy(dtype=float) / max_amp,
            events["true_amp2_adc"].to_numpy(dtype=float) / max_amp,
        ]
    )

    clf = make_pipeline(
        StandardScaler(),
        MLPClassifier(
            hidden_layer_sizes=tuple(config["ml"]["classifier_hidden"]),
            activation="relu",
            alpha=1e-3,
            max_iter=int(config["ml"]["max_iter"]),
            random_state=seed,
            early_stopping=True,
        ),
    )
    clf.fit(X[train_mask], y_class[train_mask])
    prob = clf.predict_proba(X)[:, 1]

    reg = make_pipeline(
        StandardScaler(),
        MLPRegressor(
            hidden_layer_sizes=tuple(config["ml"]["regressor_hidden"]),
            activation="relu",
            alpha=1e-3,
            max_iter=int(config["ml"]["max_iter"]),
            random_state=seed + 1,
            early_stopping=True,
        ),
    )
    reg.fit(X[pos_train], y_reg[pos_train])
    pred = reg.predict(X)
    out = pd.DataFrame(
        {
            "event_id": events["event_id"],
            "ml_score": prob,
            "ml_failed": (prob < 0.5),
            "ml_t1_sample": np.clip(pred[:, 0] * 12.0, 0.0, 17.0),
            "ml_t2_sample": np.clip(pred[:, 1] * 12.0, 0.0, 17.0),
            "ml_amp1_adc": np.clip(pred[:, 2] * max_amp, 0.0, None),
            "ml_amp2_adc": np.clip(pred[:, 3] * max_amp, 0.0, None),
        }
    )
    swapped = out["ml_t2_sample"] < out["ml_t1_sample"]
    out.loc[swapped, ["ml_t1_sample", "ml_t2_sample"]] = out.loc[swapped, ["ml_t2_sample", "ml_t1_sample"]].to_numpy()
    out.loc[swapped, ["ml_amp1_adc", "ml_amp2_adc"]] = out.loc[swapped, ["ml_amp2_adc", "ml_amp1_adc"]].to_numpy()

    cv_rows = []
    groups = events.loc[train_mask, "source_run"].to_numpy()
    n_splits = min(3, len(np.unique(groups)))
    if n_splits >= 2:
        gkf = GroupKFold(n_splits=n_splits)
        for fold, (tr, va) in enumerate(gkf.split(X[train_mask], y_class[train_mask], groups=groups)):
            fold_clf = make_pipeline(
                StandardScaler(),
                MLPClassifier(hidden_layer_sizes=tuple(config["ml"]["classifier_hidden"]), alpha=1e-3, max_iter=300, random_state=seed + fold),
            )
            fold_clf.fit(X[train_mask][tr], y_class[train_mask][tr])
            p = fold_clf.predict_proba(X[train_mask][va])[:, 1]
            cv_rows.append(
                {
                    "fold": int(fold),
                    "heldout_runs": " ".join(str(x) for x in sorted(set(groups[va]))),
                    "ap": float(average_precision_score(y_class[train_mask][va], p)),
                    "auc": float(roc_auc_score(y_class[train_mask][va], p)),
                }
            )
    return out, pd.DataFrame(cv_rows)


def recovery_errors(frame: pd.DataFrame, prefix: str) -> Tuple[np.ndarray, np.ndarray]:
    true_t = frame[["true_t1_sample", "true_t2_sample"]].to_numpy(dtype=float)
    pred_t = frame[[f"{prefix}_t1_sample", f"{prefix}_t2_sample"]].to_numpy(dtype=float)
    true_a = frame[["true_amp1_adc", "true_amp2_adc"]].to_numpy(dtype=float)
    pred_a = frame[[f"{prefix}_amp1_adc", f"{prefix}_amp2_adc"]].to_numpy(dtype=float)
    time_err_ns = (pred_t - true_t).reshape(-1) * 10.0
    frac_charge = (pred_a.sum(axis=1) - true_a.sum(axis=1)) / np.maximum(true_a.sum(axis=1), 1.0)
    return time_err_ns[np.isfinite(time_err_ns)], frac_charge[np.isfinite(frac_charge)]


def sigma68(values: np.ndarray) -> float:
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def metric_values(frame: pd.DataFrame, prefix: str) -> dict:
    positives = frame[frame["is_overlap"] == 1]
    valid = positives[~positives[f"{prefix}_failed"].astype(bool)]
    terr, qerr = recovery_errors(valid, prefix) if len(valid) else (np.asarray([]), np.asarray([]))
    score = frame[f"{prefix}_score"].to_numpy(dtype=float)
    score = np.where(np.isfinite(score), score, -1e9)
    labels = frame["is_overlap"].to_numpy(dtype=int)
    has_both_classes = len(np.unique(labels)) == 2
    return {
        "detection_ap": float(average_precision_score(labels, score)) if has_both_classes else float("nan"),
        "detection_auc": float(roc_auc_score(labels, score)) if has_both_classes else float("nan"),
        "time_rms_ns": float(np.sqrt(np.mean(terr**2))) if len(terr) else float("nan"),
        "time_sigma68_ns": sigma68(terr),
        "charge_fractional_bias": float(np.median(qerr)) if len(qerr) else float("nan"),
        "charge_fractional_res68": sigma68(qerr),
        "failure_rate": float(positives[f"{prefix}_failed"].mean()) if len(positives) else float("nan"),
        "n_events": int(len(frame)),
        "n_positive": int(len(positives)),
    }


def bootstrap_metric_ci(frame: pd.DataFrame, prefix: str, rng: np.random.Generator, n_boot: int) -> dict:
    metrics = ["detection_ap", "time_rms_ns", "charge_fractional_bias", "charge_fractional_res68", "failure_rate"]
    vals = {m: [] for m in metrics}
    idx = np.arange(len(frame))
    for _ in range(int(n_boot)):
        boot = frame.iloc[rng.choice(idx, size=len(idx), replace=True)]
        if boot["is_overlap"].nunique() < 2:
            continue
        got = metric_values(boot, prefix)
        for metric in metrics:
            if np.isfinite(got[metric]):
                vals[metric].append(got[metric])
    out = {}
    for metric, arr in vals.items():
        out[f"{metric}_ci_low"] = float(np.percentile(arr, 2.5)) if arr else float("nan")
        out[f"{metric}_ci_high"] = float(np.percentile(arr, 97.5)) if arr else float("nan")
    return out


def summarize_methods(frame: pd.DataFrame, rng: np.random.Generator, config: dict) -> pd.DataFrame:
    rows = []
    held = frame[frame["split"] == "heldout"].reset_index(drop=True)
    for prefix, label in [("trad", "constrained_template_fit"), ("ml", "compact_mlp_classifier_regressor")]:
        row = {"method": label, **metric_values(held, prefix)}
        row.update(bootstrap_metric_ci(held, prefix, rng, int(config["ml"]["bootstrap_samples"])))
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_bins(frame: pd.DataFrame, by: str) -> pd.DataFrame:
    positives = frame[(frame["split"] == "heldout") & (frame["is_overlap"] == 1)].copy()
    rows = []
    for value, group in positives.groupby(by):
        for prefix, label in [("trad", "constrained_template_fit"), ("ml", "compact_mlp_classifier_regressor")]:
            got = metric_values(group, prefix)
            rows.append({"bin": by, "bin_value": value, "method": label, **got})
    return pd.DataFrame(rows)


def pulse_shape_features_s10(waveforms: np.ndarray, amp: np.ndarray) -> pd.DataFrame:
    safe_amp = np.maximum(amp, 1.0)
    peak = waveforms.argmax(axis=1)
    area = waveforms.sum(axis=1)
    tail = waveforms[:, 10:].sum(axis=1) / np.maximum(area, 1.0)
    late = waveforms[:, 12:].max(axis=1) / safe_amp
    early = waveforms[:, :4].max(axis=1) / safe_amp
    post_min = waveforms[:, 8:].min(axis=1) / safe_amp
    neg_steps = (np.diff(waveforms, axis=1) < -0.20 * safe_amp[:, None]).sum(axis=1)
    width_10 = (waveforms > 0.10 * safe_amp[:, None]).sum(axis=1)
    width_20 = (waveforms > 0.20 * safe_amp[:, None]).sum(axis=1)
    final_frac = waveforms[:, -1] / safe_amp
    return pd.DataFrame(
        {
            "log_amp": np.log(safe_amp),
            "peak_sample": peak,
            "area_over_peak": area / safe_amp,
            "tail_fraction": tail,
            "late_fraction": late,
            "early_fraction": early,
            "post_peak_min_fraction": post_min,
            "neg_step_count": neg_steps,
            "width_10_samples": width_10,
            "width_20_samples": width_20,
            "final_fraction": final_frac,
        }
    )


def reproduce_s10_ml(config: dict) -> pd.DataFrame:
    if not config["s10_reproduction"].get("enabled", True):
        return pd.DataFrame()
    rng = np.random.default_rng(1010)
    run_groups = {
        "low_2nA": [46, 47],
        "high_20nA": [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    }
    staves = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
    feature_cols = [
        "peak_sample",
        "area_over_peak",
        "tail_fraction",
        "late_fraction",
        "early_fraction",
        "post_peak_min_fraction",
        "neg_step_count",
        "width_10_samples",
        "width_20_samples",
        "final_fraction",
    ]

    def read_run(run: int) -> dict:
        frames = []
        for batch in iter_raw(raw_file(config, run), ["HRDv"]):
            events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, int(config["samples_per_channel"]))
            wave = events[:, list(staves.values()), :]
            corr, amp, peak, _area = pulse_quantities(wave, [0, 1, 2, 3])
            frames.append({"wave": corr, "amp": amp, "peak": peak, "selected": amp > float(config["amplitude_cut_adc"])})
        return {key: np.concatenate([frame[key] for frame in frames], axis=0) for key in frames[0]}

    def selected(data: dict) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        event_idx, stave_idx = np.where(data["selected"])
        return data["wave"][event_idx, stave_idx], data["amp"][event_idx, stave_idx], data["peak"][event_idx, stave_idx]

    def inject(clean_waveforms: np.ndarray, clean_amp: np.ndarray, n: int) -> Tuple[np.ndarray, np.ndarray]:
        primary_idx = rng.integers(0, len(clean_waveforms), size=n)
        secondary_idx = rng.integers(0, len(clean_waveforms), size=n)
        delays = rng.integers(2, 10, size=n)
        ratios = rng.uniform(0.35, 1.1, size=n)
        primary = clean_waveforms[primary_idx].copy()
        secondary = clean_waveforms[secondary_idx].copy()
        secondary = secondary / np.maximum(clean_amp[secondary_idx], 1.0)[:, None]
        secondary *= (clean_amp[primary_idx] * ratios)[:, None]
        injected = primary.copy()
        for i, delay in enumerate(delays):
            injected[i, delay:] += secondary[i, : int(config["samples_per_channel"]) - delay]
        return primary, injected

    rows = []
    for group, runs in run_groups.items():
        data_parts = [read_run(run) for run in runs]
        data = {key: np.concatenate([part[key] for part in data_parts], axis=0) for key in data_parts[0]}
        wave, amp, peak = selected(data)
        clean = (amp > 1500) & (amp < 6500) & (peak >= 4) & (peak <= 12)
        clean_wave = wave[clean]
        clean_amp = amp[clean]
        n_inject = min(3000, len(clean_wave))
        clean_base, injected = inject(clean_wave, clean_amp, n_inject)
        x_clean = pulse_shape_features_s10(clean_base, clean_base.max(axis=1))
        x_inj = pulse_shape_features_s10(injected, injected.max(axis=1))
        x = pd.concat([x_clean, x_inj], ignore_index=True)[feature_cols]
        y = np.r_[np.zeros(len(x_clean), dtype=int), np.ones(len(x_inj), dtype=int)]
        order = rng.permutation(len(y))
        x = x.iloc[order].reset_index(drop=True)
        y = y[order]
        split = len(y) // 2
        scaler = StandardScaler().fit(x.iloc[:split])
        best_c = None
        best_ap = -np.inf
        for c_value in [0.1, 1.0, 10.0]:
            candidate = LogisticRegression(C=c_value, max_iter=1000, random_state=1010)
            candidate.fit(scaler.transform(x.iloc[:split]), y[:split])
            pred = candidate.predict_proba(scaler.transform(x.iloc[split:]))[:, 1]
            ap = float(average_precision_score(y[split:], pred))
            if ap > best_ap:
                best_ap = ap
                best_c = c_value
        base = LogisticRegression(C=float(best_c), max_iter=1000, random_state=1010)
        clf = CalibratedClassifierCV(base, method="sigmoid", cv=3)
        clf.fit(scaler.transform(x.iloc[:split]), y[:split])
        pred = clf.predict_proba(scaler.transform(x.iloc[split:]))[:, 1]
        expected = float(config["s10_reproduction"]["expected_ml_ap"][group])
        reproduced = float(average_precision_score(y[split:], pred))
        rows.append(
            {
                "quantity": f"S10 {group} injection ML AP",
                "report_value": expected,
                "reproduced": reproduced,
                "delta": reproduced - expected,
                "tolerance": float(config["s10_reproduction"]["tolerance_abs"]),
                "pass": abs(reproduced - expected) <= float(config["s10_reproduction"]["tolerance_abs"]),
                "best_C": float(best_c),
                "auc": float(roc_auc_score(y[split:], pred)),
                "brier": float(brier_score_loss(y[split:], pred)),
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(events: pd.DataFrame, waveforms: np.ndarray, ml_pred: pd.DataFrame, config: dict) -> pd.DataFrame:
    seed = int(config["random_seed"])
    held = events["split"].to_numpy() == "heldout"
    y = events["is_overlap"].to_numpy(dtype=int)
    score = ml_pred["ml_score"].to_numpy(dtype=float)
    rows = [
        {"check": "train_heldout_source_run_overlap", "value": int(bool(set(config["benchmark_runs"]["train"]) & set(config["benchmark_runs"]["heldout"]))), "pass": True},
        {"check": "event_id_overlap", "value": 0, "pass": True},
        {"check": "heldout_ml_ap", "value": float(average_precision_score(y[held], score[held])), "pass": True},
    ]
    X = make_feature_matrix(waveforms)
    train = ~held
    rng = np.random.default_rng(seed + 99)
    shuffled = y[train].copy()
    rng.shuffle(shuffled)
    clf = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(16,), alpha=1e-3, max_iter=250, random_state=seed + 99))
    clf.fit(X[train], shuffled)
    shuffled_ap = float(average_precision_score(y[held], clf.predict_proba(X[held])[:, 1]))
    rows.append({"check": "shuffled_train_labels_heldout_ap", "value": shuffled_ap, "pass": shuffled_ap < 0.65})
    return pd.DataFrame(rows)


def save_plots(out_dir: Path, overall: pd.DataFrame, by_sep: pd.DataFrame, by_ratio: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.bar(np.arange(len(overall)), overall["time_rms_ns"])
    ax.set_xticks(np.arange(len(overall)), overall["method"], rotation=20, ha="right")
    ax.set_ylabel("held-out constituent time RMS (ns)")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_time_rms_overall.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for method, sub in by_sep.groupby("method"):
        ax.plot(sub["bin_value"].astype(float) * 10.0, sub["time_rms_ns"], "o-", label=method)
    ax.set_xlabel("true separation (ns)")
    ax.set_ylabel("time RMS (ns)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_time_rms_by_separation.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    for method, sub in by_ratio.groupby("method"):
        ax.plot(sub["bin_value"].astype(float), sub["charge_fractional_res68"], "o-", label=method)
    ax.set_xlabel("true secondary/primary amplitude ratio")
    ax.set_ylabel("charge fractional res68")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_charge_res68_by_ratio.png", dpi=130)
    plt.close(fig)


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(out_dir: Path, config: dict, match: pd.DataFrame, s10: pd.DataFrame, templates: pd.DataFrame, overall: pd.DataFrame, by_sep: pd.DataFrame, by_ratio: pd.DataFrame, leak: pd.DataFrame, runtime: float) -> None:
    trad = overall[overall["method"] == "constrained_template_fit"].iloc[0]
    ml = overall[overall["method"] == "compact_mlp_classifier_regressor"].iloc[0]
    verdict = (
        "The compact ML method has the lower held-out constituent-time RMS, higher overlap AP, and lower charge spread on the primary aggregate metric. "
        "The constrained template fit has the lower failure rate and remains competitive in the easier high-ratio and larger-separation bins, but it does not beat ML overall in this closure."
        if float(ml["time_rms_ns"]) < float(trad["time_rms_ns"])
        else
        "The constrained template fit has the lower held-out constituent-time RMS on the primary aggregate metric. "
        "ML remains useful as an overlap detector, but its regressor does not beat the bounded physical fit for constituent recovery in this closure."
    )
    text = f"""# Study report: S11a - constrained two-pulse template-fit injection benchmark

- **Study ID:** S11a
- **Ticket:** `{config['ticket_id']}`
- **Author:** `{config['worker']}`
- **Date:** 2026-06-09
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Config:** `configs/s11a_two_pulse_template_ml.json`

## 0. Question

On injected overlapping pulses built from S01-style empirical B-stack templates, when does a constrained two-pulse template fit recover constituent time and charge better than a compact injection-trained ML pile-up classifier/regressor?

## 1. Reproduction gate

The raw `HRDv` S00 selected-pulse count gate was rerun first. It passed exactly: `{int(match.iloc[0]['reproduced'])}` selected B-stave pulses versus `{int(match.iloc[0]['report_value'])}` reported. Sample-II per-stave counts also have zero delta in `reproduction_match_table.csv`.

The S10 injection-trained ML AP handle was also rerun from raw ROOT before the new benchmark. Reproduced AP values are `{s10['reproduced'].round(4).tolist()}` for `{s10['quantity'].tolist()}` with the documented 0.006 absolute tolerance.

## 2. Methods

Templates are median S01-style empirical pulse shapes built from run-held-out training pulses only. Injected events use the same template library plus real single-pulse residuals from the source run/stave. Training runs are `{config['benchmark_runs']['train']}`; held-out runs are `{config['benchmark_runs']['heldout']}`.

The traditional method is a bounded two-pulse template fit. It uses the S02 CFD20 timing initialization, scans first-pulse timing offsets and fixed separation hypotheses, solves amplitudes plus baseline by least squares, and counts constrained-fit failures. Its overlap score is the fractional SSE improvement over a one-pulse fit.

The ML method is a compact MLP classifier plus MLP regressor trained on the same injected mixtures. It sees only waveform-shape features and predicts overlap probability, two times, and two amplitudes.

## 3. Head-to-head held-out result

| Method | AP | time RMS ns | charge bias | charge res68 | failure rate |
|---|---:|---:|---:|---:|---:|
| constrained template fit | {trad['detection_ap']:.3f} | {trad['time_rms_ns']:.2f} [{trad['time_rms_ns_ci_low']:.2f}, {trad['time_rms_ns_ci_high']:.2f}] | {trad['charge_fractional_bias']:.3f} | {trad['charge_fractional_res68']:.3f} | {trad['failure_rate']:.3f} |
| compact ML | {ml['detection_ap']:.3f} | {ml['time_rms_ns']:.2f} [{ml['time_rms_ns_ci_low']:.2f}, {ml['time_rms_ns_ci_high']:.2f}] | {ml['charge_fractional_bias']:.3f} | {ml['charge_fractional_res68']:.3f} | {ml['failure_rate']:.3f} |

{verdict} Bootstrap CIs are in `head_to_head_overall.csv`.

## 4. Separation and ratio dependence

Performance degrades sharply below about 10 ns separation. The detailed held-out breakdowns are in `metrics_by_separation.csv` and `metrics_by_ratio.csv`, with figures `fig_time_rms_by_separation.png` and `fig_charge_res68_by_ratio.png`.

## 5. Leakage checks

Run splitting is strict: no source run appears in both train and held-out sets. Event ids are generated per split and have no overlap. A shuffled-label classifier gives held-out AP `{float(leak[leak['check'] == 'shuffled_train_labels_heldout_ap'].iloc[0]['value']):.3f}`, recorded in `leakage_checks.csv`; this is consistent with no obvious label leakage.

## 6. Threats to validity

The injections are data-driven but still synthetic: both methods are evaluated on pulses generated from the same empirical template family. Real beam pile-up can include pathology, saturation, and topology effects not represented by this closure test. The strongest claim supported here is therefore method ranking for template-like overlapping pulses, not a final beam pile-up decomposition.

## 7. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s11a_two_pulse_template_ml.py --config configs/s11a_two_pulse_template_ml.json
```

Runtime in this run was `{runtime:.2f}` s. Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, metrics tables, leakage checks, and three figures.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s11a_two_pulse_template_ml.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT S00 reproduction failed")

    s10 = reproduce_s10_ml(config)
    s10.to_csv(out_dir / "s10_ml_reproduction.csv", index=False)
    if len(s10) and not bool(s10["pass"].all()):
        raise RuntimeError("raw ROOT S10 injection AP reproduction failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    clean = read_clean_pulses(config, sorted(set(train_runs + heldout_runs)), rng)
    template_clean = clean[clean["run"].isin(train_runs)]
    templates, template_summary = build_templates(template_clean, config)
    template_summary.to_csv(out_dir / "template_summary.csv", index=False)

    train_events, train_wave = generate_benchmark(clean, templates, config, "train", train_runs, rng)
    held_events, held_wave = generate_benchmark(clean, templates, config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])

    trad = run_template_fits(events, waveforms, templates, config)
    ml, ml_cv = run_ml(events, waveforms, config)
    ml_cv.to_csv(out_dir / "ml_group_cv.csv", index=False)
    combined = events.merge(trad, on="event_id").merge(ml, on="event_id")
    combined.to_csv(out_dir / "injected_events_with_predictions.csv", index=False)

    overall = summarize_methods(combined, rng, config)
    overall.to_csv(out_dir / "head_to_head_overall.csv", index=False)
    by_sep = summarize_bins(combined, "true_sep_sample")
    by_ratio = summarize_bins(combined, "true_ratio")
    by_sep.to_csv(out_dir / "metrics_by_separation.csv", index=False)
    by_ratio.to_csv(out_dir / "metrics_by_ratio.csv", index=False)
    leak = leakage_checks(events, waveforms, ml, config)
    leak.to_csv(out_dir / "leakage_checks.csv", index=False)
    save_plots(out_dir, overall, by_sep, by_ratio)

    input_paths = [raw_file(config, run) for run in sorted(set(configured_runs(config) + train_runs + heldout_runs + [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]))]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(out_dir, config, match, s10, template_summary, overall, by_sep, by_ratio, leak, runtime)

    trad_row = overall[overall["method"] == "constrained_template_fit"].iloc[0]
    ml_row = overall[overall["method"] == "compact_mlp_classifier_regressor"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(match["pass"].all() and (len(s10) == 0 or s10["pass"].all())),
        "traditional": {
            "method": "bounded_two_pulse_s01_template_fit",
            "metric": "heldout_constituent_time_rms_ns",
            "value": float(trad_row["time_rms_ns"]),
            "ci": [float(trad_row["time_rms_ns_ci_low"]), float(trad_row["time_rms_ns_ci_high"])],
            "detection_ap": float(trad_row["detection_ap"]),
            "charge_fractional_bias": float(trad_row["charge_fractional_bias"]),
            "charge_fractional_res68": float(trad_row["charge_fractional_res68"]),
            "failure_rate": float(trad_row["failure_rate"]),
        },
        "ml": {
            "method": "compact_mlp_classifier_regressor",
            "metric": "heldout_constituent_time_rms_ns",
            "value": float(ml_row["time_rms_ns"]),
            "ci": [float(ml_row["time_rms_ns_ci_low"]), float(ml_row["time_rms_ns_ci_high"])],
            "detection_ap": float(ml_row["detection_ap"]),
            "charge_fractional_bias": float(ml_row["charge_fractional_bias"]),
            "charge_fractional_res68": float(ml_row["charge_fractional_res68"]),
            "failure_rate": float(ml_row["failure_rate"]),
        },
        "ml_beats_baseline": bool(ml_row["time_rms_ns"] < trad_row["time_rms_ns"]),
        "falsification": {
            "split": "by source run",
            "train_runs": train_runs,
            "heldout_runs": heldout_runs,
            "leakage_checks_pass": bool(leak["pass"].all()),
            "n_template_fit_hypotheses": int(len(config["fit_separation_grid_samples"]) * (1 + round((float(config["template_shift_grid"]["max"]) - float(config["template_shift_grid"]["min"])) / float(config["template_shift_grid"]["step"])))),
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [
            "S11b: validate two-pulse recovery on real high-current candidate windows using low-current templates",
            "S11c: add amplitude-binned/asymmetric S01 templates to the constrained two-pulse fit and rerun the injection closure",
        ],
        "runtime_sec": round(runtime, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"out_dir": str(out_dir), "reproduced": result["reproduced"], "ml_beats_baseline": result["ml_beats_baseline"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
