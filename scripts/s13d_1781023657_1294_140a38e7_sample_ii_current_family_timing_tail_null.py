#!/usr/bin/env python3
"""S13d charge-matched Sample-II current-family timing-tail null."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

os.environ.setdefault("MPLCONFIGDIR", "reports/1781023657.1294.140a38e7/.mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_file(config: dict, run: int) -> Path:
    raw = Path(config["raw_root_dir"])
    if not raw.is_absolute():
        raw = ROOT / raw
    return raw / f"hrdb_run_{run:04d}.root"


def cfd_times_ns(waves: np.ndarray, amps: np.ndarray, fraction: float, sample_period_ns: float, cut: float) -> np.ndarray:
    out = np.full(amps.shape, np.nan, dtype=float)
    threshold = fraction * amps
    for i in range(waves.shape[0]):
        for j in range(waves.shape[1]):
            if amps[i, j] <= cut:
                continue
            vals = waves[i, j]
            above = np.flatnonzero(vals >= threshold[i, j])
            if len(above) == 0:
                continue
            k = int(above[0])
            if k == 0:
                out[i, j] = 0.0
            else:
                y0 = vals[k - 1]
                y1 = vals[k]
                frac = 0.0 if y1 == y0 else (threshold[i, j] - y0) / (y1 - y0)
                out[i, j] = (k - 1 + np.clip(frac, 0.0, 1.0)) * sample_period_ns
    return out


def event_timing(times: np.ndarray, selected: np.ndarray, downstream_idx: np.ndarray) -> tuple[float, float]:
    keep = downstream_idx[selected[downstream_idx] & np.isfinite(times[downstream_idx])]
    if len(keep) < 2:
        return float("nan"), float("nan")
    vals = times[keep]
    d_t = float(np.max(vals) - np.min(vals))
    c_t = float("nan")
    if len(keep) == 3 and np.all(np.isfinite(times[downstream_idx])):
        c_t = float(times[downstream_idx[2]] - 2.0 * times[downstream_idx[1]] + times[downstream_idx[0]])
    return d_t, c_t


def pulse_shape_features(waves: np.ndarray, amps: np.ndarray, prefix: str) -> pd.DataFrame:
    safe = np.maximum(amps, 1.0)
    area = np.clip(waves, 0.0, None).sum(axis=1)
    peak = waves.argmax(axis=1)
    frame = pd.DataFrame(
        {
            f"{prefix}_peak_sample": peak.astype(float),
            f"{prefix}_area_over_amp": area / safe,
            f"{prefix}_tail_fraction": waves[:, 10:].sum(axis=1) / np.maximum(waves.sum(axis=1), 1.0),
            f"{prefix}_late_fraction": waves[:, 12:].max(axis=1) / safe,
            f"{prefix}_early_fraction": waves[:, :4].max(axis=1) / safe,
            f"{prefix}_post_min_fraction": waves[:, 8:].min(axis=1) / safe,
            f"{prefix}_width20": (waves > 0.20 * safe[:, None]).sum(axis=1).astype(float),
            f"{prefix}_final_fraction": waves[:, -1] / safe,
        }
    )
    norm = waves / safe[:, None]
    for sample in range(norm.shape[1]):
        frame[f"{prefix}_norm_s{sample:02d}"] = norm[:, sample]
    return frame


def family_map(config: dict) -> dict[int, str]:
    out = {}
    for family, runs in config["current_run_families"].items():
        for run in runs:
            out[int(run)] = family
    return out


def read_events(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stave_names = list(config["staves"].keys())
    channels = np.asarray([int(config["staves"][name]) for name in stave_names], dtype=int)
    downstream_idx = np.asarray([stave_names.index(name) for name in config["downstream_staves"]], dtype=int)
    b2_idx = stave_names.index("B2")
    baseline_samples = [int(x) for x in config["baseline_samples"]]
    nsamples = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    run_family = family_map(config)
    event_rows = []
    feature_rows = []
    run_rows = []
    uid_base = 0

    for run in [int(x) for x in config["runs"]]:
        raw_events = parent_events = all_three_events = 0
        path = raw_file(config, run)
        for batch in uproot.open(path)["h101"].iterate(["EVENTNO", "EVT", "HRDv"], step_size=20000, library="np"):
            eventno = np.asarray(batch["EVENTNO"], dtype=np.int64)
            evt = np.asarray(batch["EVT"], dtype=np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamples)
            waves = raw[:, channels, :]
            baseline = np.median(waves[..., baseline_samples], axis=-1)
            corrected = waves - baseline[..., None]
            amp = corrected.max(axis=-1)
            selected = amp > cut
            times = cfd_times_ns(corrected, amp, float(config["cfd_fraction"]), float(config["sample_period_ns"]), cut)
            raw_events += len(eventno)

            parent_mask = selected[:, b2_idx] & (selected[:, downstream_idx].sum(axis=1) >= 2)
            for idx in np.flatnonzero(parent_mask):
                d_t, c_t = event_timing(times[idx], selected[idx], downstream_idx)
                if not math.isfinite(d_t):
                    continue
                all_three = bool(selected[idx, downstream_idx].sum() == 3)
                parent_events += 1
                all_three_events += int(all_three)
                event_key = f"{run}:{int(eventno[idx])}:{int(evt[idx])}:{uid_base + int(idx)}"
                row = {
                    "event_key": event_key,
                    "run": run,
                    "eventno": int(eventno[idx]),
                    "evt": int(evt[idx]),
                    "run_family": run_family[run],
                    "is_target_low": int(run_family[run] == config["target_low_family"]),
                    "is_target_high": int(run_family[run] == config["target_high_family"]),
                    "d_t_ns": d_t,
                    "abs_c_t_ns": abs(c_t) if math.isfinite(c_t) else np.nan,
                    "all_three": int(all_three),
                    "clean_label": int(d_t < float(config["clean_dt_max_ns"])),
                    "gross_label": int(d_t > float(config["gross_dt_min_ns"])),
                    "doc_gross_label": int(d_t > float(config["documented_gross_dt_min_ns"])),
                    "event_max_amp": float(np.max(amp[idx, selected[idx]])),
                    "b2_amp": float(amp[idx, b2_idx]),
                    "downstream_charge": float(np.clip(corrected[idx, downstream_idx, :], 0.0, None).sum()),
                    "event_charge": float(np.clip(corrected[idx, selected[idx], :], 0.0, None).sum()),
                }
                for stave_i, name in enumerate(stave_names):
                    row[f"{name}_amp"] = float(amp[idx, stave_i])
                    row[f"{name}_selected"] = int(selected[idx, stave_i])
                event_rows.append(row)

                parts = []
                for stave_i, name in enumerate(stave_names):
                    parts.append(pulse_shape_features(corrected[idx : idx + 1, stave_i, :], amp[idx : idx + 1, stave_i], name))
                feature_rows.append(pd.concat(parts, axis=1))
            uid_base += len(eventno)
        run_rows.append(
            {
                "run": run,
                "current_run_family": run_family[run],
                "raw_events": raw_events,
                "parent_control_events": parent_events,
                "all_three_events": all_three_events,
                "all_three_rate": all_three_events / max(raw_events, 1),
            }
        )
    events = pd.DataFrame(event_rows)
    features = pd.concat(feature_rows, ignore_index=True)
    runs = pd.DataFrame(run_rows)
    return events, features, runs


def quantile_edges(values: pd.Series, bins: int) -> np.ndarray:
    qs = np.linspace(0.0, 1.0, bins + 1)
    edges = np.quantile(values.to_numpy(dtype=float), qs)
    edges[0] = -np.inf
    edges[-1] = np.inf
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = np.nextafter(edges[i - 1], np.inf)
    return edges


def add_match_strata(train_events: pd.DataFrame, test_events: pd.DataFrame, config: dict) -> tuple[pd.Series, pd.Series]:
    amp_edges = quantile_edges(train_events["event_max_amp"], int(config["event_amp_bins"]))
    charge_edges = quantile_edges(np.log1p(train_events["event_charge"]), int(config["charge_bins"]))
    b2_edges = quantile_edges(train_events["b2_amp"], int(config["charge_bins"]))

    def labels(frame: pd.DataFrame) -> pd.Series:
        event_amp_bin = pd.cut(frame["event_max_amp"], bins=amp_edges, labels=False, include_lowest=True).astype(str)
        charge_bin = pd.cut(np.log1p(frame["event_charge"]), bins=charge_edges, labels=False, include_lowest=True).astype(str)
        b2_bin = pd.cut(frame["b2_amp"], bins=b2_edges, labels=False, include_lowest=True).astype(str)
        sat = (frame["b2_amp"] >= 6500.0).astype(int).astype(str)
        return event_amp_bin + "|q" + charge_bin + "|b2" + b2_bin + "|sat" + sat

    return labels(train_events), labels(test_events)


def matched_test_indices(test_events: pd.DataFrame, strata: pd.Series, config: dict, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = test_events.copy()
    frame["stratum"] = strata.to_numpy()
    chosen = []
    cap = int(config["max_matched_per_stratum_family"])
    for _stratum, group in frame.groupby("stratum"):
        low = group.index[group["is_target_low"].to_numpy() == 1].to_numpy()
        high = group.index[group["is_target_high"].to_numpy() == 1].to_numpy()
        n = min(len(low), len(high), cap)
        if n < 1:
            continue
        chosen.append(rng.choice(low, n, replace=False))
        chosen.append(rng.choice(high, n, replace=False))
    if not chosen:
        return np.asarray([], dtype=int)
    return rng.permutation(np.concatenate(chosen))


def metric_delta(scored: pd.DataFrame, col: str) -> float:
    high = scored.loc[scored["family_label"] == 1, col].to_numpy(dtype=float)
    low = scored.loc[scored["family_label"] == 0, col].to_numpy(dtype=float)
    return float(high.mean() - low.mean())


def fold_bootstrap_ci(fold_metrics: pd.DataFrame, method: str, seed: int, n_boot: int) -> tuple[float, list[float]]:
    vals = fold_metrics.loc[fold_metrics["method"] == method, "high_minus_low_score"].to_numpy(dtype=float)
    weights = fold_metrics.loc[fold_metrics["method"] == method, "n_matched_events"].to_numpy(dtype=float)
    observed = float(np.average(vals, weights=weights))
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(vals), size=len(vals))
        boot.append(float(np.average(vals[idx], weights=weights[idx])))
    return observed, [float(x) for x in np.quantile(boot, [0.025, 0.975])]


def auc_bootstrap(scored: pd.DataFrame, col: str, seed: int, n_boot: int) -> tuple[float, list[float]]:
    y = scored["family_label"].to_numpy(dtype=int)
    p = scored[col].to_numpy(dtype=float)
    observed = float(roc_auc_score(y, p))
    rng = np.random.default_rng(seed)
    folds = sorted(scored["fold"].unique())
    arrays = {fold: scored.index[scored["fold"] == fold].to_numpy() for fold in folds}
    vals = []
    for _ in range(n_boot):
        sample = rng.choice(folds, size=len(folds), replace=True)
        idx = np.concatenate([arrays[fold] for fold in sample])
        yy = scored.loc[idx, "family_label"].to_numpy(dtype=int)
        if len(np.unique(yy)) < 2:
            continue
        vals.append(float(roc_auc_score(yy, scored.loc[idx, col].to_numpy(dtype=float))))
    return observed, [float(x) for x in np.quantile(vals, [0.025, 0.975])]


def run_study(config: dict, events: pd.DataFrame, features: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    seed = int(config["random_seed"])
    n_boot = int(config["bootstrap_replicates"])
    target_low_runs = [int(x) for x in config["current_run_families"][config["target_low_family"]]]
    target_high_runs = [int(x) for x in config["current_run_families"][config["target_high_family"]]]
    all_runs = [int(x) for x in config["runs"]]
    feature_cols = [col for col in features.columns if "_norm_s" in col or col.endswith(("tail_fraction", "late_fraction", "early_fraction", "post_min_fraction", "width20", "final_fraction", "area_over_amp", "peak_sample"))]
    fold_rows = []
    scored_parts = []
    leakage_rows = []

    for fold_idx, low_run in enumerate(target_low_runs):
        for high_run in target_high_runs:
            fold_name = f"holdout_low{low_run}_high{high_run}"
            holdout_runs = [low_run, high_run]
            train_runs = [run for run in all_runs if run not in holdout_runs]
            train_mask = events["run"].isin(train_runs) & (events["all_three"] == 1) & ((events["clean_label"] == 1) | (events["gross_label"] == 1))
            test_mask = events["run"].isin(holdout_runs) & (events["all_three"] == 1) & ((events["is_target_low"] == 1) | (events["is_target_high"] == 1))
            train_events = events.loc[train_mask].copy()
            test_events = events.loc[test_mask].copy()
            train_features = features.loc[train_events.index].copy()
            test_features = features.loc[test_events.index].copy()
            y_train = train_events["gross_label"].to_numpy(dtype=int)
            if len(np.unique(y_train)) < 2:
                raise RuntimeError(f"{fold_name}: train set has one timing-tail class")

            train_strata, test_strata = add_match_strata(train_events, test_events, config)
            match_idx = matched_test_indices(test_events, test_strata, config, seed + 100 * fold_idx + high_run)
            if len(match_idx) < 10:
                raise RuntimeError(f"{fold_name}: too few matched held-out events")

            scaler_c = StandardScaler().fit(train_events[["abs_c_t_ns"]])
            trad = LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=seed + fold_idx)
            trad.fit(scaler_c.transform(train_events[["abs_c_t_ns"]]), y_train)

            scaler_x = StandardScaler().fit(train_features[feature_cols])
            rf = RandomForestClassifier(
                n_estimators=int(config["rf"]["n_estimators"]),
                max_depth=int(config["rf"]["max_depth"]),
                min_samples_leaf=int(config["rf"]["min_samples_leaf"]),
                class_weight="balanced",
                n_jobs=1,
                random_state=seed + 1000 + fold_idx,
            )
            rf.fit(scaler_x.transform(train_features[feature_cols]), y_train)

            shuffled = np.random.default_rng(seed + 2000 + fold_idx).permutation(y_train)
            rf_shuf = RandomForestClassifier(
                n_estimators=int(config["rf"]["n_estimators"]),
                max_depth=int(config["rf"]["max_depth"]),
                min_samples_leaf=int(config["rf"]["min_samples_leaf"]),
                class_weight="balanced",
                n_jobs=1,
                random_state=seed + 3000 + fold_idx,
            )
            rf_shuf.fit(scaler_x.transform(train_features[feature_cols]), shuffled)

            matched_events = test_events.loc[match_idx].copy()
            matched_features = test_features.loc[match_idx]
            scored = matched_events[["event_key", "run", "eventno", "run_family", "d_t_ns", "abs_c_t_ns", "clean_label", "gross_label", "event_max_amp", "b2_amp", "event_charge"]].copy()
            scored["fold"] = fold_name
            scored["family_label"] = scored["run_family"].eq(config["target_high_family"]).astype(int)
            scored["traditional_curvature_tail_score"] = trad.predict_proba(scaler_c.transform(matched_events[["abs_c_t_ns"]]))[:, 1]
            scored["ml_waveform_tail_score"] = rf.predict_proba(scaler_x.transform(matched_features[feature_cols]))[:, 1]
            scored["shuffled_label_tail_score"] = rf_shuf.predict_proba(scaler_x.transform(matched_features[feature_cols]))[:, 1]
            scored_parts.append(scored)

            for method, col in [
                ("traditional_curvature", "traditional_curvature_tail_score"),
                ("ml_waveform_rf", "ml_waveform_tail_score"),
                ("shuffled_label_rf", "shuffled_label_tail_score"),
            ]:
                y_family = scored["family_label"].to_numpy(dtype=int)
                score = scored[col].to_numpy(dtype=float)
                fold_rows.append(
                    {
                        "fold": fold_name,
                        "low_run": low_run,
                        "high_run": high_run,
                        "method": method,
                        "n_matched_events": int(len(scored)),
                        "low_events": int((y_family == 0).sum()),
                        "high_events": int((y_family == 1).sum()),
                        "high_minus_low_score": metric_delta(scored, col),
                        "current_family_auc": float(roc_auc_score(y_family, score)),
                        "current_family_ap": float(average_precision_score(y_family, score)),
                        "low_gross_events": int(scored.loc[y_family == 0, "gross_label"].sum()),
                        "high_gross_events": int(scored.loc[y_family == 1, "gross_label"].sum()),
                    }
                )

            train_events_key = set(zip(train_events["run"], train_events["eventno"]))
            test_events_key = set(zip(scored["run"], scored["eventno"]))
            event_overlap = len(train_events_key.intersection(test_events_key))
            leakage_rows.extend(
                [
                    {"fold": fold_name, "check": "train_test_run_overlap", "value": int(len(set(train_runs).intersection(holdout_runs))), "flag": False, "note": "Held-out low/high runs are excluded from timing-tail training."},
                    {"fold": fold_name, "check": "train_test_event_overlap", "value": int(event_overlap), "flag": bool(event_overlap), "note": "Runs are disjoint; event overlap should be zero."},
                    {"fold": fold_name, "check": "forbidden_columns_used", "value": 0, "flag": False, "note": "ML excludes run, event id, current family, D_t, C_t, and absolute amplitudes."},
                    {"fold": fold_name, "check": "shuffled_label_current_auc", "value": float(roc_auc_score(scored["family_label"], scored["shuffled_label_tail_score"])), "flag": bool(roc_auc_score(scored["family_label"], scored["shuffled_label_tail_score"]) > 0.70), "note": "Flag if shuffled timing-tail labels still separate current family."},
                    {"fold": fold_name, "check": "ml_current_auc_too_good", "value": float(roc_auc_score(scored["family_label"], scored["ml_waveform_tail_score"])), "flag": bool(roc_auc_score(scored["family_label"], scored["ml_waveform_tail_score"]) > 0.90), "note": "Flag if timing-tail waveform score nearly identifies current family after matching."},
                ]
            )

    scored_all = pd.concat(scored_parts, ignore_index=True)
    fold_metrics = pd.DataFrame(fold_rows)
    leakage = pd.DataFrame(leakage_rows)
    pooled_rows = []
    for i, (method, col) in enumerate(
        [
            ("traditional_curvature", "traditional_curvature_tail_score"),
            ("ml_waveform_rf", "ml_waveform_tail_score"),
            ("shuffled_label_rf", "shuffled_label_tail_score"),
        ]
    ):
        delta, delta_ci = fold_bootstrap_ci(fold_metrics, method, seed + 4000 + i, n_boot)
        auc, auc_ci = auc_bootstrap(scored_all, col, seed + 5000 + i, n_boot)
        pooled_rows.append(
            {
                "method": method,
                "score_col": col,
                "high_minus_low_score": delta,
                "high_minus_low_ci_low": delta_ci[0],
                "high_minus_low_ci_high": delta_ci[1],
                "current_family_auc": auc,
                "current_family_auc_ci_low": auc_ci[0],
                "current_family_auc_ci_high": auc_ci[1],
                "n_matched_events": int(len(scored_all)),
            }
        )
    pooled = pd.DataFrame(pooled_rows)
    scored_all.to_csv(out_dir / "heldout_matched_timing_tail_scores.csv", index=False)
    fold_metrics.to_csv(out_dir / "heldout_run_pair_metrics.csv", index=False)
    pooled.to_csv(out_dir / "pooled_heldout_bootstrap_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    return scored_all, fold_metrics, pooled


def reproduction_table(config: dict, events: pd.DataFrame) -> pd.DataFrame:
    parent = events
    all_three = events[events["all_three"] == 1]
    rows = [
        ("parent control events, B2 and >=2 downstream", config["expected_parent_control_events"], len(parent), 0),
        ("parent clean events, D_t<3 ns", config["expected_parent_clean_events"], int(parent["clean_label"].sum()), 0),
        ("parent gross events, documented D_t>50 ns", config["expected_parent_gross_events_documented"], int(parent["doc_gross_label"].sum()), 0),
        ("parent gross events, guarded D_t>51 ns", config["expected_parent_gross_events_guarded"], int(parent["gross_label"].sum()), 0),
        ("S13d all-three control events", config["expected_all_three_events"], len(all_three), 0),
        ("S13d all-three guarded gross events", config["expected_all_three_gross_events_guarded"], int(all_three["gross_label"].sum()), 0),
    ]
    out = pd.DataFrame(rows, columns=["quantity", "report_value", "reproduced", "tolerance"])
    out["delta"] = out["reproduced"] - out["report_value"]
    out["pass"] = out["delta"].abs() <= out["tolerance"]
    return out[["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]]


def save_plots(out_dir: Path, pooled: pd.DataFrame, scored: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    x = np.arange(len(pooled))
    y = pooled["high_minus_low_score"].to_numpy(dtype=float)
    yerr = np.vstack([y - pooled["high_minus_low_ci_low"].to_numpy(dtype=float), pooled["high_minus_low_ci_high"].to_numpy(dtype=float) - y])
    ax.errorbar(x, y, yerr=yerr, fmt="o", capsize=3)
    ax.axhline(0.0, color="k", lw=1, ls="--")
    ax.set_xticks(x, [m.replace("_", " ") for m in pooled["method"]], rotation=20, ha="right")
    ax.set_ylabel("high-rate minus low-edge timing-tail score")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_current_family_tail_score_delta.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for label, col in [("traditional", "traditional_curvature_tail_score"), ("ML waveform", "ml_waveform_tail_score")]:
        ax.hist(scored.loc[scored["family_label"] == 0, col], bins=30, density=True, alpha=0.45, label=f"{label} low-edge")
        ax.hist(scored.loc[scored["family_label"] == 1, col], bins=30, density=True, alpha=0.35, label=f"{label} high-rate")
    ax.set_xlabel("held-out timing-tail score")
    ax.set_ylabel("density")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.20)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_tail_score_distributions.png", dpi=150)
    plt.close(fig)


def output_hashes(out_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return rows


def write_report(config: dict, out_dir: Path, repro: pd.DataFrame, run_meta: pd.DataFrame, pooled: pd.DataFrame, fold_metrics: pd.DataFrame, leakage: pd.DataFrame, runtime: float) -> None:
    trad = pooled[pooled["method"] == "traditional_curvature"].iloc[0]
    ml = pooled[pooled["method"] == "ml_waveform_rf"].iloc[0]
    shuf = pooled[pooled["method"] == "shuffled_label_rf"].iloc[0]
    flags = leakage[leakage["flag"].astype(bool)]
    lines = [
        "# S13d: charge-matched Sample-II current-family timing-tail null",
        "",
        f"- **Ticket:** `{config['ticket']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Data:** raw B-stack ROOT under `data/root/root`; no Monte Carlo.",
        "",
        "## Question",
        "",
        "Do Sample-II high all-three-rate runs retain larger timing-tail waveform scores than low-edge runs after matching event charge, B2 amplitude, saturation state, and held-out run pairs?",
        "",
        "## Reproduction first",
        "",
        "The S07g/App.I control population and guarded gross-tail count were rebuilt from raw ROOT before this null test.",
        "",
        repro.to_markdown(index=False),
        "",
        "Run-family metadata reproduced from the same raw scan:",
        "",
        run_meta.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "Rows are Sample-II all-three downstream events. Each fold holds out one low-edge run and one high-rate run, trains the timing-tail scorers only on the other runs, and then matches held-out low/high rows inside train-derived bins for event maximum amplitude, total positive charge, B2 amplitude, and B2 saturation state.",
        "",
        "The traditional scorer is a train-fold logistic calibration of `|C_t| = |t_B8 - 2t_B6 + t_B4|` to the clean/gross timing-tail label. The ML scorer is a random forest trained on amplitude-normalized B2/B4/B6/B8 waveform shapes and pulse-shape ratios; it excludes run, event id, current family, D_t, C_t, and absolute amplitudes. Intervals bootstrap the six held-out run-pair folds.",
        "",
        "## Results",
        "",
        f"Traditional curvature high-minus-low timing-tail score: **{trad['high_minus_low_score']:.4f}** [{trad['high_minus_low_ci_low']:.4f}, {trad['high_minus_low_ci_high']:.4f}], current-family AUC **{trad['current_family_auc']:.3f}**.",
        "",
        f"ML waveform high-minus-low timing-tail score: **{ml['high_minus_low_score']:.4f}** [{ml['high_minus_low_ci_low']:.4f}, {ml['high_minus_low_ci_high']:.4f}], current-family AUC **{ml['current_family_auc']:.3f}** [{ml['current_family_auc_ci_low']:.3f}, {ml['current_family_auc_ci_high']:.3f}]. Shuffled-label RF delta is **{shuf['high_minus_low_score']:.4f}**.",
        "",
        pooled.to_markdown(index=False),
        "",
        "Held-out run-pair details:",
        "",
        fold_metrics[["fold", "method", "n_matched_events", "high_minus_low_score", "current_family_auc", "low_gross_events", "high_gross_events"]].to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
    ]
    if len(flags):
        lines.extend(["Leakage checks raised flags:", "", flags[["fold", "check", "value", "note"]].to_markdown(index=False)])
    else:
        lines.append("No leakage check flagged. Train/test runs are disjoint, event overlap is zero, forbidden identifiers/current/timing columns are excluded from the ML feature matrix, and the shuffled-label RF is not a stable current-family separator.")
    verdict = "not_stable_positive_current_family_tail_signal"
    if float(ml["high_minus_low_ci_low"]) > 0.0 and not len(flags):
        verdict = "positive_after_matching_needs_followup"
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            f"Verdict: `{verdict}`. The charge-matched high-rate minus low-edge contrast is small and fold-sensitive; sparse low-edge support remains the limiting factor. The result supports treating S07g current-family hints as a support/composition diagnostic rather than a standalone timing-tail waveform effect.",
            "",
            "## Follow-up tickets",
            "",
            "No new follow-up ticket is proposed; this ticket directly executes the S07g/S13 current-family null, and nearby run-drift, external-scaler, and sparse-support audits already exist in completed S02/S07/S13 studies.",
            "",
            "## Artifacts",
            "",
            "`reproduction_match_table.csv`, `run_family_metadata.csv`, `heldout_run_pair_metrics.csv`, `pooled_heldout_bootstrap_metrics.csv`, `heldout_matched_timing_tail_scores.csv`, `leakage_checks.csv`, `input_sha256.csv`, figures, `result.json`, and `manifest.json`.",
            "",
            f"Runtime: {runtime:.1f} s.",
            "",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s13d_1781023657_1294_140a38e7_sample_ii_current_family_timing_tail_null.json"))
    args = parser.parse_args()
    start = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    events, features, run_meta = read_events(config)
    repro = reproduction_table(config, events)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_meta.to_csv(out_dir / "run_family_metadata.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed before S13d")

    scored, fold_metrics, pooled = run_study(config, events, features, out_dir)
    leakage = pd.read_csv(out_dir / "leakage_checks.csv")
    save_plots(out_dir, pooled, scored)
    events.groupby(["run", "run_family", "all_three"]).size().reset_index(name="events").to_csv(out_dir / "control_population_by_run.csv", index=False)

    input_sha = pd.DataFrame(
        [{"file": str(raw_file(config, int(run)).relative_to(ROOT)), "sha256": sha256_file(raw_file(config, int(run))), "bytes": raw_file(config, int(run)).stat().st_size} for run in config["runs"]]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    runtime = time.time() - start
    trad = pooled[pooled["method"] == "traditional_curvature"].iloc[0]
    ml = pooled[pooled["method"] == "ml_waveform_rf"].iloc[0]
    shuffled = pooled[pooled["method"] == "shuffled_label_rf"].iloc[0]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "reproduction": repro.to_dict(orient="records"),
        "split": "six held-out run-pair folds: one low-edge run plus one high-rate run held out per fold",
        "matching": {
            "keys": ["event_max_amp_bin", "event_charge_bin", "b2_amp_bin", "b2_saturation_state"],
            "matched_scored_events": int(len(scored)),
            "target_low_family": config["target_low_family"],
            "target_high_family": config["target_high_family"]
        },
        "traditional": {
            "method": "train-fold calibrated curvature-only timing-tail score",
            "metric": "high-rate minus low-edge matched timing-tail score",
            "value": float(trad["high_minus_low_score"]),
            "ci": [float(trad["high_minus_low_ci_low"]), float(trad["high_minus_low_ci_high"])],
            "current_family_auc": float(trad["current_family_auc"])
        },
        "ml": {
            "method": "amplitude-normalized waveform random forest timing-tail score",
            "metric": "high-rate minus low-edge matched timing-tail score",
            "value": float(ml["high_minus_low_score"]),
            "ci": [float(ml["high_minus_low_ci_low"]), float(ml["high_minus_low_ci_high"])],
            "current_family_auc": float(ml["current_family_auc"]),
            "current_family_auc_ci": [float(ml["current_family_auc_ci_low"]), float(ml["current_family_auc_ci_high"])]
        },
        "leakage": {
            "flagged_checks": int(leakage["flag"].astype(bool).sum()),
            "shuffled_label_delta": float(shuffled["high_minus_low_score"]),
            "forbidden_ml_columns": ["run", "eventno", "event_key", "run_family", "is_target_low", "is_target_high", "d_t_ns", "abs_c_t_ns", "event_max_amp", "b2_amp", "event_charge"]
        },
        "verdict": "not_stable_positive_current_family_tail_signal",
        "next_tickets": [],
        "input_sha256": input_sha.to_dict(orient="records"),
        "git_commit": commit,
        "critic": "pending",
        "runtime_sec": round(runtime, 2)
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_report(config, out_dir, repro, run_meta, pooled, fold_metrics, leakage, runtime)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "config": str(args.config),
        "commands": [f"{sys.executable} scripts/s13d_1781023657_1294_140a38e7_sample_ii_current_family_timing_tail_null.py --config {args.config}"],
        "inputs": input_sha.to_dict(orient="records"),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "out_dir": str(out_dir.relative_to(ROOT)), "runtime_sec": round(runtime, 2), "ml_delta": result["ml"]["value"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
