"""Fast syntax gates for the build-receipt integration path."""
from __future__ import annotations

import py_compile
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_build_receipt_python_compiles() -> None:
    py_compile.compile(
        str(ROOT / "scripts" / "single_stave" / "sipm_build_receipt.py"),
        doraise=True,
    )


def test_campaign_launchers_are_valid_bash() -> None:
    for relative in (
        "geant4/single_stave/slurm/run_sensitivity_campaign.sh",
        "geant4/single_stave/slurm/submit_systematic.sh",
    ):
        subprocess.run(
            ["bash", "-n", str(ROOT / relative)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
