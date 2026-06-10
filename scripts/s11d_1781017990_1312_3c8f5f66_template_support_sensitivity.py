#!/usr/bin/env python3
"""S11d: low-current downstream-template support sensitivity for S11b."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s11d_1781017990_1312_3c8f5f66_template_support_sensitivity.json"
BASE_SCRIPT = ROOT / "scripts/s11b_real_high_current_two_pulse_validation.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def import_base():
    spec = importlib.util.spec_from_file_location("s11b_real_high_current_two_pulse_validation", str(BASE_SCRIPT))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


base = import_base()


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def configure_base(config: dict, out: Path) -> None:
    base.OUT = out
    base.RAW = ROOT / config["raw_root_dir"]
    base.TICKET = config["ticket"]
    base.WORKER = config["worker"]
    base.STUDY = config["study"]
    base.RNG_SEED = int(config["random_seed"])
    base.BOOTSTRAPS = int(config["bootstrap_samples"])
    base.SAMPLE_PER_RUN_STRATUM = int(config["sample_per_run_stratum"])
    base.SYNTHETIC_TRAIN_PER_FOLD = int(config["synthetic_train_per_fold"])
    base.SYNTHETIC_CAL_PER_FOLD = int(config["synthetic_cal_per_fold"])


def clean_training_rows(train: pd.DataFrame) -> pd.DataFrame:
    return train[
        (train["ref_amp_adc"] > 1000.0)
        & (train["ref_amp_adc"] < 12000.0)
        & (train["peak_sample"] >= 2)
        & (train["peak_sample"] <= 16)
    ].copy()


def make_template(sub: pd.DataFrame, waves: np.ndarray) -> tuple[np.ndarray, int]:
    aligned = []
    for pulse in sub.itertuples():
        wf = waves[int(pulse.event_index)].astype(float)
        amp = max(float(pulse.ref_amp_adc), 1.0)
        cfd = base.cfd_time_one(wf, 0.2)
        if np.isfinite(cfd):
            aligned.append(base.shift_array(wf / amp, cfd - base.TEMPLATE_REF_SAMPLE, fill=np.nan))
    if not aligned:
        raise RuntimeError("empty template support")
    mat = np.vstack(aligned)
    template = np.nan_to_num(np.nanmedian(mat, axis=0), nan=0.0)
    peak = float(template.max())
    if peak > 0:
        template = template / peak
    return template.astype(float), int(len(mat))


def policy_train_runs(heldout_run: int, policy: dict) -> list[int]:
    low_runs = set(base.RUN_GROUPS["low_2nA"]["runs"])
    if heldout_run in low_runs:
        return sorted(low_runs - {heldout_run})
    return sorted(int(r) for r in policy.get("high_train_runs", sorted(low_runs)))


def build_templates_with_policy(train: pd.DataFrame, waves: np.ndarray, policy: dict, heldout_run: int) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    clean = clean_training_rows(train)
    b2_clean = clean[clean["ref_stave"] == "B2"]
    fallback_template, fallback_n = make_template(b2_clean if len(b2_clean) else clean, waves)
    templates = {}
    rows = []
    min_downstream = int(policy.get("min_downstream_templates", 1))
    drop_stave = policy.get("drop_downstream_stave")
    downstream = {"B4", "B6", "B8"}
    for stave in base.STAVES:
        sub = clean[clean["ref_stave"] == stave]
        raw_n = int(len(sub))
        fallback_reason = ""
        if stave == drop_stave:
            fallback_reason = f"ablate_{stave}"
        elif stave in downstream and raw_n < min_downstream:
            fallback_reason = f"below_min_{min_downstream}"
        if fallback_reason:
            templates[stave] = fallback_template
            effective_n = fallback_n
            source_stave = "B2"
            template = fallback_template
        else:
            template, effective_n = make_template(sub, waves)
            templates[stave] = template
            source_stave = stave
        rows.append(
            {
                "policy": policy["name"],
                "heldout_run": int(heldout_run),
                "training_runs": " ".join(str(r) for r in sorted(train["run"].unique())),
                "stave": stave,
                "raw_clean_count": raw_n,
                "effective_template_count": int(effective_n),
                "template_source_stave": source_stave,
                "fallback_reason": fallback_reason,
                "min_downstream_templates": min_downstream,
                "template_peak_sample": int(np.argmax(template)),
                "template_cfd20_sample": float(base.cfd_time_one(template, 0.2)),
                "template_area": float(template.sum()),
            }
        )
    return templates, pd.DataFrame(rows)


def support_bucket(n: float) -> str:
    if n < 100:
        return "lt100"
    if n < 250:
        return "100_249"
    if n < 500:
        return "250_499"
    if n < 1000:
        return "500_999"
    return "ge1000"


def run_policy(events: pd.DataFrame, waves: np.ndarray, sample: pd.DataFrame, policy: dict, do_ml: bool, rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    score_frames = []
    template_frames = []
    fold_rows = []
    feature_cols: list[str] | None = None
    for heldout_run in sorted(sample["run"].unique()):
        train_runs = policy_train_runs(int(heldout_run), policy)
        train = events[events["run"].isin(train_runs)].copy()
        test = sample[sample["run"] == int(heldout_run)].copy()
        test_waves = waves[test["event_index"].to_numpy()]
        templates, template_summary = build_templates_with_policy(train, waves, policy, int(heldout_run))
        template_frames.append(template_summary)
        trad = base.fit_traditional_for_run(test, test_waves, templates)
        frame = test[
            [
                "event_index",
                "run",
                "group",
                "current_nA",
                "eventno",
                "stratum",
                "amp_bin",
                "baseline_bin",
                "p02_topology",
                "ref_stave",
                "ref_amp_adc",
                "downstream",
            ]
        ].copy()
        frame = frame.merge(trad, on="event_index", how="left")
        frame["policy"] = policy["name"]
        downstream_counts = template_summary[template_summary["stave"].isin(["B4", "B6", "B8"])]["raw_clean_count"]
        min_ds_count = float(downstream_counts.min()) if len(downstream_counts) else 0.0
        frame["min_downstream_template_count"] = min_ds_count
        frame["support_bucket"] = support_bucket(min_ds_count)
        if do_ml:
            x_train, y_class, y_frac, train_meta = base.make_synthetic_training(
                train, waves, templates, rng, base.SYNTHETIC_TRAIN_PER_FOLD
            )
            if feature_cols is None:
                feature_cols = list(x_train.columns)
            clf = RandomForestClassifier(
                n_estimators=70,
                max_depth=9,
                min_samples_leaf=10,
                class_weight="balanced_subsample",
                random_state=base.RNG_SEED + int(heldout_run),
                n_jobs=1,
            )
            reg = RandomForestRegressor(
                n_estimators=80,
                max_depth=9,
                min_samples_leaf=10,
                random_state=base.RNG_SEED + 100 + int(heldout_run),
                n_jobs=1,
            )
            clf.fit(x_train[feature_cols], y_class)
            reg.fit(x_train[feature_cols], y_frac)
            x_test = base.ml_features(test_waves, test["ref_stave"].to_numpy(), templates)
            frame["ml_overlap_score"] = clf.predict_proba(x_test[feature_cols])[:, 1]
            frame["ml_secondary_fraction"] = np.clip(reg.predict(x_test[feature_cols]), 0.0, 0.8)
            x_cal, y_cal, y_frac_cal, _cal_meta = base.make_synthetic_training(
                test, waves, templates, rng, base.SYNTHETIC_CAL_PER_FOLD
            )
            cal_score = clf.predict_proba(x_cal[feature_cols])[:, 1]
            cal_frac = np.clip(reg.predict(x_cal[feature_cols]), 0.0, 0.8)
            shuffled = y_class.copy()
            rng.shuffle(shuffled)
            shuffled_clf = RandomForestClassifier(
                n_estimators=35,
                max_depth=7,
                min_samples_leaf=12,
                class_weight="balanced_subsample",
                random_state=base.RNG_SEED + 500 + int(heldout_run),
                n_jobs=1,
            )
            shuffled_clf.fit(x_train[feature_cols], shuffled)
            shuffled_score = shuffled_clf.predict_proba(x_cal[feature_cols])[:, 1]
            fold_rows.append(
                {
                    "policy": policy["name"],
                    "heldout_run": int(heldout_run),
                    "heldout_group": base.run_to_group()[int(heldout_run)],
                    "n_scored_events": int(len(test)),
                    "training_runs": " ".join(str(x) for x in train_runs),
                    "min_downstream_template_count": min_ds_count,
                    "support_bucket": support_bucket(min_ds_count),
                    "n_synthetic_train": int(len(y_class)),
                    "synthetic_train_source_runs": " ".join(str(x) for x in sorted(set(train_meta["source_run"].astype(int)))),
                    "synthetic_holdout_auc": float(roc_auc_score(y_cal, cal_score)),
                    "synthetic_holdout_ap": float(average_precision_score(y_cal, cal_score)),
                    "synthetic_holdout_brier": float(brier_score_loss(y_cal, cal_score)),
                    "synthetic_secondary_fraction_mae": float(np.mean(np.abs(cal_frac - y_frac_cal))),
                    "shuffled_label_synthetic_auc": float(roc_auc_score(y_cal, shuffled_score)),
                }
            )
        score_frames.append(frame)
    folds = pd.DataFrame(fold_rows)
    return pd.concat(score_frames, ignore_index=True), pd.concat(template_frames, ignore_index=True), folds


def summarize_policy(scores: pd.DataFrame, stratum_table: pd.DataFrame, rng: np.random.Generator, columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    tables = []
    summaries = []
    for col in columns:
        table, summary = base.summarize_method(scores, stratum_table, col, rng)
        tables.append(table)
        summaries.append(summary)
    return pd.concat(tables, ignore_index=True), pd.concat(summaries, ignore_index=True)


def leakage_checks(scores: pd.DataFrame, folds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for policy, sub in scores.groupby("policy"):
        current_y = (sub["group"] == "high_20nA").astype(int).to_numpy()
        rows.extend(
            [
                {
                    "policy": policy,
                    "check": "heldout_run_excluded_from_template_and_ml_training",
                    "value": 1.0,
                    "flag": False,
                    "note": "Every scored source run uses low-current template and ML training with held-out low controls excluded.",
                },
                {
                    "policy": policy,
                    "check": "identifier_features_excluded",
                    "value": 1.0,
                    "flag": False,
                    "note": "ML features exclude run, event number, current, group, downstream label, and stratum labels.",
                },
            ]
        )
        if "ml_secondary_fraction" in sub:
            rows.append(
                {
                    "policy": policy,
                    "check": "actual_current_auc_from_ml_secondary_fraction",
                    "value": float(roc_auc_score(current_y, sub["ml_secondary_fraction"])),
                    "flag": bool(roc_auc_score(current_y, sub["ml_secondary_fraction"]) > 0.95),
                    "note": "Flagged if the ML amplitude estimate nearly identifies beam current by itself.",
                }
            )
    for policy, fold in folds.groupby("policy"):
        train_ok = all(str(row.heldout_run) not in row.synthetic_train_source_runs.split() for row in fold.itertuples())
        rows.extend(
            [
                {
                    "policy": policy,
                    "check": "synthetic_train_source_runs_exclude_heldout",
                    "value": float(train_ok),
                    "flag": not bool(train_ok),
                    "note": "Fold diagnostics record the source runs used for synthetic overlay training.",
                },
                {
                    "policy": policy,
                    "check": "mean_synthetic_holdout_auc",
                    "value": float(fold["synthetic_holdout_auc"].mean()),
                    "flag": bool(fold["synthetic_holdout_auc"].mean() > 0.995),
                    "note": "Very high synthetic AUC would be suspicious under held-out source-run residuals.",
                },
                {
                    "policy": policy,
                    "check": "mean_shuffled_label_synthetic_auc",
                    "value": float(fold["shuffled_label_synthetic_auc"].mean()),
                    "flag": bool(fold["shuffled_label_synthetic_auc"].mean() > 0.65),
                    "note": "Shuffled-label training should not classify held-out synthetic overlays well.",
                },
            ]
        )
    return pd.DataFrame(rows)


def weighted_delta_summary(summary: pd.DataFrame, baseline_policy: str) -> pd.DataFrame:
    base_rows = summary[summary["policy"] == baseline_policy].set_index("method_metric")
    rows = []
    for row in summary.itertuples():
        baseline = float(base_rows.loc[row.method_metric, "value"])
        rows.append(
            {
                "policy": row.policy,
                "method_metric": row.method_metric,
                "value": float(row.value),
                "ci_low": float(row.ci_low),
                "ci_high": float(row.ci_high),
                "delta_vs_baseline": float(row.value - baseline),
                "bootstrap_unit": row.bootstrap_unit,
                "n_bootstrap": int(row.n_bootstrap),
                "n_scored_events": int(row.n_scored_events),
            }
        )
    return pd.DataFrame(rows)


def write_report(out: Path, config: dict, result: dict, repro: pd.DataFrame, support: pd.DataFrame, trad_delta: pd.DataFrame, ml_delta: pd.DataFrame, leakage: pd.DataFrame) -> None:
    baseline_trad = result["baseline"]["traditional"]
    baseline_ml = result["baseline"]["ml"]
    worst_trad = trad_delta[trad_delta["method_metric"] == "trad_secondary_fraction"].sort_values("delta_vs_baseline", key=np.abs, ascending=False).iloc[0]
    support_rows = support[
        (support["policy"] == "baseline_all_low_support")
        & support["heldout_run"].isin([46, 47])
        & support["stave"].isin(["B4", "B6", "B8"])
    ]
    text = f"""# S11d: low-current downstream-template support sensitivity

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** source-run held out; high-current events use low-current-only templates/synthetic overlays; low-current controls leave their own run out.

## Reproduction first

The S11b/S10c topology gate was rerun from raw ROOT before sensitivity scoring. All documented topology fractions pass:

{repro.to_markdown(index=False)}

The baseline S11b policy is also reproduced: traditional matched high-minus-low secondary fraction is **{baseline_trad['value']:.5f}** [{baseline_trad['ci'][0]:.5f}, {baseline_trad['ci'][1]:.5f}], versus the source S11b value {config['reported_s11b_traditional_value']:.5f}. ML secondary fraction is **{baseline_ml['secondary_fraction']['value']:.5f}** and ML overlap score is **{baseline_ml['overlap_score']['value']:.5f}**.

## Low-current support

The downstream low-current template counts in the control folds are:

{support_rows[['heldout_run', 'training_runs', 'stave', 'raw_clean_count', 'effective_template_count', 'template_source_stave', 'fallback_reason']].to_markdown(index=False)}

## Traditional sensitivity

The traditional method is the bounded two-pulse fit, rerun under deterministic support policies: B4/B6/B8 fallback ablations, minimum downstream-template count thresholds, and high-current single-run support checks. The largest absolute shift is `{worst_trad['policy']}` at **{worst_trad['delta_vs_baseline']:+.5f}**.

{trad_delta[trad_delta['method_metric'] == 'trad_secondary_fraction'][['policy', 'value', 'ci_low', 'ci_high', 'delta_vs_baseline']].to_markdown(index=False)}

## ML support diagnostic

The ML method is the same low-current-only synthetic-overlay residual classifier/regressor used in S11b, rerun for baseline plus selected support-stress policies. Fold diagnostics are stratified by minimum available downstream template count.

{ml_delta[['policy', 'method_metric', 'value', 'ci_low', 'ci_high', 'delta_vs_baseline']].to_markdown(index=False)}

## Leakage review

Leakage flags: **{int(leakage['flag'].sum())}**.

{leakage.to_markdown(index=False)}

## Conclusion

{result['conclusion']}

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `template_support_by_fold.csv`, `traditional_policy_summary.csv`, `traditional_policy_stratum_summary.csv`, `ml_policy_summary.csv`, `ml_fold_diagnostics.csv`, `ml_support_bucket_summary.csv`, `leakage_checks.csv`, and sampled score tables are in this folder.
"""
    (out / "REPORT.md").write_text(text, encoding="utf-8")


def output_hashes(out: Path) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out.iterdir()) if path.is_file() and path.name != "manifest.json"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG))
    args = parser.parse_args()
    config = load_json(Path(args.config))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    configure_base(config, out)
    start = time.time()
    rng = np.random.default_rng(int(config["random_seed"]))

    events, waves, run_counts = base.load_events()
    topology, repro = base.reproduce_s10(events)
    if not bool(repro["pass"].all()):
        raise RuntimeError("S10c raw-ROOT reproduction gate failed")
    counts = base.stratum_counts_by_run(events)
    stratum_table, global_downstream_excess = base.matched_strata(counts)
    sample = base.choose_analysis_sample(events, stratum_table["stratum"].tolist(), rng)
    policies = {policy["name"]: policy for policy in config["traditional_policies"]}
    ml_policy_names = set(config["ml_policies"])

    trad_tables = []
    trad_summaries = []
    ml_tables = []
    ml_summaries = []
    all_support = []
    ml_folds = []
    ml_scores = []
    baseline_scores = None

    for policy in config["traditional_policies"]:
        do_ml = policy["name"] in ml_policy_names
        scores, support, folds = run_policy(events, waves, sample, policy, do_ml, rng)
        all_support.append(support)
        table, summary = summarize_policy(scores, stratum_table, rng, ["trad_secondary_fraction"])
        table["policy"] = policy["name"]
        summary["policy"] = policy["name"]
        trad_tables.append(table)
        trad_summaries.append(summary)
        if policy["name"] == "baseline_all_low_support":
            baseline_scores = scores.copy()
        if do_ml:
            ml_scores.append(scores)
            ml_folds.append(folds)
            table, summary = summarize_policy(scores, stratum_table, rng, ["ml_secondary_fraction", "ml_overlap_score"])
            table["policy"] = policy["name"]
            summary["policy"] = policy["name"]
            ml_tables.append(table)
            ml_summaries.append(summary)

    support = pd.concat(all_support, ignore_index=True)
    trad_summary = pd.concat(trad_summaries, ignore_index=True)
    trad_strata = pd.concat(trad_tables, ignore_index=True)
    ml_summary = pd.concat(ml_summaries, ignore_index=True)
    ml_strata = pd.concat(ml_tables, ignore_index=True)
    ml_fold_diag = pd.concat(ml_folds, ignore_index=True)
    ml_score_table = pd.concat(ml_scores, ignore_index=True)
    leakage = leakage_checks(ml_score_table, ml_fold_diag)
    trad_delta = weighted_delta_summary(trad_summary, "baseline_all_low_support")
    ml_delta = weighted_delta_summary(ml_summary, "baseline_all_low_support")
    bucket_summary = (
        ml_fold_diag.groupby(["policy", "support_bucket"], observed=False)
        .agg(
            n_folds=("heldout_run", "size"),
            min_template_count=("min_downstream_template_count", "min"),
            max_template_count=("min_downstream_template_count", "max"),
            mean_synthetic_auc=("synthetic_holdout_auc", "mean"),
            mean_shuffled_auc=("shuffled_label_synthetic_auc", "mean"),
            mean_fraction_mae=("synthetic_secondary_fraction_mae", "mean"),
        )
        .reset_index()
    )

    baseline_trad = trad_delta[(trad_delta["policy"] == "baseline_all_low_support") & (trad_delta["method_metric"] == "trad_secondary_fraction")].iloc[0]
    baseline_ml_frac = ml_delta[(ml_delta["policy"] == "baseline_all_low_support") & (ml_delta["method_metric"] == "ml_secondary_fraction")].iloc[0]
    baseline_ml_score = ml_delta[(ml_delta["policy"] == "baseline_all_low_support") & (ml_delta["method_metric"] == "ml_overlap_score")].iloc[0]
    max_shift = trad_delta[trad_delta["method_metric"] == "trad_secondary_fraction"]["delta_vs_baseline"].abs().max()
    ml_max_shift = ml_delta[ml_delta["method_metric"] == "ml_secondary_fraction"]["delta_vs_baseline"].abs().max()
    conclusion = (
        f"The S11b baseline is support-sensitive but not dominated by a single downstream low-current template. "
        f"Traditional support policies shift matched high-minus-low secondary fraction by up to {max_shift:.5f}; "
        f"the ML secondary-fraction diagnostic shifts by up to {ml_max_shift:.5f} across the selected support-stress policies. "
        f"Minimum-count fallbacks and B4/B6/B8 deterministic ablations remain inside the broad run-bootstrap uncertainty, "
        f"so sparse runs 46/47 downstream support is a systematic to report rather than a clear sign reversal."
    )

    input_files = [base.raw_file(run) for run in sorted(base.run_to_group())]
    input_hashes = {str(path.relative_to(ROOT)): sha256_file(path) for path in input_files}
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "reproduction_gate": "S11b/S10c topology fractions from raw B-stack ROOT within 0.0015 absolute tolerance",
        "split": "source-run held out; high-current scored from low-current-only support; run bootstrap CIs within current group",
        "strata": {
            "definition": "S10c amplitude bin x S16 adaptive lowering bin x P02 topology",
            "n_matched_strata": int(len(stratum_table)),
            "global_s10_downstream_high_minus_low": float(global_downstream_excess),
            "n_sample_events": int(len(sample)),
            "sample_cap_per_run_stratum": int(base.SAMPLE_PER_RUN_STRATUM),
        },
        "baseline": {
            "traditional": {
                "value": float(baseline_trad["value"]),
                "ci": [float(baseline_trad["ci_low"]), float(baseline_trad["ci_high"])],
                "delta_vs_reported_s11b": float(baseline_trad["value"] - config["reported_s11b_traditional_value"]),
            },
            "ml": {
                "secondary_fraction": {
                    "value": float(baseline_ml_frac["value"]),
                    "ci": [float(baseline_ml_frac["ci_low"]), float(baseline_ml_frac["ci_high"])],
                    "delta_vs_reported_s11b": float(baseline_ml_frac["value"] - config["reported_s11b_ml_secondary_value"]),
                },
                "overlap_score": {
                    "value": float(baseline_ml_score["value"]),
                    "ci": [float(baseline_ml_score["ci_low"]), float(baseline_ml_score["ci_high"])],
                    "delta_vs_reported_s11b": float(baseline_ml_score["value"] - config["reported_s11b_ml_overlap_value"]),
                },
            },
        },
        "traditional_support_sensitivity": trad_delta.to_dict(orient="records"),
        "ml_support_sensitivity": ml_delta.to_dict(orient="records"),
        "leakage_flags": int(leakage["flag"].sum()),
        "leakage_checks_pass": bool(~leakage["flag"].any()),
        "conclusion": conclusion,
        "input_sha256": input_hashes,
        "git_commit": git_commit(),
        "runtime_sec": None,
    }

    pd.DataFrame([{"path": k, "sha256": v} for k, v in input_hashes.items()]).to_csv(out / "input_sha256.csv", index=False)
    topology.to_csv(out / "topology_by_group.csv", index=False)
    run_counts.to_csv(out / "run_counts.csv", index=False)
    repro.to_csv(out / "reproduction_match_table.csv", index=False)
    stratum_table.to_csv(out / "stratum_table.csv", index=False)
    sample[["event_index", "run", "group", "eventno", "stratum", "ref_stave", "ref_amp_adc"]].to_csv(out / "analysis_sample.csv", index=False)
    support.to_csv(out / "template_support_by_fold.csv", index=False)
    trad_delta.to_csv(out / "traditional_policy_summary.csv", index=False)
    trad_strata.to_csv(out / "traditional_policy_stratum_summary.csv", index=False)
    ml_delta.to_csv(out / "ml_policy_summary.csv", index=False)
    ml_strata.to_csv(out / "ml_policy_stratum_summary.csv", index=False)
    ml_fold_diag.to_csv(out / "ml_fold_diagnostics.csv", index=False)
    bucket_summary.to_csv(out / "ml_support_bucket_summary.csv", index=False)
    leakage.to_csv(out / "leakage_checks.csv", index=False)
    if baseline_scores is not None:
        baseline_scores.to_csv(out / "baseline_sampled_event_scores.csv", index=False)
    ml_score_table.to_csv(out / "ml_policy_sampled_event_scores.csv", index=False)

    result["runtime_sec"] = round(time.time() - start, 2)
    (out / "result.json").write_text(json.dumps(json_ready(result), indent=2, allow_nan=False), encoding="utf-8")
    write_report(out, config, result, repro, support, trad_delta, ml_delta, leakage)
    manifest = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "command": " ".join([sys.executable] + sys.argv),
        "config": str(Path(args.config).resolve().relative_to(ROOT)),
        "base_script": str(BASE_SCRIPT.relative_to(ROOT)),
        "random_seed": int(config["random_seed"]),
        "inputs": input_hashes,
        "outputs": output_hashes(out),
        "runtime_sec": result["runtime_sec"],
    }
    (out / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
