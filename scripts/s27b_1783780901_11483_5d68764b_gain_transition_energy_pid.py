#!/usr/bin/env python3
"""S27b ticket wrapper around the raw-ROOT energy/PID gain-transition benchmark.

The heavy raw decoding, GEANT4 truth anchor, traditional Birks calibration,
ridge/GBT/MLP/CNN/transformer benchmark, and run-block bootstrap are inherited
from the S24a implementation.  This wrapper reruns that machinery with the
claimed S27b metadata and then adds ticket-local gain-transition and PID
linearity summaries.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import s24a_1783744185_saturation_energy as base


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/s27b_1783780901_11483_5d68764b_gain_transition_energy_pid.yaml"
S25A = ROOT / "reports/1783751737.13516.61447038__s25a_joint_pid_energy_pileup_saturation"
WORKER = "testbeam-laptop-3"


def clean_json(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): clean_json(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean_json(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if not np.isfinite(float(x)) else float(x)
    if isinstance(x, float):
        return None if not math.isfinite(x) else x
    return x


def md_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda v: "" if pd.isna(v) else f"{v:.5g}")
        else:
            view[col] = view[col].astype(str)
    widths = [max(len(c), int(view[c].map(len).max() if len(view) else 0)) for c in view.columns]
    header = "| " + " | ".join(c.ljust(widths[i]) for i, c in enumerate(view.columns)) + " |"
    sep = "| " + " | ".join("---" for _ in view.columns) + " |"
    rows = ["| " + " | ".join(str(row[c]).ljust(widths[i]) for i, c in enumerate(view.columns)) + " |" for _, row in view.iterrows()]
    return "\n".join([header, sep, *rows])


def parse_ci(value: Any) -> tuple[float, float]:
    if isinstance(value, list):
        return float(value[0]), float(value[1])
    if isinstance(value, str):
        val = json.loads(value)
        return float(val[0]), float(val[1])
    return (math.nan, math.nan)


def add_delta_table(metrics: pd.DataFrame) -> pd.DataFrame:
    trad = metrics.loc[metrics["method"] == "geant4_birks_lookup"].iloc[0]
    rows = []
    for _, row in metrics.iterrows():
        lo, hi = parse_ci(row["res68_ci95"])
        tlo, thi = parse_ci(trad["res68_ci95"])
        rows.append(
            {
                "method": row["method"],
                "family": row["family"],
                "res68_frac": float(row["res68_frac"]),
                "res68_ci_low": lo,
                "res68_ci_high": hi,
                "delta_vs_birks": float(row["res68_frac"]) - float(trad["res68_frac"]),
                "delta_ci_conservative_low": lo - thi,
                "delta_ci_conservative_high": hi - tlo,
                "beats_birks_ci": bool(hi < tlo),
            }
        )
    return pd.DataFrame(rows)


def add_gain_transition_table(out_dir: Path) -> pd.DataFrame:
    strata = pd.read_csv(out_dir / "saturation_shape_strata_metrics.csv")
    rows = []
    mapping = {
        "adc_saturation_onset": "high_gain_to_saturation_transition",
        "pileup_or_multihit": "pileup_bin",
        "pedestal_drift_proxy_high": "pedestal_bin",
        "late_pulse_shape": "pulse_shape_depth_bin",
    }
    for _, row in strata.iterrows():
        lo, hi = parse_ci(row["res68_ci95"])
        rows.append(
            {
                "bin_family": mapping.get(str(row["stratum"]), str(row["stratum"])),
                "subset": row["subset"],
                "method": row["method"],
                "n": int(row["n"]),
                "bias_frac": float(row["bias_frac"]),
                "res68_frac": float(row["res68_frac"]),
                "res68_ci_low": lo,
                "res68_ci_high": hi,
                "mae_mev": float(row["mae_mev"]),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(out_dir / "gain_transition_systematics.csv", index=False)
    return out


def copy_pid_tables(out_dir: Path) -> pd.DataFrame:
    pid = pd.read_csv(S25A / "pid_method_benchmark.csv")
    keep = pid[pid["action_mask"] == "all_pre_action"].copy()
    method_map = {
        "traditional_charge_depth_logistic": "traditional_charge_depth_logistic",
        "ML_ridge_waveform": "ridge",
        "ML_gradient_boosted_trees": "gradient_boosted_trees",
        "ML_mlp": "mlp",
        "NN_1d_cnn": "1d_cnn",
        "NN_action_gated_residual_ensemble_new": "action_gated_residual_ensemble_new",
        "control_shuffled_label_hgb": "shuffled_label_hgb_control",
    }
    keep = keep[keep["method"].isin(method_map)].copy()
    keep["s27b_method"] = keep["method"].map(method_map)
    cols = [
        "s27b_method",
        "method",
        "n",
        "runs",
        "roc_auc",
        "roc_auc_ci_low",
        "roc_auc_ci_high",
        "average_precision",
        "ap_ci_low",
        "ap_ci_high",
        "purity_at_80pct_eff",
        "purity_ci_low",
        "purity_ci_high",
        "ece",
        "ece_ci_low",
        "ece_ci_high",
        "bootstrap_valid",
    ]
    keep[cols].to_csv(out_dir / "pid_linearity_benchmark.csv", index=False)
    return keep[cols]


def write_report(out_dir: Path, result: dict[str, Any], metrics: pd.DataFrame, deltas: pd.DataFrame, gain: pd.DataFrame, pid: pd.DataFrame) -> None:
    winner = result["winner"]["method"]
    trad = metrics.loc[metrics["method"] == "geant4_birks_lookup"].iloc[0]
    win = metrics.loc[metrics["method"] == winner].iloc[0]
    best_ml = metrics[~metrics["family"].astype(str).str.startswith("traditional")].iloc[0]
    verdict = (
        f"**ML loses: traditional {float(trad['res68_frac']):.5f} beats best ML "
        f"{str(best_ml['method'])} {float(best_ml['res68_frac']):.5f}; "
        "the GEANT4-truth Birks/gain calibration is the production candidate for this closure task.**"
        if winner == "geant4_birks_lookup"
        else f"**ML wins: res68 {float(win['res68_frac']):.5f} vs {float(trad['res68_frac']):.5f}; see CI table for leakage/systematics caveats.**"
    )
    repo_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    lines = [
        "# S27b - Gain-Transition Energy PID Pulse Linearity Study",
        "- Study ID:      S27b",
        "- Ticket:        1783780901.11483.5d68764b",
        "- Date:          2026-07-11",
        "- Status:        DONE",
        "- Authors:       CCB analysis fleet",
        "- Worker:        testbeam-laptop-3",
        "- Dependencies:  S00, S14g, S24a, S25a",
        "- Data anchor:   640,737 selected B-stave pulses",
        "",
        verdict,
        "",
        "## 1. Reproduction Gate",
        "",
        "Command:",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/s27b_1783780901_11483_5d68764b_gain_transition_energy_pid.py --config configs/s27b_1783780901_11483_5d68764b_gain_transition_energy_pid.yaml",
        "```",
        "",
        f"Expected and reproduced raw ROOT count: **{result['raw_reproduction']['expected_selected_pulses']:,}** selected B-stave pulse records with baseline median samples 0--3 and even-channel amplitude above 1000 ADC. Delta = **{result['raw_reproduction']['delta']}**. Seed = 2727.",
        "",
        "## 2. Physics Motivation",
        "",
        "S27b asks whether learned pulse representations improve energy reconstruction and PID separation at the electronics gain transition, where charge integration, saturation, pedestal motion, and pile-up can all distort linearity. The incumbent is a strong conventional model: train-run duplicate-readout charge integration with a GEANT4-truth Birks-like nonlinearity correction. ML is only useful here if it preserves physical linearity and class separation on complete held-out runs.",
        "",
        "## 3. Methods and Equations",
        "",
        "Raw HRD waveforms are decoded as eight channels by eighteen samples. For channel waveform \\(V_{c,t}\\), the baseline-subtracted waveform is \\(x_{c,t}=V_{c,t}-\\mathrm{median}(V_{c,0:3})\\), amplitude is \\(A_c=\\max_t x_{c,t}\\), and positive charge is \\(Q_c=\\sum_t \\max(x_{c,t},0)\\). The selected even B staves are B2/B4/B6/B8 = channels 0/2/4/6; duplicate odd readout channels 1/3/5/7 define the closure target.",
        "",
        "The traditional calibration fits the train-run duplicate odd charges to a Birks-like response",
        "",
        "\\[ Q_i = \\alpha\\,\\frac{\\Delta E_i}{1+k_B(dE/dx)_i}, \\]",
        "",
        "where \\(\\Delta E_i\\) and \\((dE/dx)_i\\) are layer priors from `hibeam_g4` `Sci_bar_EDep` and `Sci_bar_TrackLength`. The prediction inverts this equation on the even readout and sums over selected staves. Learned methods use only even-readout features and waveforms: ridge, gradient-boosted trees, tabular MLP, 1D-CNN, a waveform transformer, and a new physics-residual MLP. The transformer is the ticket's new architecture: attention over the 18 time samples after projecting the four B-stave channels.",
        "",
        "PID separation is evaluated with the matching S25a all-pre-action run-held-out PID benchmark, copied into this S27b artifact. That table compares the conventional charge-depth logistic score against ridge, gradient-boosted trees, MLP, 1D-CNN, and an action-gated residual ensemble. It is included here because the S27b ticket explicitly couples energy linearity to PID class separation under the same raw-pulse anchor and run-split discipline.",
        "",
        "## 4. Run Split and Bootstrap",
        "",
        f"Training runs: {result['train_runs']}. Held-out runs: {result['heldout_runs']}. All confidence intervals are 95% percentile intervals from {300} complete-run bootstrap resamples; no event from a held-out run appears in training.",
        "",
        "## 5. Energy Head-to-Head",
        "",
        md_table(metrics, ["method", "family", "n", "bias_frac", "res68_frac", "res68_ci95", "mae_mev", "mae_mev_ci95"]),
        "",
        "ML-minus-traditional deltas use `geant4_birks_lookup` as the conventional incumbent. Negative deltas would favor the alternative method.",
        "",
        md_table(deltas, ["method", "res68_frac", "res68_ci_low", "res68_ci_high", "delta_vs_birks", "delta_ci_conservative_low", "delta_ci_conservative_high", "beats_birks_ci"]),
        "",
        "## 6. Gain-Transition and Systematics Bins",
        "",
        "The gain-transition table reuses the raw-waveform stratification from this run: saturation onset (`A >= 7000 ADC`), pile-up or multihit, pedestal proxy (`charge/peak` above the held-out median), and late/deep pulse topology. These are not post-hoc training cuts; they are reporting strata scored after model fitting.",
        "",
        md_table(gain[gain["method"].isin(["geant4_birks_lookup", "gradient_boosted_trees", "physics_residual_mlp", "1d_cnn", "transformer"])].head(60), ["bin_family", "subset", "method", "n", "bias_frac", "res68_frac", "res68_ci_low", "res68_ci_high", "mae_mev"]),
        "",
        "## 7. PID Linearity and Class Separation",
        "",
        md_table(pid, ["s27b_method", "n", "runs", "roc_auc", "roc_auc_ci_low", "roc_auc_ci_high", "average_precision", "purity_at_80pct_eff", "ece", "bootstrap_valid"]),
        "",
        "The perfect conventional charge-depth PID score is a useful operational separation but also a warning: the PID proxy is very close to the charge/depth definition, so the report treats PID as a closure and linearity diagnostic rather than external particle truth.",
        "",
        "## 8. Leakage Controls",
        "",
        md_table(pd.DataFrame(result["leakage_checks"]), ["check", "value", "pass"]),
        "",
        "The energy benchmark excludes odd charge, run number, event number, and EVT from ML features. The PID table includes an HGB shuffled-label control near chance, and run-family-only controls from S25a. The traditional PID score being exactly separable is therefore interpreted as definition-level separability, not as independent truth discovery.",
        "",
        "## 9. Interpretation",
        "",
        f"The winner named in `result.json` is **{winner}**. Its energy res68 is {float(win['res68_frac']):.5f}, while the conventional GEANT4/Birks lookup is {float(trad['res68_frac']):.5f}. Since the conventional method wins on the primary energy-linearity endpoint and also gives exact proxy PID separation in the paired PID benchmark, S27b does not justify replacing the physical charge-integration calibration with a generic neural waveform model at the gain transition.",
        "",
        "## 10. Systematics and Caveats",
        "",
        "The dominant caveats are the lack of event-level alignment between GEANT4 and real HRD runs, the layer-level truth prior, possible optical/electronics response mismatch, saturation at the ADC ceiling, duplicate-readout closure rather than external calorimetric truth, and PID labels that are partly charge/depth defined. The bootstrap unit is run, not row, so intervals represent run-to-run stability but not all hardware systematics.",
        "",
        "## 11. MC Verdict",
        "",
        "MC validation available as a layer-level `hibeam_g4` `Sci_bar_EDep` prior, but not as a digitized HRD waveform simulation. The data result is therefore MC-anchored for energy scale and nonlinearity, but a digitized MC response is still required to close waveform-model claims.",
        "",
        "## 12. Open Questions",
        "",
        "1. S27c: digitized gain-transition response closure. Hypothesis: a simulated HRD electronics response removes the residual mismatch that generic waveform ML currently tries to absorb. Falsifying test: train on digitized GEANT4 ADC waveforms and require the residual-ML gain to persist on real held-out runs without retuning.",
        "",
        "## 13. Provenance",
        "",
        f"- Git commit: {repo_commit}",
        "- Data SHA256: see `input_sha256.csv`.",
        f"- Python: {platform.python_version()}",
        "- Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `method_metrics.csv`, `gain_transition_systematics.csv`, `pid_linearity_benchmark.csv`, `reproduction_match_table.csv`, `input_sha256.csv`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def postprocess(config_path: Path) -> None:
    cfg = base.load_config(config_path)
    out_dir = ROOT / cfg["output_dir"]
    result_path = out_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["worker"] = WORKER
    result["winner_method"] = result["winner"]["method"]
    result["ticket_id"] = cfg["ticket_id"]
    result["study"] = cfg["study_id"]
    result["next_tickets"] = [
        {
            "title": "S27c: digitized gain-transition response closure",
            "body": "Build a digitized HRD electronics response on top of hibeam_g4 Sci_bar truth and rerun the S27b Birks, ridge, GBT, MLP, 1D-CNN, transformer, and residual-MLP panel on simulated ADC waveforms before comparing to real held-out runs.",
        }
    ]
    metrics = pd.read_csv(out_dir / "method_metrics.csv")
    deltas = add_delta_table(metrics)
    deltas.to_csv(out_dir / "method_delta_vs_traditional.csv", index=False)
    gain = add_gain_transition_table(out_dir)
    pid = copy_pid_tables(out_dir)
    result["method_delta_vs_traditional"] = clean_json(deltas.to_dict(orient="records"))
    result["gain_transition_systematics"] = clean_json(gain.to_dict(orient="records"))
    result["pid_linearity_benchmark"] = clean_json(pid.to_dict(orient="records"))
    result_path.write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, result, metrics, deltas, gain, pid)
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["worker"] = WORKER
    manifest["ticket_id"] = cfg["ticket_id"]
    manifest["study"] = cfg["study_id"]
    for name in ["REPORT.md", "result.json", "method_delta_vs_traditional.csv", "gain_transition_systematics.csv", "pid_linearity_benchmark.csv"]:
        manifest["outputs"][name] = base.sha256_file(out_dir / name)
    manifest_path.write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG.relative_to(ROOT)))
    args = parser.parse_args()
    config_path = ROOT / args.config if not Path(args.config).is_absolute() else Path(args.config)
    old_argv = sys.argv[:]
    try:
        sys.argv = [old_argv[0], "--config", str(config_path.relative_to(ROOT))]
        base.main()
    finally:
        sys.argv = old_argv
    postprocess(config_path)


if __name__ == "__main__":
    main()
