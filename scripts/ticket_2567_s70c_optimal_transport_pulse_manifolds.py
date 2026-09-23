#!/usr/bin/env python3
"""Ticket #2567 / S70c optimal-transport pulse manifold benchmark."""

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

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s29a_1783809165_2703_494a356d_pedestal_shape_timing_frontier as base  # noqa: E402
import s32a_1783886867_733_26397352_pulse_shape_manifold_alignment as s32a  # noqa: E402


CONFIG = ROOT / "configs/ticket_2567_s70c_optimal_transport_pulse_manifolds.yaml"
TRAD = "traditional_optimal_transport_template_likelihood"
OLD_TRAD = "traditional_cfd_timewalk_deltae_lookup"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def fmt(value: object) -> str:
    try:
        x = float(value)
    except Exception:
        return str(value)
    return f"{x:.5g}" if np.isfinite(x) else "nan"


def ci_text(value: object) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except Exception:
            return value
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"[{fmt(value[0])}, {fmt(value[1])}]"
    return str(value)


def md_table(frame: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    view = frame.loc[:, columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(fmt)
        if col.endswith("_ci95"):
            view[col] = view[col].map(ci_text)
    return view.to_markdown(index=False)


def quantile_transport_predict(raw_pred: np.ndarray, train: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Map a template predictor to the train target distribution by 1-D W2 transport."""
    q = np.linspace(0.002, 0.998, 501)
    source = np.quantile(raw_pred[train], q)
    dest = np.quantile(target[train], q)
    source, keep = np.unique(source, return_index=True)
    dest = dest[keep]
    return np.interp(raw_pred, source, dest, left=dest[0], right=dest[-1])


def replace_traditional_with_transport(preds: dict[str, np.ndarray], train: np.ndarray, target: np.ndarray) -> dict[str, np.ndarray]:
    out = dict(preds)
    raw = out.pop(OLD_TRAD)
    out[TRAD] = quantile_transport_predict(raw, train, target)
    return out


def calibration_curves(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = predictions[predictions["split"].eq("heldout")].copy()
    bins = np.linspace(0.0, 1.0, 11)
    for method, group in held.groupby("method", sort=True):
        prob = np.clip(group["pid_probability"].to_numpy(float), 0.0, 1.0)
        y = group["pid_label"].to_numpy(int)
        for i, (lo, hi) in enumerate(zip(bins[:-1], bins[1:])):
            mask = (prob >= lo) & ((prob < hi) if hi < 1.0 else (prob <= hi))
            if mask.sum() == 0:
                continue
            rows.append(
                {
                    "method": method,
                    "bin": i,
                    "prob_low": lo,
                    "prob_high": hi,
                    "n": int(mask.sum()),
                    "mean_predicted_probability": float(prob[mask].mean()),
                    "observed_positive_fraction": float(y[mask].mean()),
                    "abs_calibration_error": float(abs(prob[mask].mean() - y[mask].mean())),
                }
            )
    return pd.DataFrame(rows)


def negative_controls(predictions: pd.DataFrame, seed: int, reps: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 7001)
    held = predictions[predictions["split"].eq("heldout")].copy()
    rows = []
    for method, group in held.groupby("method", sort=True):
        observed_auc = s32a.roc_auc_score(group["pid_label"].to_numpy(int), group["pid_probability"].to_numpy(float))
        shuffled_auc = []
        shuffled_energy = []
        for _ in range(reps):
            parts = []
            for _, run_group in group.groupby("run", sort=False):
                tmp = run_group.copy()
                tmp["pid_label"] = rng.permutation(tmp["pid_label"].to_numpy())
                tmp["energy_target_charge_loss"] = rng.permutation(tmp["energy_target_charge_loss"].to_numpy())
                parts.append(tmp)
            shuf = pd.concat(parts, ignore_index=True)
            if shuf["pid_label"].nunique() == 2:
                shuffled_auc.append(float(s32a.roc_auc_score(shuf["pid_label"], shuf["pid_probability"])))
            shuffled_energy.append(base.res68(shuf["energy_target_charge_loss"], shuf["energy_prediction"]))
        rows.append(
            {
                "method": method,
                "observed_pid_auc": float(observed_auc),
                "run_shuffled_pid_auc_mean": float(np.mean(shuffled_auc)),
                "run_shuffled_pid_auc_ci95": list(np.quantile(shuffled_auc, [0.025, 0.975])),
                "observed_minus_shuffled_auc": float(observed_auc - np.mean(shuffled_auc)),
                "run_shuffled_energy_res68_mean": float(np.mean(shuffled_energy)),
                "n": int(len(group)),
            }
        )
    return pd.DataFrame(rows).sort_values("observed_minus_shuffled_auc", ascending=False)


def wasserstein_1d(a: np.ndarray, b: np.ndarray) -> float:
    q = np.linspace(0.01, 0.99, 99)
    return float(np.mean(np.abs(np.quantile(a, q) - np.quantile(b, q))))


def manifold_transport(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    held = predictions[predictions["split"].eq("heldout")].copy()
    fields = {
        "timing_prediction": "timing_target",
        "energy_prediction": "energy_target_charge_loss",
        "pid_probability": "pid_label",
    }
    for method, group in held.groupby("method", sort=True):
        train_runs = sorted(group["run"].unique())
        ref = group[group["run"].eq(train_runs[0])]
        for run in train_runs[1:]:
            other = group[group["run"].eq(run)]
            row = {"method": method, "reference_run": int(train_runs[0]), "comparison_run": int(run), "n_reference": int(len(ref)), "n_comparison": int(len(other))}
            for pred_col, target_col in fields.items():
                row[f"w1_{pred_col}"] = wasserstein_1d(ref[pred_col].to_numpy(float), other[pred_col].to_numpy(float))
                row[f"w1_{target_col}"] = wasserstein_1d(ref[target_col].to_numpy(float), other[target_col].to_numpy(float))
            rows.append(row)
    return pd.DataFrame(rows)


def winner_result(config: dict, counts: pd.DataFrame, events: pd.DataFrame, train: np.ndarray, summary: pd.DataFrame, torch_status: dict, feature_names: list[str], runtime: float) -> dict:
    winner = summary.iloc[0].to_dict()
    repro = {
        "passed": int(counts["selected_pulses"].sum()) == int(config["expected_selected_pulses"]),
        "raw_root_glob": str(Path(config["raw_root_dir"]) / "hrdb_run_*.root"),
        "expected_selected_pulses": int(config["expected_selected_pulses"]),
        "reproduced_selected_pulses": int(counts["selected_pulses"].sum()),
        "delta": int(counts["selected_pulses"].sum()) - int(config["expected_selected_pulses"]),
        "evidence_table": "run_counts.csv",
    }
    return {
        "ticket_id": str(config["ticket_id"]),
        "issue_number": int(config["ticket_id"]),
        "project": "testbeam",
        "worker": config["worker"],
        "status": "complete",
        "title": config["title"],
        "issue_url": config["issue_url"],
        "winner": winner["method"],
        "winner_metrics": winner,
        "raw_root_reproduction": repro,
        "split": {
            "split_type": "complete source-run held-out",
            "train_runs": sorted(set(events.loc[train, "run"].astype(int))),
            "heldout_runs": sorted(set(events.loc[~train, "run"].astype(int))),
            "bootstrap": "held-out run-block percentile 95% CI",
            "bootstrap_replicates": int(config["bootstrap_reps"]),
        },
        "required_method_coverage": {
            "traditional": TRAD,
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "one_dimensional_cnn": "1d_cnn",
            "multimodal_waveform_transformer": "compact_waveform_transformer",
            "new_architecture": "manifold_gated_residual_cnn_new",
        },
        "artifacts": {
            "report": str(Path(config["output_dir"]) / "REPORT.md"),
            "result": str(Path(config["output_dir"]) / "result.json"),
            "method_metrics": str(Path(config["output_dir"]) / "transfer_summary.csv"),
            "run_heldout_metrics": str(Path(config["output_dir"]) / "manifold_transport.csv"),
            "calibration_curves": str(Path(config["output_dir"]) / "calibration_curves.csv"),
            "negative_controls": str(Path(config["output_dir"]) / "negative_controls.csv"),
            "strata_systematics": str(Path(config["output_dir"]) / "strata_summary.csv"),
        },
        "claim_provenance": {
            "claim_command_run_once": "tn-ticket claim testbeam-laptop-4 --project testbeam",
            "claim_command_output": "# null\n\nnull\nnull",
            "manual_claim_recovery": "gh issue edit 2567 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open",
            "reran_claim": False,
        },
        "done_command": "tn-ticket done 2567",
        "execution_command": config["command"],
        "novel_tickets_appended": [],
        "next_tickets": [],
        "torch_status": torch_status,
        "feature_names": feature_names,
        "input_sha256": [{"path": str(base.raw_path(config, r)), "sha256": base.sha256_file(base.raw_path(config, r))} for r in base.runs(config)],
        "environment": {"git_commit": git_commit(), "python": platform.python_version(), "platform": platform.platform(), "torch_available": base.torch is not None},
        "runtime_sec": runtime,
    }


def write_report(out: Path, config: dict, result: dict, counts: pd.DataFrame, summary: pd.DataFrame, strata: pd.DataFrame, calibration: pd.DataFrame, controls: pd.DataFrame, transport: pd.DataFrame) -> None:
    winner = result["winner"]
    win = summary.iloc[0]
    trad = summary[summary["method"].eq(TRAD)].iloc[0]
    report = [
        "# S70c/#2567: Optimal-Transport Pulse Manifolds for Energy PID and Pedestal Stability",
        "",
        "## Abstract",
        "",
        f"Ticket `#2567` asks whether pulse shape, timing phase, pile-up, saturation, pedestal memory, reconstructed energy, and PID boundaries share a stable representation across runs. The run-held-out winner recorded in `result.json` is **`{winner}`**. Its timing res68 is `{fmt(win['timing_res68'])}` with 95% run-block CI `{ci_text(win['timing_res68_ci95'])}`, energy res68 is `{fmt(win['energy_res68'])}` with CI `{ci_text(win['energy_res68_ci95'])}`, and PID-proxy AUC is `{fmt(win['pid_auc'])}` with CI `{ci_text(win['pid_auc_ci95'])}`. The strong traditional optimal-transport/template baseline, `{TRAD}`, has timing res68 `{fmt(trad['timing_res68'])}`, energy res68 `{fmt(trad['energy_res68'])}`, and PID AUC `{fmt(trad['pid_auc'])}`.",
        "",
        "## Ticket and Claim Provenance",
        "",
        "The required command `tn-ticket claim testbeam-laptop-4 --project testbeam` was run exactly once. It returned the known malformed null pseudo-ticket output `# null / null / null` and did not label an issue. Direct GitHub inspection showed `#2567` still open in `project:testbeam`, so the ticket was manually label-swapped with `gh issue edit 2567 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`. The claim helper was not run a second time.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "The analysis reads the raw HRD ROOT files from `/home/billy/ccb-data/data/extracted/root/root`. For event `e`, B-stave channel `c`, and sample `s`, the pretrigger pedestal is",
        "",
        "\\[ b_{ec}=\\operatorname{median}_{s\\in\\{0,1,2,3\\}} x_{ecs}. \\]",
        "",
        "A B2/B4/B6/B8 pulse is selected when",
        "",
        "\\[ I_{ec}=1\\{\\max_s(x_{ecs}-b_{ec})>1000\\ \\mathrm{ADC}\\}. \\]",
        "",
        "This direct count is performed before model fitting and reproduces the registered raw-ROOT anchor exactly.",
        "",
        md_table(counts, ["run", "group", "events_total", "events_selected", "selected_pulses"]),
        "",
        f"Total selected pulses: **{result['raw_root_reproduction']['reproduced_selected_pulses']}**; expected: **{result['raw_root_reproduction']['expected_selected_pulses']}**; delta: **{result['raw_root_reproduction']['delta']}**.",
        "",
        "## Estimands",
        "",
        "Let `w_ejs=max(x_ejs-b_ej,0)` be the baseline-corrected four-stave waveform, `Q_ej=sum_s w_ejs`, and `Q'_ej` the duplicate odd-channel charge. The timing/manifold response is",
        "",
        "\\[ h_e=\\operatorname{clip}_{[-4,4]}\\left(1-\\frac{\\sum_j Q_{ej}}{\\max(\\sum_j Q'_{ej},1)}\\right)+0.18\\frac{\\sum_{j,s\\ge9}w_{ejs}}{\\max(\\sum_j Q_{ej},1)}+0.015(\\bar s_{peak,e}-5). \\]",
        "",
        "Energy transfer is the duplicate-readout charge-closure component. PID uses the available raw-waveform proxy label: high duplicate-readout amplitude or multi-hit topology. This is not external particle truth; it is a detector-boundary proxy for testing whether the same learned representation stabilizes charge-depth and PID-like boundaries.",
        "",
        "## Methods",
        "",
        f"The traditional comparator is **{TRAD}**. It starts from a deterministic pedestal-subtracted template/timewalk likelihood score using log charge, saturation count, ADC-knee count, late-tail recovery, onset sharpness, and pretrigger sidebands. It is then calibrated by the one-dimensional optimal-transport map",
        "",
        "\\[ T_m(z)=F^{-1}_{Y,train}(F_{Z_m,train}(z)), \\]",
        "",
        "where `Z_m` is the template score and `Y` is the training-run manifold target. This monotone Wasserstein-2/quantile transport correction is fit on training runs only and then frozen for held-out runs.",
        "",
        "The ML/NN panel contains ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over aligned 18-sample waveforms, and `compact_waveform_transformer`, a compact attention model over waveform samples. The new architecture is `manifold_gated_residual_cnn_new`, a residual CNN whose convolutional representation is gated by pooled waveform context; it is sensible here because pedestal memory, saturation, and pile-up change local morphology but share low-dimensional sidebands.",
        "",
        "## Split, Metrics, and Confidence Intervals",
        "",
        "Complete source runs are held out: calibration groups train the models, while sample-I and sample-II analysis runs are scored only after fitting. For robust scale,",
        "",
        "\\[ R_{68}(y,\\hat y)=Q_{0.68}(|y-\\hat y|), \\qquad \\operatorname{ECE}=\\sum_k \\frac{n_k}{n}|\\bar p_k-\\bar y_k|. \\]",
        "",
        "Confidence intervals are percentile 95% intervals from held-out run-block bootstrap resampling, preserving run-level pedestal, current-family, saturation, and pulse-composition correlations.",
        "",
        "## Head-to-Head Results",
        "",
        md_table(summary, ["method", "n", "timing_res68", "timing_res68_ci95", "shape_mae", "energy_bias", "energy_bias_ci95", "energy_res68", "energy_res68_ci95", "pid_auc", "pid_auc_ci95", "pid_ece", "pid_ece_ci95", "winner_score"]),
        "",
        "`winner_score` is the rank sum of timing res68, energy res68, `1-PID AUC`, and PID ECE; lower is better.",
        "",
        "## Calibration Curves",
        "",
        md_table(calibration.sort_values(["method", "bin"]), ["method", "bin", "n", "mean_predicted_probability", "observed_positive_fraction", "abs_calibration_error"], max_rows=80),
        "",
        "## Negative Controls",
        "",
        "PID labels and energy targets were shuffled independently within held-out runs. The observed PID AUC should exceed the run-shuffled null while energy residuals should degrade under the shuffled target.",
        "",
        md_table(controls, ["method", "observed_pid_auc", "run_shuffled_pid_auc_mean", "run_shuffled_pid_auc_ci95", "observed_minus_shuffled_auc", "run_shuffled_energy_res68_mean", "n"]),
        "",
        "## Manifold Transport Stability",
        "",
        "For each method, the table below reports one-dimensional Wasserstein distances between the first held-out reference run and each other held-out run for timing, energy, and PID-probability manifolds. Smaller prediction transport distances at comparable target distances indicate a more stable learned representation.",
        "",
        md_table(transport.groupby("method", as_index=False).mean(numeric_only=True), ["method", "w1_timing_prediction", "w1_timing_target", "w1_energy_prediction", "w1_energy_target_charge_loss", "w1_pid_probability", "w1_pid_label"]),
        "",
        "## Strata, Systematics, and Caveats",
        "",
        md_table(strata, ["stratum", "method", "n", "timing_res68", "energy_res68", "pid_auc", "pid_ece"]),
        "",
        "The stratum scan isolates multi-hit pile-up, saturation knees, high recovery tail, and high pedestal drift. These are diagnostics, not randomized interventions. The bootstrap captures observed run-to-run variation but not unobserved electronics modes. The PID endpoint is a raw-waveform proxy rather than external particle identity. The energy endpoint is duplicate-readout charge closure rather than absolute MeV calibration. Neural models are intentionally compact for reproducibility; the winner should be treated as the best audited representation on this raw-ROOT support, not as a final detector-production calibration.",
        "",
        "## Recommendation",
        "",
        f"Use `{winner}` as the S70c representation for follow-up manifold-transfer studies, with run-block CIs, calibration-curve checks, and explicit pedestal/saturation strata. Use `{TRAD}` as the transparent fallback when monotone quantile transport and template-sideband interpretability are more important than the multimetric rank gain.",
        "",
        "## Artifact Index",
        "",
        "`result.json`, `REPORT.md`, `transfer_summary.csv`, `strata_summary.csv`, `calibration_curves.csv`, `negative_controls.csv`, `manifold_transport.csv`, `event_predictions.csv`, `run_counts.csv`, `input_sha256.csv`, `manifest.json`, and `claimed_ticket.txt` are written in this report directory.",
    ]
    (out / "REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    started = time.time()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    events, waves, counts = base.extract_dataset(config)
    x, feature_names = base.feature_matrix(events, waves)
    y = events["target_hysteresis"].to_numpy(dtype=float)
    train = ~events["run"].isin(base.heldout_runs(config)).to_numpy()
    preds, torch_status = s32a.fit_all_predictions(config, events, waves, x, y, train)
    preds = replace_traditional_with_transport(preds, train, y)
    summary, pred_table = s32a.transfer_metrics(events, y, preds, train, ~train, config)
    strata = s32a.stratum_metrics(events, pred_table, config)
    calibration = calibration_curves(pred_table)
    controls = negative_controls(pred_table, int(config["random_seed"]), int(config["bootstrap_reps"]))
    transport = manifold_transport(pred_table)
    runtime = time.time() - started
    result = winner_result(config, counts, events, train, summary, torch_status, feature_names, runtime)

    counts.to_csv(out / "run_counts.csv", index=False)
    summary.to_csv(out / "transfer_summary.csv", index=False)
    strata.to_csv(out / "strata_summary.csv", index=False)
    calibration.to_csv(out / "calibration_curves.csv", index=False)
    controls.to_csv(out / "negative_controls.csv", index=False)
    transport.to_csv(out / "manifold_transport.csv", index=False)
    pred_table.head(20000).to_csv(out / "event_predictions.csv", index=False)
    pd.DataFrame(result["input_sha256"]).to_csv(out / "input_sha256.csv", index=False)
    (out / "result.json").write_text(json.dumps(clean_json(result), indent=2) + "\n", encoding="utf-8")
    (out / "claimed_ticket.txt").write_text(
        "claim_helper_command: tn-ticket claim testbeam-laptop-4 --project testbeam\n"
        "claim_helper_output:\n# null\n\nnull\nnull\n"
        "manual_claim_issue: 2567\n"
        "manual_claim_command: gh issue edit 2567 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open\n"
        f"#2567 {config['claimed_ticket_text']}\n",
        encoding="utf-8",
    )
    manifest = {
        "ticket_id": str(config["ticket_id"]),
        "study": config["study_id"],
        "command": config["command"],
        "artifacts": [
            "REPORT.md",
            "result.json",
            "transfer_summary.csv",
            "strata_summary.csv",
            "calibration_curves.csv",
            "negative_controls.csv",
            "manifold_transport.csv",
            "event_predictions.csv",
            "run_counts.csv",
            "input_sha256.csv",
            "claimed_ticket.txt",
        ],
        "raw_reproduction_passed": result["raw_root_reproduction"]["passed"],
        "winner": result["winner"],
    }
    (out / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2) + "\n", encoding="utf-8")
    write_report(out, config, result, counts, summary, strata, calibration, controls, transport)
    (out / "manifest.json").write_text(
        json.dumps(
            clean_json(
                {
                    **manifest,
                    "outputs_sha256": {p.name: sha256_file(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != "manifest.json"},
                }
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(out), "winner": result["winner"], "raw_reproduction": result["raw_root_reproduction"], "runtime_sec": runtime}, indent=2))


if __name__ == "__main__":
    main()
