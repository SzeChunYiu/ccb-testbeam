# Active Task

- **Task ID:** `AUD-FIG-005`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T170400Z`
- **Initial remote main SHA:** `03851ff128a5a351f39c7754e47ac35fe80e0fa0`
- **Scope:** bind every paper-figure `build_report.json` to the exact duplicate-key-safe registry byte snapshot used for parsing, and convert registry format failures into controlled CLI diagnostics.
- **Policy:** `FIGURE_BUILD_REPORT_MUST_BIND_TO_EXACT_REGISTRY_SNAPSHOT`.
- **Delivered:** builder snapshot integration; five-field registry provenance; controlled format-error boundary; six focused regressions; JSON/SVG/Markdown evidence; immutable archive.
- **Validation:** combined duplicate-key and report-provenance suites `12 passed in 0.28s`; exact remote builder/test blobs match locally validated bytes; replacement-after-read, duplicate-key, invalid-UTF8, structural-invalid, and one-read controls passed; JSON/SVG parsing passed; maximum implementation/test Python line length 93.
- **Implementation commits:** `db1a05a5ce9003cd45e10df4f247c55733a06dc2`, `bd81bce0fa0714f7473ae946db221e3bbdb918a5`.
- **Evidence through:** `d3b126961d32291f3756dfe3a1f4614e8f15815c`.
- **Acceptance:** focused software/provenance remediation `VALIDATED / COMPLETE`.
- **Scientific boundary:** no registry entry, paper figure, central value, uncertainty, calibration, timing, PID, stopping profile, pile-up rate, or detector-performance claim was revalidated.
- **Unrun checks:** repository-wide pytest/ruff, complete shipped-registry build, paper build, link inventory, and GitHub Actions.
- **Coordination limitation:** byte-safe append was unavailable, so `SESSION_LOG.md` and long aggregate matrices were not partially reconstructed; the immutable archive preserves the append-equivalent record.
- **Status:** `COMPLETE`
