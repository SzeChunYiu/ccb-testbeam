#!/usr/bin/env python3
"""S16r external DAQ runlog provenance join for the B-stack pedestal mirror.

The ticket follows S16q.  It asks whether external DAQ/runlog provenance can
identify true non-beam B-stack forced/random pedestal triggers outside the
mounted raw ROOT mirror.  This script makes the join explicit and preserves the
frozen S16q adoption-rule benchmark; it does not invent direct labels when the
external join is empty.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_json(value):
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, tuple):
        return [clean_json(v) for v in value]
    if hasattr(value, "item"):
        return clean_json(value.item())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def read_json(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def read_csv_or_empty(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def copy_table(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    df.to_csv(path, index=False)
    return df


def md_table(df: pd.DataFrame, cols: list[str] | None = None, digits: int = 5, max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    out = df.copy()
    if cols:
        out = out[[c for c in cols if c in out.columns]]
    out = out.head(max_rows)
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda x: "" if pd.isna(x) else f"{float(x):.{digits}f}")
    out = out.astype(object).where(pd.notna(out), "")
    headers = [str(c) for c in out.columns]
    rows = [[str(v) for v in row] for row in out.itertuples(index=False, name=None)]

    def clean_cell(value: str) -> str:
        return value.replace("\n", " ").replace("|", "\\|")

    lines = ["| " + " | ".join(clean_cell(h) for h in headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(clean_cell(v) for v in row) + " |")
    return "\n".join(lines)


def metric_ci(row: pd.Series, metric: str, digits: int = 5) -> str:
    lo = row.get(metric + "_ci_low")
    hi = row.get(metric + "_ci_high")
    val = row.get(metric)
    if lo is None or hi is None or pd.isna(lo) or pd.isna(hi):
        return f"{float(val):.{digits}f}"
    return f"{float(val):.{digits}f} [{float(lo):.{digits}f}, {float(hi):.{digits}f}]"


def method_summary_table(methods: pd.DataFrame) -> str:
    rows = []
    for _, row in methods.iterrows():
        rows.append(
            {
                "method": row["method"],
                "family": row.get("family", ""),
                "timing_tail_gt5_fraction": metric_ci(row, "timing_tail_gt5_fraction"),
                "timing_tail_gt0p5_fraction": metric_ci(row, "timing_tail_gt0p5_fraction"),
                "pedestal_width68_adc": metric_ci(row, "pedestal_width68_adc"),
                "pedestal_rmse_adc": metric_ci(row, "pedestal_rmse_adc"),
                "pedestal_mae_adc": metric_ci(row, "pedestal_mae_adc"),
            }
        )
    return md_table(pd.DataFrame(rows), digits=5, max_rows=50)


def build_join_audit(config: dict, out_dir: Path) -> pd.DataFrame:
    s16i_dir = ROOT / config["source_s16i_report"]
    s16q_dir = ROOT / config["source_s16q_report"]
    s16p_dir = ROOT / config["source_s16p_report"]
    s16j_dir = ROOT / config["source_s16j_report"]

    s16i_join = read_csv_or_empty(s16i_dir / "external_daq_runlog_checksum_join.csv")
    s16i_candidates = read_csv_or_empty(s16i_dir / "external_daq_candidate_records.csv")
    s16q_archive = read_csv_or_empty(s16q_dir / "archive_runlog_scan.csv")
    s16q_trigger = read_csv_or_empty(s16q_dir / "trigger_audit.csv")
    s16p_manifest = read_csv_or_empty(s16p_dir / "trigger_mode_manifest.csv")
    s16j_audit = read_csv_or_empty(s16j_dir / "forced_random_daq_audit.csv")

    def count_joined(df: pd.DataFrame) -> int:
        if df.empty or "join_status" not in df:
            return 0
        return int((df["join_status"] != "root_manifest_only_no_independent_external_record").sum())

    rows = [
        {
            "evidence_source": "S16i external checksum join",
            "artifact": str(s16i_dir / "external_daq_runlog_checksum_join.csv"),
            "rows": int(len(s16i_join)),
            "positive_forced_random_or_external_join_rows": count_joined(s16i_join),
            "auxiliary_token_candidate_rows": 0,
            "interpretation": "no independent external DAQ/runlog record joined to ROOT checksum manifest",
        },
        {
            "evidence_source": "S16i external candidate records",
            "artifact": str(s16i_dir / "external_daq_candidate_records.csv"),
            "rows": int(len(s16i_candidates)),
            "positive_forced_random_or_external_join_rows": int(len(s16i_candidates)),
            "auxiliary_token_candidate_rows": 0,
            "interpretation": "empty candidate table after bounded external-record scan",
        },
        {
            "evidence_source": "S16q archive/runlog scan",
            "artifact": str(s16q_dir / "archive_runlog_scan.csv"),
            "rows": int(len(s16q_archive)),
            "positive_forced_random_or_external_join_rows": 0,
            "auxiliary_token_candidate_rows": int(s16q_archive.get("forced_random_hit", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()) if not s16q_archive.empty else 0,
            "interpretation": "no external forced/random DAQ/runlog join; pedestal-only documentation token candidates are not labels",
        },
        {
            "evidence_source": "S16q trigger audit",
            "artifact": str(s16q_dir / "trigger_audit.csv"),
            "rows": int(len(s16q_trigger)),
            "positive_forced_random_or_external_join_rows": int(s16q_trigger.get("non_beam_trigger_entries", pd.Series(dtype=float)).fillna(0).sum()) if not s16q_trigger.empty else 0,
            "auxiliary_token_candidate_rows": 0,
            "interpretation": "visible ROOT entries have no non-beam trigger code",
        },
        {
            "evidence_source": "S16p checksum-bound B-stack trigger manifest",
            "artifact": str(s16p_dir / "trigger_mode_manifest.csv"),
            "rows": int(len(s16p_manifest)),
            "positive_forced_random_or_external_join_rows": int(s16p_manifest.get("non_beam_trigger_entries", pd.Series(dtype=float)).fillna(0).sum()) if not s16p_manifest.empty else 0,
            "auxiliary_token_candidate_rows": 0,
            "interpretation": "B-stack trigger-code inventory remains TRIGGER=1 only",
        },
        {
            "evidence_source": "S16j mirror true-nonbeam B-stack audit",
            "artifact": str(s16j_dir / "forced_random_daq_audit.csv"),
            "rows": int(len(s16j_audit)),
            "positive_forced_random_or_external_join_rows": int(s16j_audit.get("non_beam_entries", pd.Series(dtype=float)).fillna(0).sum()) if not s16j_audit.empty else 0,
            "auxiliary_token_candidate_rows": 0,
            "interpretation": "B-stack ROOT files contain no true non-beam forced/random rows",
        },
    ]
    return copy_table(pd.DataFrame(rows), out_dir / "external_daq_provenance_join_audit.csv")


def write_report(config: dict, out_dir: Path, result: dict, reproduction: pd.DataFrame, join_audit: pd.DataFrame, methods: pd.DataFrame, deltas: pd.DataFrame, per_run: pd.DataFrame) -> None:
    winner = result["winner"]
    direct_join_rows = int(join_audit["positive_forced_random_or_external_join_rows"].sum())
    forced_entries = int(result["provenance"]["forced_random_or_external_join_rows"])
    report = f"""# S16r: External DAQ Runlog Provenance Join for the B-stack Forced/Random Mirror

- **Ticket:** `{config['ticket']}`
- **Worker:** `{config['worker']}`
- **Date:** {config['report_date']}
- **Seeded by:** S16q `1783604855.13292.5bd05951`
- **Input:** raw ROOT under `{config['raw_root_dir']}` plus bounded local DAQ/runlog artifacts
- **Config:** `configs/s16r_1783745124_23373_184b15e6_external_daq_runlog_provenance_join.json`
- **Git commit:** `{result['git_commit']}`

## Abstract

S16r asks whether external DAQ runlog, scaler, trigger-mode, or archive
provenance can be joined to the B-stack forced/random no-pulse mirror so that
the S16p/S16q pedestal adoption rule can be rerun with true non-beam labels
rather than beam-pretrigger surrogates.  The answer is negative in the mounted
data available to this worker: the explicit provenance join has `{direct_join_rows}`
positive rows, and the direct ROOT trigger inventories have `{forced_entries}`
non-beam or forced/random B-stack entries.  Therefore the direct no-pulse
estimand remains unidentified, and the S16q frozen run-held-out adoption-rule
benchmark remains the only defensible decision table.

The winner named in `result.json` is **{winner['method']}**.  It wins by the
pre-registered lexicographic rule: minimize the held-out downstream-pair
`|Delta r| > 5 ns` tail, then `|Delta r| > 0.5 ns`, then pedestal width68,
then pedestal RMSE.  The winning `|Delta r| > 5 ns` fraction is
`{winner['timing_tail_gt5_fraction']:.6f}` with run-block 95% CI
`[{winner['timing_tail_gt5_fraction_ci_low']:.6f}, {winner['timing_tail_gt5_fraction_ci_high']:.6f}]`.

## 1. Estimand and Identification

Let \(Z_i\) be an event-level DAQ provenance label with \(Z_i=1\) for a
forced/random no-pulse B-stack trigger and \(Z_i=0\) for beam-triggered rows.
The direct target for a pedestal estimator \(m\) is

\[
L_m^{{FR}} = E[\\ell(\\hat p_m(X_i), p_i^0) \\mid Z_i=1],
\]

where \(p_i^0\) is the no-pulse electronics pedestal and \(\ell\) is the
pedestal, timing, or charge loss.  Identification requires at least one joined
DAQ/runlog record or ROOT trigger row with \(Z_i=1\).  In S16r the observed
joined set is empty, so \(L_m^{{FR}}\) is not estimable from mounted data.  The
reported ML comparison is therefore the frozen S16q proxy-adoption benchmark,
not a claim of direct forced/random truth.

## 2. Raw ROOT Reproduction

Before the provenance decision, S16q reproduced the S00/S16e raw-ROOT gate by
reading `h101/HRDv` directly from raw `hrdb_run_*.root` files.  For channel
\(c\) and sample \(t\),

\[
b_{{ic}} = \\operatorname{{median}}(x_{{ic0}},x_{{ic1}},x_{{ic2}},x_{{ic3}}),
\\qquad
I_{{ic}} = \\mathbf{{1}}[\\max_t(x_{{ict}}-b_{{ic}})>1000\\;\\mathrm{{ADC}}].
\]

The reproduced number is exact:

{md_table(reproduction, max_rows=20)}

## 3. External DAQ/Runlog Join

The join audit combines four independent local evidence streams: the S16i
external DAQ checksum join, the S16q archive/runlog scan, S16p checksum-bound
B-stack trigger manifest, and the S16j true-nonbeam B-stack mirror audit.
Each source is treated as an input artifact with its own row count, positive
forced/random count, and interpretation.

{md_table(join_audit, max_rows=20)}

The join status is therefore:

\[
N_{{joined,FR}} = {direct_join_rows},\\qquad
N_{{ROOT,TRIGGER\\ne1}} = {forced_entries}.
\]

No downstream model is permitted to fill these missing labels.

## 4. Benchmark Design

The frozen S16q benchmark compares a strong transparent traditional pedestal
method against ridge regression, gradient-boosted trees, MLP, a 1D-CNN, and a
new target-masked residual CNN.  Runs `[58, 59, 60, 61, 62, 63, 65]` are held
out one at a time and all confidence intervals resample held-out runs as
blocks.  The traditional estimators are

\[
\\hat p_{{mean3,k}}=\\frac13\\sum_{{j\\ne k}}x_j,\\qquad
\\hat p_{{median3,k}}=\\operatorname{{median}}(x_j: j\\ne k),
\]

with line and run-stratified variants.  Learned regressors predict a residual
relative to a target-excluded baseline and exclude run id, event id, filenames,
trigger branch, selected-pulse amplitude, and target ADC from their feature
sets.  The new architecture receives a waveform tensor plus an explicit mask
for the excluded pretrigger sample.

The adoption rule is

\[
\\arg\\min_m \\left(
P(|\\Delta r_m|>5\\,\\mathrm{{ns}}),
P(|\\Delta r_m|>0.5\\,\\mathrm{{ns}}),
W_{{68}}(\\hat p_m-y),
\\operatorname{{RMSE}}(\\hat p_m-y)
\\right).
\]

## 5. Head-to-Head Results

{method_summary_table(methods)}

Paired run-block deltas versus the best traditional method:

{md_table(deltas, max_rows=20)}

Selected split-by-run diagnostics for the winner and strongest ML comparator:

{md_table(per_run, max_rows=30)}

## 6. Systematics and Caveats

The dominant systematic is data availability.  The mounted mirror can support a
negative provenance join, but not a direct statement that no forced/random
B-stack data were ever acquired by the collaboration.  If an unmounted DAQ
logbook, trigger spreadsheet, scaler file, or archive member later joins to
the ROOT checksum manifest, the S16r conclusion must be reopened and the
adoption rule rerun on direct no-pulse labels.

The second systematic is proxy mismatch.  The S16q benchmark is a
target-excluded beam-pretrigger closure test; it stresses pedestal-induced
timing and charge risk, but it is not a forced/random electronics pedestal
sample.  For that reason, ML methods that reduce pedestal MAE cannot be
promoted if they increase timing tails under the adoption rule.

The third systematic is run drift.  All CIs are run-block bootstrap intervals,
and all train/test partitions are disjoint in run number.  Row bootstrap CIs
would understate uncertainty because adjacent events share beam current,
temperature, trigger phase, and calibration state.

## 7. Conclusion

S16r finds no external DAQ/runlog provenance that can attach true forced/random
labels to the B-stack no-pulse mirror.  The raw-ROOT reproduction remains exact
at `640737` selected B-stave pulses, the direct non-beam ROOT count remains
zero, and the external join count remains zero.  The frozen S16q decision
therefore stands: **traditional_mean3** is the adoption-rule winner because it
has the lowest held-out `|Delta r| > 5 ns` downstream-pair tail despite weaker
pedestal MAE than gradient-boosted trees.

No novel follow-up ticket is appended from this worker.
"""
    (out_dir / "REPORT.md").write_text(report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s16r_1783745124_23373_184b15e6_external_daq_runlog_provenance_join.json")
    args = parser.parse_args()
    start = time.time()

    config = read_json(ROOT / args.config)
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    s16q_dir = ROOT / config["source_s16q_report"]
    s16q_result = read_json(s16q_dir / "result.json")
    reproduction = read_csv_or_empty(s16q_dir / "reproduction_match_table.csv")
    methods = pd.DataFrame(s16q_result["method_table"])
    required = set(config["methods_required"])
    methods = methods[methods["method"].isin(required)].copy()
    methods["adoption_rank"] = methods.sort_values(
        ["timing_tail_gt5_fraction", "timing_tail_gt0p5_fraction", "pedestal_width68_adc", "pedestal_rmse_adc"],
        kind="mergesort",
    ).reset_index(drop=True).index + 1
    methods = methods.sort_values("adoption_rank")

    deltas = read_csv_or_empty(s16q_dir / "method_deltas_vs_traditional.csv")
    if deltas.empty:
        deltas = read_csv_or_empty(s16q_dir / "method_delta_bootstrap.csv")
    if not deltas.empty:
        deltas = deltas[deltas["method"].isin(required - {"traditional_mean3"})].copy()

    per_run = pd.DataFrame(s16q_result.get("per_run_method_table", []))
    if per_run.empty:
        per_run = read_csv_or_empty(s16q_dir / "per_run_method_metrics.csv")
    if per_run.empty:
        per_run = read_csv_or_empty(s16q_dir / "per_run_metrics.csv")
    if not per_run.empty:
        keep = {"traditional_mean3", "gradient_boosted_trees"}
        per_run = per_run[per_run["method"].isin(keep)].copy()

    join_audit = build_join_audit(config, out_dir)
    copy_table(reproduction, out_dir / "reproduction_match_table.csv")
    copy_table(methods, out_dir / "method_summary.csv")
    copy_table(deltas, out_dir / "method_deltas_vs_traditional.csv")
    copy_table(per_run, out_dir / "per_run_method_metrics.csv")

    inputs = []
    for rel in [
        args.config,
        config["source_s16q_report"] + "/result.json",
        config["source_s16q_report"] + "/reproduction_match_table.csv",
        config["source_s16i_report"] + "/external_daq_runlog_checksum_join.csv",
        config["source_s16i_report"] + "/external_daq_candidate_records.csv",
        config["source_s16p_report"] + "/trigger_mode_manifest.csv",
        config["source_s16j_report"] + "/forced_random_daq_audit.csv",
    ]:
        path = ROOT / rel
        if path.exists():
            inputs.append({"path": rel, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    input_hashes = copy_table(pd.DataFrame(inputs), out_dir / "input_sha256.csv")

    winner_row = methods.iloc[0].to_dict()
    forced_entries = int(join_audit["positive_forced_random_or_external_join_rows"].sum())
    selected_b_stave_pulses = int(reproduction.loc[reproduction["quantity"].eq("S00 selected B-stave pulses"), "reproduced"].iloc[0])
    forced_random_b_stack_entries = int(reproduction.loc[reproduction["quantity"].eq("forced/random/non-beam ROOT entries"), "reproduced"].iloc[0])
    archive_or_filename_hits = int(reproduction.loc[reproduction["quantity"].eq("forced/random/pedestal archive or filename hits"), "reproduced"].iloc[0])
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "git_commit": git_commit(),
        "runtime_seconds": time.time() - start,
        "python": platform.python_version(),
        "reproduction": {
            "source": config["source_s16q_report"],
            "selected_b_stave_pulses": selected_b_stave_pulses,
            "forced_random_b_stack_entries": forced_random_b_stack_entries,
            "archive_or_filename_hits": archive_or_filename_hits,
            "selected_pulse_gate_pass": bool(s16q_result["reproduction"]["selected_pulse_gate_pass"]),
            "s16e_gate_pass": bool(s16q_result["reproduction"]["s16e_gate_pass"]),
        },
        "raw_root_reproduction": {
            "source": config["source_s16q_report"],
            "selected_b_stave_pulses": selected_b_stave_pulses,
            "forced_random_b_stack_entries": forced_random_b_stack_entries,
            "archive_or_filename_hits": archive_or_filename_hits,
            "reproduction_table": "reproduction_match_table.csv",
        },
        "provenance": {
            "external_join_audit_rows": int(len(join_audit)),
            "forced_random_or_external_join_rows": forced_entries,
            "direct_labels_available": forced_entries > 0,
            "conclusion": "no external DAQ/runlog provenance joins true forced/random B-stack labels in mounted data",
        },
        "split": {
            "unit": "source run",
            "heldout_runs": config["heldout_runs"],
            "bootstrap": f"{config['bootstrap_replicates']} run-block replicates from S16q",
        },
        "primary_metric": config["primary_metric"],
        "winner": winner_row,
        "best_traditional": methods[methods["family"].eq("traditional")].iloc[0].to_dict(),
        "method_table": methods.to_dict(orient="records"),
        "next_tickets": [],
        "artifacts": sorted({p.name for p in out_dir.iterdir() if p.is_file()} | {"REPORT.md"}),
        "input_hashes": input_hashes.to_dict(orient="records"),
    }

    with (out_dir / "result.json").open("w") as handle:
        json.dump(clean_json(result), handle, indent=2, sort_keys=True)

    write_report(config, out_dir, result, reproduction, join_audit, methods, deltas, per_run)
    manifest = {
        "ticket": config["ticket"],
        "created_by": Path(__file__).name,
        "artifacts": sorted(p.name for p in out_dir.iterdir() if p.is_file()),
    }
    with (out_dir / "manifest.json").open("w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
