# Active Task

- **Task ID:** AUD-MC-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T040311Z
- **Initial remote main SHA:** `2868b1a7aaa15cd6a03970c2385c2b7ab53c5598`
- **Scope:** deliver a fail-closed, content-addressed replacement entry point for the issue #879/#880/#887 MC study, with strict event-weight estimators and direction-explicit issue #880 reporting.
- **Repository evidence:** historical producer blob `bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`; retained result blob `37d69e2c697a7ce7c9e1eff9aeff48539551d922`; open issue #880; preceding `AUD-MC-002` audit.
- **Confirmed defects being remediated:** nonfinite unit-weight coercion; unweighted estimator fallbacks; epsilon relative denominator; ambiguous bias direction; missing ROOT/producer content identity.
- **Files:** `scripts/single_stave/strict_event_weights.py`, `scripts/single_stave/issues879_880_887_mc_study_strict.py`, focused tests, validation JSON/SVG/Markdown, rerun instructions, archive, handoff, and backlog state.
- **Validation plan:** py_compile; focused pytest; exact retained arithmetic reconstruction; JSON parse; SVG XML parse; line-length gate; committed-blob verification; remote-main history and status check.
- **Scientific boundary:** exact one-million-event ROOT bytes are unavailable in this runtime; no production rerun, weighted uncertainty, tail-stability result, or data/MC closure will be claimed.
- **Status:** ACTIVE
