"""CLI smoke tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def test_module_help_exits_zero() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "ccb_mc_validation", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "ccb-mc-validation" in result.stdout
