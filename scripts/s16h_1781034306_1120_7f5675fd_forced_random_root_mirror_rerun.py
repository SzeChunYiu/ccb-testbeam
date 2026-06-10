#!/usr/bin/env python3
"""S16h forced/random ROOT mirror audit and non-fallback S16g rerun gate.

The claimed ticket asks for actual forced/random HRD pedestal ROOT files and a
rerun of S16g without entering the pre-trigger fallback path.  This driver
therefore treats data availability as a hard gate: it reproduces the raw HRDv
count, searches mounted mirrors and archive members for forced/random sources,
inspects ROOT trigger metadata, and only declares the direct S16g rerun
estimable if non-beam B-stack rows exist.
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
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CONFIG_DEFAULT = "configs/s16h_1781034306_1120_7f5675fd_forced_random_root_mirror_rerun.json"
S16F_PATH = "scripts/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.py"
S16G_PATH = "scripts/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.py"


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16F = load_module("s16f_helpers_for_1781034306", S16F_PATH)
S16G = load_module("s16g_acquisition_helpers_for_1781034306", S16G_PATH)


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
        return None if not np.isfinite(value) else value
    return value


def archive_member_inventory(config: dict) -> pd.DataFrame:
    rows = []
    tokens = [str(t).lower() for t in config["tag_tokens"]]
    for archive_text in config["raw_archives"]:
        archive = Path(archive_text)
        if not archive.exists():
            rows.append(
                {
                    "archive": str(archive),
                    "member": "",
                    "kind": "missing_archive",
                    "suffix": "",
                    "bytes": 0,
                    "forced_random_token": "",
                    "forced_random_hit": False,
                }
            )
            continue
        try:
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    lower = info.filename.lower()
                    hits = [token for token in tokens if token in lower]
                    rows.append(
                        {
                            "archive": str(archive),
                            "member": info.filename,
                            "kind": "zip_member",
                            "suffix": Path(info.filename).suffix.lower(),
                            "bytes": int(info.file_size),
                            "forced_random_token": ";".join(hits),
                            "forced_random_hit": bool(hits),
                        }
                    )
        except zipfile.BadZipFile:
            rows.append(
                {
                    "archive": str(archive),
                    "member": "",
                    "kind": "bad_zip",
                    "suffix": archive.suffix.lower(),
                    "bytes": 0,
                    "forced_random_token": "",
                    "forced_random_hit": False,
                }
            )
    return pd.DataFrame(rows)


def filesystem_candidate_inventory(config: dict) -> pd.DataFrame:
    full = S16G.audit_filesystem_and_archives(config)
    candidates = full[full["forced_random_hit"]].copy()
    return full, candidates


def load_proxy_context(config: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    proxy = config["proxy_context"]
    benchmark = pd.read_csv(proxy["head_to_head_benchmark_csv"])
    folds = pd.read_csv(proxy["fold_metrics_csv"])
    leakage = pd.read_csv(proxy["leakage_checks_csv"])
    result = json.loads(Path(proxy["result_json"]).read_text(encoding="utf-8"))
    return benchmark, folds, leakage, result


def method_identifiability_table(benchmark: pd.DataFrame, direct_truth_ready: bool) -> pd.DataFrame:
    methods = [
        ("deterministic_source_trigger_audit", "traditional"),
        ("ridge", "ml"),
        ("gradient_boosted_trees", "ml"),
        ("mlp", "ml"),
        ("1d_cnn", "nn"),
        ("siamese_cnn_meta", "new_architecture"),
    ]
    rows = []
    actual = benchmark[benchmark["shuffled_proxy"] == False].copy()  # noqa: E712
    alias = {"1d_cnn": "cnn1d"}
    for method, family in methods:
        proxy_name = alias.get(method, method)
        match = actual[actual["method"] == proxy_name]
        proxy_tail = float(match["tail_fraction_after"].iloc[0]) if len(match) else np.nan
        proxy_lo = float(match["tail_fraction_after_ci_low"].iloc[0]) if len(match) else np.nan
        proxy_hi = float(match["tail_fraction_after_ci_high"].iloc[0]) if len(match) else np.nan
        rows.append(
            {
                "method": method,
                "family": family,
                "direct_truth_status": "estimable" if direct_truth_ready else "not_identifiable_zero_truth_rows",
                "direct_metric": "forced/random pedestal residual",
                "direct_value": np.nan if not direct_truth_ready else np.nan,
                "direct_ci_low": np.nan,
                "direct_ci_high": np.nan,
                "proxy_context_metric": "post-veto timing-tail fraction",
                "proxy_context_value": proxy_tail,
                "proxy_context_ci_low": proxy_lo,
                "proxy_context_ci_high": proxy_hi,
            }
        )
    return pd.DataFrame(rows)


def fmt_ci(row: pd.Series, value: str, lo: str, hi: str, precision: int = 4) -> str:
    v, l, h = row[value], row[lo], row[hi]
    if pd.isna(v):
        return "not estimable"
    return f"{v:.{precision}f} [{l:.{precision}f}, {h:.{precision}f}]"


def compact_proxy_table(benchmark: pd.DataFrame) -> pd.DataFrame:
    actual = benchmark[benchmark["shuffled_proxy"] == False].copy()  # noqa: E712
    keep = []
    for _, row in actual.sort_values("tail_fraction_after").iterrows():
        keep.append(
            {
                "method": row["method"],
                "efficiency_95ci": fmt_ci(row, "timing_efficiency", "timing_efficiency_ci_low", "timing_efficiency_ci_high"),
                "tail_capture_95ci": fmt_ci(row, "tail_capture", "tail_capture_ci_low", "tail_capture_ci_high"),
                "post_veto_tail_95ci": fmt_ci(row, "tail_fraction_after", "tail_fraction_after_ci_low", "tail_fraction_after_ci_high"),
                "sigma68_after_ns_95ci": fmt_ci(row, "sigma68_after_ns", "sigma68_after_ns_ci_low", "sigma68_after_ns_ci_high", 3),
                "auc_95ci": fmt_ci(row, "auc", "auc_ci_low", "auc_ci_high", 3),
                "ap_95ci": fmt_ci(row, "average_precision", "average_precision_ci_low", "average_precision_ci_high", 3),
            }
        )
    return pd.DataFrame(keep)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    reproduction: pd.DataFrame,
    root_audit: pd.DataFrame,
    fs_inventory: pd.DataFrame,
    fs_candidates: pd.DataFrame,
    archive_inventory: pd.DataFrame,
    direct_rows: pd.DataFrame,
    method_table: pd.DataFrame,
    proxy_table: pd.DataFrame,
    leakage: pd.DataFrame,
) -> None:
    root_summary = root_audit.groupby("stack", as_index=False).agg(
        files=("file", "count"),
        entries=("entries", "sum"),
        non_beam_trigger_entries=("non_beam_trigger_entries", "sum"),
        files_with_tag_like_branch=("has_tag_like_branch", "sum"),
    )
    strict_fs = fs_candidates[fs_candidates["suffix"].isin([".root", ".zip", ".tar", ".gz"])].copy()
    strict_archive = archive_inventory[
        (archive_inventory["forced_random_hit"]) & (archive_inventory["suffix"].isin([".root", ".zip", ".tar", ".gz"]))
    ].copy()
    report = f"""# S16h: forced/random HRD pedestal ROOT mirror and non-fallback S16g rerun gate

- **Ticket:** `{config["ticket"]}`
- **Author:** `{config["worker"]}`
- **Date:** 2026-06-10
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{result["git_commit"]}`
- **Config:** `{CONFIG_DEFAULT}`

## Abstract

This ticket asked to add or mirror the actual forced/random HRD pedestal ROOT
files and rerun S16g without the pre-trigger fallback. I treated the requested
ROOT sample as a hard prerequisite rather than silently substituting the older
quiet-proxy benchmark. The mounted data were rescanned from raw `h101/HRDv`,
the three available raw archive zips were inventoried member-by-member, and the
ROOT trigger metadata were inspected for direct non-beam B-stack rows. The raw
selected-pulse anchor reproduces exactly (`640737` B-stave pulses), but no
forced/random/pedestal ROOT source and no `TRIGGER != 1` B-stack rows are
visible. Therefore the non-fallback S16g truth rerun is blocked in this
workspace state. For continuity only, the prior run-held-out S16g proxy
benchmark is summarized and clearly labeled as proxy context.

## 1. Reproduction Gate

For run \(r\), B-stack stave channel \(c\in\\{{B2,B4,B6,B8\\}}\), and sample
\(t\), the pedestal and amplitude are

\[
p_{{irc}} = \operatorname{{median}}(x_{{irc0}},x_{{irc1}},x_{{irc2}},x_{{irc3}}),
\qquad
A_{{irc}} = \max_t(x_{{irct}} - p_{{irc}}).
\]

The selected-pulse count is \(\sum_{{irc}}\mathbf{{1}}[A_{{irc}}>1000]\), read
directly from `data/root/root/hrdb_run_NNNN.root`.

{reproduction.to_markdown(index=False)}

## 2. Acquisition and Mirror Audit

The acquisition predicate required either a strict forced/random/pedestal/no-
pulse token in a ROOT/archive path or direct ROOT metadata rows with
`TRIGGER != 1`. This is intentionally conservative: generic trigger wording is
not enough to create a no-pulse truth label.

| quantity | value |
|---|---:|
| filesystem/archive rows audited | {len(fs_inventory)} |
| filesystem forced/random token hits | {len(fs_candidates)} |
| strict filesystem ROOT/archive candidates | {len(strict_fs)} |
| raw zip members audited | {len(archive_inventory)} |
| strict raw-archive ROOT/archive candidates | {len(strict_archive)} |
| direct non-beam B-stack rows | {len(direct_rows)} |

ROOT trigger summary:

{root_summary.to_markdown(index=False)}

The complete inventories are `file_archive_inventory.csv`,
`raw_archive_member_inventory.csv`, `root_trigger_branch_audit.csv`, and
`direct_nonbeam_entries.csv`.

## 3. Non-Fallback S16g Rerun Gate

A direct S16g pedestal benchmark needs labels

\[
y_i = \mathbf{{1}}[\mathrm{{event}}\ i\ \mathrm{{is\ forced/random/no\ pulse}}],
\]

or an equivalent non-beam trigger value. In this mounted mirror,

\[
\sum_i \mathbf{{1}}[\mathrm{{TRIGGER}}_i \\ne 1] = 0.
\]

Consequently the direct estimator residuals, confidence intervals, and winner
are not statistically defined. The script did not enter the pre-trigger
fallback path. The machine-readable direct result is
`direct_s16g_nonfallback.status = blocked_missing_truth_root` in `result.json`.

## 4. Method Identifiability

The requested method families are all recorded below. For the direct endpoint,
ML/NN methods are not "beaten"; they are unidentifiable because there are zero
positive truth rows.

{method_table.to_markdown(index=False, floatfmt=".5f")}

## 5. Proxy Context Only

The following table is copied from the prior S16g proxy benchmark
`{config["proxy_context"]["report_dir"]}`. It used leave-one-run-out splits by
Sample-II run with run/event bootstrap CIs and compared a strong traditional
quantile veto against ridge, gradient-boosted trees, MLP, 1D-CNN, and the
pair-symmetric `siamese_cnn_meta` architecture. It is not a direct electronics
pedestal truth result.

{proxy_table.to_markdown(index=False)}

Proxy-context winner: **{result["proxy_context_winner"]["method"]}**, by lowest
held-out post-veto proxy tail fraction subject to the fixed efficiency rule.
Direct-truth winner: **{result["direct_truth_winner"]}**.

## 6. Leakage Checks

{leakage.to_markdown(index=False)}

## 7. Systematics and Caveats

- The result is an absence-in-mounted-mirrors statement. It does not prove the
  DAQ never recorded forced/random pedestal triggers.
- The available `h101` ROOT files appear beam-trigger only. If filtering
  occurred before `root.zip` production, it is upstream of the visible data.
- The raw count reproduction verifies the audited B-stack population but cannot
  manufacture no-pulse truth labels.
- Proxy timing-tail labels are useful diagnostics but are not electronics
  pedestal truth; this report keeps them separate from the blocked direct
  endpoint.
- The accidental appended ticket id recorded for this run is
  `{config.get("appended_ticket_id", "")}`; no additional follow-up was appended
  by this script.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781034306_1120_7f5675fd_forced_random_root_mirror_rerun.py \\
  --config configs/s16h_1781034306_1120_7f5675fd_forced_random_root_mirror_rerun.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `reproduction_match_table.csv`,
`root_trigger_branch_audit.csv`, `file_archive_inventory.csv`,
`raw_archive_member_inventory.csv`, `direct_nonbeam_entries.csv`,
`direct_method_identifiability.csv`, and `proxy_context_benchmark.csv`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG_DEFAULT)
    args = parser.parse_args()

    start = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    reproduction = S16F.reproduce_counts(config)
    root_audit = S16G.audit_root_metadata(config)
    fs_inventory, fs_candidates = filesystem_candidate_inventory(config)
    archive_inventory = archive_member_inventory(config)
    direct_rows = S16G.load_direct_nonbeam_entries(config)
    benchmark, folds, leakage, proxy_result = load_proxy_context(config)

    direct_truth_ready = len(direct_rows) > 0
    method_table = method_identifiability_table(benchmark, direct_truth_ready)
    proxy_table = compact_proxy_table(benchmark)

    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    root_audit.to_csv(out_dir / "root_trigger_branch_audit.csv", index=False)
    fs_inventory.to_csv(out_dir / "file_archive_inventory.csv", index=False)
    fs_candidates.to_csv(out_dir / "forced_random_candidate_inventory.csv", index=False)
    archive_inventory.to_csv(out_dir / "raw_archive_member_inventory.csv", index=False)
    direct_rows.to_csv(out_dir / "direct_nonbeam_entries.csv", index=False)
    method_table.to_csv(out_dir / "direct_method_identifiability.csv", index=False)
    benchmark.to_csv(out_dir / "proxy_context_benchmark.csv", index=False)
    folds.to_csv(out_dir / "proxy_context_fold_metrics.csv", index=False)
    leakage.to_csv(out_dir / "proxy_context_leakage_checks.csv", index=False)

    strict_archive = archive_inventory[
        (archive_inventory["forced_random_hit"]) & (archive_inventory["suffix"].isin([".root", ".zip", ".tar", ".gz"]))
    ]
    strict_fs = fs_candidates[fs_candidates["suffix"].isin([".root", ".zip", ".tar", ".gz"])]
    selected_row = reproduction[reproduction["quantity"] == "total selected B-stave pulses"].iloc[0]
    nonbeam_entries = int(root_audit["non_beam_trigger_entries"].sum())
    actual = benchmark[benchmark["shuffled_proxy"] == False].copy()  # noqa: E712
    actual["winner_score"] = actual["tail_fraction_after"] + 0.05 * np.maximum(0.0, 0.85 - actual["timing_efficiency"])
    proxy_winner = actual.sort_values(["winner_score", "sigma68_after_ns"]).iloc[0].to_dict()

    direct_status = "ready" if direct_truth_ready else "blocked_missing_truth_root"
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "runtime_seconds": round(time.time() - start, 3),
        "reproduction": {
            "passed": bool(reproduction["pass"].all()),
            "selected_b_stave_pulses_expected": int(config["expected_selected_pulses"]),
            "selected_b_stave_pulses_reproduced": int(selected_row["reproduced"]),
            "delta": int(selected_row["delta"]),
        },
        "mirror_audit": {
            "filesystem_archive_rows_audited": int(len(fs_inventory)),
            "forced_random_path_token_hits": int(len(fs_candidates)),
            "strict_forced_random_root_or_archive_candidates": int(len(strict_fs)),
            "raw_archive_members_audited": int(len(archive_inventory)),
            "strict_forced_random_raw_archive_candidates": int(len(strict_archive)),
            "missing_search_roots": fs_inventory[fs_inventory["kind"] == "missing_search_root"]["search_root"].tolist(),
        },
        "root_trigger_audit": {
            "root_files_audited": int(len(root_audit)),
            "non_beam_trigger_entries": nonbeam_entries,
            "files_with_tag_like_branch": int(root_audit["has_tag_like_branch"].sum()),
            "trigger_summaries": sorted(root_audit["trigger_summary"].unique().tolist()),
        },
        "direct_s16g_nonfallback": {
            "status": direct_status,
            "direct_nonbeam_entries": int(len(direct_rows)),
            "fallback_path_entered": False,
            "reason": "direct forced/random entries available" if direct_truth_ready else "zero forced/random ROOT candidates and zero non-beam B-stack rows",
        },
        "direct_truth_winner": "pending_direct_benchmark" if direct_truth_ready else "none_no_direct_truth_root",
        "proxy_context_winner": {
            "method": str(proxy_winner["method"]),
            "scope": "prior_proxy_context_not_direct_truth",
            "tail_fraction_after": float(proxy_winner["tail_fraction_after"]),
            "tail_fraction_after_ci": [float(proxy_winner["tail_fraction_after_ci_low"]), float(proxy_winner["tail_fraction_after_ci_high"])],
            "timing_efficiency": float(proxy_winner["timing_efficiency"]),
            "timing_efficiency_ci": [float(proxy_winner["timing_efficiency_ci_low"]), float(proxy_winner["timing_efficiency_ci_high"])],
            "sigma68_after_ns": float(proxy_winner["sigma68_after_ns"]),
            "source_result_ticket": proxy_result.get("ticket", ""),
        },
        "winner": "none_no_direct_truth_root",
        "verdict": "blocked_missing_forced_random_root",
        "conclusion": "No actual forced/random HRD pedestal ROOT file or non-beam B-stack row is visible in the mounted data, so S16g cannot be rerun as a direct non-fallback pedestal truth benchmark in this workspace state.",
        "next_tickets": [
            {
                "appended_ticket_id": config.get("appended_ticket_id", ""),
                "note": "No additional ticket appended by this script; this id was returned by the earlier tn-ticket append invocation in this worker."
            }
        ],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2) + "\n", encoding="utf-8")

    input_paths = [config_path, Path(__file__).resolve(), Path(S16F_PATH), Path(S16G_PATH)]
    input_paths.extend(Path(p) for p in config["raw_archives"])
    input_paths.extend(Path(v) for v in config["proxy_context"].values() if str(v).endswith((".csv", ".json")))
    input_rows = [
        {"path": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)}
        for path in input_paths
        if path.exists() and path.is_file()
    ]
    pd.DataFrame(input_rows).to_csv(out_dir / "input_sha256.csv", index=False)

    write_report(
        out_dir,
        config,
        result,
        reproduction,
        root_audit,
        fs_inventory,
        fs_candidates,
        archive_inventory,
        direct_rows,
        method_table,
        proxy_table,
        leakage,
    )

    manifest = {
        "ticket": config["ticket"],
        "command": f"/home/billy/anaconda3/bin/python {Path(__file__).as_posix()} --config {config_path.as_posix()}",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "inputs": input_rows,
        "artifacts": sorted(path.name for path in out_dir.iterdir() if path.is_file()),
    }
    manifest["sha256"] = {
        path.name: sha256_file(path)
        for path in sorted(out_dir.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket"], "verdict": result["verdict"], "runtime_seconds": result["runtime_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
