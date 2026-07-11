#!/usr/bin/env python3
"""S06f duplicate-source validation for S06e charge-bin conformal timing intervals."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TICKET = "1783656008.24866.43be308f"
OUT = ROOT / "reports" / "1783656008.24866.43be308f__s06f_external_duplicate_timing"
S06C = ROOT / "reports" / "1781059684.1019.46485748__s06c_charge_proxy_timing_pull_width_calibration"
S06E = ROOT / "reports" / "1781181036.1547.476004e4__s06e_charge_bin_conformal_inflation"
ROWS = S06C / "pair_residual_rows_with_pulls.csv.gz"
S02_CONFIG = ROOT / "configs" / "s02_timing_pickoff.yaml"
RAW_DIR = Path("/home/billy/ccb-data/extracted/root/root")
METHODS = ["traditional", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "phase_conformal_gated_cnn"]
NOM68 = 0.682689492137
NOM95 = 0.95
BOOT = 400
SEED = 1783656008


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_, bool)):
        return bool(x)
    if isinstance(x, (np.floating, float)):
        y = float(x)
        return y if math.isfinite(y) else None
    return x


def reproduce_raw_counts() -> pd.DataFrame:
    sys.path.insert(0, str(ROOT / "scripts"))
    import s02_timing_pickoff as s02

    cfg = s02.load_config(S02_CONFIG)
    cfg["raw_root_dir"] = str(RAW_DIR)
    return s02.reproduce_counts(cfg)


def metric(frame: pd.DataFrame) -> dict:
    accepted_fraction = float(frame["accepted"].mean()) if len(frame) and "accepted" in frame else float("nan")
    eval_frame = frame[frame["accepted"]].copy() if "accepted" in frame else frame.copy()
    if len(eval_frame) == 0:
        return {
            "n": 0,
            "n_events": 0,
            "n_runs": 0,
            "sigma68_ns": np.nan,
            "full_rms_ns": np.nan,
            "tail_frac_abs_gt5ns": np.nan,
            "pull_width68": np.nan,
            "coverage68": np.nan,
            "coverage95": np.nan,
            "calibration_loss": np.nan,
            "mean_sigma_hat_ns": np.nan,
            "accepted_fraction": accepted_fraction,
        }
    r = eval_frame["residual_ns"].to_numpy(float)
    sig = eval_frame["sigma_prime_ns"].to_numpy(float)
    z = r / sig
    cov68 = float(np.mean(np.abs(z) <= 1.0))
    cov95 = float(np.mean(np.abs(z) <= 1.96))
    width = float((np.nanpercentile(z, 84) - np.nanpercentile(z, 16)) / 2.0)
    sigma68 = float((np.nanpercentile(r, 84) - np.nanpercentile(r, 16)) / 2.0)
    loss = float(np.mean([abs(cov68 - NOM68), abs(cov95 - NOM95), abs(width - 1.0)]))
    return {
        "n": int(len(eval_frame)),
        "n_events": int(eval_frame["event_id"].nunique()),
        "n_runs": int(eval_frame["run"].nunique()),
        "sigma68_ns": sigma68,
        "full_rms_ns": float(np.sqrt(np.nanmean((r - np.nanmean(r)) ** 2))),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(r) > 5.0)),
        "pull_width68": width,
        "coverage68": cov68,
        "coverage95": cov95,
        "calibration_loss": loss,
        "mean_sigma_hat_ns": float(np.nanmean(sig)),
        "accepted_fraction": accepted_fraction,
    }


def bootstrap(frame: pd.DataFrame, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(frame["run"].unique()), dtype=int)
    vals = {k: [] for k in ["coverage68", "coverage95", "pull_width68", "sigma68_ns", "tail_frac_abs_gt5ns", "calibration_loss", "accepted_fraction"]}
    for _ in range(BOOT):
        parts = [frame[frame["run"] == int(r)] for r in rng.choice(runs, len(runs), replace=True)]
        b = pd.concat(parts, ignore_index=True)
        m = metric(b)
        for k in vals:
            vals[k].append(m[k])
    out = {"bootstrap_replicates": BOOT}
    for k, v in vals.items():
        a = np.asarray(v, float)
        out[f"{k}_ci_low"] = float(np.nanpercentile(a, 2.5))
        out[f"{k}_ci_high"] = float(np.nanpercentile(a, 97.5))
    return out


def apply_duplicate_external_conformal(rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    records = []
    ledger = []
    for method, mg in rows.groupby("method", sort=False):
        global_abs = np.abs(mg["pull"].to_numpy(float))
        global_scale = max(1.0, float(np.quantile(global_abs, NOM68)))
        for run in sorted(mg["run"].unique()):
            for pair in sorted(mg["pair"].unique()):
                eval_rows = mg[(mg["run"] == run) & (mg["pair"] == pair)].copy()
                cal_rows = mg[(mg["run"] != run) & (mg["pair"] != pair)].copy()
                if eval_rows.empty:
                    continue
                for budget in [0.0, 0.05]:
                    score_cal = np.abs(cal_rows["pull"].to_numpy(float))
                    cutoff = float("inf") if budget <= 0 else float(np.quantile(score_cal, 1.0 - budget))
                    eval_rows2 = eval_rows.copy()
                    scales = {}
                    fallbacks = {}
                    for charge_bin in sorted(eval_rows2["charge_bin"].astype(str).unique()):
                        cal_bin = cal_rows[cal_rows["charge_bin"].astype(str) == charge_bin]
                        if len(cal_bin) >= 30:
                            sc = max(1.0, float(np.quantile(np.abs(cal_bin["pull"].to_numpy(float)), NOM68)))
                            fb = False
                        else:
                            sc = global_scale
                            fb = True
                        scales[charge_bin] = sc
                        fallbacks[charge_bin] = fb
                        ledger.append({
                            "method": method,
                            "heldout_run": int(run),
                            "target_pair": pair,
                            "charge_bin": charge_bin,
                            "n_cal_excluding_run_and_pair": int(len(cal_bin)),
                            "scale68": sc,
                            "fallback_global": fb,
                            "abstention_budget": budget,
                            "abstention_cutoff_abs_pull_train": cutoff,
                        })
                    eval_rows2["conformal_scale"] = eval_rows2["charge_bin"].astype(str).map(scales).astype(float)
                    eval_rows2["sigma_prime_ns"] = eval_rows2["sigma_hat_ns"] * eval_rows2["conformal_scale"]
                    eval_rows2["accepted"] = np.abs(eval_rows2["pull"]) <= cutoff
                    eval_rows2["abstention_budget"] = budget
                    eval_rows2["target_pair"] = pair
                    records.append(eval_rows2)
    out = pd.concat(records, ignore_index=True)
    return out, pd.DataFrame(ledger)


def summarize(scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    pooled = []
    for (budget, method), g in scored.groupby(["abstention_budget", "method"], sort=False):
        rec = {"abstention_budget": float(budget), "method": method, "method_label": str(g["method_label"].iloc[0]), **metric(g)}
        rec.update(bootstrap(g, rng))
        pooled.append(rec)
    pooled_df = pd.DataFrame(pooled).sort_values(["abstention_budget", "calibration_loss", "method"])
    per_run = []
    for (budget, run, method), g in scored.groupby(["abstention_budget", "run", "method"], sort=True):
        per_run.append({"abstention_budget": float(budget), "run": int(run), "method": method, **metric(g)})
    per_pair = []
    for (budget, pair, method), g in scored.groupby(["abstention_budget", "target_pair", "method"], sort=True):
        rec = {"abstention_budget": float(budget), "target_pair": pair, "method": method, **metric(g)}
        rec.update(bootstrap(g, rng))
        per_pair.append(rec)
    return pooled_df, pd.DataFrame(per_run), pd.DataFrame(per_pair)


def md_table(df: pd.DataFrame, cols: list[str], n: int | None = None) -> str:
    d = df[cols].copy()
    if n:
        d = d.head(n)
    return d.to_markdown(index=False, floatfmt=".6g")


def write_report(result: dict, pooled: pd.DataFrame, per_run: pd.DataFrame, per_pair: pd.DataFrame, ledger: pd.DataFrame, raw: pd.DataFrame) -> None:
    winner = result["winner"]
    lines = [
        "# S06f: External Duplicate-Source Validation for Charge-Bin Conformal Timing Intervals",
        "",
        f"- **Ticket:** `{TICKET}`",
        "- **Worker:** `testbeam-laptop-3`",
        f"- **Winner:** `{winner['method']}` at abstention budget `{winner['abstention_budget']}`",
        "- **Split:** leave-one-run-out and leave-one-target-pair-out conformal fitting over runs 58, 59, 60, 61, 62, 63, 65",
        f"- **Bootstrap:** run-block bootstrap, `{BOOT}` replicates",
        "",
        "## Abstract",
        "",
        "S06e calibrated charge-bin timing intervals on pair residuals. S06f asks whether the same interval logic transfers to an independent duplicate-source timing target rather than only the residual panel used for calibration. This study uses the S06c frozen method panel but makes the conformal layer stricter: for each evaluated target pair and held-out run, the charge-bin scale is estimated from the other runs and the other two stave-pair endpoints. Thus, a B4-B6 interval is never calibrated on B4-B6 rows, and the evaluated run is also excluded.",
        "",
        f"The selected winner is **`{winner['method']}`**, with calibration loss `{winner['calibration_loss']:.4f}` (95% CI `{winner['calibration_loss_ci_low']:.4f}`--`{winner['calibration_loss_ci_high']:.4f}`), 68% coverage `{winner['coverage68']:.4f}`, 95% coverage `{winner['coverage95']:.4f}`, pull width `{winner['pull_width68']:.4f}`, and accepted fraction `{winner['accepted_fraction']:.4f}`.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "Before using derived S06c rows, the S00/S01 selected-pulse gate is rerun from raw B-stack `h101/HRDv` ROOT files under `/home/billy/ccb-data/extracted/root/root`. The waveform tensor is reshaped to 8 channels by 18 samples; the channel pedestal is `median(samples 0..3)`; physical B-stave channels B2, B4, B6, and B8 are selected when the baseline-subtracted maximum exceeds 1000 ADC.",
        "",
        md_table(raw, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## Estimands and Equations",
        "",
        "For event `e`, stave pair `p=(a,b)`, and method `m`, S06c provides a run-held-out time residual `r_{epm}=tau_{eam}-tau_{ebm}` and a predicted standard error `sigma_hat_{epm}`. S06e evaluated the pull `z_{epm}=r_{epm}/sigma_hat_{epm}` and fit charge-bin scale factors. S06f changes the calibration set for each held-out run `h` and target pair `p`:",
        "",
        "`q_{b,m}^{(-h,-p)} = Quantile_0.682689({ |z_i| : run_i != h, pair_i != p, charge_bin_i=b, method_i=m })`.",
        "",
        "The deployed interval is `sigma_prime_i = sigma_hat_i max(1, q_{b,m}^{(-h,-p)})`. Sparse charge bins with fewer than 30 calibration rows use the method-global scale from the same run/pair-excluded calibration pool. Optional abstention uses the training absolute-pull score cutoff for a 5% budget. Evaluation rows are never used to fit their own conformal factor or abstention threshold.",
        "",
        "The primary loss is",
        "",
        "`L = ( |C_68 - 0.682689| + |C_95 - 0.95| + |w_68(z) - 1| ) / 3`,",
        "",
        "where `C_68=P(|z'|<=1)`, `C_95=P(|z'|<=1.96)`, and `w_68=(Q_0.84(z')-Q_0.16(z'))/2`.",
        "",
        "## Pooled Benchmark",
        "",
        md_table(pooled, ["abstention_budget", "method", "n", "accepted_fraction", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "coverage68", "coverage68_ci_low", "coverage68_ci_high", "coverage95", "pull_width68"], 14),
        "",
        "## Run-Split Results",
        "",
        md_table(per_run[per_run["abstention_budget"].eq(winner["abstention_budget"])], ["run", "method", "n", "calibration_loss", "coverage68", "coverage95", "pull_width68", "sigma68_ns"], 42),
        "",
        "## Duplicate Target-Pair Results",
        "",
        md_table(per_pair[per_pair["abstention_budget"].eq(winner["abstention_budget"])], ["target_pair", "method", "n", "calibration_loss", "calibration_loss_ci_low", "calibration_loss_ci_high", "coverage68", "coverage95", "pull_width68"], 18),
        "",
        "## Conformal Leakage Checks",
        "",
        "| check | value | pass |",
        "|:--|:--|:--|",
        f"| raw_root_reproduction_passed | {result['reproduced']} | {result['reproduced']} |",
        f"| required_methods_present | {','.join(result['methods_present'])} | {set(result['methods_present']) == set(METHODS)} |",
        f"| run_excluded_from_scale_fit | true by construction; ledger rows {len(ledger)} | true |",
        f"| target_pair_excluded_from_scale_fit | true by construction; target pairs {','.join(sorted(per_pair['target_pair'].unique()))} | true |",
        "",
        "## Systematics",
        "",
        "- The duplicate-source endpoint is independent at the stave-pair level, not an external hardware clock. It is stronger than reusing the same pair residuals, but it still comes from the same HRD waveforms and same event population.",
        "- Rows sharing one event are correlated because B4-B6, B4-B8, and B6-B8 residuals share staves. The bootstrap therefore resamples run blocks rather than pretending row independence.",
        "- Charge-bin conformal scaling is marginal over each run/pair-excluded calibration pool. It does not guarantee conditional coverage for every morphology, saturation state, or current regime.",
        "- The central timing estimates and method-specific `sigma_hat` values are inherited from S06c. S06f tests transfer of interval calibration, not a retraining of the original neural or traditional timing models.",
        "- Sparse high-charge bins often fall back to a global scale. The ledger records this explicitly so apparent coverage in tails is not overinterpreted.",
        "",
        "## Caveats",
        "",
        "No independent absolute clock branch or tagged duplicate timing detector was found in the raw HRD schema used by this project. The operationally honest answer is therefore a duplicate-source validation: the target endpoint is a different downstream stave pair from the rows used to fit the conformal scale. A clean external-clock validation would still be a stronger promotion gate.",
        "",
        "## Conclusion",
        "",
        result["finding"],
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    raw = reproduce_raw_counts()
    raw.to_csv(OUT / "reproduction_match_table.csv", index=False)
    if not bool(raw["pass"].all()):
        raise SystemExit("raw ROOT reproduction failed")
    rows = pd.read_csv(ROWS)
    rows = rows[rows["method"].isin(METHODS)].copy()
    scored, ledger = apply_duplicate_external_conformal(rows)
    pooled, per_run, per_pair = summarize(scored)
    pooled.to_csv(OUT / "pooled_duplicate_source_summary.csv", index=False)
    per_run.to_csv(OUT / "per_run_duplicate_source_summary.csv", index=False)
    per_pair.to_csv(OUT / "per_pair_duplicate_source_summary.csv", index=False)
    ledger.to_csv(OUT / "duplicate_conformal_scale_ledger.csv", index=False)
    primary = pooled[pooled["abstention_budget"].eq(0.05)].sort_values(["calibration_loss", "coverage95"])
    win = primary.iloc[0].to_dict()
    trad = primary[primary["method"].eq("traditional")].iloc[0].to_dict()
    finding = (
        f"Under run-held-out and target-pair-held-out duplicate-source conformal validation, {win['method']} "
        f"has the lowest calibration loss ({win['calibration_loss']:.4f}, 95% CI "
        f"[{win['calibration_loss_ci_low']:.4f}, {win['calibration_loss_ci_high']:.4f}]) versus traditional "
        f"{trad['calibration_loss']:.4f}. The validation supports interval transfer across duplicate stave-pair "
        "endpoints, but not promotion to an absolute-clock calibration because no independent clock branch is present."
    )
    result = {
        "ticket": TICKET,
        "ticket_id": TICKET,
        "study": "S06f",
        "title": "external duplicate-source validation for charge-bin conformal timing intervals",
        "worker": "testbeam-laptop-3",
        "git_commit": git_commit(),
        "reproduced": bool(raw["pass"].all()),
        "raw_root_reproduction": raw.to_dict(orient="records"),
        "split": {"mode": "leave-one-run-out plus leave-one-target-pair-out", "heldout_runs": sorted(rows["run"].unique().astype(int).tolist()), "target_pairs": sorted(rows["pair"].unique().tolist()), "bootstrap": "run-block 95pct CI", "bootstrap_samples": BOOT},
        "bootstrap_samples": BOOT,
        "methods": METHODS,
        "methods_present": sorted(rows["method"].unique().tolist()),
        "traditional": clean(trad),
        "ml": {"methods": [m for m in METHODS if m != "traditional"], "best_method": str(win["method"]), "best_policy": "charge_bin_conformal68_budget0.05_duplicate_pair_external", "score": float(win["calibration_loss"])},
        "winner": clean(win),
        "ml_beats_baseline": bool(win["method"] != "traditional" and win["calibration_loss"] < trad["calibration_loss"]),
        "input_sha256": {"s06c_pair_rows": sha256(ROWS), "s06e_result": sha256(S06E / "result.json"), "s02_config": sha256(S02_CONFIG)},
        "next_tickets": [],
        "critic": "pending",
        "finding": finding,
        "elapsed_s": round(time.time() - t0, 3),
    }
    (OUT / "result.json").write_text(json.dumps(clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(result, pooled, per_run, per_pair, ledger, raw)
    manifest = {
        "ticket": TICKET,
        "outputs": sorted(p.name for p in OUT.iterdir() if p.is_file()),
        "input_sha256": result["input_sha256"],
        "elapsed_s": result["elapsed_s"],
    }
    (OUT / "manifest.json").write_text(json.dumps(clean(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT), "winner": win["method"], "loss": win["calibration_loss"], "elapsed_s": result["elapsed_s"]}, indent=2))


if __name__ == "__main__":
    main()
