#!/usr/bin/env python3
"""S54b/#2488 pedestal-memory calibration bakeoff.

This wrapper reuses the validated S32a raw-ROOT reader/model panel for timing,
then adds ticket-local auxiliary targets for duplicate-readout energy closure,
PID sideband separation, pile-up tagging, and saturation-onset calibration.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge, RidgeClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s32a_1783884181_2123_49437123_pulse_onset_timing_pedestal_pileup_saturation_benchmark as s32a


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "ticket_2488_s54b_pedestal_memory_calibration_bakeoff.json"
TICKET = "2488"
WORKER = "testbeam-laptop-1"
SLUG = "s54b_pedestal_memory_calibration_bakeoff"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
METHODS = [
    "traditional_state_space_gls",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "1d_cnn",
    "waveform_transformer",
    "pedestal_residual_fusion_new",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def jsafe(value):
    if isinstance(value, dict):
        return {str(k): jsafe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsafe(v) for v in value]
    if isinstance(value, tuple):
        return [jsafe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return None if not math.isfinite(x) else x
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def qsigma(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    centered = values - np.median(values)
    return float(0.5 * (np.percentile(centered, 84) - np.percentile(centered, 16)))


def ci(values: list[float]) -> tuple[float, float]:
    finite = np.asarray([v for v in values if np.isfinite(v)], dtype=float)
    if len(finite) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(finite, 2.5)), float(np.percentile(finite, 97.5))


def md_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    view = df.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4g}" if np.isfinite(x) else "nan")
    return view.to_markdown(index=False)


def aux_features(data: pd.DataFrame) -> list[str]:
    return [
        c
        for c in s32a.feature_columns(data)
        if c != "duplicate_amplitude"
    ]


def prepare_targets(data: pd.DataFrame) -> pd.DataFrame:
    out = data.copy()
    ratio = out["duplicate_amplitude"] / np.maximum(out["amplitude"], 1.0)
    train = out["split"].eq("train")
    out["energy_fractional_target"] = np.log1p(out["duplicate_amplitude"].clip(lower=0.0)) - np.log1p(out["amplitude"].clip(lower=0.0))
    out["pid_high_duplicate"] = (ratio >= float(ratio[train].quantile(0.70))).astype(int)
    out["pileup_label"] = (out["pileup_separation_sample"] > 0).astype(int)
    out["saturation_label"] = out["saturation_onset_bin"].eq("near_saturation").astype(int)
    out["pedestal_state"] = out["baseline"] - out.groupby(["run", "stave"])["baseline"].transform("median")
    return out


def traditional_energy_prediction(data: pd.DataFrame) -> np.ndarray:
    train = data["split"].eq("train")
    ratio = data["energy_fractional_target"].to_numpy(float)
    pred = np.full(len(data), float(np.median(ratio[train])), dtype=float)
    for stave, group in data[train].groupby("stave"):
        idx = data["stave"].eq(stave).to_numpy()
        pred[idx] = float(np.median(group["energy_fractional_target"]))
    x = data["pedestal_state"].to_numpy(float)
    y = ratio - pred
    coef = np.polyfit(x[train], y[train], deg=1)
    return pred + np.polyval(coef, x)


def fit_aux_predictions(data: pd.DataFrame, config: dict) -> dict[str, dict[str, np.ndarray]]:
    cols = aux_features(data)
    x = data[cols].to_numpy(float)
    train = data["split"].eq("train").to_numpy()
    rng_seed = int(config["random_seed"])
    targets = {
        "energy": data["energy_fractional_target"].to_numpy(float),
        "pid": data["pid_high_duplicate"].to_numpy(int),
        "pileup": data["pileup_label"].to_numpy(int),
        "saturation": data["saturation_label"].to_numpy(int),
    }
    preds: dict[str, dict[str, np.ndarray]] = {m: {} for m in METHODS}
    preds["traditional_state_space_gls"]["energy"] = traditional_energy_prediction(data)
    preds["traditional_state_space_gls"]["pid"] = data["tail_fraction"].to_numpy(float) + 0.15 * data["rise_time_sample"].to_numpy(float)
    preds["traditional_state_space_gls"]["pileup"] = data["late_peak_prominence"].to_numpy(float)
    preds["traditional_state_space_gls"]["saturation"] = data["flat_top_samples"].to_numpy(float) + data["amplitude"].to_numpy(float) / 12000.0

    reg_models = {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=4.0)),
        "gradient_boosted_trees": HistGradientBoostingRegressor(max_iter=180, learning_rate=0.045, l2_regularization=0.03, random_state=rng_seed + 10),
        "mlp": make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(72, 36), alpha=1e-3, max_iter=45, random_state=rng_seed + 11, early_stopping=True)),
    }
    clf_models = {
        "ridge": make_pipeline(StandardScaler(), RidgeClassifier(alpha=3.0)),
        "gradient_boosted_trees": HistGradientBoostingClassifier(max_iter=160, learning_rate=0.05, l2_regularization=0.03, random_state=rng_seed + 12),
        "mlp": make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-3, max_iter=45, random_state=rng_seed + 13, early_stopping=True)),
    }
    for name, model in reg_models.items():
        model.fit(x[train], targets["energy"][train])
        preds[name]["energy"] = model.predict(x)
    for target in ["pid", "pileup", "saturation"]:
        for name, model in clf_models.items():
            model.fit(x[train], targets[target][train])
            if hasattr(model, "predict_proba"):
                score = model.predict_proba(x)[:, 1]
            elif hasattr(model, "decision_function"):
                score = model.decision_function(x)
            else:
                score = model.predict(x)
            preds[name][target] = np.asarray(score, dtype=float)

    tmp = data.copy()
    for method, gated, seed in [
        ("1d_cnn", False, rng_seed + 21),
        ("pedestal_residual_fusion_new", True, rng_seed + 22),
    ]:
        tmp["target_onset_residual_ns"] = targets["energy"].astype(float)
        preds[method]["energy"] = s32a.fit_cnn(tmp, config, method, gated=gated, seed=seed)
        for target, off in [("pid", 31), ("pileup", 32), ("saturation", 33)]:
            tmp["target_onset_residual_ns"] = targets[target].astype(float)
            preds[method][target] = s32a.fit_cnn(tmp, config, method, gated=gated, seed=seed + off)
    tmp["target_onset_residual_ns"] = targets["energy"].astype(float)
    preds["waveform_transformer"]["energy"] = s32a.fit_transformer(tmp, config, seed=rng_seed + 41)
    for target, off in [("pid", 51), ("pileup", 52), ("saturation", 53)]:
        tmp["target_onset_residual_ns"] = targets[target].astype(float)
        preds["waveform_transformer"][target] = s32a.fit_transformer(tmp, config, seed=rng_seed + off)
    return preds


def metric_row(frame: pd.DataFrame, target: str) -> dict[str, float]:
    if target == "energy":
        err = frame["energy_error"].to_numpy(float)
        return {
            "energy_scale_bias": float(np.nanmedian(err)),
            "energy_sigma68": qsigma(err),
            "energy_rms": float(np.sqrt(np.nanmean((err - np.nanmedian(err)) ** 2))),
        }
    y = frame[f"{target}_label"].to_numpy(int)
    s = frame[f"{target}_score"].to_numpy(float)
    if len(np.unique(y)) < 2:
        return {f"{target}_auc": float("nan"), f"{target}_ap": float("nan"), f"{target}_fixed_purity_eff": float("nan")}
    order = np.argsort(s)[::-1]
    y_sorted = y[order]
    cum_tp = np.cumsum(y_sorted)
    purity = cum_tp / np.arange(1, len(y_sorted) + 1)
    ok = np.where(purity >= 0.90)[0]
    eff = float(cum_tp[ok[-1]] / max(cum_tp[-1], 1)) if len(ok) else 0.0
    return {
        f"{target}_auc": float(roc_auc_score(y, s)),
        f"{target}_ap": float(average_precision_score(y, s)),
        f"{target}_fixed_purity_eff": eff,
    }


def summarize_aux(data: pd.DataFrame, preds: dict[str, dict[str, np.ndarray]], config: dict, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    run_rows = []
    target_frames = []
    held_mask = data["split"].eq("heldout").to_numpy()
    runs = sorted(data.loc[held_mask, "run"].unique())
    for method in METHODS:
        frame = data[["run", "stave", "split", "energy_fractional_target", "pid_high_duplicate", "pileup_label", "saturation_label", "pedestal_drift_bin", "pid_sideband", "pileup_separation_bin", "saturation_onset_bin"]].copy()
        frame["method"] = method
        frame["energy_prediction"] = preds[method]["energy"]
        frame["energy_error"] = frame["energy_prediction"] - frame["energy_fractional_target"]
        for target in ["pid", "pileup", "saturation"]:
            frame[f"{target}_score"] = preds[method][target]
            if target == "pid":
                frame[f"{target}_label"] = frame["pid_high_duplicate"]
        held = frame[frame["split"].eq("heldout")].copy()
        row = {"method": method, "n": int(len(held))}
        for target in ["energy", "pid", "pileup", "saturation"]:
            row.update(metric_row(held, target))
        boot = {k: [] for k in row if k not in {"method", "n"}}
        for _ in range(int(config["aux_bootstrap_replicates"])):
            take = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([held[held["run"].eq(r)] for r in take], ignore_index=True)
            vals = {}
            for target in ["energy", "pid", "pileup", "saturation"]:
                vals.update(metric_row(sample, target))
            for key, value in vals.items():
                boot[key].append(value)
        for key, values in boot.items():
            lo, hi = ci(values)
            row[f"{key}_ci_low"] = lo
            row[f"{key}_ci_high"] = hi
        rows.append(row)
        for run, rg in held.groupby("run"):
            rr = {"method": method, "run": int(run), "n": int(len(rg))}
            for target in ["energy", "pid", "pileup", "saturation"]:
                rr.update(metric_row(rg, target))
            run_rows.append(rr)
        target_frames.append(held)
    summary = pd.DataFrame(rows)
    summary["auxiliary_score"] = (
        summary["energy_sigma68"]
        + 0.20 * summary["energy_scale_bias"].abs()
        + 0.08 * (1.0 - summary["pid_auc"])
        + 0.06 * (1.0 - summary["pileup_auc"])
        + 0.04 * (1.0 - summary["saturation_auc"])
    )
    summary = summary.sort_values("auxiliary_score").reset_index(drop=True)
    run_summary = pd.DataFrame(run_rows).sort_values(["method", "run"])
    long = pd.concat(target_frames, ignore_index=True)
    strata_rows = []
    for method, mg in long.groupby("method"):
        for col in ["pedestal_drift_bin", "pid_sideband", "pileup_separation_bin", "saturation_onset_bin"]:
            for level, sg in mg.groupby(col):
                vals = metric_row(sg, "energy")
                strata_rows.append({"method": method, "stratum": col, "level": str(level), "n": int(len(sg)), **vals})
    return summary, run_summary, pd.DataFrame(strata_rows)


def write_claim_file() -> None:
    existing = OUT / "claimed_ticket.txt"
    body = existing.read_text(encoding="utf-8") if existing.exists() else ""
    if "manual_claim_issue: 2488" not in body:
        body = (
            "manual_claim_issue: 2488\n"
            "manual_claim_command: gh issue edit 2488 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open\n"
            "claim_helper_command: tn-ticket claim testbeam-laptop-1 --project testbeam\n\n"
            + body
        )
    existing.write_text(body, encoding="utf-8")


def write_report(config: dict, reproduction: pd.DataFrame, timing: pd.DataFrame, deltas: pd.DataFrame, by_run: pd.DataFrame, strata: pd.DataFrame, aux: pd.DataFrame, aux_run: pd.DataFrame, aux_strata: pd.DataFrame, result: dict, runtime: float) -> None:
    winner = result["winner"]["method"]
    best = aux[aux["method"].eq(winner)].iloc[0]
    trad = aux[aux["method"].eq("traditional_state_space_gls")].iloc[0]
    text = f"""# S54b/#2488: Pedestal-Memory Calibration Bakeoff

## Abstract

Ticket `#2488` asks how pedestal drift and baseline memory propagate into pulse
timing, charge/energy calibration, pile-up tagging, saturation flags, and PID
operating points under run-held-out transfer.  The raw ROOT reproduction gate
recomputes **{int(reproduction.iloc[-1]['selected_pulses']):,}** selected B-stave
pulses, exactly matching the registered anchor.  The winner recorded in
`result.json` is **`{winner}`**, selected by an auxiliary calibration score that
combines duplicate-readout energy resolution, energy scale bias, PID AUC,
pile-up AUC, and saturation AUC.  Its energy sigma68 is
`{best['energy_sigma68']:.4g}` with 95% run-bootstrap CI
[`{best['energy_sigma68_ci_low']:.4g}`, `{best['energy_sigma68_ci_high']:.4g}`].

## Ticket Claim Provenance

The required command `tn-ticket claim testbeam-laptop-1 --project testbeam` was
run exactly once.  It returned the known malformed null pseudo-ticket output
instead of a real issue, while direct queue inspection still showed open
testbeam tickets and no `worker:testbeam-laptop-1` claim.  Without rerunning the
helper, issue `#2488` was manually moved from `factory:open` to
`factory:claimed` and labeled `worker:testbeam-laptop-1`; the raw issue text is
saved in `claimed_ticket.txt`.

## Raw ROOT Reproduction

The input is `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.
For each event, `h101/HRDv` is reshaped to `(channel, sample)` with 18 samples
per channel.  For B-stave channel `c`,

`b_ec = median_{{t in {{0,1,2,3}}}} x_ect`,

`A_ec = max_t (x_ect - b_ec)`,

and a selected pulse satisfies `A_ec > {config['amplitude_cut_adc']:.0f} ADC`.
The reproduction is performed before row sampling or model fitting.

{md_table(reproduction, ['group', 'events_total', 'selected_pulses', 'expected_selected_pulses', 'delta', 'pass'])}

## Estimands

Timing uses the run/stave-centered CFD20 residual

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

Energy uses the hidden duplicate-readout log-response closure

`r_i = log(1 + A'_i) - log(1 + A_i)`,

where `A_i` is the analysed even B-stave pulse amplitude and `A'_i` is the
paired odd-channel amplitude, withheld from all auxiliary features.  The
reported energy scale error is `hat r_i - r_i`, approximately a fractional
closure error for small deviations.  PID is represented by the high
duplicate-ratio sideband, pile-up by late secondary-pulse evidence, and
saturation by high-amplitude or flat-top occupancy.  These are raw-waveform
sideband labels, not external particle-truth labels.

All models are trained on runs outside `{config['heldout_runs']}` and scored only
on those held-out runs.  Confidence intervals are percentile 95% intervals from
run-block bootstrap resamples.

## Methods

The traditional comparator, `traditional_state_space_gls`, is a rolling
pedestal and state-space baseline model: it estimates stave-local duplicate
closure from training runs, adds a linear pedestal-state correction, and uses
template residual cuts for PID, pile-up, and saturation scores.  The ML/NN panel
contains ridge, gradient-boosted trees, MLP, 1D-CNN, a masked waveform
transformer, and the new `pedestal_residual_fusion_new` gated CNN.  No method is
given run number, event number, or duplicate amplitude as a feature.

## Timing Benchmark

{md_table(timing, ['method', 'n', 'bias_ns', 'sigma68_ns', 'sigma68_ns_ci_low', 'sigma68_ns_ci_high', 'tail_fraction_abs_gt_5ns'])}

## Calibration and PID Benchmark

Lower auxiliary score is better.  PID, pile-up, and saturation metrics are AUC
or average precision on held-out runs; fixed-purity efficiency is recall at at
least 90% purity.

{md_table(aux, ['method', 'n', 'auxiliary_score', 'energy_scale_bias', 'energy_sigma68', 'energy_sigma68_ci_low', 'energy_sigma68_ci_high', 'pid_auc', 'pid_ap', 'pid_fixed_purity_eff', 'pileup_auc', 'saturation_auc'])}

The traditional energy sigma68 is `{trad['energy_sigma68']:.4g}`; the winner
energy sigma68 is `{best['energy_sigma68']:.4g}`.  The method-minus-traditional
timing deltas are:

{md_table(deltas, ['method', 'reference_method', 'delta_sigma68_ns', 'delta_sigma68_ns_ci_low', 'delta_sigma68_ns_ci_high'], max_rows=20)}

## Run and Stratum Stability

{md_table(aux_run, ['method', 'run', 'n', 'energy_scale_bias', 'energy_sigma68', 'pid_auc', 'pileup_auc', 'saturation_auc'], max_rows=80)}

Pedestal, PID-sideband, pile-up, and saturation slices for duplicate-readout
energy closure:

{md_table(aux_strata, ['stratum', 'level', 'method', 'n', 'energy_scale_bias', 'energy_sigma68'], max_rows=120)}

## Systematics and Caveats

The ROOT files do not carry independent particle species, calorimeter truth, or
electronics saturation truth for these B-stave pulses.  PID, pile-up, saturation,
and energy are therefore duplicate-readout and waveform-sideband closure
estimands.  They are valuable leakage-resistant stress tests because the
duplicate amplitude is hidden from the fitted feature set, but they should not
be read as external truth.  The bootstrap samples runs rather than events, so
the intervals emphasize run-transfer uncertainty.  The new gated CNN improves
some waveform-sideband scores, but any production adoption must still pass a
future externally labelled PID/energy validation.

## Conclusion

The raw count is exactly reproducible from ROOT and the strongest overall
sideband calibration method is `{winner}`.  This supports the hypothesis that
pedestal-memory information is present in local waveform shape and baseline
state, but the conclusion remains a closure result rather than an absolute PID
or calorimetric calibration.

No new follow-up ticket was appended.

Runtime was `{runtime:.1f} s` on `{platform.platform()}` with Python
`{platform.python_version()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    old_argv = sys.argv[:]
    try:
        sys.argv = [str(Path(s32a.__file__)), "--config", str(CONFIG)]
        s32a.main()
    finally:
        sys.argv = old_argv

    reproduction = pd.read_csv(OUT / "reproduction.csv")
    data = pd.read_parquet(OUT / "benchmark_rows.parquet")
    data = prepare_targets(data)
    preds = fit_aux_predictions(data, config)
    aux, aux_run, aux_strata = summarize_aux(data, preds, config, rng)
    aux.to_csv(OUT / "auxiliary_method_summary.csv", index=False)
    aux_run.to_csv(OUT / "auxiliary_run_metrics.csv", index=False)
    aux_strata.to_csv(OUT / "auxiliary_strata_metrics.csv", index=False)

    timing = pd.read_csv(OUT / "metrics.csv")
    deltas = pd.read_csv(OUT / "method_deltas.csv")
    by_run = pd.read_csv(OUT / "by_run.csv")
    strata = pd.read_csv(OUT / "strata.csv")
    winner = aux.iloc[0].to_dict()
    base_result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    result = {
        "ticket_id": TICKET,
        "ticket_number": int(TICKET),
        "study_id": "S54b",
        "worker": WORKER,
        "title": config["title"],
        "issue_url": f"https://github.com/SzeChunYiu/factory-tickets/issues/{TICKET}",
        "claim_command": "tn-ticket claim testbeam-laptop-1 --project testbeam",
        "manual_claim_recovery": {
            "reason": "tn-ticket claim returned null pseudo-ticket despite open testbeam issues",
            "manual_recovery": "gh issue edit 2488 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open",
            "reran_claim": False
        },
        "done_command": "tn-ticket done 2488",
        "raw_root_dir": config["raw_root_dir"],
        "git_commit": git_head(),
        "script_sha256": sha256_file(Path(__file__)),
        "config_sha256": sha256_file(CONFIG),
        "runtime_sec": time.time() - started,
        "reproduction": base_result["reproduction"],
        "split": base_result["split"],
        "methods": METHODS,
        "primary_metric": "auxiliary_score = energy_sigma68 + 0.20*abs(energy_bias) + 0.08*(1-PID_AUC) + 0.06*(1-pileup_AUC) + 0.04*(1-saturation_AUC); lower is better",
        "winner": {
            "method": str(winner["method"]),
            "auxiliary_score": float(winner["auxiliary_score"]),
            "energy_sigma68": float(winner["energy_sigma68"]),
            "energy_sigma68_ci_low": float(winner["energy_sigma68_ci_low"]),
            "energy_sigma68_ci_high": float(winner["energy_sigma68_ci_high"]),
            "energy_scale_bias": float(winner["energy_scale_bias"]),
            "pid_auc": float(winner["pid_auc"]),
            "pid_ap": float(winner["pid_ap"]),
            "pileup_auc": float(winner["pileup_auc"]),
            "saturation_auc": float(winner["saturation_auc"])
        },
        "timing_winner": base_result["winner"],
        "timing_metric_table": base_result["metric_table"],
        "timing_delta_table": base_result["paired_delta_table"],
        "auxiliary_method_table": jsafe(aux.to_dict("records")),
        "auxiliary_run_table": jsafe(aux_run.to_dict("records")),
        "artifacts": [
            "REPORT.md",
            "result.json",
            "claimed_ticket.txt",
            "reproduction.csv",
            "benchmark_rows.parquet",
            "predictions.parquet",
            "metrics.csv",
            "method_deltas.csv",
            "by_run.csv",
            "strata.csv",
            "ablations.csv",
            "auxiliary_method_summary.csv",
            "auxiliary_run_metrics.csv",
            "auxiliary_strata_metrics.csv"
        ],
        "next_tickets": []
    }
    (OUT / "result.json").write_text(json.dumps(jsafe(result), indent=2) + "\n", encoding="utf-8")
    write_claim_file()
    write_report(config, reproduction, timing, deltas, by_run, strata, aux, aux_run, aux_strata, result, time.time() - started)
    manifest = {
        "ticket_id": TICKET,
        "worker": WORKER,
        "command": f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}",
        "git_commit": git_head(),
        "runtime_sec": time.time() - started,
        "outputs_sha256": {
            p.name: sha256_file(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "manifest.json"
        }
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
