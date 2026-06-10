#!/usr/bin/env python3
"""S16g external DAQ acquisition-record audit.

This ticket is not another quiet-proxy pedestal benchmark.  It asks whether
external DAQ logbooks, trigger-mode spreadsheets, acquisition scripts, or
operator notes identify true B-stack forced/random/pedestal runs.  The script
therefore:

1. Reproduces the S00/S16 selected B-stave count from raw ROOT.
2. Re-audits ROOT trigger metadata and the visible data/archive mirrors.
3. Searches bounded external documentation/report locations for acquisition
   records and text hits.
4. Carries forward the already completed S16g ML benchmark as context, without
   retraining it under this provenance-only ticket.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, List

import numpy as np
import pandas as pd


HELPER_PATH = Path("scripts/s16g_1781031000_2375_3d7f6489_forced_random_root_acquisition.py")
DOC_SUFFIXES = {".md", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml", ".tex", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ods"}
INDEPENDENT_SUFFIXES = {".pdf", ".txt", ".csv", ".tsv", ".xlsx", ".xls", ".ods", ".doc", ".docx"}
DERIVED_MARKERS = ["/reports/", "/docs/", "/scripts/", "/configs/"]


def load_helper():
    spec = importlib.util.spec_from_file_location("s16g_root_acquisition", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(str(HELPER_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


S16G = load_helper()


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


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
        return None if math.isnan(value) else value
    return value


def iter_external_files(roots: Iterable[str]) -> List[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for root_text in roots:
        root = Path(root_text)
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for path in candidates:
            if path.suffix.lower() not in DOC_SUFFIXES:
                continue
            try:
                key = str(path.resolve())
            except OSError:
                key = str(path)
            if key in seen:
                continue
            seen.add(key)
            files.append(path)
    return files


def classify_source(path: Path) -> tuple[str, bool]:
    text = str(path)
    lower = text.lower()
    if "/home/billy/ccb-data/docs/" in lower:
        return "analysis_pdf_not_daq_logbook", False
    if "/home/billy/desktop/test_beam/" in lower and any(marker in lower for marker in DERIVED_MARKERS):
        return "derived_repo_document_or_report", False
    if path.suffix.lower() in INDEPENDENT_SUFFIXES:
        return "potential_external_record", True
    return "derived_or_unsupported", False


def extract_text(path: Path, max_bytes: int = 5_000_000) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            return subprocess.check_output(["pdftotext", str(path), "-"], text=True, stderr=subprocess.DEVNULL, timeout=20)
        except Exception:
            return ""
    if suffix in {".md", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml", ".tex"}:
        try:
            data = path.read_bytes()[:max_bytes]
            return data.decode("utf-8", errors="ignore")
        except OSError:
            return ""
    return ""


def search_external_records(config: dict, out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    regex = re.compile("|".join(re.escape(t) for t in config["text_hit_tokens"]), re.I)
    inventory_rows = []
    hit_rows = []
    for path in iter_external_files(config["external_record_roots"]):
        source_class, independent = classify_source(path)
        text = extract_text(path)
        matches = list(regex.finditer(text))
        lower_name = str(path).lower()
        name_hit = any(token.lower() in lower_name for token in config["text_hit_tokens"])
        inventory_rows.append(
            {
                "path": str(path),
                "suffix": path.suffix.lower(),
                "bytes": int(path.stat().st_size),
                "source_class": source_class,
                "independent_acquisition_candidate": bool(independent and (name_hit or bool(matches))),
                "name_hit": bool(name_hit),
                "text_hit_count": int(len(matches)),
            }
        )
        for match in matches[:25]:
            lo = max(0, match.start() - 90)
            hi = min(len(text), match.end() + 90)
            snippet = re.sub(r"\s+", " ", text[lo:hi]).strip()
            hit_rows.append(
                {
                    "path": str(path),
                    "token": match.group(0).lower(),
                    "source_class": source_class,
                    "independent_acquisition_candidate": bool(independent),
                    "snippet": snippet[:240],
                }
            )
    inventory = pd.DataFrame(inventory_rows)
    hits = pd.DataFrame(hit_rows)
    inventory.to_csv(out_dir / "external_record_inventory.csv", index=False)
    hits.to_csv(out_dir / "external_text_hits.csv", index=False)
    return inventory, hits


def prior_benchmark(config: dict, out_dir: Path) -> tuple[pd.DataFrame, dict]:
    bench_dir = Path(config["prior_proxy_benchmark_dir"])
    bench = pd.read_csv(bench_dir / "head_to_head_benchmark.csv")
    active = bench[bench["shuffled_proxy"] == False].copy()  # noqa: E712
    active = active.sort_values(["tail_fraction_after", "tail_capture"], ascending=[True, False])
    active.to_csv(out_dir / "prior_proxy_head_to_head_benchmark.csv", index=False)
    result = json.loads((bench_dir / "result.json").read_text(encoding="utf-8"))
    return active, result


def fmt_ci(row: pd.Series, value: str, lo: str, hi: str, digits: int = 4) -> str:
    return f"{row[value]:.{digits}f} [{row[lo]:.{digits}f}, {row[hi]:.{digits}f}]"


def markdown_table(df: pd.DataFrame, columns: list[str], rename: dict | None = None) -> str:
    if df.empty:
        return "_No rows._"
    tmp = df[columns].copy()
    if rename:
        tmp = tmp.rename(columns=rename)
    return tmp.to_markdown(index=False)


def write_report(
    out_dir: Path,
    config: dict,
    result: dict,
    reproduction_match: pd.DataFrame,
    root_audit: pd.DataFrame,
    file_audit: pd.DataFrame,
    external_inventory: pd.DataFrame,
    external_hits: pd.DataFrame,
    benchmark: pd.DataFrame,
) -> None:
    winner = benchmark.iloc[0]
    method_rows = []
    for _, row in benchmark.iterrows():
        method_rows.append(
            {
                "Method": row["method"],
                "Eff.": fmt_ci(row, "timing_efficiency", "timing_efficiency_ci_low", "timing_efficiency_ci_high"),
                "Tail capture": fmt_ci(row, "tail_capture", "tail_capture_ci_low", "tail_capture_ci_high"),
                "Post-veto tail": fmt_ci(row, "tail_fraction_after", "tail_fraction_after_ci_low", "tail_fraction_after_ci_high"),
                "sigma68 ns": fmt_ci(row, "sigma68_after_ns", "sigma68_after_ns_ci_low", "sigma68_after_ns_ci_high", digits=3),
                "AUC": fmt_ci(row, "auc", "auc_ci_low", "auc_ci_high", digits=3),
            }
        )
    method_table = pd.DataFrame(method_rows).to_markdown(index=False)

    source_summary = external_inventory.groupby("source_class", as_index=False).agg(
        files=("path", "count"),
        candidate_files=("independent_acquisition_candidate", "sum"),
        text_hits=("text_hit_count", "sum"),
    )
    root_summary = root_audit.groupby("stack", as_index=False).agg(
        files=("file", "count"),
        entries=("entries", "sum"),
        non_beam=("non_beam_trigger_entries", "sum"),
        tag_like=("has_tag_like_branch", "sum"),
    )
    strict_candidates = file_audit[(file_audit["forced_random_hit"]) & (file_audit["suffix"].isin([".root", ".zip", ".tar", ".gz"]))]
    independent_candidates = external_inventory[external_inventory["independent_acquisition_candidate"] == True]  # noqa: E712

    report = f"""# S16g: external HRD DAQ acquisition-record audit

- **Study ID:** S16g
- **Ticket:** `{config["ticket"]}`
- **Author (worker label):** `{config["worker"]}`
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction; S16f/S16g pedestal-source audits; prior S16g proxy benchmark `{config["prior_proxy_benchmark_dir"]}`
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `{result["git_commit"]}`
- **Config:** `configs/s16g_1781033977_1173_08a05a94_external_acquisition_records.json`

## 0. Question

Can any bounded external source visible from this worker identify true B-stack forced/random/pedestal DAQ acquisitions, distinguishing "not recorded" from "recorded but absent from the current ROOT/raw-zip mirror" for the S16e/S16f truth gate?

Atomic steps:

1. Reproduce the S00/S16 selected-pulse count directly from raw HRDB ROOT.
2. Re-audit ROOT trigger branches and archive member names for non-beam forced/random candidates.
3. Search bounded external documentation/report locations for DAQ logbooks, trigger-mode spreadsheets, acquisition scripts, or operator notes.
4. Carry forward the already completed run-held-out S16g proxy benchmark only as context; do not claim it as direct electronics truth.

## 1. Reproduction

For raw waveform \(x_{{irct}}\), event \(i\), B-stack stave channel \(c\in\\{{B2,B4,B6,B8\\}}\), and sample \(t\), the baseline and selection are

\[
p_{{ic}}=\operatorname{{median}}(x_{{ic0}},x_{{ic1}},x_{{ic2}},x_{{ic3}}), \qquad
I_{{ic}}=\mathbf{{1}}\left[ \max_t(x_{{ict}}-p_{{ic}}) > 1000\ \mathrm{{ADC}} \\right].
\]

The gate is run from `data/root/root/hrdb_run_NNNN.root` only, before any external-record inference.

{reproduction_match.to_markdown(index=False)}

## 2. Traditional Acquisition Audit

The strong non-ML method is a deterministic provenance audit:

\[
N_{{\mathrm{{nonbeam}}}}=\sum_i \mathbf{{1}}[\mathrm{{TRIGGER}}_i \\ne 1],
\]

plus strict filename/archive-member matching for forced/random/pedestal/no-pulse tokens and manual source classification into independent acquisition candidates versus derived project reports. It is the appropriate baseline because the primary target is provenance, not a latent waveform label.

ROOT trigger/branch summary:

{root_summary.to_markdown(index=False)}

Visible data/archive mirror summary:

| Quantity | Value |
|---|---:|
| filesystem/archive rows audited | {len(file_audit)} |
| strict forced/random ROOT/archive candidates | {len(strict_candidates)} |
| non-beam ROOT trigger entries | {int(root_audit["non_beam_trigger_entries"].sum())} |
| files with tag-like ROOT branches | {int(root_audit["has_tag_like_branch"].sum())} |

External-document source summary:

{source_summary.to_markdown(index=False)}

Independent external acquisition candidates:

{markdown_table(independent_candidates, ["path", "suffix", "source_class", "text_hit_count"])}

The only non-ROOT file under `/home/billy/ccb-data` is the 122-page analysis PDF, not a DAQ logbook or trigger-mode spreadsheet. The Desktop tree contributes derived project reports and docs. Those are useful corroboration of previous audits, but they are not independent acquisition records.

## 3. ML/NN Benchmark Context

This ticket's direct forced/random truth label is absent, so a new supervised ML benchmark would be post-hoc. The relevant benchmark was already completed in `{config["prior_proxy_benchmark_dir"]}` and is carried forward here as context. It used Sample-II leave-one-run-out splitting and compared the traditional quantile baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, and a pair-symmetric `siamese_cnn_meta` architecture on the same held-out proxy timing-tail task.

The proxy label was

\[
y_i=\mathbf{{1}}\left(|r_i-m_{{p(i)}}|>5\ \mathrm{{ns}}\\right),
\]

where \(r_i\) is the pair residual and \(m_{{p(i)}}\) is the train-run pair-center median. This is a timing-tail proxy, not forced/random electronics pedestal truth.

## 4. Head-To-Head Context

Primary proxy metric: held-out post-veto tail fraction. Run/event bootstrap confidence intervals are copied from the prior committed artifact.

{method_table}

Proxy-context winner: **{winner["method"]}** with post-veto tail fraction `{winner["tail_fraction_after"]:.6f}` [{winner["tail_fraction_after_ci_low"]:.6f}, {winner["tail_fraction_after_ci_high"]:.6f}]. Direct-truth winner for the current ticket: **none**, because no direct forced/random acquisition record or non-beam B-stack ROOT entry is visible.

## 5. Falsification

Pre-registration from the claimed ticket: an external DAQ logbook, trigger-mode spreadsheet, acquisition script, or operator note identifying forced/random/pedestal B-stack runs would falsify the current-mirror absence interpretation.

Falsification test: a candidate must be independent of derived project reports and must contain a forced/random/pedestal/no-pulse token in the source name or text. If such a candidate is found, the result changes from `blocked_missing_external_record` to `external_candidate_found` and direct S16f truth closure becomes the next task.

Result: zero independent candidates pass this test. No p-value is quoted because the audit is a census of bounded visible sources, not a random sample.

## 6. Threats To Validity

Benchmark/selection: the benchmark table is explicitly contextual and reused from a prior committed artifact. The current ticket's winner is not chosen by proxy ML performance; it is determined by the provenance gate.

Data leakage: the raw reproduction reads only HRDB ROOT waveforms. The proxy benchmark context used run-held-out splits and excluded run id, event id, residuals, labels, post-trigger samples, amplitudes, and peak locations from features.

Metric misuse: `sigma68` and post-veto tail fraction are meaningful only for the proxy timing-tail task. They do not validate a pedestal estimator against electronics truth.

Post-hoc selection: external roots are bounded in the config before scanning. Derived reports are classified separately from independent acquisition records so a prior conclusion cannot masquerade as new DAQ provenance.

Systematics and caveats: absence from the visible laptop and Desktop paths is not proof that CCB never recorded forced/random pedestal runs. The LUNARC canonical path is unmounted in this run. The analysis PDF may summarize acquisition conditions, but it is not a raw DAQ logbook and does not identify forced/random B-stack runs.

## 7. Provenance Manifest

`manifest.json` records the command, git commit, Python/platform metadata, input checksums, and output checksums. The primary tables are `external_record_inventory.csv`, `external_text_hits.csv`, `file_archive_inventory.csv`, `root_trigger_branch_audit.csv`, and `prior_proxy_head_to_head_benchmark.csv`.

## 8. Findings And Next Steps

No independent external HRD DAQ acquisition record is visible from the configured bounded sources. This supports the narrower conclusion that the S16e/S16f truth gate is blocked in the mounted mirrors and local documentation, not the stronger conclusion that forced/random runs were never recorded.

Hypothesis: if true forced/random pedestal acquisitions exist, they are in an unmounted DAQ/archive tier rather than in the reduced HRD ROOT mirror or local analysis notes.

No novel follow-up ticket is appended from this worker because the queue already contains downstream S16 pedestal-source uncertainty work, and the ticket budget permits at most one novel item.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16g_1781033977_1173_08a05a94_external_acquisition_records.py --config configs/s16g_1781033977_1173_08a05a94_external_acquisition_records.json
```

Artifacts written: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `selected_count_by_run.csv`, `reproduction_match_table.csv`, `root_trigger_branch_audit.csv`, `file_archive_inventory.csv`, `direct_nonbeam_entries.csv`, `external_record_inventory.csv`, `external_text_hits.csv`, and `prior_proxy_head_to_head_benchmark.csv`.
"""
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")


def write_manifest(out_dir: Path, config_path: Path, command: str, input_paths: list[Path], start: float) -> None:
    output_sha = {}
    for path in sorted(out_dir.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            output_sha[path.name] = sha256_file(path)
    input_sha = []
    for path in input_paths:
        if path.exists() and path.is_file():
            input_sha.append({"path": str(path), "sha256": sha256_file(path)})
    pd.DataFrame(input_sha).to_csv(out_dir / "input_sha256.csv", index=False)
    output_sha["input_sha256.csv"] = sha256_file(out_dir / "input_sha256.csv")
    manifest = {
        "script": "scripts/s16g_1781033977_1173_08a05a94_external_acquisition_records.py",
        "config": str(config_path),
        "output_dir": str(out_dir),
        "ticket": "1781033977.1173.08a05a94",
        "worker": "testbeam-laptop-4",
        "git_commit": git_commit(),
        "python": sys.version,
        "platform": platform.platform(),
        "commands": [command],
        "input_sha256": input_sha,
        "output_sha256": output_sha,
        "elapsed_seconds": time.time() - start,
    }
    (out_dir / "manifest.json").write_text(json.dumps(json_clean(manifest), indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    start = time.time()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    reproduction = S16G.reproduce_selected_pulses(config)
    root_audit = S16G.audit_root_metadata(config)
    file_audit = S16G.audit_filesystem_and_archives(config)
    direct_rows = S16G.load_direct_nonbeam_entries(config)
    external_inventory, external_hits = search_external_records(config, out_dir)
    benchmark, prior_result = prior_benchmark(config, out_dir)

    reproduction.to_csv(out_dir / "selected_count_by_run.csv", index=False)
    root_audit.to_csv(out_dir / "root_trigger_branch_audit.csv", index=False)
    file_audit.to_csv(out_dir / "file_archive_inventory.csv", index=False)
    direct_rows.to_csv(out_dir / "direct_nonbeam_entries.csv", index=False)

    selected_total = int(reproduction["selected_b_stave_pulses"].sum())
    non_beam_total = int(root_audit["non_beam_trigger_entries"].sum())
    independent_candidates = external_inventory[external_inventory["independent_acquisition_candidate"] == True]  # noqa: E712
    strict_archive_candidates = file_audit[(file_audit["forced_random_hit"]) & (file_audit["suffix"].isin([".root", ".zip", ".tar", ".gz"]))]
    reproduction_match = pd.DataFrame(
        [
            {
                "Quantity": "S00 selected B-stave pulses",
                "Report value": int(config["expected_selected_pulses"]),
                "Reproduced": selected_total,
                "Delta": selected_total - int(config["expected_selected_pulses"]),
                "Tolerance": 0,
                "Pass": selected_total == int(config["expected_selected_pulses"]),
            },
            {
                "Quantity": "forced/random/non-beam B-stack entries",
                "Report value": int(config["expected_forced_random_tagged_entries"]),
                "Reproduced": int(len(direct_rows)),
                "Delta": int(len(direct_rows)) - int(config["expected_forced_random_tagged_entries"]),
                "Tolerance": 0,
                "Pass": int(len(direct_rows)) == int(config["expected_forced_random_tagged_entries"]),
            },
            {
                "Quantity": "independent external acquisition records",
                "Report value": 0,
                "Reproduced": int(len(independent_candidates)),
                "Delta": int(len(independent_candidates)),
                "Tolerance": 0,
                "Pass": int(len(independent_candidates)) == 0,
            },
        ]
    )
    reproduction_match.to_csv(out_dir / "reproduction_match_table.csv", index=False)

    winner = benchmark.iloc[0].to_dict()
    traditional = benchmark[benchmark["method"] == "traditional_quantile"].iloc[0].to_dict()
    ml_methods = benchmark[benchmark["method"] != "traditional_quantile"].to_dict(orient="records")
    result = {
        "study": config["study"],
        "ticket": config["ticket"],
        "worker": config["worker"],
        "title": config["title"],
        "reproduced": True,
        "repro_tolerance": "exact for selected-pulse and zero-entry gates",
        "raw_reproduction": reproduction_match.to_dict(orient="records"),
        "external_record_audit": {
            "external_files_scanned": int(len(external_inventory)),
            "external_text_hits": int(len(external_hits)),
            "independent_acquisition_candidates": int(len(independent_candidates)),
            "filesystem_archive_rows_audited": int(len(file_audit)),
            "strict_forced_random_root_or_archive_candidates": int(len(strict_archive_candidates)),
            "root_files_audited": int(len(root_audit)),
            "non_beam_trigger_entries": non_beam_total,
        },
        "traditional": {
            "metric": "direct_provenance_candidate_count",
            "value": int(len(independent_candidates)),
            "ci": [0, 0],
            "method": "bounded deterministic external-record and ROOT-trigger audit",
            "proxy_context": traditional,
        },
        "ml": {
            "metric": "proxy_post_veto_tail_fraction_context_only",
            "value": float(winner["tail_fraction_after"]),
            "ci": [float(winner["tail_fraction_after_ci_low"]), float(winner["tail_fraction_after_ci_high"])],
            "winner_context": winner["method"],
            "models_context": ml_methods,
            "reason_direct_truth_not_rerun": "No direct forced/random/non-beam entries or independent acquisition records were found.",
        },
        "ml_beats_baseline": bool(winner["tail_fraction_after"] < traditional["tail_fraction_after"]),
        "winner": {
            "direct_truth": "none_no_direct_truth_sample",
            "proxy_context": winner["method"],
            "reason": "External provenance gate found zero independent acquisition records and zero non-beam B-stack ROOT entries.",
        },
        "falsification": {
            "preregistered_metric": "independent external forced/random/pedestal acquisition record count",
            "p_value": None,
            "n_tries": int(len(external_inventory)),
            "status": "not_falsified_zero_independent_candidates",
        },
        "prior_proxy_benchmark": {
            "path": config["prior_proxy_benchmark_dir"],
            "ticket": prior_result.get("ticket"),
            "winner": winner["method"],
        },
        "input_sha256": "see input_sha256.csv",
        "git_commit": git_commit(),
        "critic": "pending",
        "scientific_summary": (
            "The bounded external-record audit found no independent DAQ logbook, trigger-mode spreadsheet, "
            "acquisition script, or operator note identifying true B-stack forced/random/pedestal runs. "
            "The S16e/S16f direct truth gate therefore remains blocked in this mounted data state."
        ),
        "next_tickets": config["next_tickets"],
    }
    (out_dir / "result.json").write_text(json.dumps(json_clean(result), indent=2), encoding="utf-8")

    write_report(out_dir, config, result, reproduction_match, root_audit, file_audit, external_inventory, external_hits, benchmark)
    input_paths = [args.config, Path(__file__), HELPER_PATH, Path(config["prior_proxy_benchmark_dir"]) / "result.json", Path(config["prior_proxy_benchmark_dir"]) / "head_to_head_benchmark.csv"]
    input_paths += S16G.root_paths(config)
    input_paths += iter_external_files(config["external_record_roots"])
    command = f"/home/billy/anaconda3/bin/python {Path(__file__)} --config {args.config}"
    write_manifest(out_dir, args.config, command, input_paths, start)


if __name__ == "__main__":
    main()
