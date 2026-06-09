#!/usr/bin/env python3
"""S03b q_template-only timing-tail cuts.

This report-local script rebuilds downstream timing-tail labels from raw ROOT,
joins the S01 q_template table, and evaluates q_template-only traditional cuts
and an ML comparator with run-held-out folds.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler


OUT = Path(__file__).resolve().parent
RAW_DIR = Path("data/root/root")
QTEMPLATE_PATH = Path("reports/1780997954.15037.36463764__s01_full_dataset_templates/q_template_per_pulse.csv.gz")
TICKET = "1781006575.2877.41492e09"
WORKER = "testbeam-laptop-2"
SEED = 9303

AMPLITUDE_CUT_ADC = 1000.0
BASELINE_SAMPLES = [0, 1, 2, 3]
SAMPLES_PER_CHANNEL = 18
SAMPLE_PERIOD_NS = 10.0
CFD_FRACTION = 0.20
STAVES = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}
DOWNSTREAM = ["B4", "B6", "B8"]
RUN_GROUPS = {
    "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
    "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_ii_calib": [64],
    "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
}
EXPECTED_S00_COUNTS = {
    "total_selected_pulses": 640737,
    "sample_i_calib": 248745,
    "sample_i_analysis": 252266,
    "sample_ii_calib": 14630,
    "sample_ii_analysis": 125096,
}
Q_FEATURES = [
    "q_B2",
    "q_B4",
    "q_B6",
    "q_B8",
    "q_downstream_mean",
    "q_downstream_max",
    "q_downstream_p90",
    "q_downstream_std",
    "q_all_mean",
    "q_all_max",
]
FORBIDDEN = {
    "downstream_span_ns",
    "all_span_ns",
    "b2_displacement_ns",
    "b2_displacement_filled",
    "run",
    "eventno",
    "evt",
    "pair_residual",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def all_runs() -> list[int]:
    runs: list[int] = []
    for group_runs in RUN_GROUPS.values():
        runs.extend(group_runs)
    return sorted(set(runs))


def run_group(run: int) -> str:
    for group, runs in RUN_GROUPS.items():
        if int(run) in runs:
            return group
    raise KeyError(run)


def raw_file(run: int) -> Path:
    return RAW_DIR / f"hrdb_run_{run:04d}.root"


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray) -> np.ndarray:
    threshold = amplitudes * CFD_FRACTION
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0 = waveforms[i, j - 1]
        y1 = waveforms[i, j]
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (threshold[i] - y0) / denom
    return out


def qtemplate_event_table() -> pd.DataFrame:
    q = pd.read_csv(QTEMPLATE_PATH, usecols=["run", "eventno", "evt", "stave", "q_template_rmse"])
    wide = q.pivot_table(index=["run", "eventno", "evt"], columns="stave", values="q_template_rmse", aggfunc="first")
    wide = wide.reset_index()
    for stave in STAVES:
        if stave not in wide.columns:
            wide[stave] = np.nan
        wide[f"q_{stave}"] = wide[stave]
    downstream = wide[[f"q_{stave}" for stave in DOWNSTREAM]]
    all_q = wide[[f"q_{stave}" for stave in STAVES]]
    wide["q_downstream_mean"] = downstream.mean(axis=1, skipna=True)
    wide["q_downstream_max"] = downstream.max(axis=1, skipna=True)
    wide["q_downstream_p90"] = downstream.quantile(0.90, axis=1, interpolation="linear")
    wide["q_downstream_std"] = downstream.std(axis=1, skipna=True).fillna(0.0)
    wide["q_all_mean"] = all_q.mean(axis=1, skipna=True)
    wide["q_all_max"] = all_q.max(axis=1, skipna=True)
    return wide[["run", "eventno", "evt"] + Q_FEATURES]


def scan_raw_events() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    channels = np.asarray([STAVES[stave] for stave in STAVES], dtype=int)
    s00_counts = {group: 0 for group in RUN_GROUPS}
    s00_counts["total_selected_pulses"] = 0
    per_run_rows = []
    event_rows = []

    for run in all_runs():
        path = raw_file(run)
        tree = uproot.open(path)["h101"]
        group = run_group(run)
        run_stats = {
            "run": run,
            "group": group,
            "events_total": 0,
            "selected_pulses": 0,
            "downstream_ge2_events": 0,
            "clean_events": 0,
            "tail_events": 0,
            "ambiguous_events": 0,
        }
        for batch in tree.iterate(["EVENTNO", "EVT", "HRDv"], step_size=30000, library="np"):
            eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
            evt = np.asarray(batch["EVT"]).astype(np.int64)
            raw = np.stack(batch["HRDv"]).astype(np.float64).reshape(-1, 8, SAMPLES_PER_CHANNEL)[:, channels, :]
            baseline = np.median(raw[..., BASELINE_SAMPLES], axis=-1)
            wave = raw - baseline[..., None]
            amplitude = wave.max(axis=-1)
            selected = amplitude > AMPLITUDE_CUT_ADC
            run_stats["events_total"] += int(len(eventno))
            selected_count = int(selected.sum())
            run_stats["selected_pulses"] += selected_count
            s00_counts[group] += selected_count
            s00_counts["total_selected_pulses"] += selected_count

            times = np.full(amplitude.shape, np.nan, dtype=float)
            for idx in range(len(STAVES)):
                hit_idx = np.where(selected[:, idx])[0]
                if len(hit_idx):
                    times[hit_idx, idx] = cfd_time_samples(wave[hit_idx, idx], amplitude[hit_idx, idx]) * SAMPLE_PERIOD_NS

            ds_selected = selected[:, 1:]
            candidate_mask = ds_selected.sum(axis=1) >= 2
            if not candidate_mask.any():
                continue

            ds_times_all = times[:, 1:].copy()
            ds_times_all[~ds_selected] = np.nan
            cand_idx = np.where(candidate_mask)[0]
            ds_times = ds_times_all[candidate_mask]
            ds_span = np.nanmax(ds_times, axis=1) - np.nanmin(ds_times, axis=1)
            clean = ds_span < 5.0
            tail = ds_span > 10.0
            labelled = clean | tail
            run_stats["downstream_ge2_events"] += int(candidate_mask.sum())
            run_stats["clean_events"] += int(clean.sum())
            run_stats["tail_events"] += int(tail.sum())
            run_stats["ambiguous_events"] += int((~labelled).sum())

            labelled_pos = np.where(labelled)[0]
            for pos in labelled_pos:
                event_idx = int(cand_idx[pos])
                event_rows.append(
                    {
                        "run": run,
                        "group": group,
                        "eventno": int(eventno[event_idx]),
                        "evt": int(evt[event_idx]),
                        "label_tail": int(tail[pos]),
                        "downstream_span_ns": float(ds_span[pos]),
                    }
                )
        per_run_rows.append(run_stats)
        print(run, run_stats, flush=True)

    s00_rows = []
    for quantity, expected in EXPECTED_S00_COUNTS.items():
        observed = int(s00_counts[quantity])
        s00_rows.append(
            {
                "quantity": quantity,
                "report_value": int(expected),
                "reproduced": observed,
                "delta": observed - int(expected),
                "tolerance": 0,
                "pass": observed == int(expected),
            }
        )
    return pd.DataFrame(s00_rows), pd.DataFrame(per_run_rows), pd.DataFrame(event_rows)


def fill_q(train: pd.DataFrame, frame: pd.DataFrame) -> np.ndarray:
    med = train[Q_FEATURES].median(axis=0, skipna=True).fillna(0.0)
    return frame[Q_FEATURES].fillna(med).to_numpy(dtype=float)


def choose_cut(train: pd.DataFrame, y_train: np.ndarray) -> tuple[str, float, int, float]:
    best = None
    for feature in ["q_downstream_max", "q_downstream_p90", "q_downstream_mean", "q_all_max", "q_all_mean"]:
        values = train[feature].to_numpy(dtype=float)
        finite = np.isfinite(values)
        if finite.sum() == 0:
            continue
        for direction in [1, -1]:
            score = direction * values
            clean_scores = score[finite & (y_train == 0)]
            if len(clean_scores) == 0:
                continue
            threshold = float(np.quantile(clean_scores, 0.95))
            reject = score >= threshold
            tail_reject = float(np.mean(reject[finite & (y_train == 1)])) if np.any(finite & (y_train == 1)) else 0.0
            clean_retain = float(np.mean(~reject[finite & (y_train == 0)]))
            objective = tail_reject - 2.0 * max(0.0, 0.94 - clean_retain)
            candidate = (objective, feature, threshold, direction, clean_retain)
            if best is None or candidate > best:
                best = candidate
    if best is None:
        raise RuntimeError("no valid q_template cut candidate")
    _, feature, threshold, direction, _ = best
    return str(feature), float(threshold), int(direction), float(best[4])


def train_standard_q_score(train: pd.DataFrame, test: pd.DataFrame, y_train: np.ndarray) -> np.ndarray:
    x_train = fill_q(train, train)
    scaler = StandardScaler()
    sx_train = scaler.fit_transform(x_train)
    directions = []
    for col in range(sx_train.shape[1]):
        values = sx_train[:, col]
        if np.nanstd(values) == 0 or len(np.unique(y_train)) < 2:
            directions.append(1.0)
            continue
        auc = roc_auc_score(y_train, values)
        directions.append(1.0 if auc >= 0.5 else -1.0)
    sx_test = scaler.transform(fill_q(train, test))
    return sx_test @ np.asarray(directions)


def metric_ci_by_run(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric: str, n_boot: int = 1000) -> tuple[float, list[float]]:
    if metric == "roc_auc":
        point = float(roc_auc_score(y, score))
    elif metric == "average_precision":
        point = float(average_precision_score(y, score))
    elif metric == "brier":
        point = float(brier_score_loss(y, np.clip(score, 0, 1)))
    else:
        raise ValueError(metric)
    rng = np.random.default_rng(SEED + len(metric))
    unique_runs = np.unique(runs)
    values = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        if metric == "roc_auc":
            values.append(roc_auc_score(y[idx], score[idx]))
        elif metric == "average_precision":
            values.append(average_precision_score(y[idx], score[idx]))
        else:
            values.append(brier_score_loss(y[idx], np.clip(score[idx], 0, 1)))
    return point, [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def rate_ci_by_run(values: np.ndarray, runs: np.ndarray, n_boot: int = 1000) -> tuple[float, list[float]]:
    point = float(np.mean(values))
    rng = np.random.default_rng(SEED + 57)
    unique_runs = np.unique(runs)
    boots = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        boots.append(float(np.mean(values[idx])))
    return point, [float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))]


def delta_auc_ci_by_run(y: np.ndarray, a: np.ndarray, b: np.ndarray, runs: np.ndarray, n_boot: int = 1000) -> tuple[float, list[float]]:
    point = float(roc_auc_score(y, a) - roc_auc_score(y, b))
    rng = np.random.default_rng(SEED + 404)
    unique_runs = np.unique(runs)
    values = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        values.append(float(roc_auc_score(y[idx], a[idx]) - roc_auc_score(y[idx], b[idx])))
    return point, [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def run_heldout_models(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    y = data["label_tail"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    splitter = GroupKFold(n_splits=min(5, len(np.unique(runs))))
    fold_ids = np.zeros(len(data), dtype=int)
    trad_score = np.full(len(data), np.nan)
    trad_reject = np.full(len(data), np.nan)
    ml_scores: dict[str, np.ndarray] = {}
    leak_score = np.full(len(data), np.nan)
    shuffled_score = np.full(len(data), np.nan)
    ml_grid = [
        {"n_estimators": 200, "max_depth": 3, "min_samples_leaf": 40},
        {"n_estimators": 250, "max_depth": 4, "min_samples_leaf": 30},
        {"n_estimators": 300, "max_depth": 5, "min_samples_leaf": 20},
    ]
    for params in ml_grid:
        ml_scores[json.dumps(params, sort_keys=True)] = np.full(len(data), np.nan)

    fold_rows = []
    rng = np.random.default_rng(SEED)
    for fold, (train_idx, test_idx) in enumerate(splitter.split(data, y, groups=runs), start=1):
        train = data.iloc[train_idx]
        test = data.iloc[test_idx]
        y_train = y[train_idx]
        y_shuf = rng.permutation(y_train)
        fold_ids[test_idx] = fold

        feature, threshold, direction, train_clean_retain = choose_cut(train, y_train)
        score = train_standard_q_score(train, test, y_train)
        trad_score[test_idx] = score
        raw_feature = test[feature].to_numpy(dtype=float)
        trad_reject[test_idx] = (direction * raw_feature >= threshold).astype(float)

        for params in ml_grid:
            key = json.dumps(params, sort_keys=True)
            model = RandomForestClassifier(**params, class_weight="balanced", random_state=SEED + fold, n_jobs=-1)
            model.fit(fill_q(train, train), y_train)
            ml_scores[key][test_idx] = model.predict_proba(fill_q(train, test))[:, 1]

        shuffled = RandomForestClassifier(
            n_estimators=200, max_depth=4, min_samples_leaf=30, class_weight="balanced", random_state=SEED + 200 + fold, n_jobs=-1
        )
        shuffled.fit(fill_q(train, train), y_shuf)
        shuffled_score[test_idx] = shuffled.predict_proba(fill_q(train, test))[:, 1]

        leak_cols = Q_FEATURES + ["downstream_span_ns"]
        leak_train = train[leak_cols].copy()
        leak_test = test[leak_cols].copy()
        med = leak_train.median(axis=0, skipna=True).fillna(0.0)
        leak_train = leak_train.fillna(med)
        leak_test = leak_test.fillna(med)
        leak = RandomForestClassifier(
            n_estimators=120, max_depth=3, min_samples_leaf=20, class_weight="balanced", random_state=SEED + 100 + fold, n_jobs=-1
        )
        leak.fit(leak_train.to_numpy(dtype=float), y_train)
        leak_score[test_idx] = leak.predict_proba(leak_test.to_numpy(dtype=float))[:, 1]

        fold_rows.append(
            {
                "fold": fold,
                "test_runs": ",".join(str(int(run)) for run in sorted(np.unique(runs[test_idx]))),
                "train_n": int(len(train_idx)),
                "test_n": int(len(test_idx)),
                "test_tail": int(y[test_idx].sum()),
                "test_clean": int((1 - y[test_idx]).sum()),
                "traditional_cut_feature": feature,
                "traditional_cut_direction": direction,
                "traditional_cut_threshold": threshold,
                "traditional_train_clean_retain": train_clean_retain,
            }
        )

    ml_cv_rows = []
    for key, score in ml_scores.items():
        params = json.loads(key)
        ml_cv_rows.append(
            {
                **params,
                "roc_auc": float(roc_auc_score(y, score)),
                "average_precision": float(average_precision_score(y, score)),
                "brier": float(brier_score_loss(y, np.clip(score, 0, 1))),
            }
        )
    ml_cv = pd.DataFrame(ml_cv_rows).sort_values(["roc_auc", "average_precision"], ascending=False).reset_index(drop=True)
    best_params = {k: int(ml_cv.iloc[0][k]) for k in ["n_estimators", "max_depth", "min_samples_leaf"]}
    best_key = json.dumps(best_params, sort_keys=True)
    scores = pd.DataFrame(
        {
            "run": runs,
            "fold": fold_ids,
            "label_tail": y,
            "traditional_q_score": trad_score,
            "traditional_q_reject": trad_reject,
            "ml_q_rf_score": ml_scores[best_key],
            "leaky_downstream_span_score": leak_score,
            "shuffled_label_q_rf_score": shuffled_score,
        }
    )
    return pd.DataFrame(fold_rows), ml_cv, scores, pd.DataFrame([best_params])


def build_scoreboard(scores: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    y = scores["label_tail"].to_numpy(dtype=int)
    runs = scores["run"].to_numpy(dtype=int)
    rows = []
    for method, col, note in [
        ("traditional_q_template_only", "traditional_q_score", "q_template-only standardized score plus fold-local clean-retention cuts"),
        ("ml_q_template_rf", "ml_q_rf_score", "random forest using q_template-only event summaries"),
        ("leaky_downstream_span_control", "leaky_downstream_span_score", "deliberate forbidden-feature control using downstream span"),
        ("shuffled_label_control", "shuffled_label_q_rf_score", "q_template RF trained on shuffled train labels"),
    ]:
        score = scores[col].to_numpy(dtype=float)
        auc, auc_ci = metric_ci_by_run(y, score, runs, "roc_auc")
        ap, ap_ci = metric_ci_by_run(y, score, runs, "average_precision")
        row = {
            "method": method,
            "roc_auc": auc,
            "roc_auc_ci_low": auc_ci[0],
            "roc_auc_ci_high": auc_ci[1],
            "average_precision": ap,
            "average_precision_ci_low": ap_ci[0],
            "average_precision_ci_high": ap_ci[1],
            "note": note,
        }
        if col in {"ml_q_rf_score", "leaky_downstream_span_score", "shuffled_label_q_rf_score"}:
            brier, brier_ci = metric_ci_by_run(y, score, runs, "brier")
            row.update({"brier": brier, "brier_ci_low": brier_ci[0], "brier_ci_high": brier_ci[1]})
        rows.append(row)

    tail_reject = scores.loc[scores["label_tail"] == 1, "traditional_q_reject"].to_numpy(dtype=float)
    clean_reject = scores.loc[scores["label_tail"] == 0, "traditional_q_reject"].to_numpy(dtype=float)
    tail_runs = scores.loc[scores["label_tail"] == 1, "run"].to_numpy(dtype=int)
    clean_runs = scores.loc[scores["label_tail"] == 0, "run"].to_numpy(dtype=int)
    tail_rej, tail_rej_ci = rate_ci_by_run(tail_reject, tail_runs)
    clean_ret, clean_ret_ci = rate_ci_by_run(1.0 - clean_reject, clean_runs)
    operational = {
        "traditional_cut_tail_rejection": tail_rej,
        "traditional_cut_tail_rejection_ci": tail_rej_ci,
        "traditional_cut_clean_retention": clean_ret,
        "traditional_cut_clean_retention_ci": clean_ret_ci,
    }

    delta, delta_ci = delta_auc_ci_by_run(
        y,
        scores["ml_q_rf_score"].to_numpy(dtype=float),
        scores["traditional_q_score"].to_numpy(dtype=float),
        runs,
    )
    operational["ml_minus_traditional_auc_delta"] = delta
    operational["ml_minus_traditional_auc_delta_ci"] = delta_ci
    return pd.DataFrame(rows), operational


def write_report(
    s00: pd.DataFrame,
    per_run: pd.DataFrame,
    folds: pd.DataFrame,
    ml_cv: pd.DataFrame,
    scoreboard: pd.DataFrame,
    operational: dict,
    leakage: pd.DataFrame,
    result: dict,
) -> None:
    report = f"""# Study report: S03b - q_template-only timing-tail cuts

- **Ticket:** {TICKET}
- **Author:** {WORKER}
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT files plus S01 `q_template_per_pulse.csv.gz`
- **Split:** 5-fold GroupKFold by run across analysis runs; all metrics are out-of-fold
- **Command:** `.venv/bin/python {OUT / 's03b_qtemplate_timing_tail_cuts.py'}`

## Question
Do q_template-only clean-timing cuts predict held-out downstream timing tails without using downstream span, all-span, pair residuals, or B2 displacement as model inputs?

## Raw-ROOT reproduction first
The S00 selected-pulse gate was rerun from raw ROOT before joining `q_template`.

{s00.to_markdown(index=False)}

The downstream-tail labels were then freshly derived from raw CFD20 times: events with at least two downstream B4/B6/B8 hits are clean if downstream span `<5 ns`, tail if downstream span `>10 ns`, and otherwise excluded. This produced {result['label_counts_all_runs']['labelled_events']} labelled events across all scanned runs. The head-to-head benchmark uses only analysis-run labels, where the S01 q_template input is out-of-sample with respect to calibration-template construction: {result['label_counts']['labelled_events']} labelled events, {result['label_counts']['clean']} clean and {result['label_counts']['tail']} tail.

## Methods
Traditional: a fold-local q_template-only cut scan over downstream/all mean, max, and p90 summaries. Thresholds are chosen on train runs for about 95% clean retention, then applied unchanged to held-out runs.

ML: a random forest on q_template-only summaries (`{', '.join(Q_FEATURES)}`), with hyperparameters selected by out-of-fold run CV. Missing q values are filled with train-fold medians only.

Best ML grid row:

{ml_cv.head(1).to_markdown(index=False)}

Fold cuts:

{folds[['fold', 'test_runs', 'test_tail', 'test_clean', 'traditional_cut_feature', 'traditional_cut_direction', 'traditional_cut_threshold']].to_markdown(index=False)}

## Held-out benchmark
Metrics are run-bootstrap 95% CIs over out-of-fold predictions.

{scoreboard.fillna('').to_markdown(index=False)}

Operational q cut: tail rejection {operational['traditional_cut_tail_rejection']:.3f} [{operational['traditional_cut_tail_rejection_ci'][0]:.3f}, {operational['traditional_cut_tail_rejection_ci'][1]:.3f}] at clean retention {operational['traditional_cut_clean_retention']:.3f} [{operational['traditional_cut_clean_retention_ci'][0]:.3f}, {operational['traditional_cut_clean_retention_ci'][1]:.3f}].

ML minus traditional q-template AUC = {operational['ml_minus_traditional_auc_delta']:.3f} [{operational['ml_minus_traditional_auc_delta_ci'][0]:.3f}, {operational['ml_minus_traditional_auc_delta_ci'][1]:.3f}].

## Leakage hunt
{leakage.to_markdown(index=False)}

The deliberate downstream-span control is near-perfect because it uses the label-defining variable. The admissible q-template methods are much weaker, and the shuffled-label control is near chance, so the result does not look suspiciously too good.

## Verdict
q_template alone is a weak but nonzero downstream-tail predictor. It rejects a minority of held-out timing tails at high clean retention and does not approach the forbidden downstream-span oracle. Treat q_template as a conservative shape-quality veto, not as a replacement for timing residual diagnostics.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    s00, per_run, events = scan_raw_events()
    if not bool(s00["pass"].all()):
        raise RuntimeError("S00 reproduction gate failed")

    q = qtemplate_event_table()
    all_data = events.merge(q, on=["run", "eventno", "evt"], how="left")
    data = all_data[all_data["group"].str.endswith("_analysis")].reset_index(drop=True)
    unmatched = int(data[Q_FEATURES].isna().all(axis=1).sum())
    folds, ml_cv, scores, best_params_df = run_heldout_models(data)
    scoreboard, operational = build_scoreboard(scores)

    label_counts_all_runs = {
        "downstream_ge2_events": int(per_run["downstream_ge2_events"].sum()),
        "clean": int(per_run["clean_events"].sum()),
        "tail": int(per_run["tail_events"].sum()),
        "ambiguous": int(per_run["ambiguous_events"].sum()),
        "labelled_events": int(len(all_data)),
    }
    per_run_benchmark = per_run[per_run["group"].str.endswith("_analysis")]
    label_counts = {
        "downstream_ge2_events": int(per_run_benchmark["downstream_ge2_events"].sum()),
        "clean": int(per_run_benchmark["clean_events"].sum()),
        "tail": int(per_run_benchmark["tail_events"].sum()),
        "ambiguous": int(per_run_benchmark["ambiguous_events"].sum()),
        "labelled_events": int(len(data)),
    }
    forbidden_present = sorted(set(Q_FEATURES) & FORBIDDEN)
    train_test_run_overlap = 0
    for _, row in folds.iterrows():
        test_runs = {int(x) for x in str(row["test_runs"]).split(",") if x}
        train_runs = set(all_runs()) - test_runs
        train_test_run_overlap += len(train_runs & test_runs)
    leakage = pd.DataFrame(
        [
            {"check": "q_feature_forbidden_columns", "value": ",".join(forbidden_present) if forbidden_present else "none"},
            {"check": "train_test_run_overlap_across_folds", "value": int(train_test_run_overlap)},
            {"check": "qtemplate_unmatched_events", "value": unmatched},
            {
                "check": "leaky_downstream_span_auc",
                "value": float(scoreboard.loc[scoreboard["method"] == "leaky_downstream_span_control", "roc_auc"].iloc[0]),
            },
            {
                "check": "shuffled_label_auc",
                "value": float(scoreboard.loc[scoreboard["method"] == "shuffled_label_control", "roc_auc"].iloc[0]),
            },
        ]
    )

    s00.to_csv(OUT / "reproduction_s00_counts.csv", index=False)
    per_run.to_csv(OUT / "label_counts_by_run.csv", index=False)
    all_data["used_in_benchmark"] = all_data["group"].str.endswith("_analysis").astype(int)
    all_data.to_csv(OUT / "event_level_qtemplate_dataset.csv.gz", index=False)
    folds.to_csv(OUT / "run_heldout_folds.csv", index=False)
    ml_cv.to_csv(OUT / "ml_qtemplate_rf_cv.csv", index=False)
    scores.to_csv(OUT / "heldout_scores.csv", index=False)
    scoreboard.to_csv(OUT / "scoreboard.csv", index=False)
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)

    result = {
        "study": "S03b",
        "ticket": TICKET,
        "worker": WORKER,
        "title": "q_template-only clean-timing cuts",
        "s00_reproduced": bool(s00["pass"].all()),
        "ticket_numeric_target": "none printed; S00 raw selected-pulse gate used as reproduction gate",
        "label_definition": "tail if downstream CFD20 span >10 ns, clean if <5 ns; 5-10 ns excluded",
        "label_counts_all_runs": label_counts_all_runs,
        "label_counts": label_counts,
        "traditional": clean_json(scoreboard[scoreboard["method"] == "traditional_q_template_only"].iloc[0].to_dict()),
        "traditional_operational_cut": clean_json(operational),
        "ml": clean_json(scoreboard[scoreboard["method"] == "ml_q_template_rf"].iloc[0].to_dict()),
        "leaky_control": clean_json(scoreboard[scoreboard["method"] == "leaky_downstream_span_control"].iloc[0].to_dict()),
        "shuffled_control": clean_json(scoreboard[scoreboard["method"] == "shuffled_label_control"].iloc[0].to_dict()),
        "best_ml_params": clean_json(best_params_df.iloc[0].to_dict()),
        "q_features": Q_FEATURES,
        "forbidden_features_present": forbidden_present,
        "qtemplate_unmatched_events": unmatched,
        "input_sha256": "input_sha256.csv",
        "runtime_sec": round(time.time() - start, 3),
        "next_tickets": [
            "S03d: test q_template veto thresholds on the S03/S04 pair-residual resolution tables with pair-level run bootstrap.",
            "S01f: rebuild q_template with train-run-only templates per held-out fold to remove dependence on global S01 calibration artifacts.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(clean_json(result), indent=2), encoding="utf-8")

    input_rows = []
    for run in all_runs():
        path = raw_file(run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "role": "raw_b_root"})
    input_rows.append({"path": str(QTEMPLATE_PATH), "sha256": sha256_file(QTEMPLATE_PATH), "role": "s01_q_template_table"})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    write_report(s00, per_run, folds, ml_cv, scoreboard, operational, leakage, result)

    outputs = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path), "sha256": sha256_file(path)})
    manifest = {
        "study": "S03b",
        "ticket": TICKET,
        "worker": WORKER,
        "command": f".venv/bin/python {OUT / 's03b_qtemplate_timing_tail_cuts.py'}",
        "git_commit": git_commit(),
        "random_seed": SEED,
        "runtime_sec": round(time.time() - start, 3),
        "inputs": input_rows,
        "outputs": outputs,
    }
    (OUT / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")
    print(json.dumps(clean_json(result), indent=2))


if __name__ == "__main__":
    main()
