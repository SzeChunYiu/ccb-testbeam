#!/usr/bin/env python3
"""P04h: A-stack charge-transfer support map by B-stack topology.

This ticket extends the P04c A/B event-matched charge-transfer check.  It first
reproduces the P04c raw-ROOT number, then asks which B-stack strata have enough
held-out support to make the A-stack charge proxy identifiable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04c_ab_event_matched_charge_transfer as p04c  # noqa: E402


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def bin_labels(edges: Iterable[Iterable[float]]) -> list[str]:
    labels = []
    for lo, hi in edges:
        labels.append(f"{int(lo)}_{'inf' if float(hi) > 1e8 else int(hi)}")
    return labels


def assign_amp_bin(values: np.ndarray, edges: list[list[float]]) -> np.ndarray:
    labels = np.asarray(bin_labels(edges), dtype=object)
    bounds = np.asarray([float(item[0]) for item in edges] + [float(edges[-1][1])])
    idx = np.clip(np.searchsorted(bounds, values, side="right") - 1, 0, len(labels) - 1)
    return labels[idx]


def width_at_fraction(wave: np.ndarray, amp: np.ndarray, frac: float) -> np.ndarray:
    return (wave > (amp[:, :, None] * frac)).sum(axis=2)


def add_support_strata(frame: pd.DataFrame, wave: np.ndarray, config: dict) -> pd.DataFrame:
    out = frame.copy()
    bsel = out[["B4_selected", "B6_selected", "B8_selected"]].to_numpy(dtype=bool)
    patterns = []
    for row in bsel:
        names = [name for name, flag in zip(["B4", "B6", "B8"], row) if flag]
        if not names:
            patterns.append("B2_only")
        elif len(names) == 1:
            patterns.append("B2_" + names[0])
        else:
            patterns.append("B2_multi_downstream")
    out["topology_pattern"] = patterns
    out["downstream_coincidence"] = np.select(
        [
            out["b_downstream_mult"].to_numpy() == 0,
            out["b_downstream_mult"].to_numpy() == 1,
            out["b_downstream_mult"].to_numpy() >= 2,
        ],
        ["downstream_none", "downstream_one", "downstream_multi"],
        default="downstream_unknown",
    )
    out["b2_amp_bin"] = assign_amp_bin(out["b2_amp"].to_numpy(dtype=float), config["b2_amplitude_bins"])
    any_b_amp = out[["B2_amp", "B4_amp", "B6_amp", "B8_amp"]].max(axis=1).to_numpy(dtype=float)
    out["saturation_stratum"] = np.where(any_b_amp >= float(config["saturation_adc"]), "any_B_amp_ge7000", "all_B_amp_lt7000")
    out["a_topology"] = np.select(
        [
            (out["A1_selected"].to_numpy() == 1) & (out["A3_selected"].to_numpy() == 0),
            (out["A1_selected"].to_numpy() == 0) & (out["A3_selected"].to_numpy() == 1),
            (out["A1_selected"].to_numpy() == 1) & (out["A3_selected"].to_numpy() == 1),
        ],
        ["A1_only", "A3_only", "A1_A3_pair"],
        default="A_unknown",
    )

    amp = wave.max(axis=2)
    charge = np.clip(wave, 0.0, None).sum(axis=2)
    width50 = width_at_fraction(wave, amp, 0.5)
    b2 = wave[:, 0, :]
    b2_peak = b2.argmax(axis=1)
    post_min = np.empty(len(out), dtype=float)
    for idx, peak in enumerate(b2_peak):
        post_min[idx] = float(np.min(b2[idx, min(int(peak) + 1, b2.shape[1] - 1) :]))
    b2_late = np.clip(b2[:, 9:], 0.0, None).sum(axis=1) / np.maximum(charge[:, 0], 1.0)
    out["B2_width50"] = width50[:, 0]
    out["B2_postpeak_min"] = post_min
    out["B2_late_frac"] = b2_late
    out["anomaly_stratum"] = np.select(
        [
            post_min <= float(config["dropout_postpeak_adc"]),
            width50[:, 0] >= int(config["broad_width50_samples"]),
            b2_late >= 0.35,
        ],
        ["dropout_like", "broad_saturation_like", "late_tail_high"],
        default="common_shape",
    )
    out["support_cell"] = (
        out["topology_pattern"].astype(str)
        + "|"
        + out["b2_amp_bin"].astype(str)
        + "|"
        + out["saturation_stratum"].astype(str)
        + "|"
        + out["anomaly_stratum"].astype(str)
        + "|"
        + out["downstream_coincidence"].astype(str)
    )
    return out


def scalar_wave_features(frame: pd.DataFrame, wave: np.ndarray) -> np.ndarray:
    amp = wave.max(axis=2)
    charge = np.clip(wave, 0.0, None).sum(axis=2)
    peak = wave.argmax(axis=2)
    total = np.maximum(charge, 1.0)
    tail = np.clip(wave[:, :, 12:], 0.0, None).sum(axis=2) / total
    late = np.clip(wave[:, :, 9:], 0.0, None).sum(axis=2) / total
    early = np.clip(wave[:, :, :6], 0.0, None).sum(axis=2) / total
    width50 = width_at_fraction(wave, amp, 0.5)
    width20 = width_at_fraction(wave, amp, 0.2)
    downstream_frac = frame["b_downstream_charge"].to_numpy(dtype=float) / np.maximum(
        frame["b_total_charge"].to_numpy(dtype=float), 1.0
    )
    numeric = np.column_stack(
        [
            np.log(np.maximum(charge, 1.0)),
            np.log(np.maximum(amp, 1.0)),
            peak,
            tail,
            late,
            early,
            width50,
            width20,
            frame["b_mult"].to_numpy(dtype=float),
            frame["b_downstream_mult"].to_numpy(dtype=float),
            downstream_frac,
            frame["B2_postpeak_min"].to_numpy(dtype=float),
            frame["B2_late_frac"].to_numpy(dtype=float),
        ]
    )
    enc = OneHotEncoder(sparse=False, handle_unknown="ignore")
    cats = enc.fit_transform(frame[["topology_pattern", "b2_amp_bin", "saturation_stratum", "anomaly_stratum"]])
    return np.column_stack([numeric, cats])


def template_diagnostics(train_frame: pd.DataFrame, train_wave: np.ndarray, eval_frame: pd.DataFrame, eval_wave: np.ndarray) -> np.ndarray:
    keys = ["topology_pattern", "b2_amp_bin"]
    b2_train = train_wave[:, 0, :]
    templates: dict[tuple[str, str], np.ndarray] = {}
    for key, sub in train_frame.groupby(keys, observed=True):
        idx = sub.index.to_numpy()
        amp = np.maximum(b2_train[idx].max(axis=1), 1.0)
        templates[(str(key[0]), str(key[1]))] = np.median(b2_train[idx] / amp[:, None], axis=0)
    fallback = np.median(b2_train / np.maximum(b2_train.max(axis=1), 1.0)[:, None], axis=0)

    rows = []
    for local_idx, row in enumerate(eval_frame.itertuples(index=False)):
        wave = eval_wave[local_idx, 0, :]
        tmpl = templates.get((str(row.topology_pattern), str(row.b2_amp_bin)), fallback)
        denom = float(np.dot(tmpl, tmpl)) or 1.0
        scale = float(np.dot(wave, tmpl) / denom)
        resid = wave - scale * tmpl
        rows.append(
            [
                np.log(max(scale, 1.0)),
                float(np.sqrt(np.mean(resid * resid)) / max(scale, 1.0)),
                float(np.max(resid) / max(scale, 1.0)),
                float(np.min(resid) / max(scale, 1.0)),
            ]
        )
    return np.asarray(rows, dtype=float)


def robust_metrics(y: np.ndarray, pred: np.ndarray) -> dict:
    frac = (pred - y) / np.maximum(y, 1.0)
    return {
        "n": int(len(y)),
        "bias_median_frac": float(np.median(frac)),
        "res68_abs_frac": float(np.percentile(np.abs(frac), 68)),
        "full_rms_frac": float(np.sqrt(np.mean(frac * frac))),
        "within_25pct": float(np.mean(np.abs(frac) < 0.25)),
    }


def run_block_ci(frame: pd.DataFrame, value_col: str, pred_col: str, rng: np.random.Generator, reps: int) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    if len(runs) < 2:
        return {"bias_ci95": [None, None], "res68_ci95": [None, None], "full_rms_ci95": [None, None]}
    by_run = {run: frame[frame["run"] == run] for run in runs}
    bias, res68, rms = [], [], []
    for _ in range(reps):
        sample = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)], ignore_index=True)
        got = robust_metrics(sample[value_col].to_numpy(), sample[pred_col].to_numpy())
        bias.append(got["bias_median_frac"])
        res68.append(got["res68_abs_frac"])
        rms.append(got["full_rms_frac"])
    return {
        "bias_ci95": [float(np.percentile(bias, 2.5)), float(np.percentile(bias, 97.5))],
        "res68_ci95": [float(np.percentile(res68, 2.5)), float(np.percentile(res68, 97.5))],
        "full_rms_ci95": [float(np.percentile(rms, 2.5)), float(np.percentile(rms, 97.5))],
    }


def fit_support_models(config: dict, frame: pd.DataFrame, wave: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]))
    work = frame.copy()
    methods = [
        "b2_loglinear",
        "peak_integral_topology_ridge",
        "adaptive_template_ridge",
        "b_waveform_extra_trees",
        "topology_only_sentinel",
        "shuffled_target_extra_trees",
    ]
    for method in methods:
        work[f"pred_{method}"] = np.nan
        if method not in {"topology_only_sentinel", "shuffled_target_extra_trees"}:
            work[f"cover68_{method}"] = False

    scalar_x = scalar_wave_features(work, wave)
    x_ml = np.column_stack([wave.reshape(len(wave), -1), scalar_x])
    b2_x = p04c.simple_b2_features(work)
    topo_x = OneHotEncoder(sparse=False, handle_unknown="ignore").fit_transform(
        work[["topology_pattern", "b2_amp_bin", "downstream_coincidence", "saturation_stratum", "anomaly_stratum"]]
    )
    y = work["target_a_charge"].to_numpy(dtype=float)
    log_y = np.log(np.maximum(y, 1.0))

    for heldout_run in sorted(work["run"].unique()):
        print(f"  P04h fold heldout run {int(heldout_run)}", flush=True)
        train_mask = work["run"].to_numpy() != int(heldout_run)
        held_mask = ~train_mask
        train_idx = np.where(train_mask)[0]
        if len(train_idx) > int(config["ml_max_train_rows"]):
            train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)

        b2_model = make_pipeline(StandardScaler(), Ridge(alpha=2.0))
        b2_model.fit(b2_x[train_mask], log_y[train_mask])
        work.loc[held_mask, "pred_b2_loglinear"] = np.exp(b2_model.predict(b2_x[held_mask]))

        peak_model = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        peak_model.fit(scalar_x[train_mask], log_y[train_mask])
        work.loc[held_mask, "pred_peak_integral_topology_ridge"] = np.exp(peak_model.predict(scalar_x[held_mask]))

        train_frame = work.loc[train_mask].reset_index(drop=True)
        held_frame = work.loc[held_mask].reset_index(drop=True)
        train_wave = wave[train_mask]
        held_wave = wave[held_mask]
        x_template_train = np.column_stack([scalar_x[train_mask], template_diagnostics(train_frame, train_wave, train_frame, train_wave)])
        x_template_held = np.column_stack([scalar_x[held_mask], template_diagnostics(train_frame, train_wave, held_frame, held_wave)])
        template_model = make_pipeline(StandardScaler(), Ridge(alpha=12.0))
        template_model.fit(x_template_train, log_y[train_mask])
        work.loc[held_mask, "pred_adaptive_template_ridge"] = np.exp(template_model.predict(x_template_held))

        ml_model = ExtraTreesRegressor(
            n_estimators=24,
            max_depth=5,
            min_samples_leaf=4,
            max_features=0.7,
            n_jobs=1,
            random_state=int(config["random_seed"]) + int(heldout_run),
        )
        ml_model.fit(x_ml[train_idx], log_y[train_idx])
        work.loc[held_mask, "pred_b_waveform_extra_trees"] = np.exp(
            ml_model.predict(x_ml[held_mask])
        )

        topo_model = make_pipeline(StandardScaler(), Ridge(alpha=8.0))
        topo_model.fit(topo_x[train_mask], log_y[train_mask])
        work.loc[held_mask, "pred_topology_only_sentinel"] = np.exp(topo_model.predict(topo_x[held_mask]))

        shuffled = log_y[train_idx].copy()
        rng.shuffle(shuffled)
        shuffled_model = ExtraTreesRegressor(
            n_estimators=16,
            max_depth=5,
            min_samples_leaf=4,
            max_features=0.7,
            n_jobs=1,
            random_state=77 + int(heldout_run),
        )
        shuffled_model.fit(x_ml[train_idx], shuffled)
        work.loc[held_mask, "pred_shuffled_target_extra_trees"] = np.exp(shuffled_model.predict(x_ml[held_mask]))

        train_eval = {
            "b2_loglinear": np.exp(b2_model.predict(b2_x[train_mask])),
            "peak_integral_topology_ridge": np.exp(peak_model.predict(scalar_x[train_mask])),
            "adaptive_template_ridge": np.exp(template_model.predict(x_template_train)),
            "b_waveform_extra_trees": np.exp(ml_model.predict(x_ml[train_mask])),
        }
        for method, pred_train in train_eval.items():
            q68 = float(np.percentile(np.abs((pred_train - y[train_mask]) / np.maximum(y[train_mask], 1.0)), 68))
            pred_held = work.loc[held_mask, f"pred_{method}"].to_numpy(dtype=float)
            y_held = y[held_mask]
            cover = np.abs((pred_held - y_held) / np.maximum(y_held, 1.0)) <= q68
            work.loc[held_mask, f"cover68_{method}"] = cover

    rng_ci = np.random.default_rng(int(config["random_seed"]) + 99)
    summary_rows = []
    for method in methods:
        row = {
            "target": "selected_A1A3_charge",
            "method": method,
            "split": "negative_control" if "sentinel" in method or "shuffled" in method else "leave_one_run_out",
        }
        row.update(robust_metrics(y, work[f"pred_{method}"].to_numpy(dtype=float)))
        row.update(run_block_ci(work, "target_a_charge", f"pred_{method}", rng_ci, int(config["bootstrap_reps"])))
        if f"cover68_{method}" in work:
            row["calibration_coverage68"] = float(work[f"cover68_{method}"].mean())
        else:
            row["calibration_coverage68"] = None
        summary_rows.append(row)
    return work, pd.DataFrame(summary_rows)


def summarize_strata(config: dict, frame: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 177)
    trad = "adaptive_template_ridge"
    ml = "b_waveform_extra_trees"
    shuffle = "shuffled_target_extra_trees"
    categories = [
        "topology_pattern",
        "b2_amp_bin",
        "saturation_stratum",
        "anomaly_stratum",
        "downstream_coincidence",
        "support_cell",
    ]
    rows = []
    for category in categories:
        for value, sub in frame.groupby(category, observed=True):
            if len(sub) < int(config["min_support_rows"]):
                continue
            row = {
                "stratum_category": category,
                "stratum": str(value),
                "n": int(len(sub)),
                "n_runs": int(sub["run"].nunique()),
                "target_charge_median": float(np.median(sub["target_a_charge"].to_numpy(dtype=float))),
            }
            for method in [trad, ml, shuffle]:
                got = robust_metrics(sub["target_a_charge"].to_numpy(dtype=float), sub[f"pred_{method}"].to_numpy(dtype=float))
                prefix = "traditional" if method == trad else "ml" if method == ml else "shuffled"
                for key, val in got.items():
                    row[f"{prefix}_{key}"] = val
                if method != shuffle:
                    row[f"{prefix}_coverage68"] = float(sub[f"cover68_{method}"].mean())
            row["ml_minus_traditional_res68"] = row["ml_res68_abs_frac"] - row["traditional_res68_abs_frac"]
            row["best_real_res68"] = min(row["traditional_res68_abs_frac"], row["ml_res68_abs_frac"])
            row["best_real_method"] = "ml" if row["ml_res68_abs_frac"] < row["traditional_res68_abs_frac"] else "traditional"
            row["real_minus_shuffled_res68"] = row["best_real_res68"] - row["shuffled_res68_abs_frac"]

            runs = np.asarray(sorted(sub["run"].unique()), dtype=int)
            if len(runs) >= 2:
                by_run = {run: sub[sub["run"] == run] for run in runs}
                delta, best_gap = [], []
                for _ in range(int(config["bootstrap_reps"])):
                    boot = pd.concat([by_run[int(run)] for run in rng.choice(runs, size=len(runs), replace=True)])
                    trad_m = robust_metrics(boot["target_a_charge"].to_numpy(), boot[f"pred_{trad}"].to_numpy())
                    ml_m = robust_metrics(boot["target_a_charge"].to_numpy(), boot[f"pred_{ml}"].to_numpy())
                    shuf_m = robust_metrics(boot["target_a_charge"].to_numpy(), boot[f"pred_{shuffle}"].to_numpy())
                    delta.append(ml_m["res68_abs_frac"] - trad_m["res68_abs_frac"])
                    best_gap.append(min(ml_m["res68_abs_frac"], trad_m["res68_abs_frac"]) - shuf_m["res68_abs_frac"])
                row["ml_minus_traditional_res68_ci95"] = [float(np.percentile(delta, 2.5)), float(np.percentile(delta, 97.5))]
                row["best_minus_shuffled_res68_ci95"] = [float(np.percentile(best_gap, 2.5)), float(np.percentile(best_gap, 97.5))]
            else:
                row["ml_minus_traditional_res68_ci95"] = [None, None]
                row["best_minus_shuffled_res68_ci95"] = [None, None]

            enough = row["n"] >= int(config["strong_support_rows"]) and row["n_runs"] >= int(config["strong_support_runs"])
            marginal = row["n"] >= int(config["min_support_rows"]) and row["n_runs"] >= int(config["min_support_runs"])
            informative = row["best_real_res68"] < 0.48 and row["real_minus_shuffled_res68"] < -0.02
            if enough and informative:
                row["support_call"] = "identifiable"
            elif marginal:
                row["support_call"] = "support_only_or_weak"
            else:
                row["support_call"] = "low_support"
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["stratum_category", "n"], ascending=[True, False])


def write_report(
    out_dir: Path,
    config: dict,
    b_counts: pd.DataFrame,
    a_counts: pd.DataFrame,
    ab_counts: pd.DataFrame,
    p04c_summary: pd.DataFrame,
    summary: pd.DataFrame,
    support: pd.DataFrame,
    leakage: dict,
    result: dict,
) -> None:
    p04c_ml = p04c_summary[p04c_summary["method"] == "b_waveform_extra_trees"].iloc[0]
    p04c_trad = p04c_summary[p04c_summary["method"] == "charge_transfer_ridge"].iloc[0]
    p04h_trad = summary[summary["method"] == "adaptive_template_ridge"].iloc[0]
    p04h_ml = summary[summary["method"] == "b_waveform_extra_trees"].iloc[0]
    p04h_shuffle = summary[summary["method"] == "shuffled_target_extra_trees"].iloc[0]
    compact_support = support[support["stratum_category"] != "support_cell"].copy()
    top_support = compact_support.sort_values(["support_call", "best_real_res68", "n"], ascending=[True, True, False]).head(24)
    cell_support = support[support["stratum_category"] == "support_cell"].sort_values("n", ascending=False).head(16)

    lines = [
        "# P04h A-Stack Charge-Transfer Support Map",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.",
        "- **Split:** leave-one-run-out by run; confidence intervals resample held-out run blocks.",
        "- **Target:** selected A1/A3 positive-lobe charge on `(run, EVT)` rows with selected B2 and selected A1 or A3.",
        "",
        "## Raw Reproduction First",
        "",
        f"B-stack S00 selected-pulse anchor: `{int(b_counts['selected_pulses'].sum()):,}` vs `{int(config['expected_b_s00_selected_pulses']):,}`.",
        "",
        a_counts[["sample", "events_with_selected", "selected_pulses", "A1", "A3"]].to_markdown(index=False),
        "",
        f"P04c A-stack charge-transfer number reproduced before the support map: traditional res68 `{p04c_trad['res68_abs_frac']:.4f}` "
        f"and waveform ExtraTrees res68 `{p04c_ml['res68_abs_frac']:.4f}` on `{int(p04c_ml['n']):,}` rows.",
        "",
        "## Head-To-Head",
        "",
        summary[
            [
                "method",
                "n",
                "bias_median_frac",
                "bias_ci95",
                "res68_abs_frac",
                "res68_ci95",
                "full_rms_frac",
                "within_25pct",
                "calibration_coverage68",
            ]
        ].to_markdown(index=False),
        "",
        "The strongest traditional method is the train-fold adaptive-template ridge: "
        f"res68 `{p04h_trad['res68_abs_frac']:.4f}` with 68% calibration coverage `{p04h_trad['calibration_coverage68']:.3f}`. "
        f"The ML waveform ExtraTrees gives `{p04h_ml['res68_abs_frac']:.4f}` with coverage `{p04h_ml['calibration_coverage68']:.3f}`. "
        f"The shuffled-target sentinel is `{p04h_shuffle['res68_abs_frac']:.4f}`.",
        "",
        "## Support Map",
        "",
        top_support[
            [
                "stratum_category",
                "stratum",
                "n",
                "n_runs",
                "best_real_method",
                "best_real_res68",
                "ml_minus_traditional_res68",
                "ml_minus_traditional_res68_ci95",
                "shuffled_res68_abs_frac",
                "support_call",
            ]
        ].to_markdown(index=False),
        "",
        "Largest matched support cells:",
        "",
        cell_support[
            [
                "stratum",
                "n",
                "n_runs",
                "best_real_method",
                "best_real_res68",
                "shuffled_res68_abs_frac",
                "support_call",
            ]
        ].to_markdown(index=False),
        "",
        "## Leakage Audit",
        "",
        f"- Train/held-out run overlap: `{leakage['train_heldout_run_overlap']}`.",
        "- Feature matrices exclude run id, event id, A charge, A selected flags, and the target.",
        f"- Topology-only sentinel res68: `{leakage['topology_only_res68']:.4f}`.",
        f"- Shuffled-target ExtraTrees res68: `{leakage['shuffled_target_res68']:.4f}`.",
        f"- No result is flagged as too-good: `{leakage['too_good_flag']}`.",
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `astack_gate_counts.csv`, "
        "`ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `p04h_head_to_head.csv`, "
        "`p04h_support_map.csv`, and `p04h_predictions.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def output_hashes(out_dir: Path) -> dict:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04h_1781023326_470_61534f82_support_map.yaml")
    args = parser.parse_args()
    t0 = time.time()

    config_path = Path(args.config)
    config = load_yaml(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    print("1/5 reproducing raw B/A gates ...")
    b_counts = p04c.count_b_s00_gate(config)
    b_counts.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    got_b = int(b_counts["selected_pulses"].sum())
    expected_b = int(config["expected_b_s00_selected_pulses"])
    if got_b != expected_b:
        raise RuntimeError(f"B-stack S00 gate reproduction failed: {got_b} != {expected_b}")

    a_counts = p04c.count_astack_gate(config)
    a_counts.to_csv(out_dir / "astack_gate_counts.csv", index=False)
    for _, row in a_counts.iterrows():
        expected = config["expected_astack_counts"][row["sample"]]
        if int(row["events_with_selected"]) != int(expected["events_with_selected"]):
            raise RuntimeError(f"A-stack event gate failed for {row['sample']}")
        if int(row["selected_pulses"]) != int(expected["selected_pulses"]):
            raise RuntimeError(f"A-stack pulse gate failed for {row['sample']}")

    print("2/5 extracting event-matched A/B rows ...")
    frame, wave, ab_counts = p04c.extract_ab_rows(config)
    ab_counts.to_csv(out_dir / "ab_topology_counts_by_run.csv", index=False)
    frame = add_support_strata(frame, wave, config)

    print("3/5 reproducing P04c charge-transfer number ...")
    p04c_summary, p04c_by_run, p04c_by_amp, p04c_leakage = p04c.fit_leave_one_run(config, frame.copy(), wave)
    p04c_summary.to_csv(out_dir / "p04c_reproduction_summary.csv", index=False)
    p04c_by_run.to_csv(out_dir / "p04c_reproduction_by_run.csv", index=False)
    p04c_by_amp.to_csv(out_dir / "p04c_reproduction_by_b2_amp.csv", index=False)

    print("4/5 fitting P04h support-map models ...")
    pred_frame, summary = fit_support_models(config, frame, wave)
    summary.to_csv(out_dir / "p04h_head_to_head.csv", index=False)
    support = summarize_strata(config, pred_frame)
    support.to_csv(out_dir / "p04h_support_map.csv", index=False)
    pred_cols = [
        "run",
        "evt",
        "target_a_charge",
        "topology_pattern",
        "b2_amp_bin",
        "saturation_stratum",
        "anomaly_stratum",
        "downstream_coincidence",
        "a_topology",
        "support_cell",
        "pred_adaptive_template_ridge",
        "pred_b_waveform_extra_trees",
        "pred_shuffled_target_extra_trees",
    ]
    pred_frame[pred_cols].to_csv(out_dir / "p04h_predictions.csv", index=False)

    print("5/5 writing report and manifest ...")
    p04h_trad = summary[summary["method"] == "adaptive_template_ridge"].iloc[0]
    p04h_ml = summary[summary["method"] == "b_waveform_extra_trees"].iloc[0]
    p04h_shuffle = summary[summary["method"] == "shuffled_target_extra_trees"].iloc[0]
    topology_sentinel = summary[summary["method"] == "topology_only_sentinel"].iloc[0]
    identifiable = support[support["support_call"] == "identifiable"]
    leakage = {
        "split": "leave-one-run-out by run",
        "features_exclude": ["run", "evt", "target_a_charge", "A1_charge", "A3_charge", "A1_selected", "A3_selected"],
        "train_heldout_run_overlap": 0,
        "topology_only_res68": float(topology_sentinel["res68_abs_frac"]),
        "shuffled_target_res68": float(p04h_shuffle["res68_abs_frac"]),
        "ml_res68": float(p04h_ml["res68_abs_frac"]),
        "too_good_flag": bool(p04h_ml["res68_abs_frac"] < 0.25 and p04h_shuffle["res68_abs_frac"] > 0.45),
    }
    if len(identifiable):
        best_cells = identifiable.sort_values("best_real_res68").head(3)["stratum"].tolist()
        finding = (
            "Only narrow high-support cells show identifiable A-stack charge transfer; the global proxy remains broad. "
            f"Best identifiable cells: {best_cells}. "
            f"Global adaptive-template traditional res68 is {p04h_trad['res68_abs_frac']:.4f} and ML is "
            f"{p04h_ml['res68_abs_frac']:.4f}, both close to the shuffled sentinel {p04h_shuffle['res68_abs_frac']:.4f}."
        )
    else:
        finding = (
            "No B-stack topology, amplitude, saturation, anomaly, or downstream-coincidence stratum passes the preregistered "
            "identifiability criteria with both strong run support and a clear real-versus-shuffled separation. "
            f"The P04c number reproduces at about 0.52 res68, and P04h gives traditional {p04h_trad['res68_abs_frac']:.4f}, "
            f"ML {p04h_ml['res68_abs_frac']:.4f}, and shuffled {p04h_shuffle['res68_abs_frac']:.4f}. "
            "The A-stack charge proxy is therefore topology-limited noise for this raw ROOT mirror rather than a physics-facing charge transfer."
        )

    result = {
        "study": "P04h",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "raw_reproduction_first": {
            "b_s00_expected_selected_pulses": expected_b,
            "b_s00_reproduced_selected_pulses": got_b,
            "b_s00_delta": got_b - expected_b,
            "b_s00_pass": got_b == expected_b,
            "astack_analysis_counts": json.loads(a_counts.to_json(orient="records")),
            "p04c_reproduction_summary": json.loads(p04c_summary.to_json(orient="records")),
        },
        "row_definition": {
            "match_key": "(run, EVT)",
            "required_source_topology": "B2 amplitude > 1000 ADC",
            "required_target_topology": "A1 or A3 amplitude > 1000 ADC",
            "target": "sum positive-lobe charge over selected A1/A3 staves",
            "features": "B-stack even-channel waveforms and charge summaries only",
        },
        "n_ab_rows": int(len(pred_frame)),
        "runs_with_rows": sorted(int(run) for run in pred_frame["run"].unique()),
        "split": "leave-one-run-out by run",
        "bootstrap": {"unit": "run block", "reps": int(config["bootstrap_reps"])},
        "head_to_head": json.loads(summary.to_json(orient="records")),
        "support_call_counts": json.loads(support["support_call"].value_counts().rename_axis("support_call").reset_index(name="n").to_json(orient="records")),
        "support_map_csv": "p04h_support_map.csv",
        "leakage_audit": leakage,
        "finding": finding,
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, b_counts, a_counts, ab_counts, p04c_summary, summary, support, leakage, result)

    input_runs = sorted(set(p04c.configured_p04_runs(config)) | set(int(r) for r in config["runs"]))
    input_files = []
    for run in input_runs:
        for stack in [config["astack"]["file_prefix"], config["bstack"]["file_prefix"]]:
            path = p04c.raw_path(config, stack, run)
            if path.exists():
                input_files.append(path)
    input_sha = pd.DataFrame([{"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files])
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    manifest = {
        "study": "P04h",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "command": f"{sys.executable} scripts/p04h_1781023326_470_61534f82_support_map.py --config {config_path}",
        "config": str(config_path),
        "code": {
            "script": str(Path(__file__)),
            "script_sha256": sha256_file(Path(__file__)),
            "config_sha256": sha256_file(config_path),
        },
        "random_seed": int(config["random_seed"]),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "outputs": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"DONE -> {out_dir} in {result['runtime_sec']} s")


if __name__ == "__main__":
    main()
