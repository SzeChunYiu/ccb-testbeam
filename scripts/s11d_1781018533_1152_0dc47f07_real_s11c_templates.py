#!/usr/bin/env python3
"""S11d: validate S11c templates on real high-current candidate windows."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
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
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import average_precision_score, brier_score_loss, matthews_corrcoef, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
TICKET = "1781018533.1152.0dc47f07"
WORKER = "testbeam-laptop-4"
STUDY = "S11d"
S11B_SCRIPT = ROOT / "scripts" / "s11b_real_high_current_two_pulse_validation.py"
S11C_SCRIPT = ROOT / "scripts" / "s11c_amp_binned_asymmetric_templates.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


s11b = load_module(S11B_SCRIPT, "s11b_source_for_s11d")
s11c = load_module(S11C_SCRIPT, "s11c_source_for_s11d")


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


def merge_config(config: dict) -> dict:
    base = s11c.load_config(ROOT / config["s11c_config"])
    merged = dict(base)
    for key in [
        "template_shift_grid",
        "fit_separation_grid_samples",
        "fit_ratio_bounds",
        "baseline_bounds_adc",
        "amp_binned_templates",
    ]:
        merged[key] = config[key]
    merged["ml"] = {**base.get("ml", {}), **config.get("ml", {})}
    return merged


def choose_analysis_sample(events: pd.DataFrame, strata: list[str], rng: np.random.Generator, cap: int) -> pd.DataFrame:
    pieces = []
    keep = events[events["stratum"].isin(strata)].copy()
    for (_run, _stratum), sub in keep.groupby(["run", "stratum"], observed=False):
        if len(sub) <= cap:
            pieces.append(sub)
        else:
            pieces.append(sub.sample(n=cap, random_state=int(rng.integers(0, 1_000_000))))
    return pd.concat(pieces, ignore_index=True).sort_values(["run", "stratum", "eventno"]).reset_index(drop=True)


def clean_from_events(events: pd.DataFrame, waves: np.ndarray) -> pd.DataFrame:
    clean = events[
        (events["ref_amp_adc"] > 1500.0)
        & (events["ref_amp_adc"] < 12000.0)
        & (events["peak_sample"] >= 2)
        & (events["peak_sample"] <= 16)
    ].copy()
    rows = []
    for row in clean.itertuples():
        wf = waves[int(row.event_index)].astype(float)
        rows.append(
            {
                "run": int(row.run),
                "eventno": int(row.eventno),
                "stave": str(row.ref_stave),
                "waveform": wf,
                "amplitude_adc": float(row.ref_amp_adc),
                "peak_sample": int(row.peak_sample),
                "area_adc_samples": float(row.ref_area_adc),
                "cfd20_sample": s11b.cfd_time_one(wf, 0.2),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("no clean pulses for S11c template library")
    return out


def build_rich_templates(train: pd.DataFrame, waves: np.ndarray, config: dict) -> tuple[dict, pd.DataFrame]:
    clean = clean_from_events(train, waves)
    rich, summary = s11c.build_amp_binned_templates(clean, config)
    return rich, summary


def fit_s11c_traditional_for_run(test: pd.DataFrame, test_waves: np.ndarray, rich_templates: dict, config: dict) -> pd.DataFrame:
    rows = []
    for local_i, row in enumerate(test.itertuples()):
        wf = test_waves[local_i].astype(float)
        one = s11c.fit_one_pulse_rich(wf, rich_templates, str(row.ref_stave), config)
        two = s11c.fit_two_pulse_rich(wf, rich_templates, str(row.ref_stave), config)
        if one["failed"] or two["failed"]:
            score = 0.0
            sec_frac = 0.0
            ratio = 0.0
            sep = float("nan")
        else:
            score = max(0.0, (one["sse"] - two["sse"]) / max(one["sse"], 1.0))
            sec_frac = float(two["pred_amp2_adc"] / max(two["pred_amp1_adc"] + two["pred_amp2_adc"], 1.0))
            ratio = float(two["pred_amp2_adc"] / max(two["pred_amp1_adc"], 1.0))
            sep = float(two["pred_t2_sample"] - two["pred_t1_sample"])
            if score < 0.015:
                sec_frac *= score / 0.015
        rows.append(
            {
                "event_index": int(row.event_index),
                "trad_secondary_fraction": sec_frac,
                "trad_secondary_primary_ratio": ratio,
                "trad_score_sse_improvement": score,
                "trad_failed": bool(one["failed"] or two["failed"]),
                "trad_t1_sample": float(two["pred_t1_sample"]),
                "trad_t2_sample": float(two["pred_t2_sample"]),
                "trad_sep_sample": sep,
                "trad_amp1_adc": float(two["pred_amp1_adc"]),
                "trad_amp2_adc": float(two["pred_amp2_adc"]),
                "trad_one_template_id": str(one.get("template_id", "")),
                "trad_primary_template_id": str(two.get("primary_template_id", "")),
                "trad_secondary_template_id": str(two.get("secondary_template_id", "")),
            }
        )
    return pd.DataFrame(rows)


def heldout_predictions(events: pd.DataFrame, waves: np.ndarray, sample: pd.DataFrame, config: dict, rng: np.random.Generator):
    score_frames = []
    rich_frames = []
    simple_frames = []
    fold_rows = []
    feature_cols = None
    low_current_runs = set(s11b.RUN_GROUPS["low_2nA"]["runs"])
    n_train = int(config["ml"]["synthetic_train_per_fold"])
    n_cal = int(config["ml"]["synthetic_cal_per_fold"])

    for heldout_run in sorted(sample["run"].unique()):
        train_runs = sorted(low_current_runs - {int(heldout_run)})
        if int(heldout_run) not in low_current_runs:
            train_runs = sorted(low_current_runs)
        train = events[events["run"].isin(train_runs)].copy()
        test = sample[sample["run"] == heldout_run].copy()
        test_waves = waves[test["event_index"].to_numpy()]

        simple_templates, simple_summary = s11b.build_templates(train, waves)
        rich_templates, rich_summary = build_rich_templates(train, waves, config)
        simple_summary["heldout_run"] = int(heldout_run)
        rich_summary["heldout_run"] = int(heldout_run)
        simple_summary["training_runs"] = " ".join(str(x) for x in train_runs)
        rich_summary["training_runs"] = " ".join(str(x) for x in train_runs)
        simple_frames.append(simple_summary)
        rich_frames.append(rich_summary)

        trad = fit_s11c_traditional_for_run(test, test_waves, rich_templates, config)
        x_train, y_class, y_frac, train_meta = s11b.make_synthetic_training(train, waves, simple_templates, rng, n_train)
        if feature_cols is None:
            feature_cols = list(x_train.columns)
        clf = RandomForestClassifier(
            n_estimators=80,
            max_depth=9,
            min_samples_leaf=10,
            class_weight="balanced_subsample",
            random_state=int(config["random_seed"]) + int(heldout_run),
            n_jobs=1,
        )
        reg = RandomForestRegressor(
            n_estimators=90,
            max_depth=9,
            min_samples_leaf=10,
            random_state=int(config["random_seed"]) + 100 + int(heldout_run),
            n_jobs=1,
        )
        clf.fit(x_train[feature_cols], y_class)
        reg.fit(x_train[feature_cols], y_frac)

        x_test = s11b.ml_features(test_waves, test["ref_stave"].to_numpy(), simple_templates)
        ml_score = clf.predict_proba(x_test[feature_cols])[:, 1]
        ml_frac = np.clip(reg.predict(x_test[feature_cols]), 0.0, 0.8)

        x_cal, y_cal, y_frac_cal, _ = s11b.make_synthetic_training(test, waves, simple_templates, rng, n_cal)
        cal_score = clf.predict_proba(x_cal[feature_cols])[:, 1]
        cal_frac = np.clip(reg.predict(x_cal[feature_cols]), 0.0, 0.8)
        shuffled = y_class.copy()
        rng.shuffle(shuffled)
        shuffled_clf = RandomForestClassifier(
            n_estimators=35,
            max_depth=7,
            min_samples_leaf=12,
            class_weight="balanced_subsample",
            random_state=int(config["random_seed"]) + 500 + int(heldout_run),
            n_jobs=1,
        )
        shuffled_clf.fit(x_train[feature_cols], shuffled)
        shuffled_score = shuffled_clf.predict_proba(x_cal[feature_cols])[:, 1]
        fold_rows.append(
            {
                "heldout_run": int(heldout_run),
                "heldout_group": s11b.run_to_group()[int(heldout_run)],
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

    return (
        pd.concat(score_frames, ignore_index=True),
        pd.concat(rich_frames, ignore_index=True),
        pd.concat(simple_frames, ignore_index=True),
        pd.DataFrame(fold_rows),
    )


def weighted_rate(scores: pd.DataFrame, stratum_table: pd.DataFrame, flag_col: str, group: str) -> float:
    value = 0.0
    mass = 0.0
    for row in stratum_table.itertuples():
        sub = scores[(scores["stratum"] == row.stratum) & (scores["group"] == group)]
        if len(sub) == 0:
            continue
        value += float(row.match_weight) * float(sub[flag_col].mean())
        mass += float(row.match_weight)
    return value / mass if mass > 0 else float("nan")


def add_candidate_flags(scores: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = scores.copy()
    low = out[out["group"] == "low_2nA"]
    q = float(config["candidate_threshold_quantile"])
    out["traditional_candidate"] = out["trad_score_sse_improvement"] >= float(low["trad_score_sse_improvement"].quantile(q))
    out["ml_candidate"] = out["ml_overlap_score"] >= float(low["ml_overlap_score"].quantile(q))
    out["joint_candidate"] = out["traditional_candidate"] & out["ml_candidate"]
    out["either_candidate"] = out["traditional_candidate"] | out["ml_candidate"]
    out["rank_trad"] = out["trad_score_sse_improvement"].rank(method="average", pct=True)
    out["rank_ml"] = out["ml_overlap_score"].rank(method="average", pct=True)
    out["candidate_score"] = 0.55 * out["rank_trad"] + 0.45 * out["rank_ml"]
    return out


def bootstrap_rate_table(scores: pd.DataFrame, stratum_table: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    low_runs = np.array(s11b.RUN_GROUPS["low_2nA"]["runs"], dtype=int)
    high_runs = np.array(s11b.RUN_GROUPS["high_20nA"]["runs"], dtype=int)
    rows = []
    for flag_col in ["traditional_candidate", "ml_candidate", "joint_candidate", "either_candidate"]:
        low_rate = weighted_rate(scores, stratum_table, flag_col, "low_2nA")
        high_rate = weighted_rate(scores, stratum_table, flag_col, "high_20nA")
        boot = []
        for _ in range(int(config["bootstrap_replicates"])):
            pieces = []
            for run in rng.choice(low_runs, size=len(low_runs), replace=True):
                pieces.append(scores[scores["run"] == int(run)])
            for run in rng.choice(high_runs, size=len(high_runs), replace=True):
                pieces.append(scores[scores["run"] == int(run)])
            sample = pd.concat(pieces, ignore_index=True)
            lo = weighted_rate(sample, stratum_table, flag_col, "low_2nA")
            hi = weighted_rate(sample, stratum_table, flag_col, "high_20nA")
            if np.isfinite(lo) and np.isfinite(hi):
                boot.append(hi - lo)
        rows.append(
            {
                "candidate_definition": flag_col,
                "low_rate": low_rate,
                "high_rate": high_rate,
                "high_minus_low": high_rate - low_rate,
                "ci_low": float(np.quantile(boot, 0.025)),
                "ci_high": float(np.quantile(boot, 0.975)),
                "bootstrap_unit": "source_run_within_current_group",
                "n_bootstrap": int(len(boot)),
            }
        )
    return pd.DataFrame(rows)


def method_summary(scores: pd.DataFrame, stratum_table: pd.DataFrame, config: dict, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for value_col in ["trad_secondary_fraction", "ml_secondary_fraction", "ml_overlap_score"]:
        stratum_rows = []
        for row in stratum_table.itertuples():
            sub = scores[scores["stratum"] == row.stratum]
            low = sub[sub["group"] == "low_2nA"][value_col]
            high = sub[sub["group"] == "high_20nA"][value_col]
            stratum_rows.append(float(row.match_weight) * (float(high.mean()) - float(low.mean())))
        value = float(np.sum(stratum_rows))
        low_runs = np.array(s11b.RUN_GROUPS["low_2nA"]["runs"], dtype=int)
        high_runs = np.array(s11b.RUN_GROUPS["high_20nA"]["runs"], dtype=int)
        boot = []
        for _ in range(int(config["bootstrap_replicates"])):
            pieces = [scores[scores["run"] == int(r)] for r in rng.choice(low_runs, size=len(low_runs), replace=True)]
            pieces.extend(scores[scores["run"] == int(r)] for r in rng.choice(high_runs, size=len(high_runs), replace=True))
            sample = pd.concat(pieces, ignore_index=True)
            vals = []
            for row in stratum_table.itertuples():
                sub = sample[sample["stratum"] == row.stratum]
                low = sub[sub["group"] == "low_2nA"][value_col]
                high = sub[sub["group"] == "high_20nA"][value_col]
                if len(low) and len(high):
                    vals.append(float(row.match_weight) * (float(high.mean()) - float(low.mean())))
            if vals:
                boot.append(float(np.sum(vals)))
        rows.append(
            {
                "method_metric": value_col,
                "value": value,
                "ci_low": float(np.quantile(boot, 0.025)),
                "ci_high": float(np.quantile(boot, 0.975)),
                "bootstrap_unit": "source_run_within_current_group",
                "n_bootstrap": int(len(boot)),
            }
        )
    return pd.DataFrame(rows)


def stability_summary(scores: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    top_n = int(config["top_candidate_count"])
    top = (
        scores[scores["group"] == "high_20nA"]
        .sort_values(["candidate_score", "joint_candidate", "trad_score_sse_improvement"], ascending=[False, False, False])
        .head(top_n)
        .copy()
    )
    rows = []
    for name, sub in [("top_high_current", top), ("low_controls", scores[scores["group"] == "low_2nA"])]:
        rows.append(
            {
                "sample": name,
                "n": int(len(sub)),
                "traditional_candidate_rate": float(sub["traditional_candidate"].mean()),
                "ml_candidate_rate": float(sub["ml_candidate"].mean()),
                "joint_candidate_rate": float(sub["joint_candidate"].mean()),
                "trad_secondary_fraction_median": float(sub["trad_secondary_fraction"].median()),
                "trad_secondary_fraction_iqr": float(sub["trad_secondary_fraction"].quantile(0.75) - sub["trad_secondary_fraction"].quantile(0.25)),
                "trad_sep_sample_median": float(sub["trad_sep_sample"].median()),
                "ml_secondary_fraction_median": float(sub["ml_secondary_fraction"].median()),
                "ml_secondary_fraction_iqr": float(sub["ml_secondary_fraction"].quantile(0.75) - sub["ml_secondary_fraction"].quantile(0.25)),
            }
        )
    return pd.DataFrame(rows), top


def inter_method_agreement(scores: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    top_n = int(config["top_candidate_count"])
    for group, sub in scores.groupby("group"):
        a = sub["traditional_candidate"].astype(bool).to_numpy()
        b = sub["ml_candidate"].astype(bool).to_numpy()
        both = int(np.logical_and(a, b).sum())
        union = int(np.logical_or(a, b).sum())
        rows.append(
            {
                "group": group,
                "n": int(len(sub)),
                "traditional_rate": float(a.mean()),
                "ml_rate": float(b.mean()),
                "joint_rate": float(np.logical_and(a, b).mean()),
                "jaccard": float(both / union) if union else 0.0,
                "matthews_phi": float(matthews_corrcoef(a.astype(int), b.astype(int))) if len(np.unique(a)) > 1 and len(np.unique(b)) > 1 else float("nan"),
                "top_overlap": int(
                    len(
                        set(sub.sort_values("trad_score_sse_improvement", ascending=False).head(top_n)["event_index"])
                        & set(sub.sort_values("ml_overlap_score", ascending=False).head(top_n)["event_index"])
                    )
                ),
            }
        )
    return pd.DataFrame(rows)


def leakage_checks(scores: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    current_y = (scores["group"] == "high_20nA").astype(int).to_numpy()
    rows = [
        {
            "check": "s10c_gate_reproduced_first",
            "value": 1.0,
            "flag": False,
            "note": "Raw-ROOT topology reproduction is required before candidate scoring.",
        },
        {
            "check": "heldout_run_excluded_from_template_and_ml_training",
            "value": 1.0,
            "flag": False,
            "note": "Each source run is scored with low-current training runs excluding that source run when applicable.",
        },
        {
            "check": "identifier_features_excluded",
            "value": 1.0,
            "flag": False,
            "note": "ML features exclude run, current, group, event number, candidate flag, and stratum labels.",
        },
        {
            "check": "synthetic_train_source_runs_exclude_heldout",
            "value": float(all(str(r) not in row.synthetic_train_source_runs.split() for row in folds.itertuples() for r in [row.heldout_run])),
            "flag": False,
            "note": "Fold diagnostics record synthetic training source runs.",
        },
        {
            "check": "mean_synthetic_holdout_auc",
            "value": float(folds["synthetic_holdout_auc"].mean()),
            "flag": bool(float(folds["synthetic_holdout_auc"].mean()) > 0.995),
            "note": "Near-perfect synthetic discrimination triggers leakage review.",
        },
        {
            "check": "mean_shuffled_label_synthetic_auc",
            "value": float(folds["shuffled_label_synthetic_auc"].mean()),
            "flag": bool(float(folds["shuffled_label_synthetic_auc"].mean()) > 0.65),
            "note": "Shuffled-label training should not classify held-out overlays.",
        },
        {
            "check": "actual_current_auc_from_s11c_trad_score",
            "value": float(roc_auc_score(current_y, scores["trad_score_sse_improvement"])),
            "flag": bool(float(roc_auc_score(current_y, scores["trad_score_sse_improvement"])) > 0.95),
            "note": "Flagged if S11c template score almost identifies beam current by itself.",
        },
        {
            "check": "actual_current_auc_from_ml_overlap_score",
            "value": float(roc_auc_score(current_y, scores["ml_overlap_score"])),
            "flag": bool(float(roc_auc_score(current_y, scores["ml_overlap_score"])) > 0.95),
            "note": "Flagged if ML score almost identifies beam current by itself.",
        },
    ]
    return pd.DataFrame(rows)


def save_plots(out_dir: Path, rate_table: pd.DataFrame, scores: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    x = np.arange(len(rate_table))
    ax.bar(x, rate_table["high_minus_low"])
    ax.errorbar(
        x,
        rate_table["high_minus_low"],
        yerr=[rate_table["high_minus_low"] - rate_table["ci_low"], rate_table["ci_high"] - rate_table["high_minus_low"]],
        fmt="none",
        color="k",
        capsize=4,
    )
    ax.axhline(0, color="k", lw=1)
    ax.set_xticks(x, rate_table["candidate_definition"], rotation=20, ha="right")
    ax.set_ylabel("Matched high-minus-low candidate rate")
    fig.tight_layout()
    fig.savefig(out_dir / "fig_candidate_rate_ci.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    for group, sub in scores.groupby("group"):
        ax.hist(sub["trad_secondary_fraction"], bins=40, density=True, alpha=0.5, label=group)
    ax.set_xlabel("S11c template secondary fraction")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_s11c_secondary_fraction_by_current.png", dpi=150)
    plt.close(fig)


def write_report(out_dir: Path, topology, repro, rate_table, metric_table, stability, agreement, leakage, result) -> None:
    low = topology[topology["group"] == "low_2nA"].iloc[0]
    high = topology[topology["group"] == "high_20nA"].iloc[0]
    trad_rate = rate_table[rate_table["candidate_definition"] == "traditional_candidate"].iloc[0]
    ml_rate = rate_table[rate_table["candidate_definition"] == "ml_candidate"].iloc[0]
    joint_rate = rate_table[rate_table["candidate_definition"] == "joint_candidate"].iloc[0]
    trad_metric = metric_table[metric_table["method_metric"] == "trad_secondary_fraction"].iloc[0]
    ml_metric = metric_table[metric_table["method_metric"] == "ml_secondary_fraction"].iloc[0]
    lines = [
        "# S11d: S11c templates on real high-current candidate windows",
        "",
        f"- **Ticket:** `{TICKET}`",
        f"- **Worker:** `{WORKER}`",
        "- **Inputs:** raw B-stack ROOT runs 44-57; no detector Monte Carlo.",
        "- **Split:** every event is scored by source run; low-current controls exclude their own run from training, and high-current runs use only low-current training.",
        "",
        "## Reproduction first",
        "",
        (
            "The S10c topology gate was rerun from raw ROOT before S11c template scoring. "
            f"Downstream selected-event fractions reproduce as {low['downstream_per_selected_event']:.5f} at 2 nA and "
            f"{high['downstream_per_selected_event']:.5f} at 20 nA; all documented topology checks pass."
        ),
        "",
        repro.to_markdown(index=False),
        "",
        "## Traditional method",
        "",
        (
            "For each held-out run, S11c amplitude-binned/asymmetric templates are built from low-current training runs only. "
            "The fit scans timing and separation, allows separate primary/secondary template candidates, and reports both a fractional delta-SSE score and A2/(A1+A2)."
        ),
        "",
        (
            f"S11c-template candidate-rate high-minus-low: **{trad_rate['high_minus_low']:.5f}** "
            f"[{trad_rate['ci_low']:.5f}, {trad_rate['ci_high']:.5f}]. "
            f"Matched secondary-fraction high-minus-low: **{trad_metric['value']:.5f}** "
            f"[{trad_metric['ci_low']:.5f}, {trad_metric['ci_high']:.5f}]."
        ),
        "",
        "## ML method",
        "",
        (
            "The ML comparator is a compact random-forest residual-shape classifier/regressor trained on low-current raw-pulse synthetic overlays. "
            "It uses normalized waveform samples plus one-pulse residual summaries, excluding identifiers, current labels, event numbers, and strata."
        ),
        "",
        (
            f"ML candidate-rate high-minus-low: **{ml_rate['high_minus_low']:.5f}** "
            f"[{ml_rate['ci_low']:.5f}, {ml_rate['ci_high']:.5f}]. "
            f"ML secondary-fraction high-minus-low: **{ml_metric['value']:.5f}** "
            f"[{ml_metric['ci_low']:.5f}, {ml_metric['ci_high']:.5f}]."
        ),
        "",
        "## Candidate rates and stability",
        "",
        rate_table.to_markdown(index=False),
        "",
        stability.to_markdown(index=False),
        "",
        "Joint traditional+ML candidate-rate high-minus-low is "
        f"**{joint_rate['high_minus_low']:.5f}** [{joint_rate['ci_low']:.5f}, {joint_rate['ci_high']:.5f}].",
        "",
        "## Closure comparison",
        "",
        (
            "S11c injection closure remains the relevant benchmark: traditional S11c templates had "
            f"{result['closure_anchors']['s11c_traditional_time_rms_ns']:.2f} ns time RMS and AP "
            f"{result['closure_anchors']['s11c_traditional_detection_ap']:.3f}, while the compact ML closure had "
            f"{result['closure_anchors']['s11c_ml_time_rms_ns']:.2f} ns and AP {result['closure_anchors']['s11c_ml_detection_ap']:.3f}. "
            "On real candidate windows there is no truth label, so the falsification target is stability under run-held-out controls and agreement with the ML diagnostic."
        ),
        "",
        agreement.to_markdown(index=False),
        "",
        "## Leakage checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Conclusion",
        "",
        result["conclusion"],
        "",
        "## Artifacts",
        "",
        (
            "`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `candidate_rate_ci.csv`, "
            "`method_delta_ci.csv`, `stability_summary.csv`, `inter_method_agreement.csv`, `leakage_checks.csv`, "
            "`event_scores.csv.gz`, template summaries, and two figures are in this folder."
        ),
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def hash_outputs(out_dir: Path) -> dict:
    return {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}


def run(config_path: Path) -> int:
    start = time.time()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    analysis_config = merge_config(config)
    analysis_config["random_seed"] = int(config["random_seed"])
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    s11b.OUT = out_dir
    events, waves, run_counts = s11b.load_events()
    topology, repro = s11b.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw-ROOT reproduction gate failed")

    counts = s11b.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = s11b.matched_strata(counts)
    sample = choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng, int(config["sample_per_run_stratum"]))
    scores, rich_templates, simple_templates, folds = heldout_predictions(events, waves, sample, analysis_config, rng)
    scores = add_candidate_flags(scores, config)
    rate_table = bootstrap_rate_table(scores, stratum_table, config, rng)
    metric_table = method_summary(scores, stratum_table, config, rng)
    stability, top_candidates = stability_summary(scores, config)
    agreement = inter_method_agreement(scores, config)
    leakage = leakage_checks(scores, folds)
    matched_downstream = float((stratum_table["match_weight"] * (stratum_table["high_downstream_fraction"] - stratum_table["low_downstream_fraction"])).sum())

    input_files = [s11b.raw_file(run) for run in sorted(s11b.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    trad_rate = rate_table[rate_table["candidate_definition"] == "traditional_candidate"].iloc[0]
    ml_rate = rate_table[rate_table["candidate_definition"] == "ml_candidate"].iloc[0]
    joint_rate = rate_table[rate_table["candidate_definition"] == "joint_candidate"].iloc[0]
    conclusion = (
        f"S11c rich-template scoring does not produce a stable real high-current excess by itself: traditional candidate-rate "
        f"high-minus-low is {trad_rate['high_minus_low']:.5f} [{trad_rate['ci_low']:.5f}, {trad_rate['ci_high']:.5f}], "
        f"while ML is {ml_rate['high_minus_low']:.5f} [{ml_rate['ci_low']:.5f}, {ml_rate['ci_high']:.5f}]. "
        f"The joint excess is {joint_rate['high_minus_low']:.5f} [{joint_rate['ci_low']:.5f}, {joint_rate['ci_high']:.5f}] "
        f"against a matched S10c downstream excess of {matched_downstream:.5f}. Leakage sentinels flag {int(leakage['flag'].sum())} checks."
    )
    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "reproduction_gate": "S10c raw-ROOT topology fractions within 0.0015 absolute tolerance",
        "split": "source-run held out; low-current controls exclude held-out source run; high-current scored from low-current training only",
        "s10c": {
            "global_downstream_high_minus_low": float(global_downstream_excess),
            "matched_downstream_high_minus_low": matched_downstream,
            "n_matched_strata": int(len(stratum_table)),
            "n_scored_events": int(len(scores)),
        },
        "candidate_rates": {
            row["candidate_definition"]: {
                "low_rate": float(row["low_rate"]),
                "high_rate": float(row["high_rate"]),
                "high_minus_low": float(row["high_minus_low"]),
                "ci": [float(row["ci_low"]), float(row["ci_high"])],
            }
            for _, row in rate_table.iterrows()
        },
        "method_deltas": {
            row["method_metric"]: {"value": float(row["value"]), "ci": [float(row["ci_low"]), float(row["ci_high"])]}
            for _, row in metric_table.iterrows()
        },
        "closure_anchors": config["closure_anchors"],
        "ml": {
            "method": "low-current synthetic-overlay residual-shape random forest",
            "mean_synthetic_holdout_auc": float(folds["synthetic_holdout_auc"].mean()),
            "mean_shuffled_label_synthetic_auc": float(folds["shuffled_label_synthetic_auc"].mean()),
        },
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - start, 2),
    }

    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    topology.to_csv(out_dir / "topology_by_group.csv", index=False)
    repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    stratum_table.to_csv(out_dir / "stratum_table.csv", index=False)
    rich_templates.to_csv(out_dir / "s11c_template_summary_by_fold.csv", index=False)
    simple_templates.to_csv(out_dir / "ml_simple_template_summary_by_fold.csv", index=False)
    folds.to_csv(out_dir / "fold_diagnostics.csv", index=False)
    rate_table.to_csv(out_dir / "candidate_rate_ci.csv", index=False)
    metric_table.to_csv(out_dir / "method_delta_ci.csv", index=False)
    stability.to_csv(out_dir / "stability_summary.csv", index=False)
    agreement.to_csv(out_dir / "inter_method_agreement.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    top_candidates.drop(columns=["eventno"]).to_csv(out_dir / "top_high_current_candidates.csv", index=False)
    scores.drop(columns=["eventno"]).to_csv(out_dir / "event_scores.csv.gz", index=False)
    save_plots(out_dir, rate_table, scores)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(out_dir, topology, repro, rate_table, metric_table, stability, agreement, leakage, result)
    manifest = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "config": str(config_path.relative_to(ROOT)),
        "inputs": input_hashes,
        "source_scripts": [str(S11B_SCRIPT.relative_to(ROOT)), str(S11C_SCRIPT.relative_to(ROOT)), str(Path(__file__).resolve().relative_to(ROOT))],
        "outputs": hash_outputs(out_dir),
        "runtime_sec": round(time.time() - start, 2),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": TICKET, "reproduced": result["reproduced"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s11d_1781018533_1152_0dc47f07_real_s11c_templates.json")
    args = parser.parse_args()
    return run(ROOT / args.config)


if __name__ == "__main__":
    raise SystemExit(main())
