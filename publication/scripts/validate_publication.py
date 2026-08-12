#!/usr/bin/env python3
"""Fail-closed structural checks for the CCB publication package."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHAPTERS = [
    "00_abstract.tex",
    "01_introduction.tex",
    "02_ccb_configuration.tex",
    "03_stave_readout.tex",
    "04_simulation.tex",
    "05_data_taking.tex",
    "06_timing.tex",
    "07_deltae_e.tex",
    "08_optical_response.tex",
    "09_energy_reconstruction.tex",
    "10_discussion.tex",
    "11_conclusions.tex",
    "12_reproducibility.tex",
    "A_publication_status.tex",
    "B_evidence_paths.tex",
]
REQUIRED_DIRS = [
    "chapters",
    "figures/final",
    "figures/gated",
    "figures/model_diagnostics",
    "figures/illustrative",
    "figures/source_data",
    "scripts/gated",
    "scripts/utilities",
    "tables/final",
    "tables/gated",
    "data",
    "references",
    "source",
]


def fail(msg: str) -> None:
    print(f"PUBLICATION_STRUCTURE_FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    for rel in ("main.tex", "README.md", "STATUS.md", "build.sh", "Makefile"):
        if not (ROOT / rel).exists():
            fail(f"missing required file {rel}")
    for rel in REQUIRED_DIRS:
        if not (ROOT / rel).is_dir():
            fail(f"missing required directory {rel}")
    for name in EXPECTED_CHAPTERS:
        if not (ROOT / "chapters" / name).is_file():
            fail(f"missing chapter {name}")
    main_text = (ROOT / "main.tex").read_text(encoding="utf-8")
    for name in EXPECTED_CHAPTERS:
        stem = name.removesuffix(".tex")
        if f"chapters/{stem}" not in main_text:
            fail(f"main.tex does not input {name}")
    status = (ROOT / "STATUS.md").read_text(encoding="utf-8")
    if "NOT_SUBMISSION_READY" not in status:
        fail("STATUS.md lost fail-closed publication state")
    for path in (ROOT / "figures" / "final").iterdir():
        if path.name == "README.md":
            continue
        if "heldout" in path.name.lower() or "deltae" in path.name.lower():
            fail(f"currently gated central figure appears under figures/final: {path.name}")
    print("PUBLICATION_STRUCTURE_PASS")


if __name__ == "__main__":
    main()
