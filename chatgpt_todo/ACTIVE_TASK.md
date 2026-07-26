# Active Task

- **Task ID:** `AUD-FIG-003-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T120901Z`
- **Initial remote main SHA:** `1c1e17958568d336b667304c651054ff88d03393`
- **Scope:** remediate quantitative paper-figure PNG publication for target preservation, atomic replacement, cleanup, and content-addressed provenance.
- **Policy:** `QUANTITATIVE_FIGURE_PUBLICATION_MUST_BE_ATOMIC_AND_FAILURE_SAFE`.
- **Finding:** the former production path rendered directly to the final PNG and could destroy prior validated evidence on a partial-write exception.
- **Delivered:** same-directory temporary PNG render with explicit format, retained-byte snapshot, atomic publication and final verification, figure cleanup in `finally`, four direct production regressions, JSON/SVG/Markdown evidence, and immutable archive.
- **Validation:** byte-exact committed builder and test blobs compiled; existing snapshot-remediation plus new publication-remediation suites returned `8 passed in 0.56s`; JSON and SVG parsed; changed Python lines are at most 100 characters.
- **Acceptance:** focused production remediation `VALIDATED / COMPLETE`; broad registry, paper, and repository integration remain unrun.
- **Scientific boundary:** no paper-figure value, uncertainty, timing result, calibration, PID result, stopping profile, pile-up rate, or detector-performance claim was authorized or changed.
- **Next action:** run the complete shipped figure registry and paper build in a full checkout, then review generated artifacts and any remaining registry/build failures before accepting broader paper integration.
- **Status:** `COMPLETE`
