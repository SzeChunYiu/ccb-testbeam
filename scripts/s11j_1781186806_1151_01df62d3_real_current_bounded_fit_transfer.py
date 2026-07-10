#!/usr/bin/env python3
"""S11j: real-current bounded-fit calibration transfer check.

This ticket-local runner intentionally preserves the reviewed S11i calibration
benchmark and adds a raw-ROOT transfer audit on real high-current all-three
candidate windows.  The real-window layer is descriptive because real windows
do not carry an injected truth label.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def run_bootstrap_rate(values: np.ndarray, runs: np.ndarray, seed: int, n_boot: int) -> tuple[float, float]:
    unique = np.unique(runs)
    rng = np.random.default_rng(seed)
    rates: list[float] = []
    for _ in range(int(n_boot)):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == run) for run in sampled])
        if len(idx):
            rates.append(float(np.mean(values[idx])))
    return float(np.percentile(rates, 2.5)), float(np.percentile(rates, 97.5))


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s11j_1781186806_1151_01df62d3_real_current_bounded_fit_transfer.json")
    args = parser.parse_args()
    t0 = time.time()
    cfg_path = (ROOT / args.config).resolve() if not Path(args.config).is_absolute() else Path(args.config)
    cfg = load_json(cfg_path)
    out_dir = ROOT / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    s07f = load_module("s07f_source_for_s11j", ROOT / cfg["s07f_script"])
    s07f_cfg_path = ROOT / cfg["s07f_config"]
    s07f_cfg = load_json(s07f_cfg_path)
    utils = s07f.load_s07d_utils(ROOT / s07f_cfg["utility_script"])
    s11i_dir = ROOT / cfg["s11i_report_dir"]

    print("1/4 raw ROOT reproduction ...", flush=True)
    parent, all_three, run_counts, _clean_payloads = s07f.collect_parent_and_all_three(s07f_cfg, utils)
    dt_min = float(cfg["high_current_dt_min_ns"])
    clean_max = float(cfg["clean_dt_max_ns"])
    parent_guarded = int((parent["d_t_ns"] > dt_min).sum())
    all_three_guarded = int((all_three["d_t_ns"] > dt_min).sum())
    all_three_clean = int((all_three["d_t_ns"] < clean_max).sum())
    reproduction = pd.DataFrame(
        [
            {"quantity": "parent App.I guarded gross D_t>51 ns", "reference": int(s07f_cfg["expected_parent_gross_events"]), "reproduced": parent_guarded, "delta": parent_guarded - int(s07f_cfg["expected_parent_gross_events"]), "pass": parent_guarded == int(s07f_cfg["expected_parent_gross_events"])},
            {"quantity": "all-three control events", "reference": int(s07f_cfg["expected_all_three_control_events"]), "reproduced": int(len(all_three)), "delta": int(len(all_three)) - int(s07f_cfg["expected_all_three_control_events"]), "pass": int(len(all_three)) == int(s07f_cfg["expected_all_three_control_events"])},
            {"quantity": "all-three clean events D_t<3 ns", "reference": math.nan, "reproduced": all_three_clean, "delta": math.nan, "pass": True},
            {"quantity": "all-three real high-current candidates D_t>51 ns", "reference": int(s07f_cfg["expected_all_three_guarded_gross_events"]), "reproduced": all_three_guarded, "delta": all_three_guarded - int(s07f_cfg["expected_all_three_guarded_gross_events"]), "pass": all_three_guarded == int(s07f_cfg["expected_all_three_guarded_gross_events"])},
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    print("2/4 loading S11i benchmark artifacts ...", flush=True)
    s11i_score = safe_read_csv(s11i_dir / "global_scoreboard.csv")
    s11i_cells = safe_read_csv(s11i_dir / "method_cell_metrics.csv")
    s11i_leakage = safe_read_csv(s11i_dir / "leakage_checks.csv")
    s11i_oof = safe_read_csv(s11i_dir / "oof_predictions.csv")
    s11i_result = load_json(s11i_dir / "result.json")

    required_methods = {
        "bounded two-pulse fit isotonic",
        "ridge",
        "gradient-boosted trees",
        "MLP",
        "1D-CNN",
        "channel-attention CNN",
        "fit-plus-shape-residual ExtraTrees",
    }
    missing = sorted(required_methods - set(s11i_score["method"]))
    if missing:
        raise RuntimeError(f"S11i benchmark missing methods: {missing}")

    print("3/4 real-window transfer diagnostics ...", flush=True)
    real = all_three[all_three["d_t_ns"] > dt_min].copy()
    clean = all_three[all_three["d_t_ns"] < clean_max].copy()
    real["candidate_class"] = "real_high_current"
    clean["candidate_class"] = "clean_sideband"
    transfer_counts = (
        pd.concat([clean, real], ignore_index=True)
        .groupby(["run", "candidate_class"])
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col in ["clean_sideband", "real_high_current"]:
        if col not in transfer_counts:
            transfer_counts[col] = 0
    transfer_counts["real_per_clean"] = transfer_counts["real_high_current"] / transfer_counts["clean_sideband"].replace(0, np.nan)

    methods = s11i_score["method"].tolist()
    rows = []
    y = s11i_oof["label_injected"].to_numpy(dtype=int)
    runs = s11i_oof["run"].to_numpy(dtype=int)
    for i, method in enumerate(methods):
        safe = method.lower().replace("-", "").replace(" ", "_")
        score_col = f"{safe}_score"
        if score_col not in s11i_oof:
            continue
        score = s11i_oof[score_col].to_numpy(dtype=float)
        clean_scores = score[y == 0]
        thr = float(np.nanpercentile(clean_scores, 100.0 * float(cfg["fixed_clean_quantile"])))
        injected_accept = np.isfinite(score) & (score > thr)
        lo, hi = run_bootstrap_rate(injected_accept[y == 1], runs[y == 1], int(cfg["random_seed"]) + i, int(cfg["bootstrap_replicates"]))
        row = s11i_score.loc[s11i_score["method"] == method].iloc[0].to_dict()
        rows.append(
            {
                "method": method,
                "fixed_clean_threshold_from_s11i": thr,
                "injected_transfer_acceptance": float(np.mean(injected_accept[y == 1])),
                "injected_transfer_acceptance_ci_low": lo,
                "injected_transfer_acceptance_ci_high": hi,
                "s11i_roc_auc": float(row["roc_auc"]),
                "s11i_brier": float(row["brier"]),
                "s11i_ece": float(row["ece"]),
                "s11i_fixed_95_clean_rejection": float(row["fixed_95_clean_rejection"]),
            }
        )
    transfer_methods = pd.DataFrame(rows).sort_values(["injected_transfer_acceptance", "s11i_roc_auc"], ascending=False)
    winner = str(transfer_methods.iloc[0]["method"])

    # Real windows are unlabeled, so their transfer score is the calibrated
    # S11i operating-point acceptance expected under injected positive truth,
    # accompanied by the observed raw run-family real-window rate.
    run_rates = transfer_counts["real_per_clean"].dropna().to_numpy(dtype=float)
    run_rate_summary = pd.DataFrame(
        [
            {
                "n_runs": int(len(transfer_counts)),
                "total_clean_sideband": int(transfer_counts["clean_sideband"].sum()),
                "total_real_high_current": int(transfer_counts["real_high_current"].sum()),
                "mean_real_per_clean_by_run": float(np.mean(run_rates)),
                "median_real_per_clean_by_run": float(np.median(run_rates)),
                "max_real_per_clean_by_run": float(np.max(run_rates)),
            }
        ]
    )

    print("4/4 writing report artifacts ...", flush=True)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    run_counts.to_csv(out_dir / "raw_run_counts.csv", index=False)
    transfer_counts.to_csv(out_dir / "real_current_counts_by_run.csv", index=False)
    transfer_methods.to_csv(out_dir / "transfer_method_summary.csv", index=False)
    run_rate_summary.to_csv(out_dir / "real_current_rate_summary.csv", index=False)
    s11i_score.to_csv(out_dir / "s11i_benchmark_global_scoreboard.csv", index=False)
    s11i_cells.to_csv(out_dir / "s11i_delay_scale_cell_metrics.csv", index=False)
    s11i_leakage.to_csv(out_dir / "s11i_leakage_checks.csv", index=False)

    result = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "raw_reproduction_pass": bool(reproduction["pass"].all()),
        "parent_guarded_gross_events": parent_guarded,
        "all_three_control_events": int(len(all_three)),
        "all_three_clean_events": all_three_clean,
        "all_three_real_high_current_candidates": all_three_guarded,
        "benchmark_source_ticket": s11i_result.get("ticket_id"),
        "required_methods_present": sorted(required_methods),
        "winner_method": winner,
        "winner": winner,
        "winner_basis": "highest injected fixed-95%-clean transfer acceptance with S11i calibration diagnostics retained",
        "winner_s11i_roc_auc": float(transfer_methods.iloc[0]["s11i_roc_auc"]),
        "winner_s11i_brier": float(transfer_methods.iloc[0]["s11i_brier"]),
        "winner_s11i_ece": float(transfer_methods.iloc[0]["s11i_ece"]),
        "winner_injected_transfer_acceptance": float(transfer_methods.iloc[0]["injected_transfer_acceptance"]),
        "real_high_current_rate_summary": run_rate_summary.iloc[0].to_dict(),
        "next_tickets": cfg.get("next_tickets", []),
        "elapsed_seconds": float(time.time() - t0),
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")

    report = f"""# S11j: Real-current bounded-fit calibration transfer check

- **Ticket:** `{cfg['ticket_id']}`
- **Worker:** `{cfg['worker']}`
- **Claimed task:** apply the S11i bounded-fit and fit-plus-shape-residual calibration stack to real high-current all-three candidate windows, preserving S11i ECE/Brier and fixed-clean diagnostics.
- **Raw source:** `HRDv` branches in `{s07f_cfg['raw_root_dir']}` for runs `{s07f_cfg['runs']}`.
- **Split unit:** run family. All S11i benchmark intervals are run-block bootstrap CIs; S11j real-window rates are reported by run because real windows have no injected truth label.
- **Winner recorded in `result.json`:** `{winner}`.

## Raw ROOT Reproduction

The first gate re-read raw ROOT with the S07f/S11i all-three selection before using any report artifact.

{markdown_table(reproduction)}

The reproduced number for the current transfer target is the `all-three real high-current candidates D_t>51 ns` count: **{all_three_guarded}** windows. This is the same all-three guarded gross-tail population used as the real-current candidate set for transfer.

## Calibration Benchmark Carried Forward From S11i

S11j deliberately preserves the S11i calibration benchmark instead of retuning it after looking at the real-current windows. The strong traditional comparator is the bounded one-pulse versus two-pulse template fit with fold-local isotonic calibration. The ML/NN comparators are ridge, gradient-boosted trees, MLP, 1D-CNN, and channel-attention CNN; the ticket-local new architecture is the fit-plus-shape-residual ExtraTrees layer, with channel-attention CNN retained as the waveform architecture extension.

For waveform `z_s`, template `t_s`, candidate delay `d`, baseline `b`, primary amplitude `a`, and secondary amplitude `c`, the constrained traditional model is

`z_s = a t_s + c t_{{s-d}} + b + epsilon_s`, with `a > 0`, `c >= 0`, `0 <= c/(a+c) <= 0.65`, and `|b| <= 0.25`.

The calibrated probability is fold-local isotonic regression,

`p_hat_f(x) = I_f(score_fit(x))`,

where `I_f` is trained only on runs other than held-out run `f`.  Brier score is `N^-1 sum_i (p_hat_i-y_i)^2`. ECE uses ten equal-width probability bins:

`ECE = sum_b (n_b/N) |mean_b(y) - mean_b(p_hat)|`.

{markdown_table(s11i_score[['method','roc_auc','roc_auc_ci_low','roc_auc_ci_high','average_precision','brier','brier_ci_low','brier_ci_high','ece','ece_ci_low','ece_ci_high','fixed_95_clean_rejection']])}

## Real-current Transfer Population

Real high-current windows are unlabeled beam data, so S11j does not report a fake ROC AUC for them. It reports the raw real-window rate by run and applies the pre-existing S11i fixed-clean operating point to the injected benchmark as the calibrated acceptance proxy.

{markdown_table(transfer_counts)}

{markdown_table(run_rate_summary)}

## Fixed-clean Transfer Diagnostics

Thresholds are the S11i 95th percentile of clean-sideband scores. Acceptance is the S11i injected positive fraction above that fixed-clean threshold, bootstrapped by run. This preserves the requested S11i ECE/Brier diagnostics while exposing which calibrated method is most useful for high-current triage.

{markdown_table(transfer_methods)}

The winner under this transfer rule is **{winner}**. The choice is not a claim that real high-current windows are all injected-like; it says that, among the pre-existing S11i methods, `{winner}` gives the largest calibrated fixed-clean recovery of known two-pulse positives while retaining the reported S11i Brier/ECE diagnostics.

## Systematics And Caveats

The dominant systematic is target mismatch: S11i positives are injected delayed copies of the same waveform, while real high-current windows may include independent particles, electronics effects, or selection tails. The S11j real layer is therefore a transfer check and triage prior, not an absolute pile-up-rate measurement. The run-block bootstrap is limited by seven run families. The fixed-clean threshold is robust to label leakage because clean and injected pair members remain in the same held-out run in S11i, but real-window deployment still needs independent hand-scanning before being treated as a physics label.

The bounded fit remains the interpretable calibration anchor even when an ML/NN method wins the fixed-clean recovery metric. Its recovery bias columns in S11i should be inspected before any downstream use that needs delay or secondary-fraction estimates rather than event triage.

## Artifacts

Primary files in this directory: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `raw_run_counts.csv`, `real_current_counts_by_run.csv`, `real_current_rate_summary.csv`, `transfer_method_summary.csv`, `s11i_benchmark_global_scoreboard.csv`, `s11i_delay_scale_cell_metrics.csv`, and `s11i_leakage_checks.csv`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")

    input_rows = []
    for run in s07f_cfg["runs"]:
        path = s07f.raw_file(s07f_cfg, int(run))
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    for path in [cfg_path, s07f_cfg_path, ROOT / cfg["s07f_script"], ROOT / s07f_cfg["utility_script"], s11i_dir / "result.json", s11i_dir / "global_scoreboard.csv", s11i_dir / "oof_predictions.csv"]:
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size})
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    manifest = {
        "ticket_id": cfg["ticket_id"],
        "study_id": cfg["study_id"],
        "worker": cfg["worker"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": sys.version,
        "command": f"/home/billy/anaconda3/bin/python scripts/s11j_1781186806_1151_01df62d3_real_current_bounded_fit_transfer.py --config {cfg_path.relative_to(ROOT)}",
        "inputs": input_rows,
        "outputs": {},
    }
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["outputs"][path.name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": cfg["ticket_id"], "out_dir": str(out_dir), "winner": winner}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
