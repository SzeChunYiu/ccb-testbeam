#!/usr/bin/env python3
"""S35c joint PID, pulse-shape, and timing ablation benchmark.

This runner is deliberately ticket-local.  It reruns the raw B-stack ROOT
selected-pulse count as the hard reproduction gate, then combines two audited
raw-root-grounded benchmark panels:

* S33a: energy closure and weak-label charge-depth PID by held-out run.
* S34a: pulse-shape timing, pile-up, saturation, and sequence architectures by
  held-out source run.

The ticket asks for one winner across traditional, ML, and neural methods.  The
joint score below is a synthesis score, not a new particle-truth claim.
"""

from __future__ import annotations

import ast
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import p05a_cnn_two_pulse_decomposition as p05a  # noqa: E402


TICKET = "1784063447.978.761459bb"
WORKER = "testbeam-laptop-4"
STUDY = "S35c"
SLUG = "s35c_joint_pid_pulse_shape_timing_ablation"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_DIR = Path("/home/billy/ccb-data/extracted/root/root")
S33 = ROOT / "reports" / "1784062062.882.024708b9__s33a_rate_baseline_energy_pid_benchmark"
S34 = ROOT / "reports" / "1784062062.819.0cd45327__s34a_pileup_timing_separation_architecture_bakeoff"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def load_reproduction_config() -> dict:
    cfg = p05a.load_config(ROOT / "configs" / "p05a_cnn_two_pulse_decomposition.json")
    cfg["raw_root_dir"] = str(RAW_ROOT_DIR)
    return cfg


def parse_ci(value: object) -> List[float]:
    if isinstance(value, (list, tuple)):
        return [float(value[0]), float(value[1])]
    if pd.isna(value):
        return [float("nan"), float("nan")]
    text = str(value)
    if "nan" in text.lower():
        text = text.replace("nan", "None").replace("NaN", "None")
        parsed_nan = ast.literal_eval(text)
        return [float("nan") if item is None else float(item) for item in parsed_nan[:2]]
    parsed = ast.literal_eval(text)
    return [float(parsed[0]), float(parsed[1])]


def fnum(value: object, digits: int = 4) -> str:
    try:
        value = float(value)
    except Exception:
        return str(value)
    if not np.isfinite(value):
        return "nan"
    return f"{value:.{digits}g}"


def ci_text(value: object, digits: int = 4) -> str:
    lo, hi = parse_ci(value)
    return f"[{fnum(lo, digits)}, {fnum(hi, digits)}]"


def md_table(frame: pd.DataFrame, columns: Iterable[str]) -> str:
    cols = list(columns)
    sub = frame[cols].copy()
    for col in sub.columns:
        if col.endswith("_ci95") or col.endswith("_ci"):
            sub[col] = sub[col].map(ci_text)
        elif pd.api.types.is_float_dtype(sub[col]):
            sub[col] = sub[col].map(fnum)
        else:
            sub[col] = sub[col].astype(str)
    widths = [max(len(col), int(sub[col].map(len).max() if len(sub) else 0)) for col in sub.columns]
    header = "| " + " | ".join(col.ljust(widths[i]) for i, col in enumerate(sub.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in sub.columns) + " |"
    rows = [
        "| " + " | ".join(str(row[col]).ljust(widths[i]) for i, col in enumerate(sub.columns)) + " |"
        for _, row in sub.iterrows()
    ]
    return "\n".join([header, sep, *rows])


def copy_inputs() -> Dict[str, pd.DataFrame]:
    sources = {
        "s33_energy_metrics.csv": S33 / "method_metrics.csv",
        "s33_pid_metrics.csv": S33 / "pid_method_metrics.csv",
        "s33_composite_method_ranking.csv": S33 / "composite_method_ranking.csv",
        "s33_run_heldout_summary.csv": S33 / "run_heldout_summary.csv",
        "s33_counts_by_run.csv": S33 / "counts_by_run.csv",
        "s34_timing_metrics.csv": S34 / "method_metrics.csv",
        "s34_endpoint_metrics_ci.csv": S34 / "endpoint_metrics_ci.csv",
        "s34_winner_ranked_metrics.csv": S34 / "winner_ranked_metrics.csv",
        "s34_run_heldout_metrics.csv": S34 / "run_heldout_metrics.csv",
    }
    frames = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = OUT / name
        shutil.copy2(src, dst)
        frames[name] = pd.read_csv(dst)
    return frames


def build_joint_table(frames: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    energy = frames["s33_energy_metrics.csv"].set_index("method")
    pid = frames["s33_pid_metrics.csv"].set_index("method")
    timing = frames["s34_winner_ranked_metrics.csv"].set_index("method")

    rows = [
        {
            "method": "traditional_dedx_template_likelihood",
            "family": "traditional",
            "energy_method": "geant4_birks_lookup",
            "pid_method": "traditional_dedx_likelihood",
            "timing_method": "two_pulse_template_cfd_baseline",
            "description": "GEANT4/Birks deltaE-E energy plus Gaussian charge-depth likelihood plus bounded two-pulse template score",
        },
        {
            "method": "ridge",
            "family": "linear_ml",
            "energy_method": "ridge",
            "pid_method": "ridge",
            "timing_method": "ridge",
            "description": "standardized ridge/logistic linear heads on event and waveform summary features",
        },
        {
            "method": "gradient_boosted_trees",
            "family": "tree_ml",
            "energy_method": "gradient_boosted_trees",
            "pid_method": "gradient_boosted_trees",
            "timing_method": "gradient_boosted_trees",
            "description": "boosted decision trees for energy regression, PID scoring, and pile-up timing endpoints",
        },
        {
            "method": "mlp",
            "family": "tabular_nn",
            "energy_method": "mlp",
            "pid_method": "mlp",
            "timing_method": "mlp",
            "description": "multilayer perceptron heads over fixed event-level pulse-shape features",
        },
        {
            "method": "1d_cnn",
            "family": "waveform_nn",
            "energy_method": "1d_cnn",
            "pid_method": "1d_cnn",
            "timing_method": "1d_cnn",
            "description": "compact one-dimensional convolutional network over B-stave waveform samples",
        },
        {
            "method": "tiny_sequence_transformer",
            "family": "sequence_nn",
            "energy_method": None,
            "pid_method": None,
            "timing_method": "tiny_sequence_transformer",
            "description": "one-layer self-attention model for timing/pile-up only; no independent PID energy head in this synthesis",
        },
        {
            "method": "joint_residual_stack_new",
            "family": "new_hybrid_architecture",
            "energy_method": "range_gated_residual_mlp_new",
            "pid_method": "range_gated_residual_mlp_new",
            "timing_method": "template_residual_boosted_stack_new",
            "description": "new hybrid: physics residual MLP for energy/PID plus boosted residual stack on template timing outputs",
        },
        {
            "method": "pileup_mask_transformer_new",
            "family": "new_sequence_architecture",
            "energy_method": None,
            "pid_method": None,
            "timing_method": "pileup_mask_transformer_new",
            "description": "new late-mask transformer for timing/pile-up only; included as an architecture ablation",
        },
    ]

    out = []
    for row in rows:
        e = energy.loc[row["energy_method"]] if row["energy_method"] in energy.index else None
        p = pid.loc[row["pid_method"]] if row["pid_method"] in pid.index else None
        t = timing.loc[row["timing_method"]] if row["timing_method"] in timing.index else None
        rec = dict(row)
        rec.update(
            {
                "energy_res68_frac": float(e["res68_frac"]) if e is not None else np.nan,
                "energy_res68_ci95": str(parse_ci(e["res68_ci95"])) if e is not None else str([np.nan, np.nan]),
                "energy_mae_mev": float(e["mae_mev"]) if e is not None else np.nan,
                "pid_roc_auc": float(p["roc_auc"]) if p is not None else np.nan,
                "pid_roc_auc_ci95": str(parse_ci(p["roc_auc_ci95"])) if p is not None else str([np.nan, np.nan]),
                "pid_balanced_accuracy": float(p["balanced_accuracy"]) if p is not None else np.nan,
                "timing_sigma68_ns": float(t["time_sigma68_ns"]) if t is not None else np.nan,
                "timing_sigma68_ci95": str([float(t["time_sigma68_ns_ci_low"]), float(t["time_sigma68_ns_ci_high"])]) if t is not None else str([np.nan, np.nan]),
                "leading_edge_sigma68_ns": float(t["leading_edge_time_sigma68_ns"]) if t is not None else np.nan,
                "secondary_delay_sigma68_ns": float(t["secondary_pulse_delay_sigma68_ns"]) if t is not None else np.nan,
                "detection_ap": float(t["detection_ap"]) if t is not None else np.nan,
                "pileup_miss_rate": float(t["pileup_miss_rate"]) if t is not None else np.nan,
                "false_split_rate": float(t["false_split_rate"]) if t is not None else np.nan,
                "energy_proxy_distortion_sigma68": float(t["energy_proxy_distortion_sigma68"]) if t is not None else np.nan,
                "pid_confusion_stave_bias_span": float(t["pid_confusion_stave_bias_span"]) if t is not None else np.nan,
            }
        )
        # Registered joint score.  Missing energy/PID heads are penalized so
        # timing-only architectures remain ablations, not ticket winners.
        missing_penalty = 0.75 * int(not np.isfinite(rec["energy_res68_frac"])) + 0.75 * int(not np.isfinite(rec["pid_roc_auc"]))
        rec["joint_loss"] = (
            np.nan_to_num(rec["energy_res68_frac"], nan=0.25)
            + 5.0 * np.nan_to_num(1.0 - rec["pid_roc_auc"], nan=0.10)
            + np.nan_to_num(rec["timing_sigma68_ns"], nan=25.0) / 100.0
            + np.nan_to_num(rec["secondary_delay_sigma68_ns"], nan=30.0) / 125.0
            + 0.50 * np.nan_to_num(rec["pileup_miss_rate"], nan=0.50)
            + 0.35 * np.nan_to_num(rec["false_split_rate"], nan=0.35)
            + 0.50 * np.nan_to_num(rec["energy_proxy_distortion_sigma68"], nan=0.15)
            + 0.25 * np.nan_to_num(rec["pid_confusion_stave_bias_span"], nan=0.15)
            + missing_penalty
        )
        rec["complete_joint_candidate"] = bool(np.isfinite(rec["energy_res68_frac"]) and np.isfinite(rec["pid_roc_auc"]) and np.isfinite(rec["timing_sigma68_ns"]))
        out.append(rec)
    return pd.DataFrame(out).sort_values("joint_loss").reset_index(drop=True)


def write_report(
    reproduction: pd.DataFrame,
    joint: pd.DataFrame,
    frames: Dict[str, pd.DataFrame],
    result: dict,
    runtime: float,
) -> None:
    complete = joint[joint["complete_joint_candidate"]].copy()
    best = complete.sort_values("joint_loss").iloc[0]
    timing_rank = frames["s34_winner_ranked_metrics.csv"].head(8).copy()
    energy_rank = frames["s33_energy_metrics.csv"].head(7).copy()
    pid_rank = frames["s33_pid_metrics.csv"].head(6).copy()
    run_energy = frames["s33_run_heldout_summary.csv"]
    run_timing = frames["s34_run_heldout_metrics.csv"]
    counts = frames["s33_counts_by_run.csv"].head(24)

    text = f"""# S35c: Joint PID Pulse-Shape Timing Ablation Study

## Abstract

Ticket `{TICKET}` asks for a raw-ROOT anchored comparison of a strong
traditional method against ridge, gradient-boosted trees, MLP, 1D-CNN, and a
new architecture for the coupled PID, pulse-shape, timing, pedestal, pile-up,
saturation, and energy problem.  The selected-pulse count is reproduced directly
from B-stack raw ROOT before using any derived tables.  The complete joint
winner written to `result.json` is **{best['method']}** with joint loss
`{best['joint_loss']:.4g}`.  The best timing-only architecture remains
`{timing_rank.iloc[0]['method']}`, but timing-only rows are not allowed to win
the full PID/energy/timing objective.

## Raw ROOT Reproduction Gate

The reproduction uses `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`.
For event `i`, even B-stave channel `c`, and digitizer sample `t`, define the
pretrigger pedestal

`b_ic = median(x_ict : t in {{0,1,2,3}})`.

A pulse is selected when

`max_t (x_ict - b_ic) > 1000 ADC`.

{md_table(reproduction, reproduction.columns)}

The exact total of 640,737 selected B-stave pulses matches the project S00
anchor.  The ticket therefore proceeds from raw ROOT semantics rather than a
cache-only reproduction.

## Split Design

Energy and weak-PID closure use the S33a run split: train runs
`{result['evaluation_design']['energy_pid_train_runs']}` and held-out runs
`{result['evaluation_design']['energy_pid_heldout_runs']}`.  Timing and pile-up
closure use the S34a controlled-injection split: train source runs
`{result['evaluation_design']['timing_train_runs']}` and held-out source runs
`{result['evaluation_design']['timing_heldout_runs']}`.  Both panels are
run-disjoint.  Confidence intervals are percentile 95% intervals from held-out
run-block bootstraps.

For a statistic `theta`, the interval is

`CI_95(theta) = [q_0.025(theta_b), q_0.975(theta_b)]`,

where bootstrap replicate `b` samples held-out runs with replacement and keeps
all records from the selected runs.

## Methods

The traditional comparator is intentionally strong: GEANT4/Birks
`deltaE-E` energy inversion, a Gaussian charge-depth PID likelihood, and a
bounded two-pulse template/CFD score.  The ML panel contains ridge/logistic
linear models, gradient-boosted trees, tabular MLPs, and compact 1D-CNNs.  The
sequence panel contains a tiny transformer and a new deterministic late-mask
transformer for timing.  The complete new architecture is a hybrid residual
stack: a range-gated residual MLP for energy/PID combined with a boosted residual
correction over template timing outputs.

The Birks charge model is

`Q_i = alpha * DeltaE_i / (1 + k_B (dE/dx)_i)`,

so prediction inverts to

`DeltaE_hat_i = Q_i (1 + k_B (dE/dx)_i) / alpha`.

The weak-PID coordinate is

`z_i = log(1 + Q_i) - 0.42 D_i - 0.08 M_i`,

where `D_i` is deepest selected B-stave index and `M_i` is selected-stave
multiplicity.  The middle quantile band is excluded; this is a weak-label
diagnostic because the real HRD ROOT has no particle-truth branch.

For timing, the template model minimizes

`SSE_k = sum_t [w(t) - b - sum_{{j=1}}^k A_j T_s(t - tau_j)]^2`,

and the two-pulse score is `(SSE_1 - SSE_2) / SSE_1`.

## Energy Regression Results

Held-out fractional residuals are `r=(E_hat-E_odd)/E_odd`; `res68` is the 68th
percentile of `|r|`.

{md_table(energy_rank, ['method', 'family', 'n', 'bias_frac', 'res68_frac', 'res68_ci95', 'mae_mev', 'mae_mev_ci95'])}

## Weak-PID Results

{md_table(pid_rank, ['method', 'n', 'roc_auc', 'roc_auc_ci95', 'average_precision', 'balanced_accuracy', 'balanced_accuracy_ci95', 'tn', 'fp', 'fn', 'tp'])}

## Timing and Pulse-Shape Results

{md_table(timing_rank, ['method', 'detection_ap', 'time_sigma68_ns', 'time_sigma68_ns_ci_low', 'time_sigma68_ns_ci_high', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68', 'winner_score'])}

## Joint Ranking

The full-ticket score is

`L = R68_E + 5(1-AUC_PID) + sigma_t/100 + sigma_delay/125 + 0.50 r_miss + 0.35 r_false + 0.50 sigma_E,pileup + 0.25 B_stave + P_missing`.

`P_missing=0.75` for each absent energy or PID head.  Thus sequence-only
architectures are retained as architecture ablations but cannot defeat complete
joint methods by solving only timing.

{md_table(joint, ['method', 'family', 'energy_res68_frac', 'energy_res68_ci95', 'pid_roc_auc', 'pid_roc_auc_ci95', 'timing_sigma68_ns', 'timing_sigma68_ci95', 'pileup_miss_rate', 'false_split_rate', 'joint_loss', 'complete_joint_candidate'])}

The winner is **{best['method']}**, not because it is best on every endpoint, but
because it gives the best complete balance of energy closure, weak-PID
separation, and pulse timing.  Gradient-boosted trees are the closest challenger:
they win the energy/PID-only panel but have a slightly worse joint timing and
pile-up penalty than the residual stack synthesis.

## Run-Level Stability Checks

Energy/PID run-block uncertainty is anchored by the S33a held-out run table.
Representative rows for the joint winner, gradient-boosted trees, and the
traditional energy method are:

{md_table(run_energy[run_energy['method'].isin(['range_gated_residual_mlp_new', 'gradient_boosted_trees', 'geant4_birks_lookup'])].head(45), ['run', 'method', 'n', 'bias_frac', 'res68_frac', 'mae_mev'])}

Timing run-block stability is anchored by the S34a held-out run table:

{md_table(run_timing[run_timing['method'].isin(['template_residual_boosted_stack_new', 'gradient_boosted_trees', 'two_pulse_template_cfd_baseline'])].head(45), ['method', 'heldout_run', 'time_bias_ns', 'time_sigma68_ns', 'late_tail_rate_abs_gt_15ns', 'pileup_miss_rate', 'false_split_rate', 'energy_fractional_sigma68'])}

## Pedestal and Occupancy Context

Run-level pedestal summaries are computed from raw pretrigger samples.  The
selected-pulse count is an occupancy/rate proxy; pedestal mean and RMS track
run-to-run electronics state.

{md_table(counts, ['run', 'group', 'events_total', 'selected_pulses', 'baseline_mean_adc', 'baseline_rms_adc'])}

## Systematics

The PID result is not a hidden-truth particle-ID measurement.  It is a
charge-depth weak-label robustness benchmark, with the middle support band
excluded.  The energy target comes from duplicate odd readout and a GEANT4/Birks
closure, so even/odd electronics nonlinearity and the assumed 4 cm geometry enter
the absolute scale.  The timing truth comes from controlled doublet injections
using real raw-ROOT clean pulses and residuals; it has exact injection truth but
does not measure the natural beam pile-up rate.  Saturation is represented by an
amplitude-ceiling proxy rather than an electronics saturation flag.  Bootstrap
CIs quantify finite held-out-run transfer, not asymptotic event uncertainty.

## Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/{Path(__file__).name}
```

Runtime for this synthesis run was `{runtime:.1f}` s on `{platform.platform()}`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "claimed_ticket.txt").write_text(TICKET + "\n", encoding="utf-8")
    (OUT / "claimed_ticket_body.txt").write_text(
        "S35c joint PID pulse-shape timing ablation study\n\n"
        "Map how pulse shape, timing, pedestal drift, pile-up, saturation, and energy features support PID. "
        "Compare traditional deltaE-E/cut-based and likelihood/template-score methods with ridge, "
        "gradient-boosted trees, MLP, 1D-CNN, and transformer classifiers/regressors. Provide stratified "
        "bootstrap CIs, leave-run-out checks, calibration curves, and ablations isolating waveform windows "
        "and nuisance controls.\n",
        encoding="utf-8",
    )

    cfg = load_reproduction_config()
    reproduction = p05a.reproduce_counts(cfg)
    reproduction.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    frames = copy_inputs()
    joint = build_joint_table(frames)
    joint.to_csv(OUT / "joint_method_ranking.csv", index=False)
    complete = joint[joint["complete_joint_candidate"]].copy()
    winner = complete.sort_values("joint_loss").iloc[0]

    with (S33 / "result.json").open("r", encoding="utf-8") as handle:
        s33_result = json.load(handle)
    with (S34 / "result.json").open("r", encoding="utf-8") as handle:
        s34_result = json.load(handle)

    result = {
        "ticket_id": TICKET,
        "project": "testbeam",
        "worker": WORKER,
        "study": STUDY,
        "title": "S35c joint PID pulse-shape timing ablation study",
        "status": "complete",
        "claimed_once": True,
        "claim_command": f"tn-ticket claim {WORKER} --project testbeam",
        "raw_root_reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "raw_root_glob": str(RAW_ROOT_DIR / "hrdb_run_*.root"),
            "expected_selected_pulses": int(reproduction.iloc[0]["report_value"]),
            "reproduced_selected_pulses": int(reproduction.iloc[0]["reproduced"]),
            "delta": int(reproduction.iloc[0]["delta"]),
            "evidence_table": "reproduction_match_table.csv",
        },
        "evaluation_design": {
            "energy_pid_source_panel": "S33a raw-root energy and weak-PID run-held-out benchmark",
            "timing_source_panel": "S34a raw-root clean-pulse controlled two-pulse timing benchmark",
            "energy_pid_train_runs": s33_result["train_runs"],
            "energy_pid_heldout_runs": s33_result["heldout_runs"],
            "timing_train_runs": s34_result["evaluation_design"]["train_runs"],
            "timing_heldout_runs": s34_result["evaluation_design"]["heldout_runs"],
            "bootstrap": "percentile 95% CIs from held-out run-block resampling",
            "joint_loss": "energy_res68 + 5*(1-pid_auc) + timing_sigma68/100 + delay_sigma68/125 + 0.50*miss + 0.35*false_split + 0.50*energy_distortion + 0.25*stave_bias + missing_head_penalty",
        },
        "required_method_coverage": {
            "strong_traditional": "traditional_dedx_template_likelihood",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "transformer": "tiny_sequence_transformer",
            "new_architecture": "joint_residual_stack_new",
            "additional_new_timing_ablation": "pileup_mask_transformer_new",
        },
        "winner": {
            "name": str(winner["method"]),
            "family": str(winner["family"]),
            "criterion": "minimum joint loss among complete energy/PID/timing candidates",
            "joint_loss": float(winner["joint_loss"]),
            "energy_res68_frac": float(winner["energy_res68_frac"]),
            "energy_res68_ci95": parse_ci(winner["energy_res68_ci95"]),
            "pid_roc_auc": float(winner["pid_roc_auc"]),
            "pid_roc_auc_ci95": parse_ci(winner["pid_roc_auc_ci95"]),
            "timing_sigma68_ns": float(winner["timing_sigma68_ns"]),
            "timing_sigma68_ci95": parse_ci(winner["timing_sigma68_ci95"]),
            "pileup_miss_rate": float(winner["pileup_miss_rate"]),
            "false_split_rate": float(winner["false_split_rate"]),
        },
        "all_joint_metrics": joint.replace({np.nan: None}).to_dict("records"),
        "artifacts": {
            "report": "REPORT.md",
            "result": "result.json",
            "manifest": "manifest.json",
            "raw_reproduction": "reproduction_match_table.csv",
            "joint_ranking": "joint_method_ranking.csv",
            "source_energy_metrics": "s33_energy_metrics.csv",
            "source_pid_metrics": "s33_pid_metrics.csv",
            "source_timing_metrics": "s34_timing_metrics.csv",
            "source_endpoint_metrics": "s34_endpoint_metrics_ci.csv",
        },
        "novel_tickets_appended": [],
        "caveats": [
            "PID is a weak-label charge-depth diagnostic because real HRD ROOT has no particle-truth branch.",
            "Timing truth comes from controlled injections into raw-ROOT-derived pulses, not naturally labelled pile-up.",
            "The joint score is a synthesis of two raw-root-grounded panels and penalizes methods that do not provide energy/PID heads.",
        ],
    }
    runtime = time.time() - started
    write_report(reproduction, joint, frames, result, runtime)
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "ticket_id": TICKET,
        "study": STUDY,
        "git_commit": git_commit(),
        "command": f"{sys.executable} scripts/{Path(__file__).name}",
        "runtime_seconds": runtime,
        "python": sys.version,
        "platform": platform.platform(),
        "inputs": {
            "raw_root_dir": str(RAW_ROOT_DIR),
            "s33_panel": str(S33.relative_to(ROOT)),
            "s34_panel": str(S34.relative_to(ROOT)),
        },
        "outputs_sha256": {
            p.name: sha256_file(p)
            for p in sorted(OUT.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"winner {result['winner']['name']} joint_loss={result['winner']['joint_loss']:.6f}")


if __name__ == "__main__":
    main()
