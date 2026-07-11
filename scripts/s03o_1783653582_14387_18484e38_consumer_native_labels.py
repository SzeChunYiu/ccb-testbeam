#!/usr/bin/env python3
"""S03o consumer-native labels for frozen S03m excluded regions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s02_timing_pickoff as s02  # noqa: E402


REQUIRED_FAMILIES = {
    "traditional_hier_amp": "traditional",
    "ridge_waveform": "ridge",
    "gradient_boosted_trees": "gradient_boosted_trees",
    "mlp_waveform": "mlp",
    "tiny_1d_cnn": "1d_cnn",
    "support_gated_ensemble": "new_support_gated_ensemble",
}


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(block_size), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def fmt_ci(lo: float, hi: float, nd: int = 3) -> str:
    if pd.isna(lo) or pd.isna(hi):
        return "not estimable"
    return f"[{lo:.{nd}f}, {hi:.{nd}f}]"


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_required_benchmark(ext_dir: Path) -> pd.DataFrame:
    pooled = pd.read_csv(ext_dir / "pooled_run_bootstrap.csv")
    bench = pooled[pooled["method"].isin(REQUIRED_FAMILIES)].copy()
    bench["model_family"] = bench["method"].map(REQUIRED_FAMILIES)
    bench["metric"] = "excluded_support_pairwise_sigma68_ns"
    bench["winner_eligible"] = True
    bench = bench.sort_values("sigma68_ns").reset_index(drop=True)
    return bench


def build_consumer_label_table(consumer_dir: Path) -> pd.DataFrame:
    imported = pd.read_csv(consumer_dir / "imported_consumer_evidence.csv")
    deltas = pd.read_csv(consumer_dir / "downstream_metric_deltas.csv")
    rows = []
    best_by_consumer = imported.sort_values(["consumer", "value"]).groupby("consumer", as_index=False).first()
    for _, row in best_by_consumer.iterrows():
        rows.append(
            {
                "consumer": row["consumer"],
                "native_label_source": row["source"],
                "native_label_method": row["method"],
                "native_metric": row["metric"],
                "native_value": row["value"],
                "native_ci_low": row["ci_low"],
                "native_ci_high": row["ci_high"],
                "native_role": row["role"],
            }
        )
    label = pd.DataFrame(rows)
    hgb = deltas[deltas["candidate"] == "hgb_waveform_amp_shape_stave"].copy()
    hgb["consumer_native_priority"] = np.select(
        [
            hgb["stratum"].astype(str).str.startswith("all_"),
            hgb["stratum"].astype(str).str.contains("high-risk", case=False, na=False),
            hgb["stratum"].astype(str).eq("all"),
        ],
        [0, 1, 2],
        default=3,
    )
    if not hgb.empty:
        hgb = hgb.sort_values(
            ["consumer", "consumer_native_priority", "candidate_minus_analytic_sigma68_ns"]
        ).groupby("consumer", as_index=False).first()
        label = label.merge(
            hgb[
                [
                    "consumer",
                    "stratum",
                    "n_pair_residuals",
                    "candidate_minus_analytic_sigma68_ns",
                    "sigma68_delta_ci_low_ns",
                    "sigma68_delta_ci_high_ns",
                    "candidate_minus_analytic_tail_frac_abs_gt5ns",
                    "tail_frac_delta_ci_low",
                    "tail_frac_delta_ci_high",
                ]
            ],
            on="consumer",
            how="left",
        )
    return label


def classify_actions(config: dict, action_bands: pd.DataFrame, support: pd.DataFrame, per_run: pd.DataFrame) -> pd.DataFrame:
    rule = config["decision_rule"]
    rows = []
    excluded = action_bands[action_bands["action"].isin(["abstain", "recalibrate"])].copy()
    for _, a in excluded.iterrows():
        unit = str(a["unit"])
        stratum = str(a["stratum"])
        hgb_gain = np.nan
        hgb_tail_delta = np.nan
        support_fraction = np.nan
        supporting_method = "not_applicable"
        reason = []

        if unit == "run" and stratum.isdigit():
            run = int(stratum)
            sr = support[support["run"] == run]
            support_fraction = float(sr["support_event_fraction"].iloc[0]) if len(sr) else 0.0
            pr = per_run[per_run["heldout_run"] == run]
            hgb = pr[pr["method"] == "gradient_boosted_trees"]
            trad = pr[pr["method"] == "traditional_hier_amp"]
            if len(hgb) and len(trad):
                hgb_gain = float(hgb["sigma68_ns"].iloc[0] - trad["sigma68_ns"].iloc[0])
                hgb_tail_delta = float(hgb["tail_frac_abs_gt5ns"].iloc[0] - trad["tail_frac_abs_gt5ns"].iloc[0])
                supporting_method = "gradient_boosted_trees_vs_traditional_hier_amp"
        elif unit == "global":
            pooled = per_run.groupby("method", as_index=False).agg(
                sigma68_ns=("sigma68_ns", "mean"),
                tail_frac_abs_gt5ns=("tail_frac_abs_gt5ns", "mean"),
            )
            hgb = pooled[pooled["method"] == "gradient_boosted_trees"]
            trad = pooled[pooled["method"] == "traditional_hier_amp"]
            support_fraction = float(support["support_events"].sum() / support["events"].sum())
            if len(hgb) and len(trad):
                hgb_gain = float(hgb["sigma68_ns"].iloc[0] - trad["sigma68_ns"].iloc[0])
                hgb_tail_delta = float(hgb["tail_frac_abs_gt5ns"].iloc[0] - trad["tail_frac_abs_gt5ns"].iloc[0])
                supporting_method = "gradient_boosted_trees_vs_traditional_hier_amp"

        recoverable = (
            np.isfinite(hgb_gain)
            and hgb_gain < 0
            and np.isfinite(hgb_tail_delta)
            and hgb_tail_delta <= float(rule["max_tail_increase_for_recoverable"])
            and support_fraction >= float(rule["min_support_event_fraction"])
            and int(a["n_pair_residuals"]) >= int(rule["min_pair_residuals_for_recoverable"])
        )
        if recoverable:
            consumer_action = "recoverable_hgb_refit"
            reason.append("HGB improves excluded-support sigma68 without tail increase at adequate consumer support")
        elif int(a["n_pair_residuals"]) == 0 or support_fraction < float(rule["min_support_event_fraction"]):
            consumer_action = "hard_veto"
            reason.append("no or low consumer-native support for a refit")
        elif str(a["action"]) == "recalibrate":
            consumer_action = "hard_veto"
            reason.append("S03m flagged recalibration but consumer-native HGB evidence is not a clean recovery")
        else:
            consumer_action = "diagnostic_abstain"
            reason.append("mixed evidence: keep as diagnostic excluded support")

        rows.append(
            {
                "source_unit": unit,
                "source_stratum": stratum,
                "s03m_action": a["action"],
                "n_pair_residuals": int(a["n_pair_residuals"]),
                "n_runs": int(a["n_runs"]),
                "s03m_sigma68_ns": a["sigma68_ns"],
                "s03m_sigma68_ci_low_ns": a["sigma68_ci_low_ns"],
                "s03m_sigma68_ci_high_ns": a["sigma68_ci_high_ns"],
                "support_event_fraction": support_fraction,
                "hgb_minus_traditional_sigma68_ns": hgb_gain,
                "hgb_minus_traditional_tail_frac": hgb_tail_delta,
                "supporting_method": supporting_method,
                "consumer_native_action": consumer_action,
                "rationale": "; ".join(reason),
            }
        )
    return pd.DataFrame(rows).sort_values(["consumer_native_action", "source_unit", "source_stratum"]).reset_index(drop=True)


def write_report(out_dir: Path, config: dict, reproduction: pd.DataFrame, benchmark: pd.DataFrame, consumer_labels: pd.DataFrame, action_split: pd.DataFrame, result: dict) -> None:
    b = benchmark.copy()
    b["sigma68_ci"] = b.apply(lambda r: fmt_ci(r["sigma68_ns_ci_low"], r["sigma68_ns_ci_high"]), axis=1)
    b["tail_ci"] = b.apply(lambda r: fmt_ci(r["tail_frac_abs_gt5ns_ci_low"], r["tail_frac_abs_gt5ns_ci_high"], 4), axis=1)
    cl = consumer_labels.copy()
    cl["native_ci"] = cl.apply(lambda r: fmt_ci(r["native_ci_low"], r["native_ci_high"]), axis=1)
    sp = action_split.copy()
    sp["s03m_sigma68_ci"] = sp.apply(lambda r: fmt_ci(r["s03m_sigma68_ci_low_ns"], r["s03m_sigma68_ci_high_ns"]), axis=1)
    winner = result["winner"]
    text = f"""# S03o: consumer-native labels for frozen S03m excluded regions

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Question:** acquire or join event-native pile-up/PID/charge/energy labels for S03m abstain and recalibrate rows, then test whether excluded regions should split into recoverable HGB-refit and hard-veto actions.
- **Primary split:** run-held-out Sample-II excluded-support benchmark; bootstrap unit is held-out run.

## Abstract

This study joins the frozen S03m excluded-region action table to downstream consumer-native evidence from charge, energy, pile-up, and PID studies, and to the S03o external-shape excluded-support ML benchmark. The raw ROOT anchor is reproduced exactly at **{result['reproduction']['selected_pulses']}** selected B-stave pulses. On the excluded-support benchmark, **{winner['method']}** wins with `sigma68 = {winner['sigma68_ns']:.3f} ns`, 95% CI **[{winner['sigma68_ns_ci_low']:.3f}, {winner['sigma68_ns_ci_high']:.3f}]**, versus the strong traditional hierarchical-amplitude comparator.

The consumer-native action split is intentionally stricter than the ML ranking: an S03m excluded row is called `recoverable_hgb_refit` only when HGB improves the excluded-support residual width without increasing the tail fraction and when the event-native support fraction is adequate. Rows with no support, low support, or non-improving HGB are labelled `hard_veto`; ambiguous rows remain `diagnostic_abstain`.

## Raw ROOT Reproduction

The count gate reads the configured raw ROOT files directly, subtracts the median of samples 0--3 per channel, and counts B2/B4/B6/B8 pulses above 1000 ADC.

{reproduction.to_markdown(index=False)}

## Estimands

For event `e`, pair `p`, and method `m`, the same-particle residual is

`r_(e,p,m) = tau_(e,a,m) - tau_(e,b,m)`,

where `tau` is the geometry-corrected downstream timestamp. The principal width is

`sigma68(r) = (Q_84(r) - Q_16(r)) / 2`.

For each excluded S03m row `g`, the consumer-native recovery statistic is

`Delta_g = sigma68_g(HGB) - sigma68_g(traditional)`,

with a parallel tail statistic

`T_g = P(|r_HGB - median(r_HGB)| > 5 ns) - P(|r_trad - median(r_trad)| > 5 ns)`.

The decision rule is:

- `recoverable_hgb_refit` when `Delta_g < 0`, `T_g <= 0`, support event fraction >= {config['decision_rule']['min_support_event_fraction']}, and at least {config['decision_rule']['min_pair_residuals_for_recoverable']} pair residuals are present.
- `hard_veto` when support is absent/low, or when S03m required recalibration but the consumer-native HGB evidence does not cleanly recover the stratum.
- `diagnostic_abstain` for mixed evidence that should travel as a label but not authorize production reuse.

## Required Method Benchmark

{b[['method','model_family','n_pair_residuals','sigma68_ns','sigma68_ci','full_rms_ns','tail_frac_abs_gt5ns','tail_ci','bias_vs_log_amp_slope_ns']].to_markdown(index=False)}

This table includes the requested strong traditional method, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new support-gated ensemble. The support-gated ensemble is sensible because the candidate rows are not generic pulses: they are selected by S03m exclusion/action support and by external late-shape constraints, so a gate can condition the waveform model on support membership without using run id or event id.

## Consumer-Native Label Join

{cl[['consumer','native_label_source','native_label_method','native_metric','native_value','native_ci','native_role','stratum','candidate_minus_analytic_sigma68_ns','sigma68_delta_ci_low_ns','sigma68_delta_ci_high_ns']].to_markdown(index=False)}

These rows are not used as direct supervised labels for timing. They are event-native consumer references: charge and energy calibration loss or width, pile-up average precision, PID ROC AUC, and GEANT4 energy calibration. The joined high-risk timing deltas show whether the timing substitution that would feed those consumers improves or worsens the same-particle closure in the S03m high-risk/excluded support.

## Excluded-Region Action Split

{sp[['source_unit','source_stratum','s03m_action','n_pair_residuals','n_runs','s03m_sigma68_ns','s03m_sigma68_ci','support_event_fraction','hgb_minus_traditional_sigma68_ns','hgb_minus_traditional_tail_frac','consumer_native_action','rationale']].to_markdown(index=False)}

## Systematics and Caveats

- **Raw input:** The selected-pulse count is reproduced from raw ROOT, but the consumer-native join uses previously frozen downstream artifacts. This is deliberate: the ticket asks to acquire or join labels, not to retune all downstream consumers.
- **Split:** The excluded-support ML benchmark is split by held-out run with run-bootstrap confidence intervals. The S03m action table itself was frozen before this ticket.
- **Leakage:** The joined labels are consumer outcomes and support diagnostics; run id and event id are not features in the benchmark winner selection.
- **Interpretability:** The strong traditional comparator remains the hierarchical amplitude/timewalk method. HGB can be recoverable for some strata but is not globally authorized for all S03m exclusions.
- **Support limitation:** Run 64 has no strict B4/B6/B8 same-event support in the S03m endpoint and is therefore a hard veto here, regardless of indirect evidence.
- **Consumer scope:** Pile-up, PID, charge, and energy metrics have different units. The action decision uses timing residual recovery as the common gate and treats consumer-native metrics as external labels/caveats, not as a scalar objective to optimize.

## Verdict

`result.json` names **{winner['method']}** as the benchmark winner. The excluded-region label split contains **{result['action_counts'].get('recoverable_hgb_refit', 0)}** recoverable HGB-refit rows, **{result['action_counts'].get('hard_veto', 0)}** hard-veto rows, and **{result['action_counts'].get('diagnostic_abstain', 0)}** diagnostic-abstain rows. Production consumers should carry `consumer_native_action` with the S03m row label rather than treating all S03m exclusions as a single abstention class.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s03o_1783653582_14387_18484e38_consumer_native_labels.yaml")
    args = parser.parse_args()
    t0 = time.time()
    config = load_config(Path(args.config))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    src = {k: Path(v) for k, v in config["source_reports"].items()}

    reproduction = s02.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    action_bands = pd.read_csv(src["s03m_action_bands"] / "action_bands.csv")
    support = pd.read_csv(src["s03o_external_shape_gate"] / "support_summary.csv")
    per_run = pd.read_csv(src["s03o_external_shape_gate"] / "per_run_benchmark.csv")
    benchmark = build_required_benchmark(src["s03o_external_shape_gate"])
    consumer_labels = build_consumer_label_table(src["s03m_consumer_closure"])
    action_split = classify_actions(config, action_bands, support, per_run)

    benchmark.to_csv(out_dir / "required_family_benchmark.csv", index=False)
    consumer_labels.to_csv(out_dir / "consumer_native_label_join.csv", index=False)
    action_split.to_csv(out_dir / "excluded_region_action_split.csv", index=False)

    input_paths = [
        src["s03m_action_bands"] / "action_bands.csv",
        src["s03m_consumer_closure"] / "imported_consumer_evidence.csv",
        src["s03m_consumer_closure"] / "downstream_metric_deltas.csv",
        src["s03o_external_shape_gate"] / "pooled_run_bootstrap.csv",
        src["s03o_external_shape_gate"] / "per_run_benchmark.csv",
        src["s03o_external_shape_gate"] / "support_summary.csv",
    ]
    pd.DataFrame([{"path": str(p), "sha256": sha256_file(p)} for p in input_paths]).to_csv(out_dir / "input_sha256.csv", index=False)

    winner = benchmark.iloc[0].to_dict()
    result = {
        "ticket_id": config["ticket_id"],
        "study_id": config["study_id"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "runtime_sec": time.time() - t0,
        "reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "selected_pulses": int(reproduction.loc[reproduction["quantity"] == "total selected B-stave pulses", "reproduced"].iloc[0]),
            "expected_selected_pulses": int(config["expected_counts"]["total_selected_pulses"]),
        },
        "split": {
            "heldout_runs": sorted(int(x) for x in per_run["heldout_run"].unique()),
            "bootstrap_unit": "heldout_run",
            "evaluation_support": "S03m excluded/support-constrained Sample-II rows",
        },
        "winner": winner,
        "traditional_comparator": benchmark[benchmark["method"] == "traditional_hier_amp"].iloc[0].to_dict(),
        "required_family_results": benchmark.to_dict(orient="records"),
        "consumer_native_labels": consumer_labels.to_dict(orient="records"),
        "excluded_region_actions": action_split.to_dict(orient="records"),
        "action_counts": {str(k): int(v) for k, v in action_split["consumer_native_action"].value_counts().to_dict().items()},
        "finding": (
            f"{winner['method']} wins the excluded-support benchmark. "
            f"S03m excluded rows split into {action_split['consumer_native_action'].value_counts().to_dict()}."
        ),
        "next_tickets": [],
    }
    (out_dir / "result.json").write_text(json.dumps(clean(result), indent=2, sort_keys=True), encoding="utf-8")
    manifest = {
        "generated_at_unix": time.time(),
        "config": args.config,
        "outputs": sorted(p.name for p in out_dir.iterdir() if p.is_file()),
        "sha256": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean(manifest), indent=2, sort_keys=True), encoding="utf-8")
    write_report(out_dir, config, reproduction, benchmark, consumer_labels, action_split, result)
    manifest["outputs"] = sorted(p.name for p in out_dir.iterdir() if p.is_file())
    manifest["sha256"] = {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"}
    (out_dir / "manifest.json").write_text(json.dumps(clean(manifest), indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
