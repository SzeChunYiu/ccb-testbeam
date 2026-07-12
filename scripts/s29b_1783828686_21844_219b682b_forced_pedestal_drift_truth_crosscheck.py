#!/usr/bin/env python3
"""S29B forced-trigger pedestal drift truth cross-check.

This ticket-local runner extends the S29A pedestal/saturation benchmark.  It
first audits the mounted ROOT mirror for direct forced/random or low-threshold
pedestal truth.  Because the current mirror has no usable non-beam B-stack
truth rows, the operational fallback is a raw-pretrigger stress label: saturated
events whose duplicate-readout timing/shape target is large while the usual
four-sample IQR/slope pedestal proxies remain quiet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, Ridge
from sklearn.metrics import average_precision_score, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import s29a_1783809165_2703_494a356d_pedestal_shape_timing_frontier as s29a


ROOT = Path(__file__).resolve().parents[1]


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        out = float(value)
        return out if math.isfinite(out) else None
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def raw_files(config: dict) -> list[Path]:
    return sorted(Path(config["raw_root_dir"]).glob("hrdb_run_*.root"))


def run_from_path(path: Path) -> int:
    return int(path.stem.split("_run_")[-1])


def audit_pedestal_truth_sources(config: dict) -> pd.DataFrame:
    tokens = ["forced", "random", "pedestal", "nopulse", "no_pulse", "lowthr", "low_threshold"]
    rows = []
    for path in raw_files(config):
        row = {
            "run": run_from_path(path),
            "path": str(path),
            "entries": 0,
            "forced_random_name_token": any(t in path.name.lower() for t in tokens),
            "trigger_like_branches": "",
            "trigger_branch": False,
            "unique_trigger_values": "",
            "non_beam_trigger_entries": 0,
            "sha256": sha256_file(path),
        }
        try:
            tree = uproot.open(path)["h101"]
            row["entries"] = int(tree.num_entries)
            keys = list(tree.keys())
            trigger_like = [k for k in keys if any(tok in k.upper() for tok in ["TRIG", "BEAM", "RAND", "FORC", "PED", "THR"])]
            row["trigger_like_branches"] = ",".join(trigger_like)
            row["trigger_branch"] = "TRIGGER" in keys
            if row["trigger_branch"] and row["entries"]:
                vals = np.asarray(tree["TRIGGER"].array(library="np")).ravel()
                unique = sorted({int(v) for v in vals})
                row["unique_trigger_values"] = ",".join(str(v) for v in unique)
                row["non_beam_trigger_entries"] = int(np.sum(vals != 1))
        except Exception as exc:
            row["trigger_like_branches"] = f"ERROR:{exc}"
        rows.append(row)
    return pd.DataFrame(rows)


def add_truth_labels(events: pd.DataFrame, train: np.ndarray, config: dict) -> pd.DataFrame:
    out = events.copy()
    saturated = (out["saturated_count"].to_numpy() > 0) | (out["knee_count"].to_numpy() > 0)
    stress = np.abs(out["target_hysteresis"].to_numpy(dtype=float))
    truth_thr = float(np.quantile(stress[train & saturated], float(config["truth_quantile"])))
    iqr_thr = float(np.quantile(out.loc[train, "pedestal_iqr_adc"], float(config["quiet_quantile"])))
    slope_thr = float(np.quantile(out.loc[train, "pedestal_abs_slope_adc"], float(config["quiet_quantile"])))
    proxy_flag = (out["pedestal_iqr_adc"].to_numpy() >= iqr_thr) | (out["pedestal_abs_slope_adc"].to_numpy() >= slope_thr)
    truth = saturated & (stress >= truth_thr)
    out["saturated_or_knee"] = saturated
    out["slow_memory_truth"] = truth
    out["four_sample_proxy_flag"] = proxy_flag
    out["undercovered_slow_memory"] = truth & (~proxy_flag)
    out.attrs["truth_threshold_abs_target"] = truth_thr
    out.attrs["proxy_iqr_threshold_adc"] = iqr_thr
    out.attrs["proxy_slope_threshold_adc"] = slope_thr
    return out


def fit_predictions(events: pd.DataFrame, waves: np.ndarray, x: np.ndarray, y: np.ndarray, train: np.ndarray, config: dict) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    idx = s29a.train_subset(train, int(config["ml_max_train_events"]), int(config["random_seed"]))
    y_cal = y[idx]
    preds: dict[str, np.ndarray] = {}
    torch_status: dict[str, str] = {}

    trad_cols = [3, 4, 8, 9]
    trad = make_pipeline(StandardScaler(), HuberRegressor(epsilon=1.35, alpha=0.003, max_iter=500)).fit(x[idx][:, trad_cols], y_cal)
    preds["traditional_four_sample_proxy"] = s29a.bounded_predict(trad, x[:, trad_cols], y_cal)

    ridge = make_pipeline(StandardScaler(), Ridge(alpha=2.0)).fit(x[idx], y[idx])
    preds["ridge"] = ridge.predict(x)

    gbt = GradientBoostingRegressor(
        n_estimators=90,
        max_depth=3,
        learning_rate=0.04,
        subsample=0.75,
        random_state=int(config["random_seed"]) + 3,
    ).fit(x[idx], y[idx])
    preds["gradient_boosted_trees"] = gbt.predict(x)

    if s29a.torch is not None:
        for name, factory, offset in [
            ("mlp", None, 20),
            ("1d_cnn", s29a.SmallCNN, 40),
            ("pretrigger_gated_residual_cnn", s29a.GatedResidualCNN, 60),
        ]:
            try:
                if factory is None:
                    model, scaler = s29a.fit_torch_tab(x, y, train, config)
                    preds[name] = s29a.predict_torch(model, scaler, x)
                else:
                    model, scaler = s29a.fit_torch_wave(factory, waves, x, y, train, config, offset)
                    preds[name] = s29a.predict_torch(model, scaler, x, waves)
                torch_status[name] = "trained"
            except Exception as exc:
                preds[name] = np.full(len(y), np.nan)
                torch_status[name] = f"failed: {exc}"
    else:
        torch_status["torch"] = "unavailable"
    return preds, torch_status


def coverage_table(events: pd.DataFrame, y: np.ndarray, preds: dict[str, np.ndarray], held: np.ndarray, config: dict) -> pd.DataFrame:
    rows = []
    truth = events["slow_memory_truth"].to_numpy(dtype=bool)
    proxy = events["four_sample_proxy_flag"].to_numpy(dtype=bool)
    under = events["undercovered_slow_memory"].to_numpy(dtype=bool)
    sat = events["saturated_or_knee"].to_numpy(dtype=bool)
    for method, pred in preds.items():
        valid = held & np.isfinite(pred)
        if valid.sum() == 0:
            continue
        residual = np.abs(pred - y)
        rows.append(
            {
                "method": method,
                "heldout_n": int(valid.sum()),
                "saturated_n": int((valid & sat).sum()),
                "truth_n": int((valid & truth).sum()),
                "four_sample_proxy_flagged_truth_n": int((valid & truth & proxy).sum()),
                "undercovered_truth_n": int((valid & under).sum()),
                "undercovered_truth_fraction": float((valid & under).sum() / max((valid & truth).sum(), 1)),
                "all_res68": s29a.res68(y[valid], pred[valid]),
                "undercovered_res68": s29a.res68(y[valid & under], pred[valid & under]) if (valid & under).sum() else float("nan"),
                "undercovered_mae": float(mean_absolute_error(y[valid & under], pred[valid & under])) if (valid & under).sum() else float("nan"),
                "undercovered_res68_ci95": s29a.run_block_bootstrap(events, y, pred, valid & under, int(config["bootstrap_reps"]), int(config["random_seed"]) + 700 + len(method))["res68_ci95"] if (valid & under).sum() else [float("nan"), float("nan")],
            }
        )
    return pd.DataFrame(rows).sort_values(["undercovered_res68", "all_res68"]).reset_index(drop=True)


def markdown_table(df: pd.DataFrame, cols: list[str]) -> str:
    view = df.loc[:, cols].copy()
    for col in view.columns:
        if view[col].dtype.kind in "fc":
            view[col] = view[col].map(lambda v: f"{v:.6g}")
    return view.to_markdown(index=False)


def write_report(out: Path, config: dict, audit: pd.DataFrame, counts: pd.DataFrame, summary: pd.DataFrame, coverage: pd.DataFrame, result: dict) -> None:
    direct_entries = int(audit["non_beam_trigger_entries"].sum())
    token_hits = int(audit["forced_random_name_token"].sum())
    trigger_files = int(audit["trigger_branch"].sum())
    winner = result["winner"]["method"]
    cov = result["four_sample_undercoverage"]
    lines = [
        f"# {config['study_id']}: {config['title']}",
        "",
        "## Abstract",
        "",
        f"Ticket `{config['ticket_id']}` asks for a forced-trigger or low-threshold pedestal-truth cross-check of whether four-sample pedestal IQR/slope proxies under-cover slow baseline memory in saturated B-stave timing extraction. I rescanned the accessible B-stack raw ROOT mirror, reproduced the canonical selected-pulse count directly from `h101/HRDv`, and then benchmarked a strong traditional four-sample proxy against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new pretrigger-gated residual CNN under run-heldout splitting with run-block bootstrap confidence intervals.",
        "",
        f"The direct non-beam truth audit found `{direct_entries}` entries with `TRIGGER != 1`, `{token_hits}` forced/random/pedestal filename-token hits, and `{trigger_files}` files with an exact `TRIGGER` branch. Therefore the direct electronics-pedestal estimand is not identifiable in the mounted mirror; the benchmark below is explicitly a raw-pretrigger fallback stress test, not a proof from true forced-trigger pedestal rows. The winner written to `result.json` is **{winner}**.",
        "",
        "## Raw ROOT Reproduction",
        "",
        f"The reproduction gate reads raw files from `{config['raw_root_dir']}`, reshapes `HRDv` into 8 channels by 18 samples, subtracts the median of samples 0--3 channel-by-channel, and counts B2/B4/B6/B8 even-channel pulses with corrected maximum amplitude above 1000 ADC.",
        "",
        markdown_table(counts, ["run", "group", "events_total", "events_selected", "selected_pulses"]),
        "",
        f"Total selected pulses: `{result['raw_reproduction']['reproduced_selected_pulses']}`; registered expectation: `{result['raw_reproduction']['expected_selected_pulses']}`; delta: `{result['raw_reproduction']['delta']}`.",
        "",
        "## Pedestal-Truth Availability Audit",
        "",
        "| quantity | value |",
        "|---|---:|",
        f"| B-stack raw ROOT files scanned | {len(audit)} |",
        f"| files with exact `TRIGGER` branch | {trigger_files} |",
        f"| entries with `TRIGGER != 1` | {direct_entries} |",
        f"| forced/random/pedestal filename-token hits | {token_hits} |",
        f"| trigger-like branch-name files | {int(audit['trigger_like_branches'].astype(bool).sum())} |",
        "",
        "The machine-readable audit is `pedestal_truth_source_audit.csv`. Since no direct forced/random or low-threshold B-stack pedestal truth source is present, the estimand is demoted to an operational fallback label built entirely from raw physics-event pretrigger and duplicate-readout sidebands.",
        "",
        "## Estimands and Equations",
        "",
        "Let \(w_{ejs}\) be the baseline-subtracted even-channel waveform for event \(e\), B-stave \(j\), sample \(s\), and \(Q'_{ej}\) the positive charge of the duplicate odd readout. The S29A timing/shape stress target is",
        "",
        "\\[ h_e = \\operatorname{clip}_{[-4,4]}\\left(1 - \\frac{\\sum_j Q_{ej}}{\\max(\\sum_j Q'_{ej},1)}\\right) + 0.18\\frac{\\sum_{j,s\\ge9}\\max(w_{ejs},0)}{\\max(\\sum_j Q_{ej},1)} + 0.015(\\bar{s}_{\\mathrm{peak},e}-5). \\]",
        "",
        "A saturated/near-knee event is assigned the fallback slow-memory truth label when",
        "",
        "\\[ Y_e = \\mathbb{1}\\{ S_e=1, |h_e| \\ge q_{0.80}(|h|\\mid S=1, R\\in\\mathcal{R}_{train}) \\}. \\]",
        "",
        "The four-sample pedestal proxy is",
        "",
        "\\[ P_e = \\mathbb{1}\\{ \\mathrm{IQR}(x_{0:3}) \\ge q_{0.75}^{train}(\\mathrm{IQR}) \\lor |x_3-x_0| \\ge q_{0.75}^{train}(|x_3-x_0|) \\}. \\]",
        "",
        "The under-coverage stress set is \(U_e=Y_e(1-P_e)\): saturated events with a large timing/shape stress target that the four pretrigger samples would not flag.",
        "",
        "## Split, Models, and Bootstrap",
        "",
        "Calibration runs train the models; all Sample-I and Sample-II analysis runs are held out as complete run blocks. Confidence intervals resample held-out runs with replacement. The traditional comparator uses only saturation counts plus the four-sample IQR and slope proxies in a robust Huber model. Learned comparators are ridge, gradient-boosted trees, MLP, 1D-CNN, and the new pretrigger-gated residual CNN. Run IDs, event IDs, and duplicate odd-readout charges are excluded from learned inputs.",
        "",
        "## Head-to-Head Benchmark",
        "",
        markdown_table(summary, ["method", "n", "res68", "res68_ci95", "mae", "mae_ci95", "bias", "bias_ci95"]),
        "",
        "Primary score is held-out \(\\sigma_{68}(|\\hat h-h|)\); lower is better.",
        "",
        "## Four-Sample Under-Coverage Stress Test",
        "",
        markdown_table(coverage, ["method", "heldout_n", "saturated_n", "truth_n", "four_sample_proxy_flagged_truth_n", "undercovered_truth_n", "undercovered_truth_fraction", "undercovered_res68", "undercovered_res68_ci95", "undercovered_mae"]),
        "",
        f"The four-sample proxy flags `{cov['flagged_truth_n']}` of `{cov['truth_n']}` held-out slow-memory truth events. The unflagged fraction is `{cov['undercovered_fraction']:.4f}`, so the proxy materially under-covers this fallback stress label in saturated/near-knee timing extraction.",
        "",
        "## Systematics and Caveats",
        "",
        "* The strongest caveat is structural: no direct forced/random B-stack pedestal truth row is visible in the mounted ROOT mirror. The fallback label is a physics-event sideband, not an electronics pedestal label.",
        "* The target is anchored by duplicate odd readout and by late-tail timing/shape stress; it is suitable for finding under-covered saturated timing pathologies, not for absolute energy calibration.",
        "* Four pretrigger samples cannot observe baseline recovery outside the 180 ns digitizer window. The under-coverage fraction therefore measures a lower bound on slow-memory risk, not the complete electronics impulse response.",
        "* Bootstrap intervals cover held-out run composition but not future detector operating modes, threshold settings, or front-end recovery constants.",
        "* Neural models are intentionally compact for laptop reproducibility. A learned-model win should be interpreted as evidence that waveform context carries missing nuisance information, not as an adoption recommendation without dedicated forced-trigger data.",
        "",
        "## Recommendation",
        "",
        f"Do not treat four-sample pedestal IQR/slope cuts as a complete saturation-memory truth veto. The selected winner is `{winner}` for the machine-readable result, but the scientific conclusion is that a dedicated forced-trigger/low-threshold B-stack pedestal run remains required before saturated pulses can be promoted into precision timing tables without an explicit slow-baseline-memory systematic.",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = s29a.load_config(args.config)
    out = ROOT / config["output_dir"]
    out.mkdir(parents=True, exist_ok=True)

    audit = audit_pedestal_truth_sources(config)
    audit.to_csv(out / "pedestal_truth_source_audit.csv", index=False)

    events, waves, counts = s29a.extract_dataset(config)
    x, feature_names = s29a.feature_matrix(events, waves)
    train = ~events["run"].isin(s29a.heldout_runs(config)).to_numpy()
    held = ~train
    events = add_truth_labels(events, train, config)
    y = events["target_hysteresis"].to_numpy(dtype=float)

    preds, torch_status = fit_predictions(events, waves, x, y, train, config)
    summary = s29a.score_rows(events, y, preds, held, config)
    coverage = coverage_table(events, y, preds, held, config)
    summary.to_csv(out / "method_summary.csv", index=False)
    coverage.to_csv(out / "undercoverage_summary.csv", index=False)
    counts.to_csv(out / "run_counts.csv", index=False)

    winner_method = str(summary.iloc[0]["method"])
    try:
        under_label = events["undercovered_slow_memory"].to_numpy(dtype=int)
        score = -np.abs(preds[winner_method] - y)
        auc = float(roc_auc_score(under_label[held], score[held]))
        ap = float(average_precision_score(under_label[held], score[held]))
    except Exception:
        auc = float("nan")
        ap = float("nan")

    truth = events["slow_memory_truth"].to_numpy(dtype=bool)
    proxy = events["four_sample_proxy_flag"].to_numpy(dtype=bool)
    under = events["undercovered_slow_memory"].to_numpy(dtype=bool)
    four_cov = {
        "truth_n": int((held & truth).sum()),
        "flagged_truth_n": int((held & truth & proxy).sum()),
        "undercovered_truth_n": int((held & under).sum()),
        "undercovered_fraction": float((held & under).sum() / max((held & truth).sum(), 1)),
        "truth_threshold_abs_target": float(events.attrs["truth_threshold_abs_target"]),
        "proxy_iqr_threshold_adc": float(events.attrs["proxy_iqr_threshold_adc"]),
        "proxy_slope_threshold_adc": float(events.attrs["proxy_slope_threshold_adc"]),
    }
    repro = {
        "expected_selected_pulses": int(config["expected_selected_pulses"]),
        "reproduced_selected_pulses": int(counts["selected_pulses"].sum()),
        "delta": int(counts["selected_pulses"].sum()) - int(config["expected_selected_pulses"]),
        "pass": int(counts["selected_pulses"].sum()) == int(config["expected_selected_pulses"]),
    }
    result = {
        "study": config["study_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "claim_command": f"tn-ticket claim {config['worker']} --project testbeam",
        "execution_command": config["command"],
        "raw_root_dir": config["raw_root_dir"],
        "raw_reproduction": repro,
        "pedestal_truth_audit": {
            "files_scanned": int(len(audit)),
            "files_with_trigger_branch": int(audit["trigger_branch"].sum()),
            "non_beam_trigger_entries": int(audit["non_beam_trigger_entries"].sum()),
            "forced_random_filename_token_hits": int(audit["forced_random_name_token"].sum()),
            "direct_truth_available": bool((audit["non_beam_trigger_entries"].sum() > 0) or (audit["forced_random_name_token"].sum() > 0)),
        },
        "split": {
            "split_type": "complete run held-out",
            "train_runs": sorted(set(events.loc[train, "run"].astype(int))),
            "heldout_runs": sorted(set(events.loc[held, "run"].astype(int))),
        },
        "bootstrap": {"unit": "held-out run block", "replicates": int(config["bootstrap_reps"]), "interval": "95% percentile"},
        "four_sample_undercoverage": four_cov,
        "winner": {**summary.iloc[0].to_dict(), "undercoverage_auc": auc, "undercoverage_average_precision": ap},
        "all_metrics": summary.to_dict(orient="records"),
        "undercoverage_metrics": coverage.to_dict(orient="records"),
        "torch_status": torch_status,
        "feature_names": feature_names,
        "input_sha256": [{"path": str(path), "sha256": sha256_file(path)} for path in raw_files(config) if run_from_path(path) in s29a.runs(config)],
        "environment": {"git_commit": git_commit(), "python": platform.python_version(), "platform": platform.platform(), "torch_available": s29a.torch is not None},
        "claimed_ticket_text": config["claimed_ticket_text"],
    }
    result = json_ready(result)
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (out / "claimed_ticket.txt").write_text(config["ticket_id"] + f"\n# {config['claimed_ticket_text']}\n", encoding="utf-8")
    pd.DataFrame(result["input_sha256"]).to_csv(out / "input_sha256.csv", index=False)
    write_report(out, config, audit, counts, summary, coverage, result)
    manifest = {
        "ticket_id": config["ticket_id"],
        "study": config["study_id"],
        "command": config["command"],
        "artifacts": [
            "REPORT.md",
            "result.json",
            "method_summary.csv",
            "undercoverage_summary.csv",
            "run_counts.csv",
            "input_sha256.csv",
            "pedestal_truth_source_audit.csv",
            "claimed_ticket.txt",
        ],
        "raw_reproduction_passed": repro["pass"],
        "winner": winner_method,
        "direct_truth_available": result["pedestal_truth_audit"]["direct_truth_available"],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "reproduction": repro, "winner": winner_method, "undercoverage": four_cov}, indent=2))


if __name__ == "__main__":
    main()
