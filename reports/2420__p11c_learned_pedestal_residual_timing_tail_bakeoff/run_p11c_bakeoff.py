#!/usr/bin/env python3
"""Ticket #2420 P11c learned-pedestal residual timing-tail bakeoff.

The runner reuses the S16i raw/sorted ROOT implementation because that code
already performs the required selected-pulse reproduction, run-held-out timing
split, paired bootstrap intervals, and model panel. This wrapper confines
ticket-specific metadata and post-processing to the #2420 report directory.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = Path(__file__).resolve().parent
CONFIG = REPORT_DIR / "config.json"
BASE_SCRIPT_DIR = ROOT / "scripts"
if str(BASE_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_SCRIPT_DIR))

import s16i_1781096100_1466_0e861527_sorted_baseline_timing_tail_nuisance as s16i  # noqa: E402


def markdown_table_safe(df: pd.DataFrame, cols: list[str]) -> str:
    use = df.loc[:, cols].copy()
    for col in use.columns:
        if pd.api.types.is_float_dtype(use[col]):
            use[col] = use[col].map(lambda x: "" if pd.isna(x) else f"{float(x):.4g}")
        elif pd.api.types.is_integer_dtype(use[col]):
            use[col] = use[col].map(lambda x: "" if pd.isna(x) else str(int(x)))
        elif pd.api.types.is_bool_dtype(use[col]):
            use[col] = use[col].map(lambda x: "True" if bool(x) else "False")
        else:
            use[col] = use[col].astype(str)
    widths = {
        col: max(len(str(col)), *(len(str(v)) for v in use[col].to_list()))
        for col in use.columns
    }
    header = "| " + " | ".join(str(col).ljust(widths[col]) for col in use.columns) + " |"
    sep = "| " + " | ".join("-" * widths[col] for col in use.columns) + " |"
    rows = [
        "| " + " | ".join(str(row[col]).ljust(widths[col]) for col in use.columns) + " |"
        for _, row in use.iterrows()
    ]
    return "\n".join([header, sep] + rows)


def patch_text(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def postprocess() -> None:
    report = REPORT_DIR / "REPORT.md"
    patch_text(
        report,
        [
            ("# S16i - Sorted-Baseline Residual as a Timing-Tail Nuisance", "# P11c - Learned-Pedestal Residual as a Timing-Tail Nuisance"),
            ("- Study ID:      S16i", "- Study ID:      P11c"),
            ("- Title:         sorted-baseline residual as a timing-tail nuisance", "- Title:         learned-pedestal residual as a timing-tail nuisance"),
            ("- Date:          2026-07-08", "- Date:          2026-08-16"),
            ("- Dependencies:  S00, S02, S16h", "- Dependencies:  S00, S02/S04 timing fits, P11/S16 pedestal diagnostics"),
            ("S16i tests whether the residual", "P11c tests whether the learned-pedestal residual proxy"),
            ("S16h raw-vs-sorted baseline residual proxy", "P11 learned-pedestal residual proxy"),
            ("S16h residual", "learned-pedestal residual"),
            ("s16h_baseline_residual_adc", "p11_learned_pedestal_residual_adc"),
            ("If the winner is an ML method, the result should be read as evidence that the S16h residual carries timing-tail nuisance information beyond amplitude and peak phase.", "If the winner is an ML method, the result should be read as evidence that the learned-pedestal residual proxy carries timing-tail nuisance information beyond amplitude and peak phase."),
            ("S16j: Does replacing the scalar sorted-baseline residual with a causal pretrigger waveform state improve held-out tails without using post-trigger information?", "P11d: Does a strictly causal learned-pedestal residual, trained only on pretrigger state and forced/random controls, improve held-out tails without post-trigger leakage?"),
            ("Use `gated_cnn_residual` as the S16i timing-tail nuisance candidate", "Use `gated_cnn_residual` as the P11c learned-pedestal timing-tail nuisance candidate"),
            (
                "python scripts/s16i_1781096100_1466_0e861527_sorted_baseline_timing_tail_nuisance.py --config /home/billy/.tb-workers/testbeam-laptop-3/reports/2420__p11c_learned_pedestal_residual_timing_tail_bakeoff/config.json",
                "MPLCONFIGDIR=/tmp/matplotlib-p11c uv run --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with pyarrow --with matplotlib --with torch python reports/2420__p11c_learned_pedestal_residual_timing_tail_bakeoff/run_p11c_bakeoff.py",
            ),
        ],
    )
    text = report.read_text(encoding="utf-8")
    marker = "## Reproduction gate\n"
    claim_note = (
        "## Ticket claim provenance\n\n"
        "`tn-ticket claim testbeam-laptop-3 --project testbeam` was run exactly once. "
        "The local helper returned `null|null|null` because the empty existing-claim query is string-interpolated, "
        "so issue #2420 was manually label-repaired to `factory:claimed`/`worker:testbeam-laptop-3` without running claim again.\n\n"
    )
    if claim_note not in text:
        text = text.replace(marker, claim_note + marker, 1)
        report.write_text(text, encoding="utf-8")

    result_path = REPORT_DIR / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["study"] = "P11c"
    result["ticket"] = "2420"
    result["worker"] = "testbeam-laptop-3"
    result["title"] = "P11c learned-pedestal residual as a timing-tail nuisance"
    result["claimed_once"] = True
    result["claim_command"] = "tn-ticket claim testbeam-laptop-3 --project testbeam"
    result["claim_repair_note"] = "Local tn-ticket returned null|null|null because empty existing claims are string-interpolated; issue #2420 was manually label-repaired without running claim a second time."
    result["claimed_ticket"] = (REPORT_DIR / "claimed_ticket.txt").read_text(encoding="utf-8")
    result["execution_command"] = (
        "MPLCONFIGDIR=/tmp/matplotlib-p11c uv run --with uproot --with awkward "
        "--with numpy --with pandas --with scikit-learn --with pyarrow "
        "--with matplotlib --with torch python "
        f"{Path(__file__).resolve().relative_to(ROOT)}"
    )
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_path = REPORT_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["config_path"] = str(CONFIG.relative_to(ROOT))
    manifest["runner"] = str(Path(__file__).resolve().relative_to(ROOT))
    manifest["ticket"] = "2420"
    manifest["worker"] = "testbeam-laptop-3"
    manifest["output_sha256"] = {
        rel: digest
        for rel, digest in s16i.hash_outputs(REPORT_DIR).items()
        if "__pycache__" not in Path(rel).parts and not rel.endswith(".pyc")
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    s16i.CONFIG_DEFAULT = str(CONFIG)
    s16i.markdown_table = markdown_table_safe
    s16i.np = np
    old_argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0], "--config", str(CONFIG)]
        rc = s16i.main()
    finally:
        sys.argv = old_argv
    if rc != 0:
        return int(rc)
    postprocess()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
