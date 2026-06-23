"""Report generation, figure registry, and validation diagnostics."""

from __future__ import annotations

from ccb_mc_validation.reporting.diagnostics import lint_report
from ccb_mc_validation.reporting.registry import ResultRegistry
from ccb_mc_validation.reporting.renderer import render_mv_report

__all__ = ["ResultRegistry", "lint_report", "render_mv_report"]
