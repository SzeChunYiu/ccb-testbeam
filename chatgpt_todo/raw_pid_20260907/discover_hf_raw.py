#!/usr/bin/env python3
"""Read-only inventory of billyyiu747/ccb-testbeam for the raw PID notebook.

This script deliberately performs no physics calculation.  Its only job is to
bind the later notebook to actual repository bytes/schema before analysis.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download
import pyarrow.parquet as pq

REPO_ID = "billyyiu747/ccb-testbeam"


def entry_dict(entry):
    return {
        "type": type(entry).__name__,
        "path": getattr(entry, "path", None),
        "size": getattr(entry, "size", None),
        "oid": getattr(entry, "oid", None),
    }


def inspect_parquet(path: str) -> dict:
    local = hf_hub_download(REPO_ID, path, repo_type="dataset")
    pf = pq.ParquetFile(local)
    schema = pf.schema_arrow
    preview = pf.read_row_group(0).slice(0, 3).to_pydict() if pf.num_row_groups else {}
    return {
        "path": path,
        "local_bytes": Path(local).stat().st_size,
        "num_row_groups": pf.num_row_groups,
        "num_rows": pf.metadata.num_rows if pf.metadata else None,
        "schema": [{"name": f.name, "type": str(f.type)} for f in schema],
        "preview": preview,
    }


def main() -> int:
    api = HfApi()
    entries = list(api.list_repo_tree(REPO_ID, repo_type="dataset", recursive=True, expand=True))
    files = [e for e in entries if getattr(e, "path", None) and type(e).__name__.lower().endswith("file")]
    rows = [entry_dict(e) for e in files]

    prefixes = Counter((r["path"].split("/", 1)[0] if "/" in r["path"] else "<root>") for r in rows)
    parquets = [r for r in rows if r["path"].endswith(".parquet")]
    samples = [r for r in rows if "/sample/" in r["path"] or r["path"].endswith("events_sample.parquet")]
    archives = [r for r in rows if r["path"].lower().endswith((".zip", ".tar", ".gz", ".root"))]

    summary = {
        "repo_id": REPO_ID,
        "n_entries": len(entries),
        "n_files": len(rows),
        "top_level_counts": dict(sorted(prefixes.items())),
        "sample_files": samples,
        "archive_or_root_files": archives[:200],
        "smallest_parquets": sorted(parquets, key=lambda r: (r["size"] is None, r["size"] or 0))[:50],
    }

    candidate_paths = []
    preferred = [
        "parquet/sample/events_sample.parquet",
        "sorted/sample/events_sample.parquet",
    ]
    available = {r["path"] for r in rows}
    for path in preferred:
        if path in available:
            candidate_paths.append(path)
    if not candidate_paths:
        candidate_paths.extend([r["path"] for r in summary["smallest_parquets"][:2]])

    inspected = []
    for path in candidate_paths:
        try:
            inspected.append(inspect_parquet(path))
        except Exception as exc:
            inspected.append({"path": path, "error": f"{type(exc).__name__}: {exc}"})
    summary["inspected_parquets"] = inspected

    print("===CCB_HF_DISCOVERY_JSON_BEGIN===")
    print(json.dumps(summary, indent=2, default=str))
    print("===CCB_HF_DISCOVERY_JSON_END===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
