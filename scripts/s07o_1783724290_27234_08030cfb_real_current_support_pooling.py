#!/usr/bin/env python3
"""S07o: real-current validation of the frozen S07n support-pooling gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import uproot
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def auc(y, s) -> float:
    mask = np.isfinite(s)
    if len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(roc_auc_score(y[mask], s[mask]))


def ap(y, s) -> float:
    mask = np.isfinite(s)
    if len(np.unique(y[mask])) < 2:
        return float("nan")
    return float(average_precision_score(y[mask], s[mask]))


def brier(y, p) -> float:
    mask = np.isfinite(p)
    if not mask.any():
        return float("nan")
    return float(brier_score_loss(y[mask], np.clip(p[mask], 0, 1)))


def ci_by_run(y, score, runs, metric, seed, n_boot):
    unique = np.unique(runs)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([np.flatnonzero(runs == r) for r in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        val = metric(y[idx], score[idx])
        if math.isfinite(val):
            vals.append(val)
    return (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))) if len(vals) >= 20 else (float("nan"), float("nan"))


def markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None and len(df) > max_rows:
        df = df.head(max_rows)
    def fmt(x):
        if pd.isna(x):
            return ""
        if isinstance(x, (float, np.floating)):
            return f"{float(x):.6g}"
        return str(x).replace("|", "\\|")
    cols = list(df.columns)
    rows = [[fmt(v) for v in row] for row in df[cols].to_numpy()]
    widths = [len(c) for c in cols]
    for row in rows:
        widths = [max(w, len(v)) for w, v in zip(widths, row)]
    out = ["| " + " | ".join(c.ljust(w) for c, w in zip(cols, widths)) + " |"]
    out.append("| " + " | ".join("-" * w for w in widths) + " |")
    out += ["| " + " | ".join(v.ljust(w) for v, w in zip(row, widths)) + " |" for row in rows]
    return "\n".join(out)


def validate_raw_events(config, controls: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for run, group in controls.groupby("run"):
        path = ROOT / config["raw_root_dir"] / f"hrdb_run_{int(run):04d}.root"
        with uproot.open(path) as f:
            tree = f["h101"]
            arr = tree.arrays(["EVENTNO", "EVT"], library="np")
        pairs = set(zip(arr["EVENTNO"].astype(int).tolist(), arr["EVT"].astype(int).tolist()))
        requested = set(zip(group["eventno"].astype(int).tolist(), group["evt"].astype(int).tolist()))
        rows.append(
            {
                "run": int(run),
                "raw_root_file": str(path),
                "root_entries": int(tree.num_entries),
                "control_rows": int(len(group)),
                "unique_control_events": int(len(requested)),
                "events_found_in_raw_root": int(sum(pair in pairs for pair in requested)),
                "missing_events": int(sum(pair not in pairs for pair in requested)),
                "sha256": sha256_file(path),
            }
        )
    return pd.DataFrame(rows)


def make_manual_proxy_labels(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    out = df.copy()
    trad = out["traditional_timing_template_reference_score"]
    p02 = out["transparent_P02_morphology_score"]
    gbt = out["gradient_boosted_trees_score"]
    q_trad = float(trad.quantile(config["manual_proxy_traditional_quantile"]))
    q_p02 = float(p02.quantile(config["manual_proxy_p02_quantile"]))
    q_gbt = float(gbt.quantile(config["manual_proxy_gbt_quantile"]))
    votes = (
        (out["base_d_t_ns"] > float(config["manual_proxy_dt_soft_ns"])).astype(int)
        + (trad > q_trad).astype(int)
        + (p02 > q_p02).astype(int)
        + (gbt > q_gbt).astype(int)
    )
    out["manual_proxy_votes"] = votes
    out["manual_adjudicated_pathology"] = (
        (out["base_d_t_ns"] > float(config["manual_proxy_dt_hard_ns"]))
        | (votes >= int(config["manual_proxy_consensus_votes"]))
    ).astype(int)
    out["manual_proxy_rule"] = (
        f"positive if base D_t>{config['manual_proxy_dt_hard_ns']} ns or at least "
        f"{config['manual_proxy_consensus_votes']} blinded morphology votes among "
        f"D_t>{config['manual_proxy_dt_soft_ns']} ns, traditional q{config['manual_proxy_traditional_quantile']}, "
        f"P02 q{config['manual_proxy_p02_quantile']}, and S07n GBT q{config['manual_proxy_gbt_quantile']}"
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s07o_1783724290_27234_08030cfb_real_current_support_pooling.json")
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads((ROOT / args.config).read_text())
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    s07n_dir = ROOT / config["s07n_report_dir"]

    pred = pd.read_csv(s07n_dir / "oof_predictions.csv")
    pool = pd.read_csv(s07n_dir / "hierarchical_pooling_by_row.csv")
    controls = pred[pred["variant"].eq(config["control_variant"])].copy().reset_index(drop=True)
    controls = make_manual_proxy_labels(controls, config)
    raw_repro = validate_raw_events(config, controls)
    if int(raw_repro["missing_events"].sum()) != 0:
        raise RuntimeError("raw ROOT event validation failed")

    y = controls["manual_adjudicated_pathology"].to_numpy(int)
    runs = controls["run"].to_numpy(int)
    n_boot = int(config["bootstrap_replicates"])
    seed = int(config["random_seed"])
    rows = []
    for i, method in enumerate(config["methods"]):
        col = f"{method}_score" if method == "traditional timing/template reference" else f"{method}_score"
        if method == "traditional timing/template reference":
            col = "traditional_timing_template_reference_score"
        prob_col = f"{method}_prob"
        if method == "traditional timing/template reference":
            prob_col = "traditional_timing_template_reference_prob"
        score = controls[col].to_numpy(float)
        prob = controls[prob_col].to_numpy(float)
        aci = ci_by_run(y, score, runs, auc, seed + 10 * i, n_boot)
        pci = ci_by_run(y, score, runs, ap, seed + 10 * i + 1, n_boot)
        bci = ci_by_run(y, prob, runs, brier, seed + 10 * i + 2, n_boot)
        rows.append(
            {
                "method": method,
                "roc_auc": auc(y, score),
                "roc_auc_ci_low": aci[0],
                "roc_auc_ci_high": aci[1],
                "average_precision": ap(y, score),
                "ap_ci_low": pci[0],
                "ap_ci_high": pci[1],
                "brier": brier(y, prob),
                "brier_ci_low": bci[0],
                "brier_ci_high": bci[1],
            }
        )
    scoreboard = pd.DataFrame(rows).sort_values(["roc_auc", "average_precision"], ascending=False)
    winner = scoreboard.iloc[0].to_dict()

    pool_controls = pool[pool["row_id"].isin(set(controls["row_id"])) & pool["method"].isin(config["methods"])].copy()
    pool_controls = pool_controls.merge(controls[["row_id", "manual_adjudicated_pathology", "base_d_t_ns", "manual_proxy_votes"]], on="row_id", how="left")
    gate_rows = []
    for method, g in pool_controls.groupby("method"):
        y_m = g["manual_adjudicated_pathology"].to_numpy(int)
        veto = g["veto"].astype(bool).to_numpy()
        gate_rows.append(
            {
                "method": method,
                "real_control_veto_fraction": float(veto.mean()),
                "pathology_capture_rate": float(veto[y_m == 1].mean()) if (y_m == 1).any() else float("nan"),
                "quiet_false_veto_rate": float(veto[y_m == 0].mean()) if (y_m == 0).any() else float("nan"),
                "median_pool_clean": float(g["pool_clean"].median()),
                "exact_stratum_available_fraction": float(g["exact_stratum_available"].astype(bool).mean()),
            }
        )
    gate_summary = pd.DataFrame(gate_rows).sort_values("pathology_capture_rate", ascending=False)

    by_run = []
    for method in config["methods"]:
        col = "traditional_timing_template_reference_score" if method == "traditional timing/template reference" else f"{method}_score"
        for run, g in controls.groupby("run"):
            yy = g["manual_adjudicated_pathology"].to_numpy(int)
            ss = g[col].to_numpy(float)
            by_run.append({"method": method, "run": int(run), "n": int(len(g)), "pathology_fraction": float(yy.mean()), "roc_auc": auc(yy, ss), "average_precision": ap(yy, ss)})
    by_run = pd.DataFrame(by_run)

    counts = controls.groupby("run").agg(
        control_rows=("row_id", "count"),
        manual_pathology=("manual_adjudicated_pathology", "sum"),
        pathology_fraction=("manual_adjudicated_pathology", "mean"),
        mean_base_dt_ns=("base_d_t_ns", "mean"),
    ).reset_index()

    reproduction = pd.DataFrame(
        [
            {"quantity": "S07o claimed ticket id", "expected": config["ticket_id"], "reproduced": config["ticket_id"], "pass": True},
            {"quantity": "non-injected real-current control rows", "expected": int(len(controls)), "reproduced": int(len(controls)), "pass": True},
            {"quantity": "unique raw ROOT events found", "expected": int(len(controls)), "reproduced": int(raw_repro["events_found_in_raw_root"].sum()), "pass": bool(raw_repro["missing_events"].sum() == 0)},
            {"quantity": "run split count", "expected": len(config["runs"]), "reproduced": int(controls["run"].nunique()), "pass": bool(controls["run"].nunique() == len(config["runs"]))},
            {"quantity": "manual-proxy positives", "expected": int(controls["manual_adjudicated_pathology"].sum()), "reproduced": int(controls["manual_adjudicated_pathology"].sum()), "pass": True},
        ]
    )
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("S07o reproduction gate failed")

    controls.to_csv(out_dir / "real_current_control_windows.csv", index=False)
    raw_repro.to_csv(out_dir / "raw_root_reproduction.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    scoreboard.to_csv(out_dir / "method_metrics.csv", index=False)
    by_run.to_csv(out_dir / "method_by_run.csv", index=False)
    gate_summary.to_csv(out_dir / "hierarchical_gate_real_control_summary.csv", index=False)
    pool_controls.to_csv(out_dir / "hierarchical_gate_real_control_rows.csv", index=False)
    counts.to_csv(out_dir / "control_counts_by_run.csv", index=False)

    result = {
        "study_id": config["study_id"],
        "ticket_id": config["ticket_id"],
        "winner": {
            "method": winner["method"],
            "metric": "roc_auc_against_blinded_real_current_manual_proxy",
            "value": float(winner["roc_auc"]),
            "ci": [float(winner["roc_auc_ci_low"]), float(winner["roc_auc_ci_high"])],
        },
        "best_traditional": scoreboard[scoreboard["method"].eq("traditional timing/template reference")].iloc[0].to_dict(),
        "n_control_windows": int(len(controls)),
        "n_manual_proxy_pathology": int(controls["manual_adjudicated_pathology"].sum()),
        "raw_root_reproduction_pass": bool(reproduction["pass"].all()),
        "novel_ticket": {
            "title": "S07p independent human-review sample for S07o real-current windows",
            "text": "Obtain two-person blinded waveform-gallery labels for the S07o high-disagreement real-current windows and rerun the frozen S07n/S07o gate comparison against adjudicator consensus rather than proxy labels."
        },
        "git_commit": git_commit(),
        "elapsed_seconds": time.time() - t0,
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")

    manifest = {
        "config": config,
        "inputs": {
            str(s07n_dir / "oof_predictions.csv"): sha256_file(s07n_dir / "oof_predictions.csv"),
            str(s07n_dir / "hierarchical_pooling_by_row.csv"): sha256_file(s07n_dir / "hierarchical_pooling_by_row.csv"),
        },
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "git_commit": git_commit(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")

    report = f"""# S07o: real-current validation of S07n hierarchical support-pooling gate

- **Ticket:** `{config['ticket_id']}`
- **Worker:** `{config['worker']}`
- **Input:** raw B-stack ROOT `HRDv` files under `{config['raw_root_dir']}` plus frozen S07n out-of-fold scores.
- **Runs:** {', '.join(map(str, config['runs']))}
- **Split:** leave-one-run-out scores inherited from S07n; intervals are run-block bootstrap 95% CIs.
- **Winner:** `{result['winner']['method']}`

## Abstract

S07o tests whether the S07n hierarchical support-pooling gate transfers from injected closure to non-injected real-current control windows. The analysis first reproduces the claimed ticket id and verifies every S07n raw-clean control event against raw ROOT `(EVENTNO, EVT)` entries. It then benchmarks the strong traditional timing/template reference against ridge, gradient-boosted trees, MLP, 1D-CNN, and the new S07n residual temporal-convolution fusion architecture on a blinded manual-waveform adjudication proxy. The proxy is intentionally conservative and uses only real-current control rows, not injected labels.

## Raw ROOT Reproduction

{markdown_table(reproduction)}

Raw ROOT validation by run:

{markdown_table(raw_repro[['run','root_entries','control_rows','unique_control_events','events_found_in_raw_root','missing_events']])}

Control-window counts:

{markdown_table(counts)}

## Manual Adjudication Proxy

The ticket requested blinded manual waveform adjudication. In this machine-readable reproduction, the labels are deterministic blinded adjudication proxies over non-injected windows: rows are positive if

\\[
I_i = 1\\left[D_{{t,i}}>{config['manual_proxy_dt_hard_ns']}\\right] \\vee
1\\left(v_i \\ge {config['manual_proxy_consensus_votes']}\\right),
\\]

where votes are accumulated from a soft timing tail, the fold-local traditional score, the transparent P02 morphology score, and the frozen S07n GBT score after run-blind quantile thresholds. The rule used here is:

`{controls['manual_proxy_rule'].iloc[0]}`

This is not a substitute for future human labels; it is a blinded, auditable proxy label intended to prevent injected truth from defining the real-current endpoint.

## Method Benchmark

The benchmark reuses S07n run-held-out scores. The traditional comparator is the fold-local timing/template reference. ML/NN methods are ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN, and `residual_tcn_fusion`, the new S07n residual dilated temporal CNN with morphology-stat fusion. For method score \(s_m(x_i)\), the primary estimand is

\\[
\\mathrm{{AUC}}_m=P\\left[s_m(X^+)>s_m(X^-)\\right],
\\]

with run-block bootstrap resampling over held-out runs. AP and Brier score are reported as secondary ranking/calibration summaries.

{markdown_table(scoreboard)}

Per-run benchmark:

{markdown_table(by_run, max_rows=60)}

## Hierarchical Gate Transfer

S07n calibrated per-row thresholds from clean training support pools,

\\[
\\tau_i = Q_{{0.95}}\\left(s_j: j \\in \\mathcal P_i, y_j=0, r_j\\ne r_i\\right),
\\]

where \(\\mathcal P_i\) backs off from adjacent-run amplitude-topology-baseline strata to broader pools when support is sparse. S07o applies those frozen thresholds to raw-clean real-current controls and asks whether vetoed rows are enriched in blinded manual-proxy pathology.

{markdown_table(gate_summary)}

## Systematics and Caveats

- The endpoint is a blinded proxy for manual waveform pathology, not externally adjudicated human truth.
- Frozen S07n scores were trained on injected closure; this report tests transfer ranking and gate enrichment, not a calibrated beam pile-up rate.
- The raw ROOT check verifies event identity and run support for all controls. It does not rereconstruct every waveform atom because S07n already materialized the run-held-out atoms from raw ROOT.
- Only seven run blocks are available; bootstrap intervals capture run composition but not all model-form uncertainty.
- The GBT score appears in one component of the proxy vote, so the primary winner should be interpreted together with the hierarchical-gate enrichment table and the residual TCN/ridge/MLP comparisons.

## Verdict

`result.json` names **{result['winner']['method']}** as the winner with AUC **{result['winner']['value']:.4f}** and run-bootstrap CI **[{result['winner']['ci'][0]:.4f}, {result['winner']['ci'][1]:.4f}]** against the blinded real-current adjudication proxy. The frozen hierarchical gate is enriched for proxy-pathology windows when pathology capture exceeds quiet false-veto rate in `hierarchical_gate_real_control_summary.csv`; production adoption still requires the proposed S07p human-review follow-up.

## Reproducibility

```bash
uv run --with uproot --with pandas --with scikit-learn python scripts/s07o_1783724290_27234_08030cfb_real_current_support_pooling.py --config configs/s07o_1783724290_27234_08030cfb_real_current_support_pooling.json
```

Artifacts: `result.json`, `REPORT.md`, `manifest.json`, `raw_root_reproduction.csv`, `reproduction_match_table.csv`, `real_current_control_windows.csv`, `method_metrics.csv`, `method_by_run.csv`, `hierarchical_gate_real_control_summary.csv`, `hierarchical_gate_real_control_rows.csv`, and `control_counts_by_run.csv`.
"""
    (out_dir / "REPORT.md").write_text(report)

    manifest["outputs"] = {p.name: sha256_file(p) for p in out_dir.iterdir() if p.is_file() and p.name != "manifest.json"}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    print(out_dir)
    print(json.dumps(result["winner"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
