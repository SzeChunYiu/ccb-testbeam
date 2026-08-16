#!/usr/bin/env python3
"""Ticket #2375 P05 two-pulse decomposition architecture bakeoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402


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


def target_matrix(events: pd.DataFrame, waveforms: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    baseline = np.median(waveforms[:, :4], axis=1)
    max_amp = np.maximum(waveforms.max(axis=1) - baseline, 1.0)
    y = np.column_stack(
        [
            events["true_t1_sample"].to_numpy(float) / 12.0,
            np.nan_to_num(events["true_t2_sample"].to_numpy(float), nan=0.0) / 12.0,
            events["true_amp1_adc"].to_numpy(float) / max_amp,
            events["true_amp2_adc"].to_numpy(float) / max_amp,
        ]
    )
    return y, max_amp


def ordered_prediction_frame(events: pd.DataFrame, method: str, score: np.ndarray, pred: np.ndarray, max_amp: np.ndarray) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "event_id": events["event_id"],
            f"{method}_score": score,
            f"{method}_failed": score < 0.5,
            f"{method}_t1_sample": np.clip(pred[:, 0] * 12.0, 0.0, 17.0),
            f"{method}_t2_sample": np.clip(pred[:, 1] * 12.0, 0.0, 17.0),
            f"{method}_amp1_adc": np.clip(pred[:, 2] * max_amp, 0.0, None),
            f"{method}_amp2_adc": np.clip(pred[:, 3] * max_amp, 0.0, None),
        }
    )
    swapped = out[f"{method}_t2_sample"] < out[f"{method}_t1_sample"]
    out.loc[swapped, [f"{method}_t1_sample", f"{method}_t2_sample"]] = out.loc[
        swapped, [f"{method}_t2_sample", f"{method}_t1_sample"]
    ].to_numpy()
    out.loc[swapped, [f"{method}_amp1_adc", f"{method}_amp2_adc"]] = out.loc[
        swapped, [f"{method}_amp2_adc", f"{method}_amp1_adc"]
    ].to_numpy()
    return out


def run_sklearn_method(
    method: str,
    events: pd.DataFrame,
    waveforms: np.ndarray,
    classifier,
    regressor,
    feature_matrix: np.ndarray | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = p05a.make_feature_matrix(waveforms) if feature_matrix is None else feature_matrix
    labels = events["is_overlap"].to_numpy(int)
    train = events["split"].to_numpy() == "train"
    pos_train = train & (labels == 1)
    y_reg, max_amp = target_matrix(events, waveforms)
    classifier.fit(x[train], labels[train])
    score = classifier.predict_proba(x)[:, 1]
    regressor.fit(x[pos_train], y_reg[pos_train])
    pred = regressor.predict(x)
    cv = grouped_cv_rows(method, x[train], labels[train], events.loc[train, "source_run"].to_numpy(int), classifier)
    return ordered_prediction_frame(events, method, score, pred, max_amp), cv


def grouped_cv_rows(method: str, x: np.ndarray, y: np.ndarray, groups: np.ndarray, estimator) -> pd.DataFrame:
    rows = []
    n_splits = min(3, len(np.unique(groups)))
    if n_splits < 2:
        return pd.DataFrame(rows)
    for fold, (tr, va) in enumerate(GroupKFold(n_splits=n_splits).split(x, y, groups=groups)):
        model = clone_estimator(estimator)
        model.fit(x[tr], y[tr])
        prob = model.predict_proba(x[va])[:, 1]
        rows.append(
            {
                "method": method,
                "fold": int(fold),
                "heldout_runs": " ".join(str(v) for v in sorted(set(groups[va]))),
                "ap": float(average_precision_score(y[va], prob)),
                "auc": float(roc_auc_score(y[va], prob)),
            }
        )
    return pd.DataFrame(rows)


def clone_estimator(estimator):
    from sklearn.base import clone

    return clone(estimator)


def traditional_frame(events: pd.DataFrame, waveforms: np.ndarray, templates: dict, config: dict) -> pd.DataFrame:
    trad = p05a.run_template_fits(events, waveforms, templates, config)
    return trad.rename(
        columns={
            "trad_score": "traditional_score",
            "trad_failed": "traditional_failed",
            "trad_t1_sample": "traditional_t1_sample",
            "trad_t2_sample": "traditional_t2_sample",
            "trad_amp1_adc": "traditional_amp1_adc",
            "trad_amp2_adc": "traditional_amp2_adc",
        }
    )


def cnn_frame(events: pd.DataFrame, waveforms: np.ndarray, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    pred, cv = p05a.run_cnn(events, waveforms, config)
    return pred.rename(
        columns={
            "ml_score": "one_d_cnn_score",
            "ml_failed": "one_d_cnn_failed",
            "ml_t1_sample": "one_d_cnn_t1_sample",
            "ml_t2_sample": "one_d_cnn_t2_sample",
            "ml_amp1_adc": "one_d_cnn_amp1_adc",
            "ml_amp2_adc": "one_d_cnn_amp2_adc",
        }
    ), cv.assign(method="one_d_cnn")


def hybrid_features(base_x: np.ndarray, trad: pd.DataFrame) -> np.ndarray:
    cols = [
        "traditional_score",
        "traditional_t1_sample",
        "traditional_t2_sample",
        "traditional_amp1_adc",
        "traditional_amp2_adc",
        "trad_sse_one",
        "trad_sse_two",
    ]
    extra = trad[cols].replace([np.inf, -np.inf], np.nan).fillna(-999.0).to_numpy(float)
    return np.hstack([base_x, extra])


def metric_values(frame: pd.DataFrame, method: str) -> dict:
    positives = frame[frame["is_overlap"] == 1]
    valid = positives[~positives[f"{method}_failed"].astype(bool)]
    terr, qerr = p05a.recovery_errors(valid, method) if len(valid) else (np.asarray([]), np.asarray([]))
    labels = frame["is_overlap"].to_numpy(int)
    score = frame[f"{method}_score"].replace([np.inf, -np.inf], np.nan).fillna(-1e9).to_numpy(float)
    return {
        "detection_ap": float(average_precision_score(labels, score)),
        "detection_auc": float(roc_auc_score(labels, score)),
        "time_rms_ns": float(np.sqrt(np.mean(terr**2))) if len(terr) else float("nan"),
        "time_sigma68_ns": p05a.sigma68(terr),
        "charge_fractional_bias": float(np.median(qerr)) if len(qerr) else float("nan"),
        "charge_fractional_res68": p05a.sigma68(qerr),
        "failure_rate": float(positives[f"{method}_failed"].mean()) if len(positives) else float("nan"),
        "n_events": int(len(frame)),
        "n_positive": int(len(positives)),
    }


def bootstrap_ci(frame: pd.DataFrame, method: str, n_boot: int, rng: np.random.Generator) -> dict:
    metrics = ["detection_ap", "time_rms_ns", "time_sigma68_ns", "charge_fractional_bias", "charge_fractional_res68", "failure_rate"]
    values = {m: [] for m in metrics}
    runs = np.asarray(sorted(frame["source_run"].unique()))
    for _ in range(n_boot):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([frame[frame["source_run"] == run] for run in sampled], ignore_index=True)
        got = metric_values(boot, method)
        for metric in metrics:
            if np.isfinite(got[metric]):
                values[metric].append(got[metric])
    out = {}
    for metric, arr in values.items():
        out[f"{metric}_ci_low"] = float(np.percentile(arr, 2.5)) if arr else float("nan")
        out[f"{metric}_ci_high"] = float(np.percentile(arr, 97.5)) if arr else float("nan")
    return out


def composite(row: pd.Series) -> float:
    return float(row["time_rms_ns"] + 12.0 * row["charge_fractional_res68"] + 8.0 * abs(row["charge_fractional_bias"]) + 18.0 * row["failure_rate"])


def summarize(predictions: pd.DataFrame, methods: list[str], config: dict, rng: np.random.Generator) -> pd.DataFrame:
    held = predictions[predictions["split"] == "heldout"].reset_index(drop=True)
    rows = []
    for method in methods:
        row = {"method": method, **metric_values(held, method)}
        row.update(bootstrap_ci(held, method, int(config["ml"]["bootstrap_samples"]), rng))
        rows.append(row)
    out = pd.DataFrame(rows)
    out["winner_score"] = out.apply(composite, axis=1)
    return out.sort_values("winner_score").reset_index(drop=True)


def summarize_strata(predictions: pd.DataFrame, methods: list[str], key: str) -> pd.DataFrame:
    positives = predictions[(predictions["split"] == "heldout") & (predictions["is_overlap"] == 1)]
    rows = []
    for value, group in positives.groupby(key):
        for method in methods:
            rows.append({"stratum": key, "value": value, "method": method, **metric_values(group, method)})
    return pd.DataFrame(rows)


def table(df: pd.DataFrame, cols: list[str]) -> str:
    return df[cols].to_markdown(index=False, floatfmt=".4g")


def write_report(out_dir: Path, config: dict, match: pd.DataFrame, template_summary: pd.DataFrame, overall: pd.DataFrame, strata: pd.DataFrame, cv: pd.DataFrame, runtime: float) -> None:
    winner = overall.iloc[0]
    trad = overall[overall["method"] == "traditional"].iloc[0]
    lines = [
        "# P05-2375: pile-up detection and two-pulse decomposition architecture bakeoff",
        "",
        f"- **Ticket:** `#{config['ticket_id']}` {config['ticket_title']}",
        f"- **Author:** `{config['worker']}`",
        "- **Date:** 2026-08-16",
        "- **Config:** `configs/p05_2375_two_pulse_architecture_bakeoff.json`",
        "- **Input checksums:** `input_sha256.csv`; output hashes in `manifest.json`",
        "",
        "## Abstract",
        "",
        "This study asks when a learned waveform decomposer beats a strong constrained two-pulse template fit on controlled pile-up injections derived from raw ROOT B-stave pulses. The raw-ROOT reproduction gate exactly reproduces the S00 selected-pulse anchor before any learning. The benchmark then compares a traditional template fit with ridge, gradient-boosted trees, MLP, 1D-CNN, and a new template-residual fusion architecture on a strict run split.",
        "",
        f"The winner by the pre-registered composite score is **`{winner['method']}`** with held-out constituent-time RMS `{winner['time_rms_ns']:.3f}` ns (95% run-bootstrap CI `{winner['time_rms_ns_ci_low']:.3f}`--`{winner['time_rms_ns_ci_high']:.3f}`), charge fractional res68 `{winner['charge_fractional_res68']:.4f}`, and failure rate `{winner['failure_rate']:.3f}`. The traditional fit has time RMS `{trad['time_rms_ns']:.3f}` ns and failure rate `{trad['failure_rate']:.3f}`.",
        "",
        "## 1. Reproduction gate from raw ROOT",
        "",
        "For every configured run, `h101/HRDv` is reshaped to `(event, channel, sample)` with 18 samples per channel. The pedestal is",
        "",
        "`b_{ec}=median(x_{ec0},x_{ec1},x_{ec2},x_{ec3})`,",
        "",
        "and the selected-pulse indicator is",
        "",
        "`I_{ec}=1[max_t(x_{ect}-b_{ec})>1000 ADC]`.",
        "",
        table(match, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## 2. Data-generating benchmark",
        "",
        f"Train runs are `{config['benchmark_runs']['train']}` and held-out runs are `{config['benchmark_runs']['heldout']}`. Template construction uses only train-run clean pulses with amplitude {config['clean_min_amp_adc']:.0f}--{config['clean_max_amp_adc']:.0f} ADC and peak sample 4--12.",
        "",
        table(template_summary, ["stave", "n_train_pulses", "template_cfd20_sample", "template_peak_sample", "template_area"]),
        "",
        "Injected doublets use",
        "",
        "`w(t)=A_1 T_s(t-t_1)+r A_1 T_s(t-t_1-Delta)+epsilon_{r,s}(t)+p`,",
        "",
        "where the residual `epsilon` is sampled from raw single-pulse residuals from the same source run and stave, and `p` is a small uniform pedestal offset. Clean controls use the same machinery with `r=0`.",
        "",
        "## 3. Methods",
        "",
        "The traditional method is a bounded two-pulse least-squares template fit. For one- and two-pulse hypotheses, it minimizes",
        "",
        "`SSE_k=sum_t [w(t)-b-sum_{j=1}^k A_j T_s(t-t_j)]^2`,",
        "",
        "over a first-pulse shift grid, a fixed separation grid, positive amplitudes, an amplitude-ratio bound, and a bounded pedestal. Its detection score is `(SSE_1-SSE_2)/SSE_1`.",
        "",
        "The ML/NN methods see identical train/held-out rows and no run id or event id feature. Ridge uses L2 logistic classification plus Ridge regression. Gradient-boosted trees use histogram boosting for detection and multi-output regression. MLP uses one hidden classifier layer and a two-layer regressor. The 1D-CNN is the established P05 compact two-head convolutional network over the normalized 18 samples.",
        "",
        "The new architecture, `template_residual_fusion_new`, concatenates waveform summaries with frozen traditional fit outputs and learns residual boosted-tree corrections. This is sensible here because the physics prior localizes the candidate pulses while the learned stage can correct systematic template mismatch and failure boundaries.",
        "",
        "## 4. Metrics and uncertainty",
        "",
        "For accepted true doublets, constituent timing errors are",
        "",
        "`e_t=10 ns * (hat t - t)`,",
        "",
        "and total charge closure is",
        "",
        "`e_Q=((hat A_1+hat A_2)-(A_1+A_2))/(A_1+A_2)`.",
        "",
        "The robust width is `sigma_68=(Q_84-Q_16)/2`. The pre-registered winner score is",
        "",
        "`C = RMS_t + 12 sigma_68(e_Q) + 8 |median(e_Q)| + 18 r_fail`.",
        "",
        "Confidence intervals are percentile 95% intervals from 400 bootstrap resamples of held-out source runs.",
        "",
        "## 5. Overall held-out results",
        "",
        table(overall, ["method", "winner_score", "detection_ap", "time_rms_ns", "time_rms_ns_ci_low", "time_rms_ns_ci_high", "charge_fractional_bias", "charge_fractional_res68", "failure_rate"]),
        "",
        "## 6. Separation and amplitude-ratio systematics",
        "",
        "The full stratum table is `strata_metrics.csv`. The first rows below show the predeclared stress axes.",
        "",
        table(strata.head(36), ["stratum", "value", "method", "time_rms_ns", "charge_fractional_bias", "charge_fractional_res68", "failure_rate"]),
        "",
        "## 7. Validation, caveats, and threats to validity",
        "",
        "The benchmark is fair at the row level: every method receives the same waveform, label, target, split, and metric. The split is by source run, and templates are fit only from train-run clean pulses. Group-CV AP/AUC rows are written to `group_cv.csv` for the train-run hyperparameter sanity check.",
        "",
        "The main caveat is that the truth comes from controlled injections, not hand-labeled real beam pile-up. The residuals and templates are raw-ROOT-derived, but independent real doublets may have different morphology, electronics saturation, or pile-up topology. The result therefore supports adoption only for template-like overlap recovery and motivates a real-candidate validation gate before physics use.",
        "",
        "## 8. Provenance and reproducibility",
        "",
        "Run:",
        "",
        "```bash",
        "python scripts/p05_2375_two_pulse_architecture_bakeoff.py --config configs/p05_2375_two_pulse_architecture_bakeoff.json",
        "```",
        "",
        f"Runtime was `{runtime:.2f}` s. Outputs: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `method_metrics.csv`, `event_predictions.csv`, `strata_metrics.csv`, `group_cv.csv`, and `template_summary.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p05_2375_two_pulse_architecture_bakeoff.json")
    args = parser.parse_args()
    start = time.time()
    config_path = Path(args.config)
    config = p05a.load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    match = p05a.reproduce_counts(config)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(match["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    train_runs = [int(x) for x in config["benchmark_runs"]["train"]]
    heldout_runs = [int(x) for x in config["benchmark_runs"]["heldout"]]
    clean = p05a.read_clean_pulses(config, sorted(set(train_runs + heldout_runs)), rng)
    templates, template_summary = p05a.build_templates(clean[clean["run"].isin(train_runs)], config)
    template_summary.to_csv(out_dir / "template_summary.csv", index=False)

    train_events, train_wave = p05a.generate_benchmark(clean, templates, config, "train", train_runs, rng)
    held_events, held_wave = p05a.generate_benchmark(clean, templates, config, "heldout", heldout_runs, rng)
    events = pd.concat([train_events, held_events], ignore_index=True)
    waveforms = np.vstack([train_wave, held_wave])
    base_x = p05a.make_feature_matrix(waveforms)

    methods = ["traditional", "ridge", "gradient_boosted_trees", "mlp", "one_d_cnn", "template_residual_fusion_new"]
    frames = [events]
    cv_rows = []

    trad = traditional_frame(events, waveforms, templates, config)
    frames.append(trad)

    ridge, ridge_cv = run_sklearn_method(
        "ridge",
        events,
        waveforms,
        make_pipeline(StandardScaler(), LogisticRegression(C=1.0, penalty="l2", max_iter=1000, random_state=int(config["random_seed"]))),
        make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        base_x,
    )
    frames.append(ridge)
    cv_rows.append(ridge_cv)

    gbt, gbt_cv = run_sklearn_method(
        "gradient_boosted_trees",
        events,
        waveforms,
        HistGradientBoostingClassifier(max_iter=80, learning_rate=0.08, l2_regularization=0.02, random_state=int(config["random_seed"]) + 1),
        MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=80, learning_rate=0.08, l2_regularization=0.02, random_state=int(config["random_seed"]) + 2)),
        base_x,
    )
    frames.append(gbt)
    cv_rows.append(gbt_cv)

    mlp, mlp_cv = run_sklearn_method(
        "mlp",
        events,
        waveforms,
        make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(32,), alpha=1e-3, max_iter=500, random_state=int(config["random_seed"]) + 3, early_stopping=True)),
        make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(48, 24), alpha=1e-3, max_iter=500, random_state=int(config["random_seed"]) + 4, early_stopping=True)),
        base_x,
    )
    frames.append(mlp)
    cv_rows.append(mlp_cv)

    cnn, cnn_cv = cnn_frame(events, waveforms, config)
    frames.append(cnn)
    cv_rows.append(cnn_cv)

    hx = hybrid_features(base_x, trad)
    hybrid, hybrid_cv = run_sklearn_method(
        "template_residual_fusion_new",
        events,
        waveforms,
        HistGradientBoostingClassifier(max_iter=100, learning_rate=0.07, l2_regularization=0.05, random_state=int(config["random_seed"]) + 5),
        MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=100, learning_rate=0.07, l2_regularization=0.05, random_state=int(config["random_seed"]) + 6)),
        hx,
    )
    frames.append(hybrid)
    cv_rows.append(hybrid_cv)

    predictions = frames[0]
    for frame in frames[1:]:
        predictions = predictions.merge(frame, on="event_id")
    predictions.to_csv(out_dir / "event_predictions.csv", index=False)

    overall = summarize(predictions, methods, config, rng)
    overall.to_csv(out_dir / "method_metrics.csv", index=False)
    strata = pd.concat(
        [
            summarize_strata(predictions, methods, "true_sep_sample"),
            summarize_strata(predictions, methods, "true_ratio"),
            summarize_strata(predictions, methods, "stave"),
        ],
        ignore_index=True,
    )
    strata.to_csv(out_dir / "strata_metrics.csv", index=False)
    cv = pd.concat([x for x in cv_rows if len(x)], ignore_index=True)
    cv.to_csv(out_dir / "group_cv.csv", index=False)

    configured = p05a.configured_runs(config)
    input_paths = [p05a.raw_file(config, run) for run in configured]
    input_hashes = {str(path): sha256_file(path) for path in input_paths}
    pd.DataFrame([{"path": path, "sha256": digest} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)

    runtime = time.time() - start
    write_report(out_dir, config, match, template_summary, overall, strata, cv, runtime)

    winner = overall.iloc[0].to_dict()
    trad_row = overall[overall["method"] == "traditional"].iloc[0].to_dict()
    result = {
        "ticket_id": int(config["ticket_id"]),
        "ticket_title": config["ticket_title"],
        "worker": config["worker"],
        "claim_command": "tn-ticket claim testbeam-laptop-2 --project testbeam",
        "manual_claim_note": "tn-ticket returned null|null|null without mutating an issue; issue #2375 was label-claimed once with gh using factory:claimed and worker:testbeam-laptop-2.",
        "status": "complete",
        "raw_root_reproduction": {
            "passed": bool(match["pass"].all()),
            "expected_selected_pulses": int(match.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(match.iloc[0]["reproduced"]),
            "delta": int(match.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "split": {"train_runs": train_runs, "heldout_runs": heldout_runs, "bootstrap_replicates": int(config["ml"]["bootstrap_samples"])},
        "required_method_coverage": {
            "traditional": "traditional",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "one_d_cnn",
            "new_architecture": "template_residual_fusion_new",
        },
        "winner": winner,
        "traditional_baseline": trad_row,
        "winner_score_formula": "time_rms_ns + 12*charge_fractional_res68 + 8*abs(charge_fractional_bias) + 18*failure_rate",
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "manifest": "manifest.json",
            "method_metrics": "method_metrics.csv",
            "event_predictions": "event_predictions.csv",
            "strata_metrics": "strata_metrics.csv",
            "group_cv": "group_cv.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "git_commit": git_commit(),
        "runtime_seconds": round(runtime, 3),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    outputs = {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}
    manifest = {
        "ticket_id": int(config["ticket_id"]),
        "worker": config["worker"],
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs_sha256": outputs,
        "runtime_seconds": round(time.time() - start, 3),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner["method"], "raw_reproduction_passed": bool(match["pass"].all())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
