# Active Task

- **Task ID:** `AUD-REP-002`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T150519Z`
- **Initial remote main SHA:** `f30ff1100592e06396598ebf6975afa88e84444f`
- **Scope:** remediate Cluster E canonical-front-door provenance so every retained input byte snapshot is exactly bound to the declared base-commit tree.
- **Policy:** `INPUT_BYTES_MUST_MATCH_BASE_COMMIT_BLOBS`.
- **Confirmed defect:** the former producer parsed one path snapshot but later hashed the live path and never compared the retained bytes with `base_commit:path`; replacement or dirty worktree bytes could therefore be attributed to a clean base commit.
- **Delivered:** retained-byte Git-blob calculation, per-input commit-tree equality gate, schema-3 provenance, validator v2.1.0, eleven focused regressions, deterministic controls, JSON, SVG, Markdown audit, and immutable archive.
- **Validation:** `python -m py_compile` passed; focused pytest returned `11 passed in 0.20s`; evidence renderer returned `VALIDATED` with zero findings; JSON and SVG parsed; changed Python lines are at most 100 characters.
- **Acceptance:** focused software/provenance remediation `VALIDATED / COMPLETE`.
- **Scientific boundary:** no calibration, stopping-profile closure, C12 identity, data/MC transfer, uncertainty, or detector-performance quantity was recalculated or validated.
- **Remaining execution:** regenerate and validate the public Cluster E bundle under schema 3 from a clean immutable checkout before calling that generation independently reproduced.
- **Status:** `COMPLETE`
