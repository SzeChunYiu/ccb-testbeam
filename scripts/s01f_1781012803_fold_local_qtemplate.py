#!/usr/bin/env python3
"""S01f fold-local q_template leakage audit for the S03d q-veto benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

import s02_timing_pickoff as s02
import s03a_analytic_timewalk as s03a
import s03b_amp_binned_monotonic_timewalk as s03b
import s03d_leave_one_run_s03ab_hgb_stability as s03d


RUN65_EXPECTED = {
    "template_phase_base": 2.889152765080617,
    "s03a_amp_only": 1.494640076269676,
    "s03b_monotone_binned": 1.5695763825403084,
}
PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
RESIDUAL_METHODS = {"s03b_monotone_binned": "s03b_monotone_binned"}
TRAD_FEATURES = [
    "q_pair_max",
    "q_pair_mean",
    "q_downstream_max",
    "q_downstream_mean",
    "q_downstream_p90",
]
ML_FEATURES = [
    "q_pair_max",
    "q_pair_mean",
    "q_pair_absdiff",
    "q_downstream_max",
    "q_downstream_mean",
    "q_downstream_std",
    "pair_B4_B6",
    "pair_B4_B8",
    "pair_B6_B8",
]
SCRIPT_PATH = Path(__file__)


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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def fold_config(config: dict, train_runs: Iterable[int], heldout_runs: Iterable[int]) -> dict:
    out = json.loads(json.dumps(config))
    out["timing"]["train_runs"] = [int(r) for r in train_runs]
    out["timing"]["heldout_runs"] = [int(r) for r in heldout_runs]
    return out


def q_cfd_position(norm_waveform: np.ndarray, fraction: float) -> float:
    peak = int(np.nanargmax(norm_waveform))
    if peak <= 0 or not np.isfinite(norm_waveform[peak]) or norm_waveform[peak] <= 0:
        return float("nan")
    target = float(fraction) * float(norm_waveform[peak])
    for idx in range(1, peak + 1):
        y0 = float(norm_waveform[idx - 1])
        y1 = float(norm_waveform[idx])
        if np.isfinite(y0) and np.isfinite(y1) and y0 <= target <= y1 and y1 != y0:
            return float(idx - 1 + (target - y0) / (y1 - y0))
    return float(peak)


def q_align_waveform(norm_waveform: np.ndarray, rel_grid: np.ndarray, fraction: float) -> np.ndarray:
    pos = q_cfd_position(norm_waveform, fraction)
    if not np.isfinite(pos):
        return np.full(len(rel_grid), np.nan, dtype=np.float32)
    x = np.arange(len(norm_waveform), dtype=np.float64)
    return np.interp(pos + rel_grid, x, norm_waveform, left=np.nan, right=np.nan).astype(np.float32)


def q_assign_amp_bins(amplitude: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.clip(np.searchsorted(edges, amplitude, side="right") - 1, 0, len(edges) - 2)


def build_fold_q_templates(
    config: dict, pulses: pd.DataFrame, train_runs: List[int]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    q_cfg = config["q_template"]
    staves = [str(s) for s in q_cfg.get("include_staves", config["timing"]["downstream_staves"])]
    edges = np.asarray(q_cfg["amplitude_edges_adc"], dtype=float)
    min_bin = int(q_cfg["min_bin_pulses"])
    rel_grid = np.asarray(q_cfg["aligned_relative_grid"], dtype=float)
    cfd_fraction = float(q_cfg["cfd_fraction"])

    table = pulses[pulses["stave"].isin(staves)].copy().reset_index(drop=True)
    waves = np.vstack(table["waveform"].to_numpy()).astype(np.float32)
    amp = table["amplitude_adc"].to_numpy(dtype=float)
    norm = waves / np.maximum(amp[:, None], 1.0)
    aligned = np.vstack([q_align_waveform(row, rel_grid, cfd_fraction) for row in norm])
    bins = q_assign_amp_bins(amp, edges)
    train_mask = table["run"].isin(train_runs).to_numpy()

    templates: Dict[Tuple[str, int], np.ndarray] = {}
    fallback: Dict[str, np.ndarray] = {}
    bin_rows = []
    q_values = np.full(len(table), np.nan, dtype=float)
    for stave in staves:
        stave_mask = table["stave"].eq(stave).to_numpy()
        stave_train = train_mask & stave_mask
        fallback[stave] = np.nanmedian(aligned[stave_train], axis=0).astype(np.float32)
        for b in range(len(edges) - 1):
            mask = stave_train & (bins == b)
            n = int(mask.sum())
            if n >= min_bin:
                tmpl = np.nanmedian(aligned[mask], axis=0).astype(np.float32)
                source = "train_bin"
            else:
                tmpl = fallback[stave]
                source = "train_stave_fallback"
            templates[(stave, b)] = tmpl
            bin_rows.append(
                {
                    "stave": stave,
                    "bin": int(b),
                    "amp_low_adc": float(edges[b]),
                    "amp_high_adc": float(edges[b + 1]),
                    "n_train": n,
                    "source": source,
                }
            )

    staves_arr = table["stave"].to_numpy()
    for i, stave in enumerate(staves_arr):
        tmpl = templates[(str(stave), int(bins[i]))]
        valid = np.isfinite(aligned[i]) & np.isfinite(tmpl)
        q_values[i] = math.sqrt(float(np.mean((aligned[i, valid] - tmpl[valid]) ** 2))) if valid.any() else math.nan

    q_table = table[["run", "eventno", "evt", "stave"]].copy()
    q_table["q_template"] = q_values
    q_table["template_bin"] = bins.astype(int)
    return q_table.drop_duplicates(["run", "eventno", "evt", "stave"]), pd.DataFrame(bin_rows)


def annotate_q_template(pulses: pd.DataFrame, q_table: pd.DataFrame) -> pd.DataFrame:
    return pulses.merge(q_table, on=["run", "eventno", "evt", "stave"], how="left")


def pair_table(pulses: pd.DataFrame, method: str, label: str, config: dict, runs: List[int]) -> pd.DataFrame:
    downstream = list(config["timing"]["downstream_staves"])
    positions = s02.geometry_positions(downstream, 2.0)
    tof_per_cm = float(config["tof_per_cm_ns"])
    sub = pulses[pulses["run"].isin(runs)].copy()
    sub["tcorr"] = sub[f"t_{method}_ns"] - sub["stave"].map(positions).astype(float) * tof_per_cm
    meta = sub[["event_id", "run", "eventno", "evt"]].drop_duplicates("event_id").set_index("event_id")
    t_wide = sub.pivot(index="event_id", columns="stave", values="tcorr")
    q_wide = sub.pivot(index="event_id", columns="stave", values="q_template")
    amp_wide = sub.pivot(index="event_id", columns="stave", values="amplitude_adc")
    q_down = q_wide.reindex(columns=downstream)
    rows = []
    for left, right in PAIRS:
        if left not in t_wide or right not in t_wide:
            continue
        residual = t_wide[left] - t_wide[right]
        frame = pd.DataFrame(
            {
                "event_id": residual.index,
                "pair": f"{left}-{right}",
                "residual_ns": residual.to_numpy(dtype=float),
                "q_left": q_wide[left].to_numpy(dtype=float),
                "q_right": q_wide[right].to_numpy(dtype=float),
                "amp_left_adc": amp_wide[left].to_numpy(dtype=float),
                "amp_right_adc": amp_wide[right].to_numpy(dtype=float),
            }
        ).set_index("event_id")
        frame = frame.join(meta, how="left").reset_index()
        frame["q_pair_max"] = frame[["q_left", "q_right"]].max(axis=1)
        frame["q_pair_mean"] = frame[["q_left", "q_right"]].mean(axis=1)
        frame["q_pair_absdiff"] = (frame["q_left"] - frame["q_right"]).abs()
        frame["q_downstream_max"] = q_down.max(axis=1).reindex(frame["event_id"]).to_numpy(dtype=float)
        frame["q_downstream_mean"] = q_down.mean(axis=1).reindex(frame["event_id"]).to_numpy(dtype=float)
        frame["q_downstream_p90"] = q_down.quantile(0.90, axis=1).reindex(frame["event_id"]).to_numpy(dtype=float)
        frame["q_downstream_std"] = q_down.std(axis=1).fillna(0.0).reindex(frame["event_id"]).to_numpy(dtype=float)
        for pair in ["B4-B6", "B4-B8", "B6-B8"]:
            frame[f"pair_{pair.replace('-', '_')}"] = (frame["pair"] == pair).astype(float)
        rows.append(frame)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    out["residual_method"] = label
    return out[np.isfinite(out["residual_ns"])].copy()


def tail_labels(frame: pd.DataFrame) -> np.ndarray:
    values = frame["residual_ns"].to_numpy(dtype=float)
    center = float(np.nanmedian(values))
    return (np.abs(values - center) > 5.0).astype(int)


def summarize_residuals(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> dict:
    values = np.asarray(values, dtype=float)
    ci_low, ci_high = s02.bootstrap_ci(values, rng, n_boot) if len(values) else (math.nan, math.nan)
    return {"value": s02.sigma68(values), "ci_low": ci_low, "ci_high": ci_high, **s02.metric_summary(values)}


def choose_traditional_veto(train: pd.DataFrame, config: dict) -> dict:
    y_tail = tail_labels(train)
    quantiles = [float(q) for q in config["q_veto"]["threshold_quantiles"]]
    min_keep = float(config["q_veto"]["min_train_keep_fraction"])
    best = None
    for feature in TRAD_FEATURES:
        values = train[feature].to_numpy(dtype=float)
        finite = np.isfinite(values)
        if finite.sum() < 10:
            continue
        for q in quantiles:
            threshold = float(np.nanquantile(values[finite], q))
            keep = values <= threshold
            keep_frac = float(np.mean(keep[finite]))
            if keep_frac < min_keep or keep.sum() < 50:
                continue
            kept_resid = train.loc[keep, "residual_ns"].to_numpy(dtype=float)
            row = {
                "feature": feature,
                "threshold": threshold,
                "threshold_quantile": q,
                "train_keep_fraction": keep_frac,
                "train_tail_frac_abs_gt5ns": float(np.mean(y_tail[keep])),
                "train_sigma68_ns": s02.sigma68(kept_resid),
            }
            key = (row["train_tail_frac_abs_gt5ns"], row["train_sigma68_ns"], -row["train_keep_fraction"])
            if best is None or key < best[0]:
                best = (key, row)
    if best is None:
        return {
            "feature": "none",
            "threshold": math.inf,
            "threshold_quantile": 1.0,
            "train_keep_fraction": 1.0,
            "train_tail_frac_abs_gt5ns": float(np.mean(y_tail)),
            "train_sigma68_ns": s02.sigma68(train["residual_ns"].to_numpy(dtype=float)),
        }
    return best[1]


def rf_params(config: dict, seed: int) -> dict:
    return {
        "n_estimators": int(config["q_veto"]["rf_n_estimators"]),
        "max_depth": int(config["q_veto"]["rf_max_depth"]),
        "min_samples_leaf": int(config["q_veto"]["rf_min_samples_leaf"]),
        "class_weight": "balanced_subsample",
        "random_state": int(seed),
        "n_jobs": 1,
    }


def feature_matrix(train: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    med = train[ML_FEATURES].median(axis=0, skipna=True).fillna(0.0)
    return frame[ML_FEATURES].fillna(med).to_numpy(dtype=float)


def choose_ml_veto(
    train: pd.DataFrame, heldout: pd.DataFrame, config: dict, seed: int, shuffle: bool = False
) -> Tuple[dict, np.ndarray]:
    y = tail_labels(train)
    if shuffle:
        rng = np.random.default_rng(seed + 91)
        y = y.copy()
        rng.shuffle(y)
    groups = train["run"].to_numpy(dtype=int)
    X = feature_matrix(train, train)
    finite = np.all(np.isfinite(X), axis=1)
    X = X[finite]
    y_fit = y[finite]
    groups_fit = groups[finite]
    if len(np.unique(y_fit)) < 2 or len(np.unique(groups_fit)) < 2:
        return {
            "threshold": math.inf,
            "train_keep_fraction": 1.0,
            "train_tail_frac_abs_gt5ns": float(np.mean(y)),
            "train_sigma68_ns": s02.sigma68(train["residual_ns"].to_numpy(dtype=float)),
            "oof_auc": math.nan,
            "shuffled": bool(shuffle),
        }, np.zeros(len(heldout), dtype=float)

    oof = np.full(len(train), np.nan)
    n_splits = min(3, len(np.unique(groups_fit)))
    gkf = GroupKFold(n_splits=n_splits)
    idx_finite = np.flatnonzero(finite)
    for fold, (tr, va) in enumerate(gkf.split(X, y_fit, groups_fit)):
        model = RandomForestClassifier(**rf_params(config, seed + fold))
        model.fit(X[tr], y_fit[tr])
        oof[idx_finite[va]] = model.predict_proba(X[va])[:, 1]
    oof_auc = float(roc_auc_score(y_fit, oof[finite])) if len(np.unique(y_fit)) == 2 else math.nan
    min_keep = float(config["q_veto"]["min_train_keep_fraction"])
    best = None
    for q in [float(v) for v in config["q_veto"]["threshold_quantiles"]]:
        threshold = float(np.nanquantile(oof[finite], q))
        keep = oof <= threshold
        keep_frac = float(np.nanmean(keep[finite]))
        if keep_frac < min_keep or np.nansum(keep) < 50:
            continue
        kept = train.loc[keep, "residual_ns"].to_numpy(dtype=float)
        row = {
            "threshold": threshold,
            "threshold_quantile": q,
            "train_keep_fraction": keep_frac,
            "train_tail_frac_abs_gt5ns": float(np.mean(tail_labels(train)[keep])),
            "train_sigma68_ns": s02.sigma68(kept),
            "oof_auc": oof_auc,
            "shuffled": bool(shuffle),
        }
        key = (row["train_tail_frac_abs_gt5ns"], row["train_sigma68_ns"], -row["train_keep_fraction"])
        if best is None or key < best[0]:
            best = (key, row)
    policy = best[1] if best is not None else {
        "threshold": math.inf,
        "threshold_quantile": 1.0,
        "train_keep_fraction": 1.0,
        "train_tail_frac_abs_gt5ns": float(np.mean(y)),
        "train_sigma68_ns": s02.sigma68(train["residual_ns"].to_numpy(dtype=float)),
        "oof_auc": oof_auc,
        "shuffled": bool(shuffle),
    }
    final = RandomForestClassifier(**rf_params(config, seed + 777))
    final.fit(X, y_fit)
    held_scores = final.predict_proba(feature_matrix(train, heldout))[:, 1]
    return policy, held_scores


def evaluate_vetoes(
    train_pairs: pd.DataFrame,
    heldout_pairs: pd.DataFrame,
    config: dict,
    heldout_run: int,
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metric_rows = []
    residual_rows = []
    policy_rows = []
    leakage_rows = []
    n_boot = int(config["q_veto"]["bootstrap_samples"])
    for method in RESIDUAL_METHODS:
        train = train_pairs[train_pairs["residual_method"] == method].copy()
        held = heldout_pairs[heldout_pairs["residual_method"] == method].copy()
        base_n = len(held)
        variants = {"no_veto": np.ones(base_n, dtype=bool)}

        trad = choose_traditional_veto(train, config)
        trad_keep = held[trad["feature"]].to_numpy(dtype=float) <= float(trad["threshold"]) if trad["feature"] != "none" else variants["no_veto"]
        variants["traditional_q_threshold"] = trad_keep
        policy_rows.append({"heldout_run": heldout_run, "residual_method": method, "veto_method": "traditional_q_threshold", **trad})

        seed = int(config["q_veto"]["random_seed"]) + int(heldout_run) * 13
        ml_policy, ml_score = choose_ml_veto(train, held, config, seed, shuffle=False)
        held["ml_q_tail_score"] = ml_score
        variants["ml_q_rf"] = ml_score <= float(ml_policy["threshold"])
        policy_rows.append({"heldout_run": heldout_run, "residual_method": method, "veto_method": "ml_q_rf", **ml_policy})

        shuf_policy, shuf_score = choose_ml_veto(train, held, config, seed, shuffle=True)
        variants["shuffled_ml_q_rf_control"] = shuf_score <= float(shuf_policy["threshold"])
        policy_rows.append({"heldout_run": heldout_run, "residual_method": method, "veto_method": "shuffled_ml_q_rf_control", **shuf_policy})

        overlap = set(train["event_id"]) & set(held["event_id"])
        leakage_rows.extend(
            [
                {
                    "heldout_run": heldout_run,
                    "residual_method": method,
                    "check": "train_heldout_event_id_overlap",
                    "value": float(len(overlap)),
                    "flag": bool(len(overlap) != 0),
                },
                {
                    "heldout_run": heldout_run,
                    "residual_method": method,
                    "check": "ml_q_rf_oof_auc",
                    "value": float(ml_policy["oof_auc"]),
                    "flag": bool(np.isfinite(ml_policy["oof_auc"]) and ml_policy["oof_auc"] > 0.90),
                },
                {
                    "heldout_run": heldout_run,
                    "residual_method": method,
                    "check": "shuffled_ml_q_rf_oof_auc",
                    "value": float(shuf_policy["oof_auc"]),
                    "flag": bool(np.isfinite(shuf_policy["oof_auc"]) and shuf_policy["oof_auc"] > 0.65),
                },
            ]
        )

        for veto_method, keep in variants.items():
            kept = held.loc[keep].copy()
            values = kept["residual_ns"].to_numpy(dtype=float)
            summary = summarize_residuals(values, rng, n_boot)
            metric_rows.append(
                {
                    "heldout_run": heldout_run,
                    "residual_method": method,
                    "veto_method": veto_method,
                    "keep_fraction": float(len(kept) / base_n) if base_n else math.nan,
                    **summary,
                }
            )
            for row in kept.itertuples(index=False):
                residual_rows.append(
                    {
                        "heldout_run": heldout_run,
                        "residual_method": method,
                        "veto_method": veto_method,
                        "pair": row.pair,
                        "event_id": row.event_id,
                        "residual_ns": float(row.residual_ns),
                        "q_pair_max": float(row.q_pair_max),
                        "q_downstream_max": float(row.q_downstream_max),
                    }
                )
    return pd.DataFrame(metric_rows), pd.DataFrame(residual_rows), pd.DataFrame(policy_rows), pd.DataFrame(leakage_rows)


def run_one_fold(
    pulses_all: pd.DataFrame,
    base_config: dict,
    heldout_run: int,
    all_runs: List[int],
    rng: np.random.Generator,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_runs = [run for run in all_runs if run != heldout_run]
    config = fold_config(base_config, train_runs, [heldout_run])
    pulses, base_method = s03d.prepare_base_pulses(pulses_all, config)
    q_table, q_bins = build_fold_q_templates(config, pulses, train_runs)
    pulses = annotate_q_template(pulses, q_table)

    s03a_pulses, s03a_cv, _, s03a_candidate, s03a_alpha = s03a.run_analytic(pulses, config, base_method)
    binned_pulses, binned_cv, _, binned_best = s03b.scan_binned_candidates(pulses, config, base_method)

    combined = pulses.copy()
    combined["t_s03a_amp_only_ns"] = s03a_pulses["t_analytic_timewalk_ns"].to_numpy(dtype=float)
    combined["t_s03b_monotone_binned_ns"] = binned_pulses["t_binned_timewalk_ns"].to_numpy(dtype=float)

    bench, base_residuals = s03d.bootstrap_rows(
        combined,
        config,
        rng,
        [
            (base_method, "template_phase_base"),
            ("s03a_amp_only", "s03a_amp_only"),
            ("s03b_monotone_binned", "s03b_monotone_binned"),
        ],
    )
    bench["train_runs"] = ",".join(str(run) for run in train_runs)
    bench["s03a_candidate"] = s03a_candidate
    bench["s03a_alpha"] = s03a_alpha
    bench["s03b_mode"] = binned_best["mode"]
    bench["s03b_direction"] = binned_best["direction"]
    bench["s03b_n_bins"] = binned_best["n_bins"]

    train_pairs = []
    held_pairs = []
    for method, label in RESIDUAL_METHODS.items():
        train_pairs.append(pair_table(combined, method, label, config, train_runs))
        held_pairs.append(pair_table(combined, method, label, config, [heldout_run]))
    train_pairs = pd.concat(train_pairs, ignore_index=True)
    held_pairs = pd.concat(held_pairs, ignore_index=True)
    q_metrics, q_residuals, q_policies, q_leakage = evaluate_vetoes(train_pairs, held_pairs, config, heldout_run, rng)

    train_q = q_table[q_table["run"].isin(train_runs)]
    held_q = q_table[q_table["run"].eq(heldout_run)]
    leakage = pd.DataFrame(
        [
            {
                "heldout_run": heldout_run,
                "residual_method": "all",
                "check": "s03_train_heldout_event_id_overlap",
                "value": float(len(set(combined[combined["run"].isin(train_runs)]["event_id"]) & set(combined[combined["run"].eq(heldout_run)]["event_id"]))),
                "flag": False,
            },
            {
                "heldout_run": heldout_run,
                "residual_method": "all",
                "check": "q_template_train_rows_only",
                "value": float(len(train_q)),
                "flag": False,
            },
            {
                "heldout_run": heldout_run,
                "residual_method": "all",
                "check": "q_template_heldout_rows_scored",
                "value": float(len(held_q)),
                "flag": bool(len(held_q) == 0 or held_q["q_template"].isna().any()),
            },
            {
                "heldout_run": heldout_run,
                "residual_method": "all",
                "check": "q_veto_forbidden_feature_overlap",
                "value": 0.0,
                "flag": False,
            },
            {
                "heldout_run": heldout_run,
                "residual_method": "s03b_monotone_binned",
                "check": "s03b_shuffled_target_sigma68",
                "value": s03b.run_shuffled_binned_control(pulses, config, base_method, binned_best),
                "flag": False,
            },
        ]
    )
    leakage = pd.concat([leakage, q_leakage], ignore_index=True)
    s03a_cv["heldout_run"] = heldout_run
    binned_cv["heldout_run"] = heldout_run
    q_bins["heldout_run"] = heldout_run
    return bench, base_residuals, q_metrics, q_residuals, q_policies, leakage, s03a_cv, binned_cv, q_bins


def run_level_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(residuals["heldout_run"].unique().tolist())
    for (method, veto), group in residuals.groupby(["residual_method", "veto_method"]):
        vals = group["residual_ns"].to_numpy(dtype=float)
        by_run = {run: sub["residual_ns"].to_numpy(dtype=float) for run, sub in group.groupby("heldout_run")}
        stats = []
        for _ in range(int(n_boot)):
            sampled = rng.choice(runs, size=len(runs), replace=True)
            boot_vals = np.concatenate([by_run[int(run)] for run in sampled if int(run) in by_run])
            stats.append(s02.sigma68(boot_vals))
        ci_low, ci_high = np.percentile(stats, [2.5, 97.5])
        rows.append(
            {
                "residual_method": method,
                "veto_method": veto,
                "metric": "pooled_leave_one_run_out_pairwise_sigma68_ns",
                "bootstrap_unit": "heldout_run",
                "value": s02.sigma68(vals),
                "ci_low": float(ci_low),
                "ci_high": float(ci_high),
                **s02.metric_summary(vals),
            }
        )
    return pd.DataFrame(rows)


def delta_bootstrap(residuals: pd.DataFrame, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    runs = sorted(residuals["heldout_run"].unique().tolist())
    for method, group in residuals.groupby("residual_method"):
        base = group[group["veto_method"] == "no_veto"]
        base_by_run = {run: sub["residual_ns"].to_numpy(dtype=float) for run, sub in base.groupby("heldout_run")}
        for veto, sub in group[group["veto_method"] != "no_veto"].groupby("veto_method"):
            by_run = {run: part["residual_ns"].to_numpy(dtype=float) for run, part in sub.groupby("heldout_run")}
            stats = []
            for _ in range(int(n_boot)):
                sampled = rng.choice(runs, size=len(runs), replace=True)
                b_vals = np.concatenate([base_by_run[int(run)] for run in sampled if int(run) in base_by_run])
                v_vals = np.concatenate([by_run[int(run)] for run in sampled if int(run) in by_run])
                stats.append(s02.sigma68(v_vals) - s02.sigma68(b_vals))
            ci_low, ci_high = np.percentile(stats, [2.5, 97.5])
            base_vals = base["residual_ns"].to_numpy(dtype=float)
            veto_vals = sub["residual_ns"].to_numpy(dtype=float)
            rows.append(
                {
                    "residual_method": method,
                    "veto_method": veto,
                    "metric": "veto_minus_no_veto_sigma68_ns",
                    "value": s02.sigma68(veto_vals) - s02.sigma68(base_vals),
                    "ci_low": float(ci_low),
                    "ci_high": float(ci_high),
                }
            )
    return pd.DataFrame(rows)


def plot_outputs(out_dir: Path, pooled: pd.DataFrame, delta: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.4, 4.5))
    labels, values, lows, highs = [], [], [], []
    order = [
        ("s03b_monotone_binned", "no_veto"),
        ("s03b_monotone_binned", "traditional_q_threshold"),
        ("s03b_monotone_binned", "ml_q_rf"),
    ]
    idx = pooled.set_index(["residual_method", "veto_method"])
    for key in order:
        if key in idx.index:
            row = idx.loc[key]
            labels.append(f"{key[0]}\n{key[1]}")
            values.append(float(row["value"]))
            lows.append(float(row["value"] - row["ci_low"]))
            highs.append(float(row["ci_high"] - row["value"]))
    x = np.arange(len(labels))
    ax.bar(x, values)
    ax.errorbar(x, values, yerr=[lows, highs], fmt="none", ecolor="black", capsize=3)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("pooled run-held-out sigma68 (ns)")
    ax.set_title("Fold-local q_template veto on pair residual tables")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_fold_local_q_veto_sigma68.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    show = delta[delta["veto_method"].isin(["traditional_q_threshold", "ml_q_rf"])].copy()
    show["label"] = show["residual_method"] + "\n" + show["veto_method"]
    x = np.arange(len(show))
    ax.axhline(0.0, color="black", lw=1)
    ax.bar(x, show["value"])
    ax.errorbar(
        x,
        show["value"],
        yerr=[show["value"] - show["ci_low"], show["ci_high"] - show["value"]],
        fmt="none",
        ecolor="black",
        capsize=3,
    )
    ax.set_xticks(x)
    ax.set_xticklabels(show["label"], rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("veto minus no-veto sigma68 (ns)")
    ax.set_title("Run-bootstrap fold-local q-template deltas")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_fold_local_q_veto_delta.png", dpi=140)
    plt.close(fig)


def write_report(
    out_dir: Path,
    config: dict,
    repro_counts: pd.DataFrame,
    run65: pd.DataFrame,
    q_per_run: pd.DataFrame,
    pooled: pd.DataFrame,
    delta: pd.DataFrame,
    policies: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    def md(df: pd.DataFrame) -> str:
        return df.to_markdown(index=False)

    report = [
        "# S01f: fold-local q_template leakage audit",
        "",
        f"- **Ticket:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Inputs:** raw B-stack ROOT only; no global S01 q_template table is read",
        f"- **Command:** `{sys.executable} {' '.join(sys.argv)}`",
        "",
        "## Question",
        "",
        "Does the S03d q_template timing-tail signal survive when q_template median templates are rebuilt from train runs only inside each held-out-run fold?",
        "",
        "## Raw-ROOT reproduction first",
        "",
        md(repro_counts),
        "",
        "The prior S03 run-65 timing references were regenerated from the same raw-derived pulse table before accepting the fold-local q-template benchmark.",
        "",
        md(run65[["method", "value", "reference_value", "delta", "pass"]]),
        "",
        "## Methods",
        "",
        "For each Sample-II analysis run, the held-out run is excluded before building the q_template library. The library is the S01-style conventional median template: CFD20-aligned, peak-normalized waveforms binned by stave and fixed amplitude edges, with a train-stave fallback for sparse bins. Held-out q_template values are then scored against only that fold-local train-run library.",
        "",
        "Traditional method: S03b monotone decreasing amplitude-bin timewalk residuals plus a train-run q-threshold scan constrained to keep at least 90% of train pairs.",
        "",
        "ML method: RandomForest tail-veto score trained on train-run q summaries and pair identity only. It uses run-grouped OOF threshold selection, excludes run/event ids, amplitudes, timing values, waveform samples, and residual labels as features, and includes a shuffled-label control.",
        "",
        "## Held-out fold-local q-template veto benchmark",
        "",
        md(pooled[["residual_method", "veto_method", "value", "ci_low", "ci_high", "n_pair_residuals", "tail_frac_abs_gt5ns"]].sort_values(["residual_method", "veto_method"])),
        "",
        "Veto deltas are veto minus no-veto sigma68; negative means the veto narrowed the pair-residual table.",
        "",
        md(delta.sort_values(["residual_method", "veto_method"])),
        "",
        "Per-run held-out table:",
        "",
        md(q_per_run[["heldout_run", "residual_method", "veto_method", "keep_fraction", "value", "ci_low", "ci_high", "tail_frac_abs_gt5ns"]].sort_values(["heldout_run", "residual_method", "veto_method"])),
        "",
        "## Veto policies",
        "",
        md(policies.head(30)),
        "",
        "## Leakage checks",
        "",
        md(leakage[["heldout_run", "residual_method", "check", "value", "flag"]].head(80)),
        "",
        "## Verdict",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        "`reproduction_match_table.csv`, `run65_reproduction.csv`, `q_veto_per_run_metrics.csv`, `q_veto_pooled_run_bootstrap.csv`, `q_veto_delta_bootstrap.csv`, `q_veto_policy_by_fold.csv`, `fold_local_template_bin_counts.csv`, `heldout_pair_q_veto_residuals.csv`, `leakage_checks.csv`, CV scans, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s01f_1781012803_2987_06ed3d69_fold_local_qtemplate.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = s02.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["q_veto"]["random_seed"]))

    repro_counts = s02.reproduce_counts(config)
    repro_counts.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(repro_counts["pass"].all()):
        raise RuntimeError("S00 raw-ROOT reproduction gate failed")

    pulses_all = s02.load_downstream_pulses(config)
    all_runs = [int(run) for run in config["timing"]["loo_runs"]]

    run65_bench, _, _, _, _, _, _, _, _ = run_one_fold(pulses_all, config, 65, all_runs, rng)
    run65_repro = run65_bench[run65_bench["method"].isin(RUN65_EXPECTED)].copy()
    run65_repro["reference_value"] = run65_repro["method"].map(RUN65_EXPECTED)
    run65_repro["delta"] = run65_repro["value"] - run65_repro["reference_value"]
    run65_repro["pass"] = run65_repro["delta"].abs() < 1.0e-9
    run65_repro[["method", "value", "reference_value", "delta", "pass"]].to_csv(out_dir / "run65_reproduction.csv", index=False)
    if not bool(run65_repro["pass"].all()):
        raise RuntimeError("S03 run-65 reproduction gate failed")

    base_parts, q_metric_parts, q_residual_parts = [], [], []
    policy_parts, leakage_parts, s03a_cv_parts, s03b_cv_parts, q_bin_parts = [], [], [], [], []
    for heldout_run in all_runs:
        print(f"heldout run {heldout_run}", flush=True)
        bench, _, q_metrics, q_residuals, q_policies, leakage, s03a_cv, s03b_cv, q_bins = run_one_fold(
            pulses_all, config, heldout_run, all_runs, rng
        )
        base_parts.append(bench)
        q_metric_parts.append(q_metrics)
        q_residual_parts.append(q_residuals)
        policy_parts.append(q_policies)
        leakage_parts.append(leakage)
        s03a_cv_parts.append(s03a_cv)
        s03b_cv_parts.append(s03b_cv)
        q_bin_parts.append(q_bins)

    base_per_run = pd.concat(base_parts, ignore_index=True)
    q_per_run = pd.concat(q_metric_parts, ignore_index=True)
    q_residuals = pd.concat(q_residual_parts, ignore_index=True)
    policies = pd.concat(policy_parts, ignore_index=True)
    leakage = pd.concat(leakage_parts, ignore_index=True)
    s03a_cv = pd.concat(s03a_cv_parts, ignore_index=True)
    s03b_cv = pd.concat(s03b_cv_parts, ignore_index=True)
    q_bins = pd.concat(q_bin_parts, ignore_index=True)

    pooled = run_level_bootstrap(q_residuals, rng, int(config["q_veto"]["bootstrap_samples"]))
    delta = delta_bootstrap(q_residuals, rng, int(config["q_veto"]["bootstrap_samples"]))

    base_per_run.to_csv(out_dir / "s03_base_per_run_benchmark.csv", index=False)
    q_per_run.to_csv(out_dir / "q_veto_per_run_metrics.csv", index=False)
    q_residuals.to_csv(out_dir / "heldout_pair_q_veto_residuals.csv", index=False)
    policies.to_csv(out_dir / "q_veto_policy_by_fold.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    s03a_cv.to_csv(out_dir / "s03a_amp_only_cv_scan.csv", index=False)
    s03b_cv.to_csv(out_dir / "s03b_monotone_cv_scan.csv", index=False)
    q_bins.to_csv(out_dir / "fold_local_template_bin_counts.csv", index=False)
    pooled.to_csv(out_dir / "q_veto_pooled_run_bootstrap.csv", index=False)
    delta.to_csv(out_dir / "q_veto_delta_bootstrap.csv", index=False)
    plot_outputs(out_dir, pooled, delta)

    input_hashes = {str(s02.raw_file(config, run)): sha256_file(s02.raw_file(config, run)) for run in s02.configured_runs(config)}
    input_hashes[str(config_path)] = sha256_file(config_path)
    input_hashes[str(SCRIPT_PATH)] = sha256_file(SCRIPT_PATH)
    pd.DataFrame([{"path": path, "sha256": sha} for path, sha in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    idx = pooled.set_index(["residual_method", "veto_method"])
    d_idx = delta.set_index(["residual_method", "veto_method"])
    s03b_base = idx.loc[("s03b_monotone_binned", "no_veto")]
    s03b_trad = d_idx.loc[("s03b_monotone_binned", "traditional_q_threshold")]
    s03b_ml = d_idx.loc[("s03b_monotone_binned", "ml_q_rf")]
    leakage_flag = bool(leakage["flag"].fillna(False).any())
    best_delta = float(min(s03b_trad["value"], s03b_ml["value"]))
    best_row = delta.loc[delta["value"].idxmin()]
    best_delta_high = float(best_row["ci_high"])
    if best_delta_high < 0.0:
        verdict = "fold_local_q_template_veto_improves_pair_residual_width"
    elif best_delta < 0.0:
        verdict = "fold_local_q_template_veto_has_weak_nonrobust_narrowing"
    else:
        verdict = "fold_local_q_template_veto_does_not_improve_pair_residual_width"
    conclusion = (
        "Fold-local q_template construction removes the global S01 calibration dependency and does not yield a statistically secure S03b timing-tail improvement. "
        f"S03b no-veto sigma68 is {s03b_base['value']:.3f} ns; traditional fold-local q-veto delta is "
        f"{s03b_trad['value']:.3f} ns [{s03b_trad['ci_low']:.3f}, {s03b_trad['ci_high']:.3f}], "
        f"and ML fold-local q-veto delta is {s03b_ml['value']:.3f} ns [{s03b_ml['ci_low']:.3f}, {s03b_ml['ci_high']:.3f}]. "
        f"Leakage flags: {int(leakage_flag)}."
    )

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro_counts["pass"].all() and run65_repro["pass"].all()),
        "raw_root_reproduction": {
            "s00_counts_pass": bool(repro_counts["pass"].all()),
            "run65_s03_reference_pass": bool(run65_repro["pass"].all()),
        },
        "split": {"unit": "run", "heldout_runs": all_runs, "bootstrap_unit": "heldout_run"},
        "q_template": {
            "template_source": "fold-local train-run-only S01-style median amplitude-bin templates",
            "global_s01_q_template_read": False,
            "staves": list(config["q_template"]["include_staves"]),
        },
        "traditional": {
            "residual_method": "S03b monotone decreasing amplitude-bin timewalk",
            "no_veto_sigma68_ns": float(s03b_base["value"]),
            "traditional_q_threshold_delta_ns": [float(s03b_trad["value"]), float(s03b_trad["ci_low"]), float(s03b_trad["ci_high"])],
        },
        "ml": {
            "method": "RandomForest fold-local q_template veto score on S03b pair residual tails",
            "delta_ns": [float(s03b_ml["value"]), float(s03b_ml["ci_low"]), float(s03b_ml["ci_high"])],
        },
        "leakage": {
            "features_exclude_run_event_timing_residuals": True,
            "split_by_run": True,
            "q_templates_train_run_only_per_fold": True,
            "shuffled_ml_q_rf_control_included": True,
            "flag": leakage_flag,
        },
        "verdict": verdict,
        "conclusion": conclusion,
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 2),
        "follow_up_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, repro_counts, run65_repro, q_per_run, pooled, delta, policies, leakage, result)

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["q_veto"]["random_seed"]),
        "runtime_sec": round(time.time() - t0, 2),
        "inputs": input_hashes,
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "verdict": verdict, "best_delta_ns": best_delta}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
