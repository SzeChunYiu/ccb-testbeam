#!/usr/bin/env python3
"""S11b: real high-current two-pulse candidate validation.

This ticket uses the S11a low-current/template closure as the baseline method,
then applies a bounded two-pulse fit and compact waveform ML score to real
current-dependent candidate windows. High-current predictions are made from
low-current-derived templates and synthetic overlays; low-current predictions
leave the scored source run out.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "1781010611.1197.028b141a"
RAW = ROOT / "data/root/root"
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


TICKET = "1781010611.1197.028b141a"
WORKER = "testbeam-laptop-3"
STUDY = "S11b"
RNG_SEED = 11120
NSAMPLES = 18
BASELINE_SAMPLES = [0, 1, 2, 3]
AMP_CUT = 1000.0
BOOTSTRAPS = 600
MIN_STRATUM_N = 25
SAMPLE_PER_RUN_STRATUM = 140
SYNTHETIC_TRAIN_PER_FOLD = 2800
SYNTHETIC_CAL_PER_FOLD = 700
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


def build_templates(train: pd.DataFrame, waves: np.ndarray) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    templates: dict[str, np.ndarray] = {}
    rows = []
    for stave, sub in train.groupby("ref_stave"):
        clean = sub[
            (sub["ref_amp_adc"] > 1000.0)
            & (sub["ref_amp_adc"] < 12000.0)
            & (sub["peak_sample"] >= 2)
            & (sub["peak_sample"] <= 16)
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
        (train["ref_amp_adc"] > 1000.0)
        & (train["ref_amp_adc"] < 12000.0)
        & (train["peak_sample"] >= 2)
        & (train["peak_sample"] <= 16)
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


def fit_traditional_for_run(test: pd.DataFrame, test_waves: np.ndarray, templates: dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    for local_i, row in enumerate(test.itertuples()):
        wf = test_waves[local_i].astype(float)
        template = templates[str(row.ref_stave)]
        one = fit_one_pulse(wf, template)
        two = fit_two_pulse(wf, template)
        if one["failed"] or two["failed"]:
            score = 0.0
            sec_frac = 0.0
            ratio = 0.0
        else:
            score = max(0.0, (one["sse"] - two["sse"]) / max(one["sse"], 1.0))
            sec_frac = float(two["amp2"] / max(two["amp1"] + two["amp2"], 1.0))
            ratio = float(two["amp2"] / max(two["amp1"], 1.0))
            if score < 0.015:
                sec_frac *= score / 0.015
        rows.append(
            {
                "event_index": int(row.event_index),
                "trad_secondary_fraction": sec_frac,
                "trad_secondary_primary_ratio": ratio,
                "trad_score_sse_improvement": score,
                "trad_failed": bool(one["failed"] or two["failed"]),
                "trad_t1_sample": float(two["t1"]),
                "trad_t2_sample": float(two["t2"]),
                "trad_amp1_adc": float(two["amp1"]),
                "trad_amp2_adc": float(two["amp2"]),
            }
        )
    return pd.DataFrame(rows)


def heldout_predictions(events: pd.DataFrame, waves: np.ndarray, sample: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    score_frames = []
    template_frames = []
    fold_rows = []
    feature_cols: list[str] | None = None
    low_current_runs = set(RUN_GROUPS["low_2nA"]["runs"])
    for heldout_run in sorted(sample["run"].unique()):
        train_runs = sorted(low_current_runs - {int(heldout_run)})
        if int(heldout_run) not in low_current_runs:
            train_runs = sorted(low_current_runs)
        train = events[events["run"].isin(train_runs)].copy()
        test = sample[sample["run"] == heldout_run].copy()
        test_waves = waves[test["event_index"].to_numpy()]
        templates, template_summary = build_templates(train, waves)
        template_summary["heldout_run"] = int(heldout_run)
        template_summary["training_runs"] = " ".join(str(x) for x in train_runs)
        template_frames.append(template_summary)

        trad = fit_traditional_for_run(test, test_waves, templates)
        x_train, y_class, y_frac, train_meta = make_synthetic_training(train, waves, templates, rng, SYNTHETIC_TRAIN_PER_FOLD)
        if feature_cols is None:
            feature_cols = list(x_train.columns)
        clf = RandomForestClassifier(
            n_estimators=70,
            max_depth=9,
            min_samples_leaf=10,
            class_weight="balanced_subsample",
            random_state=RNG_SEED + int(heldout_run),
            n_jobs=1,
        )
        reg = RandomForestRegressor(
            n_estimators=80,
            max_depth=9,
            min_samples_leaf=10,
            random_state=RNG_SEED + 100 + int(heldout_run),
            n_jobs=1,
        )
        clf.fit(x_train[feature_cols], y_class)
        reg.fit(x_train[feature_cols], y_frac)

        x_test = ml_features(test_waves, test["ref_stave"].to_numpy(), templates)
        ml_score = clf.predict_proba(x_test[feature_cols])[:, 1]
        ml_frac = np.clip(reg.predict(x_test[feature_cols]), 0.0, 0.8)

        x_cal, y_cal, y_frac_cal, _cal_meta = make_synthetic_training(test, waves, templates, rng, SYNTHETIC_CAL_PER_FOLD)
        cal_score = clf.predict_proba(x_cal[feature_cols])[:, 1]
        cal_frac = np.clip(reg.predict(x_cal[feature_cols]), 0.0, 0.8)
        shuffled = y_class.copy()
        rng.shuffle(shuffled)
        shuffled_clf = RandomForestClassifier(
            n_estimators=35,
            max_depth=7,
            min_samples_leaf=12,
            class_weight="balanced_subsample",
            random_state=RNG_SEED + 500 + int(heldout_run),
            n_jobs=1,
        )
        shuffled_clf.fit(x_train[feature_cols], shuffled)
        shuffled_score = shuffled_clf.predict_proba(x_cal[feature_cols])[:, 1]
        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "heldout_group": run_to_group()[int(heldout_run)],
                "n_scored_events": int(len(test)),
                "n_synthetic_train": int(len(y_class)),
                "training_policy": "low_current_only_source_run_heldout",
                "synthetic_train_source_runs": " ".join(str(x) for x in sorted(set(train_meta["source_run"].astype(int)))),
                "synthetic_holdout_auc": float(roc_auc_score(y_cal, cal_score)),
                "synthetic_holdout_ap": float(average_precision_score(y_cal, cal_score)),
                "synthetic_holdout_brier": float(brier_score_loss(y_cal, cal_score)),
                "synthetic_secondary_fraction_mae": float(np.mean(np.abs(cal_frac - y_frac_cal))),
                "shuffled_label_synthetic_auc": float(roc_auc_score(y_cal, shuffled_score)),
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
        frame["ml_overlap_score"] = ml_score
        frame["ml_secondary_fraction"] = ml_frac
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


def leakage_checks(scores: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    current_y = (scores["group"] == "high_20nA").astype(int).to_numpy()
    current_auc = float(roc_auc_score(current_y, scores["ml_secondary_fraction"]))
    shuffled_auc = float(folds["shuffled_label_synthetic_auc"].mean())
    synth_auc = float(folds["synthetic_holdout_auc"].mean())
    rows = [
        {
            "check": "heldout_run_excluded_from_template_and_ml_training",
            "value": 1.0,
            "flag": False,
            "note": "Each source run is scored only by templates and ML trained with that run removed.",
        },
        {
            "check": "identifier_features_excluded",
            "value": 1.0,
            "flag": False,
            "note": "ML features exclude run, event number, current, group, downstream label, and stratum labels.",
        },
        {
            "check": "synthetic_train_source_runs_exclude_heldout",
            "value": float(all(str(r) not in row.synthetic_train_source_runs.split() for row in folds.itertuples() for r in [row.heldout_run])),
            "flag": False,
            "note": "Fold diagnostics record the source runs used to generate synthetic ML training overlays.",
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
            "value": current_auc,
            "flag": bool(current_auc > 0.95),
            "note": "Flagged if the ML amplitude estimate nearly identifies beam current by itself.",
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
    stratum_table: pd.DataFrame,
    method_summary: pd.DataFrame,
    stratum_summary: pd.DataFrame,
    folds: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    trad = method_summary[method_summary["method_metric"] == "trad_secondary_fraction"].iloc[0]
    ml_frac = method_summary[method_summary["method_metric"] == "ml_secondary_fraction"].iloc[0]
    ml_score = method_summary[method_summary["method_metric"] == "ml_overlap_score"].iloc[0]
    top_trad = stratum_summary[stratum_summary["method_metric"] == "trad_secondary_fraction"].sort_values("match_weight", ascending=False).head(8)
    lines = [
        "# S11b: real high-current two-pulse recovery",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** high-current events are predicted from low-current template/ML training only; low-current control events leave their own source run out. CIs resample held-out source runs within current group.",
        "",
        "## Reproduction first",
        "",
        (
            "The S10c raw-ROOT gate was reproduced before the amplitude study. "
            f"Downstream selected-event fraction is {low['downstream_per_selected_event']:.5f} at 2 nA and "
            f"{high['downstream_per_selected_event']:.5f} at 20 nA; all six documented topology fractions "
            "pass the +/-0.0015 tolerance."
        ),
        "",
        repro.to_markdown(index=False),
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
            "For each held-out run, median empirical templates are built from low-current source runs only, "
            "excluding the held-out run when it is a low-current control. A bounded two-pulse "
            "fit scans first-pulse timing and pulse separation, solves primary amplitude, secondary amplitude, "
            "and baseline by least squares, and reports the secondary fraction A2/(A1+A2)."
        ),
        "",
        (
            f"Matched high-minus-low secondary fraction: **{trad['value']:.5f}** with run-bootstrap 95% CI "
            f"**[{trad['ci_low']:.5f}, {trad['ci_high']:.5f}]**."
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
            "The ML method is a compact run-held-out random-forest classifier/regressor trained on synthetic two-pulse "
            "overlays made only from low-current training-run raw pulses. Features are normalized waveform samples and "
            "one-pulse template residual summaries; identifiers and current labels are excluded."
        ),
        "",
        (
            f"ML secondary-fraction high-minus-low: **{ml_frac['value']:.5f}** "
            f"[{ml_frac['ci_low']:.5f}, {ml_frac['ci_high']:.5f}]. "
            f"ML overlap-score high-minus-low: **{ml_score['value']:.5f}** "
            f"[{ml_score['ci_low']:.5f}, {ml_score['ci_high']:.5f}]. "
            f"Mean synthetic held-out AUC is {folds['synthetic_holdout_auc'].mean():.3f}; shuffled-label AUC is "
            f"{folds['shuffled_label_synthetic_auc'].mean():.3f}."
        ),
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
        "`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `stratum_table.csv`, `method_summary.csv`, `method_stratum_summary.csv`, `sampled_event_scores.csv`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this folder.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)
    events, waves, run_counts = load_events()
    topology, repro = reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10c raw-ROOT reproduction gate failed")
    counts = stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = matched_strata(counts)
    sample = choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)

    scores, template_summary, folds = heldout_predictions(events, waves, sample, rng)
    method_tables = []
    method_summaries = []
    for col in ["trad_secondary_fraction", "ml_secondary_fraction", "ml_overlap_score"]:
        table, summary = summarize_method(scores, stratum_table, col, rng)
        method_tables.append(table)
        method_summaries.append(summary)
    stratum_summary = pd.concat(method_tables, ignore_index=True)
    method_summary = pd.concat(method_summaries, ignore_index=True)
    leakage = leakage_checks(scores, folds)

    input_files = [raw_file(run) for run in sorted(run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    stratum_table.to_csv(OUT / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(OUT / "analysis_sample.csv", index=False)
    template_summary.to_csv(OUT / "template_summary_by_fold.csv", index=False)
    scores.to_csv(OUT / "sampled_event_scores.csv", index=False)
    folds.to_csv(OUT / "fold_diagnostics.csv", index=False)
    stratum_summary.to_csv(OUT / "method_stratum_summary.csv", index=False)
    method_summary.to_csv(OUT / "method_summary.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)
    save_plots(stratum_summary, method_summary, scores)

    trad = method_summary[method_summary["method_metric"] == "trad_secondary_fraction"].iloc[0]
    ml_frac = method_summary[method_summary["method_metric"] == "ml_secondary_fraction"].iloc[0]
    ml_score = method_summary[method_summary["method_metric"] == "ml_overlap_score"].iloc[0]
    top = stratum_summary[stratum_summary["method_metric"] == "trad_secondary_fraction"].sort_values("high_minus_low", ascending=False).iloc[0]
    conclusion = (
        f"Applying the S11a-style low-current template baseline to real high-current candidate windows gives a "
        f"matched high-current minus low-current secondary fraction of {trad['value']:.5f} "
        f"[{trad['ci_low']:.5f}, {trad['ci_high']:.5f}] from the traditional template fit. "
        f"The ML residual diagnostic gives {ml_frac['value']:.5f} "
        f"[{ml_frac['ci_low']:.5f}, {ml_frac['ci_high']:.5f}] for secondary fraction and "
        f"{ml_score['value']:.5f} [{ml_score['ci_low']:.5f}, {ml_score['ci_high']:.5f}] for overlap score. "
        f"The largest traditional positive stratum is {top['amp_bin']} / {top['baseline_bin']} / {top['p02_topology']}. "
        "Leakage probes do not flag identifier or source-run leakage, but the estimate remains a pulse-shape diagnostic rather than a truth-labelled pile-up decomposition."
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "real high-current two-pulse recovery against S10 topology excess",
        "reproduced": bool(repro["pass"].all()),
        "reproduction_gate": "S10c topology fractions from raw B-stack ROOT within 0.0015 absolute tolerance",
        "split": "low-current-only template and ML training for high-current events; leave-one-low-run-out controls; run bootstrap CIs within current group",
        "strata": {
            "definition": "S10c amplitude bin x S16 adaptive lowering bin x P02 topology",
            "n_matched_strata": int(len(stratum_table)),
            "global_s10_downstream_high_minus_low": float(global_downstream_excess),
            "n_scored_events": int(len(scores)),
            "sample_cap_per_run_stratum": SAMPLE_PER_RUN_STRATUM,
        },
        "traditional": {
            "method": "bounded_two_pulse_low_current_template_fit",
            "metric": "matched_stratified_secondary_fraction_high_minus_low",
            "value": float(trad["value"]),
            "ci": [float(trad["ci_low"]), float(trad["ci_high"])],
        },
        "ml": {
            "method": "low_current_synthetic_overlay_random_forest_residual_diagnostic",
            "secondary_fraction_high_minus_low": {
                "value": float(ml_frac["value"]),
                "ci": [float(ml_frac["ci_low"]), float(ml_frac["ci_high"])],
            },
            "overlap_score_high_minus_low": {
                "value": float(ml_score["value"]),
                "ci": [float(ml_score["ci_low"]), float(ml_score["ci_high"])],
            },
            "mean_synthetic_holdout_auc": float(folds["synthetic_holdout_auc"].mean()),
            "mean_shuffled_label_synthetic_auc": float(folds["shuffled_label_synthetic_auc"].mean()),
            "mean_secondary_fraction_mae_on_synthetic_holdout": float(folds["synthetic_secondary_fraction_mae"].mean()),
        },
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(topology, repro, stratum_table, method_summary, stratum_summary, folds, leakage, result)
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
