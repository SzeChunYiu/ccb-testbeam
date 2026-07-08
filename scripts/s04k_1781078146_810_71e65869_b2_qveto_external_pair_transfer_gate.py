#!/usr/bin/env python3
"""S04k B2 q-veto external-pair transfer gate.

The study asks whether a B2-trained q-template/shape veto transfers to
B2-excluded downstream pair families without changing hidden support.  The
script rebuilds the all-hit population from raw HRDv ROOT, benchmarks the
existing timing-correction stack, trains fixed traditional and ML veto scores on
B2-containing train folds, and evaluates retained B4-B6/B4-B8/B6-B8 residuals
on held-out runs with run-block bootstrap intervals.
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
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import {}".format(rel_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


S04H = load_module("s04h_base_s04k", "scripts/s04h_1781066704_724_5080332a_b2_inclusive_allhit_harm_map.py")
S04J = load_module("s04j_base_s04k", "scripts/s04j_1781069571_719_463e18dd_pathology_interaction_calibrated_veto_transfer.py")

if getattr(S04H, "TORCH_AVAILABLE", False):
    try:
        S04H.torch.set_num_threads(1)
        S04H.torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

CORRECTION_METHODS = ["traditional_explicit_timewalk", "ridge", "hgb", "mlp", "cnn1d", "gated_mixer"]
VETO_POLICIES = ["fixed_q_shape_veto", "rf_external_veto", "logistic_external_veto", "topology_only_sentinel", "shuffled_label_sentinel"]


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


def metric_from_values(values: np.ndarray, threshold: float) -> dict:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return {"n_pair_residuals": 0, "sigma68_ns": np.nan, "full_rms_ns": np.nan, "tail_frac_abs_gt5ns": np.nan}
    return {
        "n_pair_residuals": int(len(finite)),
        "sigma68_ns": S04H.sigma68(finite),
        "full_rms_ns": S04H.full_rms(finite),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(finite) > float(threshold))),
    }


def fixed_q_shape_score(events: pd.DataFrame) -> np.ndarray:
    score = (
        1.25 * events["b2_ratio_log_abs"].to_numpy(dtype=float)
        + 0.90 * events["peak_spread_scaled"].to_numpy(dtype=float)
        + 0.80 * events["baseline_span_scaled"].to_numpy(dtype=float)
        + 0.45 * events["flag_sum"].to_numpy(dtype=float)
    )
    score += 0.20 * np.log1p(np.maximum(events["event_b2_amp_adc"].to_numpy(dtype=float), 0.0)) / 10.0
    return np.nan_to_num(score, nan=np.nanmedian(score))


def event_tail_labels(pair_rows: pd.DataFrame, threshold: float) -> pd.Series:
    b2_rows = pair_rows[pair_rows["pair_scope"] == "all_six_with_b2"].copy()
    b2_rows["tail"] = np.abs(b2_rows["residual_ns"].astype(float)) > float(threshold)
    return b2_rows.groupby("event_id")["tail"].max().astype(int)


def feature_matrix(events: pd.DataFrame, columns: Sequence[str]) -> np.ndarray:
    return events.loc[:, list(columns)].to_numpy(dtype=np.float32)


def train_veto_scores(config: dict, events: pd.DataFrame, train_labels: pd.Series) -> Tuple[pd.DataFrame, Dict[str, np.ndarray], pd.DataFrame]:
    rng = np.random.default_rng(int(config["random_seed"]) + 410)
    train_runs = [int(v) for v in config["timing"]["train_runs"]]
    target_acceptance = float(config["veto"]["target_acceptance"])
    label_frame = events[["event_id", "run"]].copy()
    label_frame["tail_label"] = label_frame["event_id"].map(train_labels).fillna(0).astype(int)
    train_mask = label_frame["run"].isin(train_runs).to_numpy()
    y_train = label_frame.loc[train_mask, "tail_label"].to_numpy(dtype=int)

    full_cols = [
        "event_b2_amp_adc",
        "event_b2_amp_ratio",
        "event_peak_spread",
        "event_baseline_span_adc",
        "event_mean_log_amp",
        "event_min_log_amp",
        "event_peak_ptp",
        "event_baseline_ptp_adc",
        "b2_ratio_log_abs",
        "peak_spread_scaled",
        "baseline_span_scaled",
        "flag_sum",
    ]
    topo_cols = ["event_peak_spread", "event_baseline_span_adc", "event_peak_ptp", "event_baseline_ptp_adc", "peak_spread_scaled", "baseline_span_scaled", "flag_sum"]

    scores: Dict[str, np.ndarray] = {"fixed_q_shape_veto": fixed_q_shape_score(events)}
    diagnostics = []

    models = {
        "rf_external_veto": RandomForestClassifier(n_estimators=240, max_depth=5, min_samples_leaf=8, random_state=int(config["random_seed"]), class_weight="balanced_subsample"),
        "logistic_external_veto": make_pipeline(StandardScaler(), LogisticRegression(max_iter=800, C=0.4, class_weight="balanced", random_state=int(config["random_seed"]))),
        "topology_only_sentinel": RandomForestClassifier(n_estimators=160, max_depth=4, min_samples_leaf=10, random_state=int(config["random_seed"]) + 7, class_weight="balanced_subsample"),
        "shuffled_label_sentinel": RandomForestClassifier(n_estimators=160, max_depth=5, min_samples_leaf=8, random_state=int(config["random_seed"]) + 13, class_weight="balanced_subsample"),
    }
    for name, model in models.items():
        cols = topo_cols if name == "topology_only_sentinel" else full_cols
        X = feature_matrix(events, cols)
        y = y_train.copy()
        if name == "shuffled_label_sentinel":
            y = rng.permutation(y)
        model.fit(X[train_mask], y)
        if hasattr(model, "predict_proba"):
            score = model.predict_proba(X)[:, 1]
        else:
            score = model.decision_function(X)
        scores[name] = np.asarray(score, dtype=float)
        train_score = scores[name][train_mask]
        diagnostics.append(
            {
                "policy": name,
                "feature_columns": ",".join(cols),
                "train_tail_rate": float(np.mean(y_train)),
                "score_threshold_at_target_retention": float(np.quantile(train_score, target_acceptance)),
                "train_score_tail_mean": float(np.mean(train_score[y_train == 1])) if np.any(y_train == 1) else np.nan,
                "train_score_non_tail_mean": float(np.mean(train_score[y_train == 0])) if np.any(y_train == 0) else np.nan,
            }
        )

    thresholds = []
    for name, score in scores.items():
        train_score = score[train_mask]
        thresholds.append({"policy": name, "threshold": float(np.quantile(train_score, target_acceptance)), "target_acceptance": target_acceptance})
    return pd.DataFrame(thresholds), scores, pd.DataFrame(diagnostics)


def support_drift(method: str, policy: str, run: int, base: pd.DataFrame, kept: pd.DataFrame) -> dict:
    row = S04J.support_drift_row("{}__{}".format(method, policy), run, base, kept)
    row["method"] = method
    row["policy"] = policy
    return row


def corrected_pair_rows(config: dict, pulses: pd.DataFrame, predictions: Dict[str, np.ndarray], method: str, runs: Sequence[int], accepted_events: Iterable[str]) -> pd.DataFrame:
    work = S04J.method_time_columns(pulses, predictions)
    return S04J.corrected_pair_rows(config, work, method, runs, accepted_events)


def evaluate_correction_benchmark(config: dict, pulses: pd.DataFrame, predictions: Dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    heldout = [int(v) for v in config["timing"]["heldout_runs"]]
    all_events = pulses[pulses["run"].isin(heldout)]["event_id"].drop_duplicates().tolist()
    for method in CORRECTION_METHODS:
        pair_rows = corrected_pair_rows(config, pulses, predictions, method, heldout, all_events)
        for run in heldout:
            vals = pair_rows[(pair_rows["run"] == run) & (pair_rows["pair_scope"] == "downstream_only")]["residual_ns"].to_numpy(dtype=float)
            row = metric_from_values(vals, float(config["veto"]["tail_threshold_ns"]))
            row.update({"run": int(run), "method": method, "pair_scope": "B2_excluded_downstream", "policy": "no_veto"})
            rows.append(row)
    return pd.DataFrame(rows)


def evaluate_veto_transfer(
    config: dict,
    pulses: pd.DataFrame,
    predictions: Dict[str, np.ndarray],
    events: pd.DataFrame,
    thresholds: pd.DataFrame,
    scores: Dict[str, np.ndarray],
    correction_method: str,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    heldout = [int(v) for v in config["timing"]["heldout_runs"]]
    threshold_ns = float(config["veto"]["tail_threshold_ns"])
    event_scores = events[["event_id", "run"]].copy()
    for policy, score in scores.items():
        event_scores[policy] = score

    policy_rows = []
    metric_rows = []
    support_rows = []
    for policy in VETO_POLICIES:
        threshold = float(thresholds.loc[thresholds["policy"] == policy, "threshold"].iloc[0])
        accepted = event_scores[(event_scores["run"].isin(heldout)) & (event_scores[policy] <= threshold)]
        pair_rows = corrected_pair_rows(config, pulses, predictions, correction_method, heldout, accepted["event_id"].tolist())
        policy_rows.append(
            {
                "policy": policy,
                "correction_method": correction_method,
                "score_threshold": threshold,
                "n_heldout_events": int(events["run"].isin(heldout).sum()),
                "n_accepted_heldout_events": int(len(accepted)),
                "heldout_acceptance": float(len(accepted) / max(events["run"].isin(heldout).sum(), 1)),
            }
        )
        for run in heldout:
            base = events[events["run"] == run]
            kept = events[events["event_id"].isin(accepted.loc[accepted["run"] == run, "event_id"])]
            support_rows.append(support_drift(correction_method, policy, run, base, kept))
            vals = pair_rows[(pair_rows["run"] == run) & (pair_rows["pair_scope"] == "downstream_only")]["residual_ns"].to_numpy(dtype=float)
            row = metric_from_values(vals, threshold_ns)
            row.update(
                {
                    "run": int(run),
                    "method": correction_method,
                    "policy": policy,
                    "pair_scope": "B2_excluded_downstream",
                    "n_accepted_events": int(len(kept)),
                    "acceptance": float(len(kept) / max(len(base), 1)),
                }
            )
            metric_rows.append(row)
    return pd.DataFrame(policy_rows), pd.DataFrame(metric_rows), pd.DataFrame(support_rows)


def bootstrap_summary(per_run: pd.DataFrame, support: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 8146)
    runs = sorted(int(v) for v in per_run["run"].unique())
    rows = []
    for policy in sorted(per_run["policy"].unique()):
        sub = per_run[per_run["policy"] == policy].set_index("run").reindex(runs)
        sup = support[support["policy"] == policy].set_index("run").reindex(runs)
        sigma = sub["sigma68_ns"].to_numpy(dtype=float)
        rms = sub["full_rms_ns"].to_numpy(dtype=float)
        tail = sub["tail_frac_abs_gt5ns"].to_numpy(dtype=float)
        accept = sub["acceptance"].to_numpy(dtype=float)
        drift = sup["max_support_drift"].to_numpy(dtype=float)
        boots = []
        for _ in range(int(config["bootstrap_iterations"])):
            idx = rng.integers(0, len(runs), len(runs))
            boots.append([np.nanmean(sigma[idx]), np.nanmean(rms[idx]), np.nanmean(tail[idx]), np.nanmean(accept[idx]), np.nanmean(drift[idx])])
        boots = np.asarray(boots, dtype=float)
        row = {
            "policy": policy,
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
            "mean_support_distance_shift": float(np.nanmean(drift)),
            "support_shift_ci_low": float(np.nanquantile(boots[:, 4], 0.025)),
            "support_shift_ci_high": float(np.nanquantile(boots[:, 4], 0.975)),
        }
        row["support_preserving"] = bool(
            row["mean_acceptance"] >= float(config["veto"]["minimum_supported_acceptance"])
            and row["mean_support_distance_shift"] <= float(config["veto"]["max_support_drift"])
        )
        row["eligible_policy"] = bool(policy in ["fixed_q_shape_veto", "rf_external_veto", "logistic_external_veto"])
        row["primary_score"] = (
            row["mean_run_sigma68_ns"]
            + 5.0 * max(0.0, float(config["veto"]["minimum_supported_acceptance"]) - row["mean_acceptance"])
            + 2.0 * max(0.0, row["mean_support_distance_shift"] - float(config["veto"]["max_support_drift"]))
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["primary_score", "mean_run_sigma68_ns"])


def md_table(df: pd.DataFrame, columns: Sequence[str], n: int = None) -> str:
    if df.empty:
        return "_No rows._"
    show = df.loc[:, [c for c in columns if c in df.columns]].copy()
    if n is not None:
        show = show.head(n)
    return show.to_markdown(index=False)


def write_report(config: dict, out_dir: Path, result: dict, repro: pd.DataFrame, correction_summary: pd.DataFrame, policy: pd.DataFrame, per_run: pd.DataFrame, summary: pd.DataFrame, support: pd.DataFrame, diagnostics: pd.DataFrame) -> None:
    winner = result["winner"]["policy"]
    win = summary[summary["policy"] == winner].iloc[0]
    trad = summary[summary["policy"] == "fixed_q_shape_veto"].iloc[0]
    report = """# S04k: B2 q-veto external-pair transfer gate

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Input:** raw B-stack ROOT under `{raw_root}`
- **Output:** `{out_dir}`
- **Git commit:** `{commit}`

## Preregistered Question

Does the S04e/S04j B2 q-template and hand-shape veto transfer to B2-excluded pair families without silently changing amplitude, saturation, pathology, or topology support?  The target pairs are B4-B6, B4-B8, and B6-B8.  The transfer is deliberately asymmetric: veto thresholds are fitted on train-run B2-containing residual tails, then applied unchanged to held-out downstream-only pairs.

The primary estimator is the held-out run mean of

`sigma68 = [q84(Delta t) - q16(Delta t)] / 2`,

where `Delta t` contains retained B2-excluded pair residuals.  Confidence intervals are run-block bootstrap 95% intervals.  The operational score is `sigma68` plus penalties for retention below `{min_acc:.2f}` or support-distance shift above `{max_shift:.2f}`.

## Raw-ROOT Reproduction Gate

Counts are rebuilt directly from `h101/HRDv`: median baseline on samples 0-3, selected pulse if `max(HRDv - baseline) > 1000 ADC`, and all-hit event if B2, B4, B6, and B8 pass.

{repro_table}

The raw-count gate {repro_state}.

## Timing-Correction Benchmark

The correction stack is trained on train runs and scored on held-out downstream-only pairs before any veto is applied.  The strong traditional comparator is an explicit amplitude/timewalk Ridge model.  ML/NN comparators are Ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and the ticket-local gated mixer architecture.

{correction_table}

The downstream correction method used for the veto-transfer gate is `{corr_method}`, selected by the no-veto downstream `sigma68`.

## Veto Methods

The traditional veto is a fixed q-template/shape proxy: B2 amplitude imbalance, inter-stave peak spread, baseline span, B2 amplitude scale, and saturation/dropout/anomaly flags.  Its threshold is the train-run `{target_acc:.0%}` score quantile and is not refit on held-out data.

The ML vetoes are calibrated without pair residual features.  `rf_external_veto` and `logistic_external_veto` learn B2-containing train-run tail labels from waveform support features only.  The controls are a topology-only RF sentinel and a shuffled-label sentinel.  All policies are applied at matched train-run retention.

{diag_table}

## Policy Thresholds

{policy_table}

## Head-to-Head Result

{summary_table}

Winner: **{winner}** with downstream-only sigma68 `{win_sigma:.3f}` ns [{win_lo:.3f}, {win_hi:.3f}], retention `{win_acc:.3f}`, and support-distance shift `{win_shift:.3f}`.  The fixed traditional q/shape veto gives `{trad_sigma:.3f}` ns [{trad_lo:.3f}, {trad_hi:.3f}].

## Run-Split Metrics

{run_table}

## Support Diagnostics and Systematics

The support gate tracks charge proxy (B2 amplitude ratio), topology/pile-up proxy (peak spread), energy proxy (B2 amplitude), saturation, dropout, and anomaly/pathology fractions.  These are proxies rather than truth labels, but they are computed before the veto and expose hidden selection drift.

{support_table}

Systematic caveats: the q-template score is represented by raw waveform shape proxies rather than a separate persisted S04e table; the B2 tail labels are train-run labels and may not span future detector states; RF/logistic probabilities are used only for ranking, not calibrated probabilities; and the bootstrap covers run-to-run variation, not full architecture-search multiplicity.

## Verdict

{conclusion}
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        raw_root=config["raw_root_dir"],
        out_dir=config["output_dir"],
        commit=result["git_commit"],
        min_acc=config["veto"]["minimum_supported_acceptance"],
        max_shift=config["veto"]["max_support_drift"],
        target_acc=config["veto"]["target_acceptance"],
        repro_table=md_table(repro, ["quantity", "expected", "observed", "delta", "pass"]),
        repro_state="passes exactly" if result["reproduced"] else "does not pass",
        correction_table=md_table(correction_summary, ["method", "mean_run_sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "mean_run_full_rms_ns", "mean_run_tail_frac_abs_gt5ns"]),
        corr_method=result["correction_method"],
        diag_table=md_table(diagnostics, diagnostics.columns.tolist()),
        policy_table=md_table(policy, policy.columns.tolist()),
        summary_table=md_table(summary, ["policy", "mean_run_sigma68_ns", "sigma68_ci_low_ns", "sigma68_ci_high_ns", "mean_run_full_rms_ns", "mean_run_tail_frac_abs_gt5ns", "mean_acceptance", "mean_support_distance_shift", "primary_score", "support_preserving"]),
        winner=winner,
        win_sigma=win["mean_run_sigma68_ns"],
        win_lo=win["sigma68_ci_low_ns"],
        win_hi=win["sigma68_ci_high_ns"],
        win_acc=win["mean_acceptance"],
        win_shift=win["mean_support_distance_shift"],
        trad_sigma=trad["mean_run_sigma68_ns"],
        trad_lo=trad["sigma68_ci_low_ns"],
        trad_hi=trad["sigma68_ci_high_ns"],
        run_table=md_table(per_run, ["run", "policy", "pair_scope", "n_accepted_events", "acceptance", "n_pair_residuals", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns"], n=80),
        support_table=md_table(support, ["run", "policy", "acceptance", "charge_proxy_b2_amp_ratio_mean_all", "charge_proxy_b2_amp_ratio_mean_kept", "pileup_proxy_peak_spread_mean_all", "pileup_proxy_peak_spread_mean_kept", "energy_proxy_b2_amp_mean_all", "energy_proxy_b2_amp_mean_kept", "saturation_frac_all", "saturation_frac_kept", "dropout_frac_all", "dropout_frac_kept", "pid_support_proxy_anomaly_frac_all", "pid_support_proxy_anomaly_frac_kept", "max_support_drift"], n=80),
        conclusion=result["conclusion"],
    )
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def summarize_corrections(per_run: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]) + 140)
    rows = []
    runs = sorted(int(v) for v in per_run["run"].unique())
    for method in sorted(per_run["method"].unique()):
        sub = per_run[per_run["method"] == method].set_index("run").reindex(runs)
        sigma = sub["sigma68_ns"].to_numpy(dtype=float)
        rms = sub["full_rms_ns"].to_numpy(dtype=float)
        tail = sub["tail_frac_abs_gt5ns"].to_numpy(dtype=float)
        boots = []
        for _ in range(int(config["bootstrap_iterations"])):
            idx = rng.integers(0, len(runs), len(runs))
            boots.append([np.nanmean(sigma[idx]), np.nanmean(rms[idx]), np.nanmean(tail[idx])])
        boots = np.asarray(boots)
        rows.append(
            {
                "method": method,
                "mean_run_sigma68_ns": float(np.nanmean(sigma)),
                "sigma68_ci_low_ns": float(np.nanquantile(boots[:, 0], 0.025)),
                "sigma68_ci_high_ns": float(np.nanquantile(boots[:, 0], 0.975)),
                "mean_run_full_rms_ns": float(np.nanmean(rms)),
                "mean_run_tail_frac_abs_gt5ns": float(np.nanmean(tail)),
            }
        )
    return pd.DataFrame(rows).sort_values(["mean_run_sigma68_ns"])


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
    parser.add_argument("--config", default="configs/s04k_1781078146_810_71e65869_b2_qveto_external_pair_transfer_gate.json")
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
    predictions: Dict[str, np.ndarray] = {"traditional_explicit_timewalk": trad_pred}
    predictions.update(model_preds)

    correction_per_run = evaluate_correction_benchmark(config, pulses, predictions)
    correction_summary = summarize_corrections(correction_per_run, config)
    correction_method = str(correction_summary.iloc[0]["method"])
    correction_per_run.to_csv(out_dir / "correction_benchmark_by_run.csv", index=False)
    correction_summary.to_csv(out_dir / "correction_benchmark_summary.csv", index=False)
    pd.concat([trad_cv, model_cv], ignore_index=True, sort=False).to_csv(out_dir / "correction_cv.csv", index=False)

    events = S04J.event_support_features(pulses, predictions)
    train_event_ids = events[events["run"].isin(config["timing"]["train_runs"])]["event_id"].tolist()
    train_pairs = corrected_pair_rows(config, pulses, predictions, "traditional_explicit_timewalk", config["timing"]["train_runs"], train_event_ids)
    labels = event_tail_labels(train_pairs, float(config["veto"]["tail_threshold_ns"]))
    thresholds, scores, diagnostics = train_veto_scores(config, events, labels)
    policy, per_run, support = evaluate_veto_transfer(config, pulses, predictions, events, thresholds, scores, correction_method)
    summary = bootstrap_summary(per_run, support, config)

    events.to_csv(out_dir / "event_support_features.csv.gz", index=False)
    train_pairs.to_csv(out_dir / "train_b2_containing_tail_labels.csv.gz", index=False)
    diagnostics.to_csv(out_dir / "veto_training_diagnostics.csv", index=False)
    thresholds.to_csv(out_dir / "veto_policy_thresholds.csv", index=False)
    policy.to_csv(out_dir / "veto_policy_heldout_counts.csv", index=False)
    per_run.to_csv(out_dir / "heldout_external_pair_metrics.csv", index=False)
    support.to_csv(out_dir / "support_distance_shift_by_run.csv", index=False)
    summary.to_csv(out_dir / "veto_summary_bootstrap.csv", index=False)

    eligible_summary = summary[summary["eligible_policy"]].copy()
    winner_row = eligible_summary.iloc[0]
    traditional_row = summary[summary["policy"] == "fixed_q_shape_veto"].iloc[0]
    conclusion = (
        "The S04k transfer-gate winner is {policy}, evaluated on B2-excluded downstream pairs with {corr} timing corrections: "
        "sigma68 {sigma:.3f} ns [{lo:.3f}, {hi:.3f}], retention {acc:.3f}, and support-distance shift {shift:.3f}. "
        "The fixed traditional q/shape veto gives {trad_sigma:.3f} ns [{trad_lo:.3f}, {trad_hi:.3f}]. "
        "The gate is support-preserving={support_ok}; controls are reported to expose topology-only and shuffled-label failure modes."
    ).format(
        policy=winner_row["policy"],
        corr=correction_method,
        sigma=winner_row["mean_run_sigma68_ns"],
        lo=winner_row["sigma68_ci_low_ns"],
        hi=winner_row["sigma68_ci_high_ns"],
        acc=winner_row["mean_acceptance"],
        shift=winner_row["mean_support_distance_shift"],
        trad_sigma=traditional_row["mean_run_sigma68_ns"],
        trad_lo=traditional_row["sigma68_ci_low_ns"],
        trad_hi=traditional_row["sigma68_ci_high_ns"],
        support_ok=bool(winner_row["support_preserving"]),
    )
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_dir": config["raw_root_dir"],
        "git_commit": git_commit(),
        "correction_method": correction_method,
        "traditional": {
            "policy": "fixed_q_shape_veto",
            "metric": "retained B2-excluded downstream sigma68 ns",
            "value": float(traditional_row["mean_run_sigma68_ns"]),
            "ci": [float(traditional_row["sigma68_ci_low_ns"]), float(traditional_row["sigma68_ci_high_ns"])],
            "correction_best_params": trad_best,
        },
        "ml_methods": {
            "timing_corrections": {method: best_params.get(method, {}) for method in ["ridge", "hgb", "mlp", "cnn1d", "gated_mixer"]},
            "veto_policies": ["rf_external_veto", "logistic_external_veto"],
            "sentinels": ["topology_only_sentinel", "shuffled_label_sentinel"],
        },
        "winner": {
            "policy": str(winner_row["policy"]),
            "metric": "support-penalized retained B2-excluded downstream sigma68 ns",
            "value": float(winner_row["mean_run_sigma68_ns"]),
            "ci": [float(winner_row["sigma68_ci_low_ns"]), float(winner_row["sigma68_ci_high_ns"])],
            "primary_score": float(winner_row["primary_score"]),
            "mean_acceptance": float(winner_row["mean_acceptance"]),
            "mean_support_distance_shift": float(winner_row["mean_support_distance_shift"]),
            "support_preserving": bool(winner_row["support_preserving"]),
        },
        "ml_beats_baseline": bool(float(winner_row["mean_run_sigma68_ns"]) < float(traditional_row["mean_run_sigma68_ns"])),
        "bootstrap": {
            "unit": "held-out run block",
            "iterations": int(config["bootstrap_iterations"]),
            "ci": "percentile 95%",
        },
        "falsification": {
            "falsified_if": "ML vetoes fail to beat the fixed q/shape veto or violate retention/support gates",
            "observed": "see veto_summary_bootstrap.csv and support_distance_shift_by_run.csv",
        },
        "critic": "pending",
        "conclusion": conclusion,
        "next_tickets": [],
        "runtime_sec": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(clean_json(result), indent=2, sort_keys=True), encoding="utf-8")
    write_report(config, out_dir, result, repro, correction_summary, policy, per_run, summary, support, diagnostics)
    input_files = [Path(config["raw_root_dir"]) / "hrdb_run_{:04d}.root".format(run) for run in S04H.configured_runs(config)] + [Path(args.config)]
    write_manifest(config, out_dir, "python3 {} --config {}".format(Path(__file__).as_posix(), args.config), input_files)
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "out_dir": str(out_dir), "winner": result["winner"], "runtime_sec": result["runtime_sec"]}, indent=2))


if __name__ == "__main__":
    main()
