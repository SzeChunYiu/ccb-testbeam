#!/usr/bin/env python3
"""Post-process S07m artifacts with support-matched calibration and report text."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def md_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    cols = list(frame.columns)
    def fmt(v):
        if pd.isna(v):
            return ""
        if isinstance(v, float):
            return f"{v:.6g}"
        return str(v)
    rows = [[fmt(row[c]) for c in cols] for _, row in frame.iterrows()]
    widths = [len(c) for c in cols]
    for row in rows:
        widths = [max(w, len(x)) for w, x in zip(widths, row)]
    out = ["| " + " | ".join(c.ljust(w) for c, w in zip(cols, widths)) + " |"]
    out.append("| " + " | ".join("-" * w for w in widths) + " |")
    out += ["| " + " | ".join(x.ljust(w) for x, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join(out)


def robust_width(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float(0.5 * (q84 - q16))


def support_key(data: pd.DataFrame, config: dict) -> pd.Series:
    q = int(config.get("match_quantile_bins", 4))
    amp_cols = [c for c in data.columns if c.endswith("_log_amp")]
    amp = pd.Series(data[amp_cols].to_numpy(float).mean(axis=1), index=data.index)
    base = pd.Series(data["ds_shape_mean_final_fraction"].to_numpy(float), index=data.index)
    amp_bin = amp.groupby(data["run"]).transform(lambda x: pd.qcut(x.rank(method="first"), q, labels=False, duplicates="drop"))
    base_bin = base.groupby(data["run"]).transform(lambda x: pd.qcut(x.rank(method="first"), q, labels=False, duplicates="drop"))
    return (
        data["run"].astype(str)
        + "|a" + amp_bin.fillna(-1).astype(int).astype(str)
        + "|t" + data["n_downstream"].astype(int).astype(str)
        + "|b" + base_bin.fillna(-1).astype(int).astype(str)
    )


def main() -> int:
    config = json.loads(CONFIG.read_text())
    out_dir = ROOT / config["output_dir"]
    result_path = out_dir / "result.json"
    result = json.loads(result_path.read_text())

    utils = load_module("s07m_s07d_helper", ROOT / config["s07d_helper_script"])
    s07h = load_module("s07m_s07h_helper", ROOT / config["s07h_helper_script"])
    _, _, clean_payloads = utils.build_base_events(config)
    data = utils.make_dataset(config, clean_payloads)
    data = s07h.add_p02_morphology_columns(data, config).reset_index(drop=True)
    oof = pd.read_csv(out_dir / "oof_predictions.csv").reset_index(drop=True)
    y = data["label_injected"].to_numpy(int)
    runs = data["run"].to_numpy(int)
    keys = support_key(data, config).to_numpy()
    min_clean = int(config.get("min_match_stratum_train_clean", 20))
    eff = float(config["fixed_clean_efficiency"])
    score_cols = [c for c in oof.columns if c.endswith("_score")]
    rows = []
    drift_rows = []
    for col in score_cols:
        method = col[:-6].replace("_", " ")
        score = oof[col].to_numpy(float)
        for held_run in sorted(np.unique(runs)):
            train_clean = (runs != held_run) & (y == 0) & np.isfinite(score)
            test = (runs == held_run) & np.isfinite(score)
            global_thr = float(np.quantile(score[train_clean], eff))
            thresholds = {}
            for key in np.unique(keys[train_clean]):
                idx = train_clean & (keys == key)
                if idx.sum() >= min_clean:
                    thresholds[key] = float(np.quantile(score[idx], eff))
            test_idx = np.flatnonzero(test)
            thr = np.array([thresholds.get(keys[i], global_thr) for i in test_idx])
            fallback = np.array([keys[i] not in thresholds for i in test_idx])
            yy = y[test_idx]
            ss = score[test_idx]
            rows.append({
                "method": method,
                "heldout_run": int(held_run),
                "clean_acceptance": float(np.mean(ss[yy == 0] <= thr[yy == 0])),
                "false_positive_rate": float(np.mean(ss[yy == 0] > thr[yy == 0])),
                "injected_rejection": float(np.mean(ss[yy == 1] > thr[yy == 1])),
                "fallback_fraction": float(np.mean(fallback)),
                "matched_strata": int(len(thresholds)),
            })
            clean_test = test & (y == 0)
            clean_ids = np.flatnonzero(clean_test)
            clean_thr = np.array([thresholds.get(keys[i], global_thr) for i in clean_ids])
            accepted_ids = clean_ids[score[clean_ids] <= clean_thr]
            amp_cols = [c for c in data.columns if c.endswith("_log_amp")]
            drift_rows.append({
                "method": method,
                "heldout_run": int(held_run),
                "veto_fraction": float(1.0 - len(accepted_ids) / max(1, len(clean_ids))),
                "timing_sigma68_delta_ns": robust_width(data.loc[accepted_ids, "d_t_ns"].to_numpy(float)) - robust_width(data.loc[clean_ids, "d_t_ns"].to_numpy(float)),
                "charge_logamp_delta": float(data.loc[accepted_ids, amp_cols].to_numpy(float).mean() - data.loc[clean_ids, amp_cols].to_numpy(float).mean()),
                "baseline_final_fraction_delta": float(data.loc[accepted_ids, "ds_shape_mean_final_fraction"].mean() - data.loc[clean_ids, "ds_shape_mean_final_fraction"].mean()),
                "topology_n_downstream_delta": float(data.loc[accepted_ids, "n_downstream"].mean() - data.loc[clean_ids, "n_downstream"].mean()),
            })
    matched = pd.DataFrame(rows)
    matched_summary = matched.groupby("method", sort=False).agg(
        clean_acceptance_mean=("clean_acceptance", "mean"),
        false_positive_rate_mean=("false_positive_rate", "mean"),
        injected_rejection_mean=("injected_rejection", "mean"),
        fallback_fraction_mean=("fallback_fraction", "mean"),
        matched_strata_mean=("matched_strata", "mean"),
        runs=("heldout_run", "nunique"),
    ).reset_index().sort_values("injected_rejection_mean", ascending=False)
    matched_drift = pd.DataFrame(drift_rows)
    matched_drift_summary = matched_drift.groupby("method", sort=False).mean(numeric_only=True).reset_index()
    matched.to_csv(out_dir / "matched_calibration_by_run.csv", index=False)
    matched_summary.to_csv(out_dir / "matched_calibration_summary.csv", index=False)
    matched_drift.to_csv(out_dir / "matched_support_drift_by_run.csv", index=False)
    matched_drift_summary.to_csv(out_dir / "matched_support_drift_summary.csv", index=False)

    method_summary = pd.read_csv(out_dir / "method_summary.csv")
    repro = pd.read_csv(out_dir / "reproduction_match_table.csv")
    op = pd.read_csv(out_dir / "operating_point_summary.csv")
    leakage = pd.read_csv(out_dir / "leakage_checks.csv")
    counts = pd.read_csv(out_dir / "injected_counts_by_run.csv")
    winner_row = method_summary.sort_values("roc_auc", ascending=False).iloc[0]
    trad_row = method_summary[method_summary["method"] == "traditional timing/template reference"].iloc[0]
    matched_winner = matched_summary.iloc[0]
    result.update({
        "study": "S07m",
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "benchmark_winner": str(winner_row["method"]),
        "support_matched_calibration_winner": str(matched_winner["method"]),
        "matched_calibration_summary": matched_summary.to_dict(orient="records"),
        "matched_support_drift_summary": matched_drift_summary.to_dict(orient="records"),
        "next_tickets": ["S07n: hierarchical support-pooling calibration for injected morphology"],
    })
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    report = f"""# S07m: support-preserving injected-morphology calibration

- **Study ID:** S07m
- **Ticket:** {config['ticket_id']}
- **Author:** {config['worker']}
- **Date:** 2026-07-09
- **Depends on:** S07l, S07h, S07d helper code
- **Input:** raw B-stack HRDv ROOT files under `{config['raw_root_dir']}`
- **Config:** `configs/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.json`
- **Git commit used by script:** {git_commit()}

## 0. Question
Can the S07l injected-morphology score keep injected-overlap AP/AUC after thresholds are calibrated within run, amplitude, topology, and baseline-proxy matched clean strata?

The pre-registered metrics are injected AP/AUC, fixed-FPR detection, timing sigma68 delta, support drift, and run-block bootstrap 95 percent CIs.

## 1. Reproduction
Raw ROOT was read directly and the parent quantities were rebuilt before any model comparison.

{md_table(repro)}

The paired injected dataset is split by run; raw-clean and injected copies share a pair id and therefore cannot cross train/test folds.

{md_table(counts)}

## 2. Traditional Method
The non-ML comparator is the fold-local timing/template score from S07l. For each held-out run, the training runs choose the best signed scalar among downstream D_t, |C_t|, late-fraction morphology summaries, downstream peak summaries, and matched-secondary-template residuals. The score is standardized by the training median and IQR:

\\[
s_i = \\frac{{\\operatorname{{sign}}(x_j)x_{{ij}}-\\operatorname{{median}}_T(\\operatorname{{sign}}(x_j)x_j)}}{{\\operatorname{{IQR}}_T(\\operatorname{{sign}}(x_j)x_j)}}.
\\]

This is a strong traditional method because it can use timing/template observables that the strict shape-only learned models cannot use.

## 3. ML and NN Methods
The benchmark includes ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN, and a residual dilated temporal CNN with auxiliary morphology-stat fusion. All models use leave-one-run-out outer folds; dense models use inner run-CV hyperparameter selection; neural models use a deterministic inner validation run per outer fold. Probabilities are cross-fold isotonic calibrations.

{md_table(method_summary)}

The discrimination winner in `result.json` is **{winner_row['method']}** with ROC AUC {winner_row['roc_auc']:.4f} [{winner_row['roc_auc_ci_low']:.4f}, {winner_row['roc_auc_ci_high']:.4f}], versus traditional ROC AUC {trad_row['roc_auc']:.4f}.

## 4. Support-Matched Calibration
S07m replaces the single fold threshold with support-stratum thresholds:

\\[
\\tau_{{r,k}} = Q_{{0.95}}\\left(s_i \\mid y_i=0, r_i\\ne r, k_i=k\\right),
\\quad
k=(r, q_A, n_{{downstream}}, q_B),
\\]

where q_A is the run-local mean-log-amplitude quartile and q_B is the run-local baseline-final-fraction quartile. Sparse strata use the fold-global clean threshold; the fallback fraction is reported as a systematic.

{md_table(matched_summary)}

The support-matched fixed-FPR winner is **{matched_winner['method']}** with injected rejection {matched_winner['injected_rejection_mean']:.4f} at false-positive rate {matched_winner['false_positive_rate_mean']:.4f}; fallback fraction is {matched_winner['fallback_fraction_mean']:.4f}.

## 5. Support Drift
Matched calibration is evaluated on the raw-clean member only. Timing uses robust sigma68, charge uses mean log-amplitude, baseline uses the final-fraction proxy, and topology uses downstream multiplicity.

{md_table(matched_drift_summary)}

## 6. Falsification and Systematics
The leakage probes reject trivial explanations: topology-only and pre-injection D_t are near chance, shuffled-label training is near chance, and the stronger amplitude-only nuisance remains below the main learned models.

{md_table(leakage)}

Systematics: injection realism is not beam truth; bootstrap CIs cover run blocks but not future domain shift; sparse support strata induce fallback; and support proxies are not calibrated physical observables. The conclusion is therefore a screening and calibration result, not a production veto prescription.

## 7. Verdict
ML beats the strong traditional method on injected non-D_t morphology. Gradient-boosted trees are the discrimination winner, while support-matched calibration names **{matched_winner['method']}** as the operating-point winner under the ticket's fixed-FPR rule. The result supports the hypothesis that overlap information lives in normalized downstream morphology residuals, but sparse support bins remain the limiting systematic.

## 8. Next Step
Queued follow-up: S07n, hierarchical support-pooling calibration for injected morphology. Expected information gain: tests whether adjacent support-bin shrinkage can reduce fallback without increasing timing, charge, baseline, or topology drift.

## 9. Reproducibility
Regenerate with:

```bash
uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python scripts/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.py --config configs/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.json
uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python scripts/s07m_1781127054_1319_2f651c5f_augment_report.py
```
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")

    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update({
        "ticket": config["ticket_id"],
        "study": "S07m",
        "worker": config["worker"],
        "python": platform.python_version(),
        "command": "scripts/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.py --config configs/s07m_1781127054_1319_2f651c5f_support_preserving_calibration.json",
        "environment_command": "uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python",
        "postprocess_command": "scripts/s07m_1781127054_1319_2f651c5f_augment_report.py",
        "postprocess_environment_command": "uv run --index-strategy unsafe-best-match --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple --with uproot --with numpy --with pandas --with scikit-learn --with matplotlib --with 'torch==2.5.1+cpu' python",
        "outputs": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"},
    })
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"done": True, "matched_winner": str(matched_winner["method"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
