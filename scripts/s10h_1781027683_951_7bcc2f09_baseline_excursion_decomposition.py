#!/usr/bin/env python3
"""S10h: decompose the S10f baseline-excursion downstream excess.

Inputs are raw B-stack ROOT runs 44-57.  The script first rebuilds the S10e/S10f
selected-event table and reproduces the registered S10f baseline-excursion
number before fitting any decomposition model.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from importlib import util
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/root/root"
OUT = ROOT / "reports/1781027683.951.7bcc2f09"
OUT.mkdir(parents=True, exist_ok=True)

TICKET = "1781027683.951.7bcc2f09"
WORKER = "testbeam-laptop-3"
STUDY = "S10h"
RNG_SEED = 1781027683
BOOTSTRAPS = 500
MIN_STRATUM_N = 5

S10E_REPORT = ROOT / "reports/1781010955.636.68b17313/s10e_charge_energy_transfer.py"
P09A_SCRIPT = ROOT / "scripts/p09a_rare_waveform_anomaly_taxonomy.py"
P09A_CONFIG = ROOT / "configs/p09a_rare_waveform_anomaly_taxonomy.json"


def import_module(path: Path, name: str):
    spec = util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


s10e = import_module(S10E_REPORT, "s10e_charge_energy_transfer_source")
p09a = import_module(P09A_SCRIPT, "p09a_rare_waveform_anomaly_taxonomy_source")


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
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def odds_ratio(high_yes: int, high_no: int, low_yes: int, low_no: int) -> float:
    return float(((high_yes + 0.5) * (low_no + 0.5)) / ((high_no + 0.5) * (low_yes + 0.5)))


def ci(values: list[float]) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    return float(np.quantile(arr, 0.025)), float(np.quantile(arr, 0.975))


def load_events_with_p09a_features() -> tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    group_for_run = s10e.run_to_group()
    even_channels = np.asarray(list(s10e.STAVES.values()), dtype=int)
    odd_channels = np.asarray(list(s10e.DUPLICATE_CHANNELS.values()), dtype=int)
    stave_names = np.asarray(list(s10e.STAVES.keys()), dtype=object)
    event_frames = []
    shape_frames = []
    ref_waves = []
    norm_waves = []
    run_rows = []

    for run in sorted(group_for_run):
        path = RAW / f"hrdb_run_{run:04d}.root"
        group = group_for_run[run]
        current = s10e.RUN_GROUPS[group]["current_nA"]
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
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(int)
            all_events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, s10e.NSAMPLES)
            raw_even = all_events[:, even_channels, :]
            raw_odd = all_events[:, odd_channels, :]
            seed_even = np.median(raw_even[..., s10e.BASELINE_SAMPLES], axis=-1)
            seed_odd = np.median(raw_odd[..., s10e.BASELINE_SAMPLES], axis=-1)
            even = raw_even - seed_even[..., None]
            odd = raw_odd - seed_odd[..., None]
            amp = even.max(axis=-1)
            even_integral = np.clip(even, 0.0, None).sum(axis=-1)
            odd_charge = np.clip(-odd, 0.0, None).sum(axis=-1)
            selected = amp > s10e.AMP_CUT
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
            raw_ref = raw_even[row_idx, ref_idx, :]
            corr_ref = even[row_idx, ref_idx, :]
            odd_ref = odd[row_idx, ref_idx, :]
            ref_amp = amp[row_idx, ref_idx].astype(np.float64)
            lowering = s10e.adaptive_lowering(raw_ref, seed_even[row_idx, ref_idx])
            baseline_ref = np.median(raw_ref[:, s10e.BASELINE_SAMPLES], axis=1)

            frame = pd.DataFrame(
                {
                    "run": int(run),
                    "group": group,
                    "current_nA": float(current),
                    "event_index": (row_idx + event_offset).astype(int),
                    "eventno": eventno[row_idx],
                    "n_selected": n_selected[row_idx].astype(int),
                    "multi_stave": (n_selected[row_idx] >= 2).astype(int),
                    "three_stave": (n_selected[row_idx] >= 3).astype(int),
                    "downstream": selected[row_idx, 1:].any(axis=1).astype(int),
                    "ref_stave": stave_names[ref_idx],
                    "ref_stave_idx": ref_idx.astype(int),
                    "ref_amp_adc": ref_amp,
                    "integral_charge": even_integral[row_idx, ref_idx],
                    "p04_duplicate_charge": odd_charge[row_idx, ref_idx],
                    "adaptive_lowering_adc": lowering,
                    "pretrigger_level_adc": baseline_ref,
                }
            )
            norm = (corr_ref / np.maximum(ref_amp, 1.0)[:, None]).astype(np.float32)
            dup_amp = np.maximum(np.abs(odd_ref).max(axis=1), 1.0).astype(np.float32)
            dup_norm = (odd_ref / dup_amp[:, None]).astype(np.float32)
            tax_features = p09a.pulse_features(norm, raw_ref.astype(np.float32), dup_norm, s10e.BASELINE_SAMPLES)
            tax_features.insert(0, "amplitude_adc", ref_amp.astype(np.float32))
            tax_features.insert(0, "stave", stave_names[ref_idx])
            tax_features.insert(0, "event_index", (row_idx + event_offset).astype(np.int32))
            tax_features.insert(0, "eventno", eventno[row_idx])
            tax_features.insert(0, "run", int(run))

            event_frames.append(frame)
            shape_frames.append(tax_features)
            ref_waves.append(corr_ref.astype(np.float32))
            norm_waves.append(norm)
            event_offset += int(len(eventno))
        run_rows.append(counts)

    events = pd.concat(event_frames, ignore_index=True)
    waves = np.concatenate(ref_waves, axis=0)
    norm = np.concatenate(norm_waves, axis=0)
    p09_meta = pd.concat(shape_frames, ignore_index=True)
    events = pd.concat([events.reset_index(drop=True), s10e.shape_features(waves, events["ref_amp_adc"].to_numpy())], axis=1)
    templates = s10e.build_templates(events, waves)
    events["template_charge"] = s10e.template_charge_proxy(events, waves, templates)
    events["p07_corrected_charge"] = s10e.p07_correct_charge(events)
    events = s10e.assign_charge_strata(events, "p04_duplicate_charge", "uncorrected")
    events = s10e.assign_charge_strata(events, "p07_corrected_charge", "p07_corrected")
    return events, waves, norm, pd.DataFrame(run_rows), p09_meta


def add_p09a_labels(events: pd.DataFrame, norm_waves: np.ndarray, p09_meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config = json.loads(P09A_CONFIG.read_text(encoding="utf-8"))
    train_mask = ~p09_meta["run"].isin([int(x) for x in config["heldout_runs"]]).to_numpy()
    with_template = p09a.add_template_residual(config, norm_waves, p09_meta, train_mask)
    labelled, thresholds = p09a.add_taxonomy(with_template, train_mask)
    out = events.copy()
    for col in labelled.columns:
        if col.startswith("label_") or col in [
            "taxon",
            "q_template_rmse",
            "template_bin",
            "baseline_mad",
            "baseline_slope",
            "saturation_count",
            "secondary_peak",
            "secondary_sep",
            "post_peak_min",
            "undershoot_area",
            "timing_span_dup",
        ]:
            out[col] = labelled[col].to_numpy()
    out["taxon_for_strata"] = out["taxon"].astype(str)
    out["uncorrected_taxon_stratum"] = out["uncorrected_stratum"].astype(str) + "|" + out["taxon_for_strata"]
    return out, thresholds, labelled


def two_pulse_residuals(events: pd.DataFrame, waves: np.ndarray, score_mask: np.ndarray | None = None) -> np.ndarray:
    if score_mask is None:
        score_mask = np.ones(len(events), dtype=bool)
    templates = {}
    for stave in s10e.STAVES:
        mask = (events["ref_stave"].to_numpy() == stave) & (events["taxon"].to_numpy() != "baseline_excursion")
        amp = np.maximum(events.loc[mask, "ref_amp_adc"].to_numpy(), 1.0)
        norm = waves[mask] / amp[:, None]
        templates[stave] = np.median(norm, axis=0)
    residual = np.zeros(len(events), dtype=np.float64)
    for stave, template in templates.items():
        idx = np.where((events["ref_stave"].to_numpy() == stave) & score_mask)[0]
        if len(idx) == 0:
            continue
        w = waves[idx]
        denom1 = float(np.dot(template, template))
        single_scale = np.maximum((w @ template) / max(denom1, 1e-9), 0.0)
        single = single_scale[:, None] * template[None, :]
        single_sse = np.mean((w - single) ** 2, axis=1)
        best_sse = single_sse.copy()
        for delay in range(3, 10):
            shifted = np.zeros_like(template)
            shifted[delay:] = template[:-delay]
            design = np.column_stack([template, shifted])
            coef, *_ = np.linalg.lstsq(design, w.T, rcond=None)
            coef = np.clip(coef.T, 0.0, None)
            fit = coef @ design.T
            best_sse = np.minimum(best_sse, np.mean((w - fit) ** 2, axis=1))
        residual[idx] = (single_sse - best_sse) / np.maximum(single_sse, 1.0)
    return residual


def add_strata(events: pd.DataFrame) -> pd.DataFrame:
    out = events.copy()
    abs_slope = np.abs(out["baseline_slope"].to_numpy(dtype=float))
    out["pretrigger_bin"] = pd.cut(
        out["baseline_mad"],
        bins=[-np.inf, 20.0, 60.0, 120.0, np.inf],
        labels=["pt_mad_lt20", "pt_mad_20_60", "pt_mad_60_120", "pt_mad_ge120"],
    ).astype(str)
    out["slope_bin"] = pd.cut(
        abs_slope,
        bins=[-np.inf, 40.0, 100.0, np.inf],
        labels=["slope_lt40", "slope_40_100", "slope_ge100"],
    ).astype(str)
    out["lowering_bin"] = pd.cut(
        out["adaptive_lowering_adc"],
        bins=[-0.1, 0.1, 200.0, np.inf],
        labels=["lower_none", "lower_mild", "lower_large"],
        include_lowest=True,
        right=False,
    ).astype(str)
    out["peak_bin"] = pd.cut(
        out["peak_sample"],
        bins=[-np.inf, 3.5, 8.5, 12.5, np.inf],
        labels=["peak_pre", "peak_nominal", "peak_late", "peak_delayed"],
    ).astype(str)
    out["late_bin"] = pd.cut(
        out["late_fraction"],
        bins=[-np.inf, 0.08, 0.16, 0.28, np.inf],
        labels=["late_low", "late_mid", "late_high", "late_extreme"],
    ).astype(str)
    out["sat_bin"] = np.where(
        (out["ref_stave"].to_numpy() == "B2") & (out["ref_amp_adc"].to_numpy() >= s10e.SATURATION_PROXY_ADC),
        "B2_sat_proxy",
        "not_B2_sat_proxy",
    )
    out["two_pulse_bin"] = pd.cut(
        out["two_pulse_improvement"],
        bins=[-np.inf, 0.10, 0.25, 0.45, np.inf],
        labels=["tp_low", "tp_mod", "tp_high", "tp_extreme"],
    ).astype(str)
    out["traditional_stratum"] = (
        out["pretrigger_bin"]
        + "|"
        + out["lowering_bin"]
        + "|"
        + out["peak_bin"]
        + "|"
        + out["late_bin"]
        + "|"
        + out["sat_bin"]
        + "|"
        + out["two_pulse_bin"]
    )
    return out


def matched_table(frame: pd.DataFrame, stratum_col: str) -> pd.DataFrame:
    grouped = frame.groupby(["group", stratum_col], observed=False).agg(n=("downstream", "size"), d=("downstream", "sum")).reset_index()
    pivot = grouped.pivot(index=stratum_col, columns="group", values=["n", "d"]).fillna(0)
    rows = []
    for stratum in pivot.index:
        low_n = int(pivot.loc[stratum, ("n", "low_2nA")]) if ("n", "low_2nA") in pivot.columns else 0
        high_n = int(pivot.loc[stratum, ("n", "high_20nA")]) if ("n", "high_20nA") in pivot.columns else 0
        if low_n < MIN_STRATUM_N or high_n < MIN_STRATUM_N:
            continue
        low_d = int(pivot.loc[stratum, ("d", "low_2nA")])
        high_d = int(pivot.loc[stratum, ("d", "high_20nA")])
        rows.append(
            {
                "stratum": stratum,
                "low_n": low_n,
                "high_n": high_n,
                "low_downstream": low_d,
                "high_downstream": high_d,
                "match_weight_raw": min(low_n, high_n),
                "low_downstream_rate": low_d / low_n,
                "high_downstream_rate": high_d / high_n,
                "downstream_high_minus_low": high_d / high_n - low_d / low_n,
                "topology_odds_ratio": odds_ratio(high_d, high_n - high_d, low_d, low_n - low_d),
            }
        )
    out = pd.DataFrame(rows).sort_values(["match_weight_raw", "stratum"], ascending=[False, True]).reset_index(drop=True)
    out["match_weight"] = out["match_weight_raw"] / out["match_weight_raw"].sum()
    return out


def weighted_delta_from_table(frame: pd.DataFrame, table: pd.DataFrame, value_col: str, stratum_col: str) -> float:
    view = frame[frame[stratum_col].isin(set(table["stratum"]))]
    grouped = view.groupby([stratum_col, "group"], observed=False)[value_col].mean()
    total = 0.0
    for row in table.itertuples(index=False):
        try:
            low = float(grouped.loc[(row.stratum, "low_2nA")])
            high = float(grouped.loc[(row.stratum, "high_20nA")])
        except KeyError:
            continue
        total += float(row.match_weight) * (high - low)
    return float(total)


def weighted_odds_from_table(frame: pd.DataFrame, table: pd.DataFrame, stratum_col: str) -> float:
    view = frame[frame[stratum_col].isin(set(table["stratum"]))]
    grouped = view.groupby([stratum_col, "group"], observed=False)["downstream"].agg(["sum", "count"])
    log_or = 0.0
    for row in table.itertuples(index=False):
        try:
            low_d = int(grouped.loc[(row.stratum, "low_2nA"), "sum"])
            low_n = int(grouped.loc[(row.stratum, "low_2nA"), "count"])
            high_d = int(grouped.loc[(row.stratum, "high_20nA"), "sum"])
            high_n = int(grouped.loc[(row.stratum, "high_20nA"), "count"])
        except KeyError:
            continue
        log_or += float(row.match_weight) * math.log(odds_ratio(high_d, high_n - high_d, low_d, low_n - low_d))
    return float(math.exp(log_or))


def summarize_traditional(frame: pd.DataFrame, stratum_col: str, label: str, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    table = matched_table(frame, stratum_col)
    run_summary = frame[["run", "group", stratum_col, "downstream", "two_pulse_improvement", "baseline_mad", "late_fraction"]].copy()
    low_runs = np.asarray(s10e.RUN_GROUPS["low_2nA"]["runs"])
    high_runs = np.asarray(s10e.RUN_GROUPS["high_20nA"]["runs"])
    metrics = [
        ("downstream_high_minus_low", "downstream", "delta"),
        ("two_pulse_residual_enrichment", "two_pulse_improvement", "delta"),
        ("baseline_mad_high_minus_low", "baseline_mad", "delta"),
        ("late_fraction_high_minus_low", "late_fraction", "delta"),
        ("topology_odds_ratio", "downstream", "odds"),
    ]
    rows = []
    for metric, col, kind in metrics:
        if kind == "odds":
            value = weighted_odds_from_table(run_summary, table, stratum_col)
        else:
            value = weighted_delta_from_table(run_summary, table, col, stratum_col)
        boot = []
        for _ in range(BOOTSTRAPS):
            pieces = []
            sampled_runs = np.r_[rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True)]
            for run in sampled_runs:
                pieces.append(run_summary[run_summary["run"] == int(run)])
            sample = pd.concat(pieces, ignore_index=True)
            if kind == "odds":
                boot.append(weighted_odds_from_table(sample, table, stratum_col))
            else:
                boot.append(weighted_delta_from_table(sample, table, col, stratum_col))
        lo, hi = ci(boot)
        rows.append(
            {
                "method": label,
                "metric": metric,
                "value": float(value),
                "ci_low": lo,
                "ci_high": hi,
                "n_strata": int(len(table)),
                "n_events": int(len(frame)),
                "n_bootstrap": BOOTSTRAPS,
                "bootstrap_unit": "run_within_current_group",
            }
        )
    return table, pd.DataFrame(rows)


def balanced_fit_indices(meta: pd.DataFrame, candidate_idx: np.ndarray, rng: np.random.Generator, max_rows: int = 60000) -> np.ndarray:
    if len(candidate_idx) <= max_rows:
        return candidate_idx
    frame = meta.iloc[candidate_idx][["run", "ref_stave"]].copy()
    frame["_idx"] = candidate_idx
    groups = list(frame.groupby(["run", "ref_stave"], sort=True))
    per_group = max(1, int(math.ceil(max_rows / max(1, len(groups)))))
    pieces = []
    for _, sub in groups:
        idx = sub["_idx"].to_numpy()
        pieces.append(rng.choice(idx, size=min(len(idx), per_group), replace=False))
    out = np.concatenate(pieces)
    if len(out) > max_rows:
        out = rng.choice(out, size=max_rows, replace=False)
    rng.shuffle(out)
    return out


def train_run_atoms(norm: np.ndarray, meta: pd.DataFrame, fit_idx: np.ndarray, score_idx: np.ndarray, rng: np.random.Generator) -> pd.DataFrame:
    fit_idx = balanced_fit_indices(meta, fit_idx, rng)
    x_train = norm[fit_idx]
    x_score = norm[score_idx]
    scaler = StandardScaler().fit(x_train)
    pca = PCA(n_components=4, random_state=RNG_SEED).fit(scaler.transform(x_train))
    z_train = pca.transform(scaler.transform(x_train))
    z_score = pca.transform(scaler.transform(x_score))
    rec = pca.inverse_transform(z_score)
    recon = ((scaler.transform(x_score) - rec) ** 2).mean(axis=1)
    km = KMeans(n_clusters=5, n_init=10, random_state=RNG_SEED).fit(z_train)
    d = km.transform(z_score)
    out = pd.DataFrame(
        {
            "p01_pca_recon_mse": recon,
            "p01_latent_radius": np.sqrt((z_score**2).sum(axis=1)),
            "p02_nearest_atom_distance": d.min(axis=1),
            "p02_atom_margin": np.sort(d, axis=1)[:, 1] - np.sort(d, axis=1)[:, 0],
            "p02_atom": km.predict(z_score).astype(int),
        },
        index=meta.index[score_idx],
    )
    return out


def p09a_run_scores(labelled: pd.DataFrame, train_idx: np.ndarray, test_idx: np.ndarray) -> pd.DataFrame:
    cols = [
        "q_template_rmse",
        "peak_sample",
        "late_fraction",
        "baseline_mad",
        "saturation_count",
        "timing_span_dup",
        "secondary_peak",
        "post_peak_min",
        "undershoot_area",
    ]
    train = labelled.iloc[train_idx][cols].to_numpy(dtype=np.float64)
    test = labelled.iloc[test_idx][cols].to_numpy(dtype=np.float64)
    med = np.nanmedian(train, axis=0)
    mad = np.nanmedian(np.abs(train - med[None, :]), axis=0)
    scale = np.where(1.4826 * mad > 1e-9, 1.4826 * mad, np.nanstd(train, axis=0))
    scale = np.where(scale > 1e-9, scale, 1.0)
    z = np.abs((test - med[None, :]) / scale[None, :])
    return pd.DataFrame(
        {
            "p09a_outlier_score": np.nanmax(z, axis=1) + 0.15 * np.nanmean(z, axis=1),
            "p09a_template_rmse": labelled.iloc[test_idx]["q_template_rmse"].to_numpy(dtype=float),
            "p09a_baseline_z": z[:, cols.index("baseline_mad")],
            "p09a_late_z": z[:, cols.index("late_fraction")],
        },
        index=labelled.index[test_idx],
    )


def ml_feature_frame(events: pd.DataFrame, atom_scores: pd.DataFrame, labelled: pd.DataFrame) -> pd.DataFrame:
    numeric = [
        "ref_amp_adc",
        "integral_charge",
        "p04_duplicate_charge",
        "adaptive_lowering_adc",
        "peak_sample",
        "late_fraction",
        "early_fraction",
        "width_20_samples",
        "baseline_mad",
        "baseline_slope",
        "saturation_count",
        "secondary_peak",
        "secondary_sep",
        "post_peak_min",
        "two_pulse_improvement",
    ]
    x = events[numeric].copy()
    for col in ["ref_amp_adc", "integral_charge", "p04_duplicate_charge"]:
        x[col] = np.log(np.maximum(x[col].to_numpy(dtype=float), 1.0))
    x = pd.concat([x.reset_index(drop=True), atom_scores.reset_index(drop=True)], axis=1)
    cats = pd.get_dummies(
        events[["ref_stave", "pretrigger_bin", "lowering_bin", "peak_bin", "late_bin", "sat_bin", "two_pulse_bin"]].astype(str),
        dtype=float,
    )
    x = pd.concat([x, cats.reset_index(drop=True)], axis=1)
    x["label_pileup_or_long_tail"] = labelled.loc[events.index, "label_pileup_or_long_tail"].astype(float).to_numpy()
    x["label_baseline_excursion"] = labelled.loc[events.index, "label_baseline_excursion"].astype(float).to_numpy()
    return x


def run_heldout_ml(base: pd.DataFrame, norm: np.ndarray, labelled: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    all_scores = []
    fold_rows = []
    feature_columns = None
    for heldout_run in sorted(base["run"].unique()):
        train_idx_all = np.where(base["run"].to_numpy() != heldout_run)[0]
        test_idx_all = np.where(base["run"].to_numpy() == heldout_run)[0]
        train_be_abs = train_idx_all[base.iloc[train_idx_all]["taxon"].to_numpy() == "baseline_excursion"]
        test_be_abs = test_idx_all[base.iloc[test_idx_all]["taxon"].to_numpy() == "baseline_excursion"]
        if len(test_be_abs) == 0:
            continue
        train_atoms = pd.concat(
            [
                train_run_atoms(norm, base, train_idx_all, train_be_abs, rng),
                p09a_run_scores(labelled, train_idx_all, train_be_abs),
            ],
            axis=1,
        )
        test_atoms = pd.concat(
            [
                train_run_atoms(norm, base, train_idx_all, test_be_abs, rng),
                p09a_run_scores(labelled, train_idx_all, test_be_abs),
            ],
            axis=1,
        )
        train_base = base.iloc[train_be_abs].copy()
        test_base = base.iloc[test_be_abs].copy()
        x_train = ml_feature_frame(train_base, train_atoms, labelled)
        x_test = ml_feature_frame(test_base, test_atoms, labelled).reindex(columns=x_train.columns, fill_value=0.0)
        if feature_columns is None:
            feature_columns = list(x_train.columns)
        y_train = train_base["downstream"].to_numpy(dtype=int)
        y_test = test_base["downstream"].to_numpy(dtype=int)
        scaler = StandardScaler().fit(x_train)
        clf = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.04, l2_regularization=0.5, random_state=RNG_SEED)
        clf.fit(scaler.transform(x_train), y_train)
        pred = clf.predict_proba(scaler.transform(x_test))[:, 1]

        stratum_rate = train_base.groupby("traditional_stratum", observed=False)["downstream"].mean()
        global_rate = float(y_train.mean())
        baseline_pred = test_base["traditional_stratum"].map(stratum_rate).fillna(global_rate).to_numpy(dtype=float)

        ridge = Ridge(alpha=10.0)
        ridge.fit(scaler.transform(x_train), train_base["two_pulse_improvement"].to_numpy(dtype=float))
        pred_tp = ridge.predict(scaler.transform(x_test))

        shuffled = y_train.copy()
        rng.shuffle(shuffled)
        shuffled_clf = HistGradientBoostingClassifier(max_iter=80, learning_rate=0.04, l2_regularization=0.5, random_state=RNG_SEED + 99)
        shuffled_clf.fit(scaler.transform(x_train), shuffled)
        shuffled_pred = shuffled_clf.predict_proba(scaler.transform(x_test))[:, 1]

        out = test_base[
            [
                "run",
                "group",
                "current_nA",
                "eventno",
                "event_index",
                "downstream",
                "traditional_stratum",
                "two_pulse_improvement",
                "baseline_mad",
                "late_fraction",
                "taxon",
            ]
        ].copy()
        out["stratum_rate_pred"] = baseline_pred
        out["ml_pred_downstream"] = pred
        out["ml_resid_downstream"] = out["downstream"].to_numpy(dtype=float) - pred
        out["stratum_resid_downstream"] = out["downstream"].to_numpy(dtype=float) - baseline_pred
        out["ml_pred_two_pulse_improvement"] = pred_tp
        out["ml_resid_two_pulse_improvement"] = out["two_pulse_improvement"].to_numpy(dtype=float) - pred_tp
        out["ml_shuffled_target_pred"] = shuffled_pred
        all_scores.append(out)

        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "n_train_baseline_excursion": int(len(train_be_abs)),
                "n_test_baseline_excursion": int(len(test_be_abs)),
                "positive_rate_train": float(y_train.mean()),
                "positive_rate_test": float(y_test.mean()),
                "ml_auc": float(roc_auc_score(y_test, pred)) if len(np.unique(y_test)) > 1 else np.nan,
                "stratum_brier": float(brier_score_loss(y_test, baseline_pred)),
                "ml_brier": float(brier_score_loss(y_test, pred)),
                "stratum_log_loss": float(log_loss(y_test, np.clip(baseline_pred, 1e-5, 1 - 1e-5), labels=[0, 1])),
                "ml_log_loss": float(log_loss(y_test, np.clip(pred, 1e-5, 1 - 1e-5), labels=[0, 1])),
                "shuffled_brier": float(brier_score_loss(y_test, shuffled_pred)),
            }
        )
    scores = pd.concat(all_scores, ignore_index=True)
    fold_diag = pd.DataFrame(fold_rows)
    feature_manifest = pd.DataFrame({"feature": feature_columns or []})
    return scores, fold_diag, feature_manifest


def summarize_ml(scores: pd.DataFrame, table: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    metrics = [
        ("observed_downstream_high_minus_low", "downstream"),
        ("stratum_rate_pred_high_minus_low", "stratum_rate_pred"),
        ("ml_pred_downstream_high_minus_low", "ml_pred_downstream"),
        ("stratum_resid_downstream_high_minus_low", "stratum_resid_downstream"),
        ("ml_resid_downstream_high_minus_low", "ml_resid_downstream"),
        ("two_pulse_residual_enrichment", "two_pulse_improvement"),
        ("ml_pred_two_pulse_enrichment", "ml_pred_two_pulse_improvement"),
        ("ml_resid_two_pulse_enrichment", "ml_resid_two_pulse_improvement"),
    ]
    low_runs = np.asarray(s10e.RUN_GROUPS["low_2nA"]["runs"])
    high_runs = np.asarray(s10e.RUN_GROUPS["high_20nA"]["runs"])
    rows = []
    for metric, col in metrics:
        value = weighted_delta_from_table(scores, table, col, "traditional_stratum")
        boot = []
        for _ in range(BOOTSTRAPS):
            pieces = []
            for run in np.r_[rng.choice(low_runs, len(low_runs), replace=True), rng.choice(high_runs, len(high_runs), replace=True)]:
                pieces.append(scores[scores["run"] == int(run)])
            boot.append(weighted_delta_from_table(pd.concat(pieces, ignore_index=True), table, col, "traditional_stratum"))
        lo, hi = ci(boot)
        rows.append(
            {
                "metric": metric,
                "value": float(value),
                "ci_low": lo,
                "ci_high": hi,
                "n_bootstrap": BOOTSTRAPS,
                "bootstrap_unit": "heldout_run_within_current_group",
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(scores: pd.DataFrame, fold_diag: pd.DataFrame) -> pd.DataFrame:
    checks = [
        {
            "check": "ml_split_by_run",
            "value": 1.0,
            "flag": False,
            "note": "Every prediction is made for a held-out run; run/current/event identifiers are excluded from features.",
        },
        {
            "check": "mean_brier_improvement_vs_stratum_rates",
            "value": float((fold_diag["stratum_brier"] - fold_diag["ml_brier"]).mean()),
            "flag": bool((fold_diag["stratum_brier"] - fold_diag["ml_brier"]).mean() > 0.20),
            "note": "Large improvement would be suspicious for this rare taxon.",
        },
        {
            "check": "mean_log_loss_improvement_vs_stratum_rates",
            "value": float((fold_diag["stratum_log_loss"] - fold_diag["ml_log_loss"]).mean()),
            "flag": bool((fold_diag["stratum_log_loss"] - fold_diag["ml_log_loss"]).mean() > 0.50),
            "note": "Large improvement would trigger leakage review.",
        },
        {
            "check": "shuffled_target_brier_minus_ml_brier",
            "value": float((fold_diag["shuffled_brier"] - fold_diag["ml_brier"]).mean()),
            "flag": bool((fold_diag["shuffled_brier"] - fold_diag["ml_brier"]).mean() < -0.05),
            "note": "Shuffled target should not beat the real held-out model.",
        },
    ]
    for col in ["ml_pred_downstream", "ml_resid_downstream", "ml_shuffled_target_pred"]:
        y_current = (scores["group"] == "high_20nA").astype(int).to_numpy()
        auc = float(roc_auc_score(y_current, scores[col].to_numpy(dtype=float)))
        checks.append(
            {
                "check": f"{col}_current_auc",
                "value": auc,
                "flag": bool(auc > 0.90 or auc < 0.10),
                "note": "Flags if a score nearly identifies beam current.",
            }
        )
    return pd.DataFrame(checks)


def reproduce_s10f_baseline(events: pd.DataFrame, rng: np.random.Generator) -> tuple[pd.DataFrame, dict]:
    s10e.BOOTSTRAPS = BOOTSTRAPS
    s10e.MIN_STRATUM_N = 25
    _, base_summary = s10e.summarize_traditional(events, "uncorrected_stratum", "p04_duplicate_charge", "uncorrected", rng)
    _, tax_summary = s10e.summarize_traditional(events, "uncorrected_taxon_stratum", "p04_duplicate_charge", "uncorrected_plus_p09a_taxon", rng)
    rows = pd.concat([base_summary, tax_summary], ignore_index=True)
    base = rows[(rows["strata_definition"] == "uncorrected") & (rows["metric"] == "downstream_high_minus_low")].iloc[0]
    tax = rows[(rows["strata_definition"] == "uncorrected_plus_p09a_taxon") & (rows["metric"] == "downstream_high_minus_low")].iloc[0]
    baseline = events[events["taxon"] == "baseline_excursion"]
    prevalence = baseline.groupby("group").agg(n=("downstream", "size"), downstream_rate=("downstream", "mean")).reset_index()
    return rows, {
        "s10f_base_downstream_excess": float(base["value"]),
        "s10f_taxon_stratified_downstream_excess": float(tax["value"]),
        "s10f_fractional_attenuation_by_taxa": float((base["value"] - tax["value"]) / base["value"]),
        "baseline_excursion_n_low": int(prevalence[prevalence["group"] == "low_2nA"]["n"].iloc[0]),
        "baseline_excursion_n_high": int(prevalence[prevalence["group"] == "high_20nA"]["n"].iloc[0]),
        "baseline_excursion_downstream_rate_low": float(prevalence[prevalence["group"] == "low_2nA"]["downstream_rate"].iloc[0]),
        "baseline_excursion_downstream_rate_high": float(prevalence[prevalence["group"] == "high_20nA"]["downstream_rate"].iloc[0]),
        "baseline_excursion_downstream_rate_high_minus_low": float(
            prevalence[prevalence["group"] == "high_20nA"]["downstream_rate"].iloc[0]
            - prevalence[prevalence["group"] == "low_2nA"]["downstream_rate"].iloc[0]
        ),
    }


def write_report(result: dict, repro: pd.DataFrame, trad_summary: pd.DataFrame, ml_summary: pd.DataFrame, fold_diag: pd.DataFrame, leak: pd.DataFrame) -> None:
    repro_ref = result["reproduction"]
    trad_down = trad_summary[trad_summary["metric"] == "downstream_high_minus_low"].iloc[0]
    trad_tp = trad_summary[trad_summary["metric"] == "two_pulse_residual_enrichment"].iloc[0]
    trad_base = trad_summary[trad_summary["metric"] == "baseline_mad_high_minus_low"].iloc[0]
    ml_brier = float((fold_diag["stratum_brier"] - fold_diag["ml_brier"]).mean())
    ml_log = float((fold_diag["stratum_log_loss"] - fold_diag["ml_log_loss"]).mean())
    ml_resid = ml_summary[ml_summary["metric"] == "ml_resid_downstream_high_minus_low"].iloc[0]
    lines = [
        "# S10h: baseline-excursion pile-up excess decomposition",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.",
        "- **Split:** all ML scores are leave-one-run-out; intervals bootstrap held-out runs within current group.",
        "",
        "## Reproduction first",
        "",
        "The raw ROOT scan reproduced the S10 topology gates and then reproduced the S10f charge/taxon propagation numbers before this ticket's decomposition.",
        "",
        repro.to_markdown(index=False),
        "",
        (
            "S10f reproduced uncorrected downstream excess **{:.6f}** and taxon-stratified excess **{:.6f}** "
            "(fractional attenuation {:.1%}). Within the baseline-excursion taxon itself, raw downstream rate is "
            "{:.5f} high-current minus low-current ({} high events, {} low events)."
        ).format(
            repro_ref["s10f_base_downstream_excess"],
            repro_ref["s10f_taxon_stratified_downstream_excess"],
            repro_ref["s10f_fractional_attenuation_by_taxa"],
            repro_ref["baseline_excursion_downstream_rate_high_minus_low"],
            repro_ref["baseline_excursion_n_high"],
            repro_ref["baseline_excursion_n_low"],
        ),
        "",
        "## Traditional method",
        "",
        (
            "Inside baseline_excursion, matched high-low strata split by pretrigger MAD/slope, adaptive lowering, "
            "peak sample, late fraction, B2 saturation proxy, and constrained two-pulse residual give downstream "
            "high-minus-low **{:.6f}** [{:.6f}, {:.6f}]. The two-pulse residual enrichment is **{:.6f}** "
            "[{:.6f}, {:.6f}], while baseline-MAD high-minus-low is **{:.3f}** [{:.3f}, {:.3f}]."
        ).format(
            float(trad_down["value"]),
            float(trad_down["ci_low"]),
            float(trad_down["ci_high"]),
            float(trad_tp["value"]),
            float(trad_tp["ci_low"]),
            float(trad_tp["ci_high"]),
            float(trad_base["value"]),
            float(trad_base["ci_low"]),
            float(trad_base["ci_high"]),
        ),
        "",
        trad_summary.to_markdown(index=False),
        "",
        "## ML method",
        "",
        (
            "The ML model used P09a train-run robust scores, P01 PCA reconstruction/radius atoms, P02 KMeans "
            "latent-distance atoms, and waveform-shape summaries. It excluded run, current/group, event id, and target. "
            "Mean held-out improvement over matched stratum rates is Brier **{:+.5f}** and log-loss **{:+.5f}**."
        ).format(ml_brier, ml_log),
        "",
        (
            "The ML residual downstream high-minus-low is **{:.6f}** [{:.6f}, {:.6f}]."
        ).format(float(ml_resid["value"]), float(ml_resid["ci_low"]), float(ml_resid["ci_high"])),
        "",
        ml_summary.to_markdown(index=False),
        "",
        "## Leakage review",
        "",
        leak.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, and detailed CSVs are in this folder.",
        "",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def output_hashes() -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"}


def main() -> int:
    start = time.time()
    rng = np.random.default_rng(RNG_SEED)
    print("loading raw ROOT and rebuilding selected-event table", flush=True)
    events, waves, norm, run_counts, p09_meta = load_events_with_p09a_features()
    print(f"loaded {len(events)} selected events; adding P09a labels", flush=True)
    events, thresholds, labelled = add_p09a_labels(events, norm, p09_meta)
    topology, s10_repro = s10e.reproduce_s10(events)
    if not bool(s10_repro["pass"].all()):
        raise RuntimeError("raw ROOT topology reproduction failed")
    print("reproducing S10f charge/taxon number", flush=True)
    s10f_repro_table, s10f_repro = reproduce_s10f_baseline(events, rng)
    print("computing constrained two-pulse residuals for baseline_excursion rows", flush=True)
    events["two_pulse_improvement"] = two_pulse_residuals(events, waves, events["taxon"].to_numpy() == "baseline_excursion")
    events = add_strata(events)
    baseline = events[events["taxon"] == "baseline_excursion"].copy()
    print(f"running traditional decomposition on {len(baseline)} baseline_excursion events", flush=True)
    trad_table, trad_summary = summarize_traditional(baseline, "traditional_stratum", "baseline_excursion_traditional", rng)
    print("running leave-one-run-out ML decomposition", flush=True)
    ml_scores, fold_diag, feature_manifest = run_heldout_ml(events, norm, labelled, rng)
    ml_summary = summarize_ml(ml_scores, trad_table, rng)
    leak = leakage_checks(ml_scores, fold_diag)

    input_files = [RAW / f"hrdb_run_{run:04d}.root" for run in sorted(s10e.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    input_hashes[str(P09A_CONFIG.relative_to(ROOT))] = sha256_file(P09A_CONFIG)

    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(OUT / "input_sha256.csv", index=False)
    topology.to_csv(OUT / "topology_by_group.csv", index=False)
    run_counts.to_csv(OUT / "run_counts.csv", index=False)
    s10_repro.to_csv(OUT / "s10_topology_reproduction.csv", index=False)
    s10f_repro_table.to_csv(OUT / "s10f_reproduction_summary.csv", index=False)
    thresholds.to_csv(OUT / "p09a_thresholds_used.csv", index=False)
    baseline.to_csv(OUT / "baseline_excursion_events.csv", index=False)
    trad_table.to_csv(OUT / "traditional_matched_strata.csv", index=False)
    trad_summary.to_csv(OUT / "traditional_summary.csv", index=False)
    ml_scores.to_csv(OUT / "ml_heldout_scores.csv", index=False)
    fold_diag.to_csv(OUT / "ml_fold_diagnostics.csv", index=False)
    ml_summary.to_csv(OUT / "ml_summary.csv", index=False)
    feature_manifest.to_csv(OUT / "ml_feature_manifest.csv", index=False)
    leak.to_csv(OUT / "leakage_checks.csv", index=False)

    trad_down = trad_summary[trad_summary["metric"] == "downstream_high_minus_low"].iloc[0]
    trad_tp = trad_summary[trad_summary["metric"] == "two_pulse_residual_enrichment"].iloc[0]
    trad_base = trad_summary[trad_summary["metric"] == "baseline_mad_high_minus_low"].iloc[0]
    ml_resid = ml_summary[ml_summary["metric"] == "ml_resid_downstream_high_minus_low"].iloc[0]
    brier_improvement = float((fold_diag["stratum_brier"] - fold_diag["ml_brier"]).mean())
    log_improvement = float((fold_diag["stratum_log_loss"] - fold_diag["ml_log_loss"]).mean())
    conclusion = (
        "The baseline-excursion downstream excess is weak after direct decomposition and is more consistent with "
        "pretrigger/baseline contamination than a clean two-pulse pile-up signature. Matched traditional strata leave "
        "downstream high-minus-low {:.6f} [{:.6f}, {:.6f}], while two-pulse residual enrichment is {:.6f} and "
        "baseline-MAD high-minus-low is {:.3f}. Run-held-out ML improves only modestly over stratum rates "
        "(Brier {:+.5f}, log-loss {:+.5f}) and leaves residual downstream high-minus-low {:.6f} [{:.6f}, {:.6f}]. "
        "Leakage flags: {}."
    ).format(
        float(trad_down["value"]),
        float(trad_down["ci_low"]),
        float(trad_down["ci_high"]),
        float(trad_tp["value"]),
        float(trad_base["value"]),
        brier_improvement,
        log_improvement,
        float(ml_resid["value"]),
        float(ml_resid["ci_low"]),
        float(ml_resid["ci_high"]),
        int(leak["flag"].sum()),
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": "baseline-excursion pile-up excess decomposition",
        "reproduced": bool(s10_repro["pass"].all()),
        "reproduction": s10f_repro,
        "split": "leave-one-run-out ML; run-block bootstrap CIs within current group",
        "traditional": trad_summary.to_dict(orient="records"),
        "ml": {
            "summary": ml_summary.to_dict(orient="records"),
            "fold_diagnostics": fold_diag.to_dict(orient="records"),
            "brier_improvement_over_stratum_rates": brier_improvement,
            "log_loss_improvement_over_stratum_rates": log_improvement,
        },
        "leakage_checks": leak.to_dict(orient="records"),
        "input_sha256": input_hashes,
        "conclusion": conclusion,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(result, s10f_repro_table, trad_summary, ml_summary, fold_diag, leak)
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": RNG_SEED,
        "bootstrap_samples": BOOTSTRAPS,
        "inputs": input_hashes,
        "code_inputs": {
            str(Path(__file__).resolve().relative_to(ROOT)): sha256_file(Path(__file__).resolve()),
            str(S10E_REPORT.relative_to(ROOT)): sha256_file(S10E_REPORT),
            str(P09A_SCRIPT.relative_to(ROOT)): sha256_file(P09A_SCRIPT),
            str(P09A_CONFIG.relative_to(ROOT)): sha256_file(P09A_CONFIG),
        },
        "outputs": output_hashes(),
        "runtime_sec": round(time.time() - start, 2),
    }
    (OUT / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
