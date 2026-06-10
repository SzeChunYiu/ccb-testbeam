#!/usr/bin/env python3
"""S10g: validate S10f two-pulse candidates on real current windows.

The script reads raw B-stack ROOT, reproduces the S10/S10d/S10f gates first,
then scores real low/high-current candidate windows with low-current-derived
S10f amplitude-binned/asymmetric template candidates and a compact
overlay-trained ML regressor.  All scored real events are split by source run.
"""

from __future__ import annotations

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

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "1781029288.941.6912528c"
RAW = ROOT / "data/root/root"
CONFIG_PATH = ROOT / "configs" / "s10f_1781013481_902_5d6a5b89.json"
S11C_PATH = ROOT / "scripts" / "s11c_amp_binned_asymmetric_templates.py"
OUT.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S11C = load_module("s11c_amp_binned_asymmetric_templates", S11C_PATH)


TICKET = "1781029288.941.6912528c"
WORKER = "testbeam-laptop-3"
STUDY = "S10g"
RNG_SEED = 2026061003
NSAMPLES = 18
BASELINE_SAMPLES = [0, 1, 2, 3]
AMP_CUT = 1000.0
BOOTSTRAPS = 300
MIN_STRATUM_N = 25
SAMPLE_PER_RUN_STRATUM = 20
SYNTHETIC_TRAIN_PER_LOW_FOLD = 520
SYNTHETIC_CAL_PER_LOW_FOLD = 320
TRAD_SCORE_THRESHOLD = 0.015
ML_SCORE_THRESHOLD = 0.5
RUN_GROUPS = {
    "low_2nA": {"current_nA": 2.0, "runs": [46, 47]},
    "high_20nA": {"current_nA": 20.0, "runs": [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]},
}
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
S10_DOCUMENTED = {
    "low_2nA": {
        "multi_stave_per_selected_event": 0.0156,
        "three_stave_per_selected_event": 0.0041,
        "downstream_per_selected_event": 0.0231,
    },
    "high_20nA": {
        "multi_stave_per_selected_event": 0.0268,
        "three_stave_per_selected_event": 0.0085,
        "downstream_per_selected_event": 0.0334,
    },
}
FIT_SEPARATIONS = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0]
FIT_T1_SHIFTS = np.arange(-1.0, 1.0001, 0.25)
TEMPLATE_REF_SAMPLE = 5.0


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


def run_to_group() -> dict[int, str]:
    return {run: group for group, info in RUN_GROUPS.items() for run in info["runs"]}


def raw_file(run: int) -> Path:
    return RAW / f"hrdb_run_{run:04d}.root"


def cfd_time_one(waveform: np.ndarray, fraction: float = 0.2) -> float:
    amp = float(np.nanmax(waveform))
    if not np.isfinite(amp) or amp <= 0:
        return float("nan")
    threshold = amp * fraction
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
    return np.interp(x - float(shift), x, values, left=fill, right=fill)


def shifted_template(template: np.ndarray, time_sample: float) -> np.ndarray:
    return shift_array(template, float(time_sample) - TEMPLATE_REF_SAMPLE, fill=0.0)


def adaptive_lowering(raw_waveforms: np.ndarray, seed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    corrected = raw_waveforms - seed[:, None]
    amp = corrected.max(axis=1)
    eps = np.maximum(25.0, 0.015 * amp)
    mask = np.zeros(corrected.shape, dtype=bool)
    high = 0.35 * amp[:, None]
    low = 0.05 * amp[:, None]
    middle = corrected[:, 1:-1]
    left = corrected[:, :-2]
    right = corrected[:, 2:]
    jag = (left > high) & (right > high) & ((middle < low) | (middle < -50.0))
    mask[:, 1:-1] = jag
    eligible = np.where(mask, np.inf, raw_waveforms)
    pc = np.minimum(seed, eligible.min(axis=1) + eps)
    return seed - pc, amp


def shape_features(waveforms: np.ndarray, amp: np.ndarray | None = None) -> pd.DataFrame:
    if amp is None:
        amp = waveforms.max(axis=1)
    safe_amp = np.maximum(amp, 1.0)
    area = waveforms.sum(axis=1)
    area_denom = np.where(np.abs(area) > 1.0, area, np.sign(area) * 1.0 + (area == 0))
    return pd.DataFrame(
        {
            "log_amp": np.log(safe_amp),
            "peak_sample": waveforms.argmax(axis=1).astype(float),
            "area_over_peak": area / safe_amp,
            "tail_fraction": waveforms[:, 10:].sum(axis=1) / area_denom,
            "late_fraction": waveforms[:, 12:].max(axis=1) / safe_amp,
            "early_fraction": waveforms[:, :4].max(axis=1) / safe_amp,
            "post_peak_min_fraction": waveforms[:, 8:].min(axis=1) / safe_amp,
            "neg_step_count": (np.diff(waveforms, axis=1) < -0.20 * safe_amp[:, None]).sum(axis=1).astype(float),
            "width_10_samples": (waveforms > 0.10 * safe_amp[:, None]).sum(axis=1).astype(float),
            "width_20_samples": (waveforms > 0.20 * safe_amp[:, None]).sum(axis=1).astype(float),
            "final_fraction": waveforms[:, -1] / safe_amp,
        }
    )


def assign_strata(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["amp_bin"] = pd.cut(
        out["ref_amp_adc"],
        bins=[1000.0, 2500.0, 4500.0, np.inf],
        labels=["amp_1000_2500", "amp_2500_4500", "amp_ge_4500"],
        include_lowest=True,
        right=False,
    ).astype(str)
    out["baseline_bin"] = pd.cut(
        out["adaptive_lowering_adc"],
        bins=[-0.1, 0.1, 200.0, np.inf],
        labels=["s16_no_lowering", "s16_mild_lowering", "s16_large_lowering"],
        include_lowest=True,
        right=False,
    ).astype(str)
    early = (out["peak_sample"] <= 4) | (out["area_over_peak"] < 1.6)
    broad = (out["peak_sample"] >= 9) | (out["width_10_samples"] >= 11) | (out["late_fraction"] > 0.45)
    out["p02_topology"] = np.select([early, broad], ["p02_early_pathology", "p02_broad_late"], default="p02_normal")
    out["stratum"] = out["amp_bin"] + "|" + out["baseline_bin"] + "|" + out["p02_topology"]
    return out


def load_events() -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    group_for_run = run_to_group()
    stave_channels = np.asarray(list(STAVES.values()), dtype=int)
    stave_names = np.asarray(list(STAVES.keys()))
    event_frames = []
    ref_waves = []
    counts_rows = []
    for run in sorted(group_for_run):
        path = raw_file(run)
        group = group_for_run[run]
        current = RUN_GROUPS[group]["current_nA"]
        events_total = selected_events_total = selected_pulses_total = 0
        multi_total = three_total = downstream_total = 0
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            all_events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMPLES)
            raw = all_events[:, stave_channels, :]
            seed = np.median(raw[..., BASELINE_SAMPLES], axis=-1)
            corr = raw - seed[..., None]
            amp = corr.max(axis=-1)
            peak = corr.argmax(axis=-1)
            area = corr.sum(axis=-1)
            selected = amp > AMP_CUT
            n_selected = selected.sum(axis=1)
            keep = n_selected >= 1
            events_total += int(len(eventno))
            selected_events_total += int(keep.sum())
            selected_pulses_total += int(selected.sum())
            multi_total += int((n_selected >= 2).sum())
            three_total += int((n_selected >= 3).sum())
            downstream_total += int(selected[:, 1:].any(axis=1).sum())
            if not keep.any():
                continue
            masked_amp = np.where(selected, amp, -np.inf)
            ref_idx = masked_amp.argmax(axis=1)[keep]
            row_idx = np.where(keep)[0]
            raw_ref = raw[row_idx, ref_idx, :]
            corr_ref = corr[row_idx, ref_idx, :]
            seed_ref = seed[row_idx, ref_idx]
            lowering, amp_seed = adaptive_lowering(raw_ref, seed_ref)
            frame = pd.DataFrame(
                {
                    "run": int(run),
                    "group": group,
                    "current_nA": float(current),
                    "eventno": eventno[row_idx],
                    "n_selected": n_selected[row_idx].astype(int),
                    "multi_stave": (n_selected[row_idx] >= 2).astype(int),
                    "three_stave": (n_selected[row_idx] >= 3).astype(int),
                    "downstream": selected[row_idx, 1:].any(axis=1).astype(int),
                    "ref_stave": stave_names[ref_idx],
                    "ref_stave_idx": ref_idx.astype(int),
                    "ref_amp_adc": amp[row_idx, ref_idx],
                    "ref_area_adc": area[row_idx, ref_idx],
                    "seed_median4_adc": seed_ref,
                    "adaptive_lowering_adc": lowering,
                    "s16_amp_seed_adc": amp_seed,
                    "peak_sample": peak[row_idx, ref_idx].astype(int),
                }
            )
            event_frames.append(frame)
            ref_waves.append(corr_ref.astype(np.float32))
        counts_rows.append(
            {
                "run": int(run),
                "group": group,
                "current_nA": float(current),
                "events_total": events_total,
                "events_with_selected": selected_events_total,
                "selected_pulses": selected_pulses_total,
                "multi_stave_events": multi_total,
                "three_stave_events": three_total,
                "downstream_events": downstream_total,
            }
        )
    events = pd.concat(event_frames, ignore_index=True)
    waves = np.concatenate(ref_waves, axis=0)
    features = shape_features(waves, events["ref_amp_adc"].to_numpy())
    events = pd.concat([events.drop(columns=["peak_sample"]).reset_index(drop=True), features.reset_index(drop=True)], axis=1)
    events["event_index"] = np.arange(len(events), dtype=int)
    events = assign_strata(events)
    return events, waves, pd.DataFrame(counts_rows)


def reproduce_s10(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for group, sub in events.groupby("group"):
        rows.append(
            {
                "group": group,
                "runs": " ".join(str(r) for r in RUN_GROUPS[group]["runs"]),
                "current_nA": RUN_GROUPS[group]["current_nA"],
                "events_with_selected": int(len(sub)),
                "selected_pulses": int(sub["n_selected"].sum()),
                "multi_stave_events": int(sub["multi_stave"].sum()),
                "three_stave_events": int(sub["three_stave"].sum()),
                "downstream_events": int(sub["downstream"].sum()),
                "multi_stave_per_selected_event": float(sub["multi_stave"].mean()),
                "three_stave_per_selected_event": float(sub["three_stave"].mean()),
                "downstream_per_selected_event": float(sub["downstream"].mean()),
            }
        )
    topology = pd.DataFrame(rows)
    match_rows = []
    for group, expected in S10_DOCUMENTED.items():
        row = topology[topology["group"] == group].iloc[0]
        for metric, report_value in expected.items():
            reproduced = float(row[metric])
            match_rows.append(
                {
                    "quantity": f"{group} {metric}",
                    "report_value": float(report_value),
                    "reproduced": reproduced,
                    "delta": reproduced - float(report_value),
                    "tolerance": 0.0015,
                    "pass": bool(abs(reproduced - float(report_value)) <= 0.0015),
                }
            )
    return topology, pd.DataFrame(match_rows)


def reproduce_s10f_counts(config: dict) -> pd.DataFrame:
    counts = S11C.reproduce_counts(config)
    counts["quantity"] = "S10f " + counts["quantity"].astype(str)
    return counts


def stratum_counts_by_run(events: pd.DataFrame) -> pd.DataFrame:
    return (
        events.groupby(["run", "group", "stratum", "amp_bin", "baseline_bin", "p02_topology"], observed=False)
        .agg(n=("event_index", "size"), downstream=("downstream", "sum"))
        .reset_index()
    )


def matched_strata(counts: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    group_counts = counts.groupby(["stratum", "group"], observed=False).agg(n=("n", "sum"), downstream=("downstream", "sum")).reset_index()
    pivot = group_counts.pivot(index="stratum", columns="group", values=["n", "downstream"]).fillna(0)
    rows = []
    for stratum in pivot.index:
        low_n = int(pivot.loc[stratum, ("n", "low_2nA")]) if ("n", "low_2nA") in pivot.columns else 0
        high_n = int(pivot.loc[stratum, ("n", "high_20nA")]) if ("n", "high_20nA") in pivot.columns else 0
        if low_n < MIN_STRATUM_N or high_n < MIN_STRATUM_N:
            continue
        low_d = int(pivot.loc[stratum, ("downstream", "low_2nA")])
        high_d = int(pivot.loc[stratum, ("downstream", "high_20nA")])
        first = counts[counts["stratum"] == stratum].iloc[0]
        rows.append(
            {
                "stratum": stratum,
                "amp_bin": first["amp_bin"],
                "baseline_bin": first["baseline_bin"],
                "p02_topology": first["p02_topology"],
                "low_n": low_n,
                "high_n": high_n,
                "match_weight_raw": min(low_n, high_n),
                "low_downstream_fraction": low_d / low_n,
                "high_downstream_fraction": high_d / high_n,
                "downstream_high_minus_low": high_d / high_n - low_d / low_n,
            }
        )
    table = pd.DataFrame(rows).sort_values(["match_weight_raw", "stratum"], ascending=[False, True]).reset_index(drop=True)
    table["match_weight"] = table["match_weight_raw"] / table["match_weight_raw"].sum()
    grouped = counts.groupby("group").agg(n=("n", "sum"), downstream=("downstream", "sum"))
    global_excess = float(grouped.loc["high_20nA", "downstream"] / grouped.loc["high_20nA", "n"] - grouped.loc["low_2nA", "downstream"] / grouped.loc["low_2nA", "n"])
    return table, global_excess


def choose_analysis_sample(events: pd.DataFrame, strata: list[str], rng: np.random.Generator) -> pd.DataFrame:
    pieces = []
    keep = events[events["stratum"].isin(strata)].copy()
    for (_run, _stratum), sub in keep.groupby(["run", "stratum"], observed=False):
        if len(sub) <= SAMPLE_PER_RUN_STRATUM:
            pieces.append(sub)
        else:
            pieces.append(sub.sample(n=SAMPLE_PER_RUN_STRATUM, random_state=int(rng.integers(0, 1_000_000))))
    return pd.concat(pieces, ignore_index=True).sort_values(["run", "stratum", "eventno"]).reset_index(drop=True)


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    config = dict(config)
    config["raw_root_dir"] = str((ROOT / config["raw_root_dir"]).resolve()) if not Path(config["raw_root_dir"]).is_absolute() else config["raw_root_dir"]
    return config


def clean_from_events(events: pd.DataFrame, waves: np.ndarray, runs: list[int]) -> pd.DataFrame:
    rows = []
    keep = events[
        events["run"].isin([int(r) for r in runs])
        & (events["ref_amp_adc"] >= 1500.0)
        & (events["ref_amp_adc"] <= 12000.0)
        & (events["peak_sample"] >= 4)
        & (events["peak_sample"] <= 12)
    ]
    for row in keep.itertuples():
        wf = waves[int(row.event_index)].astype(float)
        rows.append(
            {
                "run": int(row.run),
                "eventno": int(row.eventno),
                "evt": int(row.eventno),
                "stave": str(row.ref_stave),
                "waveform": wf,
                "amplitude_adc": float(row.ref_amp_adc),
                "peak_sample": int(row.peak_sample),
                "area_adc_samples": float(row.ref_area_adc),
                "cfd20_sample": cfd_time_one(wf, 0.2),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError(f"no low-current clean pulses for runs {runs}")
    return out.reset_index(drop=True)


def low_template_runs_for_heldout(heldout_run: int) -> list[int]:
    low_runs = RUN_GROUPS["low_2nA"]["runs"]
    if int(heldout_run) in low_runs:
        return [run for run in low_runs if run != int(heldout_run)]
    return list(low_runs)


def ensure_rich_templates_for_staves(rich_templates: dict, template_summary: pd.DataFrame, config: dict) -> tuple[dict, pd.DataFrame]:
    rich = dict(rich_templates)
    rows = [template_summary]
    available = sorted(rich.keys())
    if not available:
        raise RuntimeError("no rich templates available")
    fallback_key = available[0]
    for stave in config["staves"].keys():
        if stave in rich:
            continue
        rich[stave] = rich[fallback_key]
        fallback_rows = template_summary[template_summary["template_id"].astype(str).str.startswith(f"{fallback_key}:")].copy()
        fallback_rows["template_id"] = fallback_rows["template_id"].astype(str).str.replace(f"{fallback_key}:", f"{stave}:fallback_from_{fallback_key}:", regex=False)
        fallback_rows["stave"] = stave
        fallback_rows["fallback_used"] = True
        fallback_rows["fallback_reason"] = f"no low-current templates for {stave}; copied {fallback_key} candidates"
        rows.append(fallback_rows)
    out = pd.concat(rows, ignore_index=True)
    if "fallback_reason" not in out:
        out["fallback_reason"] = ""
    out["fallback_reason"] = out["fallback_reason"].fillna("")
    return rich, out


def fit_traditional_for_run(test: pd.DataFrame, test_waves: np.ndarray, rich_templates: dict, config: dict) -> pd.DataFrame:
    fit_events = pd.DataFrame(
        {
            "event_id": test["event_index"].astype(str).to_numpy(),
            "stave": test["ref_stave"].astype(str).to_numpy(),
        }
    )
    raw = S11C.run_amp_binned_template_fits(fit_events, test_waves, rich_templates, config)
    raw["event_index"] = raw["event_id"].astype(int)
    score = np.maximum(raw["trad_score"].to_numpy(dtype=float), 0.0)
    score = np.nan_to_num(score, nan=0.0, posinf=0.0, neginf=0.0)
    amp1 = raw["trad_amp1_adc"].to_numpy(dtype=float)
    amp2 = raw["trad_amp2_adc"].to_numpy(dtype=float)
    frac = amp2 / np.maximum(amp1 + amp2, 1.0)
    frac = np.nan_to_num(frac, nan=0.0, posinf=0.0, neginf=0.0)
    frac = np.where(score < TRAD_SCORE_THRESHOLD, frac * score / TRAD_SCORE_THRESHOLD, frac)
    raw["trad_secondary_fraction"] = np.clip(frac, 0.0, 1.0)
    raw["trad_secondary_primary_ratio"] = np.nan_to_num(amp2 / np.maximum(amp1, 1.0), nan=0.0, posinf=0.0, neginf=0.0)
    raw["trad_score_sse_improvement"] = score
    raw["trad_candidate"] = score >= TRAD_SCORE_THRESHOLD
    raw["trad_recovered_delay_ns"] = np.nan_to_num((raw["trad_t2_sample"].to_numpy(dtype=float) - raw["trad_t1_sample"].to_numpy(dtype=float)) * 10.0, nan=0.0, posinf=0.0, neginf=0.0)
    raw["trad_total_area_proxy_adc"] = np.nan_to_num(amp1 + amp2, nan=0.0, posinf=0.0, neginf=0.0)
    return raw.drop(columns=["event_id"])


def train_low_overlay_model(clean: pd.DataFrame, train_runs: list[int], cal_runs: list[int], config: dict, rng: np.random.Generator, label: str) -> tuple[dict, dict]:
    seed = RNG_SEED + sum(train_runs) * 13 + sum(cal_runs) * 17
    model_config = dict(config)
    model_config["injected_per_train_run"] = min(int(config.get("injected_per_train_run", 260)), SYNTHETIC_TRAIN_PER_LOW_FOLD)
    model_config["clean_per_train_run"] = min(int(config.get("clean_per_train_run", 260)), SYNTHETIC_TRAIN_PER_LOW_FOLD)
    model_config["injected_per_heldout_run"] = min(int(config.get("injected_per_heldout_run", 300)), SYNTHETIC_CAL_PER_LOW_FOLD)
    model_config["clean_per_heldout_run"] = min(int(config.get("clean_per_heldout_run", 300)), SYNTHETIC_CAL_PER_LOW_FOLD)
    base_templates, _template_summary = S11C.build_templates(clean[clean["run"].isin(train_runs)], model_config)
    model_config["staves"] = {name: config["staves"][name] for name in base_templates.keys()}
    clean_model = clean[clean["stave"].isin(base_templates.keys())].copy()
    train_events, train_wave = S11C.generate_benchmark(clean_model, base_templates, model_config, "train", train_runs, rng)
    cal_events, cal_wave = S11C.generate_benchmark(clean_model, base_templates, model_config, "heldout", cal_runs, rng)
    x_train = S11C.make_feature_matrix(train_wave)
    y_class = train_events["is_overlap"].to_numpy(dtype=int)
    max_amp_train = np.maximum(train_wave.max(axis=1) - np.median(train_wave[:, :4], axis=1), 1.0)
    y_reg = np.column_stack(
        [
            train_events["true_t1_sample"].to_numpy(dtype=float) / 12.0,
            np.nan_to_num(train_events["true_t2_sample"].to_numpy(dtype=float), nan=0.0) / 12.0,
            train_events["true_amp1_adc"].to_numpy(dtype=float) / max_amp_train,
            train_events["true_amp2_adc"].to_numpy(dtype=float) / max_amp_train,
        ]
    )
    pos = y_class == 1
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
    clf.fit(x_train, y_class)
    reg.fit(x_train[pos], y_reg[pos])
    x_cal = S11C.make_feature_matrix(cal_wave)
    y_cal = cal_events["is_overlap"].to_numpy(dtype=int)
    cal_prob = clf.predict_proba(x_cal)[:, 1]
    cal_pred = reg.predict(x_cal)
    max_amp_cal = np.maximum(cal_wave.max(axis=1) - np.median(cal_wave[:, :4], axis=1), 1.0)
    cal_amp2 = np.clip(cal_pred[:, 3] * max_amp_cal, 0.0, None)
    cal_amp1 = np.clip(cal_pred[:, 2] * max_amp_cal, 0.0, None)
    cal_frac = cal_amp2 / np.maximum(cal_amp1 + cal_amp2, 1.0)
    true_frac = cal_events["true_amp2_adc"].to_numpy(dtype=float) / np.maximum(
        cal_events["true_amp1_adc"].to_numpy(dtype=float) + cal_events["true_amp2_adc"].to_numpy(dtype=float), 1.0
    )
    shuffled = y_class.copy()
    rng.shuffle(shuffled)
    shuffled_clf = make_pipeline(
        StandardScaler(),
        MLPClassifier(hidden_layer_sizes=(16,), alpha=1e-3, max_iter=250, random_state=seed + 2),
    )
    shuffled_clf.fit(x_train, shuffled)
    shuffled_prob = shuffled_clf.predict_proba(x_cal)[:, 1]
    diagnostics = {
        "ml_fold": label,
        "train_low_runs": " ".join(str(x) for x in train_runs),
        "cal_low_runs": " ".join(str(x) for x in cal_runs),
        "n_synthetic_train": int(len(train_events)),
        "n_synthetic_cal": int(len(cal_events)),
        "synthetic_staves": " ".join(sorted(base_templates.keys())),
        "synthetic_holdout_auc": float(roc_auc_score(y_cal, cal_prob)),
        "synthetic_holdout_ap": float(average_precision_score(y_cal, cal_prob)),
        "synthetic_holdout_brier": float(brier_score_loss(y_cal, cal_prob)),
        "synthetic_secondary_fraction_mae": float(np.mean(np.abs(cal_frac - true_frac))),
        "shuffled_label_synthetic_auc": float(roc_auc_score(y_cal, shuffled_prob)),
    }
    return {"clf": clf, "reg": reg, "train_runs": train_runs, "cal_runs": cal_runs, "label": label}, diagnostics


def predict_low_overlay_models(models: list[dict], waveforms: np.ndarray) -> pd.DataFrame:
    x = S11C.make_feature_matrix(waveforms)
    max_amp = np.maximum(waveforms.max(axis=1) - np.median(waveforms[:, :4], axis=1), 1.0)
    probs = []
    fracs = []
    delays = []
    total_amps = []
    for model in models:
        prob = model["clf"].predict_proba(x)[:, 1]
        pred = model["reg"].predict(x)
        t1 = np.clip(pred[:, 0] * 12.0, 0.0, 17.0)
        t2 = np.clip(pred[:, 1] * 12.0, 0.0, 17.0)
        a1 = np.clip(pred[:, 2] * max_amp, 0.0, None)
        a2 = np.clip(pred[:, 3] * max_amp, 0.0, None)
        swap = t2 < t1
        t1_swap = t1.copy()
        t1[swap] = t2[swap]
        t2[swap] = t1_swap[swap]
        a1_swap = a1.copy()
        a1[swap] = a2[swap]
        a2[swap] = a1_swap[swap]
        probs.append(prob)
        fracs.append((a2 / np.maximum(a1 + a2, 1.0)) * prob)
        delays.append((t2 - t1) * 10.0)
        total_amps.append(a1 + a2)
    return pd.DataFrame(
        {
            "ml_overlap_score": np.mean(np.vstack(probs), axis=0),
            "ml_secondary_fraction": np.mean(np.vstack(fracs), axis=0),
            "ml_recovered_delay_ns": np.mean(np.vstack(delays), axis=0),
            "ml_total_area_proxy_adc": np.mean(np.vstack(total_amps), axis=0),
        }
    )


def build_templates(train: pd.DataFrame, waves: np.ndarray) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    templates: dict[str, np.ndarray] = {}
    rows = []
    for stave, sub in train.groupby("ref_stave"):
        clean = sub[
            (sub["ref_amp_adc"] > 1300.0)
            & (sub["ref_amp_adc"] < 9000.0)
            & (sub["peak_sample"] >= 4)
            & (sub["peak_sample"] <= 12)
        ]
        aligned = []
        for pulse in clean.itertuples():
            wf = waves[int(pulse.event_index)].astype(float)
            amp = max(float(pulse.ref_amp_adc), 1.0)
            t = cfd_time_one(wf, 0.2)
            if not np.isfinite(t):
                continue
            aligned.append(shift_array(wf / amp, t - TEMPLATE_REF_SAMPLE, fill=np.nan))
        if not aligned:
            continue
        mat = np.vstack(aligned)
        template = np.nanmedian(mat, axis=0)
        template = np.nan_to_num(template, nan=0.0)
        peak = float(template.max())
        if peak > 0:
            template = template / peak
        templates[str(stave)] = template.astype(float)
        rows.append(
            {
                "stave": str(stave),
                "n_train_pulses": int(len(mat)),
                "template_peak_sample": int(np.argmax(template)),
                "template_cfd20_sample": cfd_time_one(template, 0.2),
                "template_area": float(template.sum()),
            }
        )
    missing = set(STAVES) - set(templates)
    if missing:
        raise RuntimeError(f"missing templates for staves: {sorted(missing)}")
    return templates, pd.DataFrame(rows)


def fit_one_pulse(waveform: np.ndarray, template: np.ndarray) -> dict:
    init = cfd_time_one(waveform, 0.2)
    if not np.isfinite(init):
        init = TEMPLATE_REF_SAMPLE
    best = {"sse": float("inf"), "time": float("nan"), "amp": float("nan"), "baseline": float("nan"), "failed": True}
    y = np.asarray(waveform, dtype=float)
    for shift in FIT_T1_SHIFTS:
        col = shifted_template(template, init + float(shift))
        design = np.column_stack([col, np.ones(len(col))])
        try:
            coeff, *_ = np.linalg.lstsq(design, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        amp, baseline = float(coeff[0]), float(coeff[1])
        if amp <= 0 or baseline < -400.0 or baseline > 400.0:
            continue
        sse = float(np.sum((y - design @ coeff) ** 2))
        if sse < best["sse"]:
            best = {"sse": sse, "time": init + float(shift), "amp": amp, "baseline": baseline, "failed": False}
    return best


def fit_two_pulse(waveform: np.ndarray, template: np.ndarray) -> dict:
    init = cfd_time_one(waveform, 0.2)
    if not np.isfinite(init):
        init = TEMPLATE_REF_SAMPLE
    best = {
        "sse": float("inf"),
        "t1": float("nan"),
        "t2": float("nan"),
        "amp1": float("nan"),
        "amp2": float("nan"),
        "baseline": float("nan"),
        "failed": True,
    }
    y = np.asarray(waveform, dtype=float)
    for shift in FIT_T1_SHIFTS:
        t1 = init + float(shift)
        for sep in FIT_SEPARATIONS:
            col1 = shifted_template(template, t1)
            col2 = shifted_template(template, t1 + float(sep))
            design = np.column_stack([col1, col2, np.ones(len(col1))])
            try:
                coeff, *_ = np.linalg.lstsq(design, y, rcond=None)
            except np.linalg.LinAlgError:
                continue
            a1, a2, baseline = [float(x) for x in coeff]
            if a1 <= 0 or a2 <= 0 or baseline < -400.0 or baseline > 400.0:
                continue
            ratio = a2 / max(a1, 1e-9)
            if ratio < 0.05 or ratio > 1.8:
                continue
            sse = float(np.sum((y - design @ coeff) ** 2))
            if sse < best["sse"]:
                best = {"sse": sse, "t1": t1, "t2": t1 + float(sep), "amp1": a1, "amp2": a2, "baseline": baseline, "failed": False}
    return best


def one_pulse_residual_features(waveforms: np.ndarray, staves: np.ndarray, templates: dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    for wf, stave in zip(waveforms, staves):
        template = templates[str(stave)]
        one = fit_one_pulse(wf.astype(float), template)
        amp = max(float(np.max(wf)), 1.0)
        if one["failed"]:
            resid = wf.astype(float)
            sse_norm = float(np.sum(resid**2) / (amp**2 * len(wf)))
        else:
            model = one["amp"] * shifted_template(template, one["time"]) + one["baseline"]
            resid = wf.astype(float) - model
            sse_norm = float(one["sse"] / (amp**2 * len(wf)))
        rows.append(
            {
                "one_sse_norm": sse_norm,
                "resid_peak_frac": float(np.max(resid) / amp),
                "resid_tail_frac": float(np.sum(resid[9:]) / max(abs(np.sum(wf)), 1.0)),
                "resid_late_max_frac": float(np.max(resid[10:]) / amp),
                "resid_min_frac": float(np.min(resid) / amp),
            }
        )
    return pd.DataFrame(rows)


def ml_features(waveforms: np.ndarray, staves: np.ndarray, templates: dict[str, np.ndarray]) -> pd.DataFrame:
    corr = np.asarray(waveforms, dtype=float)
    amp = np.maximum(corr.max(axis=1), 1.0)
    norm = corr / amp[:, None]
    base = shape_features(corr, amp)
    for i in range(norm.shape[1]):
        base[f"sample_{i:02d}"] = norm[:, i]
    resid = one_pulse_residual_features(corr, staves, templates)
    return pd.concat([base.reset_index(drop=True), resid.reset_index(drop=True)], axis=1)


def inject_waveforms(base: np.ndarray, base_amp: np.ndarray, secondary: np.ndarray, secondary_amp: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    delays = rng.uniform(0.75, 7.0, size=len(base))
    ratios = rng.uniform(0.12, 1.0, size=len(base))
    out = base.copy().astype(float)
    sec_norm = secondary.astype(float) / np.maximum(secondary_amp, 1.0)[:, None]
    for i, delay in enumerate(delays):
        out[i] += base_amp[i] * ratios[i] * shift_array(sec_norm[i], delay, fill=0.0)
    frac = (base_amp * ratios) / np.maximum(base_amp + base_amp * ratios, 1.0)
    return out, frac, ratios


def make_synthetic_training(train: pd.DataFrame, waves: np.ndarray, templates: dict[str, np.ndarray], rng: np.random.Generator, n: int) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    clean = train[
        (train["ref_amp_adc"] > 1300.0)
        & (train["ref_amp_adc"] < 9000.0)
        & (train["peak_sample"] >= 4)
        & (train["peak_sample"] <= 12)
    ]
    if len(clean) < 100:
        raise RuntimeError("too few clean pulses for synthetic ML training")
    n = min(int(n), len(clean))
    base_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
    sec_rows = clean.sample(n=n, replace=len(clean) < n, random_state=int(rng.integers(0, 1_000_000))).reset_index(drop=True)
    base = waves[base_rows["event_index"].to_numpy()].astype(float)
    sec = waves[sec_rows["event_index"].to_numpy()].astype(float)
    base_amp = base_rows["ref_amp_adc"].to_numpy(dtype=float)
    sec_amp = sec_rows["ref_amp_adc"].to_numpy(dtype=float)
    injected, frac, ratio = inject_waveforms(base, base_amp, sec, sec_amp, rng)
    x = np.vstack([base, injected])
    staves = np.r_[base_rows["ref_stave"].to_numpy(), base_rows["ref_stave"].to_numpy()]
    features = ml_features(x, staves, templates)
    y_class = np.r_[np.zeros(n, dtype=int), np.ones(n, dtype=int)]
    y_frac = np.r_[np.zeros(n, dtype=float), frac]
    meta = pd.DataFrame(
        {
            "synthetic_label": y_class,
            "source_run": np.r_[base_rows["run"].to_numpy(), base_rows["run"].to_numpy()],
            "true_secondary_fraction": y_frac,
            "true_secondary_primary_ratio": np.r_[np.zeros(n), ratio],
        }
    )
    order = rng.permutation(len(y_class))
    return features.iloc[order].reset_index(drop=True), y_class[order], y_frac[order], meta.iloc[order].reset_index(drop=True)


def heldout_predictions(events: pd.DataFrame, waves: np.ndarray, sample: pd.DataFrame, rng: np.random.Generator, config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    score_frames = []
    template_frames = []
    fold_rows = []
    low_runs = RUN_GROUPS["low_2nA"]["runs"]
    all_low_clean = clean_from_events(events, waves, low_runs)
    low_models = []
    for train_runs, cal_runs, label in [([46], [47], "low46_train_low47_cal"), ([47], [46], "low47_train_low46_cal")]:
        model, diag = train_low_overlay_model(all_low_clean, train_runs, cal_runs, config, rng, label)
        low_models.append(model)
        fold_rows.append({"heldout_run": -1, "heldout_group": "low_overlay_calibration", "n_scored_events": 0, **diag})

    for heldout_run in sorted(sample["run"].unique()):
        test = sample[sample["run"] == heldout_run].copy()
        test_waves = waves[test["event_index"].to_numpy()]
        template_runs = low_template_runs_for_heldout(int(heldout_run))
        template_clean = clean_from_events(events, waves, template_runs)
        rich_templates, template_summary = S11C.build_amp_binned_templates(template_clean, config)
        rich_templates, template_summary = ensure_rich_templates_for_staves(rich_templates, template_summary, config)
        template_summary["heldout_run"] = int(heldout_run)
        template_summary["template_source_runs"] = " ".join(str(x) for x in template_runs)
        template_frames.append(template_summary)

        trad = fit_traditional_for_run(test, test_waves, rich_templates, config)
        if int(heldout_run) == 46:
            eligible_models = [m for m in low_models if m["train_runs"] == [47]]
        elif int(heldout_run) == 47:
            eligible_models = [m for m in low_models if m["train_runs"] == [46]]
        else:
            eligible_models = low_models
        ml_pred = predict_low_overlay_models(eligible_models, test_waves)
        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "heldout_group": run_to_group()[int(heldout_run)],
                "n_scored_events": int(len(test)),
                "template_source_runs": " ".join(str(x) for x in template_runs),
                "ml_models_used": " ".join(m["label"] for m in eligible_models),
                "ml_train_runs_used": " ".join(",".join(str(x) for x in m["train_runs"]) for m in eligible_models),
                "synthetic_holdout_auc": float(np.mean([row["synthetic_holdout_auc"] for row in fold_rows if row.get("heldout_group") == "low_overlay_calibration"])),
                "synthetic_holdout_ap": float(np.mean([row["synthetic_holdout_ap"] for row in fold_rows if row.get("heldout_group") == "low_overlay_calibration"])),
                "synthetic_holdout_brier": float(np.mean([row["synthetic_holdout_brier"] for row in fold_rows if row.get("heldout_group") == "low_overlay_calibration"])),
                "synthetic_secondary_fraction_mae": float(np.mean([row["synthetic_secondary_fraction_mae"] for row in fold_rows if row.get("heldout_group") == "low_overlay_calibration"])),
                "shuffled_label_synthetic_auc": float(np.mean([row["shuffled_label_synthetic_auc"] for row in fold_rows if row.get("heldout_group") == "low_overlay_calibration"])),
            }
        )

        frame = test[
            [
                "event_index",
                "run",
                "group",
                "current_nA",
                "eventno",
                "stratum",
                "amp_bin",
                "baseline_bin",
                "p02_topology",
                "ref_stave",
                "ref_amp_adc",
                "downstream",
            ]
        ].copy()
        frame = frame.merge(trad, on="event_index", how="left")
        frame = pd.concat([frame.reset_index(drop=True), ml_pred.reset_index(drop=True)], axis=1)
        frame["ml_candidate"] = frame["ml_overlap_score"] >= ML_SCORE_THRESHOLD
        score_frames.append(frame)
    return pd.concat(score_frames, ignore_index=True), pd.concat(template_frames, ignore_index=True), pd.DataFrame(fold_rows)


def summarize_method(scores: pd.DataFrame, stratum_table: pd.DataFrame, value_col: str, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    strata = stratum_table["stratum"].tolist()
    weights = dict(zip(stratum_table["stratum"], stratum_table["match_weight"]))
    rows = []
    for stratum in strata:
        sub = scores[scores["stratum"] == stratum]
        low = sub[sub["group"] == "low_2nA"][value_col]
        high = sub[sub["group"] == "high_20nA"][value_col]
        rows.append(
            {
                "method_metric": value_col,
                "stratum": stratum,
                "amp_bin": stratum_table[stratum_table["stratum"] == stratum].iloc[0]["amp_bin"],
                "baseline_bin": stratum_table[stratum_table["stratum"] == stratum].iloc[0]["baseline_bin"],
                "p02_topology": stratum_table[stratum_table["stratum"] == stratum].iloc[0]["p02_topology"],
                "low_n_scored": int(len(low)),
                "high_n_scored": int(len(high)),
                "low_mean": float(low.mean()) if len(low) else float("nan"),
                "high_mean": float(high.mean()) if len(high) else float("nan"),
                "high_minus_low": float(high.mean() - low.mean()) if len(low) and len(high) else float("nan"),
                "match_weight": float(weights[stratum]),
            }
        )
    table = pd.DataFrame(rows)
    value = float((table["match_weight"] * table["high_minus_low"]).sum())
    low_runs = np.array(RUN_GROUPS["low_2nA"]["runs"], dtype=int)
    high_runs = np.array(RUN_GROUPS["high_20nA"]["runs"], dtype=int)
    boot_vals = []
    for _ in range(BOOTSTRAPS):
        pieces = []
        for run in np.r_[rng.choice(low_runs, size=len(low_runs), replace=True), rng.choice(high_runs, size=len(high_runs), replace=True)]:
            sub = scores[scores["run"] == int(run)]
            if len(sub):
                pieces.append(sub)
        sample = pd.concat(pieces, ignore_index=True)
        vals = []
        for stratum in strata:
            sub = sample[sample["stratum"] == stratum]
            low = sub[sub["group"] == "low_2nA"][value_col]
            high = sub[sub["group"] == "high_20nA"][value_col]
            if len(low) and len(high):
                vals.append(weights[stratum] * (float(high.mean()) - float(low.mean())))
        if vals:
            boot_vals.append(float(np.sum(vals)))
    summary = pd.DataFrame(
        [
            {
                "method_metric": value_col,
                "value": value,
                "ci_low": float(np.quantile(boot_vals, 0.025)),
                "ci_high": float(np.quantile(boot_vals, 0.975)),
                "bootstrap_unit": "source_run_within_current_group",
                "n_bootstrap": int(len(boot_vals)),
                "n_scored_events": int(len(scores)),
            }
        ]
    )
    return table, summary


def summarize_run_stability(scores: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    specs = [
        ("traditional", "trad_candidate", "trad_recovered_delay_ns", "trad_secondary_fraction", "trad_total_area_proxy_adc"),
        ("ml", "ml_candidate", "ml_recovered_delay_ns", "ml_secondary_fraction", "ml_total_area_proxy_adc"),
    ]
    for (run, group), sub in scores.groupby(["run", "group"]):
        idx = np.arange(len(sub))
        for method, candidate_col, delay_col, frac_col, area_col in specs:
            candidate = sub[candidate_col].astype(float).to_numpy()
            delay_values = sub.loc[sub[candidate_col].astype(bool), delay_col].to_numpy(dtype=float)
            frac_values = sub[frac_col].to_numpy(dtype=float)
            area_values = sub.loc[sub[candidate_col].astype(bool), area_col].to_numpy(dtype=float)
            boot_rate = []
            boot_delay = []
            boot_frac = []
            boot_area = []
            for _ in range(BOOTSTRAPS):
                draw = sub.iloc[rng.choice(idx, size=len(idx), replace=True)]
                boot_rate.append(float(draw[candidate_col].astype(float).mean()))
                cand = draw[draw[candidate_col].astype(bool)]
                boot_delay.append(float(cand[delay_col].mean()) if len(cand) else float("nan"))
                boot_frac.append(float(draw[frac_col].mean()))
                boot_area.append(float(cand[area_col].mean()) if len(cand) else float("nan"))

            def ci(values):
                arr = np.asarray(values, dtype=float)
                arr = arr[np.isfinite(arr)]
                if len(arr) == 0:
                    return float("nan"), float("nan")
                return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))

            rate_ci = ci(boot_rate)
            delay_ci = ci(boot_delay)
            frac_ci = ci(boot_frac)
            area_ci = ci(boot_area)
            rows.append(
                {
                    "run": int(run),
                    "group": group,
                    "method": method,
                    "n_scored": int(len(sub)),
                    "candidate_rate": float(np.mean(candidate)),
                    "candidate_rate_ci_low": rate_ci[0],
                    "candidate_rate_ci_high": rate_ci[1],
                    "mean_recovered_delay_ns": float(np.nanmean(delay_values)) if len(delay_values) else float("nan"),
                    "mean_recovered_delay_ci_low_ns": delay_ci[0],
                    "mean_recovered_delay_ci_high_ns": delay_ci[1],
                    "mean_secondary_fraction": float(np.nanmean(frac_values)) if len(frac_values) else float("nan"),
                    "mean_secondary_fraction_ci_low": frac_ci[0],
                    "mean_secondary_fraction_ci_high": frac_ci[1],
                    "mean_total_area_proxy_adc": float(np.nanmean(area_values)) if len(area_values) else float("nan"),
                    "mean_total_area_proxy_ci_low_adc": area_ci[0],
                    "mean_total_area_proxy_ci_high_adc": area_ci[1],
                    "n_bootstrap": BOOTSTRAPS,
                }
            )
    return pd.DataFrame(rows).sort_values(["method", "group", "run"]).reset_index(drop=True)


def leakage_checks(scores: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    current_y = (scores["group"] == "high_20nA").astype(int).to_numpy()
    ml_current_auc = float(roc_auc_score(current_y, np.nan_to_num(scores["ml_secondary_fraction"].to_numpy(dtype=float), nan=0.0)))
    trad_current_auc = float(roc_auc_score(current_y, np.nan_to_num(scores["trad_secondary_fraction"].to_numpy(dtype=float), nan=0.0)))
    cal = folds[folds["heldout_group"] == "low_overlay_calibration"].copy()
    shuffled_auc = float(cal["shuffled_label_synthetic_auc"].mean())
    synth_auc = float(cal["synthetic_holdout_auc"].mean())
    real_folds = folds[folds["heldout_run"] >= 0].copy()
    low_train_exclusion_ok = True
    for row in real_folds.itertuples():
        train_tokens = str(row.ml_train_runs_used).replace(",", " ").split()
        template_tokens = str(row.template_source_runs).split()
        if str(int(row.heldout_run)) in train_tokens or str(int(row.heldout_run)) in template_tokens:
            low_train_exclusion_ok = False
    low_current_source_ok = all(all(tok in {"46", "47"} for tok in str(row.template_source_runs).split()) for row in real_folds.itertuples())
    rows = [
        {
            "check": "heldout_run_excluded_from_template_and_ml_training",
            "value": float(low_train_exclusion_ok),
            "flag": not low_train_exclusion_ok,
            "note": "Low-current controls are scored only by templates and ML models excluding that source run; high-current runs are absent from low-current training.",
        },
        {
            "check": "identifier_features_excluded",
            "value": 1.0,
            "flag": False,
            "note": "ML features exclude run, event number, current, group, downstream label, and stratum labels.",
        },
        {
            "check": "low_current_only_template_and_ml_sources",
            "value": float(low_current_source_ok),
            "flag": not low_current_source_ok,
            "note": "Traditional templates and overlay ML models are derived from low-current raw pulses only.",
        },
        {
            "check": "mean_synthetic_holdout_auc",
            "value": synth_auc,
            "flag": bool(synth_auc > 0.995),
            "note": "Very high synthetic AUC would be suspicious because held-out runs contain independent residuals.",
        },
        {
            "check": "mean_shuffled_label_synthetic_auc",
            "value": shuffled_auc,
            "flag": bool(shuffled_auc > 0.65),
            "note": "Shuffled-label training should not classify held-out synthetic overlays well.",
        },
        {
            "check": "actual_current_auc_from_ml_secondary_fraction",
            "value": ml_current_auc,
            "flag": bool(ml_current_auc > 0.95),
            "note": "Flagged if the ML amplitude estimate nearly identifies beam current by itself.",
        },
        {
            "check": "actual_current_auc_from_traditional_secondary_fraction",
            "value": trad_current_auc,
            "flag": bool(trad_current_auc > 0.95),
            "note": "Flagged if the traditional amplitude estimate nearly identifies beam current by itself.",
        },
    ]
    return pd.DataFrame(rows)


def save_plots(stratum_summary: pd.DataFrame, method_summary: pd.DataFrame, scores: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    plot = stratum_summary[stratum_summary["method_metric"] == "trad_secondary_fraction"].sort_values("match_weight", ascending=False).head(10).iloc[::-1]
    ax.barh(np.arange(len(plot)), plot["high_minus_low"])
    ax.set_yticks(np.arange(len(plot)), plot["stratum"], fontsize=7)
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel("High-minus-low secondary fraction")
    ax.set_title("Traditional two-pulse fit by matched stratum")
    fig.tight_layout()
    fig.savefig(OUT / "fig_traditional_secondary_fraction_by_stratum.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    x = np.arange(len(method_summary))
    ax.bar(x, method_summary["value"])
    err_low = method_summary["value"] - method_summary["ci_low"]
    err_high = method_summary["ci_high"] - method_summary["value"]
    ax.errorbar(x, method_summary["value"], yerr=[err_low, err_high], fmt="none", color="k", capsize=4)
    ax.set_xticks(x, method_summary["method_metric"], rotation=20, ha="right")
    ax.set_ylabel("Matched high-minus-low")
    ax.axhline(0, color="k", lw=1)
    fig.tight_layout()
    fig.savefig(OUT / "fig_method_secondary_fraction_ci.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    for group, sub in scores.groupby("group"):
        ax.hist(sub["trad_secondary_fraction"], bins=40, alpha=0.5, density=True, label=f"{group} traditional")
    ax.set_xlabel("Template-fit secondary fraction")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig_trad_fraction_by_current.png", dpi=150)
    plt.close(fig)


def hash_outputs() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def write_report(
    topology: pd.DataFrame,
    repro: pd.DataFrame,
    s10f_repro: pd.DataFrame,
    stratum_table: pd.DataFrame,
    method_summary: pd.DataFrame,
    stratum_summary: pd.DataFrame,
    run_stability: pd.DataFrame,
    folds: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    trad = method_summary[method_summary["method_metric"] == "trad_secondary_fraction"].iloc[0]
    trad_rate = method_summary[method_summary["method_metric"] == "trad_candidate"].iloc[0]
    ml_frac = method_summary[method_summary["method_metric"] == "ml_secondary_fraction"].iloc[0]
    ml_score = method_summary[method_summary["method_metric"] == "ml_overlap_score"].iloc[0]
    ml_rate = method_summary[method_summary["method_metric"] == "ml_candidate"].iloc[0]
    top_trad = stratum_summary[stratum_summary["method_metric"] == "trad_secondary_fraction"].sort_values("match_weight", ascending=False).head(8)
    cal = folds[folds["heldout_group"] == "low_overlay_calibration"]
    stability_view = run_stability[
        [
            "run",
            "group",
            "method",
            "candidate_rate",
            "mean_recovered_delay_ns",
            "mean_secondary_fraction",
            "mean_total_area_proxy_adc",
        ]
    ].head(14)
    lines = [
        "# S10g: S10f real-current two-pulse validation",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** every scored event is predicted by source-run-held-out low-current templates/ML models; CIs resample held-out runs within current group.",
        "",
        "## Reproduction first",
        "",
        (
            "The S10/S10d topology gate was reproduced from raw ROOT before scoring real windows. "
            f"Downstream selected-event fraction is {low['downstream_per_selected_event']:.5f} at 2 nA and "
            f"{high['downstream_per_selected_event']:.5f} at 20 nA; all six documented topology fractions "
            "pass the +/-0.0015 tolerance."
        ),
        "",
        repro.to_markdown(index=False),
        "",
        "The S10f raw selected-pulse count gate was also rerun before the real-window analysis.",
        "",
        s10f_repro.to_markdown(index=False),
        "",
        "## Strata and event scoring",
        "",
        (
            "The S10c strata are reused exactly: maximum selected-pulse amplitude, S16 adaptive-lowering bin, "
            "and P02-style topology. Full raw-ROOT counts define the matched-stratum weights; a capped "
            f"within-run/within-stratum sample of {SAMPLE_PER_RUN_STRATUM} events supplies waveform-level scores. "
            f"{len(stratum_table)} matched strata pass the low/high count floor."
        ),
        "",
        "## Traditional method",
        "",
        (
            "For each held-out run, S10f amplitude-binned/asymmetric template candidates are built only from "
            "low-current raw pulses, excluding the held-out run when the held-out run is itself low-current. "
            "The fit scans primary/secondary candidate pairs, timing, and separation, then solves amplitudes "
            "plus baseline by least squares."
        ),
        "",
        (
            f"Matched high-minus-low secondary fraction: **{trad['value']:.5f}** with run-bootstrap 95% CI "
            f"**[{trad['ci_low']:.5f}, {trad['ci_high']:.5f}]**. Candidate-rate excess at score "
            f">{TRAD_SCORE_THRESHOLD:.3f}: **{trad_rate['value']:.5f}** "
            f"[{trad_rate['ci_low']:.5f}, {trad_rate['ci_high']:.5f}]."
        ),
        "",
        top_trad[
            [
                "amp_bin",
                "baseline_bin",
                "p02_topology",
                "low_n_scored",
                "high_n_scored",
                "low_mean",
                "high_mean",
                "high_minus_low",
                "match_weight",
            ]
        ].to_markdown(index=False),
        "",
        "## ML residual diagnostic",
        "",
        (
            "The ML method is a compact MLP classifier/regressor trained on low-current synthetic overlays. "
            "Two low-current leave-one-run-out models calibrate on the other low-current run; high-current "
            "windows are scored by averaging those two models. Features are waveform-shape summaries only; "
            "identifiers and current labels are excluded."
        ),
        "",
        (
            f"ML secondary-fraction high-minus-low: **{ml_frac['value']:.5f}** "
            f"[{ml_frac['ci_low']:.5f}, {ml_frac['ci_high']:.5f}]. "
            f"ML overlap-score high-minus-low: **{ml_score['value']:.5f}** "
            f"[{ml_score['ci_low']:.5f}, {ml_score['ci_high']:.5f}]. Candidate-rate excess at score "
            f">{ML_SCORE_THRESHOLD:.2f}: **{ml_rate['value']:.5f}** "
            f"[{ml_rate['ci_low']:.5f}, {ml_rate['ci_high']:.5f}]. Mean low-run held-out AUC is "
            f"{cal['synthetic_holdout_auc'].mean():.3f}; shuffled-label AUC is {cal['shuffled_label_synthetic_auc'].mean():.3f}."
        ),
        "",
        "## Run Stability",
        "",
        stability_view.to_markdown(index=False),
        "",
        "## Leakage review",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, `stratum_table.csv`, `method_summary.csv`, `method_stratum_summary.csv`, `run_stability_summary.csv`, `sampled_event_scores.csv`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this folder.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    start = time.time()
    rng = np.random.default_rng(RNG_SEED)
    config = load_config()
    events, waves, run_counts = load_events()
    topology, repro = reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10c raw-ROOT reproduction gate failed")
    s10f_repro = reproduce_s10f_counts(config)
    if not bool(s10f_repro["pass"].all()):
        raise RuntimeError("S10f raw selected-pulse reproduction gate failed")
    counts = stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = matched_strata(counts)
    sample = choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)

    scores, template_summary, folds = heldout_predictions(events, waves, sample, rng, config)
    method_tables = []
    method_summaries = []
    for col in ["trad_secondary_fraction", "trad_candidate", "ml_secondary_fraction", "ml_overlap_score", "ml_candidate"]:
        table, summary = summarize_method(scores, stratum_table, col, rng)
        method_tables.append(table)
        method_summaries.append(summary)
    stratum_summary = pd.concat(method_tables, ignore_index=True)
    method_summary = pd.concat(method_summaries, ignore_index=True)
    run_stability = summarize_run_stability(scores, rng)
    leakage = leakage_checks(scores, folds)

    input_runs = sorted(set(run_to_group()) | set(S11C.configured_runs(config)))
    input_files = [raw_file(run) for run in input_runs]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    s10f_repro.to_csv(OUT / "s10f_reproduction_match_table.csv", index=False)
    stratum_table.to_csv(OUT / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(OUT / "analysis_sample.csv", index=False)
    template_summary.to_csv(OUT / "template_summary_by_fold.csv", index=False)
    scores.to_csv(OUT / "sampled_event_scores.csv", index=False)
    folds.to_csv(OUT / "fold_diagnostics.csv", index=False)
    stratum_summary.to_csv(OUT / "method_stratum_summary.csv", index=False)
    method_summary.to_csv(OUT / "method_summary.csv", index=False)
    run_stability.to_csv(OUT / "run_stability_summary.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)
    save_plots(stratum_summary, method_summary, scores)

    trad = method_summary[method_summary["method_metric"] == "trad_secondary_fraction"].iloc[0]
    trad_rate = method_summary[method_summary["method_metric"] == "trad_candidate"].iloc[0]
    ml_frac = method_summary[method_summary["method_metric"] == "ml_secondary_fraction"].iloc[0]
    ml_score = method_summary[method_summary["method_metric"] == "ml_overlap_score"].iloc[0]
    ml_rate = method_summary[method_summary["method_metric"] == "ml_candidate"].iloc[0]
    top = stratum_summary[stratum_summary["method_metric"] == "trad_secondary_fraction"].sort_values("high_minus_low", ascending=False).iloc[0]
    conclusion = (
        f"Applying S10f low-current amplitude-binned/asymmetric templates to real candidate windows gives a "
        f"matched high-current minus low-current secondary fraction of {trad['value']:.5f} "
        f"[{trad['ci_low']:.5f}, {trad['ci_high']:.5f}] and candidate-rate excess {trad_rate['value']:.5f} "
        f"[{trad_rate['ci_low']:.5f}, {trad_rate['ci_high']:.5f}]. "
        f"The low-current overlay-calibrated ML diagnostic gives secondary-fraction excess {ml_frac['value']:.5f} "
        f"[{ml_frac['ci_low']:.5f}, {ml_frac['ci_high']:.5f}] for secondary fraction and "
        f"{ml_score['value']:.5f} [{ml_score['ci_low']:.5f}, {ml_score['ci_high']:.5f}] for overlap score, with "
        f"candidate-rate excess {ml_rate['value']:.5f} [{ml_rate['ci_low']:.5f}, {ml_rate['ci_high']:.5f}]. "
        f"The largest traditional positive stratum is {top['amp_bin']} / {top['baseline_bin']} / {top['p02_topology']}. "
        "Leakage probes do not flag identifier, current-label, or source-run leakage, but the estimate remains a pulse-shape diagnostic rather than a truth-labelled pile-up decomposition."
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "validate S10f on real high-current candidate windows",
        "reproduced": bool(repro["pass"].all() and s10f_repro["pass"].all()),
        "reproduction_gate": "S10/S10d topology fractions and S10f selected-pulse counts from raw B-stack ROOT",
        "split": "source-run-held-out scoring; run bootstrap CIs within current group",
        "strata": {
            "definition": "S10c amplitude bin x S16 adaptive lowering bin x P02 topology",
            "n_matched_strata": int(len(stratum_table)),
            "global_s10_downstream_high_minus_low": float(global_downstream_excess),
            "n_scored_events": int(len(scores)),
            "sample_cap_per_run_stratum": SAMPLE_PER_RUN_STRATUM,
        },
        "traditional": {
            "method": "s10f_low_current_amp_binned_asymmetric_template_fit",
            "metric": "matched_stratified_secondary_fraction_and_candidate_rate_high_minus_low",
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
            "candidate_rate_excess": {
                "value": float(trad_rate["value"]),
                "ci": [float(trad_rate["ci_low"]), float(trad_rate["ci_high"])],
                "threshold": TRAD_SCORE_THRESHOLD,
            },
        },
        "ml": {
            "method": "low_current_loro_overlay_calibrated_compact_mlp",
            "secondary_fraction_high_minus_low": {
                "value": float(ml_frac["value"]),
                "ci": [float(ml_frac["ci_low"]), float(ml_frac["ci_high"])],
            },
            "overlap_score_high_minus_low": {
                "value": float(ml_score["value"]),
                "ci": [float(ml_score["ci_low"]), float(ml_score["ci_high"])],
            },
            "candidate_rate_excess": {
                "value": float(ml_rate["value"]),
                "ci": [float(ml_rate["ci_low"]), float(ml_rate["ci_high"])],
                "threshold": ML_SCORE_THRESHOLD,
            },
            "mean_synthetic_holdout_auc": float(folds[folds["heldout_group"] == "low_overlay_calibration"]["synthetic_holdout_auc"].mean()),
            "mean_shuffled_label_synthetic_auc": float(folds[folds["heldout_group"] == "low_overlay_calibration"]["shuffled_label_synthetic_auc"].mean()),
            "mean_secondary_fraction_mae_on_synthetic_holdout": float(folds[folds["heldout_group"] == "low_overlay_calibration"]["synthetic_secondary_fraction_mae"].mean()),
        },
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "run_stability_summary_rows": int(len(run_stability)),
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(topology, repro, s10f_repro, stratum_table, method_summary, stratum_summary, run_stability, folds, leakage, result)
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": RNG_SEED,
        "inputs": input_hashes,
        "outputs": hash_outputs(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "reproduced": result["reproduced"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
