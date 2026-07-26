# Active Task

- **Task ID:** `AUD-FIG-002`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T092835Z`
- **Initial remote main SHA:** `770fa6e8ba305b29c539e64f1f151c4cf5dc1053`
- **Scope:** audit whether the paper-figure builder binds rendered/copied artifacts and recorded provenance to one exact byte snapshot.
- **Policy:** `FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`.
- **Finding:** current result JSON and source-artifact paths can be re-read after figure/copy creation, so recorded hashes and sizes can describe replacement bytes rather than the bytes used.
- **Delivered:** fail-closed AST/behavioral audit; five focused regressions; machine-readable JSON; synthetic SVG evidence; audit report; immutable archive.
- **Validation:** compilation passed; focused pytest `5 passed in 0.10s`; current-like contract `FLAWED` with three findings; corrected single-snapshot fixture `VALIDATED`; JSON and SVG parsed; atomic publication failure preserved the prior output.
- **Acceptance:** focused audit gate `VALIDATED`; production builder remains `PARTIAL / FLAWED` pending single-read exact-byte remediation and direct builder regressions.
- **Status:** `PARTIAL`
