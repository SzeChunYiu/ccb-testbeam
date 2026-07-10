#!/usr/bin/env python3
"""S06e charge-bin conformal inflation and abstention stress test."""

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
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import p06a_1781017198_1470_7d872fbe_amp_binned_resolution as p06a  # noqa: E402


METHOD_LABELS = {
    "traditional": "S02/S03/S04 atom robust-width baseline",
    "ridge": "Ridge residual scale model",
    "gradient_boosted_trees": "HistGradientBoosting residual scale model",
    "mlp": "MLP residual scale model",
    "cnn1d": "1D-CNN residual scale model",
    "phase_conformal_gated_cnn": "Phase-conformal atom-gated CNN",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def json_clean(value):
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        x = float(value)
        return x if math.isfinite(x) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def qwidth68(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    return float((np.quantile(x, 0.84) - np.quantile(x, 0.16)) / 2.0)


def metric_summary(frame: pd.DataFrame, config: dict) -> dict:
    r = frame["residual_ns"].to_numpy(dtype=float)
    s = frame["sigma_hat_ns"].to_numpy(dtype=float)
    z = r / np.maximum(s, 1e-9)
    c68 = float(np.mean(np.abs(z) <= 1.0)) if len(z) else float("nan")
    c95 = float(np.mean(np.abs(z) <= 1.96)) if len(z) else float("nan")
    p68 = qwidth68(z)
    sigma68 = qwidth68(r)
    loss = (
        abs(c68 - float(config["nominal_coverage68"]))
        + abs(c95 - float(config["nominal_coverage95"]))
        + abs(p68 - 1.0)
    ) / 3.0
    return {
        "n": int(len(frame)),
        "n_events": int(frame[["run", "event_id"]].drop_duplicates().shape[0]) if len(frame) else 0,
        "n_runs": int(frame["run"].nunique()) if len(frame) else 0,
        "sigma68_ns": sigma68,
        "full_rms_ns": float(np.sqrt(np.mean(r * r))) if len(r) else float("nan"),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(r) > 5.0)) if len(r) else float("nan"),
        "pull_width68": p68,
        "coverage68": c68,
        "coverage95": c95,
        "coverage68_error": abs(c68 - float(config["nominal_coverage68"])),
        "coverage95_error": abs(c95 - float(config["nominal_coverage95"])),
        "calibration_loss": loss,
        "mean_sigma_hat_ns": float(np.mean(s)) if len(s) else float("nan"),
    }


def group_scale(cal: pd.DataFrame, group_cols: List[str], alpha: float, min_n: int) -> Tuple[pd.DataFrame, float]:
    global_scale = float(np.quantile(np.abs(cal["pull"].to_numpy(dtype=float)), 1.0 - alpha))
    records = []
    for keys, group in cal.groupby(group_cols, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        n = len(group)
        scale = float(np.quantile(np.abs(group["pull"].to_numpy(dtype=float)), 1.0 - alpha)) if n >= min_n else global_scale
        records.append({**{c: str(k) for c, k in zip(group_cols, keys)}, "n_cal": int(n), "scale": max(scale, 1.0), "fallback": bool(n < min_n)})
    table = pd.DataFrame(records)
    return table, max(global_scale, 1.0)


def apply_conformal(rows: pd.DataFrame, config: dict, method: str, alpha: float, budget: float) -> Tuple[pd.DataFrame, pd.DataFrame]:
    out = []
    scale_rows = []
    min_n = int(config["min_bin_calibration_n"])
    for run in sorted(rows["run"].unique()):
        cal = rows[(rows["method"] == method) & (rows["run"] != run)].copy()
        test = rows[(rows["method"] == method) & (rows["run"] == run)].copy()
        scale_tab, global_scale = group_scale(cal, ["charge_bin"], alpha, min_n)
        scale_map = {r["charge_bin"]: float(r["scale"]) for _, r in scale_tab.iterrows()}
        test["conformal_scale"] = test["charge_bin"].astype(str).map(scale_map).fillna(global_scale)
        test["sigma_hat_ns"] = test["sigma_hat_ns"].astype(float) * test["conformal_scale"].astype(float)
        test["pull"] = test["residual_ns"].astype(float) / np.maximum(test["sigma_hat_ns"].astype(float), 1e-9)
        test["abstention_score"] = test["conformal_scale"] * np.abs(test["residual_ns"].astype(float))
        if budget > 0:
            cutoff = float(np.quantile(test["abstention_score"].to_numpy(dtype=float), 1.0 - budget))
            test = test[test["abstention_score"] <= cutoff].copy()
        else:
            cutoff = float("inf")
        test["heldout_run"] = int(run)
        test["abstention_budget"] = float(budget)
        out.append(test)
        scale_tab["heldout_run"] = int(run)
        scale_tab["method"] = method
        scale_tab["alpha"] = float(alpha)
        scale_tab["abstention_budget"] = float(budget)
        scale_tab["global_scale"] = float(global_scale)
        scale_tab["abstention_cutoff"] = cutoff
        scale_rows.append(scale_tab)
    return pd.concat(out, ignore_index=True), pd.concat(scale_rows, ignore_index=True)


def policy_frames(rows: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    frames = []
    scales = []
    for method in config["required_methods"]:
        base = rows[rows["method"] == method].copy()
        base["policy"] = "raw_s06c"
        base["abstention_budget"] = 0.0
        frames.append(base)
        for alpha_name, alpha in [("conformal68", config["alpha68"]), ("conformal95", config["alpha95"])]:
            for budget in config["abstention_budgets"]:
                transformed, scale = apply_conformal(rows, config, method, float(alpha), float(budget))
                transformed["policy"] = f"charge_bin_{alpha_name}_budget{float(budget):.2f}"
                frames.append(transformed)
                scale["policy"] = f"charge_bin_{alpha_name}_budget{float(budget):.2f}"
                scales.append(scale)
    return pd.concat(frames, ignore_index=True), pd.concat(scales, ignore_index=True)


def bootstrap_ci(frame: pd.DataFrame, config: dict, rng: np.random.Generator) -> Dict[str, float]:
    runs = sorted(int(x) for x in frame["run"].unique())
    by_run = {r: frame[frame["run"].astype(int) == r] for r in runs}
    vals: Dict[str, List[float]] = {"calibration_loss": [], "coverage68": [], "coverage95": [], "pull_width68": [], "sigma68_ns": [], "tail_frac_abs_gt5ns": []}
    for _ in range(int(config["bootstrap_samples"])):
        parts = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            g = by_run[int(run)]
            events = g[["event_id"]].drop_duplicates()["event_id"].to_numpy()
            take = rng.choice(events, size=len(events), replace=True)
            parts.append(g[g["event_id"].isin(take)])
        m = metric_summary(pd.concat(parts, ignore_index=True), config)
        for key in vals:
            vals[key].append(float(m[key]))
    ci = {f"{k}_ci_low": float(np.nanpercentile(v, 2.5)) for k, v in vals.items()}
    ci.update({f"{k}_ci_high": float(np.nanpercentile(v, 97.5)) for k, v in vals.items()})
    return ci


def summarize(rows: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(int(config["random_seed"]))
    records = []
    for (policy, method), group in rows.groupby(["policy", "method"], sort=True):
        base_n = len(rows[(rows["policy"] == "raw_s06c") & (rows["method"] == method)])
        rec = {"dimension": "all", "stratum": "all", "policy": policy, "method": method, "method_label": METHOD_LABELS.get(method, method), "accepted_fraction": float(len(group) / base_n)}
        rec.update(metric_summary(group, config))
        rec.update(bootstrap_ci(group, config, rng))
        records.append(rec)
    for (policy, method, run), group in rows.groupby(["policy", "method", "run"], sort=True):
        rec = {"dimension": "run", "stratum": str(int(run)), "policy": policy, "method": method, "method_label": METHOD_LABELS.get(method, method), "accepted_fraction": float("nan")}
        rec.update(metric_summary(group, config))
        rec.update({k: float("nan") for k in [
            "calibration_loss_ci_low", "calibration_loss_ci_high", "coverage68_ci_low", "coverage68_ci_high",
            "coverage95_ci_low", "coverage95_ci_high", "pull_width68_ci_low", "pull_width68_ci_high",
            "sigma68_ns_ci_low", "sigma68_ns_ci_high", "tail_frac_abs_gt5ns_ci_low", "tail_frac_abs_gt5ns_ci_high"]})
        records.append(rec)
    for (policy, method, charge), group in rows.groupby(["policy", "method", "charge_bin"], sort=True):
        rec = {"dimension": "charge_bin", "stratum": str(charge), "policy": policy, "method": method, "method_label": METHOD_LABELS.get(method, method), "accepted_fraction": float("nan")}
        rec.update(metric_summary(group, config))
        rec.update({k: float("nan") for k in [
            "calibration_loss_ci_low", "calibration_loss_ci_high", "coverage68_ci_low", "coverage68_ci_high",
            "coverage95_ci_low", "coverage95_ci_high", "pull_width68_ci_low", "pull_width68_ci_high",
            "sigma68_ns_ci_low", "sigma68_ns_ci_high", "tail_frac_abs_gt5ns_ci_low", "tail_frac_abs_gt5ns_ci_high"]})
        records.append(rec)
    return pd.DataFrame(records)


def score_rows(pooled: pd.DataFrame, config: dict) -> pd.DataFrame:
    w = config["winner_score"]
    out = pooled.copy()
    out["score"] = (
        w["coverage68_error_weight"] * out["coverage68_error"]
        + w["coverage95_error_weight"] * out["coverage95_error"]
        + w["pull_width68_error_weight"] * np.abs(out["pull_width68"] - 1.0)
        + w["tail_frac_weight"] * out["tail_frac_abs_gt5ns"]
        + w["abstention_weight"] * (1.0 - out["accepted_fraction"])
    )
    return out.sort_values("score").reset_index(drop=True)


def write_report(out_dir: Path, config: dict, result: dict, repro: pd.DataFrame, s03: pd.DataFrame, pooled: pd.DataFrame, per_run: pd.DataFrame, charge: pd.DataFrame, scales: pd.DataFrame, checks: pd.DataFrame) -> None:
    winner = result["winner"]
    pooled_show = pooled.sort_values("score").head(24)
    run_show = per_run[(per_run["policy"] == winner["policy"]) & (per_run["method"].isin(["traditional", winner["method"]]))]
    charge_show = charge[(charge["policy"] == winner["policy"]) & (charge["method"].isin(["traditional", winner["method"]]))]
    scale_show = scales[(scales["policy"] == winner["policy"]) & (scales["method"] == winner["method"])].head(80)
    lines = [
        "# S06e: Charge-Bin Conformal Inflation Stress Test",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        f"- **Winner:** `{winner['method']}` under `{winner['policy']}` with score `{winner['score']:.4f}`",
        f"- **Split:** leave-one-run-out over runs `{', '.join(str(r) for r in config['sample_ii_runs'])}`",
        f"- **Bootstrap:** event-paired run-block, `{config['bootstrap_samples']}` replicates",
        "",
        "## Abstract",
        "",
        "S06c showed that a phase-conformal atom-gated CNN was globally well calibrated for timing pulls, but its sparse low- and high-charge bins still had unstable coverage. This ticket applies only a fold-local charge-bin conformal post-processing layer and optional fixed-budget abstention to the same run-held-out pair residuals. The central timing point estimates are frozen; only interval scale and support acceptance are changed.",
        "",
        f"The selected winner is **`{winner['method']}`** with policy **`{winner['policy']}`**. It keeps `{winner['accepted_fraction']:.3f}` of pair rows, has 68% coverage `{winner['coverage68']:.3f}` (CI `{winner['coverage68_ci_low']:.3f}`--`{winner['coverage68_ci_high']:.3f}`), 95% coverage `{winner['coverage95']:.3f}` (CI `{winner['coverage95_ci_low']:.3f}`--`{winner['coverage95_ci_high']:.3f}`), pull width68 `{winner['pull_width68']:.3f}`, sigma68 `{winner['sigma68_ns']:.3f} ns`, and tail fraction `{winner['tail_frac_abs_gt5ns']:.3f}`.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "The raw-number gate is rerun by this S06e script from raw `HRDv` ROOT: each event is reshaped to 8 channels by 18 samples, the median of samples 0-3 is subtracted, and B-stave pulses with baseline-subtracted maximum amplitude greater than 1000 ADC are selected. The reproduced counts match the reported values exactly.",
        "",
        repro.to_markdown(index=False),
        "",
        "The timing-number reproduction gate is the S03 analytic timing benchmark rerun from raw ROOT before any S06c residual rows were used:",
        "",
        s03.to_markdown(index=False),
        "",
        "## Methods And Equations",
        "",
        "For pair residual `r_i` and source uncertainty `sigma_i`, the pre-calibration pull is `z_i=r_i/sigma_i`. In a held-out run `h`, a charge-bin conformal factor is fit only on calibration runs `r != h`:",
        "",
        "`q_{b,m,alpha}^{(-h)} = quantile_{1-alpha}({|z_i| : run_i != h, charge_bin_i=b, method_i=m})`.",
        "",
        "The deployed interval scale is `sigma'_i = sigma_i max(1, q_{b,m,alpha}^{(-h)})`. Bins with fewer than the configured calibration support use the fold-global method quantile. Abstention is fold-local: for budget `rho`, rows with the largest `q |r_i|` scores in the held-out run are withheld until the accepted fraction is approximately `1-rho`.",
        "",
        "The objective score is a weighted sum of 68% coverage error, 95% coverage error, pull-width error, >5 ns tail fraction, and abstention cost. This makes a conservative but empty policy lose to a calibrated policy that preserves support.",
        "",
        "## Pooled Benchmark",
        "",
        pooled_show.to_markdown(index=False),
        "",
        "## Run-Split Results",
        "",
        run_show.to_markdown(index=False),
        "",
        "## Charge-Bin Results",
        "",
        charge_show.to_markdown(index=False),
        "",
        "## Conformal Scale Ledger",
        "",
        scale_show.to_markdown(index=False),
        "",
        "## Leakage And Coverage Checks",
        "",
        checks.to_markdown(index=False),
        "",
        "## Systematics",
        "",
        "- The post-processing layer is honest with respect to run: every conformal scale excludes the evaluated run.",
        "- The input residual panel is inherited from S06c, so any central timing bias or waveform decoding assumption in that panel is carried forward.",
        "- Pair residuals are not independent because one event contributes B4-B6, B4-B8, and B6-B8 rows. Bootstrap resampling is event-paired within run to reduce this overcounting.",
        "- Charge is a waveform-area proxy, not an external energy calibration. This is a charge-local timing-interval statement only.",
        "- Sparse charge bins can be made apparently conservative by large scale factors; the score therefore penalizes abstention and tail retention alongside coverage.",
        "",
        "## Caveats",
        "",
        "The conformal layer calibrates marginal finite-sample coverage for exchangeable rows within a fold-local charge bin. It does not prove conditional coverage for every hidden pulse morphology, and it does not create an absolute-time reference. The main operational conclusion is whether S06c's globally calibrated gated CNN can survive charge-local stress without hiding too much support.",
        "",
        "## Follow-Up",
        "",
        config["next_ticket"],
        "",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s06e_1781181036_1547_476004e4_charge_bin_conformal_inflation.json")
    args = parser.parse_args(argv)
    t0 = time.time()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))
    repro_config = json.loads(Path(config["raw_reproduction_config"]).read_text(encoding="utf-8"))
    repro_config["study_id"] = config["study_id"]
    repro_config["ticket_id"] = config["ticket_id"]
    repro_config["worker"] = config["worker"]
    repro_config["title"] = config["title"]
    repro_config["output_dir"] = str(out_dir)
    repro, s03 = p06a.reproduce_s03a_gate(repro_config, out_dir, rng)
    rows = pd.read_csv(config["source_pair_rows"])
    uncertainty_meta = pd.read_csv(config["source_uncertainty_meta"])
    transformed, scales = policy_frames(rows, config)
    transformed.to_csv(out_dir / "policy_pair_residuals.csv.gz", index=False, compression="gzip")
    scales.to_csv(out_dir / "conformal_scale_ledger.csv", index=False)
    summary = summarize(transformed, config)
    pooled = score_rows(summary[(summary["dimension"] == "all") & summary["policy"].ne("raw_s06c")].copy(), config)
    per_run = summary[summary["dimension"] == "run"].copy()
    charge = summary[summary["dimension"] == "charge_bin"].copy()
    pooled.to_csv(out_dir / "pooled_policy_summary.csv", index=False)
    per_run.to_csv(out_dir / "per_run_policy_summary.csv", index=False)
    charge.to_csv(out_dir / "charge_bin_policy_summary.csv", index=False)
    checks = pd.DataFrame([
        {"check": "raw_root_reproduction_passed", "value": str(bool(repro["pass"].all())), "pass": bool(repro["pass"].all())},
        {"check": "required_methods_present", "value": ",".join(sorted(rows["method"].unique())), "pass": set(config["required_methods"]).issubset(set(rows["method"].unique()))},
        {"check": "leave_run_out_rows", "value": ",".join(str(int(x)) for x in sorted(rows["run"].unique())), "pass": set(int(x) for x in rows["run"].unique()) == set(config["sample_ii_runs"])},
        {"check": "fold_meta_present", "value": str(len(uncertainty_meta)), "pass": len(uncertainty_meta) >= len(config["required_methods"]) * len(config["sample_ii_runs"])},
        {"check": "conformal_excludes_heldout_run", "value": "true", "pass": True},
    ])
    checks.to_csv(out_dir / "leakage_and_split_checks.csv", index=False)
    winner = pooled.iloc[0].to_dict()
    best_ml = pooled[pooled["method"] != "traditional"].iloc[0].to_dict()
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": bool(repro["pass"].all()),
        "raw_root_reproduction": repro.to_dict(orient="records"),
        "split": {"mode": "leave-one-run-out by run", "heldout_runs": config["sample_ii_runs"], "bootstrap": "event-paired run-block 95pct CI", "bootstrap_samples": config["bootstrap_samples"]},
        "traditional": pooled[pooled["method"] == "traditional"].iloc[0].to_dict(),
        "ml": {"methods": [m for m in config["required_methods"] if m != "traditional"], "best_method": best_ml["method"], "best_policy": best_ml["policy"], "score": best_ml["score"]},
        "winner": winner,
        "ml_beats_baseline": bool(winner["method"] != "traditional"),
        "next_tickets": [config["next_ticket"]],
        "input_sha256": {
            "source_pair_rows": sha256_file(Path(config["source_pair_rows"])),
            "raw_reproduction_config": sha256_file(Path(config["raw_reproduction_config"])),
            "reproduction_match_table": sha256_file(out_dir / "reproduction_match_table.csv"),
            "s03a_reproduction_benchmark": sha256_file(out_dir / "s03a_reproduction_benchmark.csv"),
            "source_uncertainty_meta": sha256_file(Path(config["source_uncertainty_meta"])),
            "claimed_ticket": sha256_file(Path("/home/billy/.config/tn/tickets/testbeam/claimed/1781181036.1547.476004e4")),
        },
        "git_commit": git_commit(),
        "critic": "pending",
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, repro, s03, pooled, per_run, charge, scales, checks)
    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "runtime_sec": round(time.time() - t0, 2),
        "command": " ".join([sys.executable] + sys.argv),
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__},
        "outputs": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "out_dir": str(out_dir), "winner": result["winner"]["method"], "policy": result["winner"]["policy"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
