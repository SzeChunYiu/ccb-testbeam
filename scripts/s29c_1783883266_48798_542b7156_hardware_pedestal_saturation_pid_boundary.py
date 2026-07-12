#!/usr/bin/env python3
"""S29c hardware pedestal/saturation validation with PID-boundary labels.

This ticket-local runner reuses the most complete audited benchmark chain in
the repository: raw B-stack ROOT reproduction, raw-template/digitized GEANT4
truth alignment, a strong traditional DeltaE/E template likelihood, ridge,
gradient-boosted trees, MLP, 1D-CNN, a joint sequence transformer, and the
S29b physics-residual boosted stack.  The ticket-specific layer asks whether
the S29b winner remains safe when judged on hardware-like pedestal/saturation
metadata and an explicit downstream PID-boundary label rather than only the
older amplitude-ceiling and stave proxy strata.
"""

from __future__ import annotations

import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s31b_1783882773_37962_04e64694_causal_pretrigger_pedestal_intervention_bakeoff as base  # noqa: E402


TICKET = "1783883266.48798.542b7156"
WORKER = "testbeam-laptop-2"
SLUG = "s29c_hardware_pedestal_saturation_pid_boundary"
TITLE = "S29c hardware pedestal-saturation validation with PID-boundary labels"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
COMMAND = (
    "/home/billy/anaconda3/bin/python "
    "scripts/s29c_1783883266_48798_542b7156_hardware_pedestal_saturation_pid_boundary.py"
)
S29B_REFERENCE = ROOT / "reports/1783826036.4863.57d51ec8__s29b_saturation_pedestal_energy_recovery_frontier/result.json"


def patch_base() -> None:
    base.TICKET = TICKET
    base.WORKER = WORKER
    base.SLUG = SLUG
    base.TITLE = TITLE
    base.OUT = OUT
    base.COMMAND = COMMAND


def fmt(value: object) -> str:
    try:
        y = float(value)
    except Exception:
        return str(value)
    return f"{y:.4g}" if np.isfinite(y) else "nan"


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def sigma68(x: pd.Series | np.ndarray) -> float:
    arr = np.asarray(x, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float((np.percentile(arr, 84) - np.percentile(arr, 16)) / 2.0)


def pid_boundary_coordinate(events: pd.DataFrame) -> tuple[pd.Series, float]:
    """Deterministic downstream PID coordinate used to define the boundary band.

    The coordinate is intentionally fixed from event truth/meta quantities, not
    from any method prediction.  It mimics the charge-depth PID style used in
    downstream studies: high dE/dx, compact pulse shape, and shallow stopping
    depth move the event toward the deuteron-like side.
    """

    coord = (
        np.log1p(events["dedx_proxy"].astype(float))
        + 0.035 * events["shape_area_over_amp"].astype(float)
        - 0.18 * events["depth_index"].astype(float)
    )
    train = events[events["split"] == "train"].copy()
    train_coord = coord.loc[train.index]
    y = train["pid_label"].astype(int)
    if (y == 0).any() and (y == 1).any():
        threshold = 0.5 * (float(train_coord[y == 0].median()) + float(train_coord[y == 1].median()))
    else:
        threshold = float(train_coord.median())
    return coord, threshold


def boundary_and_hardware_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = pd.read_csv(OUT / "event_predictions.csv")
    held = events[events["split"] == "heldout"].copy()
    coord, threshold = pid_boundary_coordinate(events)
    events["pid_boundary_coordinate"] = coord
    events["pid_boundary_distance"] = (coord - threshold).abs()
    boundary_cut = float(events.loc[events["split"] == "heldout", "pid_boundary_distance"].quantile(0.40))
    events["pid_boundary_label"] = np.where(
        events["pid_boundary_distance"] <= boundary_cut,
        "near_boundary",
        "off_boundary",
    )
    events.to_csv(OUT / "event_predictions_with_hardware_labels.csv", index=False)

    held = events[events["split"] == "heldout"].copy()
    held["hardware_saturation_label"] = np.where(
        held["truth_saturation_label"].astype(int) == 1,
        "hardware_saturated",
        "hardware_unsaturated",
    )
    held["hardware_pedestal_band"] = pd.qcut(
        held["truth_pedestal_adc"].rank(method="first"),
        3,
        labels=["low_pedestal", "mid_pedestal", "high_pedestal"],
    )
    held["pid_boundary_truth"] = np.where(held["pid_label"].astype(int) == 1, "deuteron_like", "proton_like")

    rows = []
    for axis in ["hardware_saturation_label", "hardware_pedestal_band", "pid_boundary_label", "pid_boundary_truth"]:
        for (method, value), group in held.groupby(["method", axis], observed=False):
            pos = group[group["is_overlap"].astype(int) == 1].copy()
            true_e = np.maximum(pos["true_energy_proxy_adc"].astype(float), 1.0)
            pred_e = pos["amp1_adc"].astype(float) + pos["amp2_adc"].astype(float)
            e_resid = (pred_e - true_e) / true_e
            y = group["pid_label"].astype(int).to_numpy()
            yhat = (group["pid_score"].astype(float).to_numpy() >= 0.5).astype(int)
            bacc_parts = [np.mean(yhat[y == lab] == lab) for lab in [0, 1] if np.any(y == lab)]
            overlap = group["is_overlap"].astype(int).to_numpy()
            pred_overlap = (group["score"].astype(float).to_numpy() >= 0.5).astype(int)
            rows.append(
                {
                    "axis": axis,
                    "value": str(value),
                    "method": method,
                    "n": int(len(group)),
                    "energy_bias_frac": float(np.nanmedian(e_resid)) if len(e_resid) else np.nan,
                    "energy_sigma68_frac": sigma68(e_resid),
                    "time_sigma68_ns": sigma68(10.0 * (pos["t1_sample"].astype(float) - pos["true_t1_sample"].astype(float))),
                    "pid_balanced_accuracy": float(np.mean(bacc_parts)) if bacc_parts else np.nan,
                    "pileup_miss_rate": float(np.mean(pred_overlap[overlap == 1] == 0)) if np.any(overlap == 1) else np.nan,
                    "false_split_rate": float(np.mean(pred_overlap[overlap == 0] == 1)) if np.any(overlap == 0) else np.nan,
                }
            )
    sidebands = pd.DataFrame(rows).sort_values(["axis", "value", "method"])
    sidebands.to_csv(OUT / "hardware_pid_boundary_sidebands.csv", index=False)

    metrics = pd.read_csv(OUT / "winner_ranked_metrics.csv")
    focus_methods = [
        "deltaE_over_E_likelihood_template",
        "gradient_boosted_trees",
        "template_residual_boosted_stack_new",
        "ridge",
        "mlp",
        "1d_cnn",
        "joint_sequence_transformer",
    ]
    ranked_focus = metrics[metrics["method"].isin(focus_methods)].copy()
    ranked_focus.to_csv(OUT / "s29b_winner_validation_summary.csv", index=False)

    near = sidebands[(sidebands["axis"] == "pid_boundary_label") & (sidebands["value"] == "near_boundary")]
    sat = sidebands[(sidebands["axis"] == "hardware_saturation_label") & (sidebands["value"] == "hardware_saturated")]
    ped = sidebands[(sidebands["axis"] == "hardware_pedestal_band") & (sidebands["value"] == "high_pedestal")]
    safety_rows = []
    for method in focus_methods:
        row = {"method": method}
        for prefix, frame in [("pid_boundary", near), ("hardware_saturated", sat), ("high_pedestal", ped)]:
            sub = frame[frame["method"] == method]
            if len(sub):
                first = sub.iloc[0]
                row[f"{prefix}_energy_sigma68_frac"] = float(first["energy_sigma68_frac"])
                row[f"{prefix}_pid_balanced_accuracy"] = float(first["pid_balanced_accuracy"])
                row[f"{prefix}_pileup_miss_rate"] = float(first["pileup_miss_rate"])
        safety_rows.append(row)
    safety = pd.DataFrame(safety_rows)
    safety.to_csv(OUT / "hardware_safety_panel.csv", index=False)

    reproduction = pd.read_csv(OUT / "reproduction_match_table.csv")
    return sidebands, ranked_focus, safety, reproduction


def rewrite_s29c_report(started: float) -> None:
    sidebands, ranked, safety, reproduction = boundary_and_hardware_tables()
    run_metrics = pd.read_csv(OUT / "run_heldout_metrics.csv")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    s29b = json.loads(S29B_REFERENCE.read_text(encoding="utf-8"))
    winner = str(result["winner"]["name"])
    s29b_winner = s29b["winner"]["name"]
    best = ranked.sort_values("winner_score").iloc[0]
    trad = ranked[ranked["method"] == "deltaE_over_E_likelihood_template"].iloc[0]
    residual = ranked[ranked["method"] == "template_residual_boosted_stack_new"].iloc[0]

    report = f"""# S29c: hardware pedestal-saturation validation with PID-boundary labels

## Abstract

Ticket `{TICKET}` asks whether the controlled-injection S29b gain survives a
more hardware-facing validation: saturation/pedestal metadata and an explicit
downstream PID-boundary label replace the older amplitude-ceiling and stave-only
proxies.  The worker was `{WORKER}`.  The study first reproduces the canonical
B-stack selected-pulse number directly from raw ROOT, then benchmarks a strong
traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN,
`joint_sequence_transformer`, and the S29b new architecture
`template_residual_boosted_stack_new` under a run-heldout split with bootstrap
confidence intervals.

The raw selected-pulse anchor is `{int(reproduction.iloc[0]['reproduced'])}`
selected B-stave pulses versus reference `{int(reproduction.iloc[0]['report_value'])}`,
delta `{int(reproduction.iloc[0]['delta'])}`.  The S29b reference winner was
`{s29b_winner}` with energy sigma68 `{fmt(s29b['winner']['energy_fractional_sigma68'])}`.
In this hardware/PID-boundary validation, `result.json` names **`{winner}`** as
the winner by the predeclared joint held-out score.  The S29b residual-stack
candidate remains explicitly scored in the safety tables; its global score is
`{fmt(residual['winner_score'])}`.

## Raw ROOT reproduction

The reproduction gate reads `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`.
For each `h101/HRDv` trace with samples `x_c(t)`, the pretrigger baseline is

`b_c = median[x_c(0), x_c(1), x_c(2), x_c(3)]`,

and the selected-pulse indicator is

`I_i = 1[max_{{c in B2,B4,B6,B8,t}} (x_ic(t)-b_ic) > 1000 ADC]`.

No model fit starts until this raw count agrees with the reference:

{md_table(reproduction, ['quantity', 'report_value', 'reproduced', 'delta', 'pass'])}

## Estimands and labels

For event `i`, the benchmark waveform is a raw-template/digitized truth hybrid

`w_i(t) = p_i + A_i T_s(t-t_i) + A'_i T_s(t-t_i-Delta_i) + epsilon_{{r,s}}(t)`,

where `epsilon_{{r,s}}` is sampled from raw ROOT residual pools by source run and
stave.  GEANT4 supplies event-level PID, energy, and timing truth; the raw B-stack
templates and residuals supply detector-like morphology.  The primary residuals are

`e_E = (hat A_1 + hat A_2 - E_i) / E_i`,

`e_t = 10 ns (hat t_1 - t_i)`,

with robust scale

`sigma_68(e) = [Q_84(e)-Q_16(e)]/2`.

Hardware-facing metadata are represented by two explicit labels retained in the
event table: `truth_saturation_label`, the digitized waveform saturation-onset
indicator, and `truth_pedestal_adc`, the raw pretrigger pedestal.  The downstream
PID-boundary label is deterministic and event-level.  Define

`z_i = log(1 + dE/dx_i) + 0.035 area_over_amp_i - 0.18 depth_i`.

The threshold is the midpoint between the train-run proton-like and deuteron-like
class medians.  Held-out events in the lowest 40% of `|z_i-z_0|` are labeled
`near_boundary`; the others are `off_boundary`.  This boundary label is fixed
before scoring any method prediction.

## Split, bootstrap, and winner rule

The split is by complete source run: train runs
`{result['evaluation_design']['train_runs']}` and held-out runs
`{result['evaluation_design']['heldout_runs']}`.  Confidence intervals are
95% percentile intervals from `{result['evaluation_design']['bootstrap_replicates']}`
held-out run-block bootstrap resamples.  The winner score is

`C_m = sigma_E,m + 0.01 sigma_t,m + 0.25(1-BAcc_PID,m) + 0.05 r_miss,m + 0.05 r_false,m`.

## Methods

The strong traditional baseline is `deltaE_over_E_likelihood_template`: a
pretrigger-subtracted CFD/template two-pulse fit plus a diagonal DeltaE/E PID
likelihood.  With standardized features `z_j`,

`log p(z | y) = -1/2 sum_j [(z_j-mu_yj)^2 / sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel includes ridge, histogram gradient-boosted trees, MLP, 1D-CNN,
and `joint_sequence_transformer`.  The new S29b architecture is
`template_residual_boosted_stack_new`, which feeds traditional fit estimates and
waveform residual coordinates into boosted residual heads.  This is the sensible
new architecture for this ticket because saturation recovery is partially
physics-constrained: a template fit supplies low-variance amplitude/timing
coordinates, while residual learners can correct clipped-tail curvature,
pedestal drift, and overlap failure modes.

## Global held-out results

{md_table(ranked, ['method', 'winner_score', 'pid_auc', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'energy_fractional_sigma68_ci_low', 'energy_fractional_sigma68_ci_high', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate'])}

Relative to the traditional method, `{winner}` changes energy sigma68 by
`{fmt(best['energy_fractional_sigma68'] - trad['energy_fractional_sigma68'])}`,
timing sigma68 by `{fmt(best['time_sigma68_ns'] - trad['time_sigma68_ns'])}` ns,
and PID balanced accuracy by `{fmt(best['pid_balanced_accuracy'] - trad['pid_balanced_accuracy'])}`.

## Run-heldout stability

{md_table(run_metrics, ['method', 'heldout_run', 'pid_balanced_accuracy', 'pid_efficiency', 'pid_purity', 'energy_fractional_sigma68', 'time_sigma68_ns', 'pileup_miss_rate', 'false_split_rate'])}

## Hardware and PID-boundary sidebands

The sideband table is the core S29c validation artifact.  It scores every method
inside hardware saturation, pedestal, explicit near-boundary/off-boundary, and
true proton/deuteron-like slices.  The same held-out predictions are used; only
the aggregation subset changes.

{md_table(sidebands, ['axis', 'value', 'method', 'n', 'energy_bias_frac', 'energy_sigma68_frac', 'time_sigma68_ns', 'pid_balanced_accuracy', 'pileup_miss_rate', 'false_split_rate'])}

## S29b winner safety panel

The table below isolates the S29b winner candidate and its main competitors on
the three validation slices that matter most for this ticket: near PID boundary,
hardware-saturated, and high-pedestal held-out events.

{md_table(safety, ['method', 'pid_boundary_energy_sigma68_frac', 'pid_boundary_pid_balanced_accuracy', 'pid_boundary_pileup_miss_rate', 'hardware_saturated_energy_sigma68_frac', 'hardware_saturated_pid_balanced_accuracy', 'high_pedestal_energy_sigma68_frac', 'high_pedestal_pid_balanced_accuracy'])}

## Systematics and caveats

1. The raw count is reproduced from real ROOT data, but the supervised endpoint is
   a raw-template/digitized GEANT4 benchmark, not an online electronics truth
   stream.
2. `truth_saturation_label` and `truth_pedestal_adc` are hardware-like metadata
   derived from digitized raw morphology; the ROOT tree itself has no separate
   saturation flag branch.
3. The PID-boundary label is explicit and event-level, but it is a deterministic
   downstream decision coordinate rather than an externally hand-labeled particle
   boundary.
4. Bootstrap intervals quantify held-out run transfer for the fixed model panel;
   they do not include GEANT4 physics-list, material-budget, ADC/MeV, or future
   beam-current uncertainty.
5. The S29b residual-stack result should be read as a validation candidate.  It
   does not automatically replace the traditional method where interpretability
   or monotonic calibration is more important than the composite score.

## Conclusion

The controlled-injection S29b winner `{s29b_winner}` is not blindly promoted by
this ticket.  It is re-scored under hardware saturation, high-pedestal, and
explicit PID-boundary labels alongside the full required method panel.  The
winner named in `result.json` is `{winner}`; the safety panel shows where the
S29b residual-stack candidate does and does not survive the stricter validation.

Runtime was `{time.time() - started:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(report, encoding="utf-8")

    result.update(
        {
            "ticket_id": TICKET,
            "worker": WORKER,
            "title": TITLE,
            "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
            "execution_command": COMMAND,
            "ticket_scope": "hardware pedestal-saturation validation with explicit PID-boundary labels",
            "s29b_reference": {
                "path": str(S29B_REFERENCE.relative_to(ROOT)),
                "winner": s29b_winner,
                "winner_energy_fractional_sigma68": s29b["winner"]["energy_fractional_sigma68"],
            },
            "hardware_validation_labels": {
                "saturation": "truth_saturation_label from digitized waveform saturation onset",
                "pedestal": "truth_pedestal_adc tertiles",
                "pid_boundary": "near_boundary if held-out event is in the lowest 40 percent of distance to the train-defined PID coordinate threshold",
                "evidence_table": "event_predictions_with_hardware_labels.csv",
            },
            "required_method_coverage": {
                "strong_traditional": "deltaE_over_E_likelihood_template",
                "ridge": "ridge",
                "gradient_boosted_trees": "gradient_boosted_trees",
                "mlp": "mlp",
                "one_dimensional_cnn": "1d_cnn",
                "new_architecture": "joint_sequence_transformer",
                "s29b_new_architecture": "template_residual_boosted_stack_new",
            },
            "artifacts": {
                **result["artifacts"],
                "event_predictions_with_hardware_labels": "event_predictions_with_hardware_labels.csv",
                "hardware_pid_boundary_sidebands": "hardware_pid_boundary_sidebands.csv",
                "s29b_winner_validation_summary": "s29b_winner_validation_summary.csv",
                "hardware_safety_panel": "hardware_safety_panel.csv",
            },
            "novel_tickets_appended": [],
            "completion_audit": {
                "claimed_ticket": TICKET,
                "claimed_once": True,
                "raw_root_reproduced": bool(result["raw_root_reproduction"]["passed"]),
                "required_methods_present": [
                    "deltaE_over_E_likelihood_template",
                    "ridge",
                    "gradient_boosted_trees",
                    "mlp",
                    "1d_cnn",
                    "joint_sequence_transformer",
                    "template_residual_boosted_stack_new",
                ],
                "winner_named": result["winner"]["name"],
                "run_bootstrap_cis_reported": True,
                "hardware_saturation_pedestal_reported": True,
                "explicit_pid_boundary_label_reported": True,
                "s29b_winner_safety_panel_reported": True,
                "novel_tickets_appended": [],
            },
        }
    )
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["title"] = TITLE
    manifest["worker"] = WORKER
    manifest["command"] = COMMAND
    manifest["outputs_sha256"] = {
        p.name: base.impl.sha256(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = time.time()
    patch_base()
    base.main()
    rewrite_s29c_report(started)


if __name__ == "__main__":
    main()
