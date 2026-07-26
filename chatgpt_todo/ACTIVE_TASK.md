# Active Task

- **Task ID:** `AUD-FIG-006`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T180117Z`
- **Initial remote main SHA:** `8acfc727a1479ff5b616042e65743b0652900c25`
- **Scope:** determine whether the paper-figure builder can leave older managed artifacts after an entry becomes BLOCKED, QUARANTINED, fails, or is removed from the registry.
- **Policy:** `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`.
- **Repository source inspected:** `tools/figure_registry/builder.py` blob `39dcd3b13d3886c43f3e9111291d420f86cc7c85`, especially `_process_entry` and `build`.
- **Finding:** current production contract is `FLAWED`; it has no entry-output cleanup, no failure-path cleanup, and no removed-ID reconciliation.
- **Deterministic control:** two prior managed files remain in each BLOCKED, failed, and removed-entry scenario; the corrected cleanup model leaves zero.
- **Delivered:** fail-closed AST auditor, six regressions, connector-inspected source fixture, machine-readable JSON, SVG evidence, Markdown audit, and immutable archive.
- **Validation:** `python -m py_compile` passed; focused pytest `6 passed in 0.05s`; current-like fixture `FLAWED` with four findings; corrected fixture `VALIDATED` with zero findings; invalid UTF-8, alias rejection, atomic JSON failure preservation, JSON parse, and SVG parse passed.
- **Evidence commits:** `9e01ccea849e1a8d731a8a302785e8fdd1e220a5`, `6b88476c722d1bd88bc619c373540e95796b4671`, `7974953481366cd82d5514c822b5d77c37065388`, `6bec3d85e56605e68bf66834112992182d342a3f`, `f6563409ffa6b2470135df21916b7e15d7a6cf11`, `3dac03cca404ef934d1e5db0e6f07bce684ae1db`, `b7c037e08a65753f7913186030c24026974ee1a5`, `c151045a8f09c1dc1cf29d27a95dec711d47e29d`.
- **Acceptance:** audit gate/evidence `VALIDATED / COMPLETE`; production builder remediation `PARTIAL / NOT IMPLEMENTED`.
- **Scientific boundary:** no paper figure or scientific result was regenerated or revalidated.
- **Unrun checks:** repository-wide pytest/ruff, complete shipped-registry build, paper build, link inventory, and GitHub Actions.
- **Coordination limitation:** `SESSION_LOG.md` and long aggregate matrices were not partially reconstructed because paged reads plus whole-file replacement could erase append-only provenance; the immutable archive is the append-equivalent record.
- **Next:** implement a complete managed-output inventory and staged fail-closed reconciliation, then run direct transition regressions and the complete registry/paper build.
- **Status:** `COMPLETE`
