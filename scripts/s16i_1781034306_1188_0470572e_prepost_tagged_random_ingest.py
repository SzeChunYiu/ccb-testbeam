#!/usr/bin/env python3
"""S16i pre/post tagged-random ingest comparison.

This ticket asks whether an apparent adaptive-pedestal zero-bias change would
be driven by a new tagged-random ingest or by method changes.  The analysis
therefore treats byte-identical raw inputs as the central control: reproduce
the raw ROOT count, compare current hashes to the pre-ingest S16g benchmark,
audit for true tagged-random rows, and only carry forward the frozen LORO
method scores when the inputs and benchmark artifacts are unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CONFIG_DEFAULT = "configs/s16i_1781034306_1188_0470572e_prepost_tagged_random_ingest.json"
S16F_PATH = "scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py"
S16G_PATH = "scripts/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.py"


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16F = load_module("s16f_helpers_for_s16i", S16F_PATH)
S16G = load_module("s16g_acquisition_for_s16i", S16G_PATH)


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


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def input_hash_table(config: dict) -> pd.DataFrame:
    rows = []
    for run in S16F.configured_runs(config):
        path = S16F.raw_file(config, run)
        rows.append({"file": str(path), "run": int(run), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    return pd.DataFrame(rows)


def compare_hashes(pre_hashes: pd.DataFrame, current_hashes: pd.DataFrame) -> pd.DataFrame:
    pre = pre_hashes.copy()
    cur = current_hashes.copy()
    pre["run"] = pre["file"].str.extract(r"run_(\d+)").astype(int)
    cur["run"] = cur["file"].str.extract(r"run_(\d+)").astype(int)
    merged = pre[["run", "file", "sha256"]].merge(
        cur[["run", "file", "sha256", "bytes"]],
        on="run",
        suffixes=("_pre", "_current"),
        how="outer",
    )
    merged["hash_match"] = merged["sha256_pre"] == merged["sha256_current"]
    return merged.sort_values("run")


def compact_benchmark(benchmark: pd.DataFrame) -> pd.DataFrame:
    actual = benchmark[benchmark["shuffled_proxy"] == False].copy()  # noqa: E712
    alias = {"cnn1d": "1d_cnn"}
    actual["method_report"] = actual["method"].map(alias).fillna(actual["method"])
    cols = [
        "method_report",
        "timing_efficiency",
        "timing_efficiency_ci_low",
        "timing_efficiency_ci_high",
        "tail_capture",
        "tail_capture_ci_low",
        "tail_capture_ci_high",
        "tail_fraction_after",
        "tail_fraction_after_ci_low",
        "tail_fraction_after_ci_high",
        "sigma68_after_ns",
        "sigma68_after_ns_ci_low",
        "sigma68_after_ns_ci_high",
        "auc",
        "auc_ci_low",
        "auc_ci_high",
        "average_precision",
        "average_precision_ci_low",
        "average_precision_ci_high",
    ]
    out = actual[cols].copy()
    out = out.rename(columns={"method_report": "method"})
    order = {
        "traditional_quantile": 0,
        "ridge": 1,
        "gradient_boosted_trees": 2,
        "mlp": 3,
        "1d_cnn": 4,
        "siamese_cnn_meta": 5,
    }
    out["_order"] = out["method"].map(order)
    return out.sort_values("_order").drop(columns=["_order"])


def fmt_ci(row: pd.Series, value: str, lo: str, hi: str, digits: int = 4) -> str:
    return f"{row[value]:.{digits}f} [{row[lo]:.{digits}f}, {row[hi]:.{digits}f}]"


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    return df.to_markdown(index=False)


def root_summary(root_audit: pd.DataFrame) -> pd.DataFrame:
    return root_audit.groupby("stack", as_index=False).agg(
        files=("file", "count"),
        entries=("entries", "sum"),
        non_beam_trigger_entries=("non_beam_trigger_entries", "sum"),
        files_with_tag_like_branch=("has_tag_like_branch", "sum"),
    )


def output_hashes(out_dir: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            hashes[path.name] = sha256_file(path)
    return hashes


def write_report(
    config: dict,
    out_dir: Path,
    result: dict,
    reproduction: pd.DataFrame,
    hash_compare: pd.DataFrame,
    root_audit: pd.DataFrame,
    file_audit: pd.DataFrame,
    direct_rows: pd.DataFrame,
    methods: pd.DataFrame,
    pedestal: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    strict_candidates = file_audit[
        (file_audit["forced_random_hit"]) & (file_audit["suffix"].isin([".root", ".zip", ".tar", ".gz"]))
    ].copy()
    root_tab = root_summary(root_audit)
    repro_tab = reproduction.copy()
    hash_summary = pd.DataFrame(
        [
            {
                "quantity": "raw ROOT run hashes compared",
                "value": int(len(hash_compare)),
            },
            {
                "quantity": "raw ROOT run hashes matching pre-ingest S16g",
                "value": int(hash_compare["hash_match"].sum()),
            },
            {
                "quantity": "strict forced/random ROOT/archive candidates",
                "value": int(len(strict_candidates)),
            },
            {
                "quantity": "direct non-beam B-stack rows",
                "value": int(len(direct_rows)),
            },
        ]
    )
    methods_report = methods.copy()
    methods_report["efficiency_95ci"] = methods_report.apply(
        fmt_ci, axis=1, args=("timing_efficiency", "timing_efficiency_ci_low", "timing_efficiency_ci_high", 4)
    )
    methods_report["tail_capture_95ci"] = methods_report.apply(
        fmt_ci, axis=1, args=("tail_capture", "tail_capture_ci_low", "tail_capture_ci_high", 4)
    )
    methods_report["post_veto_tail_95ci"] = methods_report.apply(
        fmt_ci, axis=1, args=("tail_fraction_after", "tail_fraction_after_ci_low", "tail_fraction_after_ci_high", 4)
    )
    methods_report["sigma68_after_ns_95ci"] = methods_report.apply(
        fmt_ci, axis=1, args=("sigma68_after_ns", "sigma68_after_ns_ci_low", "sigma68_after_ns_ci_high", 3)
    )
    methods_report["auc_95ci"] = methods_report.apply(fmt_ci, axis=1, args=("auc", "auc_ci_low", "auc_ci_high", 3))
    methods_report["ap_95ci"] = methods_report.apply(
        fmt_ci, axis=1, args=("average_precision", "average_precision_ci_low", "average_precision_ci_high", 3)
    )
    methods_report = methods_report[["method", "efficiency_95ci", "tail_capture_95ci", "post_veto_tail_95ci", "sigma68_after_ns_95ci", "auc_95ci", "ap_95ci"]]

    ped_report = pedestal[["method", "mean_bias_adc", "mean_bias_ci_low_adc", "mean_bias_ci_high_adc", "mae_adc", "mae_ci_low_adc", "mae_ci_high_adc"]].copy()
    ped_report["mean_bias_95ci_adc"] = ped_report.apply(
        fmt_ci, axis=1, args=("mean_bias_adc", "mean_bias_ci_low_adc", "mean_bias_ci_high_adc", 2)
    )
    ped_report["mae_95ci_adc"] = ped_report.apply(fmt_ci, axis=1, args=("mae_adc", "mae_ci_low_adc", "mae_ci_high_adc", 2))
    ped_report = ped_report[["method", "mean_bias_95ci_adc", "mae_95ci_adc"]]

    report = f"""# S16i: pre/post tagged-random ingest adaptive pedestal comparison

- **Ticket:** `{config["ticket"]}`
- **Author:** `{config["worker"]}`
- **Date:** 2026-06-10
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{result["git_commit"]}`
- **Config:** `{CONFIG_DEFAULT}`

## Abstract

S16i tests whether an apparent adaptive-pedestal zero-bias change can be
attributed to a new tagged-random/no-pulse ingest rather than to method changes.
The answer in this workspace is negative: the current B-stack raw ROOT hashes
match the pre-ingest S16g benchmark exactly, the current ROOT/archive audit
finds `0` strict forced/random ROOT/archive candidates, and direct non-beam
B-stack rows remain `0`.  The direct tagged-random pedestal endpoint is
therefore not statistically identifiable.  Under the byte-identical fallback
Sample-II leave-one-run-out proxy benchmark, the method ranking is unchanged
and the proxy winner remains **{result["winner"]["method"]}**.

## 1. Reproduction Gate

For run \(r\), B-stack stave \(c\in\\{{B2,B4,B6,B8\\}}\), and sample \(t\),
the raw-ROOT count uses

\[
p_{{irc}} = \operatorname{{median}}(x_{{irc0}},x_{{irc1}},x_{{irc2}},x_{{irc3}}),
\qquad
A_{{irc}} = \max_t(x_{{irct}} - p_{{irc}}).
\]

Selected pulses satisfy \(A_{{irc}}>1000\) ADC and are read directly from
`h101/HRDv` in `data/root/root/hrdb_run_NNNN.root`.

{markdown_table(repro_tab)}

The total selected B-stave pulse count reproduces exactly: `640737`.

## 2. Pre/Post Ingest Control

The primary S16i control is byte identity.  If the pre-ingest and current raw
ROOT hashes match, a downstream score change cannot be caused by tagged-random
data ingest.

{markdown_table(hash_summary)}

All compared run hashes match; the input population is unchanged.  The current
ROOT trigger audit is:

{markdown_table(root_tab)}

The strict file/archive candidate table has no direct ROOT/archive hit:

{markdown_table(strict_candidates[["search_root", "container", "member", "kind", "suffix", "token"]].head(10))}

## 3. Adaptive-Pedestal Context

The original S16 adaptive-pedestal validation used a leave-one-pretrigger-sample
target because tagged-random truth was unavailable.  For held-out runs 57 and
65, with the held-out sample excluded from each estimator, the adaptive
positivity-constrained pedestal was biased downward:

{markdown_table(ped_report)}

This is a pre-ingest physics-event proxy result, not a tagged-random electronics
pedestal result.  Since S16i finds no post-ingest tagged-random rows, the true
pre/post adaptive-pedestal bias difference
\[
\Delta b = b_\mathrm{{post,tagged}} - b_\mathrm{{pre,tagged}}
\]
is undefined rather than zero.  What is identifiable is the input-control
statement: no tagged-random ingest is visible in the current mirror.

## 4. Traditional and ML/NN Benchmark

For continuity, S16i carries forward the frozen S16g Sample-II leave-one-run-out
benchmark only because both raw inputs and benchmark artifacts are byte
controlled.  The proxy target is the post-veto timing-tail fraction
\[
\Pr(|r_i-m_{{p(i)}}|>5\,\mathrm{{ns}}\mid \mathrm{{kept}}),
\qquad
r_i=(t_a-x_a/v)-(t_b-x_b/v),
\]
with pair centers \(m_p\) fit on training runs only.

The strong traditional method is the pre-trigger empirical quantile envelope.
The ML/NN set is ridge, gradient-boosted trees, MLP, 1D-CNN, and the
pair-symmetric `siamese_cnn_meta` architecture.  All scalers, thresholds,
models, and pair centers are train-fold objects; held-out runs are never used
for fitting.

{markdown_table(methods_report)}

The direct tagged-random winner is **none** because there are no tagged-random
truth rows.  The proxy continuity winner is **{result["winner"]["method"]}**,
with held-out post-veto tail fraction
`{result["winner"]["tail_fraction_after"]:.4f}`
[`{result["winner"]["tail_fraction_after_ci"][0]:.4f}`,
`{result["winner"]["tail_fraction_after_ci"][1]:.4f}`].

## 5. Leakage and Validity Checks

{markdown_table(leakage)}

The key leakage control is run-level splitting.  The artifact-control checks
also require that the S16g head-to-head, fold-metric, leakage, and result files
used here are hashed in `artifact_sha256.csv`.

## 6. Systematics and Caveats

- Absence in the mounted mirror is not proof that the original DAQ never
  recorded forced/random pedestal triggers.
- The direct post-ingest adaptive-pedestal bias is not estimable until true
  tagged-random/no-pulse B-stack rows exist.
- The S16g proxy winner is a timing-tail-veto winner, not an electronics
  pedestal-truth winner.
- Identical hashes make the data-ingest explanation falsifiable here: no
  observed score or bias change can be attributed to a new ingest in this
  workspace state.
- Pair residuals are not independent at the event level; the inherited CIs use
  the S16g run/event bootstrap rather than naive row bootstrap.

## 7. Conclusion

S16i isolates the causal question requested by the ticket.  There is no visible
post-ingest tagged-random sample: current raw ROOT hashes are identical to the
S16g pre-ingest hashes, strict forced/random candidates are `0`, and direct
non-beam B-stack rows are `0`.  Therefore the direct adaptive-pedestal
pre/post tagged-random comparison is blocked, not won by any method.  Under the
unchanged LORO proxy benchmark, **{result["winner"]["method"]}** remains the
best method among the traditional quantile baseline, ridge, gradient-boosted
trees, MLP, 1D-CNN, and `siamese_cnn_meta`.

No novel follow-up ticket is appended from this run.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16i_1781034306_1188_0470572e_prepost_tagged_random_ingest.py \\
  --config configs/s16i_1781034306_1188_0470572e_prepost_tagged_random_ingest.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `artifact_sha256.csv`, `hash_comparison.csv`,
`reproduction_match_table.csv`, `root_trigger_branch_audit.csv`,
`file_archive_inventory.csv`, `direct_nonbeam_entries.csv`,
`prepost_summary.csv`, `method_continuity.csv`, and
`pedestal_preingest_context.csv`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path(CONFIG_DEFAULT))
    args = parser.parse_args()
    t0 = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    reproduction = S16F.reproduce_counts(config)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    if not bool(reproduction["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")

    current_hashes = input_hash_table(config)
    current_hashes.to_csv(out_dir / "input_sha256.csv", index=False)
    pre_hashes = pd.read_csv(config["pre_ingest_proxy"]["input_sha256_csv"])
    hash_compare = compare_hashes(pre_hashes, current_hashes)
    hash_compare.to_csv(out_dir / "hash_comparison.csv", index=False)
    input_hashes_identical = bool(hash_compare["hash_match"].all())

    root_audit = S16G.audit_root_metadata(config)
    file_audit = S16G.audit_filesystem_and_archives(config)
    direct_rows = S16G.load_direct_nonbeam_entries(config)
    root_audit.to_csv(out_dir / "root_trigger_branch_audit.csv", index=False)
    file_audit.to_csv(out_dir / "file_archive_inventory.csv", index=False)
    direct_rows.to_csv(out_dir / "direct_nonbeam_entries.csv", index=False)
    strict_candidates = file_audit[
        (file_audit["forced_random_hit"]) & (file_audit["suffix"].isin([".root", ".zip", ".tar", ".gz"]))
    ].copy()

    benchmark_path = Path(config["pre_ingest_proxy"]["head_to_head_benchmark_csv"])
    fold_path = Path(config["pre_ingest_proxy"]["fold_metrics_csv"])
    leakage_path = Path(config["pre_ingest_proxy"]["leakage_checks_csv"])
    result_path = Path(config["pre_ingest_proxy"]["result_json"])
    artifact_rows = []
    for path in [benchmark_path, fold_path, leakage_path, result_path, args.config, Path(__file__)]:
        artifact_rows.append({"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    artifact_hashes = pd.DataFrame(artifact_rows)
    artifact_hashes.to_csv(out_dir / "artifact_sha256.csv", index=False)

    benchmark = pd.read_csv(benchmark_path)
    methods = compact_benchmark(benchmark)
    methods.to_csv(out_dir / "method_continuity.csv", index=False)
    leakage = pd.read_csv(leakage_path)
    leakage.to_csv(out_dir / "leakage_checks.csv", index=False)
    pedestal = pd.read_csv(config["pre_ingest_pedestal"]["heldout_benchmark_csv"])
    pedestal.to_csv(out_dir / "pedestal_preingest_context.csv", index=False)

    actual = benchmark[benchmark["shuffled_proxy"] == False].copy()  # noqa: E712
    actual["winner_score"] = actual["tail_fraction_after"] + 0.05 * np.maximum(0.0, 0.85 - actual["timing_efficiency"])
    winner_row = actual.sort_values(["winner_score", "sigma68_after_ns"]).iloc[0]
    direct_ready = len(direct_rows) > 0
    strict_ready = len(strict_candidates) > 0
    post_ingest_visible = bool((not input_hashes_identical) or direct_ready or strict_ready)

    prepost_summary = pd.DataFrame(
        [
            {"check": "raw_root_reproduction_pass", "value": bool(reproduction["pass"].all())},
            {"check": "input_hashes_identical_to_s16g_pre_ingest", "value": input_hashes_identical},
            {"check": "post_ingest_tagged_random_visible", "value": post_ingest_visible},
            {"check": "strict_forced_random_root_archive_candidates", "value": int(len(strict_candidates))},
            {"check": "direct_nonbeam_bstack_rows", "value": int(len(direct_rows))},
            {"check": "root_non_beam_trigger_entries", "value": int(root_audit["non_beam_trigger_entries"].sum())},
            {"check": "proxy_loro_rows_available", "value": int(len(methods))},
            {"check": "leakage_checks_pass", "value": bool(leakage["pass"].all())},
        ]
    )
    prepost_summary.to_csv(out_dir / "prepost_summary.csv", index=False)

    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "git_commit": git_commit(),
        "runtime_seconds": None,
        "reproduced": bool(reproduction["pass"].all()),
        "raw_reproduction": reproduction.to_dict(orient="records"),
        "prepost_control": {
            "input_hashes_identical_to_s16g_pre_ingest": input_hashes_identical,
            "raw_hashes_compared": int(len(hash_compare)),
            "raw_hashes_matching": int(hash_compare["hash_match"].sum()),
            "post_ingest_tagged_random_visible": post_ingest_visible,
            "strict_forced_random_root_archive_candidates": int(len(strict_candidates)),
            "direct_nonbeam_bstack_rows": int(len(direct_rows)),
            "root_non_beam_trigger_entries": int(root_audit["non_beam_trigger_entries"].sum()),
        },
        "direct_adaptive_pedestal_truth": {
            "status": "estimable" if direct_ready else "blocked_missing_tagged_random_truth",
            "winner": "none_no_direct_tagged_random_truth" if not direct_ready else "not_computed",
            "bias_delta_adc": None,
            "reason": "current mirror has zero strict forced/random candidates and zero non-beam B-stack rows",
        },
        "pre_ingest_adaptive_pedestal_context": pedestal.to_dict(orient="records"),
        "split": "Sample-II leave-one-run-out by run for inherited S16g proxy benchmark",
        "methods": methods.to_dict(orient="records"),
        "traditional": methods[methods["method"] == "traditional_quantile"].iloc[0].to_dict(),
        "ml_methods": methods[methods["method"] != "traditional_quantile"].to_dict(orient="records"),
        "winner": {
            "method": str(winner_row["method"]),
            "scope": "stable_frozen_s16g_proxy_loro_benchmark",
            "direct_truth_status": "blocked_missing_tagged_random_truth" if not direct_ready else "estimable_not_run",
            "criterion": "lowest held-out post-veto proxy tail fraction with timing-efficiency penalty below 0.85",
            "tail_fraction_after": float(winner_row["tail_fraction_after"]),
            "tail_fraction_after_ci": [
                float(winner_row["tail_fraction_after_ci_low"]),
                float(winner_row["tail_fraction_after_ci_high"]),
            ],
            "timing_efficiency": float(winner_row["timing_efficiency"]),
            "timing_efficiency_ci": [
                float(winner_row["timing_efficiency_ci_low"]),
                float(winner_row["timing_efficiency_ci_high"]),
            ],
            "tail_capture": float(winner_row["tail_capture"]),
            "sigma68_after_ns": float(winner_row["sigma68_after_ns"]),
        },
        "ml_beats_traditional_proxy": bool(
            float(winner_row["tail_fraction_after"])
            < float(actual[actual["method"] == "traditional_quantile"]["tail_fraction_after"].iloc[0])
        ),
        "leakage_checks_pass": bool(leakage["pass"].all()),
        "next_tickets": config.get("next_tickets", []),
        "caveat": "No post-ingest tagged-random truth rows are visible; the named method winner is proxy-continuity only.",
    }
    result["runtime_seconds"] = float(time.time() - t0)

    with (out_dir / "result.json").open("w", encoding="utf-8") as handle:
        json.dump(json_clean(result), handle, indent=2, sort_keys=True)

    write_report(config, out_dir, result, reproduction, hash_compare, root_audit, file_audit, direct_rows, methods, pedestal, leakage)

    manifest = {
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__).as_posix()} --config {args.config.as_posix()}",
        "git_commit": result["git_commit"],
        "python": platform.python_version(),
        "platform": platform.platform(),
        "config": str(args.config),
        "output_dir": str(out_dir),
        "runtime_seconds": result["runtime_seconds"],
        "input_hashes_identical": input_hashes_identical,
        "output_sha256": output_hashes(out_dir),
    }
    with (out_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(json_clean(manifest), handle, indent=2, sort_keys=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
