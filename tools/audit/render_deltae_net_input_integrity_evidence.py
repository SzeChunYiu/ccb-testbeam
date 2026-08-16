#!/usr/bin/env python3
"""Render synthetic evidence for the ΔE-E net-amplitude input-integrity audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render(validation: Path, output: Path) -> None:
    payload = json.loads(validation.read_text(encoding="utf-8"))
    controls = payload["synthetic_controls"]
    labels = ["Finite 250", "NaN", "+infinity"]
    accepted = [
        0 if controls["finite"]["rejected"] else 1,
        0 if controls["nan"]["rejected"] else 1,
        0 if controls["positive_infinity"]["rejected"] else 1,
    ]
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    bars = ax.bar(labels, accepted)
    ax.set_ylim(0, 1.25)
    ax.set_ylabel("Bridge accepted synthetic event (1=yes)")
    ax.set_title("ΔE-E net-amplitude input-integrity remediation")
    ax.set_yticks([0, 1], labels=["rejected", "accepted"])
    for bar, value in zip(bars, accepted, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.04, str(value), ha="center")
    note = (
        "Synthetic software evidence only. Finite input is retained; NaN and +infinity "
        "are rejected before event/stave aggregation and missing-layer zero filling."
    )
    fig.text(0.01, 0.01, note, fontsize=7, wrap=True)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, format="svg", metadata={"Description": note})
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    render(args.validation, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
