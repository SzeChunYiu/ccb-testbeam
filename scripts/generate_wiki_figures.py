#!/usr/bin/env python3
"""Compatibility entry point for the canonical paper-grade wiki figures.

The former implementation mixed hand-entered values, mock random waveforms and
150-dpi dashboard styling.  It is intentionally replaced by the evidence-bound
``ccb_plotting.wiki_figures`` pipeline.
"""

from __future__ import annotations

from generate_paper_grade_wiki_figures import main

if __name__ == "__main__":
    raise SystemExit(main())
