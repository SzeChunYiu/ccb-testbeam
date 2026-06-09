#!/usr/bin/env python3
"""S10f: anomaly-stratified pile-up excess closure.

The script reads raw B-stack ROOT first and reproduces the S10/S10c topology
fractions before assigning P09a taxa, running traditional matched strata, or
training leave-one-run-out ML diagnostics.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Iterable

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
RAW = ROOT / "data/root/root"
os.environ.setdefault("MPLCONFIGDIR", str(OUT / ".mplconfig"))

import numpy as np
import pandas as pd
import uproot
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


TICKET = "1781012706.846.1f364432"
WORKER = "testbeam-laptop-1"
STUDY = "S10f"
RNG_SEED = 1012706
BOOTSTRAPS = 300
ML_CURRENT_MAX_PER_CLASS = 12000
ML_DOWNSTREAM_MAX_NEGATIVES = 36000
AMP_CUT = 1000.0
NSAMPLES = 18
BASELINE_SAMPLES = [0, 1, 2, 3]
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
DUPLICATE_CHANNELS = {"B2": 1, "B4": 3, "B6": 5, "B8": 7}
RUN_GROUPS = {
    "low_2nA": {"current_nA": 2.0, "runs": [46, 47]},
    "high_20nA": {"current_nA": 20.0, "runs": [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]},
}
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
P09A_THRESHOLD_PATH = (
    ROOT
    / "reports/1781005319.615.15053b04__p09a_rare_waveform_anomaly_taxonomy/feature_thresholds.csv"
)
P02C_LATENT_PATH = (
    ROOT
    / "reports/1781010024.975.3e06183e__p02c_p01b_embedding_consumer/p02c_regenerated_p01b_release_latents.npz"
)
P09A_CONFIG_PATH = ROOT / "configs/p09a_rare_waveform_anomaly_taxonomy.json"
S10E_SOURCE_PATH = ROOT / "reports/1781010955.636.68b17313/s10e_charge_energy_transfer.py"
CONTROL_STRATA = [
    "taxon",
    "amp_bin",
    "lowering_bin",
    "saturation_state",
    "ref_stave",
]
PRIMARY_TAXA = [
    "unassigned_common",
    "novel_early_pretrigger",
    "novel_delayed_peak",
    "novel_broad_template_mismatch",
    "baseline_excursion",
    "pileup_or_long_tail",
]


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


def cfd20_crossing(waves: np.ndarray) -> np.ndarray:
    out = np.full(len(waves), np.nan, dtype=np.float32)
    peaks = waves.argmax(axis=1)
    for i, peak in enumerate(peaks):
        if peak <= 0:
            continue
        y = waves[i, : peak + 1]
        idx = np.where(y >= 0.2)[0]
        if len(idx) == 0:
            continue
        j = int(idx[0])
        if j == 0:
            out[i] = 0.0
            continue
        y0, y1 = float(y[j - 1]), float(y[j])
        frac = 0.0 if abs(y1 - y0) < 1e-9 else (0.2 - y0) / (y1 - y0)
        out[i] = float(j - 1 + np.clip(frac, 0.0, 1.0))
    return out


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


def shape_features(waveforms: np.ndarray, amp: np.ndarray) -> pd.DataFrame:
    safe_amp = np.maximum(amp, 1.0)
    positive = np.clip(waveforms, 0.0, None)
    charge = np.maximum(positive.sum(axis=1), 1.0)
    return pd.DataFrame(
        {
            "log_amp": np.log(safe_amp),
            "peak_sample": waveforms.argmax(axis=1).astype(float),
            "area_over_peak": waveforms.sum(axis=1) / safe_amp,
            "tail_fraction": positive[:, 10:].sum(axis=1) / charge,
            "late_fraction": positive[:, 12:].sum(axis=1) / charge,
            "early_fraction": positive[:, :4].sum(axis=1) / charge,
            "post_peak_min_fraction": waveforms[:, 8:].min(axis=1) / safe_amp,
            "neg_step_count": (np.diff(waveforms, axis=1) < -0.20 * safe_amp[:, None]).sum(axis=1),
            "width_10_samples": (waveforms > 0.10 * safe_amp[:, None]).sum(axis=1),
            "width_20_samples": (waveforms > 0.20 * safe_amp[:, None]).sum(axis=1),
            "final_fraction": waveforms[:, -1] / safe_amp,
        }
    )


def iter_root(path: Path) -> Iterable[dict[str, np.ndarray]]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np")


def load_events_from_raw() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    group_for_run = run_to_group()
    even_channels = np.asarray(list(STAVES.values()), dtype=int)
    odd_channels = np.asarray(list(DUPLICATE_CHANNELS.values()), dtype=int)
    stave_names = np.asarray(list(STAVES.keys()), dtype=object)
    frames: list[pd.DataFrame] = []
    corr_waves: list[np.ndarray] = []
    dup_waves: list[np.ndarray] = []
    run_rows: list[dict[str, object]] = []
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
        event_offset = 0
        for batch in iter_root(path):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            all_events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, NSAMPLES)
            raw_even = all_events[:, even_channels, :]
            raw_odd = all_events[:, odd_channels, :]
            seed_even = np.median(raw_even[..., BASELINE_SAMPLES], axis=-1)
            seed_odd = np.median(raw_odd[..., BASELINE_SAMPLES], axis=-1)
            even = raw_even - seed_even[..., None]
            odd = raw_odd - seed_odd[..., None]
            amp = even.max(axis=-1)
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
                event_offset += int(len(eventno))
                continue

            masked_amp = np.where(selected, amp, -np.inf)
            ref_idx = masked_amp.argmax(axis=1)[keep]
            row_idx = np.where(keep)[0]
            corr_ref = even[row_idx, ref_idx, :]
            raw_ref = raw_even[row_idx, ref_idx, :]
            dup_ref = odd[row_idx, ref_idx, :]
            dup_amp = np.maximum(np.abs(dup_ref).max(axis=1), 1.0)
            lowering = adaptive_lowering(raw_ref, seed_even[row_idx, ref_idx])
            frame = pd.DataFrame(
                {
                    "run": int(run),
                    "group": group,
                    "current_nA": float(current),
                    "event_index": (row_idx + event_offset).astype(np.int32),
                    "eventno": eventno[row_idx],
                    "evt": evt[row_idx],
                    "n_selected": n_selected[row_idx].astype(int),
                    "multi_stave": (n_selected[row_idx] >= 2).astype(int),
                    "three_stave": (n_selected[row_idx] >= 3).astype(int),
                    "downstream": selected[row_idx, 1:].any(axis=1).astype(int),
                    "ref_stave": stave_names[ref_idx],
                    "ref_stave_idx": ref_idx.astype(int),
                    "ref_amp_adc": amp[row_idx, ref_idx],
                    "integral_charge": np.clip(corr_ref, 0.0, None).sum(axis=1),
                    "p04_duplicate_charge": np.clip(-dup_ref, 0.0, None).sum(axis=1),
                    "adaptive_lowering_adc": lowering,
                    "baseline_mad": np.median(
                        np.abs(raw_ref[:, BASELINE_SAMPLES] - seed_even[row_idx, ref_idx][:, None]),
                        axis=1,
                    ),
                    "baseline_slope": raw_ref[:, BASELINE_SAMPLES[-1]] - raw_ref[:, BASELINE_SAMPLES[0]],
                    "raw_max_adc": raw_ref.max(axis=1),
                }
            )
            frames.append(frame)
            corr_waves.append(corr_ref.astype(np.float32))
            dup_waves.append((dup_ref / dup_amp[:, None]).astype(np.float32))
            event_offset += int(len(eventno))
        run_rows.append(counts)
    events = pd.concat(frames, ignore_index=True)
    waves = np.concatenate(corr_waves, axis=0)
    dup_norm = np.concatenate(dup_waves, axis=0)
    events = pd.concat([events, shape_features(waves, events["ref_amp_adc"].to_numpy())], axis=1)
    return events, waves, dup_norm, pd.DataFrame(run_rows)


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


def add_template_residual(events: pd.DataFrame, norm_waves: np.ndarray) -> pd.DataFrame:
    edges = np.asarray([1000, 1500, 2500, 4000, 7000, 12000, 25000, 50000], dtype=float)
    bins = np.digitize(events["ref_amp_adc"].to_numpy(), edges, right=False)
    out = events.copy()
    out["template_bin"] = bins.astype(int)
    q = np.zeros(len(out), dtype=np.float32)
    fallback: dict[str, np.ndarray] = {}
    templates: dict[tuple[str, int], np.ndarray] = {}
    for stave in STAVES:
        smask = out["ref_stave"].to_numpy() == stave
        fallback[stave] = np.median(norm_waves[smask], axis=0)
        for b in np.unique(bins[smask]):
            bmask = smask & (bins == b)
            if int(bmask.sum()) >= 30:
                templates[(stave, int(b))] = np.median(norm_waves[bmask], axis=0)
    for stave in STAVES:
        smask = out["ref_stave"].to_numpy() == stave
        for b in np.unique(bins[smask]):
            idx = np.where(smask & (bins == b))[0]
            tmpl = templates.get((stave, int(b)), fallback[stave])
            q[idx] = np.sqrt(np.mean((norm_waves[idx] - tmpl[None, :]) ** 2, axis=1))
    out["q_template_rmse"] = q
    return out


def add_p09a_taxonomy(events: pd.DataFrame, waves: np.ndarray, dup_norm: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    thresholds = pd.read_csv(P09A_THRESHOLD_PATH).set_index("threshold")["value"].to_dict()
    amp = np.maximum(events["ref_amp_adc"].to_numpy(), 1.0)
    norm = (waves / amp[:, None]).astype(np.float32)
    out = add_template_residual(events, norm)
    positive = np.clip(norm, 0.0, None)
    pos_sum = np.maximum(positive.sum(axis=1), 1e-6)
    peak = norm.argmax(axis=1)
    secondary_peak = np.zeros(len(out), dtype=np.float32)
    secondary_sep = np.zeros(len(out), dtype=np.int16)
    post_peak_min = np.zeros(len(out), dtype=np.float32)
    undershoot_area = np.zeros(len(out), dtype=np.float32)
    for i, p in enumerate(peak):
        masked = positive[i].copy()
        lo, hi = max(0, p - 1), min(norm.shape[1], p + 2)
        masked[lo:hi] = 0.0
        sidx = int(masked.argmax())
        secondary_peak[i] = float(masked[sidx])
        secondary_sep[i] = abs(sidx - int(p))
        tail = norm[i, min(norm.shape[1] - 1, int(p) + 1) :]
        post_peak_min[i] = float(tail.min()) if len(tail) else 0.0
        undershoot_area[i] = float(np.clip(tail, None, 0.0).sum()) if len(tail) else 0.0

    timing_span = np.abs(cfd20_crossing(norm) - cfd20_crossing(dup_norm))
    timing_span = np.where(np.isfinite(timing_span), timing_span, 18.0)
    out["p09_late_fraction"] = (positive[:, 12:].sum(axis=1) / pos_sum).astype(np.float32)
    out["p09_early_fraction"] = (positive[:, :4].sum(axis=1) / pos_sum).astype(np.float32)
    out["p09_width_half"] = (norm > 0.5).sum(axis=1).astype(int)
    out["saturation_count"] = (norm >= 0.995).sum(axis=1).astype(int)
    out["secondary_peak"] = secondary_peak
    out["secondary_sep"] = secondary_sep
    out["post_peak_min"] = post_peak_min
    out["undershoot_area"] = undershoot_area
    out["timing_span_dup"] = timing_span.astype(np.float32)

    sat = (out["ref_amp_adc"].to_numpy() > thresholds["amplitude_adc_q995"]) & (
        out["saturation_count"].to_numpy() >= max(2.0, thresholds["saturation_count_q995"])
    )
    dropout = out["post_peak_min"].to_numpy() < min(-0.75, thresholds["post_peak_min_q001"])
    baseline = (out["baseline_mad"].to_numpy() > thresholds["baseline_mad_q995"]) | (
        np.abs(out["baseline_slope"].to_numpy()) > thresholds["abs_baseline_slope_q995"]
    )
    pileup = (
        (out["secondary_peak"].to_numpy() > max(0.55, thresholds["secondary_peak_q999"]))
        & (out["secondary_sep"].to_numpy() >= 4)
    ) | (out["p09_late_fraction"].to_numpy() > thresholds["late_fraction_q999"])
    timing_tail = out["timing_span_dup"].to_numpy() > thresholds["timing_span_dup_q990"]
    known = sat | dropout | baseline | pileup
    early = (peak <= 3) & ~known
    delayed = (peak >= 14) & ~known
    undershoot = (out["undershoot_area"].to_numpy() < thresholds["undershoot_area_q001"]) & ~dropout & ~sat
    broad = (out["p09_width_half"].to_numpy() > thresholds["width_half_q995"]) & ~pileup & ~sat
    template_only = (out["q_template_rmse"].to_numpy() > thresholds["q_template_rmse_q999"]) & ~known & ~early & ~delayed
    novel = early | delayed | undershoot | broad | template_only

    label_map = {
        "label_saturation": sat,
        "label_dropout": dropout,
        "label_baseline_excursion": baseline,
        "label_pileup_or_long_tail": pileup,
        "label_timing_tail": timing_tail,
        "label_novel_early_pretrigger": early,
        "label_novel_delayed_peak": delayed,
        "label_novel_undershoot_recovery": undershoot,
        "label_novel_broad_template_mismatch": broad | template_only,
        "label_known_any": known,
        "label_novel_any": novel,
        "label_curated_any": known | novel,
    }
    for name, values in label_map.items():
        out[name] = values.astype(int)
    priority = [
        ("saturation", sat),
        ("dropout", dropout),
        ("baseline_excursion", baseline),
        ("pileup_or_long_tail", pileup),
        ("novel_early_pretrigger", early),
        ("novel_delayed_peak", delayed),
        ("novel_undershoot_recovery", undershoot),
        ("novel_broad_template_mismatch", broad | template_only),
        ("physics_timing_tail_only", timing_tail & ~(known | novel)),
    ]
    taxon = np.full(len(out), "unassigned_common", dtype=object)
    for name, mask in reversed(priority):
        taxon[mask] = name
    out["taxon"] = taxon
    out["amp_bin"] = pd.cut(
        out["ref_amp_adc"],
        bins=[0.0, 1500.0, 2500.0, 4000.0, 7000.0, 12000.0, np.inf],
        labels=["amp_1_1p5k", "amp_1p5_2p5k", "amp_2p5_4k", "amp_4_7k", "amp_7_12k", "amp_ge_12k"],
        include_lowest=True,
        right=False,
    ).astype(str)
    out["lowering_bin"] = pd.cut(
        out["adaptive_lowering_adc"],
        bins=[-0.1, 0.1, 200.0, np.inf],
        labels=["lowering_none", "lowering_mild", "lowering_large"],
        include_lowest=True,
        right=False,
    ).astype(str)
    sat_state = np.full(len(out), "nonsaturated", dtype=object)
    sat_state[out["saturation_count"].to_numpy() >= 2] = "saturation_proxy"
    out["saturation_state"] = sat_state
    out["control_stratum"] = out[CONTROL_STRATA].astype(str).agg("|".join, axis=1)
    threshold_frame = pd.DataFrame([{"threshold": k, "value": v} for k, v in thresholds.items()])
    return out, threshold_frame


def load_p02_latents(events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, object]]:
    z = np.load(P02C_LATENT_PATH)
    lat = pd.DataFrame(
        {
            "run": z["run"].astype(int),
            "event_index": z["event_index"].astype(int),
            "ref_stave_idx": z["stave_index"].astype(int),
            "latent_amp_adc": z["amplitude_adc"].astype(float),
            "p02_z0": z["z"][:, 0],
            "p02_z1": z["z"][:, 1],
            "p02_z2": z["z"][:, 2],
            "p02_z3": z["z"][:, 3],
        }
    )
    merged = events.merge(lat, on=["run", "event_index", "ref_stave_idx"], how="left", validate="one_to_one")
    zcols = ["p02_z0", "p02_z1", "p02_z2", "p02_z3"]
    missing = merged[zcols].isna().any(axis=1)
    if missing.any():
        fill = merged.loc[~missing, zcols].median()
        merged.loc[missing, zcols] = fill.to_numpy()
    meta = {
        "artifact": str(P02C_LATENT_PATH.relative_to(ROOT)),
        "sha256": sha256_file(P02C_LATENT_PATH),
        "matched_rows": int((~missing).sum()),
        "missing_rows": int(missing.sum()),
    }
    return merged, meta


def add_latent_distances(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    zcols = ["p02_z0", "p02_z1", "p02_z2", "p02_z3"]
    z = out[zcols].to_numpy(dtype=float)
    center = np.median(z, axis=0)
    common = out["taxon"].to_numpy() == "unassigned_common"
    common_center = np.median(z[common], axis=0) if common.any() else center
    rare = ~common
    rare_center = np.median(z[rare], axis=0) if rare.any() else center
    out["latent_distance_global"] = np.linalg.norm(z - center[None, :], axis=1)
    out["latent_distance_common"] = np.linalg.norm(z - common_center[None, :], axis=1)
    out["latent_distance_rare"] = np.linalg.norm(z - rare_center[None, :], axis=1)
    return out


def matched_strata(events: pd.DataFrame, stratum_col: str = "control_stratum", min_n: int = 12) -> pd.DataFrame:
    counts = (
        events.groupby([stratum_col, "group"], observed=False)
        .agg(n=("downstream", "size"), downstream=("downstream", "sum"))
        .reset_index()
        .rename(columns={stratum_col: "stratum"})
    )
    pivot = counts.pivot(index="stratum", columns="group", values=["n", "downstream"]).fillna(0)
    rows = []
    for stratum in pivot.index:
        low_n = int(pivot.loc[stratum, ("n", "low_2nA")]) if ("n", "low_2nA") in pivot.columns else 0
        high_n = int(pivot.loc[stratum, ("n", "high_20nA")]) if ("n", "high_20nA") in pivot.columns else 0
        if low_n < min_n or high_n < min_n:
            continue
        low_d = int(pivot.loc[stratum, ("downstream", "low_2nA")])
        high_d = int(pivot.loc[stratum, ("downstream", "high_20nA")])
        pieces = str(stratum).split("|")
        rows.append(
            {
                "stratum": stratum,
                "taxon": pieces[0],
                "low_n": low_n,
                "high_n": high_n,
                "match_weight_raw": min(low_n, high_n),
                "low_downstream_fraction": low_d / low_n,
                "high_downstream_fraction": high_d / high_n,
                "downstream_high_minus_low": high_d / high_n - low_d / low_n,
                "odds_ratio": ((high_d + 0.5) / (high_n - high_d + 0.5))
                / ((low_d + 0.5) / (low_n - low_d + 0.5)),
            }
        )
    table = pd.DataFrame(rows).sort_values(["taxon", "match_weight_raw"], ascending=[True, False]).reset_index(drop=True)
    if len(table):
        table["match_weight"] = table["match_weight_raw"] / table["match_weight_raw"].sum()
    return table


def weighted_delta(events: pd.DataFrame, strata: pd.DataFrame, value_col: str, mode: str = "mean") -> float:
    wanted = set(strata["stratum"])
    view = events[events["control_stratum"].isin(wanted)]
    if mode == "mean":
        series = view.groupby(["control_stratum", "group"], observed=False)[value_col].mean()
    elif mode == "log_median":
        tmp = view[["control_stratum", "group", value_col]].copy()
        tmp[value_col] = np.log(np.maximum(tmp[value_col].to_numpy(), 1.0))
        series = tmp.groupby(["control_stratum", "group"], observed=False)[value_col].median()
    else:
        raise ValueError(mode)
    total = 0.0
    norm = 0.0
    for row in strata.itertuples(index=False):
        try:
            low = float(series.loc[(row.stratum, "low_2nA")])
            high = float(series.loc[(row.stratum, "high_20nA")])
        except KeyError:
            continue
        total += float(row.match_weight_raw) * (high - low)
        norm += float(row.match_weight_raw)
    return float(total / max(norm, 1.0))


def weighted_odds_ratio(events: pd.DataFrame, strata: pd.DataFrame) -> float:
    total_low_n = total_high_n = total_low_d = total_high_d = 0.0
    for row in strata.itertuples(index=False):
        sub = events[events["control_stratum"] == row.stratum]
        low = sub[sub["group"] == "low_2nA"]
        high = sub[sub["group"] == "high_20nA"]
        w = float(row.match_weight_raw)
        total_low_n += w * len(low) / max(float(row.low_n), 1.0)
        total_high_n += w * len(high) / max(float(row.high_n), 1.0)
        total_low_d += w * float(low["downstream"].sum()) / max(float(row.low_n), 1.0)
        total_high_d += w * float(high["downstream"].sum()) / max(float(row.high_n), 1.0)
    return float(
        ((total_high_d + 0.5) / (total_high_n - total_high_d + 0.5))
        / ((total_low_d + 0.5) / (total_low_n - total_low_d + 0.5))
    )


def heterogeneity(strata: pd.DataFrame) -> float:
    if len(strata) <= 1:
        return 0.0
    w = strata["match_weight_raw"].to_numpy(dtype=float)
    x = strata["downstream_high_minus_low"].to_numpy(dtype=float)
    mu = np.average(x, weights=w)
    return float(np.sqrt(np.average((x - mu) ** 2, weights=w)))


def summarize_traditional(events: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    strata = matched_strata(events)
    run_summary = (
        events[["run", "group", "control_stratum", "downstream", "p04_duplicate_charge", "integral_charge"]]
        .groupby(["run", "group", "control_stratum"], observed=False)
        .agg(
            n=("downstream", "size"),
            downstream=("downstream", "sum"),
            p04_duplicate_charge=("p04_duplicate_charge", "median"),
            integral_charge=("integral_charge", "median"),
        )
        .reset_index()
    )
    run_summary["log_p04_duplicate_charge"] = np.log(np.maximum(run_summary["p04_duplicate_charge"].to_numpy(), 1.0))

    def filtered_summary(summary: pd.DataFrame, use_strata: pd.DataFrame) -> pd.DataFrame:
        return summary[summary["control_stratum"].isin(set(use_strata["stratum"]))].copy()

    def downstream_delta_from_summary(summary: pd.DataFrame, use_strata: pd.DataFrame) -> float:
        tmp = filtered_summary(summary, use_strata)
        grouped = tmp.groupby(["control_stratum", "group"], observed=False).agg(n=("n", "sum"), downstream=("downstream", "sum"))
        total = 0.0
        norm = 0.0
        for row in use_strata.itertuples(index=False):
            try:
                low = grouped.loc[(row.stratum, "low_2nA")]
                high = grouped.loc[(row.stratum, "high_20nA")]
            except KeyError:
                continue
            total += float(row.match_weight_raw) * (float(high.downstream) / float(high.n) - float(low.downstream) / float(low.n))
            norm += float(row.match_weight_raw)
        return float(total / max(norm, 1.0))

    def odds_from_summary(summary: pd.DataFrame, use_strata: pd.DataFrame) -> float:
        tmp = filtered_summary(summary, use_strata)
        grouped = tmp.groupby(["control_stratum", "group"], observed=False).agg(n=("n", "sum"), downstream=("downstream", "sum"))
        low_n = high_n = low_d = high_d = 0.0
        for row in use_strata.itertuples(index=False):
            try:
                low = grouped.loc[(row.stratum, "low_2nA")]
                high = grouped.loc[(row.stratum, "high_20nA")]
            except KeyError:
                continue
            w = float(row.match_weight_raw)
            low_n += w
            high_n += w
            low_d += w * float(low.downstream) / float(low.n)
            high_d += w * float(high.downstream) / float(high.n)
        return float(((high_d + 0.5) / (high_n - high_d + 0.5)) / ((low_d + 0.5) / (low_n - low_d + 0.5)))

    def charge_shift_from_summary(summary: pd.DataFrame, use_strata: pd.DataFrame) -> float:
        tmp = filtered_summary(summary, use_strata)
        tmp["weighted_log_charge"] = tmp["log_p04_duplicate_charge"] * tmp["n"]
        grouped = tmp.groupby(["control_stratum", "group"], observed=False).agg(
            n=("n", "sum"), weighted_log_charge=("weighted_log_charge", "sum")
        )
        total = 0.0
        norm = 0.0
        for row in use_strata.itertuples(index=False):
            try:
                low = grouped.loc[(row.stratum, "low_2nA")]
                high = grouped.loc[(row.stratum, "high_20nA")]
            except KeyError:
                continue
            low_log = float(low.weighted_log_charge) / float(low.n)
            high_log = float(high.weighted_log_charge) / float(high.n)
            total += float(row.match_weight_raw) * (high_log - low_log)
            norm += float(row.match_weight_raw)
        return float(total / max(norm, 1.0))

    def heterogeneity_from_summary(summary: pd.DataFrame, use_strata: pd.DataFrame) -> float:
        tmp = filtered_summary(summary, use_strata)
        grouped = tmp.groupby(["control_stratum", "group"], observed=False).agg(n=("n", "sum"), downstream=("downstream", "sum"))
        vals = []
        weights = []
        for row in use_strata.itertuples(index=False):
            try:
                low = grouped.loc[(row.stratum, "low_2nA")]
                high = grouped.loc[(row.stratum, "high_20nA")]
            except KeyError:
                continue
            vals.append(float(high.downstream) / float(high.n) - float(low.downstream) / float(low.n))
            weights.append(float(row.match_weight_raw))
        if len(vals) <= 1:
            return 0.0
        x = np.asarray(vals, dtype=float)
        w = np.asarray(weights, dtype=float)
        mu = np.average(x, weights=w)
        return float(np.sqrt(np.average((x - mu) ** 2, weights=w)))

    summary_rows = []
    taxa = ["ALL"] + [t for t in PRIMARY_TAXA if t in set(events["taxon"])]
    for taxon in taxa:
        sub_strata = strata if taxon == "ALL" else strata[strata["taxon"] == taxon].copy()
        if len(sub_strata) == 0:
            continue
        sub_events = events if taxon == "ALL" else events[events["taxon"] == taxon]
        values = {
            "downstream_high_minus_low": weighted_delta(sub_events, sub_strata, "downstream"),
            "topology_odds_ratio": weighted_odds_ratio(sub_events, sub_strata),
            "p04_duplicate_charge_log_shift": weighted_delta(sub_events, sub_strata, "p04_duplicate_charge", "log_median"),
            "stratum_heterogeneity": heterogeneity(sub_strata),
        }
        low_runs = np.asarray(RUN_GROUPS["low_2nA"]["runs"])
        high_runs = np.asarray(RUN_GROUPS["high_20nA"]["runs"])
        boot = {key: [] for key in values}
        for _ in range(BOOTSTRAPS):
            sampled_runs = np.r_[rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True)]
            sample_summary = pd.concat([run_summary[run_summary["run"] == int(run)] for run in sampled_runs], ignore_index=True)
            for key in boot:
                if key == "topology_odds_ratio":
                    boot[key].append(odds_from_summary(sample_summary, sub_strata))
                elif key == "p04_duplicate_charge_log_shift":
                    boot[key].append(charge_shift_from_summary(sample_summary, sub_strata))
                elif key == "stratum_heterogeneity":
                    boot[key].append(heterogeneity_from_summary(sample_summary, sub_strata))
                else:
                    boot[key].append(downstream_delta_from_summary(sample_summary, sub_strata))
        for metric, value in values.items():
            vals = np.asarray(boot[metric], dtype=float)
            vals = vals[np.isfinite(vals)]
            summary_rows.append(
                {
                    "taxon": taxon,
                    "metric": metric,
                    "value": float(value),
                    "ci_low": float(np.quantile(vals, 0.025)) if len(vals) else np.nan,
                    "ci_high": float(np.quantile(vals, 0.975)) if len(vals) else np.nan,
                    "n_strata": int(len(sub_strata)),
                    "matched_low_n": int(sub_strata["low_n"].sum()),
                    "matched_high_n": int(sub_strata["high_n"].sum()),
                    "bootstrap_unit": "run_within_current_group",
                    "n_bootstrap": BOOTSTRAPS,
                }
            )
    return strata, pd.DataFrame(summary_rows), run_summary


def ml_features(events: pd.DataFrame) -> pd.DataFrame:
    taxa = pd.get_dummies(events["taxon"], prefix="taxon", dtype=float)
    labels = [
        "label_saturation",
        "label_dropout",
        "label_baseline_excursion",
        "label_pileup_or_long_tail",
        "label_timing_tail",
        "label_novel_early_pretrigger",
        "label_novel_delayed_peak",
        "label_novel_broad_template_mismatch",
        "label_curated_any",
        "q_template_rmse",
        "p09_late_fraction",
        "p09_early_fraction",
        "timing_span_dup",
        "secondary_peak",
        "post_peak_min",
        "undershoot_area",
        "latent_distance_global",
        "latent_distance_common",
        "latent_distance_rare",
    ]
    return pd.concat([events[labels].astype(float).reset_index(drop=True), taxa.reset_index(drop=True)], axis=1)


def fit_calibrated(x: pd.DataFrame, y: np.ndarray) -> tuple[object, LogisticRegression, LogisticRegression]:
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=400, solver="liblinear", class_weight="balanced", C=0.5, random_state=RNG_SEED),
    )
    model.fit(x, y)
    raw = model.predict_proba(x)[:, 1]
    eps = 1e-5
    logit = np.log(np.clip(raw, eps, 1 - eps) / np.clip(1 - raw, eps, 1 - eps)).reshape(-1, 1)
    calibrator = LogisticRegression(max_iter=1000, random_state=RNG_SEED).fit(logit, y)
    return model, model[-1], calibrator


def apply_calibrated(model: object, calibrator: LogisticRegression, x: pd.DataFrame) -> np.ndarray:
    raw = model.predict_proba(x)[:, 1]
    eps = 1e-5
    logit = np.log(np.clip(raw, eps, 1 - eps) / np.clip(1 - raw, eps, 1 - eps)).reshape(-1, 1)
    return calibrator.predict_proba(logit)[:, 1]


def run_ml(events: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    x_all = ml_features(events)
    score_frames = []
    fold_rows = []
    all_cols = list(x_all.columns)
    for heldout_run in sorted(events["run"].unique()):
        train_mask = events["run"].to_numpy() != heldout_run
        test_mask = ~train_mask
        train = events.loc[train_mask]
        test = events.loc[test_mask]
        x_train = x_all.loc[train_mask, all_cols]
        x_test = x_all.loc[test_mask, all_cols]

        y_current = (train["group"] == "high_20nA").astype(int).to_numpy()
        current_low = np.where(y_current == 0)[0]
        current_high = np.where(y_current == 1)[0]
        n_current = min(len(current_low), len(current_high), ML_CURRENT_MAX_PER_CLASS)
        current_idx = np.r_[
            rng.choice(current_low, size=n_current, replace=False),
            rng.choice(current_high, size=n_current, replace=False),
        ]
        rng.shuffle(current_idx)
        current_model, _, current_cal = fit_calibrated(x_train.iloc[current_idx], y_current[current_idx])
        current_score = apply_calibrated(current_model, current_cal, x_test)

        y_down = train["downstream"].astype(int).to_numpy()
        if len(np.unique(y_down)) == 1:
            pileup_score = np.full(len(test), float(y_down[0]))
        else:
            pos = np.where(y_down == 1)[0]
            neg = np.where(y_down == 0)[0]
            n_neg = min(len(neg), max(4 * len(pos), ML_DOWNSTREAM_MAX_NEGATIVES))
            down_idx = np.r_[pos, rng.choice(neg, size=n_neg, replace=False)]
            rng.shuffle(down_idx)
            down_model, _, down_cal = fit_calibrated(x_train.iloc[down_idx], y_down[down_idx])
            pileup_score = apply_calibrated(down_model, down_cal, x_test)

        score_frames.append(
            test[
                [
                    "run",
                    "group",
                    "current_nA",
                    "event_index",
                    "eventno",
                    "downstream",
                    "taxon",
                    "control_stratum",
                ]
            ].assign(ml_current_score=current_score, ml_pileup_score=pileup_score)
        )
        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "train_rows": int(train_mask.sum()),
                "test_rows": int(test_mask.sum()),
                "feature_count": int(len(all_cols)),
                "train_current_high_fraction": float(y_current.mean()),
                "train_downstream_fraction": float(y_down.mean()),
            }
        )
    scores = pd.concat(score_frames, ignore_index=True)
    y_current_all = (scores["group"] == "high_20nA").astype(int).to_numpy()
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
                "note": "Features are P09a labels/scores and P01/P02 latent distances only; run, event, group, and current are excluded.",
            },
            {
                "check": "run_heldout_current_auc",
                "value": float(roc_auc_score(y_current_all, scores["ml_current_score"])),
                "flag": bool(roc_auc_score(y_current_all, scores["ml_current_score"]) > 0.95),
                "note": "Flagged if current is nearly identified under leave-one-run-out evaluation.",
            },
            {
                "check": "run_heldout_pileup_auc",
                "value": float(roc_auc_score(scores["downstream"], scores["ml_pileup_score"])),
                "flag": bool(roc_auc_score(scores["downstream"], scores["ml_pileup_score"]) > 0.90),
                "note": "Flagged if P09/latent features nearly recover the downstream label.",
            },
        ]
    )
    # Row-split stress test on the same allowed features; it is deliberately optimistic.
    low = events[events["group"] == "low_2nA"]
    high = events[events["group"] == "high_20nA"]
    n = min(len(low), len(high), 12000)
    row_sample = pd.concat(
        [
            low.sample(n=n, random_state=int(rng.integers(0, 1_000_000))),
            high.sample(n=n, random_state=int(rng.integers(0, 1_000_000))),
        ]
    )
    y = (row_sample["group"] == "high_20nA").astype(int).to_numpy()
    x = ml_features(row_sample)
    order = rng.permutation(len(row_sample))
    tr, te = order[: len(order) // 2], order[len(order) // 2 :]
    row_model, _, row_cal = fit_calibrated(x.iloc[tr], y[tr])
    row_pred = apply_calibrated(row_model, row_cal, x.iloc[te])
    row_auc = float(roc_auc_score(y[te], row_pred))
    run_auc = float(leakage.loc[leakage["check"] == "run_heldout_current_auc", "value"].iloc[0])
    leakage = pd.concat(
        [
            leakage,
            pd.DataFrame(
                [
                    {
                        "check": "row_split_current_auc",
                        "value": row_auc,
                        "flag": False,
                        "note": "Optimistic random row split stress test.",
                    },
                    {
                        "check": "row_minus_run_current_auc",
                        "value": float(row_auc - run_auc),
                        "flag": bool(row_auc - run_auc > 0.10),
                        "note": "Large row/run gap suggests run-local leakage sensitivity.",
                    },
                ]
            ),
        ],
        ignore_index=True,
    )
    return scores, pd.DataFrame(fold_rows), leakage


def summarize_ml_scores(scores: pd.DataFrame, strata: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    score_cols = ["ml_current_score", "ml_pileup_score"]
    run_summary = (
        scores[["run", "group", "control_stratum"] + score_cols]
        .groupby(["run", "group", "control_stratum"], observed=False)
        .agg(n=("ml_current_score", "size"), ml_current_score=("ml_current_score", "mean"), ml_pileup_score=("ml_pileup_score", "mean"))
        .reset_index()
    )

    def score_delta(summary: pd.DataFrame, use_strata: pd.DataFrame, score_col: str) -> float:
        tmp = summary[summary["control_stratum"].isin(set(use_strata["stratum"]))].copy()
        tmp["weighted"] = tmp[score_col] * tmp["n"]
        grouped = tmp.groupby(["control_stratum", "group"], observed=False).agg(weighted=("weighted", "sum"), n=("n", "sum"))
        series = grouped["weighted"] / grouped["n"]
        total = 0.0
        norm = 0.0
        for row in use_strata.itertuples(index=False):
            try:
                low = float(series.loc[(row.stratum, "low_2nA")])
                high = float(series.loc[(row.stratum, "high_20nA")])
            except KeyError:
                continue
            total += float(row.match_weight_raw) * (high - low)
            norm += float(row.match_weight_raw)
        return float(total / max(norm, 1.0))

    taxa = ["ALL"] + [t for t in PRIMARY_TAXA if t in set(strata["taxon"])]
    low_runs = np.asarray(RUN_GROUPS["low_2nA"]["runs"])
    high_runs = np.asarray(RUN_GROUPS["high_20nA"]["runs"])
    for taxon in taxa:
        use_strata = strata if taxon == "ALL" else strata[strata["taxon"] == taxon].copy()
        if len(use_strata) == 0:
            continue
        for score_col in score_cols:
            value = score_delta(run_summary, use_strata, score_col)
            boot = []
            for _ in range(BOOTSTRAPS):
                sampled_runs = np.r_[rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True)]
                sample = pd.concat([run_summary[run_summary["run"] == int(run)] for run in sampled_runs], ignore_index=True)
                boot.append(score_delta(sample, use_strata, score_col))
            rows.append(
                {
                    "taxon": taxon,
                    "metric": f"{score_col}_high_minus_low",
                    "value": float(value),
                    "ci_low": float(np.quantile(boot, 0.025)),
                    "ci_high": float(np.quantile(boot, 0.975)),
                    "n_strata": int(len(use_strata)),
                    "bootstrap_unit": "run_within_current_group",
                    "n_bootstrap": BOOTSTRAPS,
                }
            )
    return pd.DataFrame(rows), run_summary


def adoption_check(events: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    merged = events[["run", "downstream", "control_stratum"]].merge(
        scores[["run", "event_index", "ml_pileup_score"]],
        left_index=True,
        right_index=True,
        how="left",
        suffixes=("", "_score"),
    )
    rows = []
    eps = 1e-4
    for heldout_run in sorted(events["run"].unique()):
        train = events[events["run"] != heldout_run]
        test = events[events["run"] == heldout_run].copy()
        test_scores = scores[scores["run"] == heldout_run].copy()
        rates = train.groupby("control_stratum")["downstream"].mean()
        global_rate = float(train["downstream"].mean())
        base = test["control_stratum"].map(rates).fillna(global_rate).to_numpy(dtype=float)
        ml = test_scores["ml_pileup_score"].to_numpy(dtype=float)
        y = test["downstream"].to_numpy(dtype=int)
        rows.append(
            {
                "heldout_run": int(heldout_run),
                "n": int(len(test)),
                "traditional_brier": float(brier_score_loss(y, np.clip(base, eps, 1 - eps))),
                "ml_brier": float(brier_score_loss(y, np.clip(ml, eps, 1 - eps))),
                "traditional_log_loss": float(log_loss(y, np.clip(base, eps, 1 - eps), labels=[0, 1])),
                "ml_log_loss": float(log_loss(y, np.clip(ml, eps, 1 - eps), labels=[0, 1])),
            }
        )
    out = pd.DataFrame(rows)
    out["brier_improvement"] = out["traditional_brier"] - out["ml_brier"]
    out["log_loss_improvement"] = out["traditional_log_loss"] - out["ml_log_loss"]
    return out


def write_report(
    topology: pd.DataFrame,
    repro: pd.DataFrame,
    taxonomy_counts: pd.DataFrame,
    strata: pd.DataFrame,
    traditional: pd.DataFrame,
    ml_summary: pd.DataFrame,
    adoption: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict[str, object],
) -> None:
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    all_down = traditional[(traditional["taxon"] == "ALL") & (traditional["metric"] == "downstream_high_minus_low")].iloc[0]
    rare_down = traditional[
        traditional["taxon"].isin(["novel_delayed_peak", "novel_broad_template_mismatch", "baseline_excursion", "pileup_or_long_tail"])
        & (traditional["metric"] == "downstream_high_minus_low")
    ].copy()
    ml_current = ml_summary[(ml_summary["taxon"] == "ALL") & (ml_summary["metric"] == "ml_current_score_high_minus_low")].iloc[0]
    adopted = bool(result["ml_adopted"])
    best = rare_down.sort_values("value", ascending=False).head(4)
    lines = [
        "# S10f: anomaly-stratified pile-up excess closure",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** ML predictions are leave-one-run-out by run; CIs are run-block bootstrap within current group.",
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
        "## P09a taxonomy overlay",
        "",
        "P09a labels were assigned with the frozen P09a thresholds in `feature_thresholds.csv`. Matching strata are taxon x amplitude bin x S16 baseline-lowering bin x saturation proxy x stave.",
        "",
        taxonomy_counts.to_markdown(index=False),
        "",
        "## Traditional matched result",
        "",
        (
            f"Across matched taxonomy/control strata, the high-minus-low downstream excess is "
            f"**{all_down['value']:.5f}** [{all_down['ci_low']:.5f}, {all_down['ci_high']:.5f}] per selected event. "
            f"The matched topology odds ratio is reported with the same run bootstrap, and heterogeneity is the weighted "
            "SD of stratum-level high-minus-low excess."
        ),
        "",
        traditional.to_markdown(index=False),
        "",
        "Largest rare-taxon downstream excess rows:",
        "",
        best.to_markdown(index=False),
        "",
        "Top matched strata by weight:",
        "",
        strata.sort_values("match_weight_raw", ascending=False).head(10).to_markdown(index=False),
        "",
        "## ML diagnostics",
        "",
        (
            "The ML current and pile-up scores use only P09a labels/scores plus P01/P02 latent-distance features. "
            f"The all-strata current-score high-minus-low delta is **{ml_current['value']:.5f}** "
            f"[{ml_current['ci_low']:.5f}, {ml_current['ci_high']:.5f}]."
        ),
        "",
        ml_summary.to_markdown(index=False),
        "",
        "ML adoption check against the traditional train-run stratum-rate downstream baseline:",
        "",
        adoption.to_markdown(index=False),
        "",
        f"ML adopted as a physics-facing result: **{adopted}**.",
        "",
        "## Leakage review",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        str(result["conclusion"]),
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, reproduction, taxonomy, traditional, ML, adoption, leakage, and fold CSVs are in this folder.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def output_hashes() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG_SEED)

    events, waves, dup_norm, run_counts = load_events_from_raw()
    topology, repro = reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10 raw-ROOT reproduction gate failed")

    events, p02_meta = load_p02_latents(events)
    events, thresholds = add_p09a_taxonomy(events, waves, dup_norm)
    events = add_latent_distances(events)
    taxonomy_counts = (
        events.groupby(["taxon", "group"], observed=False)
        .size()
        .reset_index(name="n")
        .pivot(index="taxon", columns="group", values="n")
        .fillna(0)
        .reset_index()
    )
    taxonomy_counts["total"] = taxonomy_counts.get("low_2nA", 0) + taxonomy_counts.get("high_20nA", 0)
    taxonomy_counts["rate"] = taxonomy_counts["total"] / len(events)
    taxonomy_counts = taxonomy_counts.sort_values("total", ascending=False)

    strata, traditional, traditional_run_summary = summarize_traditional(events, rng)
    scores, ml_folds, leakage = run_ml(events, rng)
    ml_summary, ml_run_summary = summarize_ml_scores(scores, strata, rng)
    adoption = adoption_check(events, scores)
    mean_brier_improvement = float(np.average(adoption["brier_improvement"], weights=adoption["n"]))
    mean_logloss_improvement = float(np.average(adoption["log_loss_improvement"], weights=adoption["n"]))
    ml_adopted = bool(mean_brier_improvement > 0.001 and mean_logloss_improvement > 0.001 and int(leakage["flag"].sum()) == 0)

    input_files = [RAW / f"hrdb_run_{run:04d}.root" for run in sorted(run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    thresholds.to_csv(OUT / "p09a_thresholds_used.csv", index=False)
    taxonomy_counts.to_csv(OUT / "taxonomy_counts_by_current.csv", index=False)
    strata.to_csv(OUT / "matched_strata.csv", index=False)
    traditional.to_csv(OUT / "traditional_taxon_summary.csv", index=False)
    traditional_run_summary.to_csv(OUT / "traditional_run_stratum_summary.csv", index=False)
    scores.to_csv(OUT / "ml_score_by_event.csv", index=False)
    ml_folds.to_csv(OUT / "ml_loro_folds.csv", index=False)
    ml_summary.to_csv(OUT / "ml_taxon_summary.csv", index=False)
    ml_run_summary.to_csv(OUT / "ml_run_stratum_summary.csv", index=False)
    adoption.to_csv(OUT / "ml_adoption_check.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)

    all_down = traditional[(traditional["taxon"] == "ALL") & (traditional["metric"] == "downstream_high_minus_low")].iloc[0]
    all_or = traditional[(traditional["taxon"] == "ALL") & (traditional["metric"] == "topology_odds_ratio")].iloc[0]
    current_score = ml_summary[(ml_summary["taxon"] == "ALL") & (ml_summary["metric"] == "ml_current_score_high_minus_low")].iloc[0]
    rare = traditional[
        traditional["taxon"].isin(["novel_delayed_peak", "novel_broad_template_mismatch", "baseline_excursion", "pileup_or_long_tail"])
        & (traditional["metric"] == "downstream_high_minus_low")
    ].sort_values("value", ascending=False)
    rare_sentence = (
        f"The largest rare-class traditional excess is {rare.iloc[0]['taxon']} at {rare.iloc[0]['value']:.5f} "
        f"[{rare.iloc[0]['ci_low']:.5f}, {rare.iloc[0]['ci_high']:.5f}]."
        if len(rare)
        else "No rare-class matched stratum passed the minimum count gate."
    )
    conclusion = (
        f"The S10c excess is not isolated to a single P09a rare waveform class. The taxonomy/control matched "
        f"traditional excess is {all_down['value']:.5f} [{all_down['ci_low']:.5f}, {all_down['ci_high']:.5f}] per selected "
        f"event with topology odds ratio {all_or['value']:.3f} [{all_or['ci_low']:.3f}, {all_or['ci_high']:.3f}]. "
        f"{rare_sentence} The LORO ML current-score delta is {current_score['value']:.5f} "
        f"[{current_score['ci_low']:.5f}, {current_score['ci_high']:.5f}], but the downstream-score adoption check has "
        f"weighted Brier improvement {mean_brier_improvement:.6f} and log-loss improvement {mean_logloss_improvement:.6f}; "
        f"ML adopted={ml_adopted}. The physics-facing result remains the traditional matched P09a-stratified excess."
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "anomaly-stratified pile-up excess closure",
        "reproduced": bool(repro["pass"].all()),
        "repro_tolerance": "S10/S10c topology fractions within 0.0015 absolute",
        "split": "leave-one-run-out ML predictions; run-block bootstrap CIs within current group",
        "traditional": traditional.to_dict(orient="records"),
        "ml": {
            "summary": ml_summary.to_dict(orient="records"),
            "adoption": {
                "mean_brier_improvement": mean_brier_improvement,
                "mean_log_loss_improvement": mean_logloss_improvement,
                "adopted": ml_adopted,
            },
            "p02_latent_artifact": p02_meta,
        },
        "leakage_flags": int(leakage["flag"].sum()),
        "input_sha256": input_hashes,
        "upstream_artifacts": {
            "p09a_thresholds": {
                "path": str(P09A_THRESHOLD_PATH.relative_to(ROOT)),
                "sha256": sha256_file(P09A_THRESHOLD_PATH),
            },
            "p09a_config": {
                "path": str(P09A_CONFIG_PATH.relative_to(ROOT)),
                "sha256": sha256_file(P09A_CONFIG_PATH),
            },
            "p02c_latents": p02_meta,
            "s10e_source_used_as_method_reference": {
                "path": str(S10E_SOURCE_PATH.relative_to(ROOT)),
                "sha256": sha256_file(S10E_SOURCE_PATH),
            },
        },
        "ml_adopted": ml_adopted,
        "conclusion": conclusion,
        "git_commit": git_commit(),
        "follow_up_tickets": [
            "S10g: re-run anomaly-stratified excess with human-adjudicated P09b rare-class labels and compare to deterministic P09a labels.",
            "P02d: publish run-heldout P01/P02 latent-distance artifact keyed by event id for downstream leakage-safe studies.",
        ],
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(topology, repro, taxonomy_counts, strata, traditional, ml_summary, adoption, leakage, result)
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": RNG_SEED,
        "command": f"uv run --with uproot --with numpy --with pandas --with scikit-learn --with tabulate python {Path(__file__).resolve().relative_to(ROOT)}",
        "inputs": input_hashes,
        "upstream_artifacts": result["upstream_artifacts"],
        "outputs": output_hashes(),
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "reproduced": result["reproduced"], "ml_adopted": ml_adopted, "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
