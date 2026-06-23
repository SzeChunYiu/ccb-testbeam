"""Mermaid diagram generators for MC validation documentation."""

from __future__ import annotations


def program_dag_mermaid() -> str:
    """Return a mermaid flowchart describing the MV0–MV9 validation program."""
    return """flowchart TD
    truth[Truth ROOT] --> mv0[MV0 Digitizer]
    mv0 --> mv1[MV1 PID]
    mv0 --> mv2[MV2 Energy/Range]
    mv0 --> mv3[MV3 Stopping Depth]
    mv0 --> mv4[MV4 Timing]
    mv0 --> mv5[MV5 Pile-up]
    mv0 --> mv6[MV6 Pulse Shape]
    mv0 --> mv7[MV7 Pedestal]
    mv0 --> mv8[MV8 Saturation]
    mv1 --> mv9[MV9 Synthesis]
    mv2 --> mv9
    mv3 --> mv9
    data[S00 Pulse Table] --> mv9
    mv9 --> report[REPORT.md + manifest.json]
"""
