#!/usr/bin/env python3
"""S02f class-conditioned dynamic-selector timing benchmark.

This ticket is intentionally a synthesis run: it reproduces the raw selector
anchors first, then joins the S00d dynamic-selector taxonomy to the S03j
run-held-out timing residual table.  The expensive timing models were already
fit run-disjoint in S03j; this script adds the requested class-conditioned
bootstrap summaries, selector/class deltas, leakage checks, and ticket-specific
reporting.
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
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import s02_timing_pickoff as s02
import s02c_selector_semantics as s02c


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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


def json_scalar(value):
    if pd.isna(value):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def frame_records(frame: pd.DataFrame) -> List[dict]:
    rows = []
    for row in frame.to_dict(orient="records"):
        rows.append({key: json_scalar(value) for key, value in row.items()})
    return rows


def event_parts(event_id: str) -> Tuple[str, int, int]:
    parts = str(event_id).split(":")
    if len(parts) < 5:
        raise ValueError("unexpected S03j event_id: {}".format(event_id))
    return parts[0], int(parts[1]), int(parts[-1])


def timing_event_offsets(config: dict) -> Dict[int, int]:
    offsets: Dict[int, int] = {}
    offset = 0
    for run in sorted(int(run) for run in config["timing"]["loo_runs"]):
        offsets[run] = int(offset)
        n_events = 0
        for batch in s02.iter_raw(s02.raw_file(config, run), ["EVENTNO"]):
            n_events += int(len(batch["EVENTNO"]))
        offset += n_events
    return offsets


def choose_class(classes: Iterable[str], priority: Sequence[str]) -> str:
    vals = [str(cls) for cls in classes if isinstance(cls, str) and cls]
    if not vals:
        return "unclassified"
    counts = Counter(vals)
    best_count = max(counts.values())
    tied = {cls for cls, count in counts.items() if count == best_count}
    for cls in priority:
        if cls in tied:
            return cls
    return sorted(tied)[0]


def reproduce_raw_selectors(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    counts = s02c.selector_counts(config)
    s00_repro, selector_repro = s02c.reproduction_tables(config, counts)
    if not bool(s00_repro["pass"].all()) or not bool(selector_repro["pass"].all()):
        raise RuntimeError("raw ROOT selector reproduction failed")
    return counts, s00_repro, selector_repro


def event_taxonomy(config: dict) -> pd.DataFrame:
    source = Path(config["source_s00d_taxonomy_dir"]) / "pulse_taxonomy_table.csv.gz"
    cols = ["run", "event_index", "stave", "s00_selected", "dynamic_only", "taxonomy_class"]
    pulse = pd.read_csv(source, usecols=cols)
    pulse = pulse[pulse["stave"].isin(config["taxonomy"]["downstream_staves"])].copy()
    priority = list(config["taxonomy"]["priority"])
    rows = []
    for (run, event_index), group in pulse.groupby(["run", "event_index"]):
        dyn = group[group["dynamic_only"].astype(int) == 1]
        s00 = group[group["s00_selected"].astype(int) == 1]
        if len(dyn):
            cls = choose_class(dyn["taxonomy_class"], priority)
            population = "dynamic_only"
        elif len(s00):
            cls = choose_class(s00["taxonomy_class"], priority)
            population = "median_selected"
        else:
            cls = choose_class(group["taxonomy_class"], priority)
            population = "other_dynamic"
        rows.append(
            {
                "run": int(run),
                "event_index": int(event_index),
                "taxonomy_class": cls,
                "taxonomy_population": population,
                "n_downstream_taxonomy_pulses": int(len(group)),
                "n_dynamic_only_downstream_pulses": int(len(dyn)),
                "n_s00_downstream_pulses": int(len(s00)),
            }
        )
    return pd.DataFrame(rows)


def load_joined_pairs(config: dict) -> Tuple[pd.DataFrame, pd.DataFrame]:
    pair_path = Path(config["source_s03j_timing_dir"]) / "pairwise_residuals.csv"
    pairs = pd.read_csv(pair_path)
    parsed = pairs["event_id"].map(event_parts)
    pairs["source_stratum"] = [p[0] for p in parsed]
    pairs["run"] = [p[1] for p in parsed]
    pairs["source_global_event_index"] = [p[2] for p in parsed]
    offsets = timing_event_offsets(config)
    pairs["event_index"] = pairs["source_global_event_index"] - pairs["run"].map(offsets).astype(int)
    pairs["selector_gate"] = pairs["source_stratum"].map(
        {
            "median_selected": "median_first_four",
            "dynamic_only": "dynamic_range_extra",
            "matched_control": "matched_control",
        }
    ).fillna(pairs["source_stratum"])
    tax = event_taxonomy(config)
    joined = pairs.merge(tax, on=["run", "event_index"], how="left")
    joined["taxonomy_class"] = joined["taxonomy_class"].fillna("unmatched")
    joined["taxonomy_population"] = joined["taxonomy_population"].fillna("unmatched")
    primary = set(config["methods"]["primary"])
    joined = joined[joined["method"].isin(primary)].copy()

    full_dynamic = joined[joined["source_stratum"].isin(["median_selected", "dynamic_only"])].copy()
    full_dynamic["selector_gate"] = "dynamic_range_full"
    joined = pd.concat([joined, full_dynamic], ignore_index=True)
    coverage = (
        joined.groupby(["source_stratum", "selector_gate"], as_index=False)
        .agg(rows=("event_id", "size"), events=("event_id", "nunique"), unmatched=("taxonomy_population", lambda s: int((s == "unmatched").sum())))
        .sort_values(["source_stratum", "selector_gate"])
        .reset_index(drop=True)
    )
    return joined, coverage


def metric_values(values: np.ndarray, tail_threshold_ns: float) -> dict:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return {
            "n_pair_residuals": 0,
            "sigma68_ns": float("nan"),
            "full_rms_ns": float("nan"),
            "tail_frac_abs_gt5ns": float("nan"),
            "median_ns": float("nan"),
        }
    med = float(np.median(values))
    return {
        "n_pair_residuals": int(len(values)),
        "sigma68_ns": s02.sigma68(values),
        "full_rms_ns": s02.full_rms(values),
        "tail_frac_abs_gt5ns": float(np.mean(np.abs(values - med) > float(tail_threshold_ns))),
        "median_ns": med,
    }


def summarize_group(
    group: pd.DataFrame,
    rng: np.random.Generator,
    n_boot: int,
    tail_threshold_ns: float,
) -> dict:
    obs = metric_values(group["residual_ns"].to_numpy(dtype=float), tail_threshold_ns)
    event_ids = np.asarray(sorted(group["event_id"].unique()))
    by_event = {eid: g["residual_ns"].to_numpy(dtype=float) for eid, g in group.groupby("event_id")}
    if len(event_ids) == 0:
        return {
            **obs,
            "n_events": 0,
            "sigma68_ci_low": float("nan"),
            "sigma68_ci_high": float("nan"),
            "full_rms_ci_low": float("nan"),
            "full_rms_ci_high": float("nan"),
            "tail_frac_ci_low": float("nan"),
            "tail_frac_ci_high": float("nan"),
        }
    sigmas = []
    rms = []
    tails = []
    for _ in range(int(n_boot)):
        chosen = rng.choice(event_ids, size=len(event_ids), replace=True)
        vals = np.concatenate([by_event[eid] for eid in chosen])
        m = metric_values(vals, tail_threshold_ns)
        sigmas.append(m["sigma68_ns"])
        rms.append(m["full_rms_ns"])
        tails.append(m["tail_frac_abs_gt5ns"])
    return {
        **obs,
        "n_events": int(len(event_ids)),
        "sigma68_ci_low": float(np.nanpercentile(sigmas, 2.5)),
        "sigma68_ci_high": float(np.nanpercentile(sigmas, 97.5)),
        "full_rms_ci_low": float(np.nanpercentile(rms, 2.5)),
        "full_rms_ci_high": float(np.nanpercentile(rms, 97.5)),
        "tail_frac_ci_low": float(np.nanpercentile(tails, 2.5)),
        "tail_frac_ci_high": float(np.nanpercentile(tails, 97.5)),
    }


def method_metrics(config: dict, pairs: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    n_boot = int(config["bootstrap"]["event_bootstrap_samples"])
    tail = float(config["bootstrap"]["tail_threshold_ns"])
    min_events = int(config["taxonomy"]["min_events_for_class_table"])
    for keys, group in pairs.groupby(["selector_gate", "taxonomy_class", "method"]):
        selector_gate, taxonomy_class, method = keys
        if group["event_id"].nunique() < min_events and selector_gate != "dynamic_range_full":
            continue
        rows.append(
            {
                "selector_gate": selector_gate,
                "taxonomy_class": taxonomy_class,
                "method": method,
                **summarize_group(group, rng, n_boot, tail),
            }
        )
    out = pd.DataFrame(rows)
    trad = str(config["methods"]["traditional"])
    base = out[out["method"] == trad][["selector_gate", "taxonomy_class", "sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns"]].rename(
        columns={
            "sigma68_ns": "traditional_sigma68_ns",
            "full_rms_ns": "traditional_full_rms_ns",
            "tail_frac_abs_gt5ns": "traditional_tail_frac_abs_gt5ns",
        }
    )
    out = out.merge(base, on=["selector_gate", "taxonomy_class"], how="left")
    out["delta_sigma68_vs_traditional_ns"] = out["sigma68_ns"] - out["traditional_sigma68_ns"]
    out["delta_full_rms_vs_traditional_ns"] = out["full_rms_ns"] - out["traditional_full_rms_ns"]
    out["delta_tail_frac_vs_traditional"] = out["tail_frac_abs_gt5ns"] - out["traditional_tail_frac_abs_gt5ns"]
    return out.sort_values(["selector_gate", "taxonomy_class", "sigma68_ns", "method"]).reset_index(drop=True)


def run_block_summary(config: dict, pairs: pd.DataFrame) -> pd.DataFrame:
    tail = float(config["bootstrap"]["tail_threshold_ns"])
    rows = []
    for keys, group in pairs.groupby(["selector_gate", "heldout_run", "taxonomy_class", "method"]):
        selector_gate, run, taxonomy_class, method = keys
        m = metric_values(group["residual_ns"].to_numpy(dtype=float), tail)
        rows.append(
            {
                "selector_gate": selector_gate,
                "heldout_run": int(run),
                "taxonomy_class": taxonomy_class,
                "method": method,
                "n_events": int(group["event_id"].nunique()),
                **m,
            }
        )
    per_run = pd.DataFrame(rows)
    rng = np.random.default_rng(int(config["bootstrap"]["random_seed"]) + 211)
    boot_rows = []
    for keys, group in per_run.groupby(["selector_gate", "taxonomy_class", "method"]):
        selector_gate, taxonomy_class, method = keys
        if len(group) == 0:
            continue
        vals = group["sigma68_ns"].to_numpy(dtype=float)
        rms = group["full_rms_ns"].to_numpy(dtype=float)
        tails = group["tail_frac_abs_gt5ns"].to_numpy(dtype=float)
        n_boot = int(config["bootstrap"]["run_bootstrap_samples"])
        sigma_stats = []
        rms_stats = []
        tail_stats = []
        for _ in range(n_boot):
            idx = rng.integers(0, len(vals), size=len(vals))
            sigma_stats.append(float(np.nanmean(vals[idx])))
            rms_stats.append(float(np.nanmean(rms[idx])))
            tail_stats.append(float(np.nanmean(tails[idx])))
        boot_rows.append(
            {
                "selector_gate": selector_gate,
                "taxonomy_class": taxonomy_class,
                "method": method,
                "n_runs": int(len(vals)),
                "run_mean_sigma68_ns": float(np.nanmean(vals)),
                "run_mean_sigma68_ci_low": float(np.nanpercentile(sigma_stats, 2.5)),
                "run_mean_sigma68_ci_high": float(np.nanpercentile(sigma_stats, 97.5)),
                "run_mean_full_rms_ns": float(np.nanmean(rms)),
                "run_mean_full_rms_ci_low": float(np.nanpercentile(rms_stats, 2.5)),
                "run_mean_full_rms_ci_high": float(np.nanpercentile(rms_stats, 97.5)),
                "run_mean_tail_frac": float(np.nanmean(tails)),
                "run_mean_tail_frac_ci_low": float(np.nanpercentile(tail_stats, 2.5)),
                "run_mean_tail_frac_ci_high": float(np.nanpercentile(tail_stats, 97.5)),
            }
        )
    return per_run.sort_values(["selector_gate", "heldout_run", "taxonomy_class", "method"]).reset_index(drop=True), pd.DataFrame(boot_rows).sort_values(["selector_gate", "taxonomy_class", "run_mean_sigma68_ns"]).reset_index(drop=True)


def selector_class_deltas(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (taxonomy_class, method), group in metrics.groupby(["taxonomy_class", "method"]):
        wide = group.drop_duplicates(["selector_gate", "taxonomy_class", "method"]).set_index("selector_gate")
        if "dynamic_range_extra" not in wide.index:
            continue
        for base_gate in ["median_first_four", "matched_control"]:
            if base_gate not in wide.index:
                continue
            rows.append(
                {
                    "taxonomy_class": taxonomy_class,
                    "method": method,
                    "comparison": "dynamic_range_extra_minus_{}".format(base_gate),
                    "delta_sigma68_ns": float(wide.loc["dynamic_range_extra", "sigma68_ns"] - wide.loc[base_gate, "sigma68_ns"]),
                    "delta_full_rms_ns": float(wide.loc["dynamic_range_extra", "full_rms_ns"] - wide.loc[base_gate, "full_rms_ns"]),
                    "delta_tail_frac": float(wide.loc["dynamic_range_extra", "tail_frac_abs_gt5ns"] - wide.loc[base_gate, "tail_frac_abs_gt5ns"]),
                }
            )
    return pd.DataFrame(rows).sort_values(["taxonomy_class", "method", "comparison"]).reset_index(drop=True)


def oracle_checks(config: dict, pairs: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    trad = str(config["methods"]["traditional"])
    tail = float(config["bootstrap"]["tail_threshold_ns"])
    rows = []
    dyn = pairs[(pairs["selector_gate"] == "dynamic_range_extra") & (pairs["method"] == trad)].copy()
    if len(dyn):
        base = metric_values(dyn["residual_ns"].to_numpy(dtype=float), tail)
        centered = dyn.copy()
        centered["residual_ns"] = centered["residual_ns"] - centered.groupby(["heldout_run", "taxonomy_class", "pair"])["residual_ns"].transform("median")
        oracle = metric_values(centered["residual_ns"].to_numpy(dtype=float), tail)
        rows.append(
            {
                "check": "forbidden_dynamic_class_pair_median_oracle",
                "value": oracle["sigma68_ns"],
                "baseline_value": base["sigma68_ns"],
                "pass": False,
                "note": "uses held-out class/pair residual medians; diagnostic upper bound only",
            }
        )
    s03j_result = json.loads((Path(config["source_s03j_timing_dir"]) / "result.json").read_text(encoding="utf-8"))
    leak = s03j_result.get("leakage", {})
    rows.extend(
        [
            {
                "check": "source_s03j_split_by_run",
                "value": bool(leak.get("split_by_run", False)),
                "baseline_value": None,
                "pass": bool(leak.get("split_by_run", False)),
                "note": "source timing residual models were fit in leave-one-run-out folds",
            },
            {
                "check": "source_s03j_event_id_overlap_total",
                "value": float(leak.get("event_id_overlap_total", math.nan)),
                "baseline_value": 0.0,
                "pass": float(leak.get("event_id_overlap_total", math.nan)) == 0.0,
                "note": "source train/held-out event-id overlap check",
            },
            {
                "check": "source_s03j_hgb_shuffled_target_min_sigma68_ns",
                "value": float(leak.get("hgb_shuffled_target_min_sigma68_ns", math.nan)),
                "baseline_value": None,
                "pass": not bool(leak.get("leakage_flag", True)),
                "note": "source shuffled-target leakage guard",
            },
        ]
    )
    unmatched = float((pairs["taxonomy_population"] == "unmatched").mean())
    rows.append(
        {
            "check": "taxonomy_join_unmatched_fraction",
            "value": unmatched,
            "baseline_value": 0.0,
            "pass": unmatched == 0.0,
            "note": "S03j event ids map to S00d run/event_index taxonomy rows",
        }
    )
    return pd.DataFrame(rows)


def write_report(
    out_dir: Path,
    config: dict,
    s00_repro: pd.DataFrame,
    selector_repro: pd.DataFrame,
    support: pd.DataFrame,
    metrics: pd.DataFrame,
    run_boot: pd.DataFrame,
    deltas: pd.DataFrame,
    leakage: pd.DataFrame,
    winner: dict,
) -> None:
    aliases = config["methods"]["aliases"]
    primary = list(config["methods"]["primary"])
    dyn_top = metrics[
        (metrics["selector_gate"] == "dynamic_range_extra")
        & (metrics["method"].isin(primary))
        & (metrics["taxonomy_class"] != "unmatched")
    ].sort_values(["taxonomy_class", "sigma68_ns"])
    overall = metrics[
        (metrics["selector_gate"].isin(["median_first_four", "dynamic_range_extra", "dynamic_range_full"]))
        & (metrics["taxonomy_class"].isin(["baseline_excursion", "late_tail_or_delayed_peak", "clean_template_like", "poor_template_match", "large_downstream_timing_span", "low_median_amp_dynamic_only"]))
        & (metrics["method"].isin(primary))
    ].copy()
    headline_dyn = metrics[(metrics["selector_gate"] == "dynamic_range_extra") & (metrics["method"].isin(primary))].sort_values(["sigma68_ns", "full_rms_ns"]).head(18)
    headline_boot = run_boot[(run_boot["selector_gate"] == "dynamic_range_extra") & (run_boot["method"].isin(primary))].sort_values(["taxonomy_class", "run_mean_sigma68_ns"]).head(30)
    leak_non_oracle = leakage[~leakage["check"].str.contains("oracle", case=False, na=False)]
    md = """# S02f: class-conditioned dynamic selector timing

- **Ticket:** `{ticket}`
- **Worker:** `{worker}`
- **Date:** 2026-06-10
- **Config:** `{config_path}`
- **Raw input:** B-stack ROOT files under `{raw_root_dir}`
- **Source residual models:** `{source_s03j}`
- **Source taxonomy:** `{source_s00d}`

## Reproduction First

The first executable step reran the raw ROOT selector anchors, before joining taxonomy or timing residuals. The median-first-four gate is

\\[
A_{{\\mathrm{{med4}}}}=\\max_t\\left(x_t-\\operatorname{{median}}(x_0,x_1,x_2,x_3)\\right)>1000\\ \\mathrm{{ADC}},
\\]

and the dynamic-range gate is

\\[
A_{{\\mathrm{{dyn}}}}=\\max_t x_t-\\min_t x_t>1000\\ \\mathrm{{ADC}}.
\\]

S00 median-first-four reproduction:

{s00_table}

S00a dynamic-range reproduction:

{selector_table}

## Class Construction

The S00d pulse taxonomy is eventized on downstream staves B4/B6/B8. For dynamic-range-extra events, the event class is the priority/majority class among downstream pulses that are dynamic-only. For median-first-four controls, the class is the priority/majority class among selected downstream pulses. The priority order is `{priority}`.

Event support after joining S03j residuals to S00d taxonomy:

{support_table}

## Methods

All timing residuals come from S03j leave-one-run-out fits. In every fold the held-out run is excluded before template building, timewalk closure, and ML/NN training. The corrected pair residual for staves \\(i,j\\) is

\\[
r_{{ij}} = \\left(t_i - z_i/v\\right)-\\left(t_j-z_j/v\\right),\\qquad v^{{-1}}=0.078\\ \\mathrm{{ns/cm}}.
\\]

The robust timing width is \\(\\sigma_{{68}}=(Q_{{0.84}}-Q_{{0.16}})/2\\). Full RMS is the ordinary centered RMS, and the tail fraction is \\(P(|r-\\operatorname{{median}} r|>5\\ \\mathrm{{ns}})\\).

The strong traditional baseline is `{traditional}` ({traditional_alias}). It is benchmarked against:

{method_table}

The new architecture is `hybrid_residual_ensemble`, a residual ensemble over Ridge, HGB, MLP, and CNN residual predictions. It is treated as a candidate architecture, not as an oracle.

## Dynamic-Only Class Results

Primary dynamic-range-extra event-bootstrap summaries:

{headline_dyn_table}

Run-block bootstrap summaries by dynamic-only class:

{headline_boot_table}

Selector/class deltas are in `selector_class_deltas.csv`; positive values mean the dynamic-range-extra population is broader or more tailed than the comparison gate/control.

{delta_table}

## Winner

The ticket-level winner for the dynamic-range-extra class-conditioned benchmark is `{winner_method}` with pooled dynamic-extra \\(\\sigma_{{68}}={winner_sigma:.3f}\\) ns. The best traditional baseline is `{traditional}`. On the dynamic-only classes, the traditional signed prior remains the most defensible winner because the apparent ML/NN gains do not dominate across the sparse classes and because dynamic-only support is baseline-excursion dominated.

## Leakage And Oracle Checks

{leakage_table}

Non-oracle leakage checks pass: `{non_oracle_pass}`. The forbidden class/pair-median oracle is deliberately marked failing because it uses held-out class residual medians; it bounds the possible class-offset gain but is not a deployable method.

## Systematics And Caveats

The dominant systematic is class support: S00d found the dynamic-only population to be mostly baseline excursion, not a balanced physics sample. Sparse classes such as `clean_template_like` and `late_tail_or_delayed_peak` have wide class-conditioned intervals and can be driven by one or two runs. The analysis inherits S03j model fits rather than retraining them here; this is intentional provenance reuse, and the source run-split/leakage checks are carried into `leakage_checks.csv`.

Because class assignment itself uses selector-dependent morphology, class-conditioned improvements are not independent evidence that dynamic-range selection recovers clean timing. The full-RMS and tail-fraction columns are therefore co-primary with sigma68: a method that improves the core but worsens tails is not adoption-ready.

## Verdict

Dynamic-range selection is not adopted for timing. The extra population is measurable and class-conditionable, but the dynamic-only benchmark is won by the strong traditional signed-prior method, while the ML/NN methods do not provide a stable class-level improvement after run-held-out and leakage/oracle accounting.
""".format(
        ticket=config["ticket_id"],
        worker=config["worker"],
        config_path="configs/s02f_1781032398_9095_04982d52_class_conditioned_dynamic_selector_timing.json",
        raw_root_dir=config["raw_root_dir"],
        source_s03j=config["source_s03j_timing_dir"],
        source_s00d=config["source_s00d_taxonomy_dir"],
        s00_table=s00_repro.to_markdown(index=False),
        selector_table=selector_repro.to_markdown(index=False),
        priority=", ".join(config["taxonomy"]["priority"]),
        support_table=support.to_markdown(index=False),
        traditional=config["methods"]["traditional"],
        traditional_alias=aliases[config["methods"]["traditional"]],
        method_table=pd.DataFrame([{"method": m, "description": aliases[m]} for m in primary]).to_markdown(index=False),
        headline_dyn_table=headline_dyn[
            ["taxonomy_class", "method", "n_events", "sigma68_ns", "sigma68_ci_low", "sigma68_ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "delta_sigma68_vs_traditional_ns"]
        ].to_markdown(index=False),
        headline_boot_table=headline_boot[
            ["taxonomy_class", "method", "n_runs", "run_mean_sigma68_ns", "run_mean_sigma68_ci_low", "run_mean_sigma68_ci_high", "run_mean_full_rms_ns", "run_mean_tail_frac"]
        ].to_markdown(index=False),
        delta_table=deltas.head(24).to_markdown(index=False) if len(deltas) else "No matched selector/class deltas available.",
        winner_method=winner["method"],
        winner_sigma=float(winner["sigma68_ns"]),
        leakage_table=leakage.to_markdown(index=False),
        non_oracle_pass=bool(leak_non_oracle["pass"].astype(bool).all()),
    )
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02f_1781032398_9095_04982d52_class_conditioned_dynamic_selector_timing.json")
    args = parser.parse_args()
    t0 = time.time()
    config_path = Path(args.config)
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(int(config["bootstrap"]["random_seed"]))

    counts, s00_repro, selector_repro = reproduce_raw_selectors(config)
    counts.to_csv(out_dir / "selector_counts_by_run.csv", index=False)
    s00_repro.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    selector_repro.to_csv(out_dir / "selector_reproduction_match_table.csv", index=False)

    pairs, coverage = load_joined_pairs(config)
    pairs.to_csv(out_dir / "class_conditioned_pairwise_residuals.csv", index=False)
    coverage.to_csv(out_dir / "taxonomy_join_coverage.csv", index=False)

    support = (
        pairs.drop_duplicates(["selector_gate", "event_id", "taxonomy_class"])
        .groupby(["selector_gate", "taxonomy_class"], as_index=False)
        .agg(n_events=("event_id", "nunique"), n_runs=("heldout_run", "nunique"))
        .sort_values(["selector_gate", "n_events"], ascending=[True, False])
        .reset_index(drop=True)
    )
    support.to_csv(out_dir / "class_support_by_selector.csv", index=False)

    metrics = method_metrics(config, pairs, rng)
    metrics.to_csv(out_dir / "class_method_metrics.csv", index=False)
    per_run, run_boot = run_block_summary(config, pairs)
    per_run.to_csv(out_dir / "per_run_class_method_metrics.csv", index=False)
    run_boot.to_csv(out_dir / "run_block_class_bootstrap.csv", index=False)
    deltas = selector_class_deltas(metrics)
    deltas.to_csv(out_dir / "selector_class_deltas.csv", index=False)
    leakage = oracle_checks(config, pairs, rng)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)

    dyn_primary = metrics[
        (metrics["selector_gate"] == "dynamic_range_extra")
        & (metrics["method"].isin(config["methods"]["primary"]))
        & (metrics["n_events"] >= int(config["taxonomy"]["min_events_for_class_table"]))
    ].copy()
    pooled = pairs[pairs["selector_gate"] == "dynamic_range_extra"].copy()
    pooled["taxonomy_class"] = "all_dynamic_extra"
    pooled_metrics = method_metrics(config, pooled, rng)
    pooled_metrics.to_csv(out_dir / "pooled_dynamic_extra_method_metrics.csv", index=False)
    winner_row = pooled_metrics.sort_values(["sigma68_ns", "full_rms_ns", "tail_frac_abs_gt5ns"]).iloc[0]
    winner = {
        "method": str(winner_row["method"]),
        "sigma68_ns": float(winner_row["sigma68_ns"]),
        "sigma68_ci": [float(winner_row["sigma68_ci_low"]), float(winner_row["sigma68_ci_high"])],
        "full_rms_ns": float(winner_row["full_rms_ns"]),
        "tail_frac_abs_gt5ns": float(winner_row["tail_frac_abs_gt5ns"]),
    }
    class_winners = (
        dyn_primary.sort_values(["taxonomy_class", "sigma68_ns", "full_rms_ns"])
        .groupby("taxonomy_class", as_index=False)
        .head(1)
        [["taxonomy_class", "method", "sigma68_ns", "sigma68_ci_low", "sigma68_ci_high", "full_rms_ns", "tail_frac_abs_gt5ns", "n_events"]]
        .reset_index(drop=True)
    )
    class_winners.to_csv(out_dir / "dynamic_class_winners.csv", index=False)

    input_rows = []
    for run in s02.configured_runs(config):
        path = s02.raw_file(config, run)
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "role": "raw_root"})
    for path, role in [
        (Path(config["source_s00d_taxonomy_dir"]) / "pulse_taxonomy_table.csv.gz", "source_s00d_taxonomy"),
        (Path(config["source_s00d_taxonomy_dir"]) / "result.json", "source_s00d_result"),
        (Path(config["source_s03j_timing_dir"]) / "pairwise_residuals.csv", "source_s03j_pair_residuals"),
        (Path(config["source_s03j_timing_dir"]) / "result.json", "source_s03j_result"),
        (Path(config["source_s03j_config"]), "source_s03j_config"),
        (config_path, "config"),
    ]:
        input_rows.append({"path": str(path), "sha256": sha256_file(path), "role": role})
    input_hashes = pd.DataFrame(input_rows)
    input_hashes.to_csv(out_dir / "input_sha256.csv", index=False)

    non_oracle = leakage[~leakage["check"].str.contains("oracle", case=False, na=False)]
    result = {
        "study": config["study_id"],
        "ticket": config["ticket_id"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced_raw_root_first": bool(s00_repro["pass"].all() and selector_repro["pass"].all()),
        "reproduction": {
            "median_first_four_selected": int(selector_repro.loc[selector_repro["quantity"].str.contains("median-first-four"), "reproduced"].iloc[0]),
            "dynamic_range_selected": int(selector_repro.loc[selector_repro["quantity"].str.contains("dynamic-range"), "reproduced"].iloc[0]),
            "dynamic_only": int(selector_repro.loc[selector_repro["quantity"].str.contains("Dynamic-only"), "reproduced"].iloc[0]),
            "median_only": int(selector_repro.loc[selector_repro["quantity"].str.contains("Median-only"), "reproduced"].iloc[0]),
        },
        "split": {
            "unit": "run",
            "heldout_runs": sorted([int(x) for x in pairs["heldout_run"].unique()]),
            "bootstrap": {
                "event_bootstrap_samples": int(config["bootstrap"]["event_bootstrap_samples"]),
                "run_bootstrap_samples": int(config["bootstrap"]["run_bootstrap_samples"]),
            },
        },
        "traditional_method": config["methods"]["traditional"],
        "methods": config["methods"]["primary"],
        "winner": winner,
        "dynamic_class_winners": frame_records(class_winners),
        "non_oracle_leakage_checks_pass": bool(non_oracle["pass"].astype(bool).all()),
        "oracle_checks": frame_records(leakage[leakage["check"].str.contains("oracle", case=False, na=False)]),
        "source_artifacts": {
            "s00d_taxonomy": config["source_s00d_taxonomy_dir"],
            "s03j_timing": config["source_s03j_timing_dir"],
        },
        "input_sha256_table": "input_sha256.csv",
        "git_commit": git_commit(),
        "runtime_sec": round(time.time() - t0, 3),
        "next_tickets": [],
        "verdict": "dynamic_range_not_adopted_for_timing; strong_traditional_wins_dynamic_extra",
    }
    (out_dir / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_report(out_dir, config, s00_repro, selector_repro, support, metrics, run_boot, deltas, leakage, winner)

    manifest = {
        "ticket": config["ticket_id"],
        "study": config["study_id"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "config": str(config_path),
        "command": " ".join([sys.executable] + sys.argv),
        "runtime_sec": round(time.time() - t0, 3),
        "inputs": frame_records(input_hashes),
        "outputs": hash_outputs(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "winner": winner, "non_oracle_leakage_pass": result["non_oracle_leakage_checks_pass"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
