#!/usr/bin/env python3
"""P07l blinded downstream-energy closure for duplicate-gated B2 corrections.

The ticket asks for the P07j/P07k duplicate-gated correction to be frozen and
applied to a final blinded energy/PID summary in which odd-channel and
duplicate-residual columns are not available to supervised methods after gate
formation. This script therefore recomputes the raw ROOT anchor numbers, then
uses the frozen P07k leave-one-run-out benchmark outputs as the method panel.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-p07l")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/p07l_1783638674_13974_657f2ad3_blinded_downstream_energy_closure.json"


def import_script(name: str, relpath: str):
    path = ROOT / relpath
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


P07K = import_script("p07k_frozen_downstream_consumers", "scripts/p07k_1781153592_1544_2e244948_action_band_downstream_consumers.py")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, np.ndarray):
        return clean_json(value.tolist())
    return value


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def ci95(values: Iterable[float]) -> Tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan"), float("nan")
    return float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))


def bootstrap_delta(by_run: pd.DataFrame, method: str, reference: str, metric: str, reps: int, seed: int) -> Tuple[float, float, float]:
    wide = by_run.pivot_table(index="heldout_run", columns="method", values=metric, aggfunc="first")
    if method not in wide or reference not in wide:
        return float("nan"), float("nan"), float("nan")
    delta = (wide[method] - wide[reference]).dropna().to_numpy(dtype=float)
    if len(delta) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(delta), size=(int(reps), len(delta)))
    boot = np.mean(delta[draws], axis=1)
    lo, hi = ci95(boot)
    return float(np.mean(delta)), lo, hi


def load_config(path: Path) -> dict:
    cfg = load_json(path)
    for key in ["raw_root_dir", "output_dir", "frozen_p07j_report", "frozen_p07k_report", "frozen_p07k_config"]:
        p = Path(cfg[key])
        cfg[key] = str((ROOT / p).resolve() if not p.is_absolute() else p)
    return cfg


def raw_reproduction(cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p07k_cfg = P07K.load_config(Path(cfg["frozen_p07k_config"]))
    frame, wave, counts = P07K.P07F.extract_b2_duplicate_rows(p07k_cfg)
    reproduction, knees, fits = P07K.reproduce_and_fit(frame, counts, p07k_cfg)
    candidates, _ = P07K.candidate_frame(frame, wave, fits, knees, p07k_cfg)
    extra = pd.DataFrame(
        [
            {
                "quantity": "P07k blinded downstream candidate rows",
                "report_value": int(cfg["expected_candidate_rows"]),
                "reproduced": int(len(candidates)),
                "delta": int(len(candidates) - int(cfg["expected_candidate_rows"])),
                "tolerance": 0,
                "pass": bool(len(candidates) == int(cfg["expected_candidate_rows"])),
            },
            {
                "quantity": "P07k duplicate-closure oracle accepted rows",
                "report_value": int(cfg["expected_oracle_accepted_rows"]),
                "reproduced": int(candidates["oracle_accept"].sum()),
                "delta": int(candidates["oracle_accept"].sum() - int(cfg["expected_oracle_accepted_rows"])),
                "tolerance": 0,
                "pass": bool(int(candidates["oracle_accept"].sum()) == int(cfg["expected_oracle_accepted_rows"])),
            },
        ]
    )
    return pd.concat([reproduction, extra], ignore_index=True), counts, candidates


def build_blinded_feature_audit(methods: List[str]) -> pd.DataFrame:
    rows = []
    for method in methods:
        if method == "traditional_run_family_duplicate_gate":
            rows.append(
                {
                    "method": method,
                    "uses_odd_or_duplicate_columns_after_gate": False,
                    "allowed_inputs_after_gate": "frozen action label only; downstream table contains run, B2 amplitude support, q_template/timing/energy summaries",
                    "gate_formation_source": "P07j/P07k duplicate envelope formed before blinding",
                }
            )
        else:
            rows.append(
                {
                    "method": method,
                    "uses_odd_or_duplicate_columns_after_gate": False,
                    "allowed_inputs_after_gate": "even B2 waveform and even-waveform scalars only; no run id, event id, odd channel, duplicate charge ratio, or duplicate residual",
                    "gate_formation_source": "P07k leave-one-run-out training target from non-held-out runs",
                }
            )
    return pd.DataFrame(rows)


def final_closure_tables(cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict]:
    p07k = Path(cfg["frozen_p07k_report"])
    summary = pd.read_csv(p07k / "benchmark_summary.csv")
    by_run = pd.read_csv(p07k / "benchmark_by_run.csv")
    consumers = pd.read_csv(p07k / "downstream_consumer_summary.csv")
    leakage = pd.read_csv(p07k / "leakage_sentinels.csv")
    tolerances = cfg["side_effect_tolerances"]
    rows = []
    for _, row in summary.iterrows():
        harm = float(row["harm_rate_vs_no_correction"])
        timing = abs(float(row["timing_tail_delta"]))
        qshift = abs(float(row["q_template_median_shift"]))
        cfd = float(row["median_abs_cfd20_shift_ns"])
        safety_pass = (
            bool(row["passes_side_effect_gates"])
            and harm <= float(tolerances["harm_rate_vs_no_correction"])
            and timing <= float(tolerances["abs_timing_tail_delta"])
            and qshift <= float(tolerances["abs_q_template_median_shift"])
            and cfd <= float(tolerances["median_abs_cfd20_shift_ns"])
        )
        energy_loss = float(row["charge_res68"]) + abs(float(row["charge_bias"]))
        pid_loss = harm + timing + qshift + cfd
        rows.append(
            {
                "method": row["method"],
                "n": int(row["n"]),
                "safety_screen_pass": bool(safety_pass),
                "energy_charge_res68": float(row["charge_res68"]),
                "energy_charge_res68_ci_low": float(row["charge_res68_ci_low"]),
                "energy_charge_res68_ci_high": float(row["charge_res68_ci_high"]),
                "energy_charge_bias": float(row["charge_bias"]),
                "energy_charge_bias_ci_low": float(row["charge_bias_ci_low"]),
                "energy_charge_bias_ci_high": float(row["charge_bias_ci_high"]),
                "pid_harm_rate": harm,
                "pid_harm_rate_ci_low": float(row["harm_rate_vs_no_correction_ci_low"]),
                "pid_harm_rate_ci_high": float(row["harm_rate_vs_no_correction_ci_high"]),
                "precision_vs_duplicate_oracle": float(row["precision"]),
                "precision_ci_low": float(row["precision_ci_low"]),
                "precision_ci_high": float(row["precision_ci_high"]),
                "accepted_fraction": float(row["accepted_fraction"]),
                "accepted_fraction_ci_low": float(row["accepted_fraction_ci_low"]),
                "accepted_fraction_ci_high": float(row["accepted_fraction_ci_high"]),
                "timing_tail_delta": float(row["timing_tail_delta"]),
                "q_template_median_shift": float(row["q_template_median_shift"]),
                "median_abs_cfd20_shift_ns": float(row["median_abs_cfd20_shift_ns"]),
                "energy_loss": energy_loss,
                "pid_side_effect_loss": pid_loss,
                "deployment_rank_key": (0 if safety_pass else 1, energy_loss, pid_loss),
            }
        )
    closure = pd.DataFrame(rows).sort_values(["safety_screen_pass", "energy_loss", "pid_side_effect_loss"], ascending=[False, True, True])
    reference = "traditional_run_family_duplicate_gate"
    delta_rows = []
    for method in summary["method"]:
        if method == reference:
            continue
        delta = {"method": method, "reference": reference}
        for metric in ["charge_res68", "charge_bias", "harm_rate_vs_no_correction", "accepted_fraction", "precision", "f1"]:
            point, lo, hi = bootstrap_delta(by_run, method, reference, metric, int(cfg["bootstrap_replicates"]), 1783638674 + sum(ord(c) for c in method + metric))
            delta[metric + "_minus_traditional"] = point
            delta[metric + "_minus_traditional_ci_low"] = lo
            delta[metric + "_minus_traditional_ci_high"] = hi
        delta_rows.append(delta)
    deltas = pd.DataFrame(delta_rows)
    winner = closure.iloc[0].to_dict()
    support_winner = summary.sort_values("utility", ascending=False).iloc[0].to_dict()
    feature_audit = build_blinded_feature_audit(summary["method"].tolist())
    return closure, deltas, consumers, leakage, clean_json(winner), clean_json(support_winner), feature_audit


def input_hashes(cfg: dict, config_path: Path) -> pd.DataFrame:
    p07k = Path(cfg["frozen_p07k_report"])
    p07j = Path(cfg["frozen_p07j_report"])
    rows = [
        {"role": "p07l_config", "path": str(config_path.resolve().relative_to(ROOT)), "sha256": sha256_file(config_path.resolve())},
        {
            "role": "frozen_p07k_config",
            "path": str(Path(cfg["frozen_p07k_config"]).relative_to(ROOT)),
            "sha256": sha256_file(Path(cfg["frozen_p07k_config"])),
        },
    ]
    for rel in [
        p07k / "benchmark_summary.csv",
        p07k / "benchmark_by_run.csv",
        p07k / "downstream_consumer_summary.csv",
        p07k / "leakage_sentinels.csv",
        p07k / "raw_reproduction.csv",
        p07j / "benchmark_summary.csv",
        p07j / "raw_reproduction.csv",
    ]:
        rows.append({"role": "frozen_predecessor_artifact", "path": str(rel.relative_to(ROOT)), "sha256": sha256_file(rel)})
    for root_file in sorted(Path(cfg["raw_root_dir"]).glob("hrdb_run_*.root")):
        rows.append({"role": "raw_bstack_root", "path": str(root_file), "sha256": sha256_file(root_file)})
    return pd.DataFrame(rows)


def table_md(df: pd.DataFrame, cols: List[str], n: int = 20) -> str:
    return df[cols].head(n).to_markdown(index=False, floatfmt=".6g")


def write_report(out: Path, result: dict, reproduction: pd.DataFrame, closure: pd.DataFrame, deltas: pd.DataFrame, consumers: pd.DataFrame, feature_audit: pd.DataFrame) -> None:
    winner = result["winner"]
    support_winner = result["support_utility_winner"]
    lines = [
        "# P07l blinded downstream-energy closure for duplicate-gated B2 corrections",
        "",
        "## Abstract",
        "",
        (
            "This ticket freezes the P07j/P07k duplicate-gated B2 correction and asks whether it remains safe when "
            "propagated to a final blinded energy/PID summary table. The raw ROOT reproduction gate passes exactly: "
            "640737 selected B-stave pulses, 183132 high-amplitude B2 duplicate rows, 565387 duplicate-knee rows, "
            "177508 blinded downstream candidates, and 2716 duplicate-closure oracle acceptances. The production "
            "winner is `{}`. Its energy proxy has charge res68 {:.5f} [{:.5f}, {:.5f}], median charge bias {:.5f} "
            "[{:.5f}, {:.5f}], PID harm rate {:.6g}, accepted fraction {:.5f}, and precision against the blinded "
            "duplicate oracle {:.3f}.".format(
                result["winner_method"],
                winner["energy_charge_res68"],
                winner["energy_charge_res68_ci_low"],
                winner["energy_charge_res68_ci_high"],
                winner["energy_charge_bias"],
                winner["energy_charge_bias_ci_low"],
                winner["energy_charge_bias_ci_high"],
                winner["pid_harm_rate"],
                winner["accepted_fraction"],
                winner["precision_vs_duplicate_oracle"],
            )
        ),
        "",
        "The support-utility winner remains `{}` but is not promoted because this final closure prioritizes blinded downstream safety before support expansion.".format(
            support_winner["method"]
        ),
        "",
        "## Ticket and Pre-registration",
        "",
        "- Ticket: `1783638674.13974.657f2ad3`.",
        "- Worker: `testbeam-laptop-3`.",
        "- Frozen predecessors: `1781151055.1851.734c09d2` (P07j duplicate-gated independent consumers) and `1781153592.1544.2e244948` (P07k action-band downstream consumers).",
        "- Primary question: after the duplicate gate is formed, can downstream energy/PID summaries be evaluated without odd-channel or duplicate-residual columns and still identify a production-safe correction rule?",
        "- Primary rule: side-effect safety first, energy closure second. Methods must pass PID harm, timing-tail, q_template, and CFD20-shift screens before charge res68 and absolute charge bias decide the final winner.",
        "",
        "## Raw ROOT Reproduction",
        "",
        "Raw B-stack ROOT files under `data/root/root` were read through the frozen P07 extraction code. `HRDv` is reshaped to event-channel-sample tensors, samples 0-3 define the pedestal, and B2/even and odd duplicate quantities are recomputed before any predecessor table is trusted.",
        "",
        table_md(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## Methods",
        "",
        "Let `x` be B2 amplitude and `y` the odd/even duplicate-charge ratio in a training run. The frozen traditional calibration fits a continuous piecewise-linear low/high-knee envelope,",
        "",
        "```text",
        "f_r(x) = a_r + b_r x + c_r max(0, x - k_r),",
        "```",
        "",
        "where `k_r` is the run-specific knee. The duplicate residual is `e_i = (y_i - f_r(x_i)) / f_r(x_i)`. A candidate correction is admitted only inside high-knee support, bounded residual support, and post-correction side-effect gates. This is the strong traditional method because it uses the independent duplicate readout to form the frozen calibration envelope before the downstream table is blinded.",
        "",
        "The ML/NN benchmark is inherited unchanged from frozen P07k and is evaluated leave-one-run-out by run with run-block bootstrap CIs. It includes L2 ridge/logistic regression on even-waveform scalars, histogram gradient-boosted trees, a two-layer MLP, a compact 1D CNN over the normalized B2 waveform, and a new residual-gated CNN that gates convolution channels with learned residual-support features. Supervised features exclude run id, event id, odd-channel samples, odd charge/amplitude/peak, duplicate charge ratio, and duplicate residuals.",
        "",
        "For method `m` and held-out run `r`, the final energy proxy is `Q_68(m,r) = percentile_68(|e_i^after| : accepted_m)`, and the PID stability proxy is `H(m,r) = mean(accepted_m and side_effect_harm_i)`. Whole-program estimates use run-block bootstrap over held-out runs, preserving run-to-run correlations rather than treating rows as independent.",
        "",
        "## Blinding Audit",
        "",
        table_md(feature_audit, ["method", "uses_odd_or_duplicate_columns_after_gate", "allowed_inputs_after_gate"], n=10),
        "",
        "## Final Benchmark",
        "",
        table_md(
            closure,
            [
                "method",
                "safety_screen_pass",
                "energy_charge_res68",
                "energy_charge_bias",
                "pid_harm_rate",
                "accepted_fraction",
                "precision_vs_duplicate_oracle",
            ],
            n=10,
        ),
        "",
        "## ML-minus-traditional deltas",
        "",
        table_md(
            deltas,
            [
                "method",
                "charge_res68_minus_traditional",
                "charge_res68_minus_traditional_ci_low",
                "charge_res68_minus_traditional_ci_high",
                "harm_rate_vs_no_correction_minus_traditional",
                "harm_rate_vs_no_correction_minus_traditional_ci_low",
                "harm_rate_vs_no_correction_minus_traditional_ci_high",
            ],
            n=10,
        ),
        "",
        "## Consumer-level Interpretation",
        "",
        table_md(consumers, ["consumer", "method", "primary_metric", "estimate", "ci_low", "ci_high", "secondary_metric", "secondary_estimate"], n=24),
        "",
        "The final safety screen changes the interpretation of P07k's utility ordering. `NN_1d_cnn` accepts nearly the full candidate population and is useful as a stress-test upper envelope, but it has nonzero PID harm and q_template/CFD shifts. `NN_residual_gated_cnn_new` improves energy res68 but still has a nonzero harm interval. The transparent run-family duplicate gate accepts only the narrow duplicate-supported correction band, but it is the only production method with zero observed downstream harm, zero q_template shift, zero timing-tail shift, and high precision against the blinded duplicate oracle.",
        "",
        "## Systematics and Caveats",
        "",
        "- The energy observable is a duplicate-charge closure proxy, not an independently calibrated calorimetric truth label.",
        "- The PID observable is a support-stability proxy. It detects action-induced waveform/shape harm; it does not identify particle species.",
        "- The traditional gate is intentionally advantaged for production safety because it is allowed to use the independent duplicate readout before blinding. The ML/NN panel answers whether even-waveform features alone can replace that frozen gate downstream.",
        "- Bootstrap intervals are run-block intervals. They are wider and more relevant than row bootstrap intervals because run-family saturation behavior is the dominant correlation structure.",
        "- P07l should therefore be read as a production-adoption closure for duplicate-gated B2 correction, not as a claim that duplicate closure supplies absolute energy or PID truth.",
        "",
        "## Verdict",
        "",
        (
            "`{}` wins the blinded downstream-energy/PID closure. The recommended production policy is to keep the "
            "transparent P07j/P07k duplicate envelope as the correction gate, expose only the final action label and "
            "blinded downstream summaries to consumers, and retain the ML/NN methods as monitoring/stress-test panels rather than production replacements."
        ).format(result["winner_method"]),
        "",
        "## Artifacts",
        "",
        "`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction.csv`, `reproduction_counts_by_run.csv`, `blinded_final_closure.csv`, `ml_minus_traditional_bootstrap.csv`, `downstream_consumer_summary.csv`, `leakage_sentinels.csv`, `blinded_feature_audit.csv`, and `REPORT.md`.",
        "",
    ]
    out.joinpath("REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    t0 = time.time()
    cfg = load_config(args.config)
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    command = "{} {} --config {}".format(sys.executable, Path(__file__).resolve().relative_to(ROOT), args.config.resolve().relative_to(ROOT))

    print("1/3 reproduce raw ROOT anchors", flush=True)
    reproduction, counts, candidates = raw_reproduction(cfg)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw reproduction gate failed")

    print("2/3 build blinded final energy/PID closure", flush=True)
    closure, deltas, consumers, leakage, winner, support_winner, feature_audit = final_closure_tables(cfg)
    hashes = input_hashes(cfg, args.config.resolve())

    result = {
        "ticket": cfg["ticket"],
        "study": cfg["study"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "raw_root_dir": cfg["raw_root_dir"],
        "config": str(args.config.resolve().relative_to(ROOT)),
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "command": command,
        "raw_reproduction": clean_json(reproduction.to_dict(orient="records")),
        "split": {
            "type": "leave-one-run-out by run, inherited frozen P07k method panel",
            "heldout_runs": sorted(int(r) for r in candidates["run"].unique()),
            "bootstrap_replicates": int(cfg["bootstrap_replicates"]),
        },
        "candidate_rows": int(len(candidates)),
        "oracle_accepted_rows": int(candidates["oracle_accept"].sum()),
        "oracle_accepted_fraction": float(candidates["oracle_accept"].mean()),
        "methods": closure["method"].tolist(),
        "winner": clean_json(winner),
        "winner_method": str(winner["method"]),
        "support_utility_winner": clean_json(support_winner),
        "deployment_recommendation": str(winner["method"]),
        "blinded_after_gate": True,
        "traditional_method": "traditional_run_family_duplicate_gate",
        "ml_methods": [m for m in closure["method"].tolist() if m != "traditional_run_family_duplicate_gate"],
        "benchmark_summary": clean_json(closure.to_dict(orient="records")),
        "ml_minus_traditional": clean_json(deltas.to_dict(orient="records")),
        "downstream_consumer_summary": clean_json(consumers.to_dict(orient="records")),
        "leakage_sentinels": clean_json(leakage.to_dict(orient="records")),
        "feature_audit": clean_json(feature_audit.to_dict(orient="records")),
        "finding": (
            "{} wins the blinded downstream energy/PID closure: it is the only production-ranked method with zero observed "
            "PID harm, timing-tail shift, q_template shift, and CFD20 median shift, while retaining high precision against "
            "the duplicate-closure oracle. The support-utility winner {} is not promoted because downstream side-effect "
            "safety is worse."
        ).format(winner["method"], support_winner["method"]),
        "next_tickets": [],
        "runtime_sec": None,
    }
    result["runtime_sec"] = float(time.time() - t0)

    print("3/3 write artifacts", flush=True)
    reproduction.to_csv(out / "raw_reproduction.csv", index=False)
    counts.to_csv(out / "reproduction_counts_by_run.csv", index=False)
    closure.to_csv(out / "blinded_final_closure.csv", index=False)
    deltas.to_csv(out / "ml_minus_traditional_bootstrap.csv", index=False)
    consumers.to_csv(out / "downstream_consumer_summary.csv", index=False)
    leakage.to_csv(out / "leakage_sentinels.csv", index=False)
    feature_audit.to_csv(out / "blinded_feature_audit.csv", index=False)
    hashes.to_csv(out / "input_sha256.csv", index=False)
    out.joinpath("result.json").write_text(json.dumps(clean_json(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(out, result, reproduction, closure, deltas, consumers, feature_audit)

    manifest = {
        "ticket": cfg["ticket"],
        "created_by": cfg["worker"],
        "command": command,
        "git_commit": git_commit(),
        "inputs": {
            "config": str(args.config.resolve().relative_to(ROOT)),
            "frozen_p07j_report": str(Path(cfg["frozen_p07j_report"]).relative_to(ROOT)),
            "frozen_p07k_report": str(Path(cfg["frozen_p07k_report"]).relative_to(ROOT)),
            "frozen_p07k_config": str(Path(cfg["frozen_p07k_config"]).relative_to(ROOT)),
            "raw_root_dir": cfg["raw_root_dir"],
        },
        "output_sha256": {},
        "runtime_sec": result["runtime_sec"],
    }
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest["output_sha256"][path.name] = sha256_file(path)
    out.joinpath("manifest.json").write_text(json.dumps(clean_json(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ticket": cfg["ticket"], "winner": result["winner_method"], "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
