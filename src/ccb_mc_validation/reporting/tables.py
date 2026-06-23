"""Markdown table helpers for study metrics."""

from __future__ import annotations

import math
from typing import Any, Mapping


def metrics_to_markdown_table(metrics: Mapping[str, Any]) -> str:
    """Render scalar metrics as a GitHub-flavored markdown table."""
    if not metrics:
        return "_No metrics recorded._\n"

    lines = ["| metric | value |", "| --- | --- |"]
    for key in sorted(metrics):
        value = metrics[key]
        if isinstance(value, float):
            if math.isnan(value):
                rendered = "NaN"
            else:
                rendered = f"{value:.6g}"
        else:
            rendered = str(value)
        lines.append(f"| `{key}` | {rendered} |")
    return "\n".join(lines) + "\n"
