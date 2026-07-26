# Active Task

- **Task ID:** `AUD-FIG-003`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T110505Z`
- **Initial remote main SHA:** `cc0f39560f7e98b1c1c130748d268103ea08754a`
- **Scope:** audit quantitative paper-figure PNG publication for target preservation, atomic replacement, cleanup, and controlled failure semantics.
- **Policy:** `QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE`.
- **Finding:** current `_emit_quantitative` passes the final PNG path directly to `savefig` and closes the figure only after rendering returns; an injected partial-write failure destroyed a prior validated target.
- **Delivered:** fail-closed AST/behavioral auditor, seven focused tests, machine-readable JSON, SVG evidence, Markdown report, and immutable archive.
- **Validation:** compilation passed; focused pytest `7 passed in 1.38s`; current-like exact function excerpt `FLAWED` with three findings; corrected fixture `VALIDATED`; prior-target preservation and cleanup controls passed; JSON and SVG parsed.
- **Acceptance:** audit tooling/evidence `VALIDATED`; production quantitative render path `FLAWED / PARTIAL` and unchanged.
- **Scientific boundary:** no figure value or detector-performance claim authorized or changed.
- **Next action:** render to a same-directory temporary PNG with explicit format, close the figure in `finally`, atomically publish retained bytes, and add direct production-path failure regressions.
- **Status:** `PARTIAL`
