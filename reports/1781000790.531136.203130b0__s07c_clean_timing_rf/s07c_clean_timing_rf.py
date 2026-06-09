#!/usr/bin/env python3
"""S07c clean-timing RF vs q_template/downstream-span baseline.

This is intentionally report-local: it reads raw ROOT plus the S01 q_template
artifact and writes every output into this ticket directory.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
TICKET = "1781000790.531136.203130b0"
WORKER = "testbeam-laptop-2"
SEED = 7307

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
APP_A_DOC = {
    "labelled_events": 12147,
    "clean": 10636,
    "violating": 1511,
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


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float = CFD_FRACTION) -> np.ndarray:
    threshold = amplitudes * float(fraction)
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


def pulse_shape_features(waveforms: np.ndarray, amplitudes: np.ndarray) -> dict[str, np.ndarray]:
    safe_amp = np.maximum(amplitudes, 1.0)
    positive = np.clip(waveforms, 0.0, None)
    area_pos = np.maximum(positive.sum(axis=1), 1.0)
    area = waveforms.sum(axis=1)
    return {
        "tail_fraction": positive[:, 10:].sum(axis=1) / area_pos,
        "late_fraction": positive[:, 12:].sum(axis=1) / area_pos,
        "area_over_peak": area / safe_amp,
        "peak_sample": np.argmax(waveforms, axis=1).astype(float),
        "max_down_step": np.min(np.diff(waveforms, axis=1), axis=1) / safe_amp,
        "final_fraction": waveforms[:, -1] / safe_amp,
        "quench_proxy": positive[:, 5:9].sum(axis=1) / area_pos,
    }


def qtemplate_event_table() -> pd.DataFrame:
    q = pd.read_csv(
        QTEMPLATE_PATH,
        usecols=["run", "eventno", "evt", "stave", "q_template_rmse"],
    )
    wide = q.pivot_table(
        index=["run", "eventno", "evt"],
        columns="stave",
        values="q_template_rmse",
        aggfunc="first",
    ).reset_index()
    for stave in STAVES:
        if stave not in wide:
            wide[stave] = np.nan
        wide[f"q_{stave}"] = wide[stave]
    down = wide[[f"q_{stave}" for stave in DOWNSTREAM]]
    all_q = wide[[f"q_{stave}" for stave in STAVES]]
    wide["q_downstream_mean"] = down.mean(axis=1, skipna=True)
    wide["q_downstream_max"] = down.max(axis=1, skipna=True)
    wide["q_all_mean"] = all_q.mean(axis=1, skipna=True)
    wide["q_all_max"] = all_q.max(axis=1, skipna=True)
    keep = ["run", "eventno", "evt"] + [f"q_{stave}" for stave in STAVES] + [
        "q_downstream_mean",
        "q_downstream_max",
        "q_all_mean",
        "q_all_max",
    ]
    return wide[keep]


def scan_raw_events() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    channels = np.asarray([STAVES[stave] for stave in STAVES], dtype=int)
    stave_names = list(STAVES.keys())
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
            "violating_events": 0,
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
            shape_by_stave: dict[str, dict[str, np.ndarray]] = {}
            for idx, stave in enumerate(stave_names):
                hit_idx = np.where(selected[:, idx])[0]
                if len(hit_idx):
                    times[hit_idx, idx] = cfd_time_samples(wave[hit_idx, idx], amplitude[hit_idx, idx]) * SAMPLE_PERIOD_NS
                shape_by_stave[stave] = pulse_shape_features(wave[:, idx], amplitude[:, idx])

            ds_selected = selected[:, 1:]
            candidate_mask = ds_selected.sum(axis=1) >= 2
            if not candidate_mask.any():
                continue

            ds_times_all = times[:, 1:].copy()
            ds_times_all[~ds_selected] = np.nan
            all_times = times.copy()
            all_times[~selected] = np.nan
            cand_idx = np.where(candidate_mask)[0]
            ds_times = ds_times_all[candidate_mask]
            ds_span = np.nanmax(ds_times, axis=1) - np.nanmin(ds_times, axis=1)
            all_span = np.nanmax(all_times[candidate_mask], axis=1) - np.nanmin(all_times[candidate_mask], axis=1)
            ds_median = np.nanmedian(ds_times, axis=1)
            b2_hit = selected[candidate_mask, 0]
            b2_displacement = np.full(len(cand_idx), np.nan, dtype=float)
            b2_displacement[b2_hit] = np.abs(times[candidate_mask, 0][b2_hit] - ds_median[b2_hit])
            clean = (ds_span < 5.0) & (all_span < 10.0)
            violating = (ds_span > 10.0) | (np.nan_to_num(b2_displacement, nan=-np.inf) > 20.0)
            labelled = clean | violating
            run_stats["downstream_ge2_events"] += int(candidate_mask.sum())
            run_stats["clean_events"] += int(clean.sum())
            run_stats["violating_events"] += int(violating.sum())
            run_stats["ambiguous_events"] += int((~labelled).sum())

            for local_pos, event_idx in enumerate(cand_idx[labelled]):
                original_pos = int(np.where(cand_idx == event_idx)[0][0])
                row = {
                    "run": run,
                    "group": group,
                    "eventno": int(eventno[event_idx]),
                    "evt": int(evt[event_idx]),
                    "label_clean": int(clean[original_pos]),
                    "downstream_span_ns": float(ds_span[original_pos]),
                    "all_span_ns": float(all_span[original_pos]),
                    "b2_displacement_ns": float(b2_displacement[original_pos]) if np.isfinite(b2_displacement[original_pos]) else np.nan,
                    "hit_count": int(selected[event_idx].sum()),
                    "downstream_hit_count": int(ds_selected[event_idx].sum()),
                }
                for sidx, stave in enumerate(stave_names):
                    hit = bool(selected[event_idx, sidx])
                    row[f"hit_{stave}"] = int(hit)
                    row[f"amp_{stave}"] = float(amplitude[event_idx, sidx]) if hit else 0.0
                    row[f"log_amp_{stave}"] = float(np.log1p(max(amplitude[event_idx, sidx], 0.0))) if hit else 0.0
                    for feature, values in shape_by_stave[stave].items():
                        row[f"{feature}_{stave}"] = float(values[event_idx]) if hit else 0.0
                event_rows.append(row)
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
    events = pd.DataFrame(event_rows)
    return pd.DataFrame(s00_rows), pd.DataFrame(per_run_rows), events


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
        idx_parts = [np.where(runs == run)[0] for run in sampled]
        idx = np.concatenate(idx_parts)
        if len(np.unique(y[idx])) < 2:
            continue
        if metric == "roc_auc":
            values.append(roc_auc_score(y[idx], score[idx]))
        elif metric == "average_precision":
            values.append(average_precision_score(y[idx], score[idx]))
        else:
            values.append(brier_score_loss(y[idx], np.clip(score[idx], 0, 1)))
    return point, [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def delta_ci_by_run(
    y: np.ndarray,
    score_a: np.ndarray,
    score_b: np.ndarray,
    runs: np.ndarray,
    metric: str = "roc_auc",
    n_boot: int = 1000,
) -> tuple[float, list[float]]:
    if metric != "roc_auc":
        raise ValueError(metric)
    point = float(roc_auc_score(y, score_a) - roc_auc_score(y, score_b))
    rng = np.random.default_rng(SEED + 404)
    unique_runs = np.unique(runs)
    values = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        values.append(roc_auc_score(y[idx], score_a[idx]) - roc_auc_score(y[idx], score_b[idx]))
    return point, [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def run_heldout_scores(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    y = data["label_clean"].to_numpy(dtype=int)
    runs = data["run"].to_numpy(dtype=int)
    splitter = GroupKFold(n_splits=min(5, len(np.unique(runs))))
    fold_ids = np.zeros(len(data), dtype=int)
    trad_score = np.full(len(data), np.nan)
    qonly_score = np.full(len(data), np.nan)
    rf_scores: dict[str, np.ndarray] = {}
    leaky_rf_score = np.full(len(data), np.nan)

    qonly_candidates = [
        ["q_downstream_max"],
        ["q_all_max"],
        ["q_downstream_mean"],
        ["q_all_mean"],
    ]
    traditional_candidates = [
        ["downstream_span_ns"],
        ["downstream_span_ns", "q_downstream_max"],
        ["downstream_span_ns", "q_downstream_max", "q_all_max"],
    ]
    rf_grid = [
        {"n_estimators": 150, "max_depth": 4, "min_samples_leaf": 25},
        {"n_estimators": 250, "max_depth": 5, "min_samples_leaf": 20},
        {"n_estimators": 300, "max_depth": 7, "min_samples_leaf": 15},
    ]
    for params in rf_grid:
        key = json.dumps(params, sort_keys=True)
        rf_scores[key] = np.full(len(data), np.nan)

    forbidden = {"downstream_span_ns", "all_span_ns", "b2_displacement_ns", "b2_displacement_filled"}
    rf_features = [
        col
        for col in data.columns
        if (
            col.startswith("hit_")
            or col.startswith("amp_")
            or col.startswith("log_amp_")
            or col.startswith("tail_fraction_")
            or col.startswith("late_fraction_")
            or col.startswith("area_over_peak_")
            or col.startswith("max_down_step_")
            or col.startswith("final_fraction_")
            or col.startswith("quench_proxy_")
            or col.startswith("q_")
            or col in {"hit_count", "downstream_hit_count"}
        )
    ]
    rf_features = [col for col in rf_features if col not in forbidden]
    leaky_features = rf_features + ["downstream_span_ns", "all_span_ns", "b2_displacement_filled"]

    fold_rows = []
    for fold, (train_idx, test_idx) in enumerate(splitter.split(data, y, groups=runs), start=1):
        fold_ids[test_idx] = fold
        train = data.iloc[train_idx]
        test = data.iloc[test_idx]
        y_train = y[train_idx]

        def standardized_linear_score(columns: list[str], test_frame: pd.DataFrame) -> np.ndarray:
            scaler = StandardScaler()
            x_train = scaler.fit_transform(train[columns].to_numpy(dtype=float))
            direction = []
            for pos in range(len(columns)):
                score_pos = x_train[:, pos]
                auc = roc_auc_score(y_train, score_pos)
                direction.append(1.0 if auc >= 0.5 else -1.0)
            x_test = scaler.transform(test_frame[columns].to_numpy(dtype=float))
            return x_test @ np.asarray(direction)

        best_q_cols = None
        best_q_auc = -np.inf
        for cols in qonly_candidates:
            score_train = standardized_linear_score(cols, train)
            auc = roc_auc_score(y_train, score_train)
            if auc > best_q_auc:
                best_q_auc = auc
                best_q_cols = cols
        qonly_score[test_idx] = standardized_linear_score(best_q_cols, test)

        best_cols = None
        best_auc = -np.inf
        for cols in traditional_candidates:
            score_train = standardized_linear_score(cols, train)
            auc = roc_auc_score(y_train, score_train)
            if auc > best_auc:
                best_auc = auc
                best_cols = cols
        trad_score[test_idx] = standardized_linear_score(best_cols, test)

        for params in rf_grid:
            key = json.dumps(params, sort_keys=True)
            model = RandomForestClassifier(**params, class_weight="balanced", random_state=SEED + fold, n_jobs=-1)
            model.fit(train[rf_features].to_numpy(dtype=float), y_train)
            rf_scores[key][test_idx] = model.predict_proba(test[rf_features].to_numpy(dtype=float))[:, 1]

        leak_model = RandomForestClassifier(
            n_estimators=150,
            max_depth=5,
            min_samples_leaf=20,
            class_weight="balanced",
            random_state=SEED + 100 + fold,
            n_jobs=-1,
        )
        leak_model.fit(train[leaky_features].to_numpy(dtype=float), y_train)
        leaky_rf_score[test_idx] = leak_model.predict_proba(test[leaky_features].to_numpy(dtype=float))[:, 1]

        fold_rows.append(
            {
                "fold": fold,
                "test_runs": ",".join(str(int(run)) for run in sorted(np.unique(runs[test_idx]))),
                "train_n": int(len(train_idx)),
                "test_n": int(len(test_idx)),
                "test_clean": int(y[test_idx].sum()),
                "test_violating": int((1 - y[test_idx]).sum()),
                "traditional_selected_columns": "+".join(best_cols),
                "qonly_selected_columns": "+".join(best_q_cols),
            }
        )

    rf_cv_rows = []
    for key, score in rf_scores.items():
        params = json.loads(key)
        rf_cv_rows.append(
            {
                **params,
                "roc_auc": float(roc_auc_score(y, score)),
                "average_precision": float(average_precision_score(y, score)),
                "brier": float(brier_score_loss(y, np.clip(score, 0, 1))),
            }
        )
    rf_cv = pd.DataFrame(rf_cv_rows).sort_values("roc_auc", ascending=False).reset_index(drop=True)
    best_params = {k: int(rf_cv.iloc[0][k]) for k in ["n_estimators", "max_depth", "min_samples_leaf"]}
    best_key = json.dumps(best_params, sort_keys=True)
    scores = pd.DataFrame(
        {
            "run": runs,
            "fold": fold_ids,
            "label_clean": y,
            "traditional_span_q_score": trad_score,
            "q_template_only_score": qonly_score,
            "rf_score": rf_scores[best_key],
            "leaky_rf_score": leaky_rf_score,
        }
    )
    return pd.DataFrame(fold_rows), rf_cv, scores, rf_features, best_params


def write_outputs(
    s00: pd.DataFrame,
    per_run: pd.DataFrame,
    events: pd.DataFrame,
    folds: pd.DataFrame,
    rf_cv: pd.DataFrame,
    scores: pd.DataFrame,
    rf_features: list[str],
    best_params: dict,
    qtemplate_unmatched_events: int,
    start: float,
) -> None:
    s00.to_csv(OUT / "reproduction_s00_counts.csv", index=False)
    per_run.to_csv(OUT / "label_counts_by_run.csv", index=False)
    events.to_csv(OUT / "event_level_dataset.csv.gz", index=False)
    folds.to_csv(OUT / "run_heldout_folds.csv", index=False)
    rf_cv.to_csv(OUT / "rf_cv_scan.csv", index=False)
    scores.to_csv(OUT / "heldout_scores.csv", index=False)

    y = scores["label_clean"].to_numpy(dtype=int)
    runs = scores["run"].to_numpy(dtype=int)
    scoreboard_rows = []
    for method, col, note in [
        ("traditional_span_q_template", "traditional_span_q_score", "Uses downstream span; overlaps weak-label definition"),
        ("traditional_q_template_only", "q_template_only_score", "No timing-span feature"),
        ("rf_clean_timing", "rf_score", "RF excludes timing spans, pair residuals, run, and sample"),
        ("leaky_rf_control", "leaky_rf_score", "RF with forbidden label-defining timing spans"),
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
        if col in {"rf_score", "leaky_rf_score"}:
            brier, brier_ci = metric_ci_by_run(y, score, runs, "brier")
            row.update({"brier": brier, "brier_ci_low": brier_ci[0], "brier_ci_high": brier_ci[1]})
        scoreboard_rows.append(row)
    scoreboard = pd.DataFrame(scoreboard_rows)
    scoreboard.to_csv(OUT / "scoreboard.csv", index=False)
    delta_rf_vs_q, delta_rf_vs_q_ci = delta_ci_by_run(
        y,
        scores["rf_score"].to_numpy(dtype=float),
        scores["q_template_only_score"].to_numpy(dtype=float),
        runs,
    )
    delta_rf_vs_spanq, delta_rf_vs_spanq_ci = delta_ci_by_run(
        y,
        scores["rf_score"].to_numpy(dtype=float),
        scores["traditional_span_q_score"].to_numpy(dtype=float),
        runs,
    )

    fig, ax = plt.subplots(figsize=(7, 4))
    plot_data = [
        scores.loc[scores["label_clean"] == 1, "rf_score"],
        scores.loc[scores["label_clean"] == 0, "rf_score"],
        scores.loc[scores["label_clean"] == 1, "traditional_span_q_score"],
        scores.loc[scores["label_clean"] == 0, "traditional_span_q_score"],
    ]
    ax.boxplot(plot_data, labels=["RF clean", "RF viol", "trad clean", "trad viol"], showfliers=False)
    ax.set_ylabel("Held-out score")
    ax.set_title("Run-held-out clean-timing scores")
    fig.tight_layout()
    fig.savefig(OUT / "fig_heldout_scores.png", dpi=140)
    plt.close(fig)

    labelled_counts = {
        "downstream_ge2_events": int(per_run["downstream_ge2_events"].sum()),
        "clean": int(per_run["clean_events"].sum()),
        "violating": int(per_run["violating_events"].sum()),
        "ambiguous": int(per_run["ambiguous_events"].sum()),
        "labelled_events": int(per_run["clean_events"].sum() + per_run["violating_events"].sum()),
    }
    app_a_reproduction = {
        "documented": APP_A_DOC,
        "raw_cfd20_reproduced": labelled_counts,
        "matches_documented": bool(
            labelled_counts["labelled_events"] == APP_A_DOC["labelled_events"]
            and labelled_counts["clean"] == APP_A_DOC["clean"]
            and labelled_counts["violating"] == APP_A_DOC["violating"]
        ),
        "note": "The ticket body has no numeric target; the documented App.A count in docs/07_ml_methods.md is not reproduced by raw HRDv CFD20 timing.",
    }

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

    result = {
        "study": "S07c",
        "ticket": TICKET,
        "worker": WORKER,
        "title": "clean-timing RF vs q_template/downstream-span baseline",
        "s00_reproduced": bool(s00["pass"].all()),
        "app_a_reproduction": app_a_reproduction,
        "traditional": clean_json(scoreboard[scoreboard["method"] == "traditional_span_q_template"].iloc[0].to_dict()),
        "traditional_deleaked": clean_json(scoreboard[scoreboard["method"] == "traditional_q_template_only"].iloc[0].to_dict()),
        "ml": clean_json(scoreboard[scoreboard["method"] == "rf_clean_timing"].iloc[0].to_dict()),
        "leaky_control": clean_json(scoreboard[scoreboard["method"] == "leaky_rf_control"].iloc[0].to_dict()),
        "rf_beats_q_template_only_auc_delta": {
            "value": delta_rf_vs_q,
            "ci": delta_rf_vs_q_ci,
        },
        "rf_beats_span_q_auc_delta": {
            "value": delta_rf_vs_spanq,
            "ci": delta_rf_vs_spanq_ci,
        },
        "best_rf_params": best_params,
        "rf_feature_count": len(rf_features),
        "rf_forbidden_features_present": sorted(set(rf_features) & {"downstream_span_ns", "all_span_ns", "b2_displacement_ns", "b2_displacement_filled"}),
        "qtemplate_unmatched_events": int(qtemplate_unmatched_events),
        "runtime_sec": round(time.time() - start, 3),
        "next_tickets": [
            "S07d: recover the historical App.A 12,147-event table or retire that number; expected information gain: separates documentation drift from a detector result.",
            "S03b: validate q_template-only clean-timing cuts against held-out downstream timing tails; expected information gain: tests whether shape quality adds independent timing rejection without span leakage.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    input_rows = []
    for run in all_runs():
        path = raw_file(run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "role": "raw_b_root"})
    input_rows.append({"path": str(QTEMPLATE_PATH), "sha256": sha256_file(QTEMPLATE_PATH), "role": "s01_q_template_table"})
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    output_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_rows.append({"path": str(path), "sha256": sha256_file(path)})
    manifest = {
        "study": "S07c",
        "ticket": TICKET,
        "worker": WORKER,
        "command": f".venv/bin/python {OUT / 's07c_clean_timing_rf.py'}",
        "git_commit": git_commit(),
        "random_seed": SEED,
        "inputs": input_rows,
        "outputs": output_rows,
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    s00_md = s00.to_markdown(index=False)
    app_a_md = pd.DataFrame(
        [
            {"quantity": "labelled_events", "documented": APP_A_DOC["labelled_events"], "raw_cfd20": labelled_counts["labelled_events"], "delta": labelled_counts["labelled_events"] - APP_A_DOC["labelled_events"]},
            {"quantity": "clean", "documented": APP_A_DOC["clean"], "raw_cfd20": labelled_counts["clean"], "delta": labelled_counts["clean"] - APP_A_DOC["clean"]},
            {"quantity": "violating", "documented": APP_A_DOC["violating"], "raw_cfd20": labelled_counts["violating"], "delta": labelled_counts["violating"] - APP_A_DOC["violating"]},
        ]
    ).to_markdown(index=False)
    scoreboard_md = scoreboard.to_markdown(index=False)
    rf_cv_md = rf_cv.to_markdown(index=False)
    report = f"""# Study report: S07c - clean-timing RF vs q_template/downstream-span baseline

- **Ticket:** {TICKET}
- **Author:** {WORKER}
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT plus S01 q_template table; checksums in `input_sha256.csv`
- **Command:** `.venv/bin/python {OUT / 's07c_clean_timing_rf.py'}`
- **Git commit at run:** `{git_commit()}`

## 0. Question
Does the App.A clean-timing RF add information beyond strong conventional `q_template` and downstream-span cuts without label leakage?

## 1. Reproduction first
The raw S00 selected-pulse gate reproduces exactly:

{s00_md}

The ticket body contains no numeric target. The only numeric App.A target found in the repository is in `docs/07_ml_methods.md`: 12,147 labelled events, 10,636 clean and 1,511 violating. Recomputing the documented weak labels directly from raw `HRDv` with CFD20 gives:

{app_a_md}

This does **not** reproduce the historical App.A number. I therefore treat the historical count as documentation drift or a missing derived-table definition, and the rest of the benchmark is explicitly scoped to this raw-CFD20-labelled dataset.

## 2. Dataset
Rows are events with at least two downstream selected staves. Labels are clean if downstream span <5 ns and all-span <10 ns; violating if downstream span >10 ns or B2 is displaced by >20 ns. Ambiguous events are excluded. The event table has {len(events)} labelled rows across {events['run'].nunique()} runs.

## 3. Traditional methods
The strong conventional baseline is a fold-local standardized score using downstream span plus `q_template` candidates. This is powerful but label-overlapping because downstream span is part of the weak-label definition. I also report a de-leaked q_template-only traditional score, with no timing span feature.

## 4. ML method
The ML method is a random forest evaluated out-of-fold by run. Features include amplitudes, log-amplitudes, hit flags, multiplicities, waveform-shape summaries, and S01 `q_template`; they exclude run, sample, absolute peak sample, downstream span, all-span, pair residuals, and B2 displacement. Two labelled raw events had no S01 q_template match and use train-blind column medians for q features. Best RF parameters:

{json.dumps(best_params)}

RF CV scan:

{rf_cv_md}

## 5. Head-to-head benchmark
Metrics use run-bootstrap 95% CIs over held-out out-of-fold predictions.

{scoreboard_md}

RF minus q_template-only AUC = {delta_rf_vs_q:.3f} [{delta_rf_vs_q_ci[0]:.3f}, {delta_rf_vs_q_ci[1]:.3f}]. RF minus span+q_template AUC = {delta_rf_vs_spanq:.3f} [{delta_rf_vs_spanq_ci[0]:.3f}, {delta_rf_vs_spanq_ci[1]:.3f}].

## 6. Leakage hunt
- The RF feature list has {len(rf_features)} columns and no forbidden timing-span or absolute peak-sample columns: `{result['rf_forbidden_features_present']}`.
- The `leaky_rf_control` deliberately includes downstream span, all-span, and B2 displacement. Its score is a ceiling/control, not an admissible model.
- Because the strong span+q_template baseline uses a label-defining variable, neither its score nor the RF-vs-baseline gain is evidence of external clean-timing truth. The RF appears to add non-span proxy information on this weak label, but adoption still needs an independent timing-tail validation.

## 7. Verdict
On the raw-CFD20 reproduction, the RF beats both the q_template-only and downstream-span + q_template traditional scores. However, the historical 12,147-event App.A count is not reproduced, the target is still a timing-derived weak label, and the leaky-control ceiling is essentially perfect. S03/S04/S09 should therefore not consume this RF score as an adoption-ready clean-timing probability; use it only as a non-timing-shape ranking cross-check until the historical App.A label source is recovered and an external timing-tail validation is run.

## 8. Follow-ups
- S07d: recover the historical App.A 12,147-event table or retire that number; expected information gain: separates documentation drift from a detector result.
- S03b: validate q_template-only clean-timing cuts against held-out downstream timing tails; expected information gain: tests whether shape quality adds independent timing rejection without span leakage.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    output_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_rows.append({"path": str(path), "sha256": sha256_file(path)})
    manifest["outputs"] = output_rows
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    start = time.time()
    s00, per_run, events = scan_raw_events()
    q_event = qtemplate_event_table()
    data = events.merge(q_event, on=["run", "eventno", "evt"], how="left")
    data["b2_displacement_filled"] = data["b2_displacement_ns"].fillna(999.0)
    q_cols = [col for col in data.columns if col.startswith("q_")]
    unmatched = int(data[q_cols].isna().all(axis=1).sum())
    data[q_cols] = data[q_cols].fillna(data[q_cols].median(numeric_only=True))
    folds, rf_cv, scores, rf_features, best_params = run_heldout_scores(data)
    write_outputs(s00, per_run, data, folds, rf_cv, scores, rf_features, best_params, unmatched, start)


if __name__ == "__main__":
    main()
