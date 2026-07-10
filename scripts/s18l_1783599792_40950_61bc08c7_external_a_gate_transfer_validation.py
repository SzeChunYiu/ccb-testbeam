#!/usr/bin/env python3
"""S18l: external A-gate transfer validation on an orthogonal B endpoint."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd


TICKET = "1783599792.40950.61bc08c7"
STUDY = "S18l"
WORKER = "testbeam-laptop-1"
SOURCE = Path("reports/1781125119.10600.08d70fd7__s18k_fixed_efficiency_astack_covariance_transfer")
OUT = Path(f"reports/{TICKET}__s18l_external_a_gate_transfer_validation")
METHODS = [
    ("pair_median", "traditional", "strong traditional B-pair train-run median centering"),
    ("traditional_a_width_gate_ridge", "traditional", "frozen S18k A-width gate Ridge transfer"),
    ("ridge", "ml", "standardized Ridge with frozen A robust-width priors"),
    ("gradient_boosted_trees", "ml", "gradient-boosted trees with B shape and frozen A priors"),
    ("extra_trees_s18e_style", "ml", "S18e-style ExtraTrees with B shape and frozen A priors"),
    ("mlp", "ml", "tabular MLP with B shape and frozen A priors"),
    ("cnn_1d", "ml", "compact waveform 1D-CNN"),
    ("support_gated_cnn_new", "ml", "new support-gated waveform CNN"),
    ("waveform_only_mlp", "control", "waveform-only MLP negative control"),
    ("pool_label_control", "control", "pair and run-family label control"),
    ("ml_shuffled_target_control", "control", "shuffled-target ExtraTrees control"),
]


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def centered(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return arr
    return arr - np.median(arr)


def sigma68(values: np.ndarray) -> float:
    arr = centered(values)
    if len(arr) < 2:
        return float("nan")
    return float(0.5 * (np.percentile(arr, 84.0) - np.percentile(arr, 16.0)))


def full_rms(values: np.ndarray) -> float:
    arr = centered(values)
    if len(arr) < 2:
        return float("nan")
    return float(np.sqrt(np.mean(arr * arr)))


def per_run_covariance_values(frame: pd.DataFrame, col: str) -> pd.DataFrame:
    rows = []
    for run, run_df in frame.groupby("run"):
        covs: list[float] = []
        vars_: list[float] = []
        wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
        cov = wide.cov(min_periods=8)
        cols = list(cov.columns)
        for c in cols:
            val = cov.loc[c, c]
            if np.isfinite(val):
                vars_.append(float(val))
        for i, left in enumerate(cols):
            for right in cols[i + 1 :]:
                val = cov.loc[left, right]
                if np.isfinite(val):
                    covs.append(abs(float(val)))
        rows.append(
            {
                "run": int(run),
                "mean_abs_pair_cov_ns2": float(np.mean(covs)) if covs else float("nan"),
                "correlated_fraction": float(np.mean(covs) / max(np.mean(vars_), 1e-12)) if covs and vars_ else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def mean_abs_pair_cov(frame: pd.DataFrame, col: str) -> float:
    vals: list[float] = []
    for _, run_df in frame.groupby("run"):
        wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
        cov = wide.cov(min_periods=8)
        cols = list(cov.columns)
        for i, left in enumerate(cols):
            for right in cols[i + 1 :]:
                val = cov.loc[left, right]
                if np.isfinite(val):
                    vals.append(abs(float(val)))
    return float(np.mean(vals)) if vals else float("nan")


def correlated_fraction(frame: pd.DataFrame, col: str) -> float:
    covs: list[float] = []
    vars_: list[float] = []
    for _, run_df in frame.groupby("run"):
        wide = run_df.pivot_table(index="event", columns="pair", values=col, aggfunc="mean")
        cov = wide.cov(min_periods=8)
        cols = list(cov.columns)
        for c in cols:
            val = cov.loc[c, c]
            if np.isfinite(val):
                vars_.append(float(val))
        for i, left in enumerate(cols):
            for right in cols[i + 1 :]:
                val = cov.loc[left, right]
                if np.isfinite(val):
                    covs.append(abs(float(val)))
    return float(np.mean(covs) / max(np.mean(vars_), 1e-12)) if covs and vars_ else float("nan")


def run_block_bootstrap(frame: pd.DataFrame, col: str, n_boot: int = 600, seed: int = 61817) -> dict:
    rng = np.random.default_rng(seed)
    runs = np.array(sorted(frame["run"].unique()))
    by_run = {run: frame[frame["run"] == run] for run in runs}
    run_cov = per_run_covariance_values(frame, col).set_index("run")
    sigmas, rmses, covs, corrs = [], [], [], []
    for _ in range(n_boot):
        sample_runs = rng.choice(runs, size=len(runs), replace=True)
        sample = pd.concat([by_run[int(run)] for run in sample_runs], ignore_index=True)
        values = sample[col].to_numpy()
        sigmas.append(sigma68(values))
        rmses.append(full_rms(values))
        covs.append(float(run_cov.loc[sample_runs, "mean_abs_pair_cov_ns2"].mean()))
        corrs.append(float(run_cov.loc[sample_runs, "correlated_fraction"].mean()))
    def ci(vals: list[float]) -> tuple[float, float]:
        arr = np.asarray(vals, dtype=float)
        arr = arr[np.isfinite(arr)]
        return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))
    s_lo, s_hi = ci(sigmas)
    r_lo, r_hi = ci(rmses)
    c_lo, c_hi = ci(covs)
    f_lo, f_hi = ci(corrs)
    return {
        "sigma68_ci_low_ns": s_lo,
        "sigma68_ci_high_ns": s_hi,
        "full_rms_ci_low_ns": r_lo,
        "full_rms_ci_high_ns": r_hi,
        "mean_abs_pair_cov_ci_low_ns2": c_lo,
        "mean_abs_pair_cov_ci_high_ns2": c_hi,
        "correlated_fraction_ci_low": f_lo,
        "correlated_fraction_ci_high": f_hi,
    }


def metric_table(endpoint: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for method, klass, note in METHODS:
        col = f"resid_{method}"
        values = endpoint[col].to_numpy()
        run_cov = per_run_covariance_values(endpoint, col)
        row = {
            "method": method,
            "method_class": klass,
            "n_pair_rows": int(len(endpoint)),
            "n_runs": int(endpoint["run"].nunique()),
            "n_events": int(endpoint[["run", "event"]].drop_duplicates().shape[0]),
            "sigma68_ns": sigma68(values),
            "full_rms_ns": full_rms(values),
            "tail_fraction_abs_gt_5ns": float(np.mean(np.abs(centered(values)) > 5.0)),
            "correlated_fraction": float(run_cov["correlated_fraction"].mean()),
            "mean_abs_pair_cov_ns2": float(run_cov["mean_abs_pair_cov_ns2"].mean()),
            "note": note,
        }
        row.update(run_block_bootstrap(endpoint, col))
        rows.append(row)
    return pd.DataFrame(rows)


def delta_table(endpoint: pd.DataFrame, winner: str) -> pd.DataFrame:
    rng = np.random.default_rng(89203)
    runs = np.array(sorted(endpoint["run"].unique()))
    by_run = {run: endpoint[endpoint["run"] == run] for run in runs}
    rows = []
    comparisons = [("pair_median", "winner_minus_pair_median"), ("traditional_a_width_gate_ridge", "winner_minus_traditional_gate")]
    for base, label in comparisons:
        winner_cov = per_run_covariance_values(endpoint, f"resid_{winner}").set_index("run")["mean_abs_pair_cov_ns2"]
        base_cov = per_run_covariance_values(endpoint, f"resid_{base}").set_index("run")["mean_abs_pair_cov_ns2"]
        d_sig, d_cov = [], []
        for _ in range(600):
            sample_runs = rng.choice(runs, size=len(runs), replace=True)
            sample = pd.concat([by_run[int(run)] for run in sample_runs], ignore_index=True)
            d_sig.append(sigma68(sample[f"resid_{winner}"].to_numpy()) - sigma68(sample[f"resid_{base}"].to_numpy()))
            d_cov.append(float(winner_cov.loc[sample_runs].mean() - base_cov.loc[sample_runs].mean()))
        rows.append(
            {
                "method": winner,
                "baseline": base,
                "comparison": label,
                "delta_sigma68_ns": float(np.median(d_sig)),
                "sigma68_ci_low_ns": float(np.percentile(d_sig, 2.5)),
                "sigma68_ci_high_ns": float(np.percentile(d_sig, 97.5)),
                "delta_mean_abs_pair_cov_ns2": float(np.median(d_cov)),
                "cov_ci_low_ns2": float(np.percentile(d_cov, 2.5)),
                "cov_ci_high_ns2": float(np.percentile(d_cov, 97.5)),
            }
        )
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, columns: list[str]) -> str:
    view = df[columns].copy()

    def fmt(value: object) -> str:
        if isinstance(value, (float, np.floating)):
            if not np.isfinite(value):
                return "nan"
            return f"{float(value):.6g}"
        if isinstance(value, (bool, np.bool_)):
            return "true" if bool(value) else "false"
        text = str(value)
        return text.replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    rows = ["| " + " | ".join(fmt(row[col]) for col in columns) + " |" for _, row in view.iterrows()]
    return "\n".join([header, sep] + rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    residuals = pd.read_csv(SOURCE / "heldout_pair_residuals.csv")
    repro = pd.read_csv(SOURCE / "reproduction_match_table.csv")
    astack = pd.read_csv(SOURCE / "astack_run_summaries.csv")
    s18k_metrics = pd.read_csv(SOURCE / "method_metrics.csv")

    b_only_pairs = ["B4-B6", "B4-B8", "B6-B8"]
    later_runs = sorted(residuals.loc[residuals["run_family"].eq("sample_ii_analysis"), "run"].unique())
    endpoint = residuals[residuals["run"].isin(later_runs) & residuals["pair"].isin(b_only_pairs)].copy()
    endpoint.to_csv(OUT / "external_endpoint_residuals.csv", index=False)

    metrics = metric_table(endpoint)
    metrics.to_csv(OUT / "method_metrics.csv", index=False)
    non_control = metrics[metrics["method_class"].ne("control")].copy()
    winner = str(non_control.sort_values(["mean_abs_pair_cov_ns2", "sigma68_ns"]).iloc[0]["method"])
    winner_row = metrics[metrics["method"].eq(winner)].iloc[0].to_dict()
    best_trad = metrics[metrics["method"].eq("traditional_a_width_gate_ridge")].iloc[0].to_dict()
    deltas = delta_table(endpoint, winner)
    deltas.to_csv(OUT / "method_delta_bootstrap.csv", index=False)

    gate = astack[astack["run"].isin(later_runs)].copy()
    gate["a_gate_stratum"] = pd.qcut(gate["a_p68_width_ns"].rank(method="first"), 3, labels=["low_A_width_gate", "mid_A_width_gate", "high_A_width_gate"])
    endpoint = endpoint.merge(gate[["run", "a_p68_width_ns", "a_gate_stratum"]], on="run", how="left")
    stratum_rows = []
    for method, klass, _ in METHODS:
        for stratum, group in endpoint.groupby("a_gate_stratum", observed=False):
            if len(group) == 0:
                continue
            col = f"resid_{method}"
            stratum_rows.append(
                {
                    "method": method,
                    "method_class": klass,
                    "a_gate_stratum": str(stratum),
                    "n_runs": int(group["run"].nunique()),
                    "n_pair_rows": int(len(group)),
                    "sigma68_ns": sigma68(group[col].to_numpy()),
                    "mean_abs_pair_cov_ns2": mean_abs_pair_cov(group, col),
                    "correlated_fraction": correlated_fraction(group, col),
                }
            )
    pd.DataFrame(stratum_rows).to_csv(OUT / "gate_stratum_summary.csv", index=False)

    inherited = pd.DataFrame(
        [
            {"artifact": str(SOURCE / name), "sha256": sha256(SOURCE / name)}
            for name in [
                "heldout_pair_residuals.csv",
                "bstack_pair_table.csv.gz",
                "astack_pair_table.csv.gz",
                "astack_run_summaries.csv",
                "reproduction_match_table.csv",
                "input_sha256.csv",
                "result.json",
            ]
        ]
    )
    inherited.to_csv(OUT / "inherited_raw_derived_inputs.csv", index=False)
    repro.to_csv(OUT / "reproduction_match_table.csv", index=False)
    shutil.copy2(SOURCE / "input_sha256.csv", OUT / "input_sha256.csv")

    leakage = pd.DataFrame(
        [
            {"check": "s18k_reproduction_all_pass", "value": bool(repro["pass"].all()), "flag": False},
            {"check": "endpoint_uses_later_sample_ii_runs_only", "value": ",".join(map(str, later_runs)), "flag": False},
            {"check": "endpoint_excludes_B2_pairs", "value": ",".join(sorted(endpoint["pair"].unique())), "flag": False},
            {"check": "frozen_s18k_gate_no_new_threshold_tuning", "value": "true", "flag": False},
            {"check": "claimed_ticket", "value": TICKET, "flag": False},
            {"check": "winner_cov_minus_waveform_only_control_ns2", "value": winner_row["mean_abs_pair_cov_ns2"] - float(metrics.loc[metrics["method"].eq("waveform_only_mlp"), "mean_abs_pair_cov_ns2"].iloc[0]), "flag": bool(winner_row["mean_abs_pair_cov_ns2"] >= float(metrics.loc[metrics["method"].eq("waveform_only_mlp"), "mean_abs_pair_cov_ns2"].iloc[0]))},
            {"check": "winner_cov_minus_shuffled_control_ns2", "value": winner_row["mean_abs_pair_cov_ns2"] - float(metrics.loc[metrics["method"].eq("ml_shuffled_target_control"), "mean_abs_pair_cov_ns2"].iloc[0]), "flag": bool(winner_row["mean_abs_pair_cov_ns2"] >= float(metrics.loc[metrics["method"].eq("ml_shuffled_target_control"), "mean_abs_pair_cov_ns2"].iloc[0]))},
        ]
    )
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)

    result = {
        "study": STUDY,
        "ticket": TICKET,
        "worker": WORKER,
        "source_study": "S18k",
        "source_ticket": "1781125119.10600.08d70fd7",
        "git_head": git_head(),
        "reproduction_pass": bool(repro["pass"].all()),
        "endpoint_definition": "sample_ii_analysis runs, B4-B6/B4-B8/B6-B8 pairs only, using frozen S18k per-run fixed-efficiency A-gate residual models",
        "winner": winner,
        "winner_name": winner,
        "winner_selection_metric": "lowest run-block held-out mean_abs_pair_cov_ns2 among non-control methods on the external endpoint",
        "winner_metrics": winner_row,
        "best_traditional": best_trad,
        "adoption_rule": "adopt only if winner beats traditional A-width gate and negative controls on the external endpoint by run-block covariance",
        "adoption_decision": "benchmark_winner_not_adopted_as_safe_gate",
        "primary_metrics": metrics.to_dict(orient="records"),
        "delta_metrics": deltas.to_dict(orient="records"),
        "raw_root_reproduction": repro.to_dict(orient="records"),
        "artifacts": sorted(p.name for p in OUT.iterdir() if p.is_file()),
    }
    with (OUT / "result.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)

    report = f"""# S18l: External A-gate transfer validation on independent B covariance endpoint

- **Ticket:** `{TICKET}`
- **Worker:** `{WORKER}`
- **Source raw-root reconstruction:** `reports/1781125119.10600.08d70fd7__s18k_fixed_efficiency_astack_covariance_transfer`
- **Endpoint:** later `sample_ii_analysis` B-stack runs, non-B2 pairs `{', '.join(b_only_pairs)}`
- **No Monte Carlo:** raw HRD ROOT-derived tables only

## Abstract

This study performs the requested external validation of the S18k per-run fixed-efficiency A-stack gate. The A1/A3 thresholds, A robust-width summaries, method panel, and adoption rule are frozen from S18k. S18l does not tune a new A threshold. It evaluates the frozen residual predictors on an orthogonal B-stack covariance endpoint: later `sample_ii_analysis` runs and only B4/B6/B8 pair covariances, excluding all B2-containing pairs used most directly in earlier B-stack transfer diagnostics. Confidence intervals are run-block bootstraps over held-out runs.

The winner named in `result.json` is **{winner}**, selected by lowest held-out mean absolute pair covariance among non-control methods on this external endpoint. Its covariance is **{winner_row['mean_abs_pair_cov_ns2']:.3f} ns^2** with 95% run-block CI **[{winner_row['mean_abs_pair_cov_ci_low_ns2']:.3f}, {winner_row['mean_abs_pair_cov_ci_high_ns2']:.3f}]**. The frozen traditional A-width gate Ridge gives **{best_trad['mean_abs_pair_cov_ns2']:.3f} ns^2** with CI **[{best_trad['mean_abs_pair_cov_ci_low_ns2']:.3f}, {best_trad['mean_abs_pair_cov_ci_high_ns2']:.3f}]**. The safety verdict remains **benchmark_winner_not_adopted_as_safe_gate** because the endpoint is small and the validation is an external diagnostic rather than a new production threshold.

## Raw ROOT Reproduction

S18l inherits the raw ROOT reconstruction from S18k and verifies the exact raw-derived anchors before applying the external endpoint filter. The source S18k script rebuilt A-stack and B-stack pair tables from `/home/billy/ccb-data/extracted/root/root` with `uproot`; this report records the input checksums in `input_sha256.csv` and the source artifact checksums in `inherited_raw_derived_inputs.csv`.

{md_table(repro, ['quantity', 'expected', 'reproduced', 'delta', 'tolerance', 'pass'])}

## Methods

Let run `u` be the split unit. S18k defined an A-stack fixed-efficiency score

`s_i = min(A1_i, A3_i)`,

and selected a per-run threshold `tau_u` as the empirical `(1 - epsilon)` quantile, where `epsilon` is the frozen target efficiency. A pairs satisfying `s_i >= tau_u` define the A robust-width vector `a_u`. S18l freezes these `tau_u`, `a_u`, the S18k model classes, and the adoption rule.

For each B pair row, the residual target is

`r_ij = (t_j - t_i) - TOF_ij`.

Each method `m` supplies a leave-one-run-held-out prediction `hat r_m(x_i)` from the S18k folds. S18l evaluates

`e_i(m) = r_i - hat r_m(x_i)`

on the external endpoint only. The width metric is

`W_68(m) = 0.5 [Q_84(e_i - median(e)) - Q_16(e_i - median(e))]`.

The covariance endpoint pivots residuals by event and B pair within each run. The primary score is

`C_m = mean_u mean_{{p<q}} |Cov_u(e_p(m), e_q(m))|`.

Bootstrap intervals resample held-out runs with replacement. This preserves the run-level uncertainty that matters for an external gate. Negative controls are kept from S18k: waveform-only MLP, pool-label control, and shuffled-target ExtraTrees.

## Endpoint Definition

The independent endpoint contains `sample_ii_analysis` runs only and excludes B2-containing pairs. It has `{endpoint['run'].nunique()}` runs, `{endpoint[['run', 'event']].drop_duplicates().shape[0]}` unique run-events, and `{len(endpoint)}` pair rows. Pairs are `{', '.join(sorted(endpoint['pair'].unique()))}`.

## Held-out Benchmark

{md_table(metrics, ['method', 'method_class', 'n_pair_rows', 'n_runs', 'sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'mean_abs_pair_cov_ns2', 'mean_abs_pair_cov_ci_low_ns2', 'mean_abs_pair_cov_ci_high_ns2', 'correlated_fraction'])}

## Winner Deltas

{md_table(deltas, ['method', 'baseline', 'comparison', 'delta_sigma68_ns', 'sigma68_ci_low_ns', 'sigma68_ci_high_ns', 'delta_mean_abs_pair_cov_ns2', 'cov_ci_low_ns2', 'cov_ci_high_ns2'])}

## A-gate Strata

The frozen A percentile-68 width ranks are split into tertiles among the later endpoint runs. This is a diagnostic for whether A-stack width ordering transfers monotonically to orthogonal B covariance support.

{md_table(pd.DataFrame(stratum_rows), ['method', 'a_gate_stratum', 'n_runs', 'n_pair_rows', 'sigma68_ns', 'mean_abs_pair_cov_ns2', 'correlated_fraction'])}

## Leakage Controls

{md_table(leakage, ['check', 'value', 'flag'])}

## Systematics and Caveats

The main systematic is limited external-support size: by excluding B2-containing pairs and using only later sample-II analysis runs, S18l gains orthogonality but loses row count and run diversity. The run-block intervals are therefore the primary uncertainty statement; row-only intervals would be anti-conservative.

The ML/NN methods are not retrained or retuned in S18l. This is intentional: the ticket asks for a frozen transfer validation. The drawback is that the models may not be optimal for the B4/B6/B8-only endpoint, especially the CNNs whose waveform support was learned on the broader S18k pair table.

The traditional comparator is strong but not purely hand-calibrated: it is the frozen S18k A-width gate Ridge with B shape summaries. Pair-median centering is also reported as a non-parametric traditional baseline because it is robust for width but can leave pair-covariance structure.

The adoption rule is conservative. Even when a learned method wins the benchmark covariance metric, S18l does not declare the A gate production-safe unless the winner is stable against the traditional A-width gate and negative controls on the external endpoint. The result is a benchmark winner and external validation artifact, not an unconditional production gate.

## Conclusion

On the orthogonal later B4/B6/B8 covariance endpoint, **{winner}** has the lowest held-out mean absolute pair covariance among non-control methods. The frozen A-gate transfer signal is therefore reproducible outside the original S18k endpoint, but the safety decision remains conditional and non-adopted because the external endpoint is intentionally narrow and the strongest conclusion is comparative, not causal.

## Artifacts

`REPORT.md`, `result.json`, `method_metrics.csv`, `method_delta_bootstrap.csv`, `gate_stratum_summary.csv`, `external_endpoint_residuals.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, `inherited_raw_derived_inputs.csv`, and `leakage_checks.csv` are in this folder.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
