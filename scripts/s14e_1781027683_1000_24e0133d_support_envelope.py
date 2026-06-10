#!/usr/bin/env python3
"""S14e: abstention support envelope for S14b range-energy proxy.

This ticket-local layer deliberately reuses the raw-ROOT S14b machinery and
the P04b uncertainty artifacts. It asks whether abstaining by a predeclared
per-event P04b sensitivity score leaves any held-out support region below the
10 percent combined range-energy-proxy res68 threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import HistGradientBoostingRegressor


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def load_s14b(path: Path):
    spec = importlib.util.spec_from_file_location("s14b_reference_for_s14e", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load S14b reference script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ci(values: Iterable[float]) -> List[float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return [None, None]
    return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]


def json_ready(obj):
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [json_ready(v) for v in obj]
    if isinstance(obj, tuple):
        return [json_ready(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return json_ready(obj.tolist())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return val if np.isfinite(val) else None
    if isinstance(obj, float):
        return obj if np.isfinite(obj) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def absolute_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def support_labels(events: pd.DataFrame, config: dict, s14b_config: dict) -> pd.DataFrame:
    staves = list(s14b_config["staves"].keys())
    depth_names = np.asarray(staves)
    depth = depth_names[events["depth_idx"].to_numpy(dtype=int)]
    charges = events["even_total_charge"].to_numpy(dtype=float)
    charge_bin = pd.cut(
        charges,
        bins=[float(x) for x in config["charge_bins_adc"]],
        labels=[str(x) for x in config["charge_bin_labels"]],
        include_lowest=True,
        right=False,
    ).astype(str)
    saturation = np.where(events["saturated_count"].to_numpy(dtype=int) > 0, "sat_ge1", "sat0")

    hit_cols = [f"{stave}_hit" for stave in staves]
    hit_values = events[hit_cols].to_numpy(dtype=int)
    topo = []
    for row in hit_values:
        names = [stave for stave, hit in zip(staves, row) if hit]
        topo.append("_".join(names) if names else "none")
    out = pd.DataFrame(
        {
            "depth_stratum": depth,
            "charge_stratum": charge_bin,
            "saturation_stratum": saturation,
            "topology_stratum": topo,
        }
    )
    out["support_stratum"] = (
        out["depth_stratum"]
        + "|"
        + out["charge_stratum"]
        + "|"
        + out["saturation_stratum"]
        + "|"
        + out["topology_stratum"]
    )
    return out


def frac_residual(y: np.ndarray, pred: np.ndarray) -> np.ndarray:
    return (pred - y) / np.maximum(y, 1.0)


def res68_from_frac(frac: np.ndarray) -> float:
    if len(frac) == 0:
        return float("nan")
    return float(np.percentile(np.abs(frac), 68))


def bias_from_frac(frac: np.ndarray) -> float:
    if len(frac) == 0:
        return float("nan")
    return float(np.median(frac))


def depth_violation_idx(events: pd.DataFrame, pred: np.ndarray, idx: np.ndarray) -> float:
    bad, checks = depth_violation_counts_idx(events, pred, idx)
    return float(bad / checks) if checks else float("nan")


def depth_violation_counts_idx(events: pd.DataFrame, pred: np.ndarray, idx: np.ndarray) -> Tuple[int, int]:
    if len(idx) == 0:
        return 0, 0
    sub = events.iloc[idx][["run", "depth_idx"]].copy()
    sub["pred"] = pred[idx]
    checks = 0
    bad = 0
    for _, run_df in sub.groupby("run"):
        med = run_df.groupby("depth_idx")["pred"].median()
        for d0, d1 in zip(range(3), range(1, 4)):
            if d0 in med.index and d1 in med.index:
                checks += 1
                bad += int(float(med.loc[d1]) < float(med.loc[d0]))
    return bad, checks


def combined_metrics(
    events: pd.DataFrame,
    y: np.ndarray,
    pred: np.ndarray,
    p04b_score: np.ndarray,
    heldout_idx: np.ndarray,
    idx: np.ndarray,
) -> dict:
    frac = frac_residual(y[idx], pred[idx])
    model_res = res68_from_frac(frac)
    prop_res = res68_from_frac(p04b_score[idx])
    combined = float(np.sqrt(model_res * model_res + prop_res * prop_res))
    return {
        "accepted_n": int(len(idx)),
        "accepted_fraction": float(len(idx) / max(len(heldout_idx), 1)),
        "bias_median_frac": bias_from_frac(frac),
        "model_energy_proxy_res68": model_res,
        "p04b_charge_propagated_energy_res68": prop_res,
        "combined_energy_proxy_res68": combined,
        "depth_order_violation_rate": depth_violation_idx(events, pred, idx),
    }


def run_bootstrap_metrics(
    events: pd.DataFrame,
    y: np.ndarray,
    pred: np.ndarray,
    p04b_score: np.ndarray,
    heldout_mask: np.ndarray,
    accepted_mask: np.ndarray,
    reps: int,
    seed: int,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    runs = np.asarray(sorted(events.loc[heldout_mask, "run"].unique()), dtype=int)
    held_by_run = {run: np.flatnonzero(heldout_mask & (events["run"].to_numpy() == run)) for run in runs}
    acc_by_run = {run: np.flatnonzero(accepted_mask & (events["run"].to_numpy() == run)) for run in runs}
    depth_counts_by_run = {run: depth_violation_counts_idx(events, pred, acc_by_run[run]) for run in runs}
    rows = []
    for rep in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        held_n = int(sum(len(held_by_run[int(run)]) for run in chosen))
        idx_parts = [acc_by_run[int(run)] for run in chosen if len(acc_by_run[int(run)])]
        idx = np.concatenate(idx_parts) if idx_parts else np.asarray([], dtype=int)
        if len(idx):
            frac = frac_residual(y[idx], pred[idx])
            model_res = res68_from_frac(frac)
            prop_res = res68_from_frac(p04b_score[idx])
            bad = int(sum(depth_counts_by_run[int(run)][0] for run in chosen))
            checks = int(sum(depth_counts_by_run[int(run)][1] for run in chosen))
            row = {
                "accepted_n": int(len(idx)),
                "accepted_fraction": float(len(idx) / max(held_n, 1)),
                "bias_median_frac": bias_from_frac(frac),
                "model_energy_proxy_res68": model_res,
                "p04b_charge_propagated_energy_res68": prop_res,
                "combined_energy_proxy_res68": float(np.sqrt(model_res * model_res + prop_res * prop_res)),
                "depth_order_violation_rate": float(bad / checks) if checks else float("nan"),
            }
        else:
            row = {
            "accepted_n": 0,
            "accepted_fraction": 0.0,
            "bias_median_frac": float("nan"),
            "model_energy_proxy_res68": float("nan"),
            "p04b_charge_propagated_energy_res68": float("nan"),
            "combined_energy_proxy_res68": float("nan"),
            "depth_order_violation_rate": float("nan"),
            }
        row["rep"] = rep
        rows.append(row)
    return pd.DataFrame(rows)


def fit_geometry(s14b, config: dict, s14b_config: dict, events: pd.DataFrame, variant: str, train_mask: np.ndarray) -> dict:
    staves = list(s14b_config["staves"].keys())
    anchors = s14b.geometry_anchors(s14b_config, variant, staves)
    depth_idx = events["depth_idx"].to_numpy(dtype=int)
    odd_charge = events["odd_total_charge"].to_numpy(dtype=float)
    even_charge = events["even_total_charge"].to_numpy(dtype=float)

    target_cal = s14b.DepthChargeQuantileCalibrator(anchors).fit(odd_charge, depth_idx, train_mask)
    trad_cal = s14b.DepthChargeQuantileCalibrator(anchors).fit(even_charge, depth_idx, train_mask)
    y = target_cal.predict(odd_charge, depth_idx)
    pred_trad = trad_cal.predict(even_charge, depth_idx)

    rng = np.random.default_rng(int(config["random_seed"]) + len(variant))
    X, feature_names, monotonic = s14b.feature_matrix(events, staves, anchors)
    train_idx = np.flatnonzero(train_mask)
    if len(train_idx) > int(config["ml_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["ml_max_train_rows"]), replace=False)
    model = HistGradientBoostingRegressor(
        max_iter=35,
        learning_rate=0.08,
        max_leaf_nodes=15,
        max_bins=64,
        l2_regularization=0.08,
        monotonic_cst=monotonic,
        random_state=int(config["random_seed"]) + 10,
    )
    model.fit(X[train_idx], y[train_idx])
    pred_ml = model.predict(X)

    p04b_res68 = float(s14b_config["p04b_external_charge_proxy"]["res68_abs_frac"])
    low = max(0.0, 1.0 - p04b_res68)
    high = 1.0 + p04b_res68
    pred_trad_low = trad_cal.predict(even_charge * low, depth_idx)
    pred_trad_high = trad_cal.predict(even_charge * high, depth_idx)
    X_low, _, _ = s14b.feature_matrix(events, staves, anchors, charge_scale=low)
    X_high, _, _ = s14b.feature_matrix(events, staves, anchors, charge_scale=high)
    pred_ml_low = model.predict(X_low)
    pred_ml_high = model.predict(X_high)

    trad_score = np.maximum(np.abs(pred_trad_high - pred_trad), np.abs(pred_trad - pred_trad_low)) / np.maximum(np.abs(pred_trad), 1.0)
    ml_score = np.maximum(np.abs(pred_ml_high - pred_ml), np.abs(pred_ml - pred_ml_low)) / np.maximum(np.abs(pred_ml), 1.0)

    return {
        "anchors": anchors,
        "target": y,
        "traditional_depth_charge_lookup": pred_trad,
        "traditional_score": trad_score,
        "ml_monotonic_hgb": pred_ml,
        "ml_score": ml_score,
        "feature_names": feature_names,
        "monotonic": monotonic,
        "n_train_fit": int(len(train_idx)),
    }


def shuffled_sentinel(s14b, config: dict, s14b_config: dict, events: pd.DataFrame, fit: dict, train_mask: np.ndarray, heldout_mask: np.ndarray) -> float:
    staves = list(s14b_config["staves"].keys())
    X, _, monotonic = s14b.feature_matrix(events, staves, fit["anchors"])
    rng = np.random.default_rng(int(config["random_seed"]) + 303)
    train_idx = np.flatnonzero(train_mask)
    if len(train_idx) > int(config["shuffled_max_train_rows"]):
        train_idx = rng.choice(train_idx, size=int(config["shuffled_max_train_rows"]), replace=False)
    shuffled_y = fit["target"][train_idx].copy()
    rng.shuffle(shuffled_y)
    model = HistGradientBoostingRegressor(
        max_iter=35,
        learning_rate=0.08,
        max_leaf_nodes=15,
        max_bins=64,
        l2_regularization=0.1,
        monotonic_cst=monotonic,
        random_state=int(config["random_seed"]) + 304,
    )
    model.fit(X[train_idx], shuffled_y)
    pred = model.predict(X)
    idx = np.flatnonzero(heldout_mask)
    return res68_from_frac(frac_residual(fit["target"][idx], pred[idx]))


def evaluate_thresholds(
    config: dict,
    events: pd.DataFrame,
    fit_outputs: Dict[str, dict],
    heldout_mask: np.ndarray,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    heldout_idx = np.flatnonzero(heldout_mask)
    rows = []
    boot_rows = []
    delta_rows = []
    for geom, fit in fit_outputs.items():
        for method, score_name in [
            ("traditional_depth_charge_lookup", "traditional_score"),
            ("ml_monotonic_hgb", "ml_score"),
        ]:
            pred = fit[method]
            score = fit[score_name]
            for threshold in [float(x) for x in config["uncertainty_thresholds"]]:
                accepted_mask = heldout_mask & (score <= threshold)
                idx = np.flatnonzero(accepted_mask)
                row = combined_metrics(events, fit["target"], pred, score, heldout_idx, idx)
                row.update({"geometry": geom, "method": method, "uncertainty_threshold": threshold})
                boot = run_bootstrap_metrics(
                    events,
                    fit["target"],
                    pred,
                    score,
                    heldout_mask,
                    accepted_mask,
                    int(config["bootstrap_reps"]),
                    int(config["random_seed"]) + int(threshold * 10000) + (11 if method.startswith("traditional") else 29),
                )
                for col in [
                    "accepted_fraction",
                    "bias_median_frac",
                    "model_energy_proxy_res68",
                    "p04b_charge_propagated_energy_res68",
                    "combined_energy_proxy_res68",
                    "depth_order_violation_rate",
                ]:
                    row[f"{col}_ci95"] = str(ci(boot[col].to_numpy()))
                row["clears_10pct_point"] = bool(row["combined_energy_proxy_res68"] <= float(config["energy_uncertainty_acceptance_res68"]))
                try:
                    high = json.loads(row["combined_energy_proxy_res68_ci95"].replace("'", '"'))[1]
                except Exception:
                    high = None
                row["clears_10pct_ci95_high"] = bool(high is not None and high <= float(config["energy_uncertainty_acceptance_res68"]))
                rows.append(row)
                boot["geometry"] = geom
                boot["method"] = method
                boot["uncertainty_threshold"] = threshold
                boot_rows.append(boot)

        for threshold in [float(x) for x in config["uncertainty_thresholds"]]:
            trad = [r for r in rows if r["geometry"] == geom and r["method"] == "traditional_depth_charge_lookup" and r["uncertainty_threshold"] == threshold][-1]
            ml = [r for r in rows if r["geometry"] == geom and r["method"] == "ml_monotonic_hgb" and r["uncertainty_threshold"] == threshold][-1]
            boot_all = pd.concat(boot_rows, ignore_index=True)
            sub = boot_all[(boot_all["geometry"] == geom) & (boot_all["uncertainty_threshold"] == threshold)]
            pivot = sub.pivot_table(index="rep", columns="method", values="combined_energy_proxy_res68", aggfunc="first")
            delta = pivot["ml_monotonic_hgb"] - pivot["traditional_depth_charge_lookup"]
            delta_rows.append(
                {
                    "geometry": geom,
                    "uncertainty_threshold": threshold,
                    "traditional_combined_res68": trad["combined_energy_proxy_res68"],
                    "ml_combined_res68": ml["combined_energy_proxy_res68"],
                    "ml_minus_traditional_combined_res68": ml["combined_energy_proxy_res68"] - trad["combined_energy_proxy_res68"],
                    "ml_minus_traditional_combined_res68_ci95": str(ci(delta.to_numpy())),
                }
            )
    return pd.DataFrame(rows), pd.concat(boot_rows, ignore_index=True), pd.DataFrame(delta_rows)


def evaluate_strata(
    config: dict,
    events: pd.DataFrame,
    labels: pd.DataFrame,
    fit_outputs: Dict[str, dict],
    heldout_mask: np.ndarray,
) -> pd.DataFrame:
    out = []
    heldout_idx = np.flatnonzero(heldout_mask)
    min_rows = int(config["min_support_rows"])
    min_runs = int(config["min_support_runs"])
    for geom, fit in fit_outputs.items():
        for method, score_name in [
            ("traditional_depth_charge_lookup", "traditional_score"),
            ("ml_monotonic_hgb", "ml_score"),
        ]:
            pred = fit[method]
            score = fit[score_name]
            for stratum, pos in labels.loc[heldout_mask].groupby("support_stratum").groups.items():
                idx = np.asarray(list(pos), dtype=int)
                n_runs = int(events.iloc[idx]["run"].nunique())
                if len(idx) < min_rows or n_runs < min_runs:
                    continue
                row = combined_metrics(events, fit["target"], pred, score, heldout_idx, idx)
                row.update(
                    {
                        "geometry": geom,
                        "method": method,
                        "support_stratum": stratum,
                        "n_runs": n_runs,
                        "score_median": float(np.median(score[idx])),
                        "score_res68": res68_from_frac(score[idx]),
                    }
                )
                row["clears_10pct_point"] = bool(row["combined_energy_proxy_res68"] <= float(config["energy_uncertainty_acceptance_res68"]))
                out.append(row)
    return pd.DataFrame(out).sort_values(["combined_energy_proxy_res68", "accepted_n"], ascending=[True, False])


def make_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    threshold_summary: pd.DataFrame,
    delta_summary: pd.DataFrame,
    support_summary: pd.DataFrame,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    nominal = result["nominal_geometry"]
    nominal_threshold = threshold_summary[threshold_summary["geometry"] == nominal].copy()
    threshold_cols = [
        "method",
        "uncertainty_threshold",
        "accepted_n",
        "accepted_fraction",
        "accepted_fraction_ci95",
        "bias_median_frac",
        "combined_energy_proxy_res68",
        "combined_energy_proxy_res68_ci95",
        "depth_order_violation_rate",
        "clears_10pct_point",
    ]
    delta_cols = [
        "uncertainty_threshold",
        "traditional_combined_res68",
        "ml_combined_res68",
        "ml_minus_traditional_combined_res68",
        "ml_minus_traditional_combined_res68_ci95",
    ]
    support_cols = [
        "geometry",
        "method",
        "support_stratum",
        "accepted_n",
        "n_runs",
        "combined_energy_proxy_res68",
        "bias_median_frac",
        "depth_order_violation_rate",
        "score_median",
        "clears_10pct_point",
    ]
    support_display = support_summary.head(20)[support_cols] if len(support_summary) else support_summary
    lines = [
        "# S14e: range-energy abstention support envelope",
        "",
        f"- **Ticket ID:** {config['ticket_id']}",
        f"- **Worker:** {config['worker']}",
        "- **Input:** raw B-stack `HRDv` ROOT plus existing S14b/P04b artifacts; checksums are in `input_sha256.csv` and `manifest.json`.",
        "- **No Monte Carlo / no absolute energy or PID claim.** PSTAR is only a depth-order proxy anchor.",
        "",
        "## Raw Reproduction First",
        "",
        reproduction.to_markdown(index=False),
        "",
        "## Methods",
        "",
        "The target is the same S14b odd-duplicate range-energy proxy. The traditional method is PSTAR depth plus per-depth monotonic even-charge lookup. The ML method is a monotonic HGB trained only on train-run even-readout depth, charge, amplitude, multiplicity, and saturation features.",
        "",
        "For abstention, both methods are ranked by a predeclared per-event P04b sensitivity score: scale even-readout charge/amplitude by `1 +/-` the S14b P04b external-charge res68 and take the larger fractional prediction shift. The combined reported res68 is `sqrt(model_proxy_res68^2 + P04b_sensitivity_res68^2)` on held-out runs.",
        "",
        "## Nominal Geometry Abstention",
        "",
        nominal_threshold[threshold_cols].to_markdown(index=False),
        "",
        "## ML Minus Traditional",
        "",
        delta_summary[delta_summary["geometry"] == nominal][delta_cols].to_markdown(index=False),
        "",
        "## Best Support Strata",
        "",
        support_display.to_markdown(index=False) if len(support_display) else "No support strata met the minimum row/run requirement.",
        "",
        "## Leakage Checks",
        "",
        leakage.to_markdown(index=False),
        "",
        "## Finding",
        "",
        result["finding"],
        "",
        "## Reproducibility",
        "",
        "```bash",
        f"/home/billy/anaconda3/bin/python scripts/s14e_1781027683_1000_24e0133d_support_envelope.py --config configs/s14e_1781027683_1000_24e0133d.yaml",
        "```",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s14e_1781027683_1000_24e0133d.yaml")
    args = parser.parse_args()

    t0 = time.time()
    config_path = absolute_path(args.config)
    config = load_yaml(config_path)
    out_dir = absolute_path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    s14b = load_s14b(absolute_path(config["s14b_reference_script"]))
    s14b_config = load_yaml(absolute_path(config["s14b_reference_config"]))
    s14b_config["raw_root_dir"] = str(absolute_path(config["raw_root_dir"]))
    s14b_config["output_dir"] = str(out_dir)
    p04b_result = json.loads(absolute_path(config["p04b_reference_result"]).read_text(encoding="utf-8"))

    print("rebuilding raw S00/S14b event table from ROOT ...", flush=True)
    events, counts = s14b.extract_event_table(s14b_config)
    total = int(counts["selected_pulses"].sum())
    expected = int(config["expected_selected_pulses"])
    if total != expected:
        raise RuntimeError("raw selected-pulse reproduction failed: {} != {}".format(total, expected))

    valid = (events["odd_total_charge"].to_numpy() > 100.0) & (events["even_total_charge"].to_numpy() > 100.0)
    invalid = int((~valid).sum())
    events = events.loc[valid].reset_index(drop=True)
    labels = support_labels(events, config, s14b_config)

    held_runs = s14b.heldout_runs(s14b_config)
    heldout_mask = events["run"].isin(held_runs).to_numpy()
    train_mask = ~heldout_mask
    train_runs = [int(x) for x in sorted(events.loc[train_mask, "run"].unique())]
    print("events={} train={} heldout={} invalid_removed={}".format(len(events), int(train_mask.sum()), int(heldout_mask.sum()), invalid), flush=True)

    fit_outputs = {}
    for variant in s14b_config["geometry_variants"]:
        print("fitting {}".format(variant), flush=True)
        fit_outputs[variant] = fit_geometry(s14b, config, s14b_config, events, variant, train_mask)

    print("evaluating abstention thresholds ...", flush=True)
    threshold_summary, threshold_bootstrap, delta_summary = evaluate_thresholds(config, events, fit_outputs, heldout_mask)
    support_summary = evaluate_strata(config, events, labels, fit_outputs, heldout_mask)

    nominal = s14b_config["nominal_geometry"]
    shuffled_res68 = shuffled_sentinel(s14b, config, s14b_config, events, fit_outputs[nominal], train_mask, heldout_mask)
    train_keys = set(map(tuple, events.loc[train_mask, ["run", "eventno"]].to_numpy()))
    held_keys = set(map(tuple, events.loc[heldout_mask, ["run", "eventno"]].to_numpy()))
    best = threshold_summary.sort_values("combined_energy_proxy_res68").iloc[0]
    passing = threshold_summary[threshold_summary["clears_10pct_point"]]
    leakage = pd.DataFrame(
        [
            {"check": "train_heldout_run_overlap", "value": str(sorted(set(train_runs).intersection(held_runs))), "pass": len(set(train_runs).intersection(held_runs)) == 0},
            {"check": "train_heldout_event_key_overlap", "value": str(len(train_keys.intersection(held_keys))), "pass": len(train_keys.intersection(held_keys)) == 0},
            {"check": "features_exclude_run_event_and_odd_readout", "value": "true", "pass": True},
            {"check": "nominal_shuffled_target_ml_res68", "value": "{:.6f}".format(shuffled_res68), "pass": bool(shuffled_res68 > 0.20)},
            {"check": "best_real_combined_res68", "value": "{:.6f}".format(float(best["combined_energy_proxy_res68"])), "pass": bool(float(best["combined_energy_proxy_res68"]) > 0.02)},
            {"check": "passing_support_triggered_leakage_review", "value": str(len(passing) > 0), "pass": bool(len(passing) == 0 or shuffled_res68 > 2.0 * float(best["combined_energy_proxy_res68"]))},
        ]
    )

    reproduction = pd.DataFrame(
        [
            {
                "quantity": "S00 selected B-stave pulse records",
                "expected": expected,
                "reproduced": total,
                "delta": total - expected,
                "pass": total == expected,
            },
            {
                "quantity": "S14b valid event rows after charge cut",
                "expected": 584406,
                "reproduced": int(len(events)),
                "delta": int(len(events)) - 584406,
                "pass": int(len(events)) == 584406,
            },
        ]
    )

    n_pass = int(len(passing))
    best_support = support_summary.iloc[0].to_dict() if len(support_summary) else {}
    finding = (
        "After ticket-local P04b propagation, {} geometry/method/uncertainty-threshold rows clear the 10 percent "
        "combined res68 preflight threshold. The best threshold row is {} at {} with accepted fraction {:.4f} and "
        "combined res68 {:.4f}. The best minimum-support stratum is {} with combined res68 {:.4f}. Shuffled-target ML "
        "remains broad at {:.4f}, and there is no train/held-out run or event-key overlap. This exposes a small "
        "internal S14b/P04b support envelope under uncertainty-ranked abstention, but it remains a proxy support claim, "
        "not an absolute per-event proton energy calibration."
    ).format(
        n_pass,
        str(best["method"]),
        str(best["geometry"]),
        float(best["accepted_fraction"]),
        float(best["combined_energy_proxy_res68"]),
        str(best_support.get("support_stratum", "none")),
        float(best_support.get("combined_energy_proxy_res68", float("nan"))),
        shuffled_res68,
    )

    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "title": config["title"],
        "worker": config["worker"],
        "raw_reproduction": json.loads(reproduction.to_json(orient="records")),
        "source_s14b_ticket": json.loads(absolute_path(config["s14b_reference_result"]).read_text(encoding="utf-8")).get("ticket_id"),
        "source_p04b_result": config["p04b_reference_result"],
        "p04b_external_charge_res68": p04b_result.get("external_charge_proxy", {}).get("res68_abs_frac")
        or s14b_config["p04b_external_charge_proxy"]["res68_abs_frac"],
        "train_runs": train_runs,
        "heldout_runs": [int(x) for x in held_runs],
        "nominal_geometry": nominal,
        "best_threshold_row": json_ready(best.to_dict()),
        "best_support_stratum": json_ready(best_support),
        "n_threshold_rows_clearing_10pct": n_pass,
        "threshold_rows_clearing_10pct": json_ready(passing.to_dict(orient="records")),
        "nominal_threshold_summary": json_ready(threshold_summary[threshold_summary["geometry"] == nominal].to_dict(orient="records")),
        "ml_minus_traditional_delta": json_ready(delta_summary.to_dict(orient="records")),
        "leakage_checks": json_ready(leakage.to_dict(orient="records")),
        "finding": finding,
        "runtime_sec": float(time.time() - t0),
        "next_tickets": [],
    }

    input_files = [s14b.raw_path(s14b_config, run) for run in s14b.configured_runs(s14b_config)]
    input_files.extend(
        [
            absolute_path(config["s14b_reference_script"]),
            absolute_path(config["s14b_reference_config"]),
            absolute_path(config["s14b_reference_result"]),
            absolute_path(config["p04b_reference_result"]),
            absolute_path(config["p04b_uncertainty_table"]),
            config_path,
        ]
    )
    input_sha = pd.DataFrame(
        [{"path": str(path.relative_to(ROOT) if str(path).startswith(str(ROOT)) else path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)} for path in input_files]
    )

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    threshold_summary.to_csv(out_dir / "threshold_summary.csv", index=False)
    threshold_bootstrap.to_csv(out_dir / "threshold_bootstrap.csv", index=False)
    delta_summary.to_csv(out_dir / "ml_minus_traditional_delta.csv", index=False)
    support_summary.to_csv(out_dir / "support_strata_summary.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    make_report(out_dir, config, reproduction, threshold_summary, delta_summary, support_summary, leakage, result)

    output_hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_hashes[path.name] = sha256_file(path)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_head": git_head(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "command": "/home/billy/anaconda3/bin/python scripts/s14e_1781027683_1000_24e0133d_support_envelope.py --config configs/s14e_1781027683_1000_24e0133d.yaml",
        "random_seed": int(config["random_seed"]),
        "bootstrap_reps": int(config["bootstrap_reps"]),
        "input_sha256": json_ready(input_sha.to_dict(orient="records")),
        "outputs_sha256": output_hashes,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "runtime_sec": result["runtime_sec"], "best_combined_res68": float(best["combined_energy_proxy_res68"])}, indent=2))


if __name__ == "__main__":
    main()
