#!/usr/bin/env python3
"""
generate_publication_figures.py
===============================
Thin driver that generates the CCB Test-Beam publication figures from the
**result registry** (``paper/figures.yaml``) via
:func:`tools.figure_registry.builder.build`.

Migration (2026-07-20)
----------------------
This script used to embed every headline value as a Python constant
(``STAVE_TIMING``, ``MC_VS_DATA``, ``PID_DATA``, ``STOPPING``, ``SYST_BUDGET``,
``PCA_AE``, the inline ``d_frac_*`` arrays, ...) and mixed illustrative
schematics with quantitative figures -- flagged by KNOWN_CODE_DEFECTS.md and v2
governance finding #10.

It now contains **no hard-coded headline numbers**. Every quantitative figure is
built by the registry backend, which reads its central value + uncertainty
*only* from a validated result JSON / source table (never a literal) and FAILS
the build when an expected result or uncertainty is missing. Illustrative
schematics are marked ``kind: illustrative`` in the registry and rendered into a
separate ``illustrative/`` sub-directory, clearly labelled and never counted
among the quantitative figures.

See ``scripts/PUBFIG_MIGRATION.md`` for the constant -> registry-entry mapping
and how to promote an ``EXTERNAL_BLOCKER`` entry to ``VALIDATED`` once its result
file exists.

Usage
-----
    python scripts/generate_publication_figures.py \
        --registry paper/figures.yaml --out paper/figures
    # include PRELIMINARY figures:
    python scripts/generate_publication_figures.py --allow-preliminary
    # fail (nonzero) unless every quantitative figure is built:
    python scripts/generate_publication_figures.py --strict
    python scripts/generate_publication_figures.py --help

Exit codes
----------
* non-strict (default): exit 0 while quantitative results are compute-blocked
  (they are reported BLOCKED, an honest default). A genuine hard failure -- a
  missing result / uncertainty on a build-eligible entry, a source-table sha256
  mismatch, or a malformed registry -- still exits nonzero.
* ``--strict``: exit nonzero if ANY quantitative entry is not built (any FAIL,
  or any BLOCKED quantitative entry).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# The repo root holds the top-level ``tools`` namespace package. Make it
# importable regardless of how this script is launched (no analyst abs paths).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.figure_registry import (  # noqa: E402  (after sys.path bootstrap)
    FigureRegistryError,
    build,
)

DEFAULT_REGISTRY = "paper/figures.yaml"
DEFAULT_OUT = "paper/figures"


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="generate_publication_figures.py",
        description=(
            "Generate CCB test-beam publication figures from the result "
            "registry. Every quantitative figure is driven only by values "
            "read from a validated result JSON / source table -- never a "
            "hand-entered constant. Illustrative schematics are kept separate."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--registry",
        default=DEFAULT_REGISTRY,
        help="path to the YAML figure registry",
    )
    p.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="output directory for figures + build_report.json",
    )
    p.add_argument(
        "--allow-preliminary",
        action="store_true",
        help="include PRELIMINARY figures in the paper build (default: blocked)",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help=(
            "exit nonzero unless EVERY quantitative entry is built "
            "(any FAIL or any BLOCKED quantitative entry fails the run)"
        ),
    )
    return p


def _load_report(out_dir: Path) -> dict | None:
    """Best-effort read of the build report the builder writes to ``out_dir``."""
    report_path = out_dir / "build_report.json"
    if not report_path.exists():
        return None
    try:
        with open(report_path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None


def _print_summary(report: dict) -> None:
    s = report.get("summary", {})
    print(
        "publication figures: "
        f"{s.get('pass', 0)} built "
        f"({s.get('quantitative_figures', 0)} quantitative, "
        f"{s.get('illustrative_figures', 0)} illustrative), "
        f"{s.get('blocked', 0)} blocked, {s.get('fail', 0)} failed."
    )
    for rec in report.get("entries", []):
        disp = rec.get("disposition")
        if disp in ("BLOCKED", "FAIL"):
            print(f"  - {rec.get('id')}: {disp} -- {rec.get('reason', '')}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    out_dir = Path(args.out)

    try:
        report = build(
            args.registry,
            out_dir,
            paper_only=True,
            allow_preliminary=args.allow_preliminary,
        )
    except FigureRegistryError as exc:
        # A hard failure (missing result/uncertainty on a build entry, sha256
        # mismatch, malformed registry). The builder wrote whatever report it
        # could before raising -- surface it, then exit nonzero regardless of
        # --strict, because this is a real defect, not a compute block.
        print(f"FigureRegistryError: {exc}", file=sys.stderr)
        report = _load_report(out_dir)
        if report is not None:
            _print_summary(report)
        print(f"Report: {out_dir / 'build_report.json'}")
        return 1

    _print_summary(report)
    print(f"Report: {out_dir / 'build_report.json'}")

    if args.strict:
        blocked_quant = [
            rec
            for rec in report.get("entries", [])
            if rec.get("disposition") == "BLOCKED" and rec.get("quantitative")
        ]
        n_fail = report.get("summary", {}).get("fail", 0)
        if blocked_quant or n_fail:
            ids = ", ".join(rec["id"] for rec in blocked_quant) or "(none)"
            print(
                "--strict: not every quantitative figure was built "
                f"({len(blocked_quant)} blocked: {ids}; {n_fail} failed).",
                file=sys.stderr,
            )
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
