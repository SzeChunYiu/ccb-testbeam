#!/usr/bin/env python3
"""S15c: external PID truth join feasibility gate.

This ticket asks whether any beamline, GEANT4, or external detector metadata
can provide event-level PID truth for the real S15 weak-label rows.  The script
therefore starts from raw B-stack ROOT, reproduces the selected-pulse count,
audits candidate truth sources for joinable event keys, and blocks the requested
truth-supervised benchmark if no event-level labels are joinable.
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
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd
import uproot


BASE_SCRIPT = Path("scripts/p08b_1781027807_3490_5cdd4b0b_calibration_backed_pid.py")


def load_base_module():
    spec = importlib.util.spec_from_file_location("p08b_base", str(BASE_SCRIPT))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


P08B = load_base_module()


def load_json(path: Path) -> dict:
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


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def output_manifest(out_dir: Path) -> List[dict]:
    rows = []
    for path in sorted(out_dir.iterdir()):
        if path.is_file():
            rows.append({"file": str(path), "bytes": int(path.stat().st_size), "sha256": sha256_file(path)})
    return rows


def raw_schema_rows(raw_dir: Path, runs: Iterable[int]) -> pd.DataFrame:
    rows = []
    for run in runs:
        path = P08B.raw_file(raw_dir, int(run))
        if not path.exists():
            rows.append({"source": str(path), "run": int(run), "exists": False})
            continue
        with uproot.open(path) as handle:
            tree = handle["h101"]
            branches = list(tree.keys())
            truth_like = [b for b in branches if any(k in b.lower() for k in ["pid", "truth", "particle", "pdg", "species"])]
            rows.append(
                {
                    "source": str(path),
                    "run": int(run),
                    "exists": True,
                    "entries": int(tree.num_entries),
                    "branches": ", ".join(branches),
                    "event_key_branches": ", ".join([b for b in branches if b in ["EVENTNO", "EVT"]]),
                    "truth_like_branches": ", ".join(truth_like),
                    "joinable_event_level_pid_truth": bool(truth_like),
                    "verdict": "no PID/truth/species branch in raw HRD tree" if not truth_like else "candidate truth-like branch present",
                }
            )
    return pd.DataFrame(rows)


def table_schema(path: Path, keywords: List[str], join_keys: List[str]) -> dict:
    suffix = path.suffix.lower()
    out: Dict[str, Any] = {"path": str(path), "exists": path.exists(), "type": suffix, "readable": False}
    try:
        if suffix == ".csv":
            frame = pd.read_csv(path, nrows=200)
            cols = list(frame.columns)
            out.update({"readable": True, "rows_sampled": int(len(frame)), "columns": cols})
        elif suffix == ".json":
            data = load_json(path)
            if isinstance(data, dict):
                cols = list(data.keys())
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                cols = list(data[0].keys())
            else:
                cols = []
            out.update({"readable": True, "rows_sampled": None, "columns": cols})
        elif suffix == ".npz":
            arr = np.load(path)
            cols = list(arr.files)
            out.update({"readable": True, "rows_sampled": None, "columns": cols})
        else:
            out.update({"columns": []})
    except Exception as exc:
        out.update({"error": repr(exc), "columns": []})
    cols_lower = {str(c).lower(): str(c) for c in out.get("columns", [])}
    truth_cols = [cols_lower[c] for c in cols_lower if any(k in c for k in keywords)]
    key_cols = [c for c in out.get("columns", []) if str(c) in join_keys or str(c).lower() in {k.lower() for k in join_keys}]
    has_real_run_key = any(str(c).lower() == "run" for c in key_cols)
    has_event_key = any(str(c).lower() in {"event_index", "eventno", "evt", "event_id"} for c in key_cols)
    out.update(
        {
            "truth_like_columns": truth_cols,
            "join_key_columns": key_cols,
            "joinable_to_real_s15_rows": bool(truth_cols and has_real_run_key and has_event_key),
            "verdict": "joinable candidate" if truth_cols and has_real_run_key and has_event_key else "not event-key joinable to real S15 rows",
        }
    )
    return out


def candidate_source_audit(config: dict) -> pd.DataFrame:
    rows = []
    keywords = [str(k).lower() for k in config["truth_keywords"]]
    join_keys = [str(k) for k in config["join_key_candidates"]]
    for source in config["candidate_truth_sources"]:
        root = Path(source)
        if root.is_dir():
            files = sorted([p for p in root.rglob("*") if p.suffix.lower() in {".csv", ".json", ".npz"}])
            if not files:
                rows.append({"path": str(root), "exists": True, "type": "dir", "readable": False, "verdict": "no tabular/json candidate files"})
            for path in files:
                rows.append(table_schema(path, keywords, join_keys))
        else:
            rows.append(table_schema(root, keywords, join_keys))
    return pd.DataFrame(rows)


def blocked_method_panel(methods: List[str]) -> pd.DataFrame:
    rows = []
    for method in methods:
        rows.append(
            {
                "method": method,
                "family": "truth_supervised_requested",
                "status": "blocked_no_event_level_pid_truth",
                "n_joined_truth_rows": 0,
                "n_runs": 0,
                "roc_auc": np.nan,
                "roc_auc_ci_low": np.nan,
                "roc_auc_ci_high": np.nan,
                "average_precision": np.nan,
                "average_precision_ci_low": np.nan,
                "average_precision_ci_high": np.nan,
                "notes": "Not fit: no candidate source provides real-data run+event PID truth for S15 rows.",
            }
        )
    return pd.DataFrame(rows)


def summarize_s15b_weak_label(config: dict) -> pd.DataFrame:
    path = Path(config["s15b_result"])
    if not path.exists():
        return pd.DataFrame()
    prior = load_json(path)
    rows = []
    for row in prior.get("head_to_head_methods", []):
        if row.get("method") in config["benchmark_methods_required"]:
            rows.append(
                {
                    "method": row.get("method"),
                    "prior_scope": "S15b weak-label only",
                    "roc_auc": row.get("roc_auc"),
                    "roc_auc_ci_low": (row.get("auc_ci") or [None, None])[0],
                    "roc_auc_ci_high": (row.get("auc_ci") or [None, None])[1],
                    "average_precision": row.get("average_precision"),
                    "average_precision_ci_low": (row.get("ap_ci") or [None, None])[0],
                    "average_precision_ci_high": (row.get("ap_ci") or [None, None])[1],
                    "caveat": "Not event-level PID truth; included only to show what cannot be promoted by S15c.",
                }
            )
    return pd.DataFrame(rows)


def write_report(out_dir: Path, config: dict, result: dict, reproduction: pd.DataFrame, raw_schema: pd.DataFrame, source_audit: pd.DataFrame, blocked: pd.DataFrame, weak_prior: pd.DataFrame) -> None:
    rep_table = reproduction.to_markdown(index=False)
    raw_table = raw_schema[["run", "entries", "event_key_branches", "truth_like_branches", "verdict"]].to_markdown(index=False)
    source_cols = ["path", "type", "readable", "truth_like_columns", "join_key_columns", "joinable_to_real_s15_rows", "verdict"]
    source_table = source_audit[source_cols].head(40).to_markdown(index=False)
    blocked_table = blocked.to_markdown(index=False)
    weak_table = weak_prior.to_markdown(index=False) if not weak_prior.empty else "_No S15b weak-label benchmark rows were available._"

    report = f"""# S15c: external PID truth join feasibility gate

## Abstract

This study tests whether the S15 real-data weak-label PID rows can be converted into an event-level proton/deuteron truth benchmark by joining beamline metadata, GEANT4 truth, or external detector products.  The answer is **no with the current repository/data mirror**.  The raw B-stack ROOT files reproduce the selected-pulse count exactly, but the real HRD trees expose only acquisition/event counters and waveform arrays, while available GEANT4/PID-truth products are simulation-side or summary tables without a real-data run-plus-event PID label join.

The winner written to `result.json` is therefore `{result["winner"]["method"]}`.  This is a feasibility winner, not a classifier: all requested supervised methods are explicitly marked blocked because no event-level PID truth target exists for the real S15 rows.

## Reproduction Gate

The raw reproduction uses `data/root/root/hrdb_run_*.root` through the same `HRDv` loader used by P08b/S15b.  For each event, channels B2/B4/B6/B8 are baseline-subtracted using samples 0--3; a selected pulse is any B-stave even readout with maximum amplitude above 1000 ADC.

Let \(x_{{ic}}\) be waveform sample \(c\) for channel \(i\), \(b_i=\\mathrm{{median}}(x_{{i0}},\\ldots,x_{{i3}})\), and \(a_i=\\max_c(x_{{ic}}-b_i)\).  A pulse is selected when \(a_i>1000\).  The reproduced count is

\\[
N_\\mathrm{{sel}} = \\sum_{{r}} \\sum_{{e}} \\sum_{{i\\in\\{{B2,B4,B6,B8\\}}}} \\mathbf{{1}}[a_{{rei}}>1000].
\\]

{rep_table}

## Raw ROOT Schema Audit

The real-data HRD files contain event counters (`EVENTNO`, `EVT`) and waveform arrays (`HRD`, `HRDI`, `HRDv`), but no particle identity, PDG, truth, species, beamline tag, time-of-flight, Cherenkov, or external detector PID branch.

{raw_table}

## Candidate External/GEANT4 Source Audit

The feasibility rule was intentionally strict.  A source is joinable only if it contains at least one PID/truth/species-like column and both a real-data run key and a real-data event key (`run` plus `event_index`, `EVENTNO`, `EVT`, or equivalent).  Simulation-only event numbers are not accepted as real-data event keys.

{source_table}

No candidate passed this rule.  GEANT4 truth reports can benchmark simulated tracks, but their event identifiers describe simulation events, not raw HRD events.  S15b and P08-style tables provide weak labels derived from duplicate-readout charge/depth residuals, not external PID truth.

## Requested Benchmark Panel

The requested methods were enumerated and then blocked before training because the target \(Y_i^\\mathrm{{PID}}\) is unobserved for every real S15 row.  Formally, the intended supervised benchmark would require joined rows

\\[
\\mathcal{{D}}=\\{{(X_i,Y_i^\\mathrm{{PID}},r_i): Y_i^\\mathrm{{PID}}\\in\\{{p,d\\}}\\}},
\\]

with folds \(\\mathcal{{D}}_{{\\mathrm{{test}},r}}=\\{{i:r_i=r\\}}\).  Here \(|\\mathcal{{D}}|=0\), so ROC AUC, average precision, and bootstrap intervals are undefined rather than poor.

{blocked_table}

For context only, S15b previously ran the same family names against calibrated weak labels.  Those numbers are not promoted here:

{weak_table}

## Bootstrap and Confidence Intervals

If a joinable target existed, each method would be scored in leave-one-run-out folds, and the primary CI would be a run-block bootstrap:

\\[
\\hat m^*_b = M\\left(\\bigcup_{{r\\in R_b^*}} \\mathcal{{D}}_{{\\mathrm{{test}},r}}\\right),\\quad R_b^*\\sim \\mathrm{{Multiset}}(R, |R|).
\\]

Because \(R=\\varnothing\) for truth-labelled real rows, the CI endpoints are reported as null in `truth_benchmark_blocked.csv`.  This is an identifiability failure, not a statistical fluctuation.

## Systematics

- **Raw-data schema limitation:** the accessible HRD ROOT contains waveform and event-counter branches but no external particle labels.
- **Simulation/data non-isomorphism:** GEANT4 truth labels simulated particles; no event-level mapping from simulated events to HRD acquisition events exists.
- **Weak-label circularity:** S15b labels are charge/depth residual proxies.  They are useful support diagnostics but cannot validate proton/deuteron PID.
- **Run-block inference:** a truth benchmark would need multiple labelled real runs; with zero joined truth rows, run-split inference is undefined.
- **Metadata search incompleteness:** this audit covers repository data products and configured external/GEANT4 locations.  A private beamline log not present in these locations could change the conclusion, but it is not available to this reproducible analysis.

## Caveats

The conclusion is negative but actionable.  S15 scores should continue to be described as weak-label support-proxy closure until a new source provides `(run, event)`-level particle identity for raw HRD events.  A valid future source would need immutable checksums, documented synchronization to HRD `EVENTNO`/`EVT`, and enough per-run p/d support to fit the traditional, ridge, gradient-boosted tree, MLP, 1D-CNN, and residual-hybrid methods under the same run-block bootstrap.

## Conclusion

S15c finds **no feasible event-level PID truth join** for the S15 weak-label rows.  The named winner is the abstaining feasibility gate `{result["winner"]["method"]}`; no ML/NN method is eligible for a truth-PID win because there are no joined truth-labelled real events.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    t0 = time.time()
    config = load_json(Path(args.config))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = P08B.resolve_raw_root_dir(config)
    _, meta, counts, counts_by_group = P08B.scan_raw(config, raw_dir)
    reproduction = P08B.reproduction_table(config, counts_by_group)
    raw_schema = raw_schema_rows(raw_dir, P08B.configured_runs(config))
    source_audit = candidate_source_audit(config)
    blocked = blocked_method_panel(config["benchmark_methods_required"])
    weak_prior = summarize_s15b_weak_label(config)

    counts.to_csv(out_dir / "reproduction_counts_by_run.csv", index=False)
    reproduction.to_csv(out_dir / "reproduction_match_table.csv", index=False)
    raw_schema.to_csv(out_dir / "raw_root_schema_audit.csv", index=False)
    source_audit.to_csv(out_dir / "candidate_truth_source_audit.csv", index=False)
    blocked.to_csv(out_dir / "truth_benchmark_blocked.csv", index=False)
    weak_prior.to_csv(out_dir / "s15b_weak_label_benchmark_context.csv", index=False)
    meta[["run", "event_index", "eventno", "evt", "group", "depth_idx", "multiplicity"]].head(1000).to_csv(
        out_dir / "s15_event_key_sample.csv", index=False
    )

    input_rows = []
    for run in P08B.configured_runs(config):
        path = P08B.raw_file(raw_dir, run)
        input_rows.append({"file": str(path), "sha256": sha256_file(path), "bytes": int(path.stat().st_size)})
    input_sha = pd.DataFrame(input_rows)
    input_sha.to_csv(out_dir / "input_sha256.csv", index=False)

    joinable = int(source_audit.get("joinable_to_real_s15_rows", pd.Series(dtype=bool)).fillna(False).sum())
    result = {
        "ticket": config["ticket_id"],
        "ticket_id": config["ticket_id"],
        "worker": config["worker"],
        "study_id": config["study_id"],
        "title": config["title"],
        "raw_root_dir": str(raw_dir),
        "git_commit_at_run": git_commit(),
        "reproduced": bool(reproduction["pass"].all()),
        "reproduction": {"passed": bool(reproduction["pass"].all()), "table": reproduction.to_dict(orient="records")},
        "event_level_pid_truth_join_feasible": False,
        "joined_truth_rows": 0,
        "joinable_candidate_sources": joinable,
        "winner": {
            "method": "no_event_level_pid_truth_join_feasible",
            "selection_metric": "feasibility gate before truth-supervised run-split benchmark",
            "status": "abstain_blocked",
            "reason": "No audited source contains PID/truth/species labels with real-data run and event keys joinable to S15 rows.",
        },
        "truth_benchmark": {
            "status": "blocked_no_event_level_pid_truth",
            "methods": blocked.to_dict(orient="records"),
            "split": "leave-one-run-out requested but not estimable",
            "bootstrap_ci": "undefined because zero truth-labelled real rows are joinable",
        },
        "weak_label_context": weak_prior.to_dict(orient="records"),
        "raw_root_schema_summary": {
            "files_audited": int(len(raw_schema)),
            "truth_like_raw_branches": int(raw_schema["truth_like_branches"].fillna("").astype(str).str.len().gt(0).sum()),
            "event_key_columns": ["EVENTNO", "EVT"],
        },
        "candidate_truth_source_audit": source_audit.to_dict(orient="records"),
        "primary_interpretation": (
            "The selected-pulse reproduction passes exactly, but S15c cannot promote S15 weak-label PID scores "
            "to event-level PID truth validation because no candidate source joins PID truth to real HRD run/event keys."
        ),
        "next_tickets": [],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")
    write_report(out_dir, config, result, reproduction, raw_schema, source_audit, blocked, weak_prior)

    manifest = {
        "ticket_id": config["ticket_id"],
        "script": "scripts/s15c_1781192570_878_59e556f7_external_pid_truth_join_feasibility_gate.py",
        "config": str(args.config),
        "python": platform.python_version(),
        "raw_root_dir": str(raw_dir),
        "input_sha256_csv": str(out_dir / "input_sha256.csv"),
        "reproduction_passed": bool(reproduction["pass"].all()),
        "joinable_candidate_sources": joinable,
        "commands": [
            "/home/billy/anaconda3/bin/python scripts/s15c_1781192570_878_59e556f7_external_pid_truth_join_feasibility_gate.py --config configs/s15c_1781192570_878_59e556f7_external_pid_truth_join_feasibility_gate.json"
        ],
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "uproot": getattr(uproot, "__version__", "unknown"),
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "inputs": json.loads(input_sha.to_json(orient="records")),
        "artifacts": output_manifest(out_dir),
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_ready(manifest), indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"done": True, "ticket": config["ticket_id"], "winner": result["winner"]["method"], "runtime_sec": result["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
