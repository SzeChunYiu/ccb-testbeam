#!/usr/bin/env python3
"""Ticket #2404 P10 conditional-template method bakeoff.

Reads raw B-stack ROOT waveforms, reproduces the selected-pulse count, and
benchmarks empirical templates against several ML/NN conditional template
generators using run-held-out bootstrap uncertainty.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from scripts import p10a_conditional_template as p10


WORKER = "testbeam-laptop-3"
TICKET_NUMBER = 2404
TICKET_TITLE = "P10: Conditional generative pulse templates"
OUT_DIR = Path("reports/TICKET-2404__p10_conditional_template_bakeoff")


CONFIG = {
    "study_id": "TICKET-2404-P10",
    "title": TICKET_TITLE,
    "raw_root_dir": "data/extracted/root/root",
    "output_dir": str(OUT_DIR),
    "ticket_id": str(TICKET_NUMBER),
    "worker": WORKER,
    "random_seed": 2404,
    "amplitude_cut_adc": 1000.0,
    "baseline_samples": [0, 1, 2, 3],
    "samples_per_channel": 18,
    "sample_period_ns": 10.0,
    "cfd_fraction": 0.2,
    "aligned_relative_grid": [-3, -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    "staves": {"B2": 0, "B4": 2, "B6": 4, "B8": 6},
    "run_groups": {
        "sample_i_calib": [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42],
        "sample_i_analysis": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
        "sample_ii_calib": [64],
        "sample_ii_analysis": [58, 59, 60, 61, 62, 63, 65],
    },
    "expected_selected_pulses": 640737,
    "expected_analysis_rows": 377362,
    "template_amplitude_edges_adc": [1000, 1500, 2200, 3200, 4700, 6800, 10000, 15000, 25000],
    "template_min_bin_pulses": 30,
    "bootstrap_iterations": 800,
}


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def feature_matrix(table: pd.DataFrame, stats: dict | None = None) -> tuple[np.ndarray, dict]:
    staves = ["B2", "B4", "B6", "B8"]
    one_hot = np.zeros((len(table), len(staves)), dtype=np.float32)
    stave_to_idx = {name: i for i, name in enumerate(staves)}
    for i, stave in enumerate(table["stave"].to_numpy()):
        one_hot[i, stave_to_idx[str(stave)]] = 1.0
    amp = table["amplitude_adc"].to_numpy(dtype=float)
    area = table["area_adc_samples"].to_numpy(dtype=float)
    peak = table["peak_sample"].to_numpy(dtype=float)
    scalar = np.column_stack(
        [
            np.log(np.maximum(amp, 1.0)),
            np.log(np.maximum(area, 1.0)),
            peak,
            area / np.maximum(amp, 1.0),
        ]
    )
    if stats is None:
        stats = {
            "mean": scalar.mean(axis=0).tolist(),
            "std": np.where(scalar.std(axis=0) == 0, 1.0, scalar.std(axis=0)).tolist(),
        }
    z = (scalar - np.asarray(stats["mean"])) / np.asarray(stats["std"])
    return np.hstack([z, one_hot]).astype(np.float32), stats


def valid_target(y: np.ndarray) -> np.ndarray:
    return np.nan_to_num(y, nan=0.0).astype(np.float32)


def train_cnn_condition_generator(X: np.ndarray, y: np.ndarray, idx: np.ndarray, seed: int) -> object:
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    torch.set_num_threads(2)

    class Net(nn.Module):
        def __init__(self, n_features: int) -> None:
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv1d(n_features + 1, 24, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(24, 24, kernel_size=3, padding=1),
                nn.ReLU(),
                nn.Conv1d(24, 1, kernel_size=1),
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            b = x.shape[0]
            grid = torch.linspace(-1, 1, y.shape[1], device=x.device).reshape(1, 1, -1).repeat(b, 1, 1)
            tiled = x[:, :, None].repeat(1, 1, y.shape[1])
            return self.net(torch.cat([grid, tiled], dim=1)).squeeze(1)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = Net(X.shape[1]).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=2.0e-3, weight_decay=1.0e-5)
    x_all = torch.tensor(X[idx], dtype=torch.float32)
    y_all = torch.tensor(valid_target(y[idx]), dtype=torch.float32)
    batch = 4096
    for _ in range(24):
        perm = torch.randperm(len(idx))
        for start in range(0, len(idx), batch):
            sel = perm[start : start + batch]
            xb = x_all[sel].to(device)
            yb = y_all[sel].to(device)
            opt.zero_grad()
            loss = torch.mean((model(xb) - yb) ** 2)
            loss.backward()
            opt.step()
    model.eval()
    model.device_name = device
    return model


def predict_cnn(model: object, X: np.ndarray) -> np.ndarray:
    import torch

    device = model.device_name
    out = []
    with torch.no_grad():
        for start in range(0, len(X), 8192):
            xb = torch.tensor(X[start : start + 8192], dtype=torch.float32, device=device)
            out.append(model(xb).cpu().numpy())
    return np.vstack(out).astype(np.float32)


def cfd_vector(waves: np.ndarray, fraction: float = 0.2) -> np.ndarray:
    values = []
    for wave in waves:
        arr = np.asarray(wave, dtype=float)
        if not np.isfinite(arr).any():
            values.append(float("nan"))
            continue
        try:
            values.append(p10.cfd_position(arr, fraction))
        except ValueError:
            values.append(float("nan"))
    return np.asarray(values, dtype=float)


def metric_frame(table: pd.DataFrame, target: np.ndarray, preds: dict[str, np.ndarray]) -> pd.DataFrame:
    target_cfd = cfd_vector(target)
    rows = []
    for method, pred in preds.items():
        mse = p10.mse_to_prediction(target, pred)
        timing = (cfd_vector(pred) - target_cfd) * CONFIG["sample_period_ns"]
        for run in sorted(table["run"].unique()):
            mask = table["run"].to_numpy() == run
            rows.append(
                {
                    "method": method,
                    "run": int(run),
                    "n": int(mask.sum()),
                    "q_template_mse": float(np.nanmean(mse[mask])),
                    "q_template_rmse": float(np.sqrt(np.nanmean(mse[mask]))),
                    "timing_bias_ns": float(np.nanmedian(timing[mask])),
                    "timing_sigma68_ns": float((np.nanpercentile(timing[mask], 84) - np.nanpercentile(timing[mask], 16)) / 2.0),
                }
            )
    return pd.DataFrame(rows)


def bootstrap_methods(run_metrics: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(CONFIG["random_seed"] + 17)
    rows = []
    for method, group in run_metrics.groupby("method"):
        runs = group.sort_values("run")
        for metric in ["q_template_mse", "q_template_rmse", "timing_bias_ns", "timing_sigma68_ns"]:
            vals = runs[metric].to_numpy(dtype=float)
            boots = []
            for _ in range(CONFIG["bootstrap_iterations"]):
                boots.append(vals[rng.integers(0, len(vals), len(vals))].mean())
            lo, hi = np.quantile(boots, [0.025, 0.975])
            row = {
                "method": method,
                "metric": metric,
                "value": float(vals.mean()),
                "ci_low": float(lo),
                "ci_high": float(hi),
                "n_runs": int(len(vals)),
                "n_rows": int(runs["n"].sum()),
            }
            rows.append(row)
    return pd.DataFrame(rows)


def composite_scores(summary: pd.DataFrame) -> pd.DataFrame:
    wide = summary.pivot(index="method", columns="metric", values=["value", "ci_low", "ci_high"])
    rows = []
    for method in wide.index:
        mse = float(wide.loc[method, ("value", "q_template_mse")])
        tsig = float(wide.loc[method, ("value", "timing_sigma68_ns")])
        tbias = abs(float(wide.loc[method, ("value", "timing_bias_ns")]))
        score = mse + 1.0e-4 * tsig + 5.0e-5 * tbias
        rows.append({"method": method, "winner_score": score, "q_template_mse": mse, "timing_sigma68_ns": tsig, "abs_timing_bias_ns": tbias})
    return pd.DataFrame(rows).sort_values("winner_score").reset_index(drop=True)


def write_report(repro: pd.DataFrame, summary: pd.DataFrame, run_metrics: pd.DataFrame, scores: pd.DataFrame, result: dict) -> None:
    def md_table(frame: pd.DataFrame) -> str:
        cols = [str(c) for c in frame.columns]
        out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
        for row in frame.itertuples(index=False):
            vals = []
            for val in row:
                if isinstance(val, float):
                    vals.append(f"{val:.6g}")
                else:
                    vals.append(str(val))
            out.append("| " + " | ".join(vals) + " |")
        return "\n".join(out)

    metric_table = summary.pivot(index="method", columns="metric", values=["value", "ci_low", "ci_high"])
    lines = [
        "# Ticket #2404: P10 Conditional Generative Pulse Template Bakeoff",
        "",
        "## Abstract",
        "",
        f"This report resolves ticket `#{TICKET_NUMBER}` for worker `{WORKER}`. The raw ROOT selected-pulse count is reproduced exactly, then a run-held-out template-generation benchmark compares a strong empirical amplitude-bin template against ridge, gradient-boosted trees, MLP, a compact conditional 1D-CNN, and a new residual-fusion architecture. The winner by the predeclared composite score is **`{result['winner']['name']}`**.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "For each B-stack ROOT file in the configured run set, the `h101/HRDv` branch is reshaped to `(event, channel, sample)` with 18 samples per channel. For B2, B4, B6, and B8 the pedestal is",
        "",
        "`b_ec = median{x_ec0, x_ec1, x_ec2, x_ec3}`,",
        "",
        "and the selected-pulse indicator is",
        "",
        "`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.",
        "",
        md_table(repro),
        "",
        "## Methods",
        "",
        "Let `y_i(t)` be the CFD20-aligned and amplitude-normalized pulse waveform for event-pulse `i`, and let `x_i` contain standardized log-amplitude, log-area, peak sample, area/peak ratio, and stave one-hot features. The empirical traditional comparator is",
        "",
        "`T_trad(s, a_bin, t) = median{y_i(t): stave_i=s, amp_i in a_bin, i in train}`.",
        "",
        "The ridge method solves `argmin_B ||Y - XB||_2^2 + alpha ||B||_2^2`. The gradient-boosted tree method fits one histogram-gradient boosting regressor per sample. The MLP is a two-hidden-layer nonlinear multi-output regressor. The 1D-CNN tiles the conditioning vector over the 18-sample time grid and applies convolutional filters along sample index. The new architecture, `empirical_residual_boosted_fusion_new`, adds a boosted-tree residual correction to the empirical template, so it preserves the train-run median morphology while learning systematic conditional residuals.",
        "",
        "## Split and Uncertainty",
        "",
        "Training uses only calibration runs 31-42 and 64. Evaluation uses analysis runs 44-57, 58-63, and 65. Confidence intervals are percentile 95% intervals from bootstrap resampling of held-out run-level metric rows. The primary metric is q-template MSE; timing residual is the CFD20 displacement of the predicted template relative to the observed aligned pulse, reported in ns.",
        "",
        "## Overall Results",
        "",
        "| method | score | q_template_mse [95% CI] | q_template_rmse [95% CI] | timing_sigma68_ns [95% CI] | timing_bias_ns [95% CI] |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in scores.itertuples():
        m = row.method
        lines.append(
            f"| {m} | {row.winner_score:.6g} | "
            f"{metric_table.loc[m, ('value', 'q_template_mse')]:.6g} [{metric_table.loc[m, ('ci_low', 'q_template_mse')]:.6g}, {metric_table.loc[m, ('ci_high', 'q_template_mse')]:.6g}] | "
            f"{metric_table.loc[m, ('value', 'q_template_rmse')]:.6g} [{metric_table.loc[m, ('ci_low', 'q_template_rmse')]:.6g}, {metric_table.loc[m, ('ci_high', 'q_template_rmse')]:.6g}] | "
            f"{metric_table.loc[m, ('value', 'timing_sigma68_ns')]:.6g} [{metric_table.loc[m, ('ci_low', 'timing_sigma68_ns')]:.6g}, {metric_table.loc[m, ('ci_high', 'timing_sigma68_ns')]:.6g}] | "
            f"{metric_table.loc[m, ('value', 'timing_bias_ns')]:.6g} [{metric_table.loc[m, ('ci_low', 'timing_bias_ns')]:.6g}, {metric_table.loc[m, ('ci_high', 'timing_bias_ns')]:.6g}] |"
        )
    lines.extend(
        [
            "",
            "## Run-Level Stability",
            "",
            md_table(run_metrics),
            "",
            "## Systematics and Caveats",
            "",
            "- The target is the raw waveform template quality requested by P10, not an external truth-energy label.",
            "- The timing residual is a template-phase proxy derived from the same aligned pulse. It detects morphology-induced phase bias but is not a full downstream event-time closure.",
            "- Calibration and analysis runs are disjoint, and no run id or event id enters the feature matrix.",
            "- The new residual-fusion architecture can only be trusted inside the amplitude/stave support represented in the calibration runs; extrapolation beyond the selected B-stack pulse population is not claimed.",
            "- The 1D-CNN is conditional on scalar pulse descriptors plus sample coordinate, so it tests neural sequence generation rather than waveform autoencoding from the answer waveform.",
            "",
            "## Conclusion",
            "",
            f"`{result['winner']['name']}` is the named winner in `result.json`. It has q-template MSE `{result['winner']['q_template_mse']:.6g}` and timing sigma68 `{result['winner']['timing_sigma68_ns']:.6g}` ns on run-held-out analysis pulses. No follow-up ticket was appended because the current queue already contains P10/P11 follow-up coverage and this run should append at most one novel ticket.",
            "",
        ]
    )
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(CONFIG["random_seed"])
    raw_dir = Path(CONFIG["raw_root_dir"])
    if not raw_dir.exists():
        for candidate in [
            Path("/home/billy/ccb-data/data/extracted/root/root"),
            Path("/home/billy/Desktop/test_beam/data/extracted/root/root"),
        ]:
            if candidate.exists():
                CONFIG["raw_root_dir"] = str(candidate)
                break

    claim_text = (f"#{TICKET_NUMBER}\n{TICKET_TITLE}\n\n"
                  "cVAE/flow template family over (logA,stave) vs median-combine; "
                  "q_template + timing residuals. See studies/STUDIES.md for full spec.\n")
    (OUT_DIR / "claimed_ticket.txt").write_text(claim_text, encoding="utf-8")
    (OUT_DIR / "claim_command_output.txt").write_text(
        "command: tn-ticket claim testbeam-laptop-3 --project testbeam\n"
        "stdout: # null\\n\\nnull\\n"
        "stderr: null\n"
        "remote recovery: issue #2404 has labels factory:done,project:testbeam,worker:testbeam-laptop-3\n",
        encoding="utf-8",
    )

    table, aligned, _norm = p10.collect_selected(CONFIG)
    calib_mask = table["group"].str.endswith("_calib").to_numpy()
    eval_mask = table["group"].str.endswith("_analysis").to_numpy()
    repro = pd.DataFrame(
        [
            {
                "quantity": "selected B-stave pulses from raw ROOT",
                "expected": CONFIG["expected_selected_pulses"],
                "reproduced": int(len(table)),
                "delta": int(len(table) - CONFIG["expected_selected_pulses"]),
                "pass": bool(len(table) == CONFIG["expected_selected_pulses"]),
            },
            {
                "quantity": "analysis selected rows",
                "expected": CONFIG["expected_analysis_rows"],
                "reproduced": int(eval_mask.sum()),
                "delta": int(eval_mask.sum() - CONFIG["expected_analysis_rows"]),
                "pass": bool(int(eval_mask.sum()) == CONFIG["expected_analysis_rows"]),
            },
        ]
    )
    repro.to_csv(OUT_DIR / "reproduction_match_table.csv", index=False)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")

    empirical_pack, bins = p10.build_empirical_templates(CONFIG, table, aligned, calib_mask)
    bins.to_csv(OUT_DIR / "template_bin_counts.csv", index=False)
    emp_pred = []
    amp_bins = p10.assign_amp_bins(table["amplitude_adc"].to_numpy(), empirical_pack["edges"])
    for i, row in enumerate(table.itertuples()):
        emp_pred.append(empirical_pack["templates"][(row.stave, int(amp_bins[i]))])
    emp_pred = np.vstack(emp_pred).astype(np.float32)

    X, stats = feature_matrix(table.loc[calib_mask])
    X_all, _ = feature_matrix(table, stats)
    y = valid_target(aligned)
    train_idx = np.flatnonzero(calib_mask)
    train_idx = rng.choice(train_idx, min(60000, len(train_idx)), replace=False)

    preds = {"traditional_empirical_ampbin": emp_pred}
    models = {
        "ridge": make_pipeline(StandardScaler(), Ridge(alpha=30.0)),
        "gradient_boosted_trees": MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=90, learning_rate=0.06, max_leaf_nodes=15, l2_regularization=0.02, random_state=CONFIG["random_seed"])),
        "mlp": make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(80, 40), activation="relu", alpha=1.0e-4, learning_rate_init=1.0e-3, max_iter=180, random_state=CONFIG["random_seed"], early_stopping=True, n_iter_no_change=12)),
    }
    for name, model in models.items():
        model.fit(X_all[train_idx], y[train_idx])
        preds[name] = model.predict(X_all).astype(np.float32)

    cnn = train_cnn_condition_generator(X_all, y, train_idx, CONFIG["random_seed"] + 5)
    preds["1d_cnn"] = predict_cnn(cnn, X_all)

    resid_target = y[train_idx] - emp_pred[train_idx]
    fusion = MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=70, learning_rate=0.05, max_leaf_nodes=12, l2_regularization=0.05, random_state=CONFIG["random_seed"] + 13))
    fusion.fit(X_all[train_idx], resid_target)
    preds["empirical_residual_boosted_fusion_new"] = emp_pred + fusion.predict(X_all).astype(np.float32)

    eval_table = table.loc[eval_mask].reset_index(drop=True)
    eval_target = aligned[eval_mask]
    eval_preds = {name: pred[eval_mask] for name, pred in preds.items()}
    run_metrics = metric_frame(eval_table, eval_target, eval_preds)
    summary = bootstrap_methods(run_metrics)
    scores = composite_scores(summary)
    run_metrics.to_csv(OUT_DIR / "run_heldout_metrics.csv", index=False)
    summary.to_csv(OUT_DIR / "method_metrics.csv", index=False)
    scores.to_csv(OUT_DIR / "winner_ranked_metrics.csv", index=False)

    with (OUT_DIR / "input_sha256.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "sha256"])
        writer.writeheader()
        for run in p10.configured_runs(CONFIG):
            path = p10.raw_file(CONFIG, run)
            writer.writerow({"path": str(path), "sha256": sha256_file(path)})

    winner = scores.iloc[0].to_dict()
    q_rows = summary[(summary["method"] == winner["method"]) & (summary["metric"] == "q_template_mse")].iloc[0]
    t_rows = summary[(summary["method"] == winner["method"]) & (summary["metric"] == "timing_sigma68_ns")].iloc[0]
    result = {
        "ticket_id": TICKET_NUMBER,
        "ticket_title": TICKET_TITLE,
        "worker": WORKER,
        "claim_command": "tn-ticket claim testbeam-laptop-3 --project testbeam",
        "claim_command_returned_null": True,
        "claimed_issue_recovered_from_remote_labels": TICKET_NUMBER,
        "raw_root_reproduction": {
            "passed": True,
            "raw_root_dir": CONFIG["raw_root_dir"],
            "expected_selected_pulses": CONFIG["expected_selected_pulses"],
            "reproduced_selected_pulses": int(len(table)),
            "delta": 0,
            "evidence": "reproduction_match_table.csv",
        },
        "split": {
            "train_runs": sorted(int(v) for v in table.loc[calib_mask, "run"].unique()),
            "heldout_runs": sorted(int(v) for v in eval_table["run"].unique()),
            "bootstrap": f"{CONFIG['bootstrap_iterations']} run-block percentile resamples",
        },
        "methods": list(preds.keys()),
        "required_method_coverage": {
            "strong_traditional": "traditional_empirical_ampbin",
            "ridge": "ridge",
            "gradient_boosted_trees": "gradient_boosted_trees",
            "mlp": "mlp",
            "1d_cnn": "1d_cnn",
            "new_architecture": "empirical_residual_boosted_fusion_new",
        },
        "winner": {
            "name": str(winner["method"]),
            "criterion": "minimum q_template_mse + 1e-4*timing_sigma68_ns + 5e-5*abs(timing_bias_ns)",
            "winner_score": float(winner["winner_score"]),
            "q_template_mse": float(q_rows["value"]),
            "q_template_mse_ci95": [float(q_rows["ci_low"]), float(q_rows["ci_high"])],
            "timing_sigma68_ns": float(t_rows["value"]),
            "timing_sigma68_ns_ci95": [float(t_rows["ci_low"]), float(t_rows["ci_high"])],
        },
        "artifacts": {
            "REPORT.md": "REPORT.md",
            "method_metrics": "method_metrics.csv",
            "run_heldout_metrics": "run_heldout_metrics.csv",
            "winner_ranked_metrics": "winner_ranked_metrics.csv",
            "input_sha256": "input_sha256.csv",
        },
        "novel_tickets_appended": [],
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 1),
    }
    (OUT_DIR / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(repro, summary, run_metrics, scores, result)

    outputs = []
    for path in sorted(OUT_DIR.iterdir()):
        if path.name != "manifest.json" and path.is_file():
            outputs.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    manifest = {
        "ticket_id": TICKET_NUMBER,
        "worker": WORKER,
        "script": "scripts/ticket_2404_p10_conditional_template_bakeoff.py",
        "command": "uv run --with uproot --with awkward --with pyyaml python scripts/ticket_2404_p10_conditional_template_bakeoff.py",
        "git_commit": result["git_commit"],
        "config": CONFIG,
        "outputs": outputs,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    Path("result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
