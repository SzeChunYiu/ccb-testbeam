# Active Task

- **Task ID:** AUD-MC-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T040311Z
- **Initial remote main SHA:** `2868b1a7aaa15cd6a03970c2385c2b7ab53c5598`
- **Validated implementation/evidence head:** `7506eecfc54f550f2583bad24d0c85de383bbbde`
- **Scope completed:** added a fail-closed, content-addressed rerun entry point for issue #879/#880/#887 with strict event-weight estimators and direction-explicit issue #880 reporting.
- **Repository evidence:** historical producer blob `bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`; retained result blob `37d69e2c697a7ce7c9e1eff9aeff48539551d922`; open issue #880; preceding `AUD-MC-002` audit.
- **Correction:** exactly one finite nonnegative weight per event; no unit-weight coercion, unweighted estimator fallback, or epsilon denominator; both comparison directions name denominators; ROOT SHA-256 must match before/after read; clean git/script/command/runtime provenance and protected atomic JSON are recorded.
- **Validation:** focused py_compile passed; focused pytest returned `17 passed in 0.04s`; retained directional arithmetic reproduced; JSON and SVG parsed; changed Python lines are at most 100 characters; committed source blobs were re-read from `main`; no status checks are attached to the implementation head.
- **Scientific boundary:** exact one-million-event ROOT bytes were unavailable; no production rerun, weighted uncertainty, tail-stability result, first-primary weight-definition proof, or data/MC closure is claimed.
- **Status:** PARTIAL — validated code and evidence are on `main`; the retained study remains `FLAWED` until a clean content-addressed production rerun and scientific closure are complete.
