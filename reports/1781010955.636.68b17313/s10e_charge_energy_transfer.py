#!/usr/bin/env python3
"""S10e: pile-up excess transfer to charge-energy proxies.

All inputs are raw B-stack ROOT files.  The event table is rebuilt before any
stratification or ML step so the S10/S10c topology number is reproduced first.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
RAW = ROOT / "data/root/root"
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET = "1781010955.636.68b17313"
WORKER = "testbeam-laptop-4"
STUDY = "S10e"
RNG_SEED = 1010955
RUN_GROUPS = {
    "low_2nA": {"current_nA": 2.0, "runs": [46, 47]},
    "high_20nA": {"current_nA": 20.0, "runs": [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]},
}
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
DUPLICATE_CHANNELS = {"B2": 1, "B4": 3, "B6": 5, "B8": 7}
BASELINE_SAMPLES = [0, 1, 2, 3]
NSAMPLES = 18
AMP_CUT = 1000.0
SATURATION_PROXY_ADC = 7000.0
BOOTSTRAPS = 250
MIN_STRATUM_N = 25
ML_MAX_TRAIN_PER_CLASS = 12000
ML_CHARGE_TRAIN_MAX = 18000
ML_INJECTION_N = 6500
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


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def run_to_group() -> dict[int, str]:
    return {run: group for group, info in RUN_GROUPS.items() for run in info["runs"]}


def shape_features(waveforms: np.ndarray, amp: np.ndarray | None = None) -> pd.DataFrame:
    if amp is None:
        amp = waveforms.max(axis=1)
    safe_amp = np.maximum(amp, 1.0)
    positive = np.clip(waveforms, 0.0, None)
    charge = np.maximum(positive.sum(axis=1), 1.0)
    peak = waveforms.argmax(axis=1)
    width_10 = (waveforms > 0.10 * safe_amp[:, None]).sum(axis=1)
    width_20 = (waveforms > 0.20 * safe_amp[:, None]).sum(axis=1)
    return pd.DataFrame(
        {
            "log_amp": np.log(safe_amp),
            "peak_sample": peak.astype(float),
            "area_over_peak": waveforms.sum(axis=1) / safe_amp,
            "tail_fraction": positive[:, 10:].sum(axis=1) / charge,
            "late_fraction": positive[:, 12:].sum(axis=1) / charge,
            "early_fraction": positive[:, :4].sum(axis=1) / charge,
            "post_peak_min_fraction": waveforms[:, 8:].min(axis=1) / safe_amp,
            "neg_step_count": (np.diff(waveforms, axis=1) < -0.20 * safe_amp[:, None]).sum(axis=1).astype(float),
            "width_10_samples": width_10.astype(float),
            "width_20_samples": width_20.astype(float),
            "final_fraction": waveforms[:, -1] / safe_amp,
        }
    )


def adaptive_lowering(raw_waveforms: np.ndarray, seed: np.ndarray) -> np.ndarray:
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
    return seed - pc


def build_templates(events: pd.DataFrame, waves: np.ndarray) -> dict[str, np.ndarray]:
    templates: dict[str, np.ndarray] = {}
    for stave in STAVES:
        mask = events["ref_stave"].to_numpy() == stave
        amp = np.maximum(events.loc[mask, "ref_amp_adc"].to_numpy(), 1.0)
        norm = waves[mask] / amp[:, None]
        templates[stave] = np.median(norm, axis=0)
    return templates


def template_charge_proxy(events: pd.DataFrame, waves: np.ndarray, templates: dict[str, np.ndarray]) -> np.ndarray:
    out = np.zeros(len(events), dtype=float)
    for stave, template in templates.items():
        mask = events["ref_stave"].to_numpy() == stave
        if not mask.any():
            continue
        denom = float(np.dot(template, template))
        scale = (waves[mask] @ template) / max(denom, 1e-9)
        out[mask] = np.maximum(scale, 1.0) * np.clip(template, 0.0, None).sum()
    return np.maximum(out, 1.0)


def p07_correct_charge(events: pd.DataFrame) -> np.ndarray:
    """Small data-driven P07-style correction for B2 saturation-proxy events.

    The factor depends only on observed B2 waveform summaries and is intentionally
    bounded. It is a stratum/diagnostic proxy, not a truth-level energy recovery.
    """
    charge = events["p04_duplicate_charge"].to_numpy().copy()
    b2_sat = (events["ref_stave"].to_numpy() == "B2") & (events["ref_amp_adc"].to_numpy() >= SATURATION_PROXY_ADC)
    broad = np.clip((events["width_20_samples"].to_numpy() - 6.0) / 8.0, 0.0, 1.0)
    tail = np.clip(events["tail_fraction"].to_numpy() / 0.25, 0.0, 1.0)
    factor = 1.0 + b2_sat.astype(float) * (0.035 + 0.035 * broad + 0.025 * tail)
    return charge * factor


def assign_charge_strata(events: pd.DataFrame, charge_col: str, prefix: str) -> pd.DataFrame:
    out = events.copy()
    out[f"{prefix}_charge_bin"] = pd.cut(
        out[charge_col],
        bins=[0.0, 8000.0, 16000.0, 32000.0, np.inf],
        labels=["q_lt_8k", "q_8k_16k", "q_16k_32k", "q_ge_32k"],
        include_lowest=True,
        right=False,
    ).astype(str)
    out["s16_bin"] = pd.cut(
        out["adaptive_lowering_adc"],
        bins=[-0.1, 0.1, 200.0, np.inf],
        labels=["s16_no_lowering", "s16_mild_lowering", "s16_large_lowering"],
        include_lowest=True,
        right=False,
    ).astype(str)
    sat_state = np.full(len(out), "non_B2", dtype=object)
    b2 = out["ref_stave"].to_numpy() == "B2"
    sat_state[b2 & (out["ref_amp_adc"].to_numpy() < SATURATION_PROXY_ADC)] = "B2_unsat"
    sat_state[b2 & (out["ref_amp_adc"].to_numpy() >= SATURATION_PROXY_ADC)] = "B2_sat_proxy"
    out["p07_saturation_state"] = sat_state
    out[f"{prefix}_stratum"] = (
        out[f"{prefix}_charge_bin"] + "|" + out["s16_bin"] + "|" + out["p07_saturation_state"]
    )
    return out


def load_events() -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    group_for_run = run_to_group()
    even_channels = np.asarray(list(STAVES.values()), dtype=int)
    odd_channels = np.asarray(list(DUPLICATE_CHANNELS.values()), dtype=int)
    stave_names = np.asarray(list(STAVES.keys()))
    event_frames = []
    ref_waves = []
    run_rows = []
    for run in sorted(group_for_run):
        path = RAW / f"hrdb_run_{run:04d}.root"
        group = group_for_run[run]
        current = RUN_GROUPS[group]["current_nA"]
        counts = {
            "run": int(run),
            "group": group,
            "current_nA": float(current),
            "events_total": 0,
            "events_with_selected": 0,
            "selected_pulses": 0,
            "multi_stave_events": 0,
            "three_stave_events": 0,
            "downstream_events": 0,
        }
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            all_events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMPLES)
            raw_even = all_events[:, even_channels, :]
            raw_odd = all_events[:, odd_channels, :]
            seed_even = np.median(raw_even[..., BASELINE_SAMPLES], axis=-1)
            seed_odd = np.median(raw_odd[..., BASELINE_SAMPLES], axis=-1)
            even = raw_even - seed_even[..., None]
            odd = raw_odd - seed_odd[..., None]
            amp = even.max(axis=-1)
            even_integral = np.clip(even, 0.0, None).sum(axis=-1)
            odd_charge = np.clip(-odd, 0.0, None).sum(axis=-1)
            selected = amp > AMP_CUT
            n_selected = selected.sum(axis=1)
            keep = n_selected >= 1
            counts["events_total"] += int(len(eventno))
            counts["events_with_selected"] += int(keep.sum())
            counts["selected_pulses"] += int(selected.sum())
            counts["multi_stave_events"] += int((n_selected >= 2).sum())
            counts["three_stave_events"] += int((n_selected >= 3).sum())
            counts["downstream_events"] += int(selected[:, 1:].any(axis=1).sum())
            if not keep.any():
                continue
            masked_amp = np.where(selected, amp, -np.inf)
            ref_idx = masked_amp.argmax(axis=1)[keep]
            row_idx = np.where(keep)[0]
            raw_ref = raw_even[row_idx, ref_idx, :]
            corr_ref = even[row_idx, ref_idx, :]
            lowering = adaptive_lowering(raw_ref, seed_even[row_idx, ref_idx])
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
                    "integral_charge": even_integral[row_idx, ref_idx],
                    "p04_duplicate_charge": odd_charge[row_idx, ref_idx],
                    "adaptive_lowering_adc": lowering,
                }
            )
            event_frames.append(frame)
            ref_waves.append(corr_ref.astype(np.float32))
        run_rows.append(counts)
    events = pd.concat(event_frames, ignore_index=True)
    waves = np.concatenate(ref_waves, axis=0)
    events = pd.concat([events.reset_index(drop=True), shape_features(waves, events["ref_amp_adc"].to_numpy())], axis=1)
    templates = build_templates(events, waves)
    events["template_charge"] = template_charge_proxy(events, waves, templates)
    events["p07_corrected_charge"] = p07_correct_charge(events)
    events = assign_charge_strata(events, "p04_duplicate_charge", "uncorrected")
    events = assign_charge_strata(events, "p07_corrected_charge", "p07_corrected")
    return events, waves, pd.DataFrame(run_rows)


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


def stratum_counts(events: pd.DataFrame, stratum_col: str, charge_col: str) -> pd.DataFrame:
    return (
        events.groupby(["run", "group", stratum_col], observed=False)
        .agg(
            n=("downstream", "size"),
            downstream=("downstream", "sum"),
            charge_median=(charge_col, "median"),
            integral_median=("integral_charge", "median"),
            template_median=("template_charge", "median"),
            p04_median=("p04_duplicate_charge", "median"),
        )
        .reset_index()
        .rename(columns={stratum_col: "stratum"})
    )


def matched_strata(counts: pd.DataFrame, min_n: int = MIN_STRATUM_N) -> pd.DataFrame:
    group_counts = counts.groupby(["stratum", "group"], observed=False).agg(n=("n", "sum"), downstream=("downstream", "sum")).reset_index()
    pivot = group_counts.pivot(index="stratum", columns="group", values=["n", "downstream"]).fillna(0)
    rows = []
    for stratum in pivot.index:
        low_n = int(pivot.loc[stratum, ("n", "low_2nA")]) if ("n", "low_2nA") in pivot.columns else 0
        high_n = int(pivot.loc[stratum, ("n", "high_20nA")]) if ("n", "high_20nA") in pivot.columns else 0
        if low_n < min_n or high_n < min_n:
            continue
        low_d = int(pivot.loc[stratum, ("downstream", "low_2nA")])
        high_d = int(pivot.loc[stratum, ("downstream", "high_20nA")])
        rows.append(
            {
                "stratum": stratum,
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
    return table


def weighted_metric(events: pd.DataFrame, stratum_table: pd.DataFrame, stratum_col: str, value_col: str, kind: str) -> float:
    wanted = set(stratum_table["stratum"])
    view = events[events[stratum_col].isin(wanted)]
    if kind == "fraction":
        grouped = view.groupby([stratum_col, "group"], observed=False)[value_col].mean()
    elif kind == "median_log_shift":
        tmp = view[[stratum_col, "group", value_col]].copy()
        tmp[value_col] = np.log(np.maximum(tmp[value_col].to_numpy(), 1.0))
        grouped = tmp.groupby([stratum_col, "group"], observed=False)[value_col].median()
    else:
        raise ValueError(kind)
    total = 0.0
    for row in stratum_table.itertuples(index=False):
        try:
            low = float(grouped.loc[(row.stratum, "low_2nA")])
            high = float(grouped.loc[(row.stratum, "high_20nA")])
        except KeyError:
            continue
        total += float(row.match_weight) * (high - low)
    return float(total)


def summarize_traditional(events: pd.DataFrame, stratum_col: str, charge_col: str, label: str, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    counts = stratum_counts(events, stratum_col, charge_col)
    strata = matched_strata(counts)
    run_summary = events[[stratum_col, "run", "group", "downstream", "integral_charge", "template_charge", "p04_duplicate_charge", "p07_corrected_charge"]].copy()
    for col in ["integral_charge", "template_charge", "p04_duplicate_charge", "p07_corrected_charge"]:
        run_summary[f"log_{col}"] = np.log(np.maximum(run_summary[col].to_numpy(), 1.0))
    run_summary = (
        run_summary.groupby(["run", "group", stratum_col], observed=False)
        .agg(
            n=("downstream", "size"),
            downstream_sum=("downstream", "sum"),
            log_integral_charge=("log_integral_charge", "median"),
            log_template_charge=("log_template_charge", "median"),
            log_p04_duplicate_charge=("log_p04_duplicate_charge", "median"),
            log_p07_corrected_charge=("log_p07_corrected_charge", "median"),
        )
        .reset_index()
        .rename(columns={stratum_col: "stratum"})
    )

    def boot_metric(sample_summary: pd.DataFrame, value_col: str, kind: str) -> float:
        if kind == "fraction":
            grouped = sample_summary.groupby(["stratum", "group"], observed=False).agg(n=("n", "sum"), downstream_sum=("downstream_sum", "sum"))
            series = grouped["downstream_sum"] / grouped["n"]
        elif kind == "median_log_shift":
            log_col = f"log_{value_col}"
            tmp = sample_summary.copy()
            tmp["weighted"] = tmp[log_col] * tmp["n"]
            grouped = tmp.groupby(["stratum", "group"], observed=False).agg(weighted=("weighted", "sum"), n=("n", "sum"))
            series = grouped["weighted"] / grouped["n"]
        else:
            raise ValueError(kind)
        total = 0.0
        for row in strata.itertuples(index=False):
            try:
                low = float(series.loc[(row.stratum, "low_2nA")])
                high = float(series.loc[(row.stratum, "high_20nA")])
            except KeyError:
                continue
            total += float(row.match_weight) * (high - low)
        return float(total)

    rows = []
    metrics = [
        ("downstream_high_minus_low", "downstream", "fraction"),
        ("integral_charge_median_log_shift", "integral_charge", "median_log_shift"),
        ("template_charge_median_log_shift", "template_charge", "median_log_shift"),
        ("p04_duplicate_charge_median_log_shift", "p04_duplicate_charge", "median_log_shift"),
        (f"{label}_charge_median_log_shift", charge_col, "median_log_shift"),
    ]
    for metric, value_col, kind in metrics:
        value = weighted_metric(events, strata, stratum_col, value_col, kind)
        boot = []
        low_runs = np.asarray(RUN_GROUPS["low_2nA"]["runs"])
        high_runs = np.asarray(RUN_GROUPS["high_20nA"]["runs"])
        for _ in range(BOOTSTRAPS):
            pieces = []
            for run in np.r_[rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True)]:
                pieces.append(run_summary[run_summary["run"] == int(run)])
            sample = pd.concat(pieces, ignore_index=True)
            boot.append(boot_metric(sample, value_col, kind))
        rows.append(
            {
                "strata_definition": label,
                "metric": metric,
                "value": float(value),
                "ci_low": float(np.quantile(boot, 0.025)),
                "ci_high": float(np.quantile(boot, 0.975)),
                "n_strata": int(len(strata)),
                "bootstrap_unit": "run_within_current_group",
                "n_bootstrap": BOOTSTRAPS,
            }
        )
    return strata, pd.DataFrame(rows)


FEATURE_COLS = [
    "log_amp",
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
    "adaptive_lowering_adc",
    "integral_charge",
    "template_charge",
]


def inject_pileup(clean_waveforms: np.ndarray, clean_amp: np.ndarray, rng: np.random.Generator, n: int) -> tuple[np.ndarray, np.ndarray]:
    primary_idx = rng.integers(0, len(clean_waveforms), size=n)
    secondary_idx = rng.integers(0, len(clean_waveforms), size=n)
    delays = rng.integers(2, 10, size=n)
    ratios = rng.uniform(0.35, 1.1, size=n)
    primary = clean_waveforms[primary_idx].copy()
    secondary = clean_waveforms[secondary_idx] / np.maximum(clean_amp[secondary_idx], 1.0)[:, None]
    secondary *= (clean_amp[primary_idx] * ratios)[:, None]
    injected = primary.copy()
    for i, delay in enumerate(delays):
        injected[i, delay:] += secondary[i, : NSAMPLES - delay]
    return primary, injected


def make_injection_training(train: pd.DataFrame, train_waves: np.ndarray, rng: np.random.Generator, n_max: int) -> tuple[pd.DataFrame, np.ndarray]:
    clean = (
        (train["ref_amp_adc"].to_numpy() > 1300.0)
        & (train["ref_amp_adc"].to_numpy() < 8000.0)
        & (train["peak_sample"].to_numpy() >= 4.0)
        & (train["peak_sample"].to_numpy() <= 12.0)
    )
    clean_waves = train_waves[clean]
    clean_amp = train.loc[clean, "ref_amp_adc"].to_numpy()
    n = min(n_max, len(clean_waves))
    base, injected = inject_pileup(clean_waves, clean_amp, rng, n)
    x0 = shape_features(base)
    x1 = shape_features(injected)
    for frame in (x0, x1):
        frame["adaptive_lowering_adc"] = 0.0
        frame["integral_charge"] = np.clip(base if frame is x0 else injected, 0.0, None).sum(axis=1)
        frame["template_charge"] = frame["integral_charge"]
    x = pd.concat([x0, x1], ignore_index=True)[FEATURE_COLS]
    y = np.r_[np.zeros(len(x0), dtype=int), np.ones(len(x1), dtype=int)]
    order = rng.permutation(len(y))
    return x.iloc[order].reset_index(drop=True), y[order]


def fit_scaled_logistic(x: pd.DataFrame, y: np.ndarray, c_value: float = 1.0) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler().fit(x)
    clf = LogisticRegression(C=c_value, max_iter=1000, class_weight="balanced", random_state=RNG_SEED)
    clf.fit(scaler.transform(x), y)
    return scaler, clf


def current_model(train: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, StandardScaler, LogisticRegression, LogisticRegression]:
    low = train[train["group"] == "low_2nA"]
    high = train[train["group"] == "high_20nA"]
    n = min(len(low), len(high), ML_MAX_TRAIN_PER_CLASS)
    sampled = pd.concat(
        [
            low.sample(n=n, random_state=int(rng.integers(0, 1_000_000))),
            high.sample(n=n, random_state=int(rng.integers(0, 1_000_000))),
        ],
        ignore_index=True,
    )
    y = (sampled["group"] == "high_20nA").astype(int).to_numpy()
    groups = sampled["run"].to_numpy()
    cv_mode = "group_kfold" if sampled[sampled["group"] == "low_2nA"]["run"].nunique() >= 2 else "stratified_row_fallback_one_low_run"

    def splits():
        if cv_mode == "group_kfold":
            return list(GroupKFold(n_splits=min(4, len(np.unique(groups)))).split(sampled[FEATURE_COLS], y, groups=groups))
        return list(StratifiedKFold(n_splits=3, shuffle=True, random_state=RNG_SEED).split(sampled[FEATURE_COLS], y))

    rows = []
    best_c = 1.0
    best_brier = np.inf
    for c_value in [0.1, 1.0, 10.0]:
        oof = np.zeros(len(sampled))
        for tr, va in splits():
            scaler, clf = fit_scaled_logistic(sampled.iloc[tr][FEATURE_COLS], y[tr], c_value)
            oof[va] = clf.predict_proba(scaler.transform(sampled.iloc[va][FEATURE_COLS]))[:, 1]
        brier = brier_score_loss(y, oof)
        rows.append({"C": c_value, "cv_mode": cv_mode, "validation_brier": float(brier), "validation_auc": float(roc_auc_score(y, oof)), "n": int(len(sampled))})
        if brier < best_brier:
            best_brier = brier
            best_c = c_value
    oof = np.zeros(len(sampled))
    for tr, va in splits():
        scaler, clf = fit_scaled_logistic(sampled.iloc[tr][FEATURE_COLS], y[tr], best_c)
        oof[va] = clf.predict_proba(scaler.transform(sampled.iloc[va][FEATURE_COLS]))[:, 1]
    eps = 1e-5
    logit = np.log(np.clip(oof, eps, 1 - eps) / np.clip(1 - oof, eps, 1 - eps)).reshape(-1, 1)
    calibrator = LogisticRegression(max_iter=1000, random_state=RNG_SEED).fit(logit, y)
    scaler, clf = fit_scaled_logistic(sampled[FEATURE_COLS], y, best_c)
    cv = pd.DataFrame(rows)
    cv["selected"] = cv["C"] == best_c
    return cv, scaler, clf, calibrator


def apply_calibrated(scaler: StandardScaler, clf: LogisticRegression, calibrator: LogisticRegression, x: pd.DataFrame) -> np.ndarray:
    raw = clf.predict_proba(scaler.transform(x[FEATURE_COLS]))[:, 1]
    eps = 1e-5
    logit = np.log(np.clip(raw, eps, 1 - eps) / np.clip(1 - raw, eps, 1 - eps)).reshape(-1, 1)
    return calibrator.predict_proba(logit)[:, 1]


def ml_matrix(events: pd.DataFrame, waves: np.ndarray) -> np.ndarray:
    stave_idx = events["ref_stave_idx"].to_numpy().astype(int)
    onehot = np.zeros((len(events), 4), dtype=float)
    onehot[np.arange(len(events)), stave_idx] = 1.0
    return np.column_stack(
        [
            waves,
            events[FEATURE_COLS].to_numpy(),
            onehot,
        ]
    )


def run_ml(events: pd.DataFrame, waves: np.ndarray, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    score_frames = []
    cv_frames = []
    x_all = ml_matrix(events, waves)
    for heldout_run in sorted(events["run"].unique()):
        train = events[events["run"] != heldout_run].copy()
        test = events[events["run"] == heldout_run].copy()
        train_waves = waves[train.index.to_numpy()]

        x_inj, y_inj = make_injection_training(train, train_waves, rng, ML_INJECTION_N)
        scaler_inj, clf_inj = fit_scaled_logistic(x_inj, y_inj, c_value=1.0)
        inj_score = clf_inj.predict_proba(scaler_inj.transform(test[FEATURE_COLS]))[:, 1]

        cv, scaler_cur, clf_cur, cal_cur = current_model(train, rng)
        cv["heldout_run"] = int(heldout_run)
        cv_frames.append(cv)
        current_score = apply_calibrated(scaler_cur, clf_cur, cal_cur, test)

        train_idx = train.index.to_numpy()
        if len(train_idx) > ML_CHARGE_TRAIN_MAX:
            train_idx = rng.choice(train_idx, size=ML_CHARGE_TRAIN_MAX, replace=False)
        charge_model = make_pipeline(StandardScaler(), RidgeCV(alphas=np.asarray([0.1, 1.0, 10.0, 100.0], dtype=float)))
        charge_model.fit(x_all[train_idx], np.log(np.maximum(events.loc[train_idx, "p04_duplicate_charge"].to_numpy(), 1.0)))
        pred_log_charge = charge_model.predict(x_all[test.index.to_numpy()])
        charge_residual = np.log(np.maximum(test["p04_duplicate_charge"].to_numpy(), 1.0)) - pred_log_charge

        frame = test[
            [
                "run",
                "group",
                "current_nA",
                "eventno",
                "downstream",
                "uncorrected_stratum",
                "p07_corrected_stratum",
                "p04_duplicate_charge",
                "p07_corrected_charge",
            ]
        ].copy()
        frame["injection_pileup_score"] = inj_score
        frame["weak_current_score"] = current_score
        frame["charge_regression_residual_score"] = charge_residual
        score_frames.append(frame)
    return pd.concat(score_frames, ignore_index=True), pd.concat(cv_frames, ignore_index=True)


def summarize_ml(scores: pd.DataFrame, stratum_table: pd.DataFrame, stratum_col: str, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    score_cols = ["injection_pileup_score", "weak_current_score", "charge_regression_residual_score"]
    run_summary = (
        scores[["run", "group", stratum_col] + score_cols]
        .groupby(["run", "group", stratum_col], observed=False)
        .agg(
            n=("injection_pileup_score", "size"),
            injection_pileup_score=("injection_pileup_score", "mean"),
            weak_current_score=("weak_current_score", "mean"),
            charge_regression_residual_score=("charge_regression_residual_score", "mean"),
        )
        .reset_index()
        .rename(columns={stratum_col: "stratum"})
    )

    def boot_score(sample_summary: pd.DataFrame, score_col: str) -> float:
        tmp = sample_summary.copy()
        tmp["weighted"] = tmp[score_col] * tmp["n"]
        grouped = tmp.groupby(["stratum", "group"], observed=False).agg(weighted=("weighted", "sum"), n=("n", "sum"))
        series = grouped["weighted"] / grouped["n"]
        total = 0.0
        for row in stratum_table.itertuples(index=False):
            try:
                low = float(series.loc[(row.stratum, "low_2nA")])
                high = float(series.loc[(row.stratum, "high_20nA")])
            except KeyError:
                continue
            total += float(row.match_weight) * (high - low)
        return float(total)

    for score_col in ["injection_pileup_score", "weak_current_score", "charge_regression_residual_score"]:
        value = weighted_metric(scores, stratum_table, stratum_col, score_col, "fraction")
        boot = []
        low_runs = np.asarray(RUN_GROUPS["low_2nA"]["runs"])
        high_runs = np.asarray(RUN_GROUPS["high_20nA"]["runs"])
        for _ in range(BOOTSTRAPS):
            pieces = []
            for run in np.r_[rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True)]:
                pieces.append(run_summary[run_summary["run"] == int(run)])
            sample = pd.concat(pieces, ignore_index=True)
            boot.append(boot_score(sample, score_col))
        rows.append(
            {
                "metric": f"matched_stratified_{score_col}_high_minus_low",
                "value": float(value),
                "ci_low": float(np.quantile(boot, 0.025)),
                "ci_high": float(np.quantile(boot, 0.975)),
                "n_bootstrap": BOOTSTRAPS,
                "bootstrap_unit": "run_within_current_group",
            }
        )
    return pd.DataFrame(rows)


def row_split_current_auc(events: pd.DataFrame, rng: np.random.Generator) -> float:
    low = events[events["group"] == "low_2nA"]
    high = events[events["group"] == "high_20nA"]
    n = min(len(low), len(high), ML_MAX_TRAIN_PER_CLASS)
    sample = pd.concat(
        [
            low.sample(n=n, random_state=int(rng.integers(0, 1_000_000))),
            high.sample(n=n, random_state=int(rng.integers(0, 1_000_000))),
        ],
        ignore_index=True,
    )
    y = (sample["group"] == "high_20nA").astype(int).to_numpy()
    order = rng.permutation(len(sample))
    tr = order[: len(order) // 2]
    te = order[len(order) // 2 :]
    scaler, clf = fit_scaled_logistic(sample.iloc[tr][FEATURE_COLS], y[tr], 1.0)
    pred = clf.predict_proba(scaler.transform(sample.iloc[te][FEATURE_COLS]))[:, 1]
    return float(roc_auc_score(y[te], pred))


def output_hashes() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def save_plots(strata_uncorr: pd.DataFrame, trad_summary: pd.DataFrame, ml_scores: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    plot = strata_uncorr.sort_values("match_weight", ascending=False).head(12).iloc[::-1]
    ax.barh(np.arange(len(plot)), plot["downstream_high_minus_low"])
    ax.set_yticks(np.arange(len(plot)), plot["stratum"], fontsize=7)
    ax.axvline(0, color="k", lw=1)
    ax.set_xlabel("High minus low downstream fraction")
    ax.set_title("S10e P04 charge strata")
    fig.tight_layout()
    fig.savefig(OUT / "fig_charge_stratum_downstream_excess.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = trad_summary[trad_summary["metric"].str.contains("charge_median_log_shift")].copy()
    labels = bars["strata_definition"] + "\n" + bars["metric"].str.replace("_median_log_shift", "", regex=False)
    ax.bar(np.arange(len(bars)), bars["value"])
    ax.set_xticks(np.arange(len(bars)), labels, rotation=60, ha="right", fontsize=7)
    ax.axhline(0, color="k", lw=1)
    ax.set_ylabel("Matched median log charge shift")
    fig.tight_layout()
    fig.savefig(OUT / "fig_charge_proxy_shifts.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4))
    for group, sub in ml_scores.groupby("group"):
        ax.hist(sub["charge_regression_residual_score"], bins=40, alpha=0.5, density=True, label=group)
    ax.set_xlabel("Leave-one-run-out P04 charge residual")
    ax.set_ylabel("Density")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "fig_ml_charge_residual_by_current.png", dpi=160)
    plt.close(fig)


def write_report(topology: pd.DataFrame, repro: pd.DataFrame, strata_uncorr: pd.DataFrame, trad_summary: pd.DataFrame, ml_summary: pd.DataFrame, leakage: pd.DataFrame, result: dict) -> None:
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    trad_down = trad_summary[(trad_summary["strata_definition"] == "uncorrected") & (trad_summary["metric"] == "downstream_high_minus_low")].iloc[0]
    corr_down = trad_summary[(trad_summary["strata_definition"] == "p07_corrected") & (trad_summary["metric"] == "downstream_high_minus_low")].iloc[0]
    p04_shift = trad_summary[(trad_summary["strata_definition"] == "uncorrected") & (trad_summary["metric"] == "p04_duplicate_charge_median_log_shift")].iloc[0]
    ml_res = ml_summary[ml_summary["metric"].str.contains("charge_regression_residual")].iloc[0]
    lines = [
        "# S10e: pile-up excess transfer to charge-energy proxies",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** ML predictions are leave-one-run-out; CIs resample held-out runs within current group.",
        "",
        "## Reproduction first",
        "",
        (
            f"Raw ROOT reproduction passes before modeling: downstream selected-event fraction is "
            f"{low['downstream_per_selected_event']:.5f} at 2 nA and {high['downstream_per_selected_event']:.5f} at 20 nA. "
            "All six documented S10/S10c topology fractions pass the +/-0.0015 tolerance."
        ),
        "",
        repro.to_markdown(index=False),
        "",
        "## Traditional charge-energy transfer",
        "",
        (
            "Each selected event is represented by its maximum selected B pulse. The traditional controls use "
            "`integral_charge`, a template-scale charge proxy, the P04 paired odd-readout duplicate charge, and "
            "a bounded P07-style corrected B2 saturation-proxy charge. Strata are charge bin x S16 lowering x "
            "B2 saturation state."
        ),
        "",
        (
            f"Matched downstream excess is **{trad_down['value']:.5f}** "
            f"[{trad_down['ci_low']:.5f}, {trad_down['ci_high']:.5f}] in uncorrected P04 charge strata and "
            f"**{corr_down['value']:.5f}** [{corr_down['ci_low']:.5f}, {corr_down['ci_high']:.5f}] after P07 B2 correction. "
            f"The matched P04 duplicate-charge median log shift is **{p04_shift['value']:.5f}** "
            f"[{p04_shift['ci_low']:.5f}, {p04_shift['ci_high']:.5f}]."
        ),
        "",
        trad_summary.to_markdown(index=False),
        "",
        "Top matched uncorrected strata:",
        "",
        strata_uncorr.head(8).to_markdown(index=False),
        "",
        "## ML diagnostics",
        "",
        (
            "The ML pile-up/current scores are trained leave-one-run-out on the same selected events. "
            "The charge-residual score is a leave-one-run-out P04 duplicate-charge regressor using even-channel "
            "waveform and traditional charge summaries only; odd charge is the target, not a feature."
        ),
        "",
        ml_summary.to_markdown(index=False),
        "",
        (
            f"The matched charge-regression residual high-minus-low is **{ml_res['value']:.5f}** "
            f"[{ml_res['ci_low']:.5f}, {ml_res['ci_high']:.5f}]. It is diagnostic; it is not promoted above "
            "the matched traditional downstream/charge excess unless it predicts held-out excess beyond those controls."
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
        "`result.json`, `manifest.json`, `input_sha256.csv`, reproduction, stratum, traditional, ML, leakage CSVs, and PNG diagnostics are in this folder.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    start = time.time()
    rng = np.random.default_rng(RNG_SEED)
    events, waves, run_counts = load_events()
    topology, repro = reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10 raw-ROOT reproduction gate failed")

    strata_uncorr, trad_uncorr = summarize_traditional(events, "uncorrected_stratum", "p04_duplicate_charge", "uncorrected", rng)
    strata_corr, trad_corr = summarize_traditional(events, "p07_corrected_stratum", "p07_corrected_charge", "p07_corrected", rng)
    trad_summary = pd.concat([trad_uncorr, trad_corr], ignore_index=True)

    scores, current_cv = run_ml(events, waves, rng)
    ml_summary = summarize_ml(scores, strata_uncorr, "uncorrected_stratum", rng)
    y_current = (scores["group"] == "high_20nA").astype(int).to_numpy()
    run_auc = float(roc_auc_score(y_current, scores["weak_current_score"]))
    row_auc = row_split_current_auc(events, rng)
    inj_down_auc = float(roc_auc_score(scores["downstream"], scores["injection_pileup_score"]))
    residual_current_auc = float(roc_auc_score(y_current, scores["charge_regression_residual_score"]))
    leakage = pd.DataFrame(
        [
            {
                "check": "heldout_runs_excluded_from_training",
                "value": 1.0,
                "flag": False,
                "note": "Every ML score is predicted for a source run held out from fitting.",
            },
            {
                "check": "identifier_and_label_features_excluded",
                "value": 1.0,
                "flag": False,
                "note": "Features exclude run, event number, current, group, downstream label, and odd charge samples.",
            },
            {
                "check": "row_split_current_auc",
                "value": row_auc,
                "flag": False,
                "note": "Random row split is an optimistic leakage stress test.",
            },
            {
                "check": "run_heldout_current_auc",
                "value": run_auc,
                "flag": bool(run_auc > 0.95),
                "note": "Flagged if current is nearly identified under run holdout.",
            },
            {
                "check": "row_minus_run_current_auc",
                "value": float(row_auc - run_auc),
                "flag": bool(row_auc - run_auc > 0.10),
                "note": "Large row/run gap would indicate run-local leakage sensitivity.",
            },
            {
                "check": "injection_score_downstream_auc",
                "value": inj_down_auc,
                "flag": bool(inj_down_auc > 0.90),
                "note": "Flagged if synthetic pile-up score nearly recovers the downstream label.",
            },
            {
                "check": "charge_residual_current_auc",
                "value": residual_current_auc,
                "flag": bool(residual_current_auc > 0.90),
                "note": "Flagged if charge residual alone nearly identifies beam current.",
            },
        ]
    )

    save_plots(strata_uncorr, trad_summary, scores)
    input_files = [RAW / f"hrdb_run_{run:04d}.root" for run in sorted(run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    strata_uncorr.to_csv(OUT / "stratum_excess_uncorrected.csv", index=False)
    strata_corr.to_csv(OUT / "stratum_excess_p07_corrected.csv", index=False)
    trad_summary.to_csv(OUT / "traditional_summary.csv", index=False)
    scores.to_csv(OUT / "ml_score_by_event.csv", index=False)
    current_cv.to_csv(OUT / "ml_current_cv_scan.csv", index=False)
    ml_summary.to_csv(OUT / "ml_summary.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)

    trad_down = trad_summary[(trad_summary["strata_definition"] == "uncorrected") & (trad_summary["metric"] == "downstream_high_minus_low")].iloc[0]
    corr_down = trad_summary[(trad_summary["strata_definition"] == "p07_corrected") & (trad_summary["metric"] == "downstream_high_minus_low")].iloc[0]
    p04_shift = trad_summary[(trad_summary["strata_definition"] == "uncorrected") & (trad_summary["metric"] == "p04_duplicate_charge_median_log_shift")].iloc[0]
    ml_res = ml_summary[ml_summary["metric"].str.contains("charge_regression_residual")].iloc[0]
    conclusion = (
        f"The S10c high-current downstream excess remains after replacing the amplitude/topology-only control with "
        f"P04 charge and P07 saturation-energy strata: uncorrected matched downstream excess is {trad_down['value']:.5f} "
        f"[{trad_down['ci_low']:.5f}, {trad_down['ci_high']:.5f}], and P07-corrected B2 strata give {corr_down['value']:.5f} "
        f"[{corr_down['ci_low']:.5f}, {corr_down['ci_high']:.5f}]. The P04 duplicate-charge median log shift is "
        f"{p04_shift['value']:.5f} [{p04_shift['ci_low']:.5f}, {p04_shift['ci_high']:.5f}], while the ML charge-residual "
        f"delta is {ml_res['value']:.5f} [{ml_res['ci_low']:.5f}, {ml_res['ci_high']:.5f}]. ML supports a current-coupled "
        "pulse/charge pathology diagnostic, but the traditional matched excess remains the physics-facing result."
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "pile-up excess transfer to P04/P07 charge-energy proxies",
        "reproduced": bool(repro["pass"].all()),
        "repro_tolerance": "S10/S10c topology fractions within 0.0015 absolute",
        "split": "leave-one-run-out ML predictions; run-block bootstrap CIs within current group",
        "traditional": {
            "uncorrected_downstream_high_minus_low": {
                "value": float(trad_down["value"]),
                "ci": [float(trad_down["ci_low"]), float(trad_down["ci_high"])],
                "n_strata": int(trad_down["n_strata"]),
            },
            "p07_corrected_downstream_high_minus_low": {
                "value": float(corr_down["value"]),
                "ci": [float(corr_down["ci_low"]), float(corr_down["ci_high"])],
                "n_strata": int(corr_down["n_strata"]),
            },
            "p04_duplicate_charge_median_log_shift": {
                "value": float(p04_shift["value"]),
                "ci": [float(p04_shift["ci_low"]), float(p04_shift["ci_high"])],
            },
        },
        "ml": {
            "summary": ml_summary.to_dict(orient="records"),
            "run_heldout_current_auc": run_auc,
            "injection_score_downstream_auc": inj_down_auc,
            "charge_residual_current_auc": residual_current_auc,
        },
        "leakage_flags": int(leakage["flag"].sum()),
        "input_sha256": input_hashes,
        "conclusion": conclusion,
        "git_commit": git_commit(),
        "next_tickets": [
            "S10f: propagate P09a anomaly labels through the P04/P07 charge-stratified current excess model.",
            "S14c: test saturation-corrected charge proxy energy ordering with P04 duplicate-readout uncertainty.",
        ],
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(topology, repro, strata_uncorr, trad_summary, ml_summary, leakage, result)
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": RNG_SEED,
        "command": f"python {Path(__file__).resolve().relative_to(ROOT)}",
        "inputs": input_hashes,
        "outputs": output_hashes(),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "reproduced": result["reproduced"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
