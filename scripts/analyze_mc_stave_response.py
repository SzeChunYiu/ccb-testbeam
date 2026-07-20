#!/usr/bin/env python3
"""Single-stave MC response analysis (issue #796) — CLI front end.

REPLACES the previous stub, which only ran ``df.describe()`` on hard-coded
LUNARC paths (see ``audit/KNOWN_CODE_DEFECTS.md``). The real analysis now lives
in ``scripts/single_stave/analyze_single_stave.py``: it accepts input paths as
arguments, discovers the ntuple schema, validates the photon-count inequality
(generated >= end-arrival >= detected), writes normalized event + summary
tables, and produces the deposited-energy vs photon / PE plot set with a
``result.json`` and ``manifest.json``.

This thin wrapper preserves the historical entry-point name and forwards to the
maintained analyzer so no caller breaks, while removing the hard-coded paths and
the ``describe()``-only behaviour.

Examples
--------
    # Analyze a ROOT/parquet/CSV single-stave ntuple:
    python scripts/analyze_mc_stave_response.py \
        --input out/stave_p100.root --output reports/stave_p100 --bins 12

    # Offline determinism check on a synthetic fixture:
    python scripts/single_stave/make_single_stave_fixture.py --output /tmp/f.csv --n 2000
    python scripts/analyze_mc_stave_response.py --input /tmp/f.csv --output /tmp/f_report
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_ANALYZER = (
    Path(__file__).resolve().parent / "single_stave" / "analyze_single_stave.py"
)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not _ANALYZER.exists():
        sys.stderr.write(
            f"error: analyzer not found at {_ANALYZER}\n"
            "The single-stave analysis toolchain lives in scripts/single_stave/.\n"
        )
        return 2
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(__doc__ or "")
        sys.stdout.write(
            "\nThis command forwards all arguments to:\n"
            f"  {_ANALYZER}\nRun it with --help for the full option list:\n"
            f"  python {_ANALYZER} --help\n"
        )
        return 0
    # Forward argv verbatim to the maintained analyzer.
    sys.argv = [str(_ANALYZER)] + argv
    runpy.run_path(str(_ANALYZER), run_name="__main__")
    return 0


if __name__ == "__main__":
    sys.exit(main())
