#!/usr/bin/env python3
"""S07 ML-rigour scoreboard from raw B-stack waveforms.

The study has two pieces:
1. reproduce the S00 selected-pulse count from raw HRDv waveforms;
2. build a run-split, calibrated ML-vs-traditional scoreboard for the App.H-like
   current/topology proxy using waveform-shape features only.

Data is read-only at ./data. Outputs are written only to the configured report directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "reports/1780997954.15217.702122ea__s07_ml_rigour_scoreboard/.matplotlib-cache")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def raw_file(raw_root_dir: Path, run: int) -> Path:
    return raw_root_dir / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, step_size: int = 20000) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(["EVENTNO", "HRDv"], step_size=step_size, library="np")


def pulse_arrays(batch: dict, channels: np.ndarray, baseline_idx: List[int], nsamp: int) -> Tuple[np.ndarray, np.ndarray]:
    events = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, nsamp)
    wave = events[:, channels, :]
    baseline = np.median(wave[..., baseline_idx], axis=-1)
    corrected = wave - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    return corrected, amplitude


def all_s00_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for group_runs in config["s00_run_groups"].values():
        runs.extend(int(run) for run in group_runs)
    return sorted(set(runs))


def group_for_run(config: dict) -> Dict[int, str]:
    lookup = {}
    for group, runs in config["s00_run_groups"].items():
        for run in runs:
            lookup[int(run)] = group
    return lookup


def reproduce_s00_counts(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    raw_root_dir = Path(config["raw_root_dir"])
    staves = list(config["staves"])
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    cut = float(config["amplitude_cut_adc"])
    nsamp = int(config["samples_per_channel"])
    lookup = group_for_run(config)

    run_rows = []
    group_counts = {name: 0 for name in config["s00_run_groups"]}
    for run in all_s00_runs(config):
        selected_pulses = 0
        path = raw_file(raw_root_dir, run)
        for batch in iter_raw(path):
            _, amplitude = pulse_arrays(batch, channels, baseline_idx, nsamp)
            selected_pulses += int((amplitude > cut).sum())
        run_rows.append({"run": run, "group": lookup[run], "selected_pulses": selected_pulses})
        group_counts[lookup[run]] += selected_pulses

    expected = config["expected_counts"]
    rows = [
        {
            "quantity": "total selected B-stave pulses",
            "report_value": int(expected["total_selected_pulses"]),
            "reproduced": int(sum(group_counts.values())),
            "tolerance": 0,
        }
    ]
    for group in config["s00_run_groups"]:
        key = f"{group}_pulses"
        rows.append(
            {
                "quantity": f"{group} selected pulses",
                "report_value": int(expected[key]),
                "reproduced": int(group_counts[group]),
                "tolerance": 0,
            }
        )
    match = pd.DataFrame(rows)
    match["delta"] = match["reproduced"] - match["report_value"]
    match["pass"] = match["delta"].abs() <= match["tolerance"]
    return pd.DataFrame(run_rows), pd.DataFrame([{"group": k, "selected_pulses": v} for k, v in group_counts.items()]), match


def shape_feature_frame(
    run: int,
    stave_names: List[str],
    corrected: np.ndarray,
    amplitude: np.ndarray,
    cut: float,
    label: int,
    rng: np.random.Generator,
    max_per_stave: int,
) -> pd.DataFrame:
    rows = []
    for stave_idx, stave in enumerate(stave_names):
        selected = np.flatnonzero(amplitude[:, stave_idx] > cut)
        if len(selected) > max_per_stave:
            selected = rng.choice(selected, size=max_per_stave, replace=False)
        if not len(selected):
            continue
        w = corrected[selected, stave_idx, :]
        amp = amplitude[selected, stave_idx]
        norm = w / np.maximum(amp[:, None], 1e-9)
        area = norm.sum(axis=1)
        tail = norm[:, 12:].sum(axis=1) / np.maximum(area, 1e-6)
        late = norm[:, 9:].sum(axis=1) / np.maximum(area, 1e-6)
        peak = norm.argmax(axis=1)
        down_steps = np.diff(norm, axis=1)
        frame = pd.DataFrame(
            {
                "run": run,
                "stave": stave,
                "low_current": int(label),
                "tail_fraction": tail,
                "late_fraction": late,
                "area_over_peak": area,
                "peak_sample": peak.astype(float),
                "max_down_step": down_steps.min(axis=1),
                "final_fraction": norm[:, -1],
            }
        )
        for sample in range(norm.shape[1]):
            frame[f"norm_s{sample:02d}"] = norm[:, sample]
        rows.append(frame)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def load_current_proxy(config: dict) -> pd.DataFrame:
    settings = config["current_proxy"]
    raw_root_dir = Path(config["raw_root_dir"])
    staves = list(config["staves"])
    channels = np.asarray([int(config["staves"][name]) for name in staves], dtype=int)
    baseline_idx = [int(i) for i in config["baseline_samples"]]
    nsamp = int(config["samples_per_channel"])
    cut = float(config["amplitude_cut_adc"])
    rng = np.random.default_rng(int(settings["random_seed"]))
    low_runs = set(int(run) for run in settings["low_current_runs"])
    high_runs = set(int(run) for run in settings["high_current_runs"])
    rows = []

    for run in sorted(low_runs | high_runs):
        run_frames = []
        for batch in iter_raw(raw_file(raw_root_dir, run)):
            corrected, amplitude = pulse_arrays(batch, channels, baseline_idx, nsamp)
            run_frames.append(
                shape_feature_frame(
                    run,
                    staves,
                    corrected,
                    amplitude,
                    cut,
                    int(run in low_runs),
                    rng,
                    int(settings["max_pulses_per_run_stave"]),
                )
            )
        rows.append(pd.concat(run_frames, ignore_index=True))
    data = pd.concat(rows, ignore_index=True)

    # Balance per stave and current class so the classifier cannot win by class/stave priors.
    balanced = []
    for (_, _), subset in data.groupby(["stave", "low_current"]):
        balanced.append(subset.sample(n=min(len(subset), int(settings["max_pulses_per_run_stave"]) * 2), random_state=int(settings["random_seed"])))
    return pd.concat(balanced, ignore_index=True).sample(frac=1.0, random_state=int(settings["random_seed"])).reset_index(drop=True)


def fold_masks(data: pd.DataFrame, settings: dict) -> List[Tuple[np.ndarray, np.ndarray, str]]:
    folds = []
    runs = data["run"].to_numpy()
    for idx, fold in enumerate(settings["fold_pairs"], start=1):
        test_runs = {int(fold["test_low_run"]), *[int(run) for run in fold["test_high_runs"]]}
        test = np.asarray([run in test_runs for run in runs], dtype=bool)
        train = ~test
        folds.append((train, test, f"fold{idx}"))
    return folds


def best_traditional_score(train_df: pd.DataFrame, test_df: pd.DataFrame, features: List[str]) -> Tuple[np.ndarray, dict]:
    y = train_df["low_current"].to_numpy()
    best = None
    for feature in features:
        values = train_df[feature].to_numpy(dtype=float)
        for sign in [1.0, -1.0]:
            score = sign * values
            auc = roc_auc_score(y, score)
            candidate = {"feature": feature, "sign": sign, "train_auc": float(auc)}
            if best is None or auc > best["train_auc"]:
                best = candidate
    assert best is not None
    return best["sign"] * test_df[best["feature"]].to_numpy(dtype=float), best


def rf_oof_score(train_df: pd.DataFrame, test_df: pd.DataFrame, feature_cols: List[str], params: dict, seed: int) -> np.ndarray:
    clf = RandomForestClassifier(
        n_estimators=int(params["n_estimators"]),
        max_depth=int(params["max_depth"]),
        min_samples_leaf=int(params["min_samples_leaf"]),
        class_weight="balanced",
        random_state=seed,
        n_jobs=1,
    )
    clf.fit(train_df[feature_cols], train_df["low_current"])
    return clf.predict_proba(test_df[feature_cols])[:, 1]


def crossfold_isotonic_probability(y: np.ndarray, score: np.ndarray, fold_id: np.ndarray) -> np.ndarray:
    prob = np.full(len(y), np.nan)
    for fold in np.unique(fold_id):
        test = fold_id == fold
        cal = ~test
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(score[cal], y[cal])
        prob[test] = iso.predict(score[test])
    return prob


def evaluate_score(y: np.ndarray, score: np.ndarray, fold_id: np.ndarray, seed: int, n_boot: int) -> dict:
    prob = crossfold_isotonic_probability(y, score, fold_id)
    auc = roc_auc_score(y, score)
    ap = average_precision_score(y, score)
    brier = brier_score_loss(y, prob)
    rng = np.random.default_rng(seed)
    boot_auc, boot_ap, boot_brier = [], [], []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        boot_auc.append(roc_auc_score(y[idx], score[idx]))
        boot_ap.append(average_precision_score(y[idx], score[idx]))
        boot_brier.append(brier_score_loss(y[idx], prob[idx]))
    return {
        "roc_auc": float(auc),
        "roc_auc_ci": [float(x) for x in np.quantile(boot_auc, [0.025, 0.975])],
        "average_precision": float(ap),
        "average_precision_ci": [float(x) for x in np.quantile(boot_ap, [0.025, 0.975])],
        "brier_isotonic": float(brier),
        "brier_ci": [float(x) for x in np.quantile(boot_brier, [0.025, 0.975])],
        "probability": prob,
    }


def paired_auc_diff_test(y: np.ndarray, baseline_score: np.ndarray, ml_score: np.ndarray, seed: int, n_boot: int, n_tries: int) -> dict:
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        diffs.append(roc_auc_score(y[idx], ml_score[idx]) - roc_auc_score(y[idx], baseline_score[idx]))
    diffs = np.asarray(diffs)
    p_uncorrected = float((1 + np.sum(diffs <= 0.0)) / (len(diffs) + 1))
    return {
        "ml_minus_traditional_auc": float(roc_auc_score(y, ml_score) - roc_auc_score(y, baseline_score)),
        "bootstrap_ci": [float(x) for x in np.quantile(diffs, [0.025, 0.975])],
        "p_value_one_sided": p_uncorrected,
        "p_value_bonferroni": min(1.0, p_uncorrected * int(n_tries)),
    }


def current_proxy_scoreboard(config: dict, out_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, dict]:
    settings = config["current_proxy"]
    data = load_current_proxy(config)
    feature_cols = [col for col in data.columns if col.startswith("norm_s")] + list(settings["baseline_features"])
    baseline_features = list(settings["baseline_features"])
    folds = fold_masks(data, settings)
    seed = int(settings["random_seed"])

    y = data["low_current"].to_numpy()
    baseline_score = np.full(len(data), np.nan)
    fold_id = np.full(len(data), "", dtype=object)
    rf_scores = {json.dumps(params, sort_keys=True): np.full(len(data), np.nan) for params in settings["rf_grid"]}
    baseline_choices = []

    for train_mask, test_mask, fold_name in folds:
        train_df = data.loc[train_mask].copy()
        test_df = data.loc[test_mask].copy()
        score, choice = best_traditional_score(train_df, test_df, baseline_features)
        baseline_score[test_mask] = score
        fold_id[test_mask] = fold_name
        choice["fold"] = fold_name
        choice["test_runs"] = ",".join(str(run) for run in sorted(test_df["run"].unique()))
        baseline_choices.append(choice)
        for params in settings["rf_grid"]:
            key = json.dumps(params, sort_keys=True)
            rf_scores[key][test_mask] = rf_oof_score(train_df, test_df, feature_cols, params, seed)

    valid = ~np.isnan(baseline_score)
    y_eval = y[valid]
    fold_eval = fold_id[valid]
    baseline_eval = baseline_score[valid]
    baseline_metrics = evaluate_score(y_eval, baseline_eval, fold_eval, seed, int(settings["bootstrap_replicates"]))

    cv_rows = []
    for key, score in rf_scores.items():
        params = json.loads(key)
        score_eval = score[valid]
        metrics = evaluate_score(y_eval, score_eval, fold_eval, seed + len(cv_rows) + 1, int(settings["bootstrap_replicates"]))
        row = dict(params)
        row.update({k: v for k, v in metrics.items() if k != "probability"})
        cv_rows.append(row)
    cv = pd.DataFrame(cv_rows).sort_values(["roc_auc", "average_precision"], ascending=False)
    best_params = cv.iloc[0][["n_estimators", "max_depth", "min_samples_leaf"]].astype(int).to_dict()
    best_key = json.dumps(best_params, sort_keys=True)
    rf_eval = rf_scores[best_key][valid]
    rf_metrics = evaluate_score(y_eval, rf_eval, fold_eval, seed + 100, int(settings["bootstrap_replicates"]))
    n_tries = len(config["current_proxy"]["baseline_features"]) * 2 + len(config["current_proxy"]["rf_grid"])
    diff_test = paired_auc_diff_test(y_eval, baseline_eval, rf_eval, seed + 200, int(settings["bootstrap_replicates"]), n_tries)

    scoreboard = pd.DataFrame(
        [
            {
                "method": "traditional single-shape-variable score",
                "metric": "low-current ROC AUC",
                "value": baseline_metrics["roc_auc"],
                "ci_low": baseline_metrics["roc_auc_ci"][0],
                "ci_high": baseline_metrics["roc_auc_ci"][1],
                "average_precision": baseline_metrics["average_precision"],
                "average_precision_ci_low": baseline_metrics["average_precision_ci"][0],
                "average_precision_ci_high": baseline_metrics["average_precision_ci"][1],
                "brier_isotonic": baseline_metrics["brier_isotonic"],
                "notes": "Best one-dimensional waveform-shape score selected inside each training fold.",
            },
            {
                "method": "calibrated random forest waveform-shape model",
                "metric": "low-current ROC AUC",
                "value": rf_metrics["roc_auc"],
                "ci_low": rf_metrics["roc_auc_ci"][0],
                "ci_high": rf_metrics["roc_auc_ci"][1],
                "average_precision": rf_metrics["average_precision"],
                "average_precision_ci_low": rf_metrics["average_precision_ci"][0],
                "average_precision_ci_high": rf_metrics["average_precision_ci"][1],
                "brier_isotonic": rf_metrics["brier_isotonic"],
                "notes": f"Run-held-out OOF; best RF params={best_params}.",
            },
        ]
    )

    pd.DataFrame(baseline_choices).to_csv(out_dir / "traditional_baseline_choices.csv", index=False)
    cv.to_csv(out_dir / "rf_cv_scan.csv", index=False)
    scoreboard.to_csv(out_dir / "scoreboard.csv", index=False)
    data.groupby(["run", "stave", "low_current"]).size().reset_index(name="n").to_csv(out_dir / "dataset_counts.csv", index=False)

    make_score_figures(out_dir, y_eval, baseline_eval, baseline_metrics["probability"], rf_eval, rf_metrics["probability"])
    details = {
        "n_rows": int(len(data)),
        "n_evaluated": int(valid.sum()),
        "positive_low_current_fraction": float(y_eval.mean()),
        "feature_columns": feature_cols,
        "best_rf_params": best_params,
        "ml_vs_traditional": diff_test,
        "folds": [
            {"name": name, "train_n": int(train.sum()), "test_n": int(test.sum())}
            for train, test, name in folds
        ],
    }
    return scoreboard, cv, details


def make_score_figures(out_dir: Path, y: np.ndarray, baseline_score: np.ndarray, baseline_prob: np.ndarray, rf_score: np.ndarray, rf_prob: np.ndarray) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for score, label in [(baseline_score, "traditional"), (rf_score, "RF")]:
        fpr, tpr, _ = roc_curve(y, score)
        axes[0].plot(fpr, tpr, label=label)
        precision, recall, _ = precision_recall_curve(y, score)
        axes[1].plot(recall, precision, label=label)
    axes[0].plot([0, 1], [0, 1], "k--", lw=1)
    axes[0].set_xlabel("False positive rate")
    axes[0].set_ylabel("True positive rate")
    axes[0].set_title("Run-held-out ROC")
    axes[1].set_xlabel("Recall")
    axes[1].set_ylabel("Precision")
    axes[1].set_title("Run-held-out PR")
    for ax in axes:
        ax.legend()
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_roc_pr.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 4))
    bins = np.linspace(0, 1, 11)
    for prob, label in [(baseline_prob, "traditional"), (rf_prob, "RF")]:
        centers, observed = [], []
        for lo, hi in zip(bins[:-1], bins[1:]):
            mask = (prob >= lo) & (prob <= hi if hi == 1 else prob < hi)
            if mask.sum() >= 20:
                centers.append(float(prob[mask].mean()))
                observed.append(float(y[mask].mean()))
        ax.plot(centers, observed, marker="o", label=label)
    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("Mean calibrated probability")
    ax.set_ylabel("Observed low-current fraction")
    ax.set_title("Reliability, isotonic OOF calibration")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_dir / "fig_reliability.png", dpi=160)
    plt.close(fig)


def output_hashes(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/s07_ml_rigour_scoreboard.yaml"))
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(args.config)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    counts_by_run, counts_by_group, match = reproduce_s00_counts(config)
    counts_by_run.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    counts_by_group.to_csv(out_dir / "reproduction_counts_by_group.csv", index=False)
    match.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    scoreboard, cv, details = current_proxy_scoreboard(config, out_dir)

    input_files = [raw_file(Path(config["raw_root_dir"]), run) for run in all_s00_runs(config)]
    input_sha = pd.DataFrame(
        [{"file": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size} for path in input_files]
    )
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    result = {
        "study": config["study_id"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(match["pass"].all()),
        "repro_tolerance": "exact selected-pulse count match",
        "traditional": {
            "metric": "low-current ROC AUC",
            "value": float(scoreboard.iloc[0]["value"]),
            "ci": [float(scoreboard.iloc[0]["ci_low"]), float(scoreboard.iloc[0]["ci_high"])],
        },
        "ml": {
            "metric": "low-current ROC AUC",
            "value": float(scoreboard.iloc[1]["value"]),
            "ci": [float(scoreboard.iloc[1]["ci_low"]), float(scoreboard.iloc[1]["ci_high"])],
        },
        "ml_beats_baseline": bool(scoreboard.iloc[1]["value"] > scoreboard.iloc[0]["value"]),
        "falsification": {
            "preregistered_metric": "run-held-out low-current ROC AUC",
            "traditional_baseline_tries": len(config["current_proxy"]["baseline_features"]) * 2,
            "ml_hyperparameter_tries": len(config["current_proxy"]["rf_grid"]),
            "n_tries": len(config["current_proxy"]["baseline_features"]) * 2 + len(config["current_proxy"]["rf_grid"]),
            "ml_minus_traditional_auc": details["ml_vs_traditional"]["ml_minus_traditional_auc"],
            "bootstrap_ci": details["ml_vs_traditional"]["bootstrap_ci"],
            "p_value_one_sided": details["ml_vs_traditional"]["p_value_one_sided"],
            "p_value_bonferroni": details["ml_vs_traditional"]["p_value_bonferroni"],
        },
        "input_sha256": input_sha.iloc[0]["sha256"],
        "git_commit": commit,
        "critic": "pending",
        "next_tickets": [
            "S07b: timing-control classifier calibration with D_t labels and bootstrap CIs",
            "S07c: event-level clean-timing RF vs q_template/downstream-span baseline",
        ],
        "details": details,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "config": str(args.config),
        "git_commit": commit,
        "commands": [f"python scripts/s07_ml_rigour_scoreboard.py --config {args.config}"],
        "random_seed": int(config["current_proxy"]["random_seed"]),
        "input_files": input_sha.to_dict(orient="records"),
        "output_files": output_hashes(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(match.to_string(index=False))
    print()
    print(scoreboard.to_string(index=False))
    print(f"\nWrote {out_dir}")
    return 0 if bool(match["pass"].all()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
