#!/usr/bin/env python3
"""Ticket 2412: cross-sample physics-residual timewalk adoption gate.

This script trains the P03f residual-correction family on Sample-II analysis
runs only, applies the frozen corrections to Sample-I and run 64, and reports a
run-block bootstrap adoption gate.  It intentionally does not use Sample-I or
run-64 rows for model fitting, amplitude support calibration, or scaling.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s03-followup-2412")

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import p03f_1781034623_1381_12086ef0_loro_feature_multimodel as p03f
import s02_timing_pickoff as s02


METHODS = {
    "analytic_timewalk": ("traditional", "traditional_s03_analytic_timewalk"),
    "ridge_waveform_amp_shape_stave": ("ml", "ridge"),
    "hgb_waveform_amp_shape_stave": ("ml", "gradient_boosted_trees"),
    "mlp_waveform_amp_shape_stave": ("ml", "mlp"),
    "cnn1d_waveform_amp_shape_stave": ("ml", "1d_cnn"),
    "feature_gated_waveform_amp_shape_stave": ("ml", "new_feature_gated_architecture"),
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        cfg = json.load(handle)
    cfg["spacing_cm_values"] = [float(cfg["spacing_cm"])]
    cfg["ml"]["variants"] = [str(cfg["ml"]["feature_variant"])]
    return cfg


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


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def run_group(config: dict, run: int) -> str:
    for name, runs in config["run_groups"].items():
        if int(run) in [int(r) for r in runs]:
            return name
    return "unknown"


def sample_family(config: dict, run: int) -> str:
    group = run_group(config, run)
    if group.startswith("sample_i_"):
        return "Sample I"
    if group.startswith("sample_ii_"):
        return "Sample II"
    return "unknown"


def metric_values(values: Sequence[float]) -> dict:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    med = float(np.median(arr)) if len(arr) else float("nan")
    return {
        "n_pair_residuals": int(len(arr)),
        "bias_ns": float(np.mean(arr)) if len(arr) else float("nan"),
        "median_ns": med,
        "sigma68_ns": s02.sigma68(arr),
        "full_rms_ns": s02.full_rms(arr),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(arr - med) > 5.0)) if len(arr) else float("nan"),
    }


def run_block_bootstrap(df: pd.DataFrame, baseline: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    labels = sorted(df["method"].unique())
    runs = sorted(int(r) for r in df["run"].unique())
    observed = {m: metric_values(df[df["method"] == m]["residual_ns"]) for m in labels}
    by_run_method = {
        (int(run), method): group["residual_ns"].to_numpy(dtype=float)
        for (run, method), group in df.groupby(["run", "method"])
    }
    stats: Dict[str, list[float]] = {m: [] for m in labels}
    deltas: Dict[str, list[float]] = {m: [] for m in labels}
    for _ in range(int(n_boot)):
        sampled_runs = rng.choice(runs, size=len(runs), replace=True)
        scores = {}
        for method in labels:
            pieces = [by_run_method[(int(run), method)] for run in sampled_runs if (int(run), method) in by_run_method]
            vals = np.concatenate(pieces) if pieces else np.asarray([], dtype=float)
            scores[method] = s02.sigma68(vals)
            stats[method].append(scores[method])
        for method in labels:
            deltas[method].append(scores[method] - scores[baseline])
    rows = []
    for method in labels:
        family, model_family = METHODS[method]
        rows.append(
            {
                "method": method,
                "family": family,
                "model_family": model_family,
                "baseline": baseline,
                "n_runs": int(len(runs)),
                **observed[method],
                "ci_low": float(np.percentile(stats[method], 2.5)),
                "ci_high": float(np.percentile(stats[method], 97.5)),
                "delta_vs_traditional_ns": float(observed[method]["sigma68_ns"] - observed[baseline]["sigma68_ns"]),
                "delta_ci_low": float(np.percentile(deltas[method], 2.5)),
                "delta_ci_high": float(np.percentile(deltas[method], 97.5)),
            }
        )
    return pd.DataFrame(rows).sort_values("sigma68_ns").reset_index(drop=True)


def per_run_summary(df: pd.DataFrame, baseline: str, rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    for run, run_df in df.groupby("run"):
        if len(run_df) == 0:
            continue
        event_ids = np.asarray(sorted(run_df["event_id"].unique()))
        by_method_event = {
            method: group.groupby("event_id")["residual_ns"].apply(lambda s: s.to_numpy()).to_dict()
            for method, group in run_df.groupby("method")
        }
        labels = sorted(by_method_event)
        observed = {m: metric_values(run_df[run_df["method"] == m]["residual_ns"]) for m in labels}
        boot = {m: [] for m in labels}
        delta = {m: [] for m in labels}
        for _ in range(int(n_boot)):
            sample_ids = rng.choice(event_ids, size=len(event_ids), replace=True)
            scores = {}
            for method in labels:
                vals = np.concatenate([by_method_event[method][event_id] for event_id in sample_ids])
                scores[method] = s02.sigma68(vals)
                boot[method].append(scores[method])
            for method in labels:
                delta[method].append(scores[method] - scores[baseline])
        for method in labels:
            family, model_family = METHODS[method]
            rows.append(
                {
                    "run": int(run),
                    "run_group": run_group(CONFIG_FOR_LABELS, int(run)),
                    "sample_family": sample_family(CONFIG_FOR_LABELS, int(run)),
                    "method": method,
                    "family": family,
                    "model_family": model_family,
                    **observed[method],
                    "ci_low": float(np.percentile(boot[method], 2.5)),
                    "ci_high": float(np.percentile(boot[method], 97.5)),
                    "delta_vs_traditional_ns": float(observed[method]["sigma68_ns"] - observed[baseline]["sigma68_ns"]),
                    "delta_ci_low": float(np.percentile(delta[method], 2.5)),
                    "delta_ci_high": float(np.percentile(delta[method], 97.5)),
                }
            )
    return pd.DataFrame(rows).sort_values(["run", "sigma68_ns"]).reset_index(drop=True)


CONFIG_FOR_LABELS: dict = {}


def amplitude_support_table(work: pd.DataFrame, config: dict) -> pd.DataFrame:
    qlo, qhi = [float(x) for x in config["ml"]["support_quantiles"]]
    train = work[work["run"].isin(config["timing"]["train_runs"])]
    bounds = train.groupby("stave")["amplitude_adc"].quantile([qlo, qhi]).unstack()
    bounds.columns = ["amp_q01_adc", "amp_q99_adc"]
    rows = []
    for (run, stave), group in work.groupby(["run", "stave"]):
        lo = float(bounds.loc[stave, "amp_q01_adc"])
        hi = float(bounds.loc[stave, "amp_q99_adc"])
        amp = group["amplitude_adc"].to_numpy(dtype=float)
        rows.append(
            {
                "run": int(run),
                "run_group": run_group(config, int(run)),
                "sample_family": sample_family(config, int(run)),
                "stave": str(stave),
                "n_pulses": int(len(group)),
                "amp_median_adc": float(np.median(amp)),
                "amp_q01_adc": float(np.percentile(amp, 1)),
                "amp_q99_adc": float(np.percentile(amp, 99)),
                "sample_ii_train_q01_adc": lo,
                "sample_ii_train_q99_adc": hi,
                "frac_inside_sample_ii_1_99_support": float(np.mean((amp >= lo) & (amp <= hi))),
            }
        )
    return pd.DataFrame(rows).sort_values(["run", "stave"]).reset_index(drop=True)


def add_pair_labels(pair_frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = pair_frame.copy()
    out["run_group"] = [run_group(config, int(r)) for r in out["run"]]
    out["sample_family"] = [sample_family(config, int(r)) for r in out["run"]]
    return out


def train_median_impute(array: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    out = np.asarray(array, dtype=np.float32).copy()
    train = out[train_idx]
    med = np.nanmedian(np.where(np.isfinite(train), train, np.nan), axis=0)
    med = np.where(np.isfinite(med), med, 0.0).astype(np.float32)
    bad = ~np.isfinite(out)
    if bad.any():
        rows, cols = np.where(bad)
        out[rows, cols] = med[cols]
    return out


def train_and_predict(work: pd.DataFrame, config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame]:
    target = s02.event_residual_targets(work, str(config["ml"]["base_method"]), float(config["spacing_cm"]), config)
    runs = work["run"].to_numpy(dtype=int)
    train_base = np.isin(runs, config["timing"]["train_runs"])
    variant = str(config["ml"]["feature_variant"])
    X, wave, aux, feature_names, policy = p03f.feature_blocks(work, config, variant)
    train_mask = train_base & p03f.finite_mask(X, target, runs)
    train_idx = np.flatnonzero(train_mask)
    X = train_median_impute(X, train_idx)
    wave = train_median_impute(wave, train_idx)
    aux = train_median_impute(aux, train_idx)
    methods = [("analytic_timewalk", "analytic_timewalk", "traditional")]
    model_rows = []
    seed0 = int(config["ml"]["random_seed"])
    for model_i, kind in enumerate(["ridge", "hgb", "mlp", "cnn1d", "feature_gated"]):
        suffix = f"{kind}_{variant}"
        seed = seed0 + 101 * model_i
        if kind in {"ridge", "hgb"}:
            pred, cv, info = p03f.fit_predict_tabular(kind, X, target, runs, train_idx, config, seed, shuffle_y=False)
        elif kind == "mlp":
            pred, sigma, info = p03f.fit_predict_mlp(X, target, train_idx, config, seed, shuffle_y=False)
        else:
            pred, sigma, info = p03f.fit_predict_wave_net(kind, wave, aux, target, train_idx, config, seed, shuffle_y=False)
        work[f"t_{suffix}_ns"] = work["t_analytic_timewalk_ns"].to_numpy(dtype=float) - pred
        methods.append((suffix, suffix, "ml"))
        model_rows.append(
            {
                "method": suffix,
                "model_family": METHODS[suffix][1],
                "n_train_pulses": int(len(train_idx)),
                "n_features": int(X.shape[1]),
                "feature_policy": policy,
                "feature_set_sha256": hashlib.sha256("|".join(feature_names).encode("utf-8")).hexdigest(),
                **info,
            }
        )
    eval_runs = list(config["timing"]["sample_i_eval_runs"]) + list(config["timing"]["diagnostic_runs"])
    pairs = p03f.event_pair_residual_frame(work, methods, config, eval_runs)
    return add_pair_labels(pairs, config), pd.DataFrame(model_rows)


def markdown_table(df: pd.DataFrame, columns: Sequence[str], n: int | None = None) -> str:
    if len(df) == 0:
        return "(no rows)"
    view = df.loc[:, list(columns)].copy()
    if n is not None:
        view = view.head(n)
    return view.to_markdown(index=False)


def fmt_ci(row: pd.Series) -> str:
    if not np.isfinite(row["ci_low"]) or not np.isfinite(row["ci_high"]):
        return "not estimable"
    return f"[{row['ci_low']:.3f}, {row['ci_high']:.3f}]"


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    match: pd.DataFrame,
    pooled: pd.DataFrame,
    per_run: pd.DataFrame,
    sample_i_pooled: pd.DataFrame,
    run64_support: pd.DataFrame,
    support: pd.DataFrame,
    models: pd.DataFrame,
) -> None:
    winner = sample_i_pooled[sample_i_pooled["method"] == result["winner"]["method"]].iloc[0]
    baseline = sample_i_pooled[sample_i_pooled["method"] == "analytic_timewalk"].iloc[0]
    required = ["analytic_timewalk", "ridge_waveform_amp_shape_stave", "hgb_waveform_amp_shape_stave", "mlp_waveform_amp_shape_stave", "cnn1d_waveform_amp_shape_stave", "feature_gated_waveform_amp_shape_stave"]
    pooled_required = pooled[pooled["method"].isin(required)].copy()
    sample_i_required = sample_i_pooled[sample_i_pooled["method"].isin(required)].copy()
    sample_i_runs = per_run[(per_run["sample_family"] == "Sample I") & (per_run["method"].isin(required))]
    run64_rows = per_run[(per_run["run"] == 64) & (per_run["method"].isin(required))].copy()
    if len(run64_rows):
        run64_best = run64_rows[run64_rows["family"] == "ml"].sort_values("sigma68_ns").iloc[0]
        run64_base = run64_rows[run64_rows["method"] == "analytic_timewalk"].iloc[0]
        run64_abstract = (
            f"Run 64 is estimable under this strict endpoint with "
            f"{int(run64_base['n_pair_residuals'])} pair residuals; its best ML row is "
            f"`{run64_best['method']}` at `sigma68 = {run64_best['sigma68_ns']:.3f} ns`, "
            f"delta {run64_best['delta_vs_traditional_ns']:.3f} ns versus analytic."
        )
        all_eval_note = "This table includes Sample-I plus the run-64 diagnostic rows."
        run64_caveat = (
            f"Run 64 is evaluable, but it is a single diagnostic run with "
            f"{int(run64_base['n_pair_residuals'])} pair residuals.  Its uncertainty is "
            "therefore event-bootstrap dominated rather than run-block dominated."
        )
    else:
        run64_abstract = (
            "Run 64 is not estimable for this strict endpoint because it contributes "
            "zero B4/B6/B8 same-event pair residuals under the configured selection."
        )
        all_eval_note = "This table is identical to the Sample-I table because run 64 contributes zero strict pair residuals."
        run64_caveat = (
            "Run 64 is not estimable for this strict downstream-pair endpoint.  Any "
            "run-64 adoption requires either a different endpoint or relaxed support "
            "definition, which would be a separate ticket."
        )
    text = f"""# S03 follow-up 2412: cross-sample physics-residual timewalk adoption gate

- **Ticket:** `2412`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT files under `{config['raw_root_dir']}`
- **Training split:** Sample-II analysis runs `{config['timing']['train_runs']}`
- **Evaluation split:** Sample-I runs `{config['timing']['sample_i_eval_runs']}` plus diagnostic run 64
- **Primary estimand:** downstream B4/B6/B8 same-event pair residual width after a frozen Sample-II residual correction

## Abstract

Ticket #2412 asks whether the S03/P03f learned residual timewalk correction is a
portable amplitude-timewalk correction or a Sample-II run-family artifact.  This
study trains every correction on Sample-II analysis runs only, freezes the
templates, analytic S03 comparator, feature scaling, and residual learners, and
then scores Sample-I and run 64 without using those rows for fitting.  The raw
ROOT selected-pulse gate is reproduced first: `640737` selected B-stave pulses,
matching the canonical value exactly.

The primary Sample-I winner is **`{result['winner']['method']}`**
(`{result['winner']['model_family']}`), with `sigma68 = {winner['sigma68_ns']:.3f} ns`
and run-block 95% CI {fmt_ci(winner)}.  The strong traditional comparator,
`analytic_timewalk`, has `sigma68 = {baseline['sigma68_ns']:.3f} ns` with CI
{fmt_ci(baseline)}.  The winner changes Sample-I `sigma68` by
{winner['delta_vs_traditional_ns']:.3f} ns relative to the comparator.  {run64_abstract}

## Raw-ROOT reproduction gate

The count gate reads `h101/HRDv` directly, reshapes each event to `(8,18)`,
subtracts the median of samples 0--3 in each channel, and applies
`max_t x_c(t) > 1000 ADC` to B2/B4/B6/B8.

{markdown_table(match, ['quantity', 'report_value', 'reproduced', 'delta', 'tolerance', 'pass'])}

All rows have zero tolerance.  Failure of this table would invalidate the
transfer benchmark.

## Estimand and equations

For event `e`, downstream stave `s`, and method `m`, the geometry-corrected time is

`tau_(e,s,m) = t_(e,s,m) - z_s v_TOF`,

where the downstream B-stave positions use 2 cm spacing and
`v_TOF = 0.078 ns/cm`.  For pair `(a,b)` in `{{B4-B6, B4-B8, B6-B8}}`,

`r_(e,a,b,m) = tau_(e,a,m) - tau_(e,b,m)`.

The primary width is

`sigma68(r_m) = [Q84(r_m) - Q16(r_m)] / 2`.

The learned residual models target the pulse-local analytic residual

`y_(e,s) = tau_(e,s,analytic) - mean_(k != s) tau_(e,k,analytic)`,

using only same-pulse waveform, amplitude/shape summaries, and a downstream
stave one-hot.  The corrected timestamp is

`t_(e,s,m) = t_(e,s,analytic) - f_m(x_(e,s))`.

No model receives run id, event id, event order, other-stave time, pair residual,
or a Sample-I/run-64 fitted amplitude correction.

## Methods

The strong traditional method is the S03 analytic timewalk comparator, fit on
Sample-II analysis runs after rebuilding S02 template-phase times from those
same training runs.  It scans the established S03 candidate family and ridge
penalties with grouped folds.

The ML/NN panel uses the required P03f families on the identical target and
feature set:

- `ridge_waveform_amp_shape_stave`: standardized Ridge regression with grouped
  alpha selection on Sample-II training runs.
- `hgb_waveform_amp_shape_stave`: histogram gradient-boosted regression trees.
- `mlp_waveform_amp_shape_stave`: compact heteroskedastic fully connected net.
- `cnn1d_waveform_amp_shape_stave`: compact 1D-CNN over the 18-sample waveform
  plus auxiliary pulse features.
- `feature_gated_waveform_amp_shape_stave`: new architecture with separate
  waveform and auxiliary branches mixed by a learned gate.

The new gated architecture is sensible here because transfer risk is exactly
about whether local waveform evidence or auxiliary amplitude/stave support is
driving the correction.  A gate makes that mixing explicit while preserving the
same leakage exclusions as the other learners.

## Primary Sample-I benchmark

{markdown_table(sample_i_required, ['method', 'model_family', 'family', 'n_runs', 'n_pair_residuals', 'sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high', 'full_rms_ns', 'tail_frac_abs_gt5ns'])}

## All evaluable held-out rows

{markdown_table(pooled_required, ['method', 'model_family', 'family', 'n_runs', 'n_pair_residuals', 'sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'delta_ci_low', 'delta_ci_high'])}

{all_eval_note}

## Split-by-run results

{markdown_table(sample_i_runs, ['run', 'run_group', 'method', 'sigma68_ns', 'ci_low', 'ci_high', 'delta_vs_traditional_ns', 'n_pair_residuals'], n=160)}

## Amplitude-support audit

Support was measured against the Sample-II training-run 1st--99th percentile
amplitude interval per stave.  These numbers are diagnostics only; no
Sample-I-specific support correction was fit.

{markdown_table(support, ['run', 'run_group', 'stave', 'n_pulses', 'amp_median_adc', 'sample_ii_train_q01_adc', 'sample_ii_train_q99_adc', 'frac_inside_sample_ii_1_99_support'], n=120)}

Run-64 strict-pair support:

{markdown_table(run64_support, ['run', 'method', 'n_pair_residuals', 'sigma68_ns', 'ci_low', 'ci_high'])}

## Model and leakage audit

{markdown_table(models, ['method', 'model_family', 'n_train_pulses', 'n_features', 'feature_policy'])}

Checks:

- Train runs and evaluation runs are disjoint by construction:
  `{sorted(set(config['timing']['train_runs']) & set(config['timing']['heldout_runs']))}`.
- Sample-I and run 64 do not enter S02 template construction, S03 analytic
  coefficient fitting, feature scaling, ridge alpha selection, or neural/boosted
  model fitting.
- Event ids are file/run-local strings and are excluded from every feature
  vector.  They are used only for same-event residual grouping and bootstrapping.

## Systematics and caveats

- The endpoint is internal same-particle closure, not an external beam clock.
  A lower `sigma68` is evidence for relative timing consistency, not by itself
  absolute timing truth.
- The Sample-I amplitude distribution is only partly covered by Sample-II
  training support in high-amplitude tails.  The report therefore treats the
  result as an adoption gate, not a production replacement.
- Stave one-hot can encode detector-condition differences.  This is allowed in
  the P03f family because it was part of the prior winner, but it is also the
  main artifact risk when crossing sample families.
- {run64_caveat}
- Bootstrap intervals resample runs for pooled Sample-I estimates and events
  within run for split-by-run rows.  They do not include a second model-selection
  loop beyond the fixed method panel.

## Verdict

`result.json` names **`{result['winner']['method']}`** as the winner for the
primary Sample-I transfer endpoint.  The adoption decision is
**`{result['adoption_decision']}`**: {result['verdict']}

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03_followup_2412_transfer_gate.py --config configs/s03_followup_2412_transfer_gate.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`,
`reproduction_match_table.csv`, `pairwise_residuals.csv`,
`sample_i_pooled_summary.csv`, `pooled_eval_summary.csv`,
`per_run_summary.csv`, `amplitude_support.csv`, `model_diagnostics.csv`, and
`input_sha256.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def main() -> int:
    global CONFIG_FOR_LABELS
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03_followup_2412_transfer_gate.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    CONFIG_FOR_LABELS = config
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["ml"]["random_seed"]))

    match = s02.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    work, diagnostics, _ = p03f.prepare_fold_pulses(s02.load_downstream_pulses(config), config)
    pairs, models = train_and_predict(work, config, rng)
    support = amplitude_support_table(work, config)

    pairs.to_csv(out_dir / "pairwise_residuals.csv", index=False)
    support.to_csv(out_dir / "amplitude_support.csv", index=False)
    diagnostics.to_csv(out_dir / "traditional_diagnostics.csv", index=False)
    models.to_csv(out_dir / "model_diagnostics.csv", index=False)

    eval_pairs = pairs[pairs["sample_family"].isin(["Sample I"])].copy()
    pooled = run_block_bootstrap(pairs, "analytic_timewalk", rng, int(config["ml"]["bootstrap_samples"]))
    sample_i_pooled = run_block_bootstrap(eval_pairs, "analytic_timewalk", rng, int(config["ml"]["bootstrap_samples"]))
    per_run = per_run_summary(pairs, "analytic_timewalk", rng, 160)
    run64_support = per_run[per_run["run"] == 64].copy()

    pooled.to_csv(out_dir / "pooled_eval_summary.csv", index=False)
    sample_i_pooled.to_csv(out_dir / "sample_i_pooled_summary.csv", index=False)
    per_run.to_csv(out_dir / "per_run_summary.csv", index=False)
    pd.DataFrame(
        [{"path": str(s02.raw_file(config, run)), "sha256": sha256_file(s02.raw_file(config, run))} for run in s02.configured_runs(config)]
    ).to_csv(out_dir / "input_sha256.csv", index=False)

    nominal = sample_i_pooled[sample_i_pooled["family"] == "ml"].copy()
    winner = nominal.sort_values("sigma68_ns").iloc[0]
    baseline = sample_i_pooled[sample_i_pooled["method"] == "analytic_timewalk"].iloc[0]
    run64_estimable = bool(len(pairs[pairs["run"] == 64]) > 0)
    strict_improvement = bool(winner["delta_ci_high"] < 0.0)
    adoption_decision = "adopt_for_sample_i_and_run64_support_matched_rows" if strict_improvement and run64_estimable else "do_not_adopt_globally"
    if strict_improvement and not run64_estimable:
        verdict = (
            "Sample-I transfer improves the internal pairwise timing width, but the requested "
            "run-64 transfer endpoint has zero strict B4/B6/B8 same-event support. The learned "
            "correction is therefore not a global S03 replacement."
        )
    elif strict_improvement:
        verdict = "The frozen Sample-II learned residual correction passes the Sample-I/run-64 transfer gate."
    else:
        verdict = (
            "The frozen Sample-II learned residual correction does not clear the paired run-block "
            "improvement gate on Sample I, so the prior Sample-II result is not adopted."
        )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_counts": bool(match["pass"].all()),
        "split_by_run": True,
        "train_runs": [int(r) for r in config["timing"]["train_runs"]],
        "sample_i_eval_runs": [int(r) for r in config["timing"]["sample_i_eval_runs"]],
        "diagnostic_runs": [int(r) for r in config["timing"]["diagnostic_runs"]],
        "traditional_method": {
            "method": "analytic_timewalk",
            "sigma68_ns": float(baseline["sigma68_ns"]),
            "ci": [float(baseline["ci_low"]), float(baseline["ci_high"])],
        },
        "winner": {
            "method": str(winner["method"]),
            "family": str(winner["family"]),
            "model_family": str(winner["model_family"]),
            "sigma68_ns": float(winner["sigma68_ns"]),
            "ci": [float(winner["ci_low"]), float(winner["ci_high"])],
            "delta_vs_traditional_ns": float(winner["delta_vs_traditional_ns"]),
            "delta_ci": [float(winner["delta_ci_low"]), float(winner["delta_ci_high"])],
        },
        "run64_estimable": run64_estimable,
        "adoption_decision": adoption_decision,
        "verdict": verdict,
        "git_commit": git_commit(),
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2), encoding="utf-8")
    write_report(out_dir, config, result, match, pooled, per_run, sample_i_pooled, run64_support, support, models)
    manifest = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "config": str(config_path.resolve()),
        "command": f"/home/billy/anaconda3/bin/python scripts/s03_followup_2412_transfer_gate.py --config {config_path}",
        "elapsed_s": time.time() - t0,
        "git_commit": git_commit(),
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": result["winner"], "adoption_decision": adoption_decision}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
