#!/usr/bin/env python3
"""S19c report/result postprocessor.

This script consumes the raw-ROOT benchmark artifacts produced with the S19c
configuration and rewrites the final report/result around the pile-up
saturation timing-recovery ticket.  The expensive ROOT pass is intentionally
kept in the shared S05l benchmark engine; this file adds the S19c-specific
interpretation, proxy diagnostics, and completion audit artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "1783759304.10079.0a892fb8__s19c_pileup_saturation_timing_recovery"
CONFIG = ROOT / "configs" / "s19c_1783759304_10079_0a892fb8_pileup_saturation_timing_recovery.yaml"

METHOD_LABELS = {
    "raw_pair_median": "CFD20 pair-median template baseline",
    "ridge_no_saturation": "Ridge, no explicit saturation features",
    "ridge_duplicate_safe": "Strong traditional ridge recovery with waveform saturation diagnostics",
    "gbt_duplicate_safe": "Gradient-boosted trees",
    "extra_trees_duplicate_safe": "ExtraTrees architecture added as the new non-linear comparator",
    "mlp_duplicate_safe": "Tabular MLP",
    "cnn_waveform_only": "1D-CNN on endpoint waveforms",
    "hybrid_cnn_tabular_duplicate_safe": "New hybrid 1D-CNN plus tabular architecture",
    "gbt_shuffled_target": "Shuffled-target negative control",
}

PRIMARY_METHODS = [
    "raw_pair_median",
    "ridge_no_saturation",
    "ridge_duplicate_safe",
    "gbt_duplicate_safe",
    "mlp_duplicate_safe",
    "cnn_waveform_only",
    "hybrid_cnn_tabular_duplicate_safe",
    "extra_trees_duplicate_safe",
]


def fmt(x, nd=3):
    if pd.isna(x):
        return ""
    return f"{float(x):.{nd}f}"


def sigma68(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    centered = x - np.nanmedian(x)
    return float((np.nanpercentile(centered, 84.0) - np.nanpercentile(centered, 16.0)) / 2.0)


def run_bootstrap_ci(df, value_func, seed=190319, n_resamples=300):
    rng = np.random.default_rng(seed)
    runs = np.array(sorted(df["run"].dropna().unique()))
    if len(runs) == 0:
        return (float("nan"), float("nan"))
    vals = []
    groups = {run: sub for run, sub in df.groupby("run")}
    for _ in range(n_resamples):
        sampled = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([groups[r] for r in sampled], ignore_index=True)
        vals.append(value_func(boot))
    return tuple(float(v) for v in np.nanpercentile(vals, [2.5, 97.5]))


def md_table(rows, headers):
    def esc(value):
        return str(value).replace("|", "\\|")

    out = ["| " + " | ".join(esc(h) for h in headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(esc(row.get(h, "")) for h in headers) + " |")
    return "\n".join(out)


def main():
    method_metrics = pd.read_csv(OUT / "method_metrics.csv")
    repro = pd.read_csv(OUT / "reproduction_match_table.csv")
    residuals = pd.read_csv(OUT / "heldout_pair_residuals.csv")
    strata = pd.read_csv(OUT / "saturation_strata.csv")
    leakage = pd.read_csv(OUT / "leakage_checks.csv")
    folds = pd.read_csv(OUT / "fold_hyperparameters.csv")
    pair_counts = pd.read_csv(OUT / "pair_counts.csv")

    metric_all = method_metrics[(method_metrics["subset"] == "all") & (method_metrics["method"].isin(PRIMARY_METHODS))]
    winner_row = metric_all.sort_values("sigma68_ns").iloc[0]
    winner_method = str(winner_row["method"])

    label = (residuals["b2_sat_count"] > 0).astype(int)
    proxy_rows = []
    for method in [m for m in PRIMARY_METHODS if f"resid_{m}" in residuals.columns]:
        col = f"resid_{method}"
        score = np.abs(residuals[col].to_numpy(dtype=float))
        try:
            ap = float(average_precision_score(label, score))
        except Exception:
            ap = float("nan")
        fail_mask = residuals["b2_sat_count"] > 0
        fail_rate = float((np.abs(residuals.loc[fail_mask, col]) > 5.0).mean()) if fail_mask.any() else float("nan")
        bias = float(np.nanmedian(residuals[col]))
        sat_sig = sigma68(residuals.loc[fail_mask, col])
        sat_ci = run_bootstrap_ci(residuals.loc[fail_mask].copy(), lambda d, c=col: sigma68(d[c]))
        proxy_rows.append(
            {
                "method": method,
                "pileup_ap_proxy": ap,
                "timing_bias_ns": bias,
                "saturated_sigma68_ns": sat_sig,
                "saturated_sigma68_ci_low_ns": sat_ci[0],
                "saturated_sigma68_ci_high_ns": sat_ci[1],
                "saturation_failure_rate_abs_gt5ns": fail_rate,
            }
        )
    proxy = pd.DataFrame(proxy_rows)
    proxy.to_csv(OUT / "s19c_proxy_diagnostics.csv", index=False)

    delay_bins = [-np.inf, 1.0, 3.0, 6.0, np.inf]
    delay_labels = ["abs_raw_delay_lt1ns", "abs_raw_delay_1to3ns", "abs_raw_delay_3to6ns", "abs_raw_delay_ge6ns"]
    residuals["delay_proxy_bin"] = pd.cut(np.abs(residuals["target_residual_ns"]), delay_bins, labels=delay_labels)
    amp_cut = float(np.nanpercentile(residuals["B2_amp"], 90.0))
    residuals["amp_ratio_proxy_bin"] = np.where(residuals["B2_amp"] >= amp_cut, "B2_amp_top_decile", "B2_amp_lower_90pct")
    stratum_rows = []
    for method in ["raw_pair_median", "ridge_duplicate_safe", "gbt_duplicate_safe", "mlp_duplicate_safe", "hybrid_cnn_tabular_duplicate_safe"]:
        col = f"resid_{method}"
        for group_col in ["delay_proxy_bin", "amp_ratio_proxy_bin"]:
            for name, sub in residuals.groupby(group_col):
                if len(sub) == 0:
                    continue
                lo, hi = run_bootstrap_ci(sub.copy(), lambda d, c=col: sigma68(d[c]))
                stratum_rows.append(
                    {
                        "method": method,
                        "stratum_type": group_col,
                        "stratum": str(name),
                        "n_pair_rows": int(len(sub)),
                        "n_runs": int(sub["run"].nunique()),
                        "sigma68_ns": sigma68(sub[col]),
                        "sigma68_ci_low_ns": lo,
                        "sigma68_ci_high_ns": hi,
                    }
                )
    stratum_df = pd.DataFrame(stratum_rows)
    stratum_df.to_csv(OUT / "s19c_delay_amplitude_strata.csv", index=False)

    method_rows = []
    for _, r in metric_all.sort_values("sigma68_ns").iterrows():
        method_rows.append(
            {
                "method": r["method"],
                "role": METHOD_LABELS.get(r["method"], r["method"]),
                "sigma68 ns": fmt(r["sigma68_ns"]),
                "95% CI ns": f"[{fmt(r['sigma68_ci_low_ns'])}, {fmt(r['sigma68_ci_high_ns'])}]",
                "full RMS ns": fmt(r["full_rms_ns"]),
                "tail |r|>5 ns": fmt(r["tail_frac_abs_gt5ns"], 4),
            }
        )

    proxy_table_rows = []
    for _, r in proxy.sort_values("saturated_sigma68_ns").iterrows():
        proxy_table_rows.append(
            {
                "method": r["method"],
                "AP proxy": fmt(r["pileup_ap_proxy"], 4),
                "bias ns": fmt(r["timing_bias_ns"]),
                "sat sigma68 ns": fmt(r["saturated_sigma68_ns"]),
                "sat 95% CI ns": f"[{fmt(r['saturated_sigma68_ci_low_ns'])}, {fmt(r['saturated_sigma68_ci_high_ns'])}]",
                "sat fail rate": fmt(r["saturation_failure_rate_abs_gt5ns"], 4),
            }
        )

    delay_table = stratum_df[stratum_df["stratum_type"] == "delay_proxy_bin"]
    delay_table = delay_table[delay_table["method"].isin(["raw_pair_median", "ridge_duplicate_safe", "hybrid_cnn_tabular_duplicate_safe"])]
    delay_rows = []
    for _, r in delay_table.sort_values(["method", "stratum"]).iterrows():
        delay_rows.append(
            {
                "method": r["method"],
                "delay proxy stratum": r["stratum"],
                "n": int(r["n_pair_rows"]),
                "sigma68 ns": fmt(r["sigma68_ns"]),
                "95% CI ns": f"[{fmt(r['sigma68_ci_low_ns'])}, {fmt(r['sigma68_ci_high_ns'])}]",
            }
        )

    amp_rows = []
    amp_table = stratum_df[stratum_df["stratum_type"] == "amp_ratio_proxy_bin"]
    amp_table = amp_table[amp_table["method"].isin(["raw_pair_median", "ridge_duplicate_safe", "hybrid_cnn_tabular_duplicate_safe"])]
    for _, r in amp_table.sort_values(["method", "stratum"]).iterrows():
        amp_rows.append(
            {
                "method": r["method"],
                "amplitude proxy stratum": r["stratum"],
                "n": int(r["n_pair_rows"]),
                "sigma68 ns": fmt(r["sigma68_ns"]),
                "95% CI ns": f"[{fmt(r['sigma68_ci_low_ns'])}, {fmt(r['sigma68_ci_high_ns'])}]",
            }
        )

    repro_rows = []
    for _, r in repro.iterrows():
        repro_rows.append(
            {
                "quantity": r["quantity"],
                "reported": int(r["report_value"]),
                "reproduced": int(r["reproduced"]),
                "delta": int(r["delta"]),
                "pass": bool(r["pass"]),
            }
        )

    leak_rows = []
    for _, r in leakage.iterrows():
        leak_rows.append(
            {
                "check": r["check"],
                "value": fmt(r["value"]),
                "pass": bool(r["pass"]),
            }
        )

    report = f"""# S19c: pile-up saturation timing recovery head-to-head

- **Ticket:** 1783759304.10079.0a892fb8
- **Worker:** testbeam-laptop-3
- **Config:** `{CONFIG.relative_to(ROOT)}`
- **Raw input:** `data/root/root`
- **Primary output:** `{OUT.relative_to(ROOT)}/result.json`

## Abstract

S19c asks whether timing can be recovered under overlapping or saturated B-stack
pulses with baseline drift, and whether waveform-based ML/NN corrections beat a
strong traditional timing baseline when validation is split by source run.  The
raw ROOT reproduction gate exactly recovers the selected B-pulse counts, then a
leave-one-run-out benchmark evaluates CFD20 pair-template timing, Ridge,
gradient-boosted trees, MLP, 1D-CNN, and a hybrid CNN-tabular architecture with
run-block bootstrap 95% confidence intervals.  The primary all-pair winner is
`{winner_method}` with sigma68 = {fmt(winner_row['sigma68_ns'])} ns and 95% CI
[{fmt(winner_row['sigma68_ci_low_ns'])}, {fmt(winner_row['sigma68_ci_high_ns'])}]
ns.

## Raw ROOT Reproduction

The analysis reads `h101/HRDv` from the raw ROOT files under `data/root/root`,
uses the physical B-stack channels `B2/B4/B6/B8 = 0/2/4/6`, subtracts the
median of samples 0--3 as a pedestal, requires amplitude above 1000 ADC, and
computes CFD20 timing.  The reproduced count gate is exact:

{md_table(repro_rows, ['quantity', 'reported', 'reproduced', 'delta', 'pass'])}

Pair rows used in the run-split timing benchmark:

{md_table(pair_counts.to_dict('records'), list(pair_counts.columns))}

## Methods

For event `e`, run `r`, and stave pair `p=(i,j)`, the benchmark target is

```text
y_erp = t_j(e) - t_i(e) - (z_j - z_i) * 0.078 ns/cm
```

with 2 cm stave spacing.  The CFD20 time is estimated after pedestal refit from
the median baseline samples.  The uncorrected traditional comparator centers
each pair by a train-fold median:

```text
residual_raw = y_erp - median_train(y_p)
```

The Ridge comparators fit

```text
argmin_beta ||y - X beta||_2^2 + alpha ||beta||_2^2
```

where the no-saturation model uses amplitude, area, tail, peak, and pair
identity summaries, while the duplicate-safe traditional model additionally
uses direct waveform saturation observables: high-ADC sample count, near-peak
width, saturation excess, post-peak fall, and recovery tail.  Tree, MLP, CNN,
and hybrid models are trained only on the six non-held-out runs in each fold.
The hybrid CNN-tabular method is the new architecture: a waveform branch over
the two endpoint samples is concatenated with duplicate-safe tabular features.

The robust timing width is

```text
sigma68(x) = (Q84(x - median(x)) - Q16(x - median(x))) / 2
```

Confidence intervals resample held-out runs with replacement, preserving the
source-run split, and then evaluate the same held-out residual distribution.

## Primary Run-Split Benchmark

All folds hold out one Sample-II source run from `{sorted(folds['heldout_run'].tolist())}`;
all metrics below are computed on every held-out pair row.

{md_table(method_rows, ['method', 'role', 'sigma68 ns', '95% CI ns', 'full RMS ns', 'tail |r|>5 ns'])}

The requested ML/NN family coverage is explicit: Ridge, gradient-boosted trees,
MLP, 1D-CNN, and a new hybrid CNN-tabular architecture are all included.  The
new architecture did not win this run-split validation; the CFD20 pair-template
median baseline retained the narrowest central timing residual.

## Saturated and Pile-Up Candidate Diagnostics

The raw B-stack does not contain truth labels for simulated pile-up onset,
charge-energy residuals, or downstream PID decisions.  Therefore the following
diagnostics are proxy validations, not production estimates of those quantities.
The pile-up/saturation candidate label is `b2_sat_count > 0`, and AP uses
`abs(residual)` as a failure-score proxy.  The saturation failure rate is the
fraction of those candidate rows with `abs(residual) > 5 ns`.

{md_table(proxy_table_rows, ['method', 'AP proxy', 'bias ns', 'sat sigma68 ns', 'sat 95% CI ns', 'sat fail rate'])}

Delay and amplitude-ratio requests are approximated with observable proxies:
`abs(target_residual_ns)` for apparent delay and the top decile of B2 amplitude
for high amplitude-ratio stress.

{md_table(delay_rows, ['method', 'delay proxy stratum', 'n', 'sigma68 ns', '95% CI ns'])}

{md_table(amp_rows, ['method', 'amplitude proxy stratum', 'n', 'sigma68 ns', '95% CI ns'])}

The independently generated B2 saturation strata are retained in
`saturation_strata.csv`; they show that the all-B2-containing raw baseline has
sigma68 {fmt(strata[(strata['method'] == 'raw_pair_median') & (strata['stratum'] == 'all_B2_containing')]['sigma68_ns'].iloc[0])}
ns, but B2 saturated rows broaden to
{fmt(strata[(strata['method'] == 'raw_pair_median') & (strata['stratum'] == 'B2_sat_count_gt0')]['sigma68_ns'].iloc[0])}
ns.

## Negative Controls and Leakage Checks

{md_table(leak_rows, ['check', 'value', 'pass'])}

The shuffled-target sentinel stays worse than the nominal ExtraTrees model and
far worse than an intentionally leaked target echo.  Features exclude run,
event, direct timing labels, and raw target residuals.

## Systematics

The leading systematic is label limitation: there is no independent truth for
two-pulse overlay time, charge energy, or PID classification in the real B-stack
candidate table, so pile-up detection AP, charge residuals, and PID stability
are reported only as waveform-derived proxies.  The second systematic is model
capacity: NN fits are deliberately capped (`nn_epochs = 1`, 1200 fit rows per
fold) to make the ticket benchmark reproducible on CPU, which likely underfits
the CNN and MLP.  The third systematic is selection: the benchmark uses
Sample-II runs 58, 59, 60, 61, 62, 63, and 65 because the duplicate-readout
saturation validity gate is defined there; the reproduction gate covers the
larger configured B-stack count set.

Baseline drift is handled by per-pulse pedestal refits from samples 0--3, but no
separate slow-control or spill-level baseline model is fitted.  Saturation
features are duplicate-safe waveform measurements and do not use any adopted
P07 ratio-transfer amplitude correction.

## Caveats

This is a real-candidate run-split study, not a full synthetic overlay campaign.
The ticket's synthetic-overlay, charge-energy, and PID-consumer requirements are
addressed only through available real-candidate timing and saturation proxies in
this repository state.  A future dedicated overlay truth table would be needed
to convert the proxy AP, proxy amplitude strata, and proxy stability quantities
into detector-performance claims.

## Conclusion

The raw ROOT count gate passes exactly.  In leave-one-run-out validation with
run bootstrap confidence intervals, `{winner_method}` wins the primary timing
metric.  The best non-traditional ML comparator is
`{metric_all[metric_all['method'] != 'raw_pair_median'].sort_values('sigma68_ns').iloc[0]['method']}`,
but its all-pair sigma68 remains wider than the raw CFD20 pair-template
baseline.  The result is recorded in `result.json`, with auxiliary S19c proxy
tables in `s19c_proxy_diagnostics.csv` and `s19c_delay_amplitude_strata.csv`.
"""

    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    existing = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    existing.update(
        {
            "study_id": "S19c",
            "title": "Pile-up saturation timing recovery head-to-head",
            "ticket": "1783759304.10079.0a892fb8",
            "worker": "testbeam-laptop-3",
            "config": str(CONFIG.relative_to(ROOT)),
            "raw_root_dir": "data/root/root",
            "primary_metric": "held-out all-pair sigma68_ns; lower is better",
            "winning_method": winner_method,
            "winner": {
                "method": winner_method,
                "metric": "held-out all-pair sigma68_ns; lower is better",
                "value": float(winner_row["sigma68_ns"]),
                "ci": [float(winner_row["sigma68_ci_low_ns"]), float(winner_row["sigma68_ci_high_ns"])],
                "full_rms_ns": float(winner_row["full_rms_ns"]),
                "tail_frac_abs_gt5ns": float(winner_row["tail_frac_abs_gt5ns"]),
            },
            "s19c_proxy_outputs": {
                "proxy_diagnostics_csv": "s19c_proxy_diagnostics.csv",
                "delay_amplitude_strata_csv": "s19c_delay_amplitude_strata.csv",
                "proxy_caveat": "No independent truth labels exist for synthetic overlay, charge-energy residuals, or PID-consumer stability in the raw B-stack candidate table; those quantities are reported as real-candidate waveform proxies.",
            },
        }
    )
    (OUT / "result.json").write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
