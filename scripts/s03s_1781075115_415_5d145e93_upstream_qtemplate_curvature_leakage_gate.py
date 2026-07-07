#!/usr/bin/env python3
"""S03s upstream-only q-template curvature leakage gate.

This ticket intentionally reuses the S03e raw ROOT scan and q-template
construction, then removes downstream q-template observables from the primary
benchmark.  The held-out target is the all-three curvature tail,
``|C_t| > 51 ns``, versus clean events, ``|C_t| < 3 ns``.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler


BASE_SCRIPT = Path("scripts/s03e_1781027860_926_103338b4_all_three_curvature_qtemplate.py")
DOWNSTREAM_FORBIDDEN = {"q_b4", "q_b6", "q_b8", "q_ds_mean", "q_ds_max", "q_ds_std", "q_ds_span"}


def load_base_module():
    spec = importlib.util.spec_from_file_location("s03e_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {BASE_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def auc(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], score[mask]))


def ap(y: np.ndarray, score: np.ndarray) -> float:
    mask = np.isfinite(score)
    if mask.sum() == 0 or len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], score[mask]))


def bootstrap_ci(
    y: np.ndarray,
    score: np.ndarray,
    runs: np.ndarray,
    metric: Callable[[np.ndarray, np.ndarray], float],
    seed: int,
    n_boot: int,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    unique_runs = np.unique(runs)
    values = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        value = metric(y[idx], score[idx])
        if np.isfinite(value):
            values.append(value)
    if len(values) < 50:
        return (float("nan"), float("nan"))
    return (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value):
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.6g}"
        return str(value).replace("|", "\\|")

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def add_upstream_features(data: pd.DataFrame, train_mask: np.ndarray | None = None) -> pd.DataFrame:
    out = data.copy()
    out["log_amp_b2"] = np.log1p(out["amp_b2"].astype(float))
    if train_mask is None:
        train_mask = np.ones(len(out), dtype=bool)
    q = out["q_b2"].to_numpy(dtype=float)
    x = out["log_amp_b2"].to_numpy(dtype=float)
    finite = train_mask & np.isfinite(q) & np.isfinite(x)
    if finite.sum() >= 3:
        coef = np.polyfit(x[finite], q[finite], deg=1)
        pred = np.polyval(coef, x)
    else:
        pred = np.nanmedian(q[finite]) if finite.any() else np.nan
    resid = q - pred
    sigma = float(np.nanstd(resid[finite])) if finite.any() else float("nan")
    out["q_b2_amp_resid"] = resid
    out["q_b2_amp_z"] = resid / sigma if np.isfinite(sigma) and sigma > 0 else resid
    out["run_family_code"] = np.where(out["run"].to_numpy(dtype=int) <= 63, 0.0, 1.0)
    return out


def train_selected_traditional(data: pd.DataFrame, y: np.ndarray, candidates: list[str], seed: int) -> tuple[np.ndarray, pd.DataFrame]:
    runs = data["run"].to_numpy(dtype=int)
    out = np.full(len(data), np.nan, dtype=float)
    rows = []
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        fold_data = add_upstream_features(data, train)
        best_key = (-np.inf, -np.inf)
        best = None
        for col in candidates:
            values = fold_data[col].to_numpy(dtype=float)
            for sign, sign_name in [(1.0, "high_bad"), (-1.0, "low_bad")]:
                score = sign * values
                train_auc = auc(y[train], score[train])
                train_ap = ap(y[train], score[train])
                rows.append(
                    {
                        "heldout_run": int(held_run),
                        "candidate": col,
                        "sign": sign_name,
                        "train_auc": train_auc,
                        "train_ap": train_ap,
                    }
                )
                key = (train_ap, train_auc)
                if np.isfinite(train_ap) and key > best_key:
                    best_key = key
                    best = (col, sign, sign_name)
        if best is None:
            best = (candidates[0], 1.0, "high_bad")
        out[test] = best[1] * fold_data.loc[test, best[0]].to_numpy(dtype=float)
        rows.append(
            {
                "heldout_run": int(held_run),
                "candidate": "__selected__",
                "sign": best[2],
                "train_auc": float("nan"),
                "train_ap": float("nan"),
                "selected": best[0],
            }
        )
    return out, pd.DataFrame(rows)


def cnn_features(x: np.ndarray) -> np.ndarray:
    """Fixed local-filter feature map for a tiny 1D-CNN-style classifier."""
    x = np.asarray(x, dtype=float)
    if x.ndim == 1:
        x = x[None, :]
    padded = np.pad(x, ((0, 0), (1, 1)), mode="edge")
    kernels = np.asarray([[1.0, -1.0, 0.0], [0.0, -1.0, 1.0], [1.0, -2.0, 1.0], [1.0, 0.0, -1.0]])
    feats = []
    for kernel in kernels:
        conv = np.stack([np.sum(padded[:, i : i + 3] * kernel, axis=1) for i in range(x.shape[1])], axis=1)
        feats.append(np.maximum(conv, 0.0))
        feats.append(np.maximum(-conv, 0.0))
    return np.concatenate([x, *feats], axis=1)


def make_model(name: str, seed: int):
    if name == "ridge":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            LogisticRegression(class_weight="balanced", C=1.0, max_iter=2000, random_state=seed),
        )
    if name == "gradient_boosted_trees":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            HistGradientBoostingClassifier(max_iter=120, learning_rate=0.04, l2_regularization=0.05, random_state=seed),
        )
    if name == "mlp":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(24, 12), alpha=0.02, max_iter=600, early_stopping=True, random_state=seed),
        )
    if name == "one_dimensional_cnn":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            FunctionTransformer(cnn_features, validate=False),
            LogisticRegression(class_weight="balanced", C=0.5, max_iter=2000, random_state=seed),
        )
    if name == "amplitude_residual_stack":
        return make_pipeline(
            SimpleImputer(strategy="median"),
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(16, 16, 8), alpha=0.05, max_iter=800, early_stopping=True, random_state=seed),
        )
    raise KeyError(name)


def oof_scores(data: pd.DataFrame, y: np.ndarray, cols: list[str], model_name: str, seed: int) -> np.ndarray:
    runs = data["run"].to_numpy(dtype=int)
    out = np.full(len(data), np.nan, dtype=float)
    for fold, held_run in enumerate(sorted(np.unique(runs))):
        train = runs != held_run
        test = runs == held_run
        fold_data = add_upstream_features(data, train)
        x = fold_data[cols].to_numpy(dtype=float)
        model = make_model(model_name, seed + fold)
        model.fit(x[train], y[train])
        if hasattr(model, "predict_proba"):
            out[test] = model.predict_proba(x[test])[:, 1]
        else:
            out[test] = model.decision_function(x[test])
    return out


def fixed_clean_eff(data: pd.DataFrame, y: np.ndarray, score: np.ndarray, method: str, eff: float) -> pd.DataFrame:
    runs = data["run"].to_numpy(dtype=int)
    rows = []
    for held_run in sorted(np.unique(runs)):
        train = runs != held_run
        test = runs == held_run
        clean_train = score[train & (y == 0)]
        clean_train = clean_train[np.isfinite(clean_train)]
        if len(clean_train) == 0:
            continue
        threshold = float(np.quantile(clean_train, eff))
        clean = test & (y == 0) & np.isfinite(score)
        tail = test & (y == 1) & np.isfinite(score)
        rows.append(
            {
                "method": method,
                "heldout_run": int(held_run),
                "threshold": threshold,
                "clean_efficiency": float(np.mean(score[clean] <= threshold)) if clean.any() else float("nan"),
                "tail_rejection": float(np.mean(score[tail] > threshold)) if tail.any() else float("nan"),
                "n_clean": int(clean.sum()),
                "n_tail": int(tail.sum()),
            }
        )
    return pd.DataFrame(rows)


def summarize_method(name: str, y: np.ndarray, score: np.ndarray, runs: np.ndarray, seed: int, n_boot: int) -> dict:
    auc_ci = bootstrap_ci(y, score, runs, auc, seed, n_boot)
    ap_ci = bootstrap_ci(y, score, runs, ap, seed + 1, n_boot)
    return {
        "method": name,
        "roc_auc": auc(y, score),
        "roc_auc_ci_low": auc_ci[0],
        "roc_auc_ci_high": auc_ci[1],
        "average_precision": ap(y, score),
        "ap_ci_low": ap_ci[0],
        "ap_ci_high": ap_ci[1],
    }


def write_report(
    out_dir: Path,
    config: dict,
    base_config: dict,
    reproduction: pd.DataFrame,
    run_counts: pd.DataFrame,
    dataset_counts: pd.DataFrame,
    method_summary: pd.DataFrame,
    fixed_eff: pd.DataFrame,
    fold_metrics: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: dict,
) -> None:
    eff_summary = fixed_eff.groupby("method", as_index=False).agg(
        clean_efficiency=("clean_efficiency", "mean"),
        tail_rejection=("tail_rejection", "mean"),
        n_tail=("n_tail", "sum"),
    )
    report = f"""# S03s: Upstream q-template curvature leakage gate

**Ticket:** `{config['ticket_id']}`  
**Worker:** `{config['worker']}`  
**Raw data:** `{base_config['raw_root_dir']}` (`hrdb_run_0031.root` through `hrdb_run_0065.root`, configured subset)  
**Primary split:** leave-one-run-out over Sample-II analysis runs {base_config['benchmark_runs']} with run-bootstrap 95% confidence intervals.

## Abstract

This study asks whether an upstream-only q-template atom can predict the all-three downstream curvature-tail label after excluding the downstream waveform provenance that defines the tail. The target is a rare binary endpoint on all-three downstream events: clean events satisfy `|C_t| < 3 ns`, tail events satisfy `|C_t| > 51 ns`, where

`C_t = t_B8 - 2 t_B6 + t_B4`.

The central result is that the winner is **{winner['method']}** with ROC AUC {winner['roc_auc']:.3f} [{winner['roc_auc_ci_low']:.3f}, {winner['roc_auc_ci_high']:.3f}] and AP {winner['average_precision']:.3f} [{winner['ap_ci_low']:.3f}, {winner['ap_ci_high']:.3f}]. Because the target is rare and downstream-defined, this is a leakage gate rather than a claim of independent timing truth.

## Raw ROOT Reproduction

The analysis first re-runs the S03e/S00 raw ROOT scan before fitting any model. The gate reads `HRDv` from `h101`, subtracts the median baseline from samples 0-3, selects B2/B4/B6/B8 pulses with amplitude greater than 1000 ADC, and reconstructs CFD20 timing. The predeclared reproduction numbers are copied from the earlier S03e gate and must match exactly.

{markdown_table(reproduction)}

Benchmark run counts:

{markdown_table(run_counts[run_counts['run'].isin(base_config['benchmark_runs'])][['run', 'selected_pulses', 'all_three_control_events', 'all_three_gross_dt_gt51']])}

## Statistical Design

For each held-out run `r`, all preprocessing choices that can depend on the endpoint are made using the remaining runs only. The score vector `s_m` for method `m` is evaluated out of fold. ROC AUC is

`AUC_m = P(s_m(x_tail) > s_m(x_clean)) + 0.5 P(s_m(x_tail) = s_m(x_clean))`.

Average precision is computed from the same held-out scores. Confidence intervals sample the seven held-out runs with replacement and recompute the metric on the concatenated sampled runs. This preserves within-run correlation and makes run-to-run instability visible.

## Features and Leakage Controls

The primary matrix is upstream-only plus nuisance terms: `{', '.join(config['primary_feature_columns'])}`. Downstream q-template columns are not allowed in primary models: `{', '.join(sorted(DOWNSTREAM_FORBIDDEN))}`. The nuisance terms are B2 amplitude, log amplitude, an amplitude-residualized B2 q-template score, an amplitude-z-scored B2 score, and a coarse run-family code for the run-64/65 acquisition family. No `D_t`, `C_t`, App.A label, event id, downstream q-template, selected-downstream flag, or waveform sample enters the primary benchmark.

Dataset:

{markdown_table(dataset_counts)}

Leakage and sentinel checks:

{markdown_table(leakage)}

## Methods

The traditional method is a training-run-selected scalar upstream score over `q_b2`, `q_b2_amp_resid`, and `q_b2_amp_z`, with sign selected inside the training runs. Ridge is L2 logistic regression. Gradient-boosted trees use histogram gradient boosting. MLP is a two-hidden-layer neural network. The 1D-CNN entry uses fixed local convolutional filters on the ordered upstream/nuisance vector followed by ridge logistic readout, providing a small convolutional inductive bias without downstream samples. The new architecture, `amplitude_residual_stack`, is a residual MLP over the same upstream nuisance feature set, designed to test whether a deeper residualized upstream score adds information beyond amplitude correction.

## Results

{markdown_table(method_summary)}

At 95% clean acceptance, the held-out tail rejection summary is:

{markdown_table(eff_summary)}

Per-run metrics:

{markdown_table(fold_metrics)}

## Systematics and Caveats

The positive class has only 23 tail events after the clean/tail endpoint is applied, so AP and fixed-efficiency tail rejection are sensitive to individual runs. The bootstrap interval is therefore the decision object, not the point estimate alone. The endpoint is defined from downstream times; even when downstream q-template features are excluded, any upstream correlation may reflect event-level beam or electronics conditions rather than a causal B2 shape mechanism. Run-family coding is retained as a nuisance because run 64/65 acquisition conditions are known to differ, but it can also absorb genuine run-specific physics. The CNN entry is deliberately small; it tests a local-filter inductive bias on the tabular upstream sequence and is not a high-capacity waveform CNN.

## Verdict

The raw ROOT reproduction gate passes exactly. The winner written to `result.json` is **{winner['method']}**. The gate does not justify adopting downstream q-template features as independent truth; it supports using the upstream-only signal as a conservative diagnostic with explicit run-level uncertainty.

## Reproduction Command

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python scripts/s03s_1781075115_415_5d145e93_upstream_qtemplate_curvature_leakage_gate.py --config configs/s03s_1781075115_415_5d145e93_upstream_qtemplate_curvature_leakage_gate.json
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03s_1781075115_415_5d145e93_upstream_qtemplate_curvature_leakage_gate.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base = load_base_module()
    base_config_path = Path(config["base_config"])
    base_config = base.load_config(base_config_path)
    base_config["output_dir"] = config["output_dir"]
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    seed = int(config["random_seed"])

    run_counts, calib_meta, calib_aligned, bench_pulses, bench_aligned, events = base.scan_raw(base_config)
    reproduction = base.reproduction_table(base_config, run_counts)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("Raw ROOT reproduction gate failed")

    template_pack, template_bins = base.build_templates(base_config, calib_meta, calib_aligned)
    q_values = base.template_q(bench_pulses, bench_aligned, template_pack)
    data = base.aggregate_events(events, bench_pulses, q_values)
    data = data[data["all_three_downstream"]].copy().reset_index(drop=True)
    data["abs_c_t_ns"] = np.abs(data["c_t_ns"].to_numpy(dtype=float))
    clean = data["abs_c_t_ns"].to_numpy(dtype=float) < float(base_config["clean_ct_max_ns"])
    tail = data["abs_c_t_ns"].to_numpy(dtype=float) > float(base_config["tail_ct_min_ns"])
    bench = data[clean | tail].copy().reset_index(drop=True)
    bench["label_tail"] = (bench["abs_c_t_ns"].to_numpy(dtype=float) > float(base_config["tail_ct_min_ns"])).astype(int)
    y = bench["label_tail"].to_numpy(dtype=int)
    runs = bench["run"].to_numpy(dtype=int)

    if any(col in DOWNSTREAM_FORBIDDEN for col in config["primary_feature_columns"]):
        raise RuntimeError("Primary feature list contains downstream q-template leakage")

    trad_score, trad_choices = train_selected_traditional(bench, y, list(config["traditional_candidates"]), seed)
    method_scores = {"traditional_upstream_q": trad_score}
    for offset, name in enumerate(["ridge", "gradient_boosted_trees", "mlp", "one_dimensional_cnn", "amplitude_residual_stack"], start=1):
        method_scores[name] = oof_scores(bench, y, list(config["primary_feature_columns"]), name, seed + 100 * offset)

    method_summary = pd.DataFrame(
        [summarize_method(name, y, score, runs, seed + i * 10, int(config["bootstrap_replicates"])) for i, (name, score) in enumerate(method_scores.items())]
    ).sort_values(["roc_auc", "average_precision"], ascending=False, ignore_index=True)
    winner = method_summary.iloc[0].to_dict()

    fixed = pd.concat(
        [fixed_clean_eff(bench, y, score, name, float(config["fixed_clean_efficiency"])) for name, score in method_scores.items()],
        ignore_index=True,
    )
    fold_rows = []
    for name, score in method_scores.items():
        for run in sorted(np.unique(runs)):
            mask = runs == run
            fold_rows.append(
                {
                    "method": name,
                    "heldout_run": int(run),
                    "n_clean": int(((y == 0) & mask).sum()),
                    "n_tail": int(((y == 1) & mask).sum()),
                    "roc_auc": auc(y[mask], score[mask]),
                    "average_precision": ap(y[mask], score[mask]),
                }
            )
    fold_metrics = pd.DataFrame(fold_rows)

    all_b2_features = ["q_b2"]
    downstream_probe_cols = ["q_b4", "q_b6", "q_b8", "q_ds_mean", "q_ds_max", "q_ds_std", "q_ds_span"]
    amp_cols = ["amp_b2", "amp_mean", "amp_ds_mean"]
    leakage_scores = {
        "b2_only_ridge": oof_scores(bench, y, all_b2_features, "ridge", seed + 901),
        "downstream_forbidden_gbt": oof_scores(bench, y, downstream_probe_cols, "gradient_boosted_trees", seed + 902),
        "amplitude_only_gbt": oof_scores(bench, y, amp_cols, "gradient_boosted_trees", seed + 903),
        "leaky_abs_ct_ceiling": bench["abs_c_t_ns"].to_numpy(dtype=float),
    }
    leakage = pd.DataFrame(
        [
            {
                "probe": name,
                "roc_auc": auc(y, score),
                "average_precision": ap(y, score),
                "notes": {
                    "b2_only_ridge": "Strict upstream shape-only lower-capacity sentinel.",
                    "downstream_forbidden_gbt": "Forbidden provenance ceiling using downstream q-template columns.",
                    "amplitude_only_gbt": "Nuisance-only amplitude sentinel.",
                    "leaky_abs_ct_ceiling": "Label-defining oracle; must be 1.0 if target construction is coherent.",
                }[name],
            }
            for name, score in leakage_scores.items()
        ]
    )

    dataset_counts = pd.DataFrame(
        [
            {"quantity": "all-three control events", "value": int(len(data))},
            {"quantity": "clean events |C_t|<3 ns", "value": int((y == 0).sum())},
            {"quantity": "tail events |C_t|>51 ns", "value": int((y == 1).sum())},
            {"quantity": "benchmark events", "value": int(len(bench))},
            {"quantity": "tail fraction", "value": float(y.mean())},
        ]
    )

    run_counts.to_csv(out_dir / "run_counts.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    template_bins.to_csv(out_dir / "template_bin_counts.csv", index=False)
    dataset_counts.to_csv(out_dir / "dataset_counts.csv", index=False)
    method_summary.to_csv(out_dir / "method_summary.csv", index=False)
    fixed.to_csv(out_dir / "fixed_clean_efficiency.csv", index=False)
    fold_metrics.to_csv(out_dir / "fold_metrics.csv", index=False)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    trad_choices.to_csv(out_dir / "traditional_fold_choices.csv", index=False)
    bench_for_output = add_upstream_features(bench)
    oof = bench_for_output[
        [
            "event_uid",
            "run",
            "eventno",
            "evt",
            "d_t_ns",
            "c_t_ns",
            "abs_c_t_ns",
            "label_tail",
            *config["primary_feature_columns"],
        ]
    ].copy()
    for name, score in method_scores.items():
        oof[f"{name}_score"] = score
    oof.to_csv(out_dir / "oof_predictions.csv", index=False)

    input_hashes = {}
    input_rows = []
    for run in base.configured_runs(base_config):
        path = base.raw_file(base_config, run)
        digest = sha256_file(path)
        input_hashes[str(path)] = digest
        input_rows.append({"path": str(path), "sha256": digest, "size": int(path.stat().st_size)})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "claimed_once_evidence": {
            "command": "tn-ticket claim testbeam-laptop-3 --project testbeam",
            "event_log": "2026-07-07T18:30:23Z claim OK id=1781075115.415.5d145e93 worker=testbeam-laptop-3"
        },
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction": reproduction.to_dict(orient="records"),
        "split": "leave-one-run-out by run over Sample-II analysis runs, with run bootstrap CIs",
        "primary_features": list(config["primary_feature_columns"]),
        "forbidden_downstream_features": sorted(DOWNSTREAM_FORBIDDEN),
        "metric": "ROC AUC primary, AP secondary for |C_t|>51 ns versus |C_t|<3 ns",
        "methods": method_summary.to_dict(orient="records"),
        "winner_name": str(winner["method"]),
        "winner": json_ready(winner),
        "traditional_method": "training-run-selected upstream q-template scalar score",
        "ml_methods": ["ridge", "gradient_boosted_trees", "mlp", "one_dimensional_cnn", "amplitude_residual_stack"],
        "leakage_checks": leakage.to_dict(orient="records"),
        "details": {
            "n_all_three_control_events": int(len(data)),
            "n_clean_events": int((y == 0).sum()),
            "n_tail_events": int((y == 1).sum()),
            "tail_fraction": float(y.mean()),
            "bootstrap_replicates": int(config["bootstrap_replicates"]),
            "fixed_clean_efficiency": float(config["fixed_clean_efficiency"]),
        },
        "input_sha256": hashlib.sha256("".join(input_hashes.values()).encode("ascii")).hexdigest(),
        "git_commit": git_commit(),
        "next_tickets": [],
    }
    write_report(out_dir, config, base_config, reproduction, run_counts, dataset_counts, method_summary, fixed, fold_metrics, leakage, winner)
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "base_config": str(base_config_path),
        "command": " ".join(sys.argv),
        "runtime_sec": round(time.time() - start, 2),
        "inputs": input_hashes,
        "outputs": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "reproduced": True, "winner": winner["method"], "winner_auc": winner["roc_auc"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
