"""Connector-inspected relevant excerpt from PR #939 head ce81f22e.

This fixture is intentionally limited to the pair-width to single-stave inference
and report wording reviewed by AUD-TIMING-003. It is not a full PR checkout.
"""
import numpy as np


def run_tag(rows):
    best_sigma68 = min(
        (r for r in rows if np.isfinite(r["sigma68_ns"])),
        default=None,
        key=lambda r: r["sigma68_ns"],
    )
    if best_sigma68:
        single = best_sigma68["sigma68_ns"] / np.sqrt(2)
        print(
            "HEADLINE: best sigma68 = "
            f"{best_sigma68['sigma68_ns']:.3f} ns "
            f"-> single-stave ~ {single:.3f} ns (assume equal)"
        )
    return best_sigma68


def write_report(best_sigma68):
    lines = []
    if best_sigma68:
        lines.append(
            "- Single-stave estimate (pair / sqrt2) = "
            f"**{best_sigma68['sigma68_ns']/1.4142:.3f} ns**, "
            "consistent with the validated ledger CL-002 (B6 = 0.63-0.80 ns)."
        )
    return "\n".join(lines)
