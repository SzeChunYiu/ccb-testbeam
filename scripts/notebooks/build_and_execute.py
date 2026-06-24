#!/usr/bin/env python3
"""Build, sync, and execute MC validation Jupyter notebooks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

NOTEBOOK_SRC = ROOT / "notebooks" / "source"
NOTEBOOK_OUT = ROOT / "notebooks"


def _run_dir(run_id: str) -> Path:
    return ROOT / "reports/mc_validation/runs" / run_id


def sync_notebooks() -> list[Path]:
    """Copy .py percent-format sources to notebooks/ as .ipynb stubs via jupytext if available."""
    synced: list[Path] = []
    NOTEBOOK_OUT.mkdir(parents=True, exist_ok=True)
    for src in sorted(NOTEBOOK_SRC.glob("*.py")):
        ipynb = NOTEBOOK_OUT / f"{src.stem}.ipynb"
        try:
            subprocess.run(
                ["jupytext", "--to", "ipynb", str(src), "-o", str(ipynb)],
                check=True,
                capture_output=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            # Minimal ipynb without jupytext
            nb = {
                "nbformat": 4,
                "nbformat_minor": 5,
                "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"}},
                "cells": [
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": [f"# {src.stem}\n", "\n", "Execute source: notebooks/source/\n"],
                    },
                    {
                        "cell_type": "code",
                        "metadata": {},
                        "source": [f"%run {src.relative_to(ROOT)}\n"],
                        "outputs": [],
                        "execution_count": None,
                    },
                ],
            }
            ipynb.write_text(json.dumps(nb, indent=2) + "\n", encoding="utf-8")
        synced.append(ipynb)
    return synced


def execute_notebook(ipynb: Path, run_id: str) -> int:
    out_dir = _run_dir(run_id) / "notebooks" / "executed"
    html_dir = _run_dir(run_id) / "notebooks" / "html"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_dir.mkdir(parents=True, exist_ok=True)
    executed = out_dir / ipynb.name
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "jupyter",
                "nbconvert",
                "--to",
                "notebook",
                "--execute",
                str(ipynb),
                "--output",
                str(executed),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "jupyter",
                "nbconvert",
                "--to",
                "html",
                str(executed),
                "--output-dir",
                str(html_dir),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        return 0
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        # Fallback: run source .py directly
        src = NOTEBOOK_SRC / f"{ipynb.stem}.py"
        if src.is_file():
            r = subprocess.run([sys.executable, str(src), "--run-id", run_id], cwd=ROOT)
            return r.returncode
        print(exc, file=sys.stderr)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", default="all")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--export-html", action="store_true")
    args = ap.parse_args()

    synced = sync_notebooks()
    if not args.execute:
        print(f"synced {len(synced)} notebooks")
        return 0

    targets = synced if args.target == "all" else [NOTEBOOK_OUT / f"{args.target}.ipynb"]
    rc = 0
    for nb in targets:
        if nb.is_file():
            rc = max(rc, execute_notebook(nb, args.run_id))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
