# Active Task

- **Task ID:** AUD-DOC-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T010711Z
- **Initial remote main SHA:** `bf46fe4ef69a5fdf24d39f264d90218b0335f491`
- **Scope:** repair and harden the repository Markdown link checker so invalid UTF-8, missing local targets, and repository-root escapes produce deterministic fail-closed findings instead of interpreter crashes or false passes.
- **Repository evidence:** former `scripts/broken_link_checker.py` blob `0cc64c1e54291af0eed70ce3d4cfada976250e75` used implicit text decoding and referenced undefined variable `boken`; open PR #883 contains a partial stale fix and was not merged or modified.
- **Files:** `scripts/broken_link_checker.py`; `tests/test_broken_link_checker.py`; deterministic evidence renderer; validation JSON/SVG/audit; immutable archive; latest handoff.
- **Validation:** exact former source reproduced `NameError` after a missing-link finding and uncaught `UnicodeDecodeError` at byte 6; corrected compilation passed; focused pytest returned `6 passed in 2.55s`; valid, missing, invalid-UTF-8, root-escape, percent-encoded, and atomic-JSON cases passed; JSON and SVG parsed; changed Python lines are at most 100 characters; committed script/test blobs match validated bytes.
- **Scientific boundary:** documentation integrity tooling cannot validate detector data, simulations, numerical physics, or external URLs; link presence alone does not establish scientific correctness. Reference-style links and heading-anchor validation remain outside this unit.
- **Status:** COMPLETE — fail-closed Markdown link audit and reproducible evidence delivered directly to remote `main`.
