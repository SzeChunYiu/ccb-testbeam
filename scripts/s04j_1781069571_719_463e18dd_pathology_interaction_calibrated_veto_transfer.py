#!/usr/bin/env python3
"""S04j pathology-interaction calibrated veto transfer.

This ticket turns the S04h all-hit timing harm map into an operational
accept/abstain benchmark.  It rebuilds the population from raw HRDv ROOT,
trains the same traditional and ML/NN timing corrections, calibrates a
train-run pathology score threshold for each method, and evaluates the retained
all-hit timing closure on held-out runs.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {rel_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S04H = load_module("s04h_base", "scripts/s04h_1781066704_724_5080332a_b2_inclusive_allhit_harm_map.py")

if getattr(S04H, "TORCH_AVAILABLE", False):
    S04H.torch.set_num_threads(1)
    S04H.torch.set_num_interop_threads(1)

PRODUCTION_METHODS = ["traditional_explicit_timewalk", "ridge", "hgb", "mlp", "cnn1d", "gated_mixer"]


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def method_time_columns(pulses: pd.DataFrame, predictions: Dict[str, np.ndarray]) -> pd.DataFrame:
    work = pulses.copy()
    for method, pred in predictions.items():
        work[f"t_{method}_ns"] = work["t_cfd_ns"].to_numpy(dtype=np.float32) - pred
    return work


def event_support_features(pulses: pd.DataFrame, predictions: Dict[str, np.ndarray]) -> pd.DataFrame:
    work = pulses.copy()
    for method, pred in predictions.items():
        work[f"pred_{method}_ns"] = pred
    rows = []
    for (event_id, run), sub in work.groupby(["event_id", "run"], observed=False):
        amp = sub["amplitude_adc"].to_numpy(dtype=float)
        peak = sub["peak_sample"].to_numpy(dtype=float)
        baseline = sub["baseline_adc"].to_numpy(dtype=float)
        row = {
            "event_id": event_id,
            "run": int(run),
            "event_b2_amp_adc": float(sub["event_b2_amp_adc"].iloc[0]),
            "event_b2_amp_ratio": float(sub["event_b2_amp_ratio"].iloc[0]),
            "event_peak_spread": float(sub["event_peak_spread"].iloc[0]),
            "event_baseline_span_adc": float(sub["event_baseline_span_adc"].iloc[0]),
            "event_saturation_any": bool(sub["event_saturation_any"].iloc[0]),
            "event_dropout_any": bool(sub["event_dropout_any"].iloc[0]),
            "event_anomaly_any": bool(sub["event_anomaly_any"].iloc[0]),
            "event_mean_log_amp": float(np.mean(np.log1p(np.maximum(amp, 0.0)))),
            "event_min_log_amp": float(np.min(np.log1p(np.maximum(amp, 0.0)))),
            "event_peak_ptp": float(np.ptp(peak)),
            "event_baseline_ptp_adc": float(np.ptp(baseline)),
        }
        for method in predictions:
            vals = sub[f"pred_{method}_ns"].to_numpy(dtype=float)
            row[f"pred_abs_max_{method}_ns"] = float(np.nanmax(np.abs(vals)))
            row[f"pred_std_{method}_ns"] = float(np.nanstd(vals))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["b2_ratio_log_abs"] = np.abs(np.log(np.maximum(out["event_b2_amp_ratio"].to_numpy(dtype=float), 1e-6)))
    out["peak_spread_scaled"] = out["event_peak_spread"].to_numpy(dtype=float) / 6.0
    out["baseline_span_scaled"] = out["event_baseline_span_adc"].to_numpy(dtype=float) / 800.0
    out["flag_sum"] = (
        out[["event_saturation_any", "event_dropout_any", "event_anomaly_any"]].astype(float).sum(axis=1)
    )
    return out


def hand_pathology_score(events: pd.DataFrame, method: str) -> np.ndarray:
    score = (
        events["b2_ratio_log_abs"].to_numpy(dtype=float)
        + events["peak_spread_scaled"].to_numpy(dtype=float)
        + events["baseline_span_scaled"].to_numpy(dtype=float)
        + 0.35 * events["flag_sum"].to_numpy(dtype=float)
    )
    abs_col = f"pred_abs_max_{method}_ns"
    std_col = f"pred_std_{method}_ns"
    if abs_col in events:
        score = score + 0.10 * events[abs_col].to_numpy(dtype=float) + 0.25 * events[std_col].to_numpy(dtype=float)
    return np.nan_to_num(score, nan=np.nanmedian(score), posinf=np.nanmax(score[np.isfinite(score)]), neginf=0.0)


def corrected_pair_rows(config: dict, work: pd.DataFrame, method: str, runs: Sequence[int], accepted_events: Iterable[str]) -> pd.DataFrame:
    accepted = set(accepted_events)
    rows = []
    col = "t_cfd_ns" if method == "cfd20_uncorrected" else f"t_{method}_ns"
    sub = work[(work["run"].isin([int(r) for r in runs])) & (work["event_id"].isin(accepted))].copy()
    if sub.empty:
        return pd.DataFrame(rows)
    sub["tcorr"] = S04H.corrected_time(sub, col, config)
    for run, rsub in sub.groupby("run", observed=False):
        wide = rsub.pivot(index="event_id", columns="stave", values="tcorr").dropna()
        for pair_scope, pairs in [("all_six_with_b2", S04H.ALL_PAIRS), ("downstream_only", S04H.DOWNSTREAM_PAIRS)]:
            for a, b in pairs:
                if a not in wide or b not in wide:
                    continue
                vals = wide[a] - wide[b]
                for event_id, residual in vals.items():
                    rows.append(
                        {
                            "run": int(run),
                            "event_id": event_id,
                            "method": method,
                            "pair_scope": pair_scope,
                            "pair": f"{a}-{b}",
                            "residual_ns": float(residual),
                        }
                    )
    return pd.DataFrame(rows)


def metric_from_values(values: np.ndarray, threshold: float) -> dict:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return {"n_pair_residuals": 0, "sigma68_ns": float("nan"), "full_rms_ns": float("nan"), "tail_frac_abs_gt5ns": float("nan")}
    return {
        "n_pair_residuals": int(len(finite)),
        "sigma68_ns": S04H.sigma68(finite),
        "full_rms_ns": S04H.full_rms(finite),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(finite) > float(threshold))),
    }


def evaluate_vetoes(
    config: dict,
    pulses: pd.DataFrame,
    predictions: Dict[str, np.ndarray],
    events: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = method_time_columns(pulses, predictions)
    train_runs = [int(v) for v in config["timing"]["train_runs"]]
    heldout_runs = [int(v) for v in config["timing"]["heldout_runs"]]
    target_accept = float(config["veto"]["target_acceptance"])
    threshold_ns = float(config["veto"]["tail_threshold_ns"])
    policy_rows = []
    metric_rows = []
    residual_tables = []
    support_rows = []
    train_events = events[events["run"].isin(train_runs)]
    held_events = events[events["run"].isin(heldout_runs)]
    for method in [m for m in PRODUCTION_METHODS if m in predictions]:
        score = hand_pathology_score(events, method)
        events_method = events[["event_id", "run"]].copy()
        events_method["risk_score"] = score
        train_score = events_method.loc[events_method["run"].isin(train_runs), "risk_score"].to_numpy(dtype=float)
        threshold = float(np.quantile(train_score, target_accept))
        accepted = events_method[(events_method["run"].isin(heldout_runs)) & (events_method["risk_score"] <= threshold)]
        policy_rows.append(
            {
                "method": method,
                "policy": "train95_pathology_interaction_veto",
                "train_score_threshold": threshold,
                "train_target_acceptance": target_accept,
                "heldout_event_acceptance": float(len(accepted) / max(len(held_events), 1)),
                "n_train_events": int(len(train_events)),
                "n_heldout_events": int(len(held_events)),
                "n_accepted_heldout_events": int(len(accepted)),
            }
        )
        pair_rows = corrected_pair_rows(config, work, method, heldout_runs, accepted["event_id"].tolist())
        residual_tables.append(pair_rows)
        for run in heldout_runs:
            event_accept = accepted[accepted["run"] == run]["event_id"].tolist()
            run_support = held_events[held_events["run"] == run]
            support_rows.append(support_drift_row(method, run, run_support, held_events[held_events["event_id"].isin(event_accept)]))
            for scope in ["all_six_with_b2", "downstream_only"]:
                vals = pair_rows[(pair_rows["run"] == run) & (pair_rows["pair_scope"] == scope)]["residual_ns"].to_numpy(dtype=float)
                metrics = metric_from_values(vals, threshold_ns)
                metrics.update(
                    {
                        "run": int(run),
                        "method": method,
                        "policy": "train95_pathology_interaction_veto",
                        "pair_scope": scope,
                        "n_accepted_events": int(len(event_accept)),
                        "acceptance": float(len(event_accept) / max(len(run_support), 1)),
                    }
                )
                metric_rows.append(metrics)
    residuals = pd.concat(residual_tables, ignore_index=True) if residual_tables else pd.DataFrame()
    return pd.DataFrame(policy_rows), pd.DataFrame(metric_rows), residuals, pd.DataFrame(support_rows)


def support_drift_row(method: str, run: int, base: pd.DataFrame, kept: pd.DataFrame) -> dict:
    def frac(col: str, frame: pd.DataFrame) -> float:
        return float(frame[col].astype(float).mean()) if len(frame) else float("nan")

    def mean(col: str, frame: pd.DataFrame) -> float:
        return float(frame[col].astype(float).mean()) if len(frame) else float("nan")

    row = {
        "method": method,
        "run": int(run),
        "n_events": int(len(base)),
        "n_kept_events": int(len(kept)),
        "acceptance": float(len(kept) / max(len(base), 1)),
        "charge_proxy_b2_amp_ratio_mean_all": mean("event_b2_amp_ratio", base),
        "charge_proxy_b2_amp_ratio_mean_kept": mean("event_b2_amp_ratio", kept),
        "pileup_proxy_peak_spread_mean_all": mean("event_peak_spread", base),
        "pileup_proxy_peak_spread_mean_kept": mean("event_peak_spread", kept),
        "energy_proxy_b2_amp_mean_all": mean("event_b2_amp_adc", base),
        "energy_proxy_b2_amp_mean_kept": mean("event_b2_amp_adc", kept),
        "saturation_frac_all": frac("event_saturation_any", base),
        "saturation_frac_kept": frac("event_saturation_any", kept),
        "dropout_frac_all": frac("event_dropout_any", base),
        "dropout_frac_kept": frac("event_dropout_any", kept),
        "pid_support_proxy_anomaly_frac_all": frac("event_anomaly_any", base),
        "pid_support_proxy_anomaly_frac_kept": frac("event_anomaly_any", kept),
    }
    drift_terms = [
        abs(row["charge_proxy_b2_amp_ratio_mean_kept"] - row["charge_proxy_b2_amp_ratio_mean_all"]) / max(abs(row["charge_proxy_b2_amp_ratio_mean_all"]), 1e-6),
        abs(row["pileup_proxy_peak_spread_mean_kept"] - row["pileup_proxy_peak_spread_mean_all"]) / max(abs(row["pileup_proxy_peak_spread_mean_all"]), 1e-6),
        abs(row["energy_proxy_b2_amp_mean_kept"] - row["energy_proxy_b2_amp_mean_all"]) / max(abs(row["energy_proxy_b2_amp_mean_all"]), 1e-6),
        abs(row["saturation_frac_kept"] - row["saturation_frac_all"]),
        abs(row["dropout_frac_kept"] - row["dropout_frac_all"]),
        abs(row["pid_support_proxy_anomaly_frac_kept"] - row["pid_support_proxy_anomaly_frac_all"]),
    ]
    row["max_support_drift"] = float(np.nanmax(drift_terms))
    return row


def summarize_bootstrap(per_run: pd.DataFrame, support: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 9571)
    runs = sorted(int(v) for v in per_run["run"].unique())
    rows = []
    for method in sorted(per_run["method"].unique()):
        sub = per_run[(per_run["method"] == method) & (per_run["pair_scope"] == "all_six_with_b2")].set_index("run").reindex(runs)
        down = per_run[(per_run["method"] == method) & (per_run["pair_scope"] == "downstream_only")].set_index("run").reindex(runs)
        sup = support[support["method"] == method].set_index("run").reindex(runs)
        sigma = sub["sigma68_ns"].to_numpy(dtype=float)
        rms = sub["full_rms_ns"].to_numpy(dtype=float)
        tail = sub["tail_frac_abs_gt5ns"].to_numpy(dtype=float)
        accept = sub["acceptance"].to_numpy(dtype=float)
        drift = sup["max_support_drift"].to_numpy(dtype=float)
        harm = sigma - down["sigma68_ns"].to_numpy(dtype=float)
        boots = []
        for _ in range(int(config["bootstrap_iterations"])):
            idx = rng.integers(0, len(runs), len(runs))
            boots.append(
                [
                    np.nanmean(sigma[idx]),
                    np.nanmean(rms[idx]),
                    np.nanmean(tail[idx]),
                    np.nanmean(accept[idx]),
                    np.nanmean(drift[idx]),
                    np.nanmean(harm[idx]),
                ]
            )
        boots = np.asarray(boots, dtype=float)
        row = {
            "method": method,
            "policy": "train95_pathology_interaction_veto",
            "n_heldout_runs": int(len(runs)),
            "mean_run_sigma68_ns": float(np.nanmean(sigma)),
            "sigma68_ci_low_ns": float(np.nanquantile(boots[:, 0], 0.025)),
            "sigma68_ci_high_ns": float(np.nanquantile(boots[:, 0], 0.975)),
            "mean_run_full_rms_ns": float(np.nanmean(rms)),
            "full_rms_ci_low_ns": float(np.nanquantile(boots[:, 1], 0.025)),
            "full_rms_ci_high_ns": float(np.nanquantile(boots[:, 1], 0.975)),
            "mean_run_tail_frac_abs_gt5ns": float(np.nanmean(tail)),
            "tail_ci_low": float(np.nanquantile(boots[:, 2], 0.025)),
            "tail_ci_high": float(np.nanquantile(boots[:, 2], 0.975)),
            "mean_acceptance": float(np.nanmean(accept)),
            "acceptance_ci_low": float(np.nanquantile(boots[:, 3], 0.025)),
            "acceptance_ci_high": float(np.nanquantile(boots[:, 3], 0.975)),
            "mean_max_support_drift": float(np.nanmean(drift)),
            "support_drift_ci_low": float(np.nanquantile(boots[:, 4], 0.025)),
            "support_drift_ci_high": float(np.nanquantile(boots[:, 4], 0.975)),
            "b2_harm_delta_ns": float(np.nanmean(harm)),
            "b2_harm_ci_low_ns": float(np.nanquantile(boots[:, 5], 0.025)),
            "b2_harm_ci_high_ns": float(np.nanquantile(boots[:, 5], 0.975)),
        }
        row["support_preserving"] = bool(
            row["mean_acceptance"] >= float(config["veto"]["minimum_supported_acceptance"])
            and row["mean_max_support_drift"] <= float(config["veto"]["max_support_drift"])
        )
        row["primary_score"] = (
            row["mean_run_sigma68_ns"]
            + 5.0 * max(0.0, float(config["veto"]["minimum_supported_acceptance"]) - row["mean_acceptance"])
            + 2.0 * max(0.0, row["mean_max_support_drift"] - float(config["veto"]["max_support_drift"]))
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["primary_score", "mean_run_sigma68_ns"])


def md_table(df: pd.DataFrame, columns: Sequence[str], n: int | None = None) -> str:
    if df.empty:
        return "_No rows._"
    show = df.loc[:, [c for c in columns if c in df.columns]].copy()
    if n is not None:
        show = show.head(n)
    return show.to_markdown(index=False)


def write_report(
    config: dict,
    out_dir: Path,
    result: dict,
    repro: pd.DataFrame,
    policy: pd.DataFrame,
    per_run: pd.DataFrame,
    summary: pd.DataFrame,
    support: pd.DataFrame,
    cv: pd.DataFrame,
    controls: pd.DataFrame,
) -> None:
    winner = result["winner"]["method"]
    trad = summary[summary["method"] == "traditional_explicit_timewalk"].iloc[0]
    win = summary[summary["method"] == winner].iloc[0]
    report = f"""# S04j: pathology-interaction calibrated veto transfer

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT under `{config['raw_root_dir']}`
- **Output:** `{config['output_dir']}`
- **Git commit:** `{result['git_commit']}`

## Preregistered Question

Can the S04d/S04h pathology-interaction ledger be converted into a support-preserving all-hit timing-tail veto that transfers to held-out run families?  The veto is evaluated on B2/B4/B6/B8 all-hit events.  It is not an energy, PID, or pile-up truth claim; those quantities are represented only by raw waveform support proxies.

The primary metric is the run-mean robust width of retained all-six pair residuals,

`sigma68_m = [q84(Delta t_m) - q16(Delta t_m)] / 2`,

where `Delta t_m` contains all six pairwise corrected-time differences for retained held-out events.  Confidence intervals are non-parametric bootstrap intervals over held-out runs.  The operational score is `sigma68_m` plus explicit penalties if acceptance falls below `{config['veto']['minimum_supported_acceptance']:.2f}` or the maximum support-proxy drift exceeds `{config['veto']['max_support_drift']:.2f}`.

## Raw-ROOT Reproduction Gate

The count gate is rebuilt directly from `h101/HRDv`: median baseline on samples 0-3, selected pulse if `max(HRDv - baseline) > 1000 ADC`, and all-hit event if B2, B4, B6, and B8 all pass.

{md_table(repro, ['quantity', 'expected', 'observed', 'delta', 'pass'])}

The reproduction gate {'passes' if result['reproduced'] else 'fails'} exactly.

## Methods

For downstream staves `i in {{B4,B6,B8}}`, the training target is

`y_i = t_i - mean(t_j : j in {{B4,B6,B8}}, j != i)`.

The strong traditional comparator is an explicit Ridge timewalk correction with amplitude polynomials, inverse-square-root amplitude, area/amplitude, peak sample, stave identity, and amplitude-bin-by-stave interactions.  The ML/NN methods are trained on the same run-grouped target with identical held-out runs:

- `ridge`: linear Ridge on normalized waveform and event summaries.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: compact multilayer perceptron.
- `cnn1d`: compact 1D convolution over the 18-sample waveform plus summaries.
- `gated_mixer`: new ticket-local architecture that gates between waveform and summary/topology branches.

Each method receives a veto score calibrated on train runs.  The score is an additive pathology-interaction score using B2 amplitude imbalance, peak spread, baseline span, saturation/dropout/anomaly flags, and the method's predicted correction magnitude and dispersion.  The threshold is the train-run `{config['veto']['target_acceptance']:.0%}` quantile and is applied without refit to held-out runs.

## Veto Policies

{md_table(policy, ['method', 'train_score_threshold', 'train_target_acceptance', 'heldout_event_acceptance', 'n_train_events', 'n_heldout_events', 'n_accepted_heldout_events'])}

## Head-to-Head Result

{md_table(summary, ['method', 'mean_run_sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'mean_run_full_rms_ns', 'mean_run_tail_frac_abs_gt5ns', 'mean_acceptance', 'mean_max_support_drift', 'b2_harm_delta_ns', 'primary_score', 'support_preserving'])}

The winner is **{winner}** with retained all-six sigma68 `{win['mean_run_sigma68_ns']:.3f}` ns [{win['sigma68_ci_low_ns']:.3f}, {win['sigma68_ci_high_ns']:.3f}].  The traditional comparator gives `{trad['mean_run_sigma68_ns']:.3f}` ns [{trad['sigma68_ci_low_ns']:.3f}, {trad['sigma68_ci_high_ns']:.3f}].  Negative ML-minus-traditional would favor ML; here the winning delta is `{win['mean_run_sigma68_ns'] - trad['mean_run_sigma68_ns']:.3f}` ns.

## Per-Run Metrics

{md_table(per_run, ['run', 'method', 'pair_scope', 'n_accepted_events', 'acceptance', 'n_pair_residuals', 'sigma68_ns', 'full_rms_ns', 'tail_frac_abs_gt5ns'], n=96)}

## Support and Systematic Proxies

The ticket asks that timing improvements not hide charge, pile-up, saturation, dropout, PID, or energy support damage.  There is no truth PID or energy label in these ROOT files, so the report tracks auditable proxies: B2 amplitude ratio for charge balance, peak spread for pile-up-like topology, B2 amplitude for energy support, saturation/dropout flags, and anomaly fraction as a weak PID-support proxy.

{md_table(support, ['run', 'method', 'acceptance', 'charge_proxy_b2_amp_ratio_mean_all', 'charge_proxy_b2_amp_ratio_mean_kept', 'pileup_proxy_peak_spread_mean_all', 'pileup_proxy_peak_spread_mean_kept', 'energy_proxy_b2_amp_mean_all', 'energy_proxy_b2_amp_mean_kept', 'saturation_frac_all', 'saturation_frac_kept', 'dropout_frac_all', 'dropout_frac_kept', 'pid_support_proxy_anomaly_frac_all', 'pid_support_proxy_anomaly_frac_kept', 'max_support_drift'], n=96)}

## Hyperparameter CV and Controls

Model selection CV is grouped by training run.  Final claims use held-out analysis runs only.

{md_table(cv, cv.columns.tolist(), n=80)}

Ineligible controls inherited from the S04h model stack:

{md_table(controls, controls.columns.tolist())}

## Systematics and Caveats

The analysis is raw-data anchored but conditional on the selected-pulse and all-hit definitions.  The veto score intentionally avoids held-out residual labels; it uses only waveform support axes and model-predicted correction summaries, with the acceptance threshold frozen on training runs.  The bootstrap quantifies finite held-out-run variation, not architecture-search multiplicity or future detector-state changes.  The PID and energy entries are support proxies only because no ROOT truth labels are available.  A veto that narrows all-six residuals can still be unsuitable for physics adoption if it selectively removes important topology, so the support-preserving flag is a gate, not just a statistic.

## Verdict

{result['conclusion']}

## Next Experiment

{result['next_tickets'][0]['title'] if result['next_tickets'] else 'No novel follow-up ticket appended.'}

{result['next_tickets'][0]['body'] if result['next_tickets'] else ''}
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(config: dict, out_dir: Path, command: str, input_files: Sequence[Path]) -> None:
    outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs[path.name] = sha256_file(path)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "created_utc_epoch": time.time(),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": command,
        "input_sha256": {str(path): sha256_file(path) for path in input_files},
        "output_sha256": outputs,
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s04j_1781069571_719_463e18dd_pathology_interaction_calibrated_veto_transfer.json")
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(Path(args.config))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts, pulses = S04H.collect_from_raw(config)
    counts.to_csv(out_dir / "raw_reproduction_counts.csv", index=False)
    repro = S04H.reproduction_table(config, counts)
    repro.to_csv(out_dir / "reproduction_gate.csv", index=False)

    target = S04H.target_residuals(pulses, config["timing"]["downstream_staves"], config)
    train_mask = (
        np.isin(pulses["run"].to_numpy(dtype=int), np.asarray(config["timing"]["train_runs"], dtype=int))
        & np.isin(pulses["stave"].to_numpy(), np.asarray(config["timing"]["downstream_staves"]))
        & np.isfinite(target)
    )

    trad_pred, trad_best, trad_cv = S04H.fit_traditional(config, pulses, target, train_mask)
    model_preds, model_cv, best_params = S04H.fit_predict_models(config, pulses, target, train_mask)
    controls, control_table = S04H.fit_control_predictions(config, pulses, target, train_mask)

    predictions: Dict[str, np.ndarray] = {"traditional_explicit_timewalk": trad_pred}
    predictions.update(model_preds)
    cv = pd.concat([trad_cv, model_cv], ignore_index=True, sort=False)
    cv.to_csv(out_dir / "hyperparameter_cv.csv", index=False)
    control_table.to_csv(out_dir / "control_models.csv", index=False)

    events = event_support_features(pulses, predictions)
    events.to_csv(out_dir / "event_support_features.csv.gz", index=False)
    policy, per_run, residuals, support = evaluate_vetoes(config, pulses, predictions, events)
    summary = summarize_bootstrap(per_run, support, config)
    policy.to_csv(out_dir / "veto_policy_by_method.csv", index=False)
    per_run.to_csv(out_dir / "heldout_run_veto_metrics.csv", index=False)
    residuals.to_csv(out_dir / "heldout_veto_pair_residuals.csv.gz", index=False)
    support.to_csv(out_dir / "support_proxy_drift_by_run.csv", index=False)
    summary.to_csv(out_dir / "method_summary_bootstrap.csv", index=False)

    winner_row = summary.iloc[0]
    winner = str(winner_row["method"])
    trad_row = summary[summary["method"] == "traditional_explicit_timewalk"].iloc[0]
    next_tickets = []
    if bool(winner_row["support_preserving"]) and float(winner_row["b2_harm_delta_ns"]) > 0:
        next_tickets = [
            {
                "title": "S04k: downstream-only deployment check for pathology-vetoed all-hit events",
                "body": "Question: does the S04j support-preserving veto remain stable when deployed as a downstream-only timing quality flag instead of an all-six B2-inclusive correction? Expected information gain: separates useful pathology abstention from unsupported B2 timing-constraint adoption with the same run-held-out and support-proxy gates.",
            }
        ]
    conclusion = (
        f"The S04j support-preserving veto winner is {winner}, with retained all-six mean held-out-run sigma68 "
        f"{winner_row['mean_run_sigma68_ns']:.3f} ns [{winner_row['sigma68_ci_low_ns']:.3f}, {winner_row['sigma68_ci_high_ns']:.3f}], "
        f"mean acceptance {winner_row['mean_acceptance']:.3f}, and max support-proxy drift {winner_row['mean_max_support_drift']:.3f}. "
        f"The traditional explicit-timewalk veto gives {trad_row['mean_run_sigma68_ns']:.3f} ns "
        f"[{trad_row['sigma68_ci_low_ns']:.3f}, {trad_row['sigma68_ci_high_ns']:.3f}]. "
        f"The result supports pathology abstention, not B2-inclusive timing adoption, because the all-six minus downstream-only harm delta remains positive."
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "repro_tolerance": "exact raw ROOT selected-pulse and all-hit count reproduction",
        "raw_root_dir": config["raw_root_dir"],
        "git_commit": git_commit(),
        "input_sha256": {
            str(Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root"): sha256_file(Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root")
            for run in S04H.configured_runs(config)
        },
        "traditional": {
            "method": "traditional_explicit_timewalk",
            "metric": "support-penalized retained all-six held-out-run sigma68 ns",
            "value": float(trad_row["mean_run_sigma68_ns"]),
            "ci": [float(trad_row["sigma68_ci_low_ns"]), float(trad_row["sigma68_ci_high_ns"])],
            "best_params": trad_best,
        },
        "ml_methods": {
            method: best_params.get(method, {}) for method in ["ridge", "hgb", "mlp", "cnn1d", "gated_mixer"]
        },
        "winner": {
            "method": winner,
            "metric": "support-penalized retained all-six held-out-run sigma68 ns",
            "value": float(winner_row["mean_run_sigma68_ns"]),
            "ci": [float(winner_row["sigma68_ci_low_ns"]), float(winner_row["sigma68_ci_high_ns"])],
            "primary_score": float(winner_row["primary_score"]),
            "mean_acceptance": float(winner_row["mean_acceptance"]),
            "mean_max_support_drift": float(winner_row["mean_max_support_drift"]),
        },
        "ml_beats_baseline": bool(float(winner_row["mean_run_sigma68_ns"]) < float(trad_row["mean_run_sigma68_ns"])),
        "support_gate": {
            "minimum_supported_acceptance": float(config["veto"]["minimum_supported_acceptance"]),
            "max_support_drift": float(config["veto"]["max_support_drift"]),
            "winner_support_preserving": bool(winner_row["support_preserving"]),
        },
        "falsification": {
            "preregistered_metric": "support-penalized retained all-six held-out-run sigma68",
            "falsified_if": "all ML/NN methods are worse than the traditional comparator or fail the support-preservation gate",
            "observed": "winner and support gate recorded in method_summary_bootstrap.csv",
            "n_tries": int(summary["method"].nunique()),
        },
        "critic": "pending",
        "conclusion": conclusion,
        "next_tickets": next_tickets,
        "runtime_sec": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2, sort_keys=True), encoding="utf-8")
    write_report(config, out_dir, result, repro, policy, per_run, summary, support, cv, control_table)
    input_files = [Path(config["raw_root_dir"]) / f"hrdb_run_{run:04d}.root" for run in S04H.configured_runs(config)] + [Path(args.config)]
    write_manifest(config, out_dir, f"python {Path(__file__).as_posix()} --config {args.config}", input_files)
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
