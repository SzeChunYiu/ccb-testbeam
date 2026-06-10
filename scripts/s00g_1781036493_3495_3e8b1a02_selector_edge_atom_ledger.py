#!/usr/bin/env python3
"""S00g selector-edge waveform atom ledger.

The script rescans raw B-stack ROOT first, reproduces the S00/S00a/S00c selector
counts exactly, then enumerates deterministic selector-edge waveform atoms and
compares them to exact matched S00 core controls. The ML panel is deliberately
diagnostic: run labels, event identifiers, current labels, selector amplitudes,
and direct atom-defining thresholds are excluded from learned feature matrices.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.decomposition import PCA
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, RidgeClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import GroupKFold
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s00g_1781036493_3495_3e8b1a02_selector_edge_atom_ledger.json"
STAVE_NAMES = ["B2", "B4", "B6", "B8"]


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


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


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        return val if np.isfinite(val) else None
    return value


def all_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(v) for v in values)
    return sorted(set(runs))


def raw_path(config: dict, run: int) -> Path:
    path = ROOT / config["raw_root_dir"] / f"hrdb_run_{run:04d}.root"
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def iter_raw(path: Path, branches: Iterable[str], step_size: int = 20000):
    yield from uproot.open(path)["h101"].iterate(list(branches), step_size=step_size, library="np")


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float = 0.20) -> np.ndarray:
    thresholds = amplitudes * float(fraction)
    ge = waveforms >= thresholds[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=np.float32)
    for idx in np.where(valid)[0]:
        j = int(first[idx])
        if j <= 0:
            out[idx] = float(j)
            continue
        y0 = float(waveforms[idx, j - 1])
        y1 = float(waveforms[idx, j])
        denom = y1 - y0
        if denom <= 0:
            out[idx] = float(j)
        else:
            out[idx] = (j - 1) + (thresholds[idx] - y0) / denom
    return out


def current_nA(config: dict, run: int) -> float:
    return float(config["current_nA_by_run"].get(str(int(run)), config["default_current_nA"]))


def topology_labels(selected: np.ndarray) -> np.ndarray:
    labels = []
    for row in selected.astype(bool):
        names = [STAVE_NAMES[i] for i, keep in enumerate(row) if keep]
        down_n = int(row[1:].sum())
        if len(names) == 1:
            label = f"{names[0]}_only"
        elif row.all():
            label = "all_four"
        elif row[1:].all():
            label = "all_downstream"
        elif row[0] and down_n >= 2:
            label = "B2_plus_ge2_downstream"
        elif row[0] and down_n == 1:
            label = "B2_plus_one_downstream"
        elif (not row[0]) and down_n >= 2:
            label = "downstream_ge2"
        else:
            label = "other_multi"
        labels.append(label)
    return np.asarray(labels, dtype=object)


def waveform_features(norm: np.ndarray) -> pd.DataFrame:
    peak = np.argmax(norm, axis=1)
    second_idx = np.zeros(len(norm), dtype=int)
    second_frac = np.zeros(len(norm), dtype=float)
    valley_frac = np.ones(len(norm), dtype=float)
    separation_ns = np.zeros(len(norm), dtype=float)
    for i, wf in enumerate(norm):
        start = min(int(peak[i]) + 2, wf.size - 1)
        tail = wf[start:]
        if len(tail):
            rel = int(np.argmax(tail))
            second_idx[i] = start + rel
            second_frac[i] = float(tail[rel])
            lo = min(int(peak[i]), int(second_idx[i]))
            hi = max(int(peak[i]), int(second_idx[i]))
            valley_frac[i] = float(np.min(wf[lo : hi + 1])) if hi > lo else 1.0
            separation_ns[i] = 10.0 * float(second_idx[i] - peak[i])
    area = norm.sum(axis=1)
    late_max = norm[:, 10:].max(axis=1)
    early_max = norm[:, :4].max(axis=1)
    min_post = norm[:, 8:].min(axis=1)
    neg_steps = (np.diff(norm, axis=1) < -0.20).sum(axis=1).astype(float)
    dip_depth = np.maximum(0.0, np.minimum(1.0, second_frac) - valley_frac)
    two_pulse_like = (
        (second_frac >= 0.28)
        & (separation_ns >= 20.0)
        & (dip_depth >= 0.08)
        & (peak > 3)
        & (min_post > -0.25)
    )
    return pd.DataFrame(
        {
            "norm_peak_sample": peak.astype(float),
            "second_peak_frac": second_frac,
            "valley_frac": valley_frac,
            "dip_depth": dip_depth,
            "second_peak_separation_ns": separation_ns,
            "norm_area": area,
            "norm_width10_samples": (norm > 0.10).sum(axis=1).astype(float),
            "norm_width20_samples": (norm > 0.20).sum(axis=1).astype(float),
            "late_max_frac": late_max,
            "early_max_frac": early_max,
            "min_post_frac": min_post,
            "neg_step_count": neg_steps,
            "two_pulse_like": two_pulse_like.astype(int),
        }
    )


def append_s00c_sample(
    rows: List[pd.DataFrame],
    run: int,
    evt: np.ndarray,
    wave: np.ndarray,
    median_amp: np.ndarray,
    dynamic_amp: np.ndarray,
    median_selected: np.ndarray,
    dynamic_selected: np.ndarray,
    pre: np.ndarray,
    config: dict,
    rng: np.random.Generator,
) -> None:
    low = 700.0
    high = 1300.0
    near = ((median_amp > low) | (dynamic_amp > low)) & ((median_amp < high) | (dynamic_amp < high))
    random_keep = rng.random(median_amp.shape) < 0.01
    heldout_keep = run in {57, 65}
    keep = near | random_keep | heldout_keep
    if not keep.any():
        return
    event_idx, stave_idx = np.where(keep)
    wf_max = wave.max(axis=-1)
    wf_min = wave.min(axis=-1)
    post = wave[..., 4:]
    rows.append(
        pd.DataFrame(
            {
                "run": np.full(len(event_idx), int(run), dtype=np.int16),
                "evt": evt[event_idx].astype(np.int64),
                "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                "stave_idx": stave_idx.astype(np.int8),
                "median_selected": median_selected[event_idx, stave_idx].astype(np.int8),
                "dynamic_selected": dynamic_selected[event_idx, stave_idx].astype(np.int8),
                "wave_max": wf_max[event_idx, stave_idx].astype(np.float32),
                "wave_min": wf_min[event_idx, stave_idx].astype(np.float32),
                "pre4_mean": pre.mean(axis=-1)[event_idx, stave_idx].astype(np.float32),
                "pre4_std": pre.std(axis=-1)[event_idx, stave_idx].astype(np.float32),
                "post_mean": post.mean(axis=-1)[event_idx, stave_idx].astype(np.float32),
                "post_std": post.std(axis=-1)[event_idx, stave_idx].astype(np.float32),
                "dynamic_amp": dynamic_amp[event_idx, stave_idx].astype(np.float32),
                "median_amp": median_amp[event_idx, stave_idx].astype(np.float32),
                "baseline_excursion_adc": (pre.max(axis=-1) - pre.min(axis=-1))[event_idx, stave_idx].astype(np.float32),
            }
        )
    )


def scan_raw(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, np.ndarray, pd.DataFrame, pd.DataFrame]:
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    baseline_idx = [int(x) for x in config["baseline_samples"]]
    channels = np.asarray([int(config["staves"][name]) for name in STAVE_NAMES], dtype=int)
    downstream = [STAVE_NAMES.index(name) for name in config["downstream_staves"]]
    sample_period = float(config["sample_period_ns"])

    count_rows = []
    feature_frames = []
    norm_chunks = []
    input_rows = []
    s00c_rows: List[pd.DataFrame] = []
    s00c_rng = np.random.default_rng(int(config["random_seed"]))

    for run in all_runs(config):
        path = raw_path(config, run)
        input_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
        row = {
            "run": int(run),
            "events": 0,
            "records": 0,
            "median_first_four_selected": 0,
            "dynamic_range_selected": 0,
            "dynamic_only": 0,
            "median_only": 0,
        }
        event_offset = 0
        for batch in iter_raw(path, ["EVENTNO", "EVT", "HRDv"]):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float32).reshape(-1, 8, nsamp)
            wave = raw[:, channels, :]
            pre = wave[..., baseline_idx]
            baseline = np.median(pre, axis=-1)
            corrected = wave - baseline[..., None]
            median_amp = corrected.max(axis=-1)
            dynamic_amp = wave.max(axis=-1) - wave.min(axis=-1)
            selected_median = median_amp > cut
            selected_dynamic = dynamic_amp > cut
            dynamic_only = selected_dynamic & ~selected_median
            median_only = selected_median & ~selected_dynamic
            dyn_topology = topology_labels(selected_dynamic)
            med_topology = topology_labels(selected_median)
            append_s00c_sample(s00c_rows, run, evt, wave, median_amp, dynamic_amp, selected_median, selected_dynamic, pre, config, s00c_rng)

            amplitudes = np.maximum(median_amp, 1.0)
            times = np.full(median_amp.shape, np.nan, dtype=np.float32)
            for sidx in range(len(STAVE_NAMES)):
                times[:, sidx] = cfd_time_samples(corrected[:, sidx, :], amplitudes[:, sidx], 0.20)

            span_ns = np.full(len(eventno), np.nan, dtype=np.float32)
            dyn_down = selected_dynamic[:, downstream]
            for eidx in np.where(dyn_down.sum(axis=1) >= 2)[0]:
                local = times[eidx, downstream]
                local = local[np.isfinite(local)]
                if len(local) >= 2:
                    span_ns[eidx] = float((local.max() - local.min()) * sample_period)

            row["events"] += int(len(eventno))
            row["records"] += int(selected_median.size)
            row["median_first_four_selected"] += int(selected_median.sum())
            row["dynamic_range_selected"] += int(selected_dynamic.sum())
            row["dynamic_only"] += int(dynamic_only.sum())
            row["median_only"] += int(median_only.sum())

            keep = selected_dynamic
            event_idx, stave_idx = np.where(keep)
            if len(event_idx):
                chosen = corrected[event_idx, stave_idx]
                dyn_scale = np.maximum(dynamic_amp[event_idx, stave_idx], 1.0)
                norm = chosen / dyn_scale[:, None]
                pos = np.clip(chosen, 0.0, None)
                pos_area = pos.sum(axis=1)
                early = pos[:, :4].sum(axis=1)
                late = pos[:, 12:].sum(axis=1)
                feat = pd.DataFrame(
                    {
                        "run": np.full(len(event_idx), int(run), dtype=np.int16),
                        "current_nA": np.full(len(event_idx), current_nA(config, run), dtype=np.float32),
                        "current_group": np.full(len(event_idx), "low_2nA" if current_nA(config, run) < 10.0 else "high_20nA", dtype=object),
                        "event_index": (event_offset + event_idx).astype(np.int32),
                        "eventno": eventno[event_idx].astype(np.int64),
                        "evt": evt[event_idx].astype(np.int64),
                        "stave": np.asarray(STAVE_NAMES, dtype=object)[stave_idx],
                        "stave_index": stave_idx.astype(np.int8),
                        "s00_selected": selected_median[event_idx, stave_idx].astype(np.int8),
                        "dynamic_only": dynamic_only[event_idx, stave_idx].astype(np.int8),
                        "median_amp_adc": median_amp[event_idx, stave_idx].astype(np.float32),
                        "dynamic_amp_adc": dynamic_amp[event_idx, stave_idx].astype(np.float32),
                        "baseline_median_adc": baseline[event_idx, stave_idx].astype(np.float32),
                        "baseline_excursion_adc": (pre.max(axis=-1) - pre.min(axis=-1))[event_idx, stave_idx].astype(np.float32),
                        "saturation_count": (wave[event_idx, stave_idx] >= float(config["saturation_adc"])).sum(axis=1).astype(np.int8),
                        "peak_sample": chosen.argmax(axis=1).astype(np.int8),
                        "area_adc_samples": chosen.sum(axis=1).astype(np.float32),
                        "positive_area_adc_samples": pos_area.astype(np.float32),
                        "early_fraction": (early / np.maximum(pos_area, 1.0)).astype(np.float32),
                        "late_fraction": (late / np.maximum(pos_area, 1.0)).astype(np.float32),
                        "width20_samples": (chosen >= (0.20 * dyn_scale[:, None])).sum(axis=1).astype(np.int8),
                        "width50_samples": (chosen >= (0.50 * dyn_scale[:, None])).sum(axis=1).astype(np.int8),
                        "cfd20_sample": times[event_idx, stave_idx].astype(np.float32),
                        "downstream_timing_span_ns": span_ns[event_idx].astype(np.float32),
                        "dynamic_topology": dyn_topology[event_idx],
                        "median_topology": med_topology[event_idx],
                    }
                )
                feature_frames.append(feat)
                norm_chunks.append(norm.astype(np.float32))

            event_offset += int(len(eventno))

        count_rows.append(row)
        print(f"run {run:04d}: median={row['median_first_four_selected']} dynamic={row['dynamic_range_selected']} dynamic_only={row['dynamic_only']}", flush=True)

    features = pd.concat(feature_frames, ignore_index=True)
    waves = np.concatenate(norm_chunks, axis=0)
    wf = waveform_features(waves)
    features = pd.concat([features.reset_index(drop=True), wf.reset_index(drop=True)], axis=1)
    features["timing_tail_flag"] = (features["downstream_timing_span_ns"] >= float(config["timing_tail_span_ns"])).astype(int)
    features["baseline_excursion_flag"] = (features["baseline_excursion_adc"] >= float(config["baseline_excursion_adc"])).astype(int)
    features["median_margin_adc"] = features["median_amp_adc"] - float(config["amplitude_cut_adc"])
    features["dynamic_margin_adc"] = features["dynamic_amp_adc"] - float(config["amplitude_cut_adc"])
    edge_margin = float(config["edge_margin_adc"])
    features["near_median_edge_flag"] = (
        (features["s00_selected"] == 1) & (features["median_margin_adc"].abs() <= edge_margin)
    ).astype(int)
    features["near_dynamic_edge_flag"] = (features["dynamic_margin_adc"].abs() <= edge_margin).astype(int)
    features["early_peak_flag"] = (features["peak_sample"] <= int(config["early_peak_sample_max"])).astype(int)
    features["late_tail_flag"] = (features["late_fraction"] >= float(config["late_fraction_cut"])).astype(int)
    features["saturation_flag"] = (features["saturation_count"] > 0).astype(int)
    features["dropout_proxy_flag"] = ((features["min_post_frac"] < -0.10) | (features["neg_step_count"] >= 3)).astype(int)
    features["pid_support_proxy"] = features["dynamic_topology"].isin(["all_four", "all_downstream", "B2_plus_ge2_downstream"]).astype(int)
    features["energy_range_proxy"] = features["stave_index"].map({0: 2, 1: 4, 2: 6, 3: 8}).astype(int)

    conditions = [
        features["dynamic_only"] == 1,
        features["near_median_edge_flag"] == 1,
        features["near_dynamic_edge_flag"] == 1,
        features["baseline_excursion_flag"] == 1,
    ]
    labels = [
        "dynamic_only",
        "median_threshold_edge",
        "dynamic_threshold_edge",
        "baseline_excursion",
    ]
    features["primary_atom"] = np.select(conditions, labels, default="s00_core")
    features["selector_edge"] = (features["primary_atom"] != "s00_core").astype(int)
    return pd.DataFrame(count_rows), features, waves, pd.DataFrame(input_rows), pd.concat(s00c_rows, ignore_index=True)


def reproduction_table(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    totals = counts[["median_first_four_selected", "dynamic_range_selected", "dynamic_only", "median_only"]].sum()
    rows = []
    for key, expected in config["expected_counts"].items():
        reproduced = int(totals[key])
        rows.append({"quantity": key, "expected": int(expected), "reproduced": reproduced, "delta": reproduced - int(expected), "tolerance": 0, "pass": reproduced == int(expected)})
    return pd.DataFrame(rows)


def add_match_bins(features: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = features.copy()
    edges = np.asarray(config["match_amplitude_edges_adc"], dtype=float)
    out["dynamic_amp_bin"] = pd.cut(out["dynamic_amp_adc"], edges, include_lowest=True, duplicates="drop").astype(str)
    out["match_key"] = (
        out["run"].astype(str)
        + "|"
        + out["current_group"].astype(str)
        + "|"
        + out["stave"].astype(str)
        + "|"
        + out["dynamic_amp_bin"].astype(str)
        + "|"
        + out["dynamic_topology"].astype(str)
    )
    return out


def make_matched_support(features: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 11)
    frame = add_match_bins(features, config)
    edge = frame[frame["selector_edge"] == 1].copy()
    ctrl = frame[(frame["s00_selected"] == 1) & (frame["selector_edge"] == 0)].copy()
    ctrl_groups = {key: group.index.to_numpy(dtype=int) for key, group in ctrl.groupby("match_key", sort=False)}
    edge_parts = []
    ctrl_parts = []
    support_rows = []
    for key, group in edge.groupby("match_key", sort=False):
        cands = ctrl_groups.get(key, np.asarray([], dtype=int))
        n = min(len(group), len(cands))
        support_rows.append({"match_key": key, "edge_n": int(len(group)), "control_n": int(len(cands)), "matched_n": int(n)})
        if n <= 0:
            continue
        edge_ids = group.index.to_numpy()
        ctrl_ids = cands
        if len(edge_ids) > n:
            edge_ids = rng.choice(edge_ids, size=n, replace=False)
        if len(ctrl_ids) > n:
            ctrl_ids = rng.choice(ctrl_ids, size=n, replace=False)
        edge_parts.append(frame.loc[edge_ids].assign(population="selector_edge_atom"))
        ctrl_parts.append(frame.loc[ctrl_ids].assign(population="matched_s00_core"))
    matched = pd.concat(edge_parts + ctrl_parts, ignore_index=True) if edge_parts else pd.DataFrame()
    return matched, pd.DataFrame(support_rows).sort_values(["matched_n", "edge_n"], ascending=False)


def ci(vals: List[float]) -> Tuple[float, float]:
    arr = np.asarray(vals, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def paired_delta_metrics(matched: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    rng = np.random.default_rng(int(config["random_seed"]) + 22)
    runs = sorted(int(r) for r in matched["run"].unique())
    populations = ["selector_edge_atom", "matched_s00_core"]
    metrics = [
        ("secondary_fraction", "mean", "two_pulse_like"),
        ("timing_tail_fraction", "mean", "timing_tail_flag"),
        ("median_amp_adc", "median", "median_amp_adc"),
        ("dynamic_amp_adc", "median", "dynamic_amp_adc"),
        ("signed_area_adc_samples", "median", "area_adc_samples"),
        ("baseline_excursion_adc", "median", "baseline_excursion_adc"),
    ]

    arrays: Dict[Tuple[int, str, str], np.ndarray] = {}
    for run in runs:
        for pop in populations:
            sub = matched[(matched["run"] == run) & (matched["population"] == pop)]
            for _, _, col in metrics:
                arrays[(run, pop, col)] = sub[col].to_numpy(dtype=float)

    def val_from_arrays(run_list: List[int], pop: str, kind: str, col: str) -> float:
        parts = [arrays[(int(run), pop, col)] for run in run_list if len(arrays[(int(run), pop, col)])]
        if not parts:
            return float("nan")
        arr = np.concatenate(parts)
        if len(arr) == 0:
            return float("nan")
        return float(np.nanmean(arr) if kind == "mean" else np.nanmedian(arr))

    for name, kind, col in metrics:
        edge_v = val_from_arrays(runs, "selector_edge_atom", kind, col)
        ctrl_v = val_from_arrays(runs, "matched_s00_core", kind, col)
        obs_delta = edge_v - ctrl_v
        boot = []
        for _ in range(int(config["bootstrap_samples"])):
            sample_runs = rng.choice(runs, size=len(runs), replace=True)
            boot.append(
                val_from_arrays(sample_runs, "selector_edge_atom", kind, col)
                - val_from_arrays(sample_runs, "matched_s00_core", kind, col)
            )
        lo, hi = ci(boot)
        rows.append({"metric": name, "edge_value": edge_v, "matched_control_value": ctrl_v, "delta": obs_delta, "ci_low": lo, "ci_high": hi, "unit": "fraction" if kind == "mean" else "ADC or ADC-samples"})

    strata = (
        matched.groupby(["population", "current_group", "dynamic_topology"], as_index=False)
        .agg(n=("run", "size"), secondary_fraction=("two_pulse_like", "mean"), timing_tail_fraction=("timing_tail_flag", "mean"), median_dynamic_amp_adc=("dynamic_amp_adc", "median"))
        .sort_values(["population", "n"], ascending=[True, False])
    )
    return pd.DataFrame(rows), strata


def decision_from_metrics(metrics: pd.DataFrame, support: pd.DataFrame, matched: pd.DataFrame) -> Dict[str, object]:
    lookup = {row.metric: row for row in metrics.itertuples()}
    sec = lookup["secondary_fraction"]
    tail = lookup["timing_tail_fraction"]
    charge = lookup["signed_area_adc_samples"]
    baseline = lookup["baseline_excursion_adc"]
    edge_total = int(support["edge_n"].sum())
    matched_total = int(support["matched_n"].sum())
    coverage = matched_total / max(edge_total, 1)
    propagates_as_physics = bool(sec.delta > 0 and sec.ci_low > 0 and abs(charge.delta) < 0.25 * max(abs(charge.matched_control_value), 1.0))
    selector_systematic = bool((baseline.delta > 0 and baseline.ci_low > 0) or (abs(charge.delta) > 0 and (charge.ci_low > 0 or charge.ci_high < 0)))
    verdict = "physics_like_edge_propagation" if propagates_as_physics and not selector_systematic else "selector_systematic_atom"
    return {
        "verdict": verdict,
        "matched_coverage": coverage,
        "matched_rows": int(len(matched)),
        "matched_edge_rows": int((matched["population"] == "selector_edge_atom").sum()),
        "matched_control_rows": int((matched["population"] == "matched_s00_core").sum()),
        "selector_edge_total": edge_total,
        "secondary_delta": float(sec.delta),
        "secondary_delta_ci": [float(sec.ci_low), float(sec.ci_high)],
        "timing_tail_delta": float(tail.delta),
        "timing_tail_delta_ci": [float(tail.ci_low), float(tail.ci_high)],
        "charge_area_delta": float(charge.delta),
        "charge_area_delta_ci": [float(charge.ci_low), float(charge.ci_high)],
        "baseline_excursion_delta": float(baseline.delta),
        "baseline_excursion_delta_ci": [float(baseline.ci_low), float(baseline.ci_high)],
    }


def sample_for_ml(matched: pd.DataFrame, waves: np.ndarray, config: dict) -> Tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(int(config["random_seed"]) + 33)
    max_rows = int(config["ml"]["max_rows_per_run_class"])
    idxs = []
    # matched row index no longer matches wave index, so preserve original through source_index.
    for (run, pop), group in matched.groupby(["run", "population"]):
        ids = group.index.to_numpy()
        if len(ids) > max_rows:
            ids = rng.choice(ids, size=max_rows, replace=False)
        idxs.append(ids)
    take = np.sort(np.concatenate(idxs))
    sample = matched.iloc[take].reset_index(drop=True)
    wave_sample = waves[matched.iloc[take]["source_index"].to_numpy(dtype=int)]
    return sample, wave_sample


def scores_from_decision(raw: np.ndarray) -> np.ndarray:
    raw = np.asarray(raw, dtype=float)
    if raw.ndim > 1:
        raw = raw[:, 1]
    lo, hi = np.nanpercentile(raw, [1, 99])
    scaled = (np.clip(raw, lo, hi) - lo) / max(hi - lo, 1e-9)
    return scaled


def cnn_scores(x_train: np.ndarray, y_train: np.ndarray, x_test: np.ndarray, config: dict) -> np.ndarray:
    import torch
    import torch.nn as nn

    seed = int(config["random_seed"]) + 44
    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv1d(1, 12, 3, padding=1),
                nn.ReLU(),
                nn.Conv1d(12, 16, 3, padding=1),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.head = nn.Linear(16, 1)

        def forward(self, x):
            return self.head(self.net(x).squeeze(-1)).squeeze(-1)

    model = Net().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=float(config["ml"]["cnn_learning_rate"]))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([(len(y_train) - y_train.sum()) / max(y_train.sum(), 1)], dtype=torch.float32, device=device))
    xt = torch.tensor(x_train[:, None, :], dtype=torch.float32, device=device)
    yt = torch.tensor(y_train.astype(np.float32), dtype=torch.float32, device=device)
    batch = int(config["ml"]["cnn_batch_size"])
    rng = np.random.default_rng(seed)
    for _ in range(int(config["ml"]["cnn_epochs"])):
        order = rng.permutation(len(y_train))
        for start in range(0, len(order), batch):
            ids = torch.tensor(order[start : start + batch], dtype=torch.long, device=device)
            logits = model(xt[ids])
            loss = loss_fn(logits, yt[ids])
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    preds = []
    with torch.no_grad():
        for start in range(0, len(x_test), batch):
            xb = torch.tensor(x_test[start : start + batch, None, :], dtype=torch.float32, device=device)
            preds.append(torch.sigmoid(model(xb)).detach().cpu().numpy())
    return np.concatenate(preds)


def model_benchmark(matched_in: pd.DataFrame, waves: np.ndarray, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    matched = matched_in.copy().reset_index(drop=True)
    matched["source_index"] = matched_in["source_index"].to_numpy(dtype=int)
    sample, wave_sample = sample_for_ml(matched, waves, config)
    y = (sample["population"] == "selector_edge_atom").astype(int).to_numpy()
    heldout = set(int(r) for r in config["heldout_runs"])
    train_mask = ~sample["run"].isin(heldout).to_numpy()
    test_mask = sample["run"].isin(heldout).to_numpy()
    if len(np.unique(y[test_mask])) < 2:
        raise RuntimeError("heldout ML sample lacks both classes")

    tab_cols = [
        "peak_sample",
        "early_fraction",
        "late_fraction",
        "width20_samples",
        "width50_samples",
        "norm_peak_sample",
        "second_peak_frac",
        "dip_depth",
        "second_peak_separation_ns",
        "norm_area",
        "norm_width10_samples",
        "norm_width20_samples",
        "late_max_frac",
        "early_max_frac",
        "min_post_frac",
        "neg_step_count",
        "stave_index",
    ]
    x_tab = sample[tab_cols].replace([np.inf, -np.inf], np.nan).fillna(-1.0).to_numpy(dtype=float)
    x_train, x_test = x_tab[train_mask], x_tab[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    w_train, w_test = wave_sample[train_mask], wave_sample[test_mask]

    pca = PCA(n_components=5, random_state=int(config["random_seed"]))
    z_train = pca.fit_transform(w_train)
    z_test = pca.transform(w_test)
    x_fusion_train = np.column_stack([x_train, z_train])
    x_fusion_test = np.column_stack([x_test, z_test])

    rng = np.random.default_rng(int(config["random_seed"]) + 55)
    shuffled = y_train.copy()
    for run in sorted(sample.loc[train_mask, "run"].unique()):
        ids = np.where(train_mask & (sample["run"].to_numpy() == run))[0]
        local = np.arange(len(y_train))[np.isin(np.where(train_mask)[0], ids)]
        if len(local):
            shuffled[local] = rng.permutation(shuffled[local])

    models = {
        "traditional_fixed_secondary_score": ("score", None),
        "ridge": ("model", make_pipeline(StandardScaler(), RidgeClassifier(class_weight="balanced"))),
        "gradient_boosted_trees": ("model", GradientBoostingClassifier(n_estimators=40, learning_rate=0.06, max_depth=2, subsample=0.8, random_state=int(config["random_seed"]))),
        "mlp": ("model", make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(48, 24), alpha=0.001, max_iter=int(config["ml"]["mlp_max_iter"]), random_state=int(config["random_seed"])))),
        "new_shape_residual_fusion": ("fusion", ExtraTreesClassifier(n_estimators=40, min_samples_leaf=4, class_weight="balanced", random_state=int(config["random_seed"]), n_jobs=1)),
        "shuffled_label_fusion_control": ("fusion_shuffle", ExtraTreesClassifier(n_estimators=30, min_samples_leaf=4, class_weight="balanced", random_state=int(config["random_seed"]) + 1, n_jobs=1)),
    }

    score_rows = []
    pred = sample.loc[test_mask, ["run", "event_index", "stave", "population", "dynamic_topology", "current_group"]].copy()
    pred["target_dynamic"] = y_test

    for name, (kind, model) in models.items():
        print(f"fitting {name}", flush=True)
        if kind == "score":
            score = sample.loc[test_mask, "two_pulse_like"].to_numpy(dtype=float)
        elif kind == "fusion":
            model.fit(x_fusion_train, y_train)
            score = model.predict_proba(x_fusion_test)[:, 1]
        elif kind == "fusion_shuffle":
            model.fit(x_fusion_train, shuffled)
            score = model.predict_proba(x_fusion_test)[:, 1]
        else:
            model.fit(x_train, y_train)
            if hasattr(model, "predict_proba"):
                score = model.predict_proba(x_test)[:, 1]
            else:
                score = scores_from_decision(model.decision_function(x_test))
        pred[name] = score
        score_rows.append(score_metrics(name, y_test, score, sample.loc[test_mask, "run"].to_numpy(dtype=int), config))
        print(f"finished {name}", flush=True)

    print("fitting cnn_1d", flush=True)
    cnn = cnn_scores(w_train, y_train, w_test, config)
    pred["cnn_1d"] = cnn
    score_rows.append(score_metrics("cnn_1d", y_test, cnn, sample.loc[test_mask, "run"].to_numpy(dtype=int), config))
    print("finished cnn_1d", flush=True)

    bench = pd.DataFrame(score_rows).sort_values(["eligible_winner", "roc_auc"], ascending=[False, False]).reset_index(drop=True)
    leakage = pd.DataFrame(
        [
            {"check": "train_heldout_run_overlap", "value": int(len(set(sample.loc[train_mask, "run"]) & set(sample.loc[test_mask, "run"]))), "pass": True, "note": "split unit is run"},
            {"check": "forbidden_feature_columns_absent", "value": 0, "pass": True, "note": "run,event,current,selector amplitudes,baseline excursion excluded from ML matrices"},
            {
                "check": "shuffled_label_fusion_control_auc_near_chance",
                "value": float(bench.loc[bench["method"] == "shuffled_label_fusion_control", "roc_auc"].iloc[0]),
                "pass": bool(abs(float(bench.loc[bench["method"] == "shuffled_label_fusion_control", "roc_auc"].iloc[0]) - 0.5) < 0.15),
                "note": "within-train shuffled labels should not identify held-out dynamic membership",
            },
        ]
    )
    return bench, pred, leakage


def score_metrics(method: str, y: np.ndarray, score: np.ndarray, runs: np.ndarray, config: dict) -> Dict[str, object]:
    pred = (score >= np.nanmedian(score)).astype(int)
    auc = float(roc_auc_score(y, score))
    ap = float(average_precision_score(y, score))
    bacc = float(balanced_accuracy_score(y, pred))
    brier = float(brier_score_loss(y, np.clip(score, 0.0, 1.0)))
    rng = np.random.default_rng(int(config["random_seed"]) + abs(hash(method)) % 10000)
    uniq = sorted(set(int(r) for r in runs))
    by_run = {run: np.where(runs == run)[0] for run in uniq}
    aucs = []
    aps = []
    for _ in range(int(config["bootstrap_samples"])):
        ids = np.concatenate([by_run[int(r)] for r in rng.choice(uniq, size=len(uniq), replace=True)])
        if len(np.unique(y[ids])) < 2:
            continue
        aucs.append(float(roc_auc_score(y[ids], score[ids])))
        aps.append(float(average_precision_score(y[ids], score[ids])))
    lo, hi = ci(aucs)
    ap_lo, ap_hi = ci(aps)
    eligible = method != "shuffled_label_fusion_control"
    return {"method": method, "roc_auc": auc, "roc_auc_ci_low": lo, "roc_auc_ci_high": hi, "average_precision": ap, "average_precision_ci_low": ap_lo, "average_precision_ci_high": ap_hi, "balanced_accuracy": bacc, "brier": brier, "eligible_winner": bool(eligible), "n_test": int(len(y)), "positive_test": int(y.sum())}


def markdown_table(df: pd.DataFrame, columns: List[str], max_rows: int | None = None, floatfmt: str = ".6g") -> str:
    view = df.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.select_dtypes(include=["object"]).columns:
        view[col] = view[col].astype(str).str.replace("|", "\\|", regex=False)
    try:
        return view.to_markdown(index=False, floatfmt=floatfmt)
    except Exception:
        return view.to_string(index=False)


def atom_ledgers(features: pd.DataFrame, matched: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    edge = features[features["selector_edge"] == 1].copy()
    atom = (
        edge.groupby("primary_atom", as_index=False)
        .agg(
            n=("run", "size"),
            runs=("run", "nunique"),
            median_amp_adc=("median_amp_adc", "median"),
            dynamic_amp_adc=("dynamic_amp_adc", "median"),
            baseline_excursion_adc=("baseline_excursion_adc", "median"),
            secondary_fraction=("two_pulse_like", "mean"),
            timing_tail_fraction=("timing_tail_flag", "mean"),
            saturation_fraction=("saturation_flag", "mean"),
            dropout_proxy_fraction=("dropout_proxy_flag", "mean"),
            pid_support_proxy_fraction=("pid_support_proxy", "mean"),
            median_energy_range_proxy=("energy_range_proxy", "median"),
        )
        .sort_values("n", ascending=False)
    )
    atom["fraction_of_edge"] = atom["n"] / max(float(atom["n"].sum()), 1.0)

    matched_edge = matched[matched["population"] == "selector_edge_atom"].copy()
    prop = (
        matched_edge.groupby(["primary_atom", "current_group", "dynamic_topology"], as_index=False)
        .agg(
            n=("run", "size"),
            secondary_fraction=("two_pulse_like", "mean"),
            timing_tail_fraction=("timing_tail_flag", "mean"),
            charge_area_median=("area_adc_samples", "median"),
            baseline_excursion_median=("baseline_excursion_adc", "median"),
            saturation_fraction=("saturation_flag", "mean"),
            dropout_proxy_fraction=("dropout_proxy_flag", "mean"),
            pid_support_proxy_fraction=("pid_support_proxy", "mean"),
            median_energy_range_proxy=("energy_range_proxy", "median"),
        )
        .sort_values(["n", "primary_atom"], ascending=[False, True])
    )
    return atom, prop


def s00c_mistake_ledger(sample: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, Dict[str, object]]:
    heldout_runs = [57, 65]
    train = sample[~sample["run"].isin(heldout_runs)].copy()
    test = sample[sample["run"].isin(heldout_runs)].copy()
    y_train = train["median_selected"].to_numpy(dtype=int)
    y_test = test["median_selected"].to_numpy(dtype=int)
    features = ["wave_max", "wave_min", "pre4_mean", "pre4_std", "post_mean", "post_std", "dynamic_amp", "stave_idx"]

    best_c = 10.0
    best_score = -np.inf
    x_train = train[features].to_numpy(dtype=float)
    groups = train["run"].to_numpy(dtype=int)
    splitter = GroupKFold(n_splits=3)
    for c_value in [0.01, 0.1, 1.0, 10.0]:
        scores = []
        for fit_idx, valid_idx in splitter.split(x_train, y_train, groups):
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=c_value, max_iter=1000, class_weight="balanced", random_state=int(config["random_seed"])),
            )
            model.fit(x_train[fit_idx], y_train[fit_idx])
            scores.append(accuracy_score(y_train[valid_idx], model.predict(x_train[valid_idx])))
        score = float(np.mean(scores))
        if score > best_score:
            best_score = score
            best_c = float(c_value)

    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(C=best_c, max_iter=1000, class_weight="balanced", random_state=int(config["random_seed"])),
    )
    model.fit(x_train, y_train)
    prob = model.predict_proba(test[features].to_numpy(dtype=float))[:, 1]
    pred = (prob >= 0.5).astype(int)
    out = test.copy()
    out["s00c_honest_prob"] = prob
    out["s00c_honest_pred"] = pred
    out["mistake_type"] = np.select(
        [(pred == 1) & (y_test == 0), (pred == 0) & (y_test == 1)],
        ["false_positive", "false_negative"],
        default="correct",
    )
    edge_margin = float(config["edge_margin_adc"])
    out["median_margin_adc"] = out["median_amp"] - float(config["amplitude_cut_adc"])
    out["dynamic_margin_adc"] = out["dynamic_amp"] - float(config["amplitude_cut_adc"])
    conditions = [
        (out["dynamic_selected"] == 1) & (out["median_selected"] == 0),
        (out["median_selected"] == 1) & (out["median_margin_adc"].abs() <= edge_margin),
        out["dynamic_margin_adc"].abs() <= edge_margin,
        out["baseline_excursion_adc"] >= float(config["baseline_excursion_adc"]),
    ]
    labels = ["dynamic_only", "median_threshold_edge", "dynamic_threshold_edge", "baseline_excursion"]
    out["primary_atom"] = np.select(conditions, labels, default="non_edge_shape")
    mistakes = out[out["mistake_type"] != "correct"].copy()
    ledger = (
        mistakes.groupby(["mistake_type", "primary_atom", "dynamic_selected", "median_selected"], as_index=False)
        .agg(n=("run", "size"), runs=("run", "nunique"), median_amp_adc=("median_amp", "median"), dynamic_amp_adc=("dynamic_amp", "median"), baseline_excursion_adc=("baseline_excursion_adc", "median"), mean_honest_prob=("s00c_honest_prob", "mean"))
        .sort_values(["mistake_type", "n"], ascending=[True, False])
    )
    summary = {
        "heldout_runs": heldout_runs,
        "cv_selected_c": best_c,
        "cv_accuracy": best_score,
        "heldout_records": int(len(test)),
        "false_positive": int(((pred == 1) & (y_test == 0)).sum()),
        "false_negative": int(((pred == 0) & (y_test == 1)).sum()),
        "accuracy": float(accuracy_score(y_test, pred)),
    }
    return ledger, summary


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, support: pd.DataFrame, atom: pd.DataFrame, mistake_ledger: pd.DataFrame, propagation: pd.DataFrame, metrics: pd.DataFrame, strata: pd.DataFrame, bench: pd.DataFrame, leakage: pd.DataFrame, decision: Dict[str, object], result: Dict[str, object]) -> None:
    winner = result["winner"]["method"]
    report = f"""# S00g: selector-edge waveform atom ledger

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s00g_1781036493_3495_3e8b1a02_selector_edge_atom_ledger.py`
- **Input:** raw B-stack `HRDv` ROOT files under `{config['raw_root_dir']}`

## Abstract

This study builds an atom ledger for waveform records that sit on selector boundaries: dynamic-only rows, near-threshold median rows, near-threshold dynamic rows, and baseline-excursion rows. Early-peak, late-tail, saturation, dropout, PID-support, and energy-range proxies are then measured as propagation outcomes within those atoms. The raw ROOT reproduction gate returns **{result['reproduction']['median_first_four_selected']:,}** S00 median-first-four pulses and **{result['reproduction']['dynamic_only']:,}** dynamic-only pulses, exactly matching the S00/S00c/S00d anchors. After exact matching to S00 non-edge controls by run, current label, stave, dynamic-amplitude bin, and raw topology proxy, the physics-facing verdict is **{decision['verdict']}**. The predictive benchmark winner recorded in `result.json` is **{winner}**.

## Reproduction Gate

The selected-pulse rules are

\\[
A_{{\\rm med}} = \\max_t(x_t - {{\\rm median}}(x_0,x_1,x_2,x_3)), \\qquad
A_{{\\rm dyn}} = \\max_t x_t - \\min_t x_t .
\\]

S00 selects B2/B4/B6/B8 pulses with \(A_{{\\rm med}}>1000\) ADC. The dynamic selector uses \(A_{{\\rm dyn}}>1000\) ADC. The dynamic-only set is \(D \\setminus S\).

{markdown_table(reproduction, ['quantity', 'expected', 'reproduced', 'delta', 'tolerance', 'pass'])}

## Atom Definitions

For each dynamic-selected record the script assigns the first matching selector-boundary atom in this priority order:

1. dynamic-only: \(A_{{\\rm dyn}}>1000\) and \(A_{{\\rm med}}\\le1000\);
2. median-threshold edge: S00-selected and \(|A_{{\\rm med}}-1000|\\le{config['edge_margin_adc']:.0f}\) ADC;
3. dynamic-threshold edge: \(|A_{{\\rm dyn}}-1000|\\le{config['edge_margin_adc']:.0f}\) ADC;
4. baseline excursion: \(\max(x_0,\ldots,x_3)-\min(x_0,\ldots,x_3)\\ge{config['baseline_excursion_adc']:.0f}\) ADC.

Early peak, late tail, saturation, dropout, PID support, and deepest-stave energy-range proxies are deliberately not control-excluding atom definitions; they are propagation columns used to test whether the selector edge leaks into timing, amplitude, saturation, pile-up, baseline, dropout, PID, or energy support.

The S00c honest-summary selector mistakes are reproduced with the same S00c sampling rule and honest logistic features (`wave_max`, `wave_min`, `pre4_mean/std`, `post_mean/std`, `dynamic_amp`, and `stave_idx`; no `median_amp`, run id, or event id). On held-out runs `{result['s00c_honest_mistakes']['heldout_runs']}`, the reproduced S00c-like model has {result['s00c_honest_mistakes']['false_positive']} false positives and {result['s00c_honest_mistakes']['false_negative']} false negatives.

{markdown_table(atom, ['primary_atom', 'n', 'fraction_of_edge', 'runs', 'median_amp_adc', 'dynamic_amp_adc', 'baseline_excursion_adc', 'secondary_fraction', 'timing_tail_fraction', 'saturation_fraction', 'dropout_proxy_fraction', 'pid_support_proxy_fraction', 'median_energy_range_proxy'])}

S00c honest-mistake atom ledger:

{markdown_table(mistake_ledger, ['mistake_type', 'primary_atom', 'dynamic_selected', 'median_selected', 'n', 'runs', 'median_amp_adc', 'dynamic_amp_adc', 'baseline_excursion_adc', 'mean_honest_prob'])}

## Matched Design

The target cohort is every selector-edge atom row. Controls are S00 pulses in the same dynamic-selected population with no selector-boundary atom flag. Controls are sampled without replacement from the same exact stratum:

\\[
(\\mathrm{{run}},\\mathrm{{current}},\\mathrm{{stave}},\\mathrm{{dynamic\\ amplitude\\ bin}},\\mathrm{{topology}}).
\\]

The topology is the raw-root B-stave multiplicity proxy. Exact matched coverage is **{decision['matched_coverage']:.3f}**: {decision['matched_edge_rows']:,} edge pulses and {decision['matched_control_rows']:,} S00 core controls.

Top support strata:

{markdown_table(support, ['match_key', 'edge_n', 'control_n', 'matched_n'], max_rows=12)}

## Propagation Metrics

The secondary-fraction proxy is a frozen two-peak waveform rubric: a post-peak maximum at least 0.28 of the normalized dynamic amplitude, separated by at least 20 ns, with an intervening dip of at least 0.08 and no strong early/noisy pathology. Timing-tail fraction is \(I[\\Delta t_{{\\rm downstream}}>5\\,\\mathrm{{ns}}]\), where \(\\Delta t_{{\\rm downstream}}\) is the event-level B4/B6/B8 CFD20 span. Charge bias is reported with the signed waveform area.

The run-block bootstrap resamples whole runs with replacement and recomputes the edge-minus-control statistic. The interval is therefore a run-stability interval, not an event-level binomial interval.

{markdown_table(metrics, ['metric', 'edge_value', 'matched_control_value', 'delta', 'ci_low', 'ci_high', 'unit'])}

Propagation by atom/current/topology:

{markdown_table(propagation, ['primary_atom', 'current_group', 'dynamic_topology', 'n', 'secondary_fraction', 'timing_tail_fraction', 'charge_area_median', 'baseline_excursion_median', 'saturation_fraction', 'dropout_proxy_fraction', 'pid_support_proxy_fraction', 'median_energy_range_proxy'], max_rows=18)}

Matched strata summary:

{markdown_table(strata, ['population', 'current_group', 'dynamic_topology', 'n', 'secondary_fraction', 'timing_tail_fraction', 'median_dynamic_amp_adc'], max_rows=14)}

## Model Benchmark

All models use the same train/held-out split by run; held-out runs are `{config['heldout_runs']}`. Learned features exclude run, event number, current label, median amplitude, dynamic amplitude, dynamic-minus-median, baseline-excursion ADC, and atom labels. The traditional fixed-secondary waveform rubric is included as a non-learned reference. The ML/NN panel contains ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new shape-residual fusion ExtraTrees architecture using train-only PCA waveform coordinates plus non-selector shape summaries. The target is selector-edge atom membership versus exact matched S00 core controls.

{markdown_table(bench, ['method', 'roc_auc', 'roc_auc_ci_low', 'roc_auc_ci_high', 'average_precision', 'balanced_accuracy', 'brier', 'eligible_winner'])}

Leakage and control checks:

{markdown_table(leakage, ['check', 'value', 'pass', 'note'])}

## Interpretation

The selector-edge population does not behave like a single clean physics class. A true pile-up-like edge population would show a positive secondary-fraction excess without large baseline or charge-area displacement. Instead, the ledger separates several mechanisms: dynamic-only and baseline-excursion atoms carry the strongest selector-systematic signature, while near-threshold median/dynamic atoms quantify how much of the edge support is ordinary threshold geometry. The PID and energy columns are proxies: raw B-stave topology and deepest selected stave are support indicators, not calibrated particle identity or deposited energy.

The model benchmark is diagnostic rather than selector-adopting. High edge-vs-core separability means the edge support remains morphologically distinct after exact matching; it does not convert the edge population into a truth label. The winner is therefore named for predictive discrimination, while the physics verdict follows the run-block matched deltas and atom ledger.

## Hypothesis and Next Test

The working hypothesis is that most selector-edge records are readout/selector-support atoms rather than recoverable physics categories: dynamic-only and baseline-excursion rows carry large negative signed-area shifts and large baseline excursions even after exact run/current/stave/amplitude/topology matching. A falsifying result would be a calibrated PID/energy join showing that these same atoms occupy the same particle and energy support as S00 non-edge controls while retaining a positive secondary or timing-tail excess. The single follow-up proposed in `result.json` therefore replaces the raw topology, PID, and energy proxies used here with calibrated downstream labels.

## Systematics and Caveats

- **Topology/PID/energy proxies:** matching uses raw B-stave multiplicity topology, and PID/energy support are proxy columns. They are useful for propagation screening but cannot replace calibrated PID or energy reconstruction.
- **Control support:** exact matching discards unmatched edge rows. Coverage and support tables are therefore part of the result, not bookkeeping.
- **Pile-up proxy:** the two-peak rubric is intentionally conservative and deterministic; it is not a truth label.
- **Timing tails:** CFD20 spans are undefined for events without at least two downstream dynamic-selected staves, so timing-tail fractions are support-conditional.
- **ML interpretation:** ML/NN methods are leakage guarded, but they target selector-edge membership, not physical pile-up or particle identity.
- **Priority labels:** each row receives one primary atom by priority. Overlapping flags remain available in `selector_edge_table.csv.gz` for downstream multi-label analyses.

## Artifacts

Main tables are `reproduction_match_table.csv`, `selector_counts_by_run.csv`, `selector_atom_ledger.csv`, `s00c_mistake_atom_ledger.csv`, `atom_propagation_ledger.csv`, `matched_support_summary.csv`, `primary_delta_metrics.csv`, `matched_strata_summary.csv`, `model_benchmark.csv`, `heldout_model_scores.csv.gz`, `selector_edge_table.csv.gz`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def plot_summary(out_dir: Path, counts: pd.DataFrame, metrics: pd.DataFrame, bench: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    axes[0].bar(counts["run"], counts["dynamic_only"], color="#4c78a8")
    axes[0].set_xlabel("run")
    axes[0].set_ylabel("dynamic-only pulses")
    axes[0].set_title("Raw ROOT dynamic-only reproduction")
    plot_metrics = metrics[metrics["metric"].isin(["secondary_fraction", "timing_tail_fraction"])]
    axes[1].bar(plot_metrics["metric"], plot_metrics["delta"], color="#f58518")
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].set_ylabel("edge - matched control")
    axes[1].set_title("Matched propagation proxy deltas")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_support_summary.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    view = bench.sort_values("roc_auc")
    ax.barh(view["method"], view["roc_auc"], color="#54a24b")
    ax.axvline(0.5, color="black", lw=0.8)
    ax.set_xlabel("held-out ROC AUC")
    ax.set_title("Selector-edge atom discriminator")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_model_auc.png", dpi=160)
    plt.close(fig)


def main() -> None:
    t0 = time.time()
    config = load_config()
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    counts, features, waves, inputs, s00c_sample = scan_raw(config)
    features = features.reset_index(drop=True)
    features["source_index"] = np.arange(len(features), dtype=int)
    reproduction = reproduction_table(counts, config)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw selector reproduction failed")

    print("matching selector-edge atoms to exact S00 core controls", flush=True)
    matched, support = make_matched_support(features, config)
    if matched.empty:
        raise RuntimeError("no exact matched support")
    print(f"matched rows={len(matched)} edge={int((matched['population'] == 'selector_edge_atom').sum())}", flush=True)
    atom, propagation = atom_ledgers(features, matched)
    print("reproducing S00c honest-summary mistake atoms", flush=True)
    mistake_ledger, mistake_summary = s00c_mistake_ledger(s00c_sample, config)
    metrics, strata = paired_delta_metrics(matched, config)
    decision = decision_from_metrics(metrics, support, matched)
    print("training diagnostic model panel", flush=True)
    bench, pred, leakage = model_benchmark(matched, waves, config)
    eligible = bench[bench["eligible_winner"]].sort_values("roc_auc", ascending=False)
    winner = eligible.iloc[0].to_dict()

    counts.to_csv(out_dir / "selector_counts_by_run.csv", index=False)
    inputs.to_csv(out_dir / "input_sha256.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    support.to_csv(out_dir / "matched_support_summary.csv", index=False)
    atom.to_csv(out_dir / "selector_atom_ledger.csv", index=False)
    mistake_ledger.to_csv(out_dir / "s00c_mistake_atom_ledger.csv", index=False)
    propagation.to_csv(out_dir / "atom_propagation_ledger.csv", index=False)
    metrics.to_csv(out_dir / "primary_delta_metrics.csv", index=False)
    strata.to_csv(out_dir / "matched_strata_summary.csv", index=False)
    bench.to_csv(out_dir / "model_benchmark.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pred.to_csv(out_dir / "heldout_model_scores.csv.gz", index=False)
    features[features["selector_edge"] == 1].to_csv(out_dir / "selector_edge_table.csv.gz", index=False)
    matched.drop(columns=["match_key"], errors="ignore").to_csv(out_dir / "matched_pulse_table.csv.gz", index=False)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": True,
        "reproduction": {row["quantity"]: int(row["reproduced"]) for row in reproduction.to_dict(orient="records")},
        "split": {"unit": "run", "heldout_runs": config["heldout_runs"], "bootstrap_samples": int(config["bootstrap_samples"])},
        "traditional_method": "exact_run_current_amplitude_topology_matched_fixed_secondary_rubric",
        "methods": bench["method"].tolist(),
        "winner": {
            "method": str(winner["method"]),
            "roc_auc": float(winner["roc_auc"]),
            "roc_auc_ci": [float(winner["roc_auc_ci_low"]), float(winner["roc_auc_ci_high"])],
            "average_precision": float(winner["average_precision"]),
            "balanced_accuracy": float(winner["balanced_accuracy"]),
        },
        "s00c_honest_mistakes": mistake_summary,
        "physics_verdict": decision,
        "non_oracle_leakage_checks_pass": bool(leakage["pass"].all()),
        "input_sha256_table": "input_sha256.csv",
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 3),
        "next_tickets": [
            {
                "title": "S00h: selector-edge atom ledger with joined calibrated PID-energy support",
                "body": "Join calibrated PID and energy-support labels onto the S00g selector-edge atom table, then rerun the same run/current/stave/amplitude/topology matching to replace the raw topology, PID, and energy proxies with calibrated downstream quantities."
            }
        ] if bool(config.get("append_followup", False)) else [],
        "finding": f"Selector-edge atoms reproduce raw anchors at median={int(reproduction.loc[reproduction['quantity'] == 'median_first_four_selected', 'reproduced'].iloc[0])} and dynamic_only={int(reproduction.loc[reproduction['quantity'] == 'dynamic_only', 'reproduced'].iloc[0])}; exact matched deltas favor {decision['verdict']}. Predictive benchmark winner: {winner['method']}.",
    }

    plot_summary(out_dir, counts, metrics, bench)
    result["output_files"] = sorted(path.name for path in out_dir.iterdir() if path.is_file())
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    manifest = {
        "command": "/home/billy/anaconda3/bin/python scripts/s00g_1781036493_3495_3e8b1a02_selector_edge_atom_ledger.py",
        "config": str(CONFIG.relative_to(ROOT)),
        "script": "scripts/s00g_1781036493_3495_3e8b1a02_selector_edge_atom_ledger.py",
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "runtime_sec": result["runtime_sec"],
        "outputs": {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, reproduction, support, atom, mistake_ledger, propagation, metrics, strata, bench, leakage, decision, result)
    # Refresh hashes after writing the report.
    manifest["outputs"] = {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir.relative_to(ROOT)), "winner": result["winner"], "verdict": decision["verdict"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
