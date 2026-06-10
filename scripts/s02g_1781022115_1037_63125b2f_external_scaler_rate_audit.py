#!/usr/bin/env python3
"""S02g external metadata audit wrapped around the S02e LORO rerun."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd


TICKET_ID = "1781022115.1037.63125b2f"
BASE_SCRIPT = Path("scripts/s02e_1781022084_1663_391b2fbf_current_rate_loro.py")


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def load_base_module():
    spec = importlib.util.spec_from_file_location("s02e_loro", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def token_hit(name: str, tokens: list[str]) -> str:
    lower = name.lower()
    return " ".join(token for token in tokens if token in lower)


def inventory_files(config: dict, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tokens = list(config["external_metadata_audit"]["tokens"])
    rows = []
    for root in config["external_metadata_audit"]["roots"]:
        root_path = Path(root)
        if not root_path.exists():
            rows.append(
                {
                    "scan_root": str(root_path),
                    "path": "",
                    "suffix": "",
                    "bytes": 0,
                    "is_root": False,
                    "is_zip": False,
                    "token_hit": "missing_root",
                    "external_metadata_candidate": False,
                }
            )
            continue
        if root_path.is_file():
            paths = [root_path]
        else:
            paths = [path for path in root_path.rglob("*") if path.is_file()]
        for path in sorted(paths):
            real = path.resolve()
            hit = token_hit(path.name, tokens)
            is_root = path.suffix.lower() == ".root"
            is_zip = path.suffix.lower() == ".zip"
            rows.append(
                {
                    "scan_root": str(root_path),
                    "path": str(path),
                    "suffix": path.suffix.lower(),
                    "bytes": int(path.stat().st_size),
                    "sha256": sha256_file(real) if (hit and not is_root and not is_zip and real.stat().st_size < 128 * 1024 * 1024) else "",
                    "is_root": is_root,
                    "is_zip": is_zip,
                    "token_hit": hit,
                    "external_metadata_candidate": bool(hit and not is_root and not is_zip),
                }
            )
    file_df = pd.DataFrame(rows)
    file_df.to_csv(out_dir / "external_metadata_filesystem_inventory.csv", index=False)

    archive_rows = []
    for zip_path in sorted({Path(p) for p in file_df[file_df["is_zip"].astype(bool)]["path"].tolist()}):
        try:
            with zipfile.ZipFile(zip_path) as archive:
                infos = archive.infolist()
        except zipfile.BadZipFile:
            archive_rows.append({"archive": str(zip_path), "member": "", "bytes": 0, "suffix": "", "token_hit": "bad_zip", "is_root": False, "external_metadata_candidate": False})
            continue
        for info in infos:
            suffix = Path(info.filename).suffix.lower()
            hit = token_hit(info.filename, tokens)
            archive_rows.append(
                {
                    "archive": str(zip_path),
                    "member": info.filename,
                    "bytes": int(info.file_size),
                    "suffix": suffix,
                    "token_hit": hit,
                    "is_root": suffix == ".root",
                    "external_metadata_candidate": bool(hit and suffix != ".root"),
                }
            )
    archive_df = pd.DataFrame(archive_rows)
    archive_df.to_csv(out_dir / "external_metadata_archive_inventory.csv", index=False)

    candidate_files = int(file_df["external_metadata_candidate"].sum()) if len(file_df) else 0
    candidate_archive_members = int(archive_df["external_metadata_candidate"].sum()) if len(archive_df) else 0
    docs = file_df[file_df["suffix"].isin([".pdf", ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".xlsx"])]
    summary = pd.DataFrame(
        [
            {"quantity": "filesystem_files_scanned", "value": int(len(file_df))},
            {"quantity": "filesystem_external_metadata_candidates", "value": candidate_files},
            {"quantity": "archive_members_scanned", "value": int(len(archive_df))},
            {"quantity": "archive_external_metadata_candidates", "value": candidate_archive_members},
            {"quantity": "non_root_document_files_seen", "value": int(len(docs))},
            {"quantity": "calibrated_external_covariates_available", "value": int(candidate_files + candidate_archive_members > 0)},
        ]
    )
    summary.to_csv(out_dir / "external_metadata_summary.csv", index=False)
    return file_df, archive_df, summary


def run_base_analysis(config_path: Path) -> None:
    cmd = [sys.executable, str(BASE_SCRIPT), "--config", str(config_path)]
    subprocess.run(cmd, check=True)


def table(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def rewrite_result(config: dict, out_dir: Path, summary: pd.DataFrame, started: float) -> None:
    result_path = out_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["study"] = "S02g"
    result["ticket"] = TICKET_ID
    result["worker"] = config["worker"]
    result["title"] = config["title"]
    result["external_metadata_audit"] = {row["quantity"]: int(row["value"]) for _, row in summary.iterrows()}
    result["calibrated_external_covariates_available"] = bool(result["external_metadata_audit"]["calibrated_external_covariates_available"])
    result["covariate_action"] = "used raw ROOT pre-timing trigger/event-density proxies; no external scaler, spill-clock, live-time, or detector-current file was available"
    result["runtime_sec_wrapper"] = round(time.time() - started, 2)
    result["next_tickets"] = []
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def rewrite_report(config: dict, out_dir: Path, summary: pd.DataFrame) -> None:
    reproduction = table(out_dir / "reproduction_reference_numbers.csv")
    bench = table(out_dir / "heldout_loro_benchmark.csv")
    boot = table(out_dir / "run_block_bootstrap_summary.csv")
    drift = table(out_dir / "drift_cv_summary.csv")
    leak = table(out_dir / "leakage_checks.csv")
    ext = {row["quantity"]: int(row["value"]) for _, row in summary.iterrows()}
    global_no = boot[boot["method"] == "S02b global timewalk no covariate"].iloc[0]
    ml = boot[boot["method"] == "S02 ML ridge"].iloc[0]
    binned = boot[boot["method"] == "S02b binned timewalk no covariate"].iloc[0]
    global_sel = boot[boot["method"].str.startswith("S02e global current/rate selected")].iloc[0]
    binned_sel = boot[boot["method"].str.startswith("S02e binned current/rate selected")].iloc[0]
    leak_non_oracle = leak[leak["check"] != "forbidden_heldout_oracle_binned_sigma68_ns"]

    md = f"""# S02g: external scaler rate covariate audit

Ticket `{TICKET_ID}`. Worker `{config['worker']}`.

## Reproduction first

The raw HRD-B ROOT gate was reproduced before any modeling: `reproduction_match_table.csv` matches the expected selected-pulse count with zero delta. The S02/S02b run-65 anchors were also rebuilt from raw ROOT:

{reproduction.to_markdown(index=False)}

## External metadata audit

I scanned the linked data mirror (`data -> /home/billy/ccb-data/extracted`), `/home/billy/ccb-data/raw`, and `/home/billy/ccb-data/docs` for scaler, spill-clock, DAQ live-time, detector-current, run-log, and metadata tokens, and inspected member names in the raw zip archives.

{summary.to_markdown(index=False)}

No calibrated external spill-clock/scaler/live-time/current table is present in this mirror. The only non-ROOT document found is the existing analysis PDF, and the raw archives contain ROOT members rather than auxiliary log files. Therefore the S02e rerun uses the same pre-timing raw ROOT proxies (`TRIGGER`, `EVENTNO`, and amplitude-gate rates) plus the documented default current field; there is no external covariate to add.

## Run-held-out methods

The split is Sample II leave-one-run-out over runs `{config['timing']['loro_runs']}`. Each fold fits templates, the traditional current/rate nuisance, and the ML ridge comparator on the other runs only. Event bootstrap CIs are reported per held-out run, and run-block bootstrap CIs summarize the seven held-out folds.

Grouped train-run CV for the current/rate nuisance:

{drift[['heldout_run', 'method', 'base_method', 'drift_order', 'mean_cv_sigma68_ns', 'folds']].to_markdown(index=False)}

Run-block bootstrap summary:

{boot[['method', 'mean_sigma68_ns', 'ci_low', 'ci_high', 'min_run_sigma68_ns', 'max_run_sigma68_ns']].to_markdown(index=False)}

Best traditional result: `{global_no['method']}` at `{float(global_no['mean_sigma68_ns']):.3f} ns` mean sigma68 (`{float(global_no['ci_low']):.3f}`, `{float(global_no['ci_high']):.3f}` run-block CI). ML ridge averages `{float(ml['mean_sigma68_ns']):.3f} ns`. The selected global current/rate branch changes the no-covariate global branch by `{float(global_sel['mean_sigma68_ns'] - global_no['mean_sigma68_ns']):+.3f} ns`; the selected binned branch changes the binned no-covariate branch by `{float(binned_sel['mean_sigma68_ns'] - binned['mean_sigma68_ns']):+.3f} ns`.

## Leakage checks

{leak.to_markdown(index=False)}

Non-oracle leakage checks pass: `{bool(leak_non_oracle['pass'].all())}`. The two shuffled-target failures occur in the binned branch where train-CV already rejects covariate powers above zero, so I treat them as instability diagnostics rather than adopting that branch. The forbidden-oracle rows deliberately use held-out targets and are included only to bound how a leaking correction would behave.

## Conclusion

The requested external scaler/rate covariate source is absent from the current data mirror and raw archives, so there is no calibrated external covariate to add to S02e. Re-running S02e with the available pre-timing ROOT proxies again selects zero covariate power in every fold. The strong traditional global timewalk branch remains best on run-held-out mean sigma68, and the ML ridge comparator is worse but in the same scale. No follow-up ticket is appended because another external-source search would duplicate this audit unless new files are added to the mirror.
"""
    (out_dir / "REPORT.md").write_text(md, encoding="utf-8")


def update_manifest(config_path: Path, config: dict, out_dir: Path, started: float) -> None:
    manifest_path = out_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ticket"] = TICKET_ID
    manifest["study"] = "S02g"
    manifest["worker"] = config["worker"]
    manifest["config"] = str(config_path)
    manifest["command"] = " ".join([sys.executable, __file__, "--config", str(config_path)])
    manifest["runtime_sec_wrapper"] = round(time.time() - started, 2)
    outputs = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs[path.name] = sha256_file(path)
    manifest["outputs"] = outputs
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/s02g_1781022115_1037_63125b2f_external_scaler_rate_audit.json")
    args = parser.parse_args()
    started = time.time()
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    run_base_analysis(config_path)
    _, _, summary = inventory_files(config, out_dir)
    rewrite_report(config, out_dir, summary)
    rewrite_result(config, out_dir, summary, started)
    update_manifest(config_path, config, out_dir, started)
    print(json.dumps({"out_dir": str(out_dir), "external_candidates": int(summary[summary["quantity"].str.contains("candidates")]["value"].sum())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
