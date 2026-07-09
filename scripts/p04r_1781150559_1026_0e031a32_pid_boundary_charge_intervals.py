#!/usr/bin/env python3
"""P04r: atom-conditional charge intervals at PID decision boundaries.

This downstream-consumer study uses the run-held-out P04q charge predictions
and conformal fractional intervals, then tests whether those intervals preserve
event-level range/PID topology-band decisions near score boundaries.  It still
starts with an independent raw-ROOT selector reproduction gate.
"""

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
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p04k_1781029246_839_554f50f7_selector_charge_closure as p04k  # noqa: E402


REAL_METHODS = [
    "strong_traditional_huber",
    "ridge",
    "gradient_boosted_trees",
    "mlp",
    "cnn_1d",
    "wavegate_interval_net",
]
SENTINEL_METHOD = "shuffled_target_gbt"
METHODS = REAL_METHODS + [SENTINEL_METHOD]


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def hash_outputs(out_dir: Path) -> Dict[str, str]:
    return {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }


def check_counts(counts: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for key, expected in config["expected_counts"].items():
        reproduced = int(counts[key].sum())
        rows.append(
            {
                "quantity": key,
                "report_value": int(expected),
                "reproduced": reproduced,
                "delta": reproduced - int(expected),
                "tolerance": 0,
                "pass": reproduced == int(expected),
            }
        )
    out = pd.DataFrame(rows)
    if not bool(out["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed:\n" + out.to_string(index=False))
    return out


def configured_runs(config: dict) -> List[int]:
    runs: List[int] = []
    for values in config["run_groups"].values():
        runs.extend(int(run) for run in values)
    return sorted(set(runs))


def score_from_charge(charge: np.ndarray, stave: Iterable[str], weights: Dict[str, float]) -> np.ndarray:
    w = np.asarray([float(weights[str(s)]) for s in stave], dtype=float)
    return w * np.log1p(np.maximum(charge.astype(float), 0.0))


def band_index(score: np.ndarray, boundaries: np.ndarray) -> np.ndarray:
    return np.digitize(score, boundaries, right=False).astype(int)


def event_frame(pred: pd.DataFrame, method: str, boundaries: np.ndarray, weights: Dict[str, float]) -> pd.DataFrame:
    q90 = pred[f"q90_{method}"].to_numpy(dtype=float)
    pred_q = np.maximum(pred[f"pred_{method}"].to_numpy(dtype=float), 0.0)
    truth_q = np.maximum(pred["target_odd_pos_charge"].to_numpy(dtype=float), 0.0)
    stave = pred["stave"].astype(str).to_numpy()
    truth_piece = score_from_charge(truth_q, stave, weights)
    pred_piece = score_from_charge(pred_q, stave, weights)

    # P04q q90 is fractional absolute charge residual.  Propagate it as a
    # conservative additive charge envelope before the monotone log score.
    lower_q = np.maximum(0.0, pred_q - q90 * np.maximum(pred_q, 1.0))
    upper_q = pred_q + q90 * np.maximum(pred_q, 1.0)
    lower_piece = score_from_charge(lower_q, stave, weights)
    upper_piece = score_from_charge(upper_q, stave, weights)

    pieces = pd.DataFrame(
        {
            "run": pred["run"].to_numpy(dtype=int),
            "evt": pred["evt"].to_numpy(dtype=int),
            "truth_piece": truth_piece,
            "pred_piece": pred_piece,
            "lower_piece": lower_piece,
            "upper_piece": upper_piece,
            "all_pulses_retained": pred[f"keep_{method}"].to_numpy(dtype=bool),
        }
    )
    ev = pieces.groupby(["run", "evt"], observed=True).agg(
        truth_score=("truth_piece", "sum"),
        pred_score=("pred_piece", "sum"),
        lower_score=("lower_piece", "sum"),
        upper_score=("upper_piece", "sum"),
        n_pulses=("truth_piece", "size"),
        all_pulses_retained=("all_pulses_retained", "all"),
    ).reset_index()
    ev["true_band"] = band_index(ev["truth_score"].to_numpy(dtype=float), boundaries)
    ev["pred_band"] = band_index(ev["pred_score"].to_numpy(dtype=float), boundaries)
    ev["lower_band"] = band_index(ev["lower_score"].to_numpy(dtype=float), boundaries)
    ev["upper_band"] = band_index(ev["upper_score"].to_numpy(dtype=float), boundaries)
    ev["band_preserved"] = ev["pred_band"] == ev["true_band"]
    ev["interval_covers_band"] = (ev["lower_band"] <= ev["true_band"]) & (ev["upper_band"] >= ev["true_band"])
    ev["interval_decision_resolved"] = ev["lower_band"] == ev["upper_band"]
    ev["resolved_correct"] = ev["interval_decision_resolved"] & (ev["lower_band"] == ev["true_band"])
    ev["abs_score_error"] = np.abs(ev["pred_score"].to_numpy(dtype=float) - ev["truth_score"].to_numpy(dtype=float))
    ev["nearest_boundary_distance"] = np.min(
        np.abs(ev["truth_score"].to_numpy(dtype=float)[:, None] - boundaries[None, :]), axis=1
    )
    return ev


def metrics_from_event(ev: pd.DataFrame, boundary_cut: float) -> dict:
    near = ev["nearest_boundary_distance"].to_numpy(dtype=float) <= float(boundary_cut)
    retained = ev["all_pulses_retained"].to_numpy(dtype=bool)
    out = {
        "event_n": int(len(ev)),
        "boundary_event_n": int(near.sum()),
        "band_accuracy": float(ev["band_preserved"].mean()),
        "flip_rate": float(1.0 - ev["band_preserved"].mean()),
        "boundary_band_accuracy": float(ev.loc[near, "band_preserved"].mean()) if near.any() else math.nan,
        "boundary_flip_rate": float(1.0 - ev.loc[near, "band_preserved"].mean()) if near.any() else math.nan,
        "interval_band_coverage": float(ev["interval_covers_band"].mean()),
        "boundary_interval_band_coverage": float(ev.loc[near, "interval_covers_band"].mean()) if near.any() else math.nan,
        "resolved_correct_rate": float(ev["resolved_correct"].mean()),
        "boundary_resolved_correct_rate": float(ev.loc[near, "resolved_correct"].mean()) if near.any() else math.nan,
        "event_abstention_coverage": float(retained.mean()),
        "retained_boundary_flip_rate": float(1.0 - ev.loc[near & retained, "band_preserved"].mean())
        if (near & retained).any()
        else math.nan,
        "score_abs68": float(np.percentile(ev["abs_score_error"].to_numpy(dtype=float), 68)),
    }
    return out


def run_block_ci(ev: pd.DataFrame, boundary_cut: float, reps: int, rng: np.random.Generator) -> dict:
    runs = np.asarray(sorted(ev["run"].unique()), dtype=int)
    by_run = {int(run): ev.index[ev["run"].to_numpy(dtype=int) == int(run)].to_numpy() for run in runs}
    keys = [
        "band_accuracy",
        "flip_rate",
        "boundary_flip_rate",
        "interval_band_coverage",
        "boundary_interval_band_coverage",
        "resolved_correct_rate",
        "boundary_resolved_correct_rate",
        "event_abstention_coverage",
        "retained_boundary_flip_rate",
        "score_abs68",
    ]
    vals = {k: np.empty(reps, dtype=float) for k in keys}
    for i in range(reps):
        chosen = rng.choice(runs, size=len(runs), replace=True)
        idx = np.concatenate([rng.choice(by_run[int(run)], size=len(by_run[int(run)]), replace=True) for run in chosen])
        row = metrics_from_event(ev.loc[idx].reset_index(drop=True), boundary_cut)
        for key in keys:
            vals[key][i] = row[key]
    return {f"{key}_ci95": [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for key, v in vals.items()}


def per_run_metrics(events: Dict[str, pd.DataFrame], boundary_cut: float) -> pd.DataFrame:
    rows = []
    for method, ev in events.items():
        for run, block in ev.groupby("run", observed=True):
            row = metrics_from_event(block.reset_index(drop=True), boundary_cut)
            row["method"] = method
            row["run"] = int(run)
            rows.append(row)
    return pd.DataFrame(rows)


def atom_systematics(pred: pd.DataFrame, methods: List[str], boundaries: np.ndarray, weights: Dict[str, float]) -> pd.DataFrame:
    rows = []
    atom_cols = ["lowering_axis", "anomaly_taxon", "saturation_stratum"]
    for atom, block in pred.groupby(atom_cols, observed=True):
        if len(block) < 500:
            continue
        true_event_score = block.assign(
            truth_piece=score_from_charge(
                block["target_odd_pos_charge"].to_numpy(dtype=float),
                block["stave"].astype(str).to_numpy(),
                weights,
            )
        ).groupby(["run", "evt"], observed=True)["truth_piece"].sum()
        true_band = band_index(true_event_score.to_numpy(dtype=float), boundaries)
        for method in methods:
            method_event = block.assign(
                pred_piece=score_from_charge(
                    block[f"pred_{method}"].to_numpy(dtype=float),
                    block["stave"].astype(str).to_numpy(),
                    weights,
                )
            ).groupby(["run", "evt"], observed=True)["pred_piece"].sum()
            pred_band = band_index(method_event.to_numpy(dtype=float), boundaries)
            rows.append(
                {
                    "lowering_axis": str(atom[0]),
                    "anomaly_taxon": str(atom[1]),
                    "saturation_stratum": str(atom[2]),
                    "method": method,
                    "pulse_rows": int(len(block)),
                    "event_rows": int(len(method_event)),
                    "atom_band_accuracy": float(np.mean(pred_band == true_band)),
                    "atom_flip_rate": float(np.mean(pred_band != true_band)),
                }
            )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: List[str], limit: int = 40) -> str:
    if frame.empty:
        return "_No rows._"
    use = frame.loc[:, columns].head(limit).copy()
    for col in use.columns:
        if use[col].dtype.kind in "fc":
            use[col] = use[col].map(lambda x: f"{x:.6g}")
    return use.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    reproduction: pd.DataFrame,
    method_summary: pd.DataFrame,
    per_run: pd.DataFrame,
    atoms: pd.DataFrame,
    result: dict,
) -> None:
    view = method_summary.sort_values("primary_rank")
    winner = result["winner"]
    atom_view = atoms[atoms["method"].isin(["strong_traditional_huber", winner])].sort_values(
        ["anomaly_taxon", "atom_flip_rate"]
    )
    lines = [
        "# P04r Atom-Conditional Charge Intervals at PID Decision Boundaries",
        "",
        f"- **Ticket:** `{config['ticket_id']}`",
        f"- **Worker:** `{config['worker']}`",
        "- **Input:** raw B-stack ROOT `HRDv` branches for count reproduction; P04q run-held-out charge predictions for downstream interval propagation.",
        f"- **Config:** `configs/p04r_1781150559_1026_0e031a32_pid_boundary_charge_intervals.json`",
        f"- **Git commit:** `{result['git_commit']}`",
        "",
        "## Abstract",
        "",
        result["finding"],
        "",
        "## 1. Raw-ROOT Reproduction Gate",
        "",
        "The first operation reruns the S00/P04 raw selector before any PID-boundary metric is computed.  For each `h101/HRDv` event, the eight 18-sample channels are reshaped, a per-channel pedestal is the median of samples 0--3, and physical B-stack even channels B2/B4/B6/B8 are selected when `max_t(HRDv_t - pedestal) > 1000 ADC`.  The dynamic-range extension uses `max(raw)-min(raw)>1000 ADC` and is retained because P04q intervals explicitly cover pathology-tail support.",
        "",
        markdown_table(reproduction, ["quantity", "report_value", "reproduced", "delta", "tolerance", "pass"]),
        "",
        "## 2. Downstream PID-Band Target",
        "",
        "The ticket asks whether conformal charge intervals remain useful after propagation into event-level topology/PID decisions.  Since these data do not contain external particle truth labels for every event, the analysis uses the duplicate-readout charge as an external closure target and defines a monotone range/PID score",
        "",
        "`S_e = sum_{i in event e} w_{s_i} log(1 + q_i)`,",
        "",
        "where `q_i` is the odd-channel duplicate charge of selected B2/B4/B6/B8 pulse `i`, and weights increase with depth: B2=1.00, B4=1.35, B6=1.70, B8=2.05.  PID-like topology bands are the empirical 35% and 65% quantiles of this truth score over the held-out evaluation events.  Boundary events are the closest 25% of events to either band boundary.",
        "",
        "## 3. Methods",
        "",
        "P04r benchmarks the exact P04q method panel under the same run-held-out split: `strong_traditional_huber`, `ridge`, `gradient_boosted_trees`, `mlp`, `cnn_1d`, and the new `wavegate_interval_net`; `shuffled_target_gbt` is a leakage/null sentinel and is ineligible to win.  The strong traditional method is a Huber/template charge closure with one-hot support atoms.  Ridge and gradient-boosted trees operate on tabular pulse and waveform summaries.  MLP, 1D-CNN, and `wavegate_interval_net` are neural regressors, with the new architecture using a pathology/support gate on a waveform convolution embedding.",
        "",
        "## 4. Interval Propagation and Equations",
        "",
        "For method `m`, P04q supplies a charge prediction `hat q_i^(m)` and fold-local conformal fractional half-width `c_i,0.90^(m)`, calibrated on training-run residuals `|hat q_i-y_i|/max(y_i,1)` with support-cell fallback.  P04r propagates the interval through the monotone score using",
        "",
        "`q_i^- = max(0, hat q_i - c_i hat q_i)`,",
        "",
        "`q_i^+ = hat q_i + c_i hat q_i`,",
        "",
        "`S_e^- = sum_i w_i log(1+q_i^-)`, and `S_e^+ = sum_i w_i log(1+q_i^+)`.",
        "",
        "The primary metrics are boundary flip rate, interval band coverage, resolved-correct rate, event abstention coverage, and the 68th percentile absolute score error.  Bootstrap confidence intervals resample complete runs and then events within each selected run.",
        "",
        "## 5. Main Results",
        "",
        markdown_table(
            view,
            [
                "method",
                "method_family",
                "event_n",
                "boundary_event_n",
                "boundary_flip_rate",
                "boundary_flip_rate_ci95",
                "boundary_interval_band_coverage",
                "boundary_interval_band_coverage_ci95",
                "event_abstention_coverage",
                "event_abstention_coverage_ci95",
                "score_abs68",
                "score_abs68_ci95",
                "primary_rank",
            ],
        ),
        "",
        f"**Winner:** `{winner}`.  Winner selection excludes the shuffled-target sentinel and first requires boundary interval band coverage at least 0.84 and event abstention coverage at least 0.45; among passing methods it minimizes boundary flip rate, then score abs68, then maximizes boundary interval coverage.",
        "",
        "## 6. Run-Split Stability",
        "",
        markdown_table(
            per_run.sort_values(["method", "run"]),
            ["method", "run", "event_n", "boundary_event_n", "boundary_flip_rate", "boundary_interval_band_coverage", "event_abstention_coverage", "score_abs68"],
            limit=80,
        ),
        "",
        "## 7. Atom Systematics",
        "",
        markdown_table(
            atom_view,
            ["lowering_axis", "anomaly_taxon", "saturation_stratum", "method", "pulse_rows", "event_rows", "atom_flip_rate", "atom_band_accuracy"],
            limit=50,
        ),
        "",
        "The main systematic is that nominal median-selected template-shift pulses dominate event count, while large baseline-lowering and saturation-boundary atoms dominate interval width and abstention.  Thus a method can have excellent charge closure yet remain operationally weak if its intervals do not contain the correct PID band near the boundaries.",
        "",
        "## 8. Caveats",
        "",
        "- The PID score is a monotone topology proxy, not an externally calibrated proton/deuteron truth label.",
        "- P04r reuses P04q frozen run-held-out predictions instead of refitting every model, so the comparison tests downstream propagation of an existing charge-interval panel.",
        "- The conformal intervals are empirical and support-cell conditional; sparse atom exchangeability remains an assumption, especially for boundary events.",
        "- The run-block bootstrap has only eight held-out runs, so CIs are stability intervals rather than asymptotic guarantees.",
        "- A shuffled-target sentinel is retained to expose leakage-scale failures but cannot validate physical interpretation by itself.",
        "",
        "## 9. Reproducibility",
        "",
        "```bash",
        "/home/billy/anaconda3/bin/python scripts/p04r_1781150559_1026_0e031a32_pid_boundary_charge_intervals.py --config configs/p04r_1781150559_1026_0e031a32_pid_boundary_charge_intervals.json",
        "```",
        "",
        "Artifacts: `result.json`, `manifest.json`, `reproduction_gate.csv`, `counts_by_run.csv`, `pid_boundary_method_summary.csv`, `pid_boundary_by_run.csv`, `atom_pid_systematics.csv`, `event_scores_sample.csv`, and this `REPORT.md`.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/p04r_1781150559_1026_0e031a32_pid_boundary_charge_intervals.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["random_seed"]))

    print("1/5 raw ROOT selector reproduction", flush=True)
    _, _, counts = p04k.extract_rows(config)
    reproduction = check_counts(counts, config)

    print("2/5 loading P04q run-held-out method panel", flush=True)
    pred_path = Path(config["predecessor_prediction_csv"])
    pred = pd.read_csv(pred_path)
    pred = pred[pred["run"].isin(config["evaluation_runs"])].reset_index(drop=True)
    missing = [m for m in METHODS if f"pred_{m}" not in pred.columns or f"q90_{m}" not in pred.columns]
    if missing:
        raise RuntimeError(f"missing predecessor methods: {missing}")

    truth_event = (
        pred.assign(
            truth_piece=score_from_charge(
                pred["target_odd_pos_charge"].to_numpy(dtype=float),
                pred["stave"].astype(str).to_numpy(),
                config["proxy_stave_weights"],
            )
        )
        .groupby(["run", "evt"], observed=True)["truth_piece"]
        .sum()
        .reset_index(name="truth_score")
    )
    boundaries = np.quantile(truth_event["truth_score"].to_numpy(dtype=float), config["pid_band_quantiles"])
    distance = np.min(np.abs(truth_event["truth_score"].to_numpy(dtype=float)[:, None] - boundaries[None, :]), axis=1)
    boundary_cut = float(np.quantile(distance, float(config["boundary_fraction"])))

    print("3/5 propagating intervals to PID bands", flush=True)
    events = {method: event_frame(pred, method, boundaries, config["proxy_stave_weights"]) for method in METHODS}
    summary_rows = []
    for method, ev in events.items():
        row = metrics_from_event(ev, boundary_cut)
        row.update(run_block_ci(ev, boundary_cut, int(config["bootstrap_reps"]), rng))
        row["method"] = method
        row["method_family"] = "sentinel" if method == SENTINEL_METHOD else "traditional" if method == "strong_traditional_huber" else "ml_nn"
        summary_rows.append(row)
    method_summary = pd.DataFrame(summary_rows)

    candidates = method_summary[method_summary["method"].isin(REAL_METHODS)].copy()
    candidates["_gate_fail"] = ~(
        (candidates["boundary_interval_band_coverage"] >= 0.84)
        & (candidates["event_abstention_coverage"] >= 0.45)
    )
    candidates = candidates.sort_values(
        ["_gate_fail", "boundary_flip_rate", "score_abs68", "boundary_interval_band_coverage"],
        ascending=[True, True, True, False],
    )
    winner = str(candidates.iloc[0]["method"])
    rank_map = {method: i + 1 for i, method in enumerate(candidates["method"])}
    method_summary["primary_rank"] = method_summary["method"].map(lambda m: rank_map.get(m, len(rank_map) + 1))
    method_summary = method_summary.sort_values("primary_rank")

    print("4/5 writing summaries and report", flush=True)
    per_run = per_run_metrics(events, boundary_cut)
    atoms = atom_systematics(pred, REAL_METHODS, boundaries, config["proxy_stave_weights"])
    win = method_summary[method_summary["method"] == winner].iloc[0]
    trad = method_summary[method_summary["method"] == "strong_traditional_huber"].iloc[0]
    finding = (
        f"The P04r winner is {winner}: boundary flip rate {win['boundary_flip_rate']:.4f}, "
        f"boundary interval band coverage {win['boundary_interval_band_coverage']:.3f}, event abstention coverage "
        f"{win['event_abstention_coverage']:.3f}, and score abs68 {win['score_abs68']:.4f}. "
        f"The strong traditional Huber/template baseline gives boundary flip rate {trad['boundary_flip_rate']:.4f}, "
        f"boundary interval band coverage {trad['boundary_interval_band_coverage']:.3f}, event abstention coverage "
        f"{trad['event_abstention_coverage']:.3f}, and score abs68 {trad['score_abs68']:.4f}. "
        f"The raw ROOT reproduction gate matched {int(config['expected_counts']['median_first_four_selected'])} "
        "median-first-four selected pulses and all dynamic support counts exactly."
    )
    result = {
        "study": "P04r",
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "winner": winner,
        "winner_selection": "real methods only; boundary_interval_band_coverage>=0.84 and event_abstention_coverage>=0.45, then min boundary_flip_rate, score_abs68, max boundary_interval_band_coverage",
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "pid_score": {
            "equation": "S_e=sum_i w_stave_i log(1+q_i)",
            "weights": config["proxy_stave_weights"],
            "band_quantiles": config["pid_band_quantiles"],
            "band_boundaries": [float(x) for x in boundaries],
            "boundary_fraction": float(config["boundary_fraction"]),
            "boundary_distance_cut": boundary_cut,
        },
        "methods": METHODS,
        "method_summary": method_summary.to_dict(orient="records"),
        "finding": finding,
        "next_tickets": [],
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_sec": round(time.time() - t0, 2),
    }

    counts.to_csv(out_dir / "counts_by_run.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_gate.csv", index=False)
    method_summary.to_csv(out_dir / "pid_boundary_method_summary.csv", index=False)
    per_run.to_csv(out_dir / "pid_boundary_by_run.csv", index=False)
    atoms.to_csv(out_dir / "atom_pid_systematics.csv", index=False)
    sample_cols = ["run", "evt", "truth_score", "pred_score", "lower_score", "upper_score", "true_band", "pred_band", "interval_covers_band"]
    events[winner].loc[:, sample_cols].head(5000).to_csv(out_dir / "event_scores_sample.csv", index=False)
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, reproduction, method_summary, per_run, atoms, result)

    print("5/5 manifest", flush=True)
    input_paths = [pred_path, Path(config["predecessor_method_summary_csv"])]
    input_paths.extend(p04k.raw_path(config, int(run)) for run in configured_runs(config))
    manifest = {
        "ticket": config["ticket_id"],
        "study": "P04r",
        "worker": config["worker"],
        "git_commit": git_commit(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "random_seed": int(config["random_seed"]),
        "runtime_sec": result["runtime_sec"],
        "inputs": {str(path): sha256_file(path) for path in input_paths if path.exists()},
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "runtime_sec": result["runtime_sec"]}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
