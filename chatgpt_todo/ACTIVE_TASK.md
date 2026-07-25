# Active Task

- **Task ID:** AUD-DOC-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T010711Z
- **Initial remote main SHA:** `bf46fe4ef69a5fdf24d39f264d90218b0335f491`
- **Scope:** repair and harden the repository Markdown link checker so invalid UTF-8, missing local targets, and repository-root escapes produce deterministic fail-closed findings instead of interpreter crashes or false passes.
- **Repository evidence:** current `scripts/broken_link_checker.py` blob `0cc64c1e54291af0eed70ce3d4cfada976250e75` uses implicit text decoding and references undefined variable `boken`; open PR #883 proposes a partial stale fix but its Chapter 9 patch no longer applies to current `main`.
- **Files:** `scripts/broken_link_checker.py`; focused tests; validation JSON/SVG/audit; relevant `chatgpt_todo/` ledgers, immutable archive, session log, and handoff.
- **Validation plan:** reproduce both former crashes from exact current source; compile changed Python; run focused pytest; validate missing-link, invalid-UTF-8, root-escape, percent-encoding, valid-link, and atomic JSON cases; parse JSON/SVG; enforce 100-character Python lines; confirm remote `main` contains the delivery commit.
- **Scientific boundary:** documentation integrity tooling cannot validate detector data, simulations, numerical physics, or external URLs; link presence alone does not establish scientific correctness.
- **Status:** ACTIVE.
