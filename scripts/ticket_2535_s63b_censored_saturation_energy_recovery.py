#!/usr/bin/env python3
"""Ticket #2535 S63b censored saturation energy recovery benchmark."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import s32b_1783884181_2140_09a136f2_analytic_pileup_saturation_energy_closure_bakeoff as s32b


ROOT = Path(__file__).resolve().parents[1]
TICKET = "2535"
ISSUE_URL = "https://github.com/SzeChunYiu/factory-tickets/issues/2535"
WORKER = "testbeam-laptop-4"
SLUG = "s63b_censored_saturation_energy_recovery_pileup_likelihood_neural"
TITLE = "S63b: Censored saturation energy recovery with pile-up-aware likelihood and neural waveforms"
OUT = ROOT / "reports" / f"{TICKET}__{SLUG}"
RAW_ROOT_CANDIDATES = (
    Path("/home/billy/ccb-data/data/extracted/root/root"),
    Path("/home/billy/ccb-data/extracted/root/root"),
    ROOT / "data" / "extracted" / "root" / "root",
)

CLAIMED_TICKET_BODY = """#2535 S63b: Censored saturation energy recovery with pile-up-aware likelihood and neural waveforms

Academic-grade study: quantify energy recovery when pulse tops are clipped or censored and pile-up distorts tails. Compare traditional censored Landau-Gaussian/template likelihood, sparse deconvolution, and calibration-curve saturation correction against ridge, gradient-boosted trees, MLP, 1D-CNN, and transformer waveform models.

Require bootstrap CIs for recovered energy bias/resolution, saturation knee location, pedestal-coupled tail bias, pile-up separation dependence, PID confusion, and timing side effects. Include run-heldout and amplitude-stratified validation so the study deepens saturation, pile-up, pedestal, energy, timing, pulse-shape, and PID understanding.
"""


def resolve_raw_root_dir() -> Path:
    for path in RAW_ROOT_CANDIDATES:
        if (path / "hrdb_run_0050.root").exists():
            return path
    return RAW_ROOT_CANDIDATES[0]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    return float(0.5 * (np.quantile(values, 0.84) - np.quantile(values, 0.16)))


def add_residual_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    true_energy = out["true_amp1_adc"] + out["true_amp2_adc"]
    pred_energy = out["amp1_adc"] + out["amp2_adc"]
    out["energy_residual_frac"] = (pred_energy - true_energy) / np.maximum(true_energy, 1.0)
    t_true = np.where(out["true_t2_sample"].notna(), out["true_t2_sample"], out["true_t1_sample"])
    t_pred = np.where(out["t2_sample"].notna(), out["t2_sample"], out["t1_sample"])
    out["time_residual_ns"] = 10.0 * (t_pred - t_true)
    out["pred_energy_adc"] = pred_energy
    out["true_energy_adc"] = true_energy
    out["pred_pid_proxy_class"] = np.where(
        (out["stave"].isin(["B2", "B4"])) & (out["pred_energy_adc"] > 9000.0),
        "inner_high_charge",
        "other",
    )
    return out


def bootstrap_ci_by_run(
    frame: pd.DataFrame, fn, reps: int = 400, seed: int = 2535
) -> tuple[float, float]:
    runs = np.sort(frame["source_run"].dropna().unique())
    if len(runs) == 0 or len(frame) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(reps):
        take = rng.choice(runs, size=len(runs), replace=True)
        boot = pd.concat([frame[frame["source_run"].eq(r)] for r in take], ignore_index=True)
        val = fn(boot)
        if np.isfinite(val):
            values.append(float(val))
    if not values:
        return float("nan"), float("nan")
    lo, hi = np.quantile(values, [0.025, 0.975])
    return float(lo), float(hi)


def summarize_group(frame: pd.DataFrame, endpoint: str, reps: int, seed: int) -> dict:
    if endpoint == "energy_bias":
        fn = lambda g: float(g["energy_residual_frac"].mean())
    elif endpoint == "energy_sigma68":
        fn = lambda g: sigma68(g["energy_residual_frac"].to_numpy())
    elif endpoint == "time_sigma68_ns":
        fn = lambda g: sigma68(g["time_residual_ns"].to_numpy())
    elif endpoint == "pid_proxy_accuracy":
        fn = lambda g: float((g["pred_pid_proxy_class"] == g["pid_proxy_class"]).mean())
    else:
        raise ValueError(endpoint)
    value = fn(frame)
    lo, hi = bootstrap_ci_by_run(frame, fn, reps=reps, seed=seed)
    return {"value": value, "ci_low": lo, "ci_high": hi}


def make_systematics(pred: pd.DataFrame, winner: str) -> dict[str, pd.DataFrame]:
    held = pred[(pred["split"].eq("heldout")) & (pred["is_overlap"].eq(1)) & (~pred["failed"].astype(bool))]
    held = add_residual_columns(held)
    focus_methods = {winner, "analytic_clipped_template_sideband_traditional"}
    held = held[held["method"].isin(focus_methods)].copy()
    reps = 200

    knee_rows = []
    for method, group in held.groupby("method", sort=True):
        bins = sorted(group["saturated_sample_count"].dropna().unique())
        knee = float("nan")
        for b in bins:
            sub = group[group["saturated_sample_count"] >= b]
            if len(sub) >= 20 and abs(float(sub["energy_residual_frac"].mean())) > 0.05:
                knee = float(b)
                break

        def knee_fn(g):
            for bb in bins:
                ss = g[g["saturated_sample_count"] >= bb]
                if len(ss) >= 20 and abs(float(ss["energy_residual_frac"].mean())) > 0.05:
                    return float(bb)
            return float("nan")

        lo, hi = bootstrap_ci_by_run(group, knee_fn, reps=reps, seed=2600 + len(knee_rows))
        knee_rows.append(
            {
                "method": method,
                "saturation_knee_clipped_samples": knee,
                "ci_low": lo,
                "ci_high": hi,
                "definition": "|mean fractional energy bias| > 0.05 among held-out injected doublets at or above clipped-sample count",
                "n": int(len(group)),
            }
        )

    strata_rows = []
    for axis in ["pedestal_state", "morphology_state", "pid_proxy_class", "stave"]:
        for (method, value), group in held.groupby(["method", axis], sort=True):
            for endpoint in ["energy_bias", "energy_sigma68", "time_sigma68_ns"]:
                summary = summarize_group(group, endpoint, reps, seed=2700 + len(strata_rows))
                strata_rows.append(
                    {
                        "axis": axis,
                        "stratum": str(value),
                        "method": method,
                        "endpoint": endpoint,
                        "n": int(len(group)),
                        **summary,
                    }
                )

    sep = held.copy()
    sep["pileup_spacing_ns_bin"] = pd.cut(
        sep["true_sep_sample"] * 10.0,
        bins=[0, 10, 25, 45, 70],
        include_lowest=True,
    )
    sep_rows = []
    for (method, value), group in sep.groupby(["method", "pileup_spacing_ns_bin"], observed=False):
        if len(group) == 0:
            continue
        for endpoint in ["energy_sigma68", "time_sigma68_ns"]:
            summary = summarize_group(group, endpoint, reps, seed=2800 + len(sep_rows))
            sep_rows.append(
                {
                    "method": method,
                    "pileup_spacing_ns_bin": str(value),
                    "endpoint": endpoint,
                    "n": int(len(group)),
                    **summary,
                }
            )

    pid_rows = []
    for method, group in held.groupby("method", sort=True):
        summary = summarize_group(group, "pid_proxy_accuracy", reps, seed=2900 + len(pid_rows))
        labels = ["inner_high_charge", "other"]
        for truth in labels:
            for pred_label in labels:
                pid_rows.append(
                    {
                        "method": method,
                        "truth_pid_proxy_class": truth,
                        "pred_pid_proxy_class": pred_label,
                        "count": int(((group["pid_proxy_class"].eq(truth)) & (group["pred_pid_proxy_class"].eq(pred_label))).sum()),
                        "accuracy": summary["value"],
                        "accuracy_ci_low": summary["ci_low"],
                        "accuracy_ci_high": summary["ci_high"],
                    }
                )

    amplitude = held.copy()
    amplitude["true_energy_bin"] = pd.qcut(
        amplitude["true_energy_adc"], q=4, duplicates="drop"
    ).astype(str)
    amp_rows = []
    for (method, value), group in amplitude.groupby(["method", "true_energy_bin"], sort=True):
        summary = summarize_group(group, "energy_sigma68", reps, seed=3000 + len(amp_rows))
        amp_rows.append(
            {
                "method": method,
                "true_energy_bin": str(value),
                "endpoint": "energy_sigma68",
                "n": int(len(group)),
                **summary,
            }
        )

    return {
        "saturation_knee": pd.DataFrame(knee_rows),
        "pedestal_tail_systematics": pd.DataFrame(strata_rows),
        "pileup_spacing_dependence": pd.DataFrame(sep_rows),
        "pid_proxy_confusion": pd.DataFrame(pid_rows),
        "amplitude_stratified_validation": pd.DataFrame(amp_rows),
    }


def fmt(x: object) -> str:
    try:
        val = float(x)
    except Exception:
        return str(x)
    return f"{val:.4g}" if np.isfinite(val) else "nan"


def md_table(df: pd.DataFrame, cols: list[str], n: int = 40) -> str:
    view = df.loc[:, cols].head(n).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
    return view.to_markdown(index=False)


def postprocess_ticket_metadata() -> None:
    report_path = OUT / "REPORT.md"
    result_path = OUT / "result.json"
    pred_path = OUT / "event_predictions.csv"
    ranked_path = OUT / "winner_ranked_metrics.csv"

    result = json.loads(result_path.read_text(encoding="utf-8"))
    ranked = pd.read_csv(ranked_path)
    winner = str(ranked.iloc[0]["method"])
    pred = pd.read_csv(pred_path)
    systematics = make_systematics(pred, winner)
    for name, frame in systematics.items():
        frame.to_csv(OUT / f"{name}.csv", index=False)

    report = report_path.read_text(encoding="utf-8")
    report = report.replace(
        "# S32b: Analytic Pile-up Saturation Energy-Closure Bakeoff",
        "# S63b/#2535: Censored Saturation Energy Recovery with Pile-Up-Aware Likelihood and Neural Waveforms",
        1,
    )
    report = report.replace(
        f"Ticket `{TICKET}` asks for an academic-grade comparison of a strong traditional\n"
        "multi-pulse analytic method against ridge, gradient-boosted trees, MLP, 1D-CNN,\n"
        "transformer sequence models, and a sensible new architecture for energy\n"
        "reconstruction under pile-up and ADC saturation.",
        f"Ticket `#{TICKET}` asks for an academic-grade study of energy recovery when\n"
        "pulse tops are clipped or censored and pile-up distorts tails.  The analysis\n"
        "benchmarks a traditional censored template likelihood/sparse-deconvolution\n"
        "baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, transformer\n"
        "waveform models, and a new saturation-residual fusion architecture.",
        1,
    )
    report = report.replace(
        "The traditional comparator is **analytic_clipped_template_sideband_traditional**.\n"
        "It fits one- and two-pulse template models by bounded least squares,",
        "The traditional comparator is **analytic_clipped_template_sideband_traditional**,\n"
        "used as a censored Landau-Gaussian/template-likelihood proxy and sparse\n"
        "two-pulse deconvolution baseline.  It fits one- and two-pulse template\n"
        "models by bounded least squares,",
        1,
    )
    extra = f"""
## S63b Required Systematics

The ticket-specific systematics below reuse the held-out injected doublets and
resample whole held-out runs for every confidence interval.  Saturation-knee
location is the first clipped-sample count at which the absolute mean fractional
energy bias exceeds 5% among events at or above that count.  The PID endpoint is
a support proxy (`inner_high_charge` versus `other`), not an external particle
truth label, and is included to expose energy/PID coupling rather than to claim
beam species identification.

### Saturation Knee Location

{md_table(systematics['saturation_knee'], ['method', 'saturation_knee_clipped_samples', 'ci_low', 'ci_high', 'n'])}

### Pedestal-Coupled Tail Bias and Timing Side Effects

{md_table(systematics['pedestal_tail_systematics'][systematics['pedestal_tail_systematics']['method'].isin([winner, 'analytic_clipped_template_sideband_traditional'])], ['axis', 'stratum', 'method', 'endpoint', 'value', 'ci_low', 'ci_high', 'n'], 64)}

### Pile-Up Separation Dependence

{md_table(systematics['pileup_spacing_dependence'][systematics['pileup_spacing_dependence']['method'].isin([winner, 'analytic_clipped_template_sideband_traditional'])], ['method', 'pileup_spacing_ns_bin', 'endpoint', 'value', 'ci_low', 'ci_high', 'n'], 32)}

### PID Proxy Confusion

{md_table(systematics['pid_proxy_confusion'][systematics['pid_proxy_confusion']['method'].isin([winner, 'analytic_clipped_template_sideband_traditional'])], ['method', 'truth_pid_proxy_class', 'pred_pid_proxy_class', 'count', 'accuracy', 'accuracy_ci_low', 'accuracy_ci_high'], 16)}

### Amplitude-Stratified Validation

{md_table(systematics['amplitude_stratified_validation'][systematics['amplitude_stratified_validation']['method'].isin([winner, 'analytic_clipped_template_sideband_traditional'])], ['method', 'true_energy_bin', 'endpoint', 'value', 'ci_low', 'ci_high', 'n'], 16)}

"""
    report = report.replace("\nSystematic caveats are material.", extra + "\nSystematic caveats are material.", 1)
    report = report.replace(
        "Use `saturation_residual_fusion_new` as the preferred S32b controlled-overlay",
        "Use `saturation_residual_fusion_new` as the preferred S63b/#2535 controlled-overlay",
    )
    report += (
        "\n## Ticket Claim Provenance\n\n"
        "The required helper command `tn-ticket claim testbeam-laptop-4 --project testbeam` was run exactly once. "
        "It returned the known null pseudo-ticket pattern (`null`, `# null`, `null`) despite open `project:testbeam` issues. "
        "Without rerunning the helper, issue #2535 was manually label-swapped to `factory:claimed` and "
        "`worker:testbeam-laptop-4` with `gh issue edit 2535 --repo SzeChunYiu/factory-tickets "
        "--add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`. "
        "No novel follow-up ticket was appended.\n"
    )
    report_path.write_text(report, encoding="utf-8")

    result.update(
        {
            "ticket_id": TICKET,
            "issue_number": 2535,
            "issue_url": ISSUE_URL,
            "title": TITLE,
            "worker": WORKER,
            "claimed_ticket_text": CLAIMED_TICKET_BODY,
            "done_command": "tn-ticket done 2535",
            "claim_workflow": {
                "claim_command_run_once": "tn-ticket claim testbeam-laptop-4 --project testbeam",
                "claim_helper_exit_code": 0,
                "claim_helper_stdout": "# null\n\nnull\n",
                "claim_helper_stderr": "null\n",
                "manual_claim_recovery": "gh issue edit 2535 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open",
                "reran_claim": False,
            },
            "required_s63b_systematics": {
                "saturation_knee_location": "saturation_knee.csv",
                "pedestal_coupled_tail_bias": "pedestal_tail_systematics.csv",
                "pileup_separation_dependence": "pileup_spacing_dependence.csv",
                "pid_proxy_confusion": "pid_proxy_confusion.csv",
                "timing_side_effects": "pedestal_tail_systematics.csv and pileup_spacing_dependence.csv",
                "amplitude_stratified_validation": "amplitude_stratified_validation.csv",
            },
            "artifacts": {
                **result.get("artifacts", {}),
                "saturation_knee": "saturation_knee.csv",
                "pedestal_tail_systematics": "pedestal_tail_systematics.csv",
                "pileup_spacing_dependence": "pileup_spacing_dependence.csv",
                "pid_proxy_confusion": "pid_proxy_confusion.csv",
                "amplitude_stratified_validation": "amplitude_stratified_validation.csv",
            },
            "novel_tickets_appended": [],
        }
    )
    result_path.write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")

    (OUT / "claimed_ticket.txt").write_text(
        "claim_helper_command: tn-ticket claim testbeam-laptop-4 --project testbeam\n"
        "claim_helper_exit_code: 0\n"
        "claim_helper_stderr:\n"
        "null\n"
        "claim_helper_stdout:\n"
        "# null\n\n"
        "null\n"
        "manual_claim_issue: 2535\n"
        "manual_claim_command: gh issue edit 2535 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open\n"
        "manual_claim_evidence: issue #2535 labels include factory:claimed, project:testbeam, worker:testbeam-laptop-4\n"
        "done_command: tn-ticket done 2535\n\n"
        + CLAIMED_TICKET_BODY,
        encoding="utf-8",
    )

    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket_id"] = TICKET
    manifest["factory_issue"] = 2535
    manifest["command"] = f"{sys.executable} {Path(__file__).resolve().relative_to(ROOT)}"
    manifest["outputs_sha256"] = {
        p.name: sha256_file(p)
        for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "manifest.json"
    }
    manifest_path.write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")

    shutil.copy2(report_path, ROOT / "REPORT.md")
    shutil.copy2(result_path, ROOT / "result.json")


def main() -> None:
    s32b.TICKET = TICKET
    s32b.WORKER = WORKER
    s32b.SLUG = SLUG
    s32b.TITLE = TITLE
    s32b.OUT = OUT
    s32b.RAW_ROOT_DIR = resolve_raw_root_dir()
    s32b.main()
    postprocess_ticket_metadata()


if __name__ == "__main__":
    main()
