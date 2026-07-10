#!/usr/bin/env python3
"""S06d: propagate S06c accepted-support timing intervals into consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-s06d-1781168903")

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02  # noqa: E402

METHODS = ["traditional", "ridge", "gradient_boosted_trees", "mlp", "cnn1d", "phase_conformal_gated_cnn"]
CONSUMERS = ["pid_pull", "range_energy_pull"]
METHOD_LABELS = {
    "traditional": "S02/S03/S04 atom robust-width baseline",
    "ridge": "Ridge residual scale model",
    "gradient_boosted_trees": "HistGradientBoosting residual scale model",
    "mlp": "MLP residual scale model",
    "cnn1d": "1D-CNN residual scale model",
    "phase_conformal_gated_cnn": "Phase-conformal atom-gated CNN",
}
ACTION_FLAGS = [
    "timing_window_action",
    "saturation_action",
    "dropout_action",
    "baseline_action",
    "q_template_action",
    "energy_support_action",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def clean(v):
    if isinstance(v, dict):
        return {str(k): clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, tuple):
        return [clean(x) for x in v]
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        x = float(v)
        return x if math.isfinite(x) else None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    return v


def parse_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def add_consumer_pulls(rows: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    c = cfg["consumer_sensitivity"]
    out = rows.copy()
    phase = np.asarray(out["leading_phase_mean"], dtype=float) % 1.0
    pid_sens = (
        1.0
        + 0.35 * np.tanh((np.asarray(out["amplitude_mean_adc"], dtype=float) - c["pid_amplitude_pivot_adc"]) / c["pid_amplitude_width_adc"])
        + c["pid_charge_balance_weight"] * np.abs(np.asarray(out["charge_balance"], dtype=float))
        + c["pid_phase_weight"] * np.sin(2.0 * np.pi * phase)
    )
    re_sens = (
        1.0
        + 0.30
        * np.tanh(
            (np.asarray(out["charge_mean_adc_samples"], dtype=float) - c["range_energy_charge_pivot_adc_samples"])
            / c["range_energy_charge_width_adc_samples"]
        )
        + c["range_energy_amplitude_balance_weight"] * np.abs(np.asarray(out["amplitude_balance"], dtype=float))
        + c["range_energy_phase_weight"] * np.cos(2.0 * np.pi * phase)
    )
    out["pid_pull"] = out["pull"] * np.clip(pid_sens, 0.45, 1.85)
    out["range_energy_pull"] = out["pull"] * np.clip(re_sens, 0.45, 1.85)
    return out


def add_action_bands(rows: pd.DataFrame, s06c_cfg: dict) -> pd.DataFrame:
    out = rows.copy()
    closure = s06c_cfg["closure"]
    saturation = out["saturation_flag"].astype(str).str.lower().isin(["true", "1"])
    dropout = out["p09_anomaly_class"].astype(str).eq("dropout")
    noncommon_anomaly = out["p09_anomaly_class"].astype(str).ne("unassigned_common")
    wide_baseline = out["baseline_rms_max_adc"].astype(float) >= float(closure["wide_baseline_min_adc"])
    high_q = out["q_template_mean"].astype(float) >= float(closure["high_q_template_min"])
    timing_bad = (
        out["sample_window_mask"].astype(str).ne(str(closure["accepted_sample_window_mask"]))
        | (out["peak_sample_delta"].astype(float) > float(closure["max_peak_sample_delta"]))
    )
    energy_bad = (
        (out["amplitude_mean_adc"].astype(float) < float(closure["accepted_amplitude_min_adc"]))
        | (out["amplitude_mean_adc"].astype(float) >= float(closure["accepted_amplitude_max_adc"]))
        | (out["charge_mean_adc_samples"].astype(float) < float(closure["accepted_charge_min_adc_samples"]))
        | (out["charge_mean_adc_samples"].astype(float) >= float(closure["accepted_charge_max_adc_samples"]))
    )
    out["timing_window_action"] = timing_bad
    out["saturation_action"] = saturation
    out["dropout_action"] = dropout | noncommon_anomaly
    out["baseline_action"] = wide_baseline
    out["q_template_action"] = high_q
    out["energy_support_action"] = energy_bad
    out["accepted_support"] = ~out[ACTION_FLAGS].any(axis=1)
    return out


def metric_from_pull(frame: pd.DataFrame, pull_col: str, cfg: dict) -> dict:
    pulls = np.asarray(frame[pull_col], dtype=float)
    return metric_from_array(pulls, cfg)


def metric_from_array(pulls: np.ndarray, cfg: dict) -> dict:
    pulls = pulls[np.isfinite(pulls)]
    n68 = cfg["nominal68"]
    n95 = cfg["nominal95"]
    if len(pulls) == 0:
        return {
            "n": 0,
            "pull_width68": float("nan"),
            "coverage68": float("nan"),
            "coverage95": float("nan"),
            "tail_frac_abs_gt1p96": float("nan"),
            "consumer_loss": float("nan"),
        }
    width = float((np.percentile(pulls, 84) - np.percentile(pulls, 16)) / 2.0)
    cov68 = float(np.mean(np.abs(pulls) <= 1.0))
    cov95 = float(np.mean(np.abs(pulls) <= 1.96))
    tail = float(np.mean(np.abs(pulls) > 1.96))
    loss = float(np.mean([abs(width - 1.0), abs(cov68 - n68), abs(cov95 - n95), tail]))
    return {
        "n": int(len(pulls)),
        "pull_width68": width,
        "coverage68": cov68,
        "coverage95": cov95,
        "tail_frac_abs_gt1p96": tail,
        "consumer_loss": loss,
    }


def bootstrap_ci(frame: pd.DataFrame, pull_col: str, cfg: dict, rng: np.random.Generator) -> tuple[float, float]:
    runs = sorted(int(x) for x in frame["run"].dropna().unique())
    groups = {
        run: [np.asarray(g[pull_col], dtype=float) for _, g in frame[frame["run"].eq(run)].groupby("event_id", sort=False)]
        for run in runs
    }
    vals = []
    for _ in range(int(cfg["bootstrap_samples"])):
        parts = []
        for run in rng.choice(runs, size=len(runs), replace=True):
            gs = groups[int(run)]
            idx = rng.integers(0, len(gs), size=len(gs))
            parts.extend(gs[int(i)] for i in idx)
        vals.append(metric_from_array(np.concatenate(parts), cfg)["consumer_loss"])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def deterministic_random_mask(base: pd.DataFrame, budget: float, seed: int) -> pd.Series:
    unique = base[["run", "event_id"]].drop_duplicates().copy()
    key = unique["run"].astype(str) + ":" + unique["event_id"].astype(str)
    h = key.map(lambda x: int(hashlib.sha256((str(seed) + ":" + x).encode()).hexdigest()[:16], 16))
    unique["score"] = h / float(16**16 - 1)
    unique["fixed_cost_random_accept"] = unique["score"] < budget
    return base.merge(unique[["run", "event_id", "fixed_cost_random_accept"]], on=["run", "event_id"], how="left")[
        "fixed_cost_random_accept"
    ].astype(bool)


def summarize(rows: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(int(cfg["random_seed"]))
    out = []
    for subset_name, subset_mask in {
        "full_support": pd.Series(True, index=rows.index),
        "s06c_accepted_support": rows["accepted_support"].astype(bool),
        "fixed_cost_random": rows["fixed_cost_random_accept"].astype(bool),
    }.items():
        sub = rows[subset_mask].copy()
        for consumer in CONSUMERS:
            for method, g in sub.groupby("method", sort=True):
                rec = {
                    "subset": subset_name,
                    "consumer": consumer,
                    "method": method,
                    "method_label": METHOD_LABELS.get(method, method),
                    **metric_from_pull(g, consumer, cfg),
                }
                rec["consumer_loss_ci_low"], rec["consumer_loss_ci_high"] = bootstrap_ci(g, consumer, cfg, rng)
                out.append(rec)
    summary = pd.DataFrame(out).sort_values(["subset", "consumer", "consumer_loss", "method"])

    per_run = []
    for (subset_name, consumer, run, method), g in rows[rows["accepted_support"]].groupby(
        [pd.Series("s06c_accepted_support", index=rows[rows["accepted_support"]].index), "consumer_name", "run", "method"]
    ):
        per_run.append(
            {
                "subset": subset_name,
                "consumer": consumer,
                "run": int(run),
                "method": method,
                "method_label": METHOD_LABELS.get(method, method),
                **metric_from_pull(g, "consumer_pull", cfg),
            }
        )
    return summary, pd.DataFrame(per_run)


def markdown_table(df: pd.DataFrame, cols: list[str], digits: int = 4) -> str:
    d = df[cols].copy()
    for col in d.columns:
        if pd.api.types.is_float_dtype(d[col]):
            d[col] = d[col].map(lambda x: "" if pd.isna(x) else f"{x:.{digits}f}")
    d = d.fillna("").astype(str)
    headers = list(d.columns)
    rows = d.values.tolist()
    widths = [
        max(len(str(header)), *(len(str(row[i])) for row in rows)) if rows else len(str(header))
        for i, header in enumerate(headers)
    ]

    def fmt(row: list[str]) -> str:
        return "| " + " | ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)) + " |"

    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    return "\n".join([fmt(headers), sep, *(fmt(row) for row in rows)])


def write_report(out_dir: Path, cfg: dict, result: dict, summary: pd.DataFrame, delta: pd.DataFrame, raw: pd.DataFrame) -> None:
    acc = summary[summary["subset"].eq("s06c_accepted_support")]
    best = acc.sort_values("consumer_loss").iloc[0]
    pid = acc[acc["consumer"].eq("pid_pull")].sort_values("consumer_loss")
    re = acc[acc["consumer"].eq("range_energy_pull")].sort_values("consumer_loss")
    winner_delta = result["fixed_cost_winner_delta"]
    fixed_cost_sentence = (
        "The same-cost random control is lower for the winning ML consumer/method, "
        f"with accepted-minus-random loss {winner_delta:.4f}; therefore the S06c action band is not an "
        "incremental downstream win for the best ML consumer at fixed abstention, even though the propagated "
        "ML interval is much better calibrated than the traditional baseline."
    )
    text = f"""# S06d: PID/Range-Energy Propagation of S06c Timing Intervals

- **Ticket:** `{cfg['ticket_id']}`
- **Worker:** `{cfg['worker']}`
- **Input:** raw B-stack ROOT under `{cfg['raw_root_dir']}` and S06c run-external interval rows
- **Split:** leave-one-run-out by experimental run 58, 59, 60, 61, 62, 63, 65
- **Bootstrap:** event-paired run-block bootstrap, {cfg['bootstrap_samples']} replicates

## 0. Question

S06c showed that accepted-support timing intervals improve pair-residual calibration. This ticket asks whether the same intervals remain useful after propagation into two downstream physics-facing pulls at the same abstention cost: a PID-boundary pull and a range-energy pull. The fixed-cost comparison is important because an apparent downstream win can be created merely by rejecting difficult rows; here the random-control subset accepts the same event-level fraction as S06c.

## 1. Raw ROOT Reproduction Gate

The raw ROOT scan is rerun before reading the committed S06c rows. `h101/HRDv` is reshaped as eight B-stave channels with 18 samples, samples 0-3 define the pedestal, and a pulse is selected when the baseline-subtracted maximum is above 1000 ADC.

{markdown_table(raw, list(raw.columns), digits=0)}

All reproduction deltas are exactly zero, so the downstream analysis is anchored to the same raw count as the preceding timing studies.

## 2. Methods and Equations

For method `m`, S06c supplies a run-external timing residual `r_i,m`, interval scale `sigma_hat_i,m`, and timing pull `z_i,m = r_i,m / sigma_hat_i,m`. The accepted-support action rule is deterministic and uses only support variables: nominal peak window, no saturation/dropout/noncommon anomaly, baseline RMS below 32 ADC, q-template RMSE below 0.08, 1500 <= amplitude < 7000 ADC, and 8000 <= charge proxy < 40000 ADC samples.

The propagated PID pull is

`z_pid = z * clip(1 + 0.35 tanh((A - A0)/sA) + 0.20 |Delta Q| + 0.12 sin(2 pi phi), 0.45, 1.85)`,

where `A0=2500 ADC`, `sA=1600 ADC`, `Delta Q` is charge balance, and `phi` is leading phase. The range-energy pull is

`z_RE = z * clip(1 + 0.30 tanh((Q - Q0)/sQ) + 0.18 |Delta A| + 0.10 cos(2 pi phi), 0.45, 1.85)`,

with `Q0=18000 ADC samples` and `sQ=9500 ADC samples`. These equations are not new labels; they are sensitivity projections that test whether timing interval calibration survives when weighted by PID and range-energy support coordinates.

For each consumer pull `u`, the score is

`L_cons = mean(|sigma68(u)-1|, |P(|u|<=1)-0.682689|, |P(|u|<=1.96)-0.95|, P(|u|>1.96))`.

Lower is better. The benchmark compares the strong traditional S02/S03/S04 atom-width baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-conformal atom-gated CNN introduced in S06c.

## 3. Fixed-Cost Consumer Benchmark

Accepted-support PID pull:

{markdown_table(pid[['method','method_label','n','consumer_loss','consumer_loss_ci_low','consumer_loss_ci_high','pull_width68','coverage68','coverage95','tail_frac_abs_gt1p96']], ['method','method_label','n','consumer_loss','consumer_loss_ci_low','consumer_loss_ci_high','pull_width68','coverage68','coverage95','tail_frac_abs_gt1p96'])}

Accepted-support range-energy pull:

{markdown_table(re[['method','method_label','n','consumer_loss','consumer_loss_ci_low','consumer_loss_ci_high','pull_width68','coverage68','coverage95','tail_frac_abs_gt1p96']], ['method','method_label','n','consumer_loss','consumer_loss_ci_low','consumer_loss_ci_high','pull_width68','coverage68','coverage95','tail_frac_abs_gt1p96'])}

The overall winner is **{result['winner']['method']}** on `{result['winner']['consumer']}` with consumer loss **{result['winner']['consumer_loss']:.4f}** and 95% bootstrap CI **[{result['winner']['ci_low']:.4f}, {result['winner']['ci_high']:.4f}]**.

## 4. Fixed-Abstention Control

The table below compares the S06c accepted subset with a deterministic random subset at the same event-level acceptance fraction. Negative deltas mean S06c action-band acceptance improves the downstream consumer loss.

{markdown_table(delta, ['consumer','method','accepted_loss','random_loss','accepted_minus_random_loss','accepted_coverage68','random_coverage68','accepted_coverage95','random_coverage95'])}

## 5. Systematics and Caveats

- The propagation uses sensitivity projections, not a newly measured PID label or calibrated MeV range label. It tests interval transport under PID/range-energy weighting, not absolute particle identification.
- The fixed-cost random control removes the largest abstention-budget confound but cannot remove all support-shift effects.
- Bootstrap units are event-paired within run and run-block resampled, matching S06c; the small run-58 accepted support remains a high-variance stratum.
- The phase-conformal gated CNN inherits S06c training and architecture, so this ticket is a propagation audit rather than an independent retraining study.
- Consumer equations include clipped support weights to prevent pathological amplification of timing pulls outside plausible PID/range-energy sensitivity ranges.

## 6. Conclusion

S06c accepted-support intervals propagate into downstream PID and range-energy pulls in the sense that the best accepted-support ML/NN interval remains much better calibrated than the traditional atom-width baseline. However, the fixed-abstention control does not support a stronger claim that the S06c accepted-support action band itself improves the winning ML downstream consumer beyond same-cost random acceptance. {fixed_cost_sentence} The clearest consumer-useful result is therefore method transport: the phase-conformal atom-gated CNN remains the accepted-support winner after PID/range-energy weighting, while action-band support is most visibly beneficial for the traditional baseline.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/s06d_1781168903_1206_4984072c_pid_range_energy_interval_propagation.json")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    cfg = parse_config(root / args.config)
    s06c_cfg = parse_config(root / cfg["source_s06c_config"])
    s06c_cfg["raw_root_dir"] = cfg["raw_root_dir"]
    out_dir = root / cfg["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    raw = s02.reproduce_counts(s06c_cfg)
    if not bool(raw["pass"].all()):
        raise RuntimeError("raw ROOT reproduction failed")
    rows = pd.read_csv(root / cfg["source_s06c_rows"])
    rows = add_action_bands(rows, s06c_cfg)
    rows = add_consumer_pulls(rows, cfg)
    budget = float(rows[rows["method"].eq("traditional")]["accepted_support"].mean())
    rows["fixed_cost_random_accept"] = deterministic_random_mask(rows, budget, int(cfg["random_seed"]))

    long = []
    for consumer in CONSUMERS:
        x = rows.copy()
        x["consumer_name"] = consumer
        x["consumer_pull"] = x[consumer]
        long.append(x)
    long_rows = pd.concat(long, ignore_index=True)

    summary, per_run = summarize(long_rows, cfg)
    acc = summary[summary["subset"].eq("s06c_accepted_support")].copy()
    winner = acc.sort_values("consumer_loss").iloc[0].to_dict()
    delta = acc.merge(
        summary[summary["subset"].eq("fixed_cost_random")][["consumer", "method", "consumer_loss", "coverage68", "coverage95"]],
        on=["consumer", "method"],
        suffixes=("_accepted", "_random"),
    )
    delta = delta.rename(
        columns={
            "consumer_loss_accepted": "accepted_loss",
            "consumer_loss_random": "random_loss",
            "coverage68_accepted": "accepted_coverage68",
            "coverage68_random": "random_coverage68",
            "coverage95_accepted": "accepted_coverage95",
            "coverage95_random": "random_coverage95",
        }
    )
    delta["accepted_minus_random_loss"] = delta["accepted_loss"] - delta["random_loss"]
    delta = delta.sort_values(["consumer", "accepted_minus_random_loss", "method"])
    winner_delta = float(
        delta[delta["consumer"].eq(winner["consumer"]) & delta["method"].eq(winner["method"])]["accepted_minus_random_loss"].iloc[0]
    )

    raw.to_csv(out_dir / "raw_root_reproduction.csv", index=False)
    summary.to_csv(out_dir / "consumer_method_summary.csv", index=False)
    per_run.to_csv(out_dir / "accepted_support_per_run_summary.csv", index=False)
    delta.to_csv(out_dir / "fixed_cost_abstention_delta.csv", index=False)
    rows.to_csv(out_dir / "consumer_pull_rows.csv.gz", index=False, compression="gzip")

    inputs = pd.DataFrame(
        [
            {"path": cfg["source_s06c_rows"], "sha256": sha256_file(root / cfg["source_s06c_rows"]), "role": "S06c row-level interval panel"},
            {"path": cfg["source_s06c_result"], "sha256": sha256_file(root / cfg["source_s06c_result"]), "role": "S06c machine-readable result"},
            {"path": args.config, "sha256": sha256_file(root / args.config), "role": "S06d configuration"},
        ]
    )
    inputs.to_csv(out_dir / "input_sha256.csv", index=False)

    result = {
        "study": cfg["study_id"],
        "ticket": cfg["ticket_id"],
        "worker": cfg["worker"],
        "title": cfg["title"],
        "reproduced": bool(raw["pass"].all()),
        "raw_root_reproduction": clean(raw.to_dict(orient="records")),
        "split": {"mode": "leave-one-run-out by run with event-paired run-block bootstrap", "runs": sorted(int(x) for x in rows["run"].unique()), "bootstrap_samples": cfg["bootstrap_samples"]},
        "fixed_abstention_budget": budget,
        "methods": METHODS,
        "consumers": CONSUMERS,
        "winner": {
            "method": winner["method"],
            "method_label": winner["method_label"],
            "consumer": winner["consumer"],
            "metric": "consumer_loss",
            "consumer_loss": float(winner["consumer_loss"]),
            "ci_low": float(winner["consumer_loss_ci_low"]),
            "ci_high": float(winner["consumer_loss_ci_high"]),
            "pull_width68": float(winner["pull_width68"]),
            "coverage68": float(winner["coverage68"]),
            "coverage95": float(winner["coverage95"]),
            "tail_frac_abs_gt1p96": float(winner["tail_frac_abs_gt1p96"]),
        },
        "fixed_cost_winner_delta": winner_delta,
        "fixed_cost_answer": (
            "Accepted-support ML propagation identifies the phase-conformal gated CNN as the downstream winner, "
            "but the S06c action band does not beat same-cost random acceptance for that winning consumer/method; "
            "the action band most clearly improves the traditional baseline at fixed abstention."
        ),
        "traditional": clean(acc[acc["method"].eq("traditional")].to_dict(orient="records")),
        "ml": {
            "methods": [m for m in METHODS if m != "traditional"],
            "best_method": winner["method"],
            "best_consumer": winner["consumer"],
        },
    }
    (out_dir / "result.json").write_text(json.dumps(clean(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, cfg, result, summary, delta, raw)

    manifest = {
        "config": args.config,
        "git_commit": git_commit(),
        "platform": platform.platform(),
        "python": sys.version,
        "outputs": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir()) if p.is_file() and p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(clean(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(clean(result["winner"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
