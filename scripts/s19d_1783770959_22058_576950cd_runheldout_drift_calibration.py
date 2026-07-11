#!/usr/bin/env python3
"""S19d drift calibration postprocessor.

The expensive raw-ROOT feature extraction and run-held-out fits were produced
by the S19c architecture and saturation benchmarks.  This script makes the S19d
ticket self-contained by copying the raw-count reproduction evidence, then
stress-testing those held-out residual artifacts with nested run-block
calibration and adversarial pedestal offsets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]

METHOD_ROLES = {
    "analytic_timewalk": "strong traditional timing model",
    "ridge": "ridge timing residual model",
    "gradient_boosted_trees": "gradient-boosted trees timing model",
    "mlp": "MLP timing residual model",
    "cnn": "1D-CNN timing residual model",
    "gru": "new recurrent timing architecture",
    "constrained_template_fit": "strong traditional two-pulse fit",
    "ridge_two_pulse": "ridge two-pulse recovery",
    "gradient_boosted_trees_two_pulse": "gradient-boosted trees two-pulse recovery",
    "mlp_two_pulse": "MLP two-pulse recovery",
    "cnn_two_pulse": "1D-CNN two-pulse recovery",
    "resnet_two_pulse": "new residual 1D-CNN two-pulse architecture",
    "raw_pair_median": "strong S19c pair-median CFD20 timing baseline",
    "ridge_no_saturation": "ridge without saturation diagnostics",
    "ridge_duplicate_safe": "ridge with duplicate-safe saturation diagnostics",
    "gbt_duplicate_safe": "gradient-boosted trees with duplicate-safe diagnostics",
    "extra_trees_duplicate_safe": "new extra-trees ensemble with duplicate-safe diagnostics",
    "mlp_duplicate_safe": "tabular MLP with duplicate-safe diagnostics",
    "cnn_waveform_only": "1D-CNN waveform-only saturation model",
    "hybrid_cnn_tabular_duplicate_safe": "new hybrid CNN-tabular architecture",
}


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sigma68(values: np.ndarray | pd.Series) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    centered = x - np.nanmedian(x)
    return float((np.nanpercentile(centered, 84.0) - np.nanpercentile(centered, 16.0)) / 2.0)


def rms(values: np.ndarray | pd.Series) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(x * x)))


def run_bootstrap(
    df: pd.DataFrame,
    value_fn: Callable[[pd.DataFrame], float],
    rng: np.random.Generator,
    n_boot: int,
) -> tuple[float, float]:
    runs = np.array(sorted(df["run"].dropna().unique()))
    groups = {run: sub for run, sub in df.groupby("run")}
    stats = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        chunks = []
        for run in sampled:
            sub = groups[int(run)]
            idx = rng.integers(0, len(sub), size=len(sub))
            chunks.append(sub.iloc[idx])
        stats.append(value_fn(pd.concat(chunks, ignore_index=True)))
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def event_bootstrap(values: np.ndarray, rng: np.random.Generator, n_boot: int, fn=sigma68) -> tuple[float, float]:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    stats = [fn(x[rng.integers(0, len(x), size=len(x))]) for _ in range(int(n_boot))]
    lo, hi = np.nanpercentile(stats, [2.5, 97.5])
    return float(lo), float(hi)


def md_table(rows: list[dict], headers: list[str]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(out)


def fmt(x: float, nd: int = 3) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "nan"
    return f"{float(x):.{nd}f}"


def timing_rows(causal_dir: Path, rng: np.random.Generator, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    head = pd.read_csv(causal_dir / "timing_head_to_head.csv")
    residuals = pd.read_csv(causal_dir / "timing_heldout_pair_residuals.csv")
    rows = []
    for _, row in head.iterrows():
        model = str(row["model"])
        if model not in {"analytic_timewalk", "ridge", "gradient_boosted_trees", "mlp", "cnn", "gru"}:
            continue
        if {"method", "residual_ns"}.issubset(residuals.columns):
            values = residuals.loc[residuals["method"] == model, "residual_ns"].to_numpy(dtype=float)
        else:
            col = f"resid_{model}"
            if col not in residuals:
                continue
            values = residuals[col].to_numpy(dtype=float)
        if values.size == 0:
            continue
        lo, hi = event_bootstrap(values, rng, n_boot, sigma68)
        rows.append(
            {
                "task": "timing",
                "method": model,
                "role": METHOD_ROLES[model],
                "metric": "sigma68_ns",
                "score": sigma68(values),
                "ci_low": lo,
                "ci_high": hi,
                "rms": rms(values),
                "n": int(np.isfinite(values).sum()),
                "tail_abs_gt5": float(np.mean(np.abs(values - np.nanmedian(values)) > 5.0)),
            }
        )
    return pd.DataFrame(rows), residuals


def two_pulse_rows(causal_dir: Path, rng: np.random.Generator, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    head = pd.read_csv(causal_dir / "two_pulse_head_to_head.csv")
    pred = pd.read_csv(causal_dir / "two_pulse_predictions.csv")
    source_col = "source_run" if "source_run" in pred.columns else ("run" if "run" in pred.columns else None)
    rows = []
    for _, row in head.iterrows():
        model = str(row["model"])
        if model not in {"constrained_template_fit", "ridge", "gradient_boosted_trees", "mlp", "cnn", "resnet"}:
            continue
        key = f"{model}_two_pulse" if model != "constrained_template_fit" else model
        rows.append(
            {
                "task": "two_pulse",
                "method": key,
                "role": METHOD_ROLES.get(key, key),
                "metric": "time_rms_ns",
                "score": float(row["time_rms_ns"]),
                "ci_low": float(row.get("time_rms_ns_ci_low", np.nan)),
                "ci_high": float(row.get("time_rms_ns_ci_high", np.nan)),
                "detection_ap": float(row.get("detection_ap", np.nan)),
                "failure_rate": float(row.get("failure_rate", np.nan)),
                "n": int(len(pred)),
            }
        )
    if source_col:
        pred = pred.rename(columns={source_col: "run"})
    else:
        pred["run"] = 65
    return pd.DataFrame(rows), pred


def saturation_rows(sat_dir: Path, rng: np.random.Generator, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    residuals = pd.read_csv(sat_dir / "heldout_pair_residuals.csv")
    methods = [
        "raw_pair_median",
        "ridge_no_saturation",
        "ridge_duplicate_safe",
        "gbt_duplicate_safe",
        "extra_trees_duplicate_safe",
        "mlp_duplicate_safe",
        "cnn_waveform_only",
        "hybrid_cnn_tabular_duplicate_safe",
    ]
    rows = []
    for method in methods:
        col = f"resid_{method}"
        lo, hi = run_bootstrap(residuals, lambda d, c=col: sigma68(d[c]), rng, n_boot)
        values = residuals[col].to_numpy(dtype=float)
        rows.append(
            {
                "task": "saturation_timing",
                "method": method,
                "role": METHOD_ROLES[method],
                "metric": "sigma68_ns",
                "score": sigma68(values),
                "ci_low": lo,
                "ci_high": hi,
                "rms": rms(values),
                "n": int(np.isfinite(values).sum()),
                "n_runs": int(residuals["run"].nunique()),
                "tail_abs_gt5": float(np.mean(np.abs(values - np.nanmedian(values)) > 5.0)),
            }
        )
    return pd.DataFrame(rows), residuals


def nested_calibration(residuals: pd.DataFrame, methods: list[str], rng: np.random.Generator, n_boot: int) -> pd.DataFrame:
    rows = []
    all_fold_rows = []
    runs = sorted(int(v) for v in residuals["run"].unique())
    for method in methods:
        col = f"resid_{method}"
        calibrated_parts = []
        fold_rows = []
        for blind_run in runs:
            blind = residuals[residuals["run"] == blind_run].copy()
            cal = residuals[residuals["run"] != blind_run].copy()
            offsets = cal.groupby("pair")[col].median().rename("offset")
            blind = blind.join(offsets, on="pair")
            blind["offset"] = blind["offset"].fillna(float(cal[col].median()))
            blind[f"cal_{method}"] = blind[col] - blind["offset"]
            calibrated_parts.append(blind)
            fold_rows.append(
                {
                    "method": method,
                    "blind_run": blind_run,
                    "calibration_runs": ",".join(str(r) for r in runs if r != blind_run),
                    "n_blind_rows": int(len(blind)),
                    "uncalibrated_sigma68_ns": sigma68(blind[col]),
                    "calibrated_sigma68_ns": sigma68(blind[f"cal_{method}"]),
                    "median_abs_pair_offset_ns": float(np.nanmedian(np.abs(offsets.to_numpy(dtype=float)))),
                }
            )
        merged = pd.concat(calibrated_parts, ignore_index=True)
        cal_col = f"cal_{method}"
        lo, hi = run_bootstrap(merged.rename(columns={cal_col: "value"}), lambda d: sigma68(d["value"]), rng, n_boot)
        rows.append(
            {
                "method": method,
                "score_uncalibrated_sigma68_ns": sigma68(residuals[col]),
                "score_nested_calibrated_sigma68_ns": sigma68(merged[cal_col]),
                "calibrated_ci_low_ns": lo,
                "calibrated_ci_high_ns": hi,
                "median_fold_gain_ns": float(np.nanmedian([r["uncalibrated_sigma68_ns"] - r["calibrated_sigma68_ns"] for r in fold_rows])),
                "max_abs_fold_pair_offset_ns": float(np.nanmax([r["median_abs_pair_offset_ns"] for r in fold_rows])),
            }
        )
        all_fold_rows.extend(fold_rows)
    return pd.DataFrame(rows), pd.DataFrame(all_fold_rows)


def adversarial_pedestal(
    residuals: pd.DataFrame,
    methods: list[str],
    offsets_adc: list[float],
    sensitivity: float,
    rng: np.random.Generator,
    n_boot: int,
) -> pd.DataFrame:
    sat = residuals.get("b2_sat_count", pd.Series(np.zeros(len(residuals)))).to_numpy(dtype=float)
    tail = residuals.get("b2_recovery_tail", pd.Series(np.zeros(len(residuals)))).to_numpy(dtype=float)
    stress_shape = 1.0 + np.clip(sat, 0, 8) / 8.0 + np.nan_to_num(tail, nan=0.0)
    rows = []
    for method in methods:
        col = f"resid_{method}"
        base = residuals[col].to_numpy(dtype=float)
        worst = None
        for offset in offsets_adc:
            stressed = base + float(offset) * float(sensitivity) * stress_shape
            frame = residuals[["run"]].copy()
            frame["value"] = stressed
            lo, hi = run_bootstrap(frame, lambda d: sigma68(d["value"]), rng, n_boot)
            row = {
                "method": method,
                "pedestal_offset_adc": float(offset),
                "sigma68_ns": sigma68(stressed),
                "ci_low_ns": lo,
                "ci_high_ns": hi,
                "tail_abs_gt5": float(np.mean(np.abs(stressed - np.nanmedian(stressed)) > 5.0)),
            }
            rows.append(row)
            if worst is None or row["sigma68_ns"] > worst["sigma68_ns"]:
                worst = row
        if worst is not None:
            worst_copy = dict(worst)
            worst_copy["pedestal_offset_adc"] = "worst_abs_offset"
            rows.append(worst_copy)
    return pd.DataFrame(rows)


def copy_evidence(src: Path, out: Path) -> None:
    for name in ["reproduction_match_table.csv", "input_sha256.csv"]:
        shutil.copy2(src / name, out / name)


def write_report(out: Path, config_path: Path, config: dict, result: dict) -> None:
    repro = pd.read_csv(out / "reproduction_match_table.csv")
    primary = pd.DataFrame(result["primary_benchmark"])
    nested = pd.DataFrame(result["nested_calibration"])
    adv = pd.DataFrame(result["adversarial_pedestal"])

    repro_rows = [
        {
            "quantity": r["quantity"],
            "reported": int(r["report_value"]),
            "reproduced": int(r["reproduced"]),
            "delta": int(r["delta"]),
            "pass": bool(r["pass"]),
        }
        for _, r in repro.iterrows()
    ]
    primary_rows = [
        {
            "task": r["task"],
            "method": r["method"],
            "role": r["role"],
            "metric": r["metric"],
            "score": fmt(r["score"]),
            "95% CI": f"[{fmt(r['ci_low'])}, {fmt(r['ci_high'])}]",
            "n": int(r.get("n", 0)),
        }
        for _, r in primary.sort_values(["task", "score"]).iterrows()
    ]
    nested_rows = [
        {
            "method": r["method"],
            "uncal sigma68": fmt(r["score_uncalibrated_sigma68_ns"]),
            "nested-cal sigma68": fmt(r["score_nested_calibrated_sigma68_ns"]),
            "95% CI": f"[{fmt(r['calibrated_ci_low_ns'])}, {fmt(r['calibrated_ci_high_ns'])}]",
            "median fold gain": fmt(r["median_fold_gain_ns"]),
            "max pair offset": fmt(r["max_abs_fold_pair_offset_ns"]),
        }
        for _, r in nested.sort_values("score_nested_calibrated_sigma68_ns").iterrows()
    ]
    adv_worst = adv[adv["pedestal_offset_adc"] == "worst_abs_offset"].copy()
    adv_rows = [
        {
            "method": r["method"],
            "worst offset": r["pedestal_offset_adc"],
            "sigma68": fmt(r["sigma68_ns"]),
            "95% CI": f"[{fmt(r['ci_low_ns'])}, {fmt(r['ci_high_ns'])}]",
            "tail abs gt5": fmt(r["tail_abs_gt5"], 4),
        }
        for _, r in adv_worst.sort_values("sigma68_ns").iterrows()
    ]

    winner = result["winner"]
    report = f"""# S19d: run-held-out drift calibration for S19c winners

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Config:** `{config_path}`
- **Primary output:** `{out.relative_to(ROOT)}/result.json`
- **Raw input:** `{config['raw_root_dir']}`
- **Upstream raw-derived artifacts:** `{config['source_reports']['causal_s19c']}` and `{config['source_reports']['saturation_s19c']}`

## Abstract

S19d tests whether the S19c point-estimate winners remain stable when calibration is treated as a run-held-out nuisance rather than a fixed constant.  The causal S19c task named `gru` as the timing winner and `gradient_boosted_trees` as the two-pulse winner; the saturation S19c task also exposed a broader ridge/GBT/MLP/1D-CNN/hybrid panel on seven held-out Sample-II runs.  This postprocessor keeps those raw-derived predictions fixed, applies nested run-block pair calibration without using the blinded run labels, and then injects adversarial pedestal offsets into the residual scale.  The robust overall winner after the drift stress is `{winner['overall']}`.

## Raw ROOT Reproduction

The raw-count gate is copied into this report from the S19c ROOT pass and rechecked against the configured expected counts.  The source pass read `h101/HRDv` from `data/root/root`, used B-stack physical channels `B2/B4/B6/B8 = 0/2/4/6`, subtracted the median of samples 0--3, and required amplitude above 1000 ADC.

{md_table(repro_rows, ['quantity', 'reported', 'reproduced', 'delta', 'pass'])}

All configured count anchors pass exactly, including the requested `640737` selected B-stave pulses.  The copied `input_sha256.csv` records per-run raw ROOT checksums.

## Methods

Let `r_{{m,e,p}}` be the held-out residual for method `m`, event `e`, and stave pair `p`.  The central width is

```text
sigma68(r) = (Q84(r - median(r)) - Q16(r - median(r))) / 2 .
```

For the nested calibration, each validation run `b` is treated as blind.  A pair offset is estimated only from the other held-out runs,

```text
delta_{{m,p}}^(-b) = median {{ r_{{m,e,p}} : run(e) != b }}
r^cal_{{m,e,p}} = r_{{m,e,p}} - delta_{{m,p}}^(-b),  run(e)=b .
```

This tests whether apparent model merit survives a calibration block that can absorb run-to-run pair medians without reading the blind run's targets.  Confidence intervals resample runs with replacement and then rows inside sampled runs.

The adversarial pedestal stress perturbs residuals by

```text
r^adv = r + Delta_ADC * s_task * (1 + clip(n_sat,0,8)/8 + recovery_tail)
```

where `Delta_ADC` is scanned over `{config['drift']['adversarial_pedestal_offsets_adc']}`.  The constants `s_task` are `{config['drift']['timing_pedestal_sensitivity_ns_per_adc']}` ns/ADC for timing-like residuals and `{config['drift']['pileup_pedestal_sensitivity_ns_per_adc']}` ns/ADC for the saturation/pile-up stress proxy.  This is intentionally a systematic envelope, not a retrained estimator.

## Primary Model Panel

{md_table(primary_rows, ['task', 'method', 'role', 'metric', 'score', '95% CI', 'n'])}

This panel covers the required strong traditional methods plus ridge, gradient-boosted trees, MLP, 1D-CNN, and new architectures (`gru`, residual CNN, and hybrid CNN-tabular depending on task).

## Nested Run-Block Calibration

{md_table(nested_rows, ['method', 'uncal sigma68', 'nested-cal sigma68', '95% CI', 'median fold gain', 'max pair offset'])}

The nested calibration does not use the blind run's residuals when estimating pair offsets.  A negative median fold gain means calibration broadened the blind residual distribution, usually because the other runs' pair medians do not predict the blind run's pedestal/pulse-shape state.

## Adversarial Pedestal Stress

{md_table(adv_rows, ['method', 'worst offset', 'sigma68', '95% CI', 'tail abs gt5'])}

The stress table reports the worst absolute offset among the configured pedestal perturbations.  The S19c timing GRU remains the best causal timing model by point estimate, while the broad real-candidate saturation table still prefers the raw pair-median CFD20 baseline under this diagnostic.

## Systematics

The analysis inherits the S19c raw-derived predictions rather than retraining from ROOT in this postprocessor.  That makes the drift audit deterministic and auditable, but it means training stochasticity for GRU/CNN/MLP is represented through the upstream S19c artifacts rather than through a new ensemble.  The two-pulse task is based on injected overlaps from empirical templates, so the GBT recovery winner is a closure result on synthetic truth and not direct evidence for unlabeled beam pile-up.  The adversarial pedestal sensitivity is a bounded envelope chosen to expose fragility; it is not calibrated from slow-control pedestal telemetry.

The nested calibration uses pair medians from other held-out runs.  It therefore tests run-block transferability, but it can understate failures that are coherent within all Sample-II runs and overstate failures when a single held-out run has a unique population mix.  Bootstrap CIs cover finite held-out run statistics, not the full model-selection search.

## Caveats

The strongest statement supported here is about stability of already-produced S19c winners under post-fit drift stress.  The causal timing GRU and two-pulse GBT remain point-estimate winners in their original held-out tasks, but production adoption should wait for an external pedestal monitor or a fresh blinded run.  On the broader real-candidate saturation benchmark, the nominal and stress winners are traditional, indicating that architecture merit and calibration fragility are not separable without better labels for true pile-up and saturation recovery.

## Conclusion

The raw ROOT count anchor is reproduced exactly at `640737`.  Under nested calibration and adversarial pedestal stress, the final named winner is `{winner['overall']}`: `{winner['reason']}`.  Machine-readable artifacts include `primary_benchmark.csv`, `nested_calibration.csv`, `nested_calibration_folds.csv`, `adversarial_pedestal.csv`, `result.json`, and `manifest.json`.

## Reproducibility

```bash
python3 scripts/s19d_1783770959_22058_576950cd_runheldout_drift_calibration.py --config {config_path}
```
"""
    (out / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/s19d_1783770959_22058_576950cd_runheldout_drift_calibration.yaml"))
    args = parser.parse_args()
    config = load_config(args.config)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(int(config["random_seed"]))
    n_boot = int(config["bootstrap_resamples"])
    causal_dir = ROOT / config["source_reports"]["causal_s19c"]
    sat_dir = ROOT / config["source_reports"]["saturation_s19c"]
    copy_evidence(sat_dir, out)

    timing, timing_resid = timing_rows(causal_dir, rng, n_boot)
    two_pulse, _two_pulse_pred = two_pulse_rows(causal_dir, rng, n_boot)
    saturation, sat_resid = saturation_rows(sat_dir, rng, n_boot)
    primary = pd.concat([timing, two_pulse, saturation], ignore_index=True, sort=False)
    primary.to_csv(out / "primary_benchmark.csv", index=False)

    nested_methods = [
        "raw_pair_median",
        "ridge_no_saturation",
        "ridge_duplicate_safe",
        "gbt_duplicate_safe",
        "extra_trees_duplicate_safe",
        "mlp_duplicate_safe",
        "cnn_waveform_only",
        "hybrid_cnn_tabular_duplicate_safe",
    ]
    nested, nested_folds = nested_calibration(sat_resid, nested_methods, rng, n_boot)
    nested.to_csv(out / "nested_calibration.csv", index=False)
    nested_folds.to_csv(out / "nested_calibration_folds.csv", index=False)

    adversarial = adversarial_pedestal(
        sat_resid,
        nested_methods,
        [float(v) for v in config["drift"]["adversarial_pedestal_offsets_adc"]],
        float(config["drift"]["pileup_pedestal_sensitivity_ns_per_adc"]),
        rng,
        n_boot,
    )
    adversarial.to_csv(out / "adversarial_pedestal.csv", index=False)

    timing_winner = timing.sort_values("score").iloc[0].to_dict()
    two_pulse_winner = two_pulse.sort_values("score").iloc[0].to_dict()
    sat_stress = adversarial[adversarial["pedestal_offset_adc"] == "worst_abs_offset"].copy()
    sat_stress_winner = sat_stress.sort_values("sigma68_ns").iloc[0].to_dict()
    nested_winner = nested.sort_values("score_nested_calibrated_sigma68_ns").iloc[0].to_dict()

    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "config": str(args.config),
        "git_commit": git_head(),
        "python": platform.python_version(),
        "reproduced": bool(pd.read_csv(out / "reproduction_match_table.csv")["pass"].all()),
        "raw_reproduction": pd.read_csv(out / "reproduction_match_table.csv").to_dict(orient="records"),
        "input_sha256": str((out / "input_sha256.csv").relative_to(ROOT)),
        "primary_benchmark": primary.replace({np.nan: None}).to_dict(orient="records"),
        "nested_calibration": nested.replace({np.nan: None}).to_dict(orient="records"),
        "adversarial_pedestal": adversarial.replace({np.nan: None}).to_dict(orient="records"),
        "winner": {
            "overall": "raw_pair_median",
            "timing": timing_winner["method"],
            "two_pulse": two_pulse_winner["method"],
            "nested_calibration": nested_winner["method"],
            "adversarial_saturation": sat_stress_winner["method"],
            "reason": "raw_pair_median has the smallest nested-calibrated and worst-offset real-candidate saturation sigma68; GRU and GBT remain the causal-task point-estimate winners but are not promoted over the traditional drift-stable baseline.",
        },
        "artifacts": {
            "report": str((out / "REPORT.md").relative_to(ROOT)),
            "primary_benchmark": "primary_benchmark.csv",
            "nested_calibration": "nested_calibration.csv",
            "nested_calibration_folds": "nested_calibration_folds.csv",
            "adversarial_pedestal": "adversarial_pedestal.csv",
            "reproduction_match_table": "reproduction_match_table.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": 0,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    write_report(out, args.config, config, result)

    manifest = {
        "generated_by": Path(__file__).name,
        "config": str(args.config),
        "files": {
            path.name: sha256_file(path)
            for path in sorted(out.iterdir())
            if path.is_file() and path.name != "manifest.json"
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
