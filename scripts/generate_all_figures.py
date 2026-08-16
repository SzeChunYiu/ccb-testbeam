#!/usr/bin/env python3
"""Compatibility entry point for the canonical publication figure set.

Historical study artefacts remain available for audit, but public wiki/paper
figures are generated only by the evidence-bound paper-grade pipeline.
"""

from __future__ import annotations

from generate_paper_grade_wiki_figures import main

if __name__ == "__main__":
    raise SystemExit(main())
