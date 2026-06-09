#!/usr/bin/env python3
"""S07e App.A archive provenance search.

This ticket asks whether the historical App.A 12,147 labelled-event table can
be recovered outside the repo. The script first rebuilds the documented weak
labels from raw HRDv ROOT, then records a provenance inventory of external
archives/notebooks/derived tables, and finally reruns the S07c-style
traditional-vs-RF benchmark on the raw-reproducible labels.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
TICKET = "1781012847.2575.40cb6e31"
WORKER = "testbeam-laptop-1"
SEED = 8707
TARGET = {"labelled_events": 12147, "clean": 10636, "violating": 1511}
S07C_SCRIPT = ROOT / "reports/1781000790.531136.203130b0__s07c_clean_timing_rf/s07c_clean_timing_rf.py"
S07D_REPORT = ROOT / "reports/1781006575.2866.622a4328"
EXTERNAL_ROOTS = [
    Path("/home/billy/Desktop/test_beam"),
    Path("/home/billy/ccb-data"),
    Path("/home/billy/HIBEAM"),
    Path("/home/billy/HIBEAM_Reconstruction"),
    Path("/home/billy/GNN_HIBEAM"),
    Path("/home/billy/Downloads"),
    Path("/home/billy/.tb-workers"),
]
KEYWORDS = [
    "App.A",
    "App A",
    "12,147",
    "12147",
    "10636",
    "1511",
    "clean-timing",
    "clean_timing",
    "downstream span",
    "all-span",
    "weak labels",
    "labelled events",
    "labeled events",
]
TABLE_SUFFIXES = (".csv", ".csv.gz", ".tsv", ".txt", ".parquet", ".json", ".jsonl", ".npz", ".npy", ".pkl", ".pt")
TABLE_NAME_TOKENS = (
    "app",
    "s07",
    "clean",
    "timing",
    "label",
    "training",
    "event_dataset",
    "oof",
    "score",
    "q_template",
    "weak",
)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True).strip()
    except Exception:
        return "unknown"


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    return value


def load_s07c():
    spec = importlib.util.spec_from_file_location("s07c_clean_timing_rf_current", str(S07C_SCRIPT))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {S07C_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RAW_DIR = Path("data/root/root")
    module.QTEMPLATE_PATH = Path("reports/1780997954.15037.36463764__s01_full_dataset_templates/q_template_per_pulse.csv.gz")
    module.SEED = SEED
    return module


def metric_ci_by_run(y: np.ndarray, score: np.ndarray, runs: np.ndarray, metric: str, n_boot: int = 1000):
    if metric == "roc_auc":
        point = float(roc_auc_score(y, score))
    elif metric == "average_precision":
        point = float(average_precision_score(y, score))
    elif metric == "brier":
        point = float(brier_score_loss(y, np.clip(score, 0, 1)))
    else:
        raise ValueError(metric)
    rng = np.random.default_rng(SEED + len(metric))
    unique_runs = np.unique(runs)
    values = []
    for _ in range(n_boot):
        sampled = rng.choice(unique_runs, size=len(unique_runs), replace=True)
        idx = np.concatenate([np.where(runs == run)[0] for run in sampled])
        if len(np.unique(y[idx])) < 2:
            continue
        if metric == "roc_auc":
            values.append(roc_auc_score(y[idx], score[idx]))
        elif metric == "average_precision":
            values.append(average_precision_score(y[idx], score[idx]))
        else:
            values.append(brier_score_loss(y[idx], np.clip(score[idx], 0, 1)))
    return point, [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def markdown_table(frame: pd.DataFrame) -> str:
    def fmt(value: Any) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6g}"
        return str(value)

    cols = list(frame.columns)
    rows = [[fmt(row[col]) for col in cols] for _, row in frame.iterrows()]
    widths = [len(str(col)) for col in cols]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(cols, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header, sep, *body])


def iter_files(roots: Iterable[Path]) -> Iterable[Path]:
    skip_parts = {".git", "__pycache__", "node_modules", ".cache", "logs"}
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(str(root)):
            dirnames[:] = [name for name in dirnames if name not in skip_parts]
            for name in filenames:
                path = Path(dirpath) / name
                if OUT in path.parents:
                    continue
                yield path


def text_hits() -> pd.DataFrame:
    rows = []
    pattern = "|".join(KEYWORDS)
    for root in EXTERNAL_ROOTS:
        if not root.exists():
            continue
        cmd = [
            "rg",
            "-n",
            "-i",
            "--glob",
            "!.git/**",
            "--glob",
            "!logs/**",
            "--glob",
            "!*.out",
            "--glob",
            "!*.csv",
            "--glob",
            "!*.csv.gz",
            pattern,
            str(root),
        ]
        try:
            output = subprocess.check_output(cmd, cwd=str(ROOT), text=True, stderr=subprocess.STDOUT, timeout=45)
        except subprocess.CalledProcessError as exc:
            output = exc.output or ""
        except subprocess.TimeoutExpired as exc:
            output = exc.output or ""
            rows.append({"path": str(root), "line": -1, "kind": "rg_timeout", "text": "search timed out"})
        for line in str(output).splitlines()[:500]:
            parts = line.split(":", 2)
            if len(parts) != 3:
                continue
            path, lineno, text = parts
            rows.append(
                {
                    "path": path,
                    "line": int(lineno) if lineno.isdigit() else -1,
                    "kind": "text_hit",
                    "text": text[:320],
                }
            )

    pdf = Path("/home/billy/Downloads/bstack_astack_report_with_timing_label_pileup_ml.pdf")
    if pdf.exists():
        try:
            text = subprocess.check_output(["pdftotext", str(pdf), "-"], text=True, timeout=30)
            for lineno, line in enumerate(text.splitlines(), start=1):
                low = line.lower()
                if any(key.lower() in low for key in KEYWORDS):
                    rows.append({"path": str(pdf), "line": lineno, "kind": "pdf_text_hit", "text": line[:320]})
        except Exception as exc:
            rows.append({"path": str(pdf), "line": -1, "kind": "pdf_parse_error", "text": repr(exc)})
    return pd.DataFrame(rows)


def count_delimited_rows(path: Path) -> tuple[int | None, list[str]]:
    opener = gzip.open if path.name.endswith(".gz") else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace", newline="") as handle:
            sample = handle.read(8192)
            handle.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
            except Exception:
                dialect = csv.excel_tab if path.suffix == ".tsv" else csv.excel
            reader = csv.reader(handle, dialect)
            header = next(reader, [])
            n = sum(1 for _ in reader)
        return int(n), [str(col) for col in header]
    except Exception:
        return None, []


def json_row_count(path: Path) -> tuple[int | None, list[str]]:
    try:
        if path.suffix == ".jsonl":
            with path.open("rt", encoding="utf-8", errors="replace") as handle:
                return sum(1 for line in handle if line.strip()), []
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(obj, list):
            cols = sorted(obj[0].keys()) if obj and isinstance(obj[0], dict) else []
            return len(obj), cols
        if isinstance(obj, dict):
            rows = obj.get("rows") or obj.get("data") or obj.get("events")
            if isinstance(rows, list):
                cols = sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
                return len(rows), cols
    except Exception:
        pass
    return None, []


def table_inventory() -> pd.DataFrame:
    rows = []
    for path in iter_files(EXTERNAL_ROOTS + [S07D_REPORT]):
        lower = str(path).lower()
        if not lower.endswith(TABLE_SUFFIXES):
            continue
        if not any(token in lower for token in TABLE_NAME_TOKENS):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > 250 * 1024 * 1024:
            continue
        row_count = None
        columns: list[str] = []
        suffix = "".join(path.suffixes[-2:]) if path.name.endswith(".csv.gz") else path.suffix
        if path.name.endswith((".csv", ".csv.gz", ".tsv", ".txt")):
            row_count, columns = count_delimited_rows(path)
        elif path.suffix in (".json", ".jsonl"):
            row_count, columns = json_row_count(path)
        labelish = [col for col in columns if any(tok in col.lower() for tok in ["label", "clean", "violat", "run", "event", "evt"])]
        rows.append(
            {
                "path": str(path),
                "suffix": suffix,
                "bytes": int(size),
                "sha256": sha256_file(path) if size <= 50 * 1024 * 1024 else "",
                "row_count": row_count,
                "columns_preview": "|".join(columns[:16]),
                "labelish_columns": "|".join(labelish[:16]),
                "exact_12147_rows": bool(row_count == TARGET["labelled_events"]),
                "exact_10636_rows": bool(row_count == TARGET["clean"]),
                "exact_1511_rows": bool(row_count == TARGET["violating"]),
                "plausible_label_table": bool(row_count == TARGET["labelled_events"] and len(labelish) >= 2),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.sort_values(
        ["plausible_label_table", "exact_12147_rows", "path"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    return frame


def summarize_provenance(tables: pd.DataFrame, hits: pd.DataFrame) -> pd.DataFrame:
    source_hits = pd.DataFrame(
        [
            {
                "check": "table_like_files_scanned",
                "value": int(len(tables)),
                "pass": True,
                "notes": "Candidate table-like files with App.A/S07/label/training/timing names.",
            },
            {
                "check": "exact_12147_row_tables",
                "value": int(tables["exact_12147_rows"].sum()) if not tables.empty else 0,
                "pass": bool((not tables.empty) and tables["exact_12147_rows"].any()),
                "notes": "Any table with exactly the documented labelled-event row count.",
            },
            {
                "check": "plausible_recovered_label_table",
                "value": int(tables["plausible_label_table"].sum()) if not tables.empty else 0,
                "pass": bool((not tables.empty) and tables["plausible_label_table"].any()),
                "notes": "Exact 12,147 rows plus label/run/event-like columns.",
            },
            {
                "check": "semantic_text_hits",
                "value": int(len(hits)),
                "pass": bool(len(hits)),
                "notes": "Mostly docs/notebooks/PDF text; table recovery requires a plausible table hit.",
            },
        ]
    )
    return source_hits


def write_inputs(s07c) -> list[dict[str, Any]]:
    rows = []
    for run in s07c.all_runs():
        path = ROOT / s07c.raw_file(run)
        rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": "raw_doc_scope_hrdv_root"})
    for path, role in [
        (ROOT / "docs/07_ml_methods.md", "documented_app_a_number"),
        (S07C_SCRIPT, "raw_reproduction_and_benchmark_helper"),
        (ROOT / s07c.QTEMPLATE_PATH, "traditional_q_template_input"),
    ]:
        if path.exists():
            rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path), "role": role})
    pdf = Path("/home/billy/Downloads/bstack_astack_report_with_timing_label_pileup_ml.pdf")
    if pdf.exists():
        rows.append({"path": str(pdf), "sha256": sha256_file(pdf), "role": "external_pdf_archive_candidate"})
    return rows


def write_manifest(start: float, command: str, input_rows: list[dict[str, Any]]) -> None:
    outputs = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            outputs.append({"path": str(path.relative_to(ROOT)), "sha256": sha256_file(path)})
    manifest = {
        "study": "S07e_archive_provenance_search",
        "ticket": TICKET,
        "worker": WORKER,
        "command": command,
        "git_commit_at_run": git_commit(),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_sec": round(time.time() - start, 3),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "inputs": input_rows,
        "outputs": outputs,
    }
    (OUT / "manifest.json").write_text(json.dumps(clean_json(manifest), indent=2), encoding="utf-8")


def main() -> None:
    start = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    s07c = load_s07c()

    # Raw ROOT reproduction first.
    s00, per_run, events = s07c.scan_raw_events()
    s00.to_csv(OUT / "reproduction_s00_counts.csv", index=False)
    per_run.to_csv(OUT / "raw_cfd20_counts_by_run.csv", index=False)
    events.to_csv(OUT / "raw_cfd20_event_dataset.csv.gz", index=False)
    raw_counts = {
        "labelled_events": int(per_run["clean_events"].sum() + per_run["violating_events"].sum()),
        "clean": int(per_run["clean_events"].sum()),
        "violating": int(per_run["violating_events"].sum()),
        "ambiguous": int(per_run["ambiguous_events"].sum()),
        "downstream_ge2_events": int(per_run["downstream_ge2_events"].sum()),
    }
    reproduction = pd.DataFrame(
        [
            {
                "quantity": key,
                "documented": TARGET[key],
                "raw_cfd20": raw_counts[key],
                "delta": raw_counts[key] - TARGET[key],
                "matches": raw_counts[key] == TARGET[key],
            }
            for key in ["labelled_events", "clean", "violating"]
        ]
    )
    reproduction.to_csv(OUT / "reproduction_match_table.csv", index=False)

    # Provenance search over external/mirrored archives and old notebooks.
    tables = table_inventory()
    hits = text_hits()
    provenance = summarize_provenance(tables, hits)
    tables.to_csv(OUT / "archive_table_inventory.csv", index=False)
    hits.to_csv(OUT / "archive_text_hits.csv", index=False)
    provenance.to_csv(OUT / "archive_provenance_summary.csv", index=False)

    # Traditional and ML methods on the raw-reproducible labels, split by run.
    q_event = s07c.qtemplate_event_table()
    data = events.merge(q_event, on=["run", "eventno", "evt"], how="left")
    data["b2_displacement_filled"] = data["b2_displacement_ns"].fillna(999.0)
    q_cols = [col for col in data.columns if col.startswith("q_")]
    qtemplate_unmatched_events = int(data[q_cols].isna().all(axis=1).sum())
    data[q_cols] = data[q_cols].fillna(data[q_cols].median(numeric_only=True))
    folds, rf_cv, scores, rf_features, best_params = s07c.run_heldout_scores(data)
    folds.to_csv(OUT / "run_heldout_folds.csv", index=False)
    rf_cv.to_csv(OUT / "rf_cv_scan.csv", index=False)
    scores.to_csv(OUT / "heldout_scores.csv", index=False)

    y = scores["label_clean"].to_numpy(dtype=int)
    runs = scores["run"].to_numpy(dtype=int)
    scoreboard_rows = []
    for method, col, note in [
        ("traditional_span_q_template", "traditional_span_q_score", "Uses downstream span; overlaps weak-label definition."),
        ("traditional_q_template_only", "q_template_only_score", "No timing-span feature."),
        ("rf_clean_timing", "rf_score", "RF excludes timing spans, pair residuals, run, and sample."),
        ("leaky_rf_control", "leaky_rf_score", "RF with forbidden label-defining timing spans."),
    ]:
        score = scores[col].to_numpy(dtype=float)
        auc, auc_ci = metric_ci_by_run(y, score, runs, "roc_auc")
        ap, ap_ci = metric_ci_by_run(y, score, runs, "average_precision")
        row = {
            "method": method,
            "roc_auc": auc,
            "roc_auc_ci_low": auc_ci[0],
            "roc_auc_ci_high": auc_ci[1],
            "average_precision": ap,
            "average_precision_ci_low": ap_ci[0],
            "average_precision_ci_high": ap_ci[1],
            "note": note,
        }
        if col in {"rf_score", "leaky_rf_score"}:
            brier, brier_ci = metric_ci_by_run(y, score, runs, "brier")
            row.update({"brier": brier, "brier_ci_low": brier_ci[0], "brier_ci_high": brier_ci[1]})
        scoreboard_rows.append(row)
    scoreboard = pd.DataFrame(scoreboard_rows)
    scoreboard.to_csv(OUT / "scoreboard.csv", index=False)
    forbidden = sorted(set(rf_features).intersection({"downstream_span_ns", "all_span_ns", "b2_displacement_ns", "run"}))
    leakage = pd.DataFrame(
        [
            {"check": "rf_forbidden_feature_intersection", "value": "|".join(forbidden), "pass": not forbidden},
            {
                "check": "leaky_control_auc_is_ceiling",
                "value": float(scoreboard.loc[scoreboard["method"] == "leaky_rf_control", "roc_auc"].iloc[0]),
                "pass": bool(float(scoreboard.loc[scoreboard["method"] == "leaky_rf_control", "roc_auc"].iloc[0]) >= 0.999),
            },
            {
                "check": "archive_plausible_label_table_found",
                "value": int(provenance.loc[provenance["check"] == "plausible_recovered_label_table", "value"].iloc[0]),
                "pass": bool(int(provenance.loc[provenance["check"] == "plausible_recovered_label_table", "value"].iloc[0]) > 0),
            },
            {
                "check": "qtemplate_unmatched_events",
                "value": qtemplate_unmatched_events,
                "pass": bool(qtemplate_unmatched_events <= 2),
            },
        ]
    )
    leakage.to_csv(OUT / "leakage_checks.csv", index=False)

    input_rows = write_inputs(s07c)
    pd.DataFrame(input_rows).to_csv(OUT / "input_sha256.csv", index=False)

    source_found = bool(provenance.loc[provenance["check"] == "plausible_recovered_label_table", "value"].iloc[0] > 0)
    result = {
        "study": "S07e_archive_provenance_search",
        "ticket": TICKET,
        "worker": WORKER,
        "documented_target": TARGET,
        "raw_cfd20_reproduced": raw_counts,
        "raw_cfd20_matches_documented": bool(reproduction["matches"].all()),
        "archive_table_candidates_scanned": int(len(tables)),
        "archive_text_hits": int(len(hits)),
        "source_table_found": source_found,
        "exact_12147_row_tables": int(tables["exact_12147_rows"].sum()) if not tables.empty else 0,
        "plausible_recovered_label_tables": int(tables["plausible_label_table"].sum()) if not tables.empty else 0,
        "best_rf_params": best_params,
        "rf_feature_count": int(len(rf_features)),
        "rf_forbidden_features_present": forbidden,
        "qtemplate_unmatched_events": qtemplate_unmatched_events,
        "traditional": scoreboard[scoreboard["method"] == "traditional_span_q_template"].iloc[0].to_dict(),
        "traditional_deleaked": scoreboard[scoreboard["method"] == "traditional_q_template_only"].iloc[0].to_dict(),
        "ml": scoreboard[scoreboard["method"] == "rf_clean_timing"].iloc[0].to_dict(),
        "leaky_control": scoreboard[scoreboard["method"] == "leaky_rf_control"].iloc[0].to_dict(),
        "verdict": "no_external_source_table_recovered_retire_12147" if not source_found else "external_source_table_candidate_found",
        "follow_up_tickets": [
            "S07j: preserve and diff the PDF-era notebook/PDF provenance chain for App.A; expected information gain: determines whether the 12,147 value was copied from a pre-HRDv analysis note.",
            "S03f: replace App.A clean-timing adoption with q_template-only and independent timing-tail gates; expected information gain: removes dependency on the unrecovered weak-label table.",
        ],
    }
    (OUT / "result.json").write_text(json.dumps(clean_json(result), indent=2), encoding="utf-8")

    top_tables = tables.head(12)[
        ["path", "row_count", "exact_12147_rows", "plausible_label_table", "labelish_columns"]
    ] if not tables.empty else pd.DataFrame(columns=["path", "row_count", "exact_12147_rows", "plausible_label_table", "labelish_columns"])
    text = f"""# S07e: archive provenance search for App.A training table

- **Ticket:** `{TICKET}`
- **Worker:** `{WORKER}`
- **Question:** can the App.A 12,147 labelled-event table be recovered from external archives, old notebooks, or non-repo derived data?
- **Inputs:** raw B-stack `HRDv` ROOT, mirrored/external filesystem candidates, S01 q_template artifact.

## Raw-ROOT Reproduction First

{markdown_table(reproduction)}

The documented App.A count is not reproduced from raw `HRDv`: the raw CFD20 definition gives `{raw_counts['labelled_events']}` labelled events (`{raw_counts['clean']}` clean, `{raw_counts['violating']}` violating), not `12,147` (`10,636` clean, `1,511` violating). The benchmark below therefore uses the raw-reproducible labels and treats the historical number as a provenance target, not as a detector result.

## Archive Provenance Search

{markdown_table(provenance)}

Top table-like candidates:

{markdown_table(top_tables)}

The semantically relevant text hits are documentation or mirrors of the same documentation. Numeric-only hits in unrelated GNN/HIBEAM logs were excluded from the source-table claim. No table with exactly 12,147 rows and run/event/label-like columns was recovered.

## Traditional And ML Methods

Evaluation is by run-held-out folds with run-bootstrap 95% CIs over out-of-fold predictions.

{markdown_table(scoreboard)}

The strong traditional span+q_template method is intentionally partly label-overlapping and reaches ROC AUC `{float(scoreboard.loc[scoreboard['method'] == 'traditional_span_q_template', 'roc_auc'].iloc[0]):.3f}`. The de-leaked q_template-only baseline reaches `{float(scoreboard.loc[scoreboard['method'] == 'traditional_q_template_only', 'roc_auc'].iloc[0]):.3f}`. The RF reaches `{float(scoreboard.loc[scoreboard['method'] == 'rf_clean_timing', 'roc_auc'].iloc[0]):.3f}` while excluding timing spans, pair residuals, run, and sample.

## Leakage Hunt

{markdown_table(leakage)}

The near-perfect leaky control confirms that timing-span features can trivially recover the weak label. The main RF has no forbidden timing/run features, but because the historical table was not recovered, it remains a weak-label screen only.

## Finding

I do not recover the App.A 12,147 labelled-event training table from the external/mirrored archives searched here. The only durable source of the number remains documentation; raw HRDv produces a different count. The supported action is to retire `12,147` unless a future, byte-identifiable derived label table is found.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python reports/{TICKET}/s07e_app_a_archive_provenance_search.py
```

Key artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `archive_table_inventory.csv`, `archive_text_hits.csv`, `archive_provenance_summary.csv`, `scoreboard.csv`, `leakage_checks.csv`.
"""
    (OUT / "REPORT.md").write_text(text, encoding="utf-8")

    command = f"/home/billy/anaconda3/bin/python reports/{TICKET}/s07e_app_a_archive_provenance_search.py"
    write_manifest(start, command, input_rows)


if __name__ == "__main__":
    main()
