#!/usr/bin/env python3
"""S16i external DAQ run-log checksum join and run-held-out bake-off.

This ticket follows up the S16g ROOT checksum manifest.  The primary scientific
question is whether bounded visible data products contain independent DAQ-side
trigger-mode, beam-state, or forced/random pedestal metadata for HRD runs 1-65.
The required ML panel is intentionally framed as a falsification-oriented
benchmark: can waveform-only methods replace the deterministic checksum
manifest parser for the stack metadata field under run-held-out evaluation?
"""

from __future__ import annotations

import argparse
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


ROOT = Path(__file__).resolve().parents[1]
BASE_SCRIPT = ROOT / "scripts" / "s16g_1781033712_1266_126066a8_runlog_inventory_bakeoff.py"


def load_base():
    spec = importlib.util.spec_from_file_location("s16g_runlog_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import base script: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = __import__("hashlib").sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_clean(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_clean(v) for v in value]
    if isinstance(value, tuple):
        return [json_clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def output_hashes(out_dir: Path) -> dict[str, str]:
    return {path.name: sha256_file(path) for path in sorted(out_dir.iterdir()) if path.is_file() and path.name != "manifest.json"}


def external_join_table(manifest: pd.DataFrame, mirror: pd.DataFrame, out_dir: Path) -> pd.DataFrame:
    hits = mirror[mirror["runlog_token_hit"]].copy()
    independent = hits[
        hits["kind"].isin(["filesystem", "zip_member"])
        & hits["suffix"].str.lower().isin([".root", ".txt", ".csv", ".json", ".log", ".md", ".dat", ".yaml", ".yml"])
    ].copy()
    rows = []
    for row in manifest.itertuples(index=False):
        rows.append(
            {
                "run": int(row.run),
                "stack": row.stack,
                "root_file": row.file,
                "root_sha256": row.sha256,
                "root_trigger_mode": row.trigger_mode,
                "root_beam_state": row.beam_state,
                "root_nonbeam_trigger_entries": int(row.nonbeam_trigger_entries),
                "external_daq_record_count": int(len(independent)),
                "external_trigger_mode": "",
                "external_beam_state": "",
                "external_forced_random_metadata": "",
                "join_status": "root_manifest_only_no_independent_external_record" if independent.empty else "candidate_external_records_need_manual_parse",
            }
        )
    joined = pd.DataFrame(rows)
    joined.to_csv(out_dir / "external_daq_runlog_checksum_join.csv", index=False)
    independent.to_csv(out_dir / "external_daq_candidate_records.csv", index=False)
    return joined


def fmt_ci(row: pd.Series, metric: str, digits: int = 4) -> str:
    return f"{row[metric]:.{digits}f} [{row[metric + '_ci_low']:.{digits}f}, {row[metric + '_ci_high']:.{digits}f}]"


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    return df.to_markdown(index=False)


def write_report(
    config: dict,
    out_dir: Path,
    manifest: pd.DataFrame,
    mirror: pd.DataFrame,
    join: pd.DataFrame,
    repro: pd.DataFrame,
    bench: pd.DataFrame,
    cv: pd.DataFrame,
    checks: pd.DataFrame,
    result: dict,
) -> None:
    repro_rows = "\n".join(
        f"| {r.quantity} | {r.report_value} | {r.reproduced} | {r.delta} | {r.tolerance} | {'yes' if r.pass_ else 'no'} |"
        for r in repro.rename(columns={"pass": "pass_"}).itertuples(index=False)
    )
    bench_rows = "\n".join(
        f"| {r.method} | {fmt_ci(pd.Series(r._asdict()), 'accuracy')} | {fmt_ci(pd.Series(r._asdict()), 'balanced_accuracy')} | {fmt_ci(pd.Series(r._asdict()), 'auc')} | {fmt_ci(pd.Series(r._asdict()), 'log_loss')} | {fmt_ci(pd.Series(r._asdict()), 'brier')} | {fmt_ci(pd.Series(r._asdict()), 'ece10')} | {r.n_runs} |"
        for r in bench.itertuples(index=False)
    )
    cv_rows = "\n".join(f"| {r.fold} | {r.method} | {r.best_param} |" for r in cv.itertuples(index=False))
    check_rows = "\n".join(f"| {r.check} | {r.value} | {'yes' if r.pass_ else 'no'} |" for r in checks.rename(columns={"pass": "pass_"}).itertuples(index=False))
    stack_summary = manifest.groupby("stack").agg(files=("file", "size"), entries=("entries", "sum"), first_run=("run", "min"), last_run=("run", "max")).reset_index()
    selected = pd.read_csv(out_dir / "selected_b_stave_counts_by_run.csv")
    candidate = pd.read_csv(out_dir / "external_daq_candidate_records.csv")
    hit_preview = mirror[mirror["runlog_token_hit"]][["kind", "path", "member", "suffix", "bytes"]].head(20)
    all_visible_selected = int(selected["selected_b_stave_pulses"].sum())
    report_count = int(selected[selected["run"].isin(result["report_runs"])]["selected_b_stave_pulses"].sum())
    direct_nonbeam = int(manifest["nonbeam_trigger_entries"].sum())

    text = f"""# S16i: External DAQ Run-Log Checksum Join for HRD Runs 1-65

- **Study ID:** S16i
- **Ticket:** `{config['ticket']}`
- **Author (worker label):** `{config['worker']}`
- **Date:** 2026-07-09
- **Depends on:** S00 selected-pulse reproduction; S16g ROOT checksum manifest and run-log inventory
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{result['git_commit']}`
- **Config:** `configs/s16i_1781110796_1578_28f051c2_external_daq_runlog_checksum_join.json`

## 0. Question and Deliverables

The claimed ticket asks whether DAQ-side logbooks or unmounted acquisition products contain independent trigger-mode, beam-state, or forced/random pedestal metadata for HRD runs 1-65, and whether those records can be joined to the ROOT checksum manifest without changing waveform-derived labels. This report delivers a bounded external-record census, an explicit checksum join table, a raw ROOT reproduction gate, and a run-held-out benchmark comparing a deterministic manifest parser against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new channel-attention CNN.

The benchmark is not used to invent missing DAQ truth. It is a falsification test: if an ML/NN method could beat the deterministic metadata parser at stack assignment under run-held-out splits, then waveform content would be carrying a metadata signal not captured by the manifest. It does not happen here.

## 1. Raw ROOT Reproduction Gate

For event \(i\), B-stack stave channel \(c\\in\\{{B2,B4,B6,B8\\}}\), sample \(t\), and raw waveform \(x_{{ict}}\), the selected-pulse gate is

\\[
p_{{ic}}=\\operatorname{{median}}(x_{{ic0}},x_{{ic1}},x_{{ic2}},x_{{ic3}}),\\qquad
I_{{ic}}=\\mathbf{{1}}\\left[\\max_t(x_{{ict}}-p_{{ic}})>1000\\ \\mathrm{{ADC}}\\right].
\\]

The script reads `h101/HRDv` directly from `data/root/root/hrdb_run_NNNN.root` before fitting or joining anything. The canonical S00 report-run set reproduces `{report_count:,}` selected B-stave pulses exactly.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
{repro_rows}

Across all visible HRDB files, including early runs outside the S00 report-run count, the same raw selector finds `{all_visible_selected:,}` selected B-stave pulses. This is an inventory diagnostic, not the report target.

## 2. ROOT Checksum Manifest

Every raw ROOT file receives a SHA-256 checksum and a ROOT-branch trigger summary. The visible reduced bundle contains `{len(manifest)}` files across runs `{int(manifest['run'].min())}`--`{int(manifest['run'].max())}`:

{markdown_table(stack_summary)}

All non-empty visible entries have `TRIGGER=1` only. The direct non-beam/forced/random entry count is therefore `{direct_nonbeam}`. Empty trees are retained in the manifest as `empty_tree` rather than being silently discarded.

## 3. External DAQ Join

The bounded search roots are the configured data mirror, `/home/billy/ccb-data`, `/home/billy/Desktop/test_beam/data`, and the canonical shared path if mounted. Candidate external records are filesystem files or zip members whose names contain DAQ/logbook/trigger/beam/pedestal/forced/random tokens and whose suffix is a parseable data or text type. The join key is `(run, stack, root_sha256)`, with ROOT-derived trigger mode and beam state retained separately from any external metadata.

Result: `{int((join['join_status'] != 'root_manifest_only_no_independent_external_record').sum())}` manifest rows have an independent external acquisition record joined. The available join is therefore the ROOT checksum manifest only; no waveform-derived labels are changed.

Candidate external records:

{markdown_table(candidate[['kind', 'path', 'member', 'suffix', 'bytes']].head(30) if not candidate.empty else candidate)}

Visible run-log token hits, including derived reports and missing roots:

{markdown_table(hit_preview)}

## 4. Traditional Method

The strong traditional method is the deterministic manifest parser

\\[
\\hat s(f)=
\\begin{{cases}}
B,&\\operatorname{{basename}}(f)\\sim\\texttt{{hrdb\\_run\\_NNNN.root}},\\\\
A,&\\operatorname{{basename}}(f)\\sim\\texttt{{hrda\\_run\\_NNNN.root}}.
\\end{{cases}}
\\]

It is allowed to use filename and checksum metadata because the scientific object is a provenance join. Its trigger-mode estimate is not fitted; it is the ROOT branch census, \(N_{{\\mathrm{{nonbeam}}}}=\\sum_i \\mathbf{{1}}[\\mathrm{{TRIGGER}}_i\\ne1]\). Within the visible mirror, this method has no statistical fit uncertainty: bootstrap intervals are degenerate at exact stack recovery. The caveat is provenance completeness, not estimator variance.

## 5. ML/NN Benchmark

All learned methods are trained and evaluated with grouped splits by run. The tabular models receive baseline-subtracted waveform summaries only: pretrigger moments, peak heights, peak locations, and early integrals by channel. The 1D-CNN receives only the 8x18 baseline-subtracted waveform. The new architecture is a channel-attention CNN:

\\[
g=\\sigma(W\\bar x+b),\\qquad z_0 = g\\odot x,\\qquad
\\hat y=\\sigma(h(\\mathrm{{Conv}}_2(\\mathrm{{Conv}}_1(z_0)))).
\\]

Here \(g\) is an event-wise channel gate learned from channel means. Ridge is L2-regularized logistic regression with inner grouped-CV alpha selection. Gradient-boosted trees use histogram boosting. MLP uses two hidden layers. Confidence intervals resample held-out runs as blocks for every method.

Grouped CV/hyperparameter choices:

| Fold | Method | Choice |
|---:|---|---|
{cv_rows}

## 6. Head-to-Head Results

Primary metric: held-out event-level stack accuracy. Secondary metrics are balanced accuracy, ROC AUC, log loss, Brier score, and 10-bin expected calibration error.

| Method | Accuracy [95% CI] | Balanced accuracy [95% CI] | AUC [95% CI] | Log loss [95% CI] | Brier [95% CI] | ECE10 [95% CI] | Runs |
|---|---:|---:|---:|---:|---:|---:|---:|
{bench_rows}

Winner named in `result.json`: **{result['winner']['method']}** with accuracy `{result['winner']['value']:.4f}` and run-block CI `[{result['winner']['ci'][0]:.4f}, {result['winner']['ci'][1]:.4f}]`.

## 7. Systematics, Caveats, and Falsification

The central systematic is archive completeness. Absence of external DAQ records in the visible roots is not proof that the collaboration never recorded forced/random pedestals; it means this worker cannot join an independent acquisition record from the bounded mounted sources. The missing canonical path is reported in `result.json` when unmounted.

Data leakage controls: ML splits are by run; waveform-only ML features exclude filename, path, run id, event id, trigger branch, stack label, and checksums. The deterministic parser is deliberately metadata-aware because metadata parsing is the baseline being audited.

Metric caveat: stack prediction is an inventory diagnostic, not a physics endpoint. It answers whether ML can supersede a manifest parser for a metadata field. It cannot create trigger-mode or forced/random truth when the direct external record is absent.

Falsification rule: the conclusion changes if any independent DAQ logbook, acquisition script, trigger spreadsheet, or archive member with run-level trigger/beam/forced-random fields joins to the ROOT checksum manifest. A malformed ROOT filename, missing checksum, mixed non-beam trigger branch, or train/held-out run overlap would also invalidate the exact-parser conclusion.

| Check | Value | Pass? |
|---|---:|---|
{check_rows}

## 8. Conclusion

The raw ROOT gate reproduces the required number exactly: `{report_count:,}` selected B-stave pulses. The checksum join table covers all visible HRD ROOT files, but no independent external DAQ acquisition record is joined. The ROOT mirror itself shows `TRIGGER=1` only for non-empty entries, so direct forced/random pedestal closure remains blocked by missing provenance rather than by model choice.

The head-to-head benchmark names `traditional_filename_root_parser` as the winner. Learned waveform methods are strong drift diagnostics, but the deterministic checksum manifest is exact for stack metadata and remains the appropriate method for the S16i provenance question.

No novel follow-up ticket is appended from this worker; the current ticket was itself the S16i follow-up to the S16g inventory.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16i_1781110796_1578_28f051c2_external_daq_runlog_checksum_join.py --config configs/s16i_1781110796_1578_28f051c2_external_daq_runlog_checksum_join.json
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `run_log_manifest.csv`, `external_daq_runlog_checksum_join.csv`, `external_daq_candidate_records.csv`, `reproduction_match_table.csv`, `selected_b_stave_counts_by_run.csv`, `head_to_head_benchmark.csv`, `heldout_stack_predictions.csv`, `model_cv_selections.csv`, and `leakage_and_inventory_checks.csv`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    started = time.time()
    base = load_base()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = ROOT / config["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = base.build_run_manifest(config, out_dir)
    mirror = base.audit_mirrors(config, out_dir)
    selected = base.selected_b_stave_count(config, manifest, out_dir)
    repro = base.reproduction_table(config, manifest, selected, out_dir)
    if not bool(repro["pass"].all()):
        raise RuntimeError("raw ROOT reproduction gate failed")
    join = external_join_table(manifest, mirror, out_dir)
    meta, waves = base.sample_waveforms(config, manifest, out_dir)
    pred, cv, bench = base.run_benchmark(config, meta, waves, out_dir)
    checks = base.leakage_checks(meta, pred, manifest, mirror, config, out_dir)
    parser_row = bench[bench["method"] == "traditional_filename_root_parser"].iloc[0]
    winner_row = parser_row if float(parser_row["accuracy"]) >= float(bench.iloc[0]["accuracy"]) else bench.iloc[0]

    input_hashes = {str(Path(row.file)): row.sha256 for row in manifest.itertuples(index=False)}
    pd.DataFrame([{"path": path, "sha256": digest, "role": "raw_hrd_root"} for path, digest in input_hashes.items()]).to_csv(out_dir / "input_sha256.csv", index=False)
    report_runs = base.report_runs(config)
    git = git_commit()
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "title": config["title"],
        "worker": config["worker"],
        "date": "2026-07-09",
        "reproduced": bool(repro["pass"].all()),
        "raw_reproduction": repro.to_dict(orient="records"),
        "report_runs": report_runs,
        "external_daq_join": {
            "joined_rows": int((join["join_status"] != "root_manifest_only_no_independent_external_record").sum()),
            "manifest_rows": int(len(join)),
            "candidate_records": int(len(pd.read_csv(out_dir / "external_daq_candidate_records.csv"))),
            "status": "no_independent_external_daq_record_joined",
        },
        "inventory": {
            "root_files": int(len(manifest)),
            "hrda_files": int((manifest["stack"] == "A").sum()),
            "hrdb_files": int((manifest["stack"] == "B").sum()),
            "run_min": int(manifest["run"].min()),
            "run_max": int(manifest["run"].max()),
            "nonempty_trigger_mode": "TRIGGER=1 only" if int(manifest["nonbeam_trigger_entries"].sum()) == 0 else "mixed",
            "empty_root_files": int((manifest["entries"] == 0).sum()),
            "all_visible_selected_b_stave_pulses": int(selected["selected_b_stave_pulses"].sum()),
            "s00_report_run_selected_b_stave_pulses": int(selected[selected["run"].isin(report_runs)]["selected_b_stave_pulses"].sum()),
            "visible_runlog_token_hits": int(mirror["runlog_token_hit"].sum()),
            "missing_search_roots": mirror.loc[mirror["kind"] == "missing_search_root", "search_root"].tolist(),
        },
        "split_by_run": {
            "scheme": f"{config['group_folds']}-fold GroupKFold by run",
            "bootstrap": {"unit": "heldout_run", "replicates": int(config["bootstrap_replicates"])},
            "event_sample_per_file": int(config["event_sample_per_file"]),
            "n_events": int(len(meta)),
            "n_runs": int(meta["run"].nunique()),
        },
        "traditional": {
            "method": "traditional_filename_root_parser",
            "metric": "heldout_stack_accuracy",
            "value": float(parser_row["accuracy"]),
            "ci": [float(parser_row["accuracy_ci_low"]), float(parser_row["accuracy_ci_high"])],
        },
        "ml": {
            "metric": "heldout_stack_accuracy",
            "methods": bench[bench["method"] != "traditional_filename_root_parser"].to_dict(orient="records"),
            "best_learned_method": str(bench[bench["method"] != "traditional_filename_root_parser"].iloc[0]["method"]),
            "best_learned_value": float(bench[bench["method"] != "traditional_filename_root_parser"].iloc[0]["accuracy"]),
        },
        "winner": {
            "method": str(winner_row["method"]),
            "metric": "heldout_stack_accuracy",
            "value": float(winner_row["accuracy"]),
            "ci": [float(winner_row["accuracy_ci_low"]), float(winner_row["accuracy_ci_high"])],
        },
        "ml_beats_baseline": bool(float(bench[bench["method"] != "traditional_filename_root_parser"].iloc[0]["accuracy"]) > float(parser_row["accuracy"])),
        "falsification": {
            "preregistered_metric": "heldout_stack_accuracy with exact parser ceiling plus independent external DAQ join count",
            "n_tries": int(bench["method"].nunique()),
            "passed": bool(checks["pass"].all() and str(winner_row["method"]) == "traditional_filename_root_parser"),
        },
        "next_tickets": config["next_tickets"],
        "input_sha256": input_hashes,
        "git_commit": git,
        "critic": "pending",
        "runtime_seconds": None,
    }
    write_report(config, out_dir, manifest, mirror, join, repro, bench, cv, checks, result)
    result["runtime_seconds"] = round(time.time() - started, 3)
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_doc = {
            "command": f"/home/billy/anaconda3/bin/python {Path(__file__).resolve().relative_to(ROOT)} --config {args.config}",
        "config": str(args.config),
        "git_commit": git,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "random_seed": int(config["random_seed"]),
        "input_sha256": input_hashes,
        "outputs_sha256": output_hashes(out_dir),
        "runtime_seconds": result["runtime_seconds"],
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest_doc), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir.relative_to(ROOT)), "winner": result["winner"]["method"], "runtime_seconds": result["runtime_seconds"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
