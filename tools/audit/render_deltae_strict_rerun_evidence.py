#!/usr/bin/env python3
"""Render deterministic software/provenance evidence for the strict ΔE-E rerun."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["svg.fonttype"] = "none"
import matplotlib.pyplot as plt


POLICY = "DELTAE_BRIDGE_CONTENT_ADDRESSED_TRANSACTIONAL_RERUN"


def render(input_json: Path, output_svg: Path) -> None:
    payload = json.loads(input_json.read_text(encoding="utf-8"))
    validation = payload["validation"]
    synthetic = payload["synthetic_bundle"]
    checks = validation["checks"]

    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    ax.text(
        0.5,
        0.95,
        "A-002 ΔE-E strict rerun: provenance and publication gate",
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
    )
    ax.text(
        0.5,
        0.905,
        "Synthetic software validation — not detector data or a stopping/PID result",
        ha="center",
        va="top",
        fontsize=10,
    )

    old_lines = [
        "Former entry point",
        "• hard-coded input/output paths",
        "• path-based pandas read; no exact input digest",
        "• direct JSON / CSV / PNG writes",
        "• no command, runtime, or code-byte identity",
        "• no transactional bundle rollback",
    ]
    new_lines = [
        "Strict runner",
        "• expected input SHA-256 + before/after identity",
        "• explicit amplitude column / convention / polarity",
        "• clean expected repository commit + script hashes",
        "• unique composite keys + finite output validation",
        "• staged-directory publication with rollback",
    ]
    ax.text(
        0.05,
        0.79,
        "\n".join(old_lines),
        ha="left",
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.6", "facecolor": "#f5f5f5"},
    )
    ax.text(
        0.53,
        0.79,
        "\n".join(new_lines),
        ha="left",
        va="top",
        fontsize=10,
        bbox={"boxstyle": "round,pad=0.6", "facecolor": "#f5f5f5"},
    )

    result_lines = [
        f"Focused pytest: {validation['pytest_result']}",
        f"py_compile: {checks['py_compile']}",
        f"JSON parse: {checks['json_parse']}",
        f"SVG XML parse: {checks['svg_xml_parse']}",
        f"Maximum changed Python line: {checks['max_python_line_length']} chars",
        f"Synthetic physical events: {synthetic['event_rows']}",
        f"Unique composite keys: {synthetic['unique_composite_keys']}",
        f"Stopping-bin total: {synthetic['stopping_distribution_total']}",
    ]
    ax.text(
        0.05,
        0.43,
        "Validated checks\n" + "\n".join(f"• {line}" for line in result_lines),
        ha="left",
        va="top",
        fontsize=10,
    )

    rejection_lines = [
        "input hash mismatch",
        "repository commit mismatch",
        "input/output containment alias",
        "implicit overwrite",
        "injected publication failure",
        "input replacement during processing",
        "duplicate event keys",
        "nonfinite output values",
    ]
    ax.text(
        0.53,
        0.43,
        "Fail-closed regressions\n"
        + "\n".join(f"• {item}" for item in rejection_lines),
        ha="left",
        va="top",
        fontsize=10,
    )

    ax.text(
        0.5,
        0.075,
        f"policy={POLICY}\nstatus={payload['status']} — real A-002 rerun remains blocked",
        ha="center",
        va="bottom",
        fontsize=9,
    )
    fig.tight_layout()
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_svg, format="svg", metadata={"Title": POLICY})
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
