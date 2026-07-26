# Active Task

- **Task ID:** `AUD-FIG-004`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T160640Z`
- **Initial remote main SHA:** `cd4c299dbd67e285950a69610e4b27caed4413e1`
- **Scope:** prevent duplicate YAML figure IDs or nested registry fields from silently replacing earlier scientific evidence before validation and paper-figure build decisions.
- **Policy:** `FIGURE_REGISTRY_YAML_KEYS_MUST_BE_UNIQUE_AT_EVERY_MAPPING_DEPTH`.
- **Delivered:** duplicate-key-safe strict-UTF8 single-read registry loader; content-addressed `RegistrySnapshot`; package exports; focused regressions; deterministic JSON/SVG evidence; audit report; immutable archive; handoff.
- **Validation:** `6 passed in 0.07s`; final rerun `6 passed in 0.04s`; 2/2 ambiguous YAML controls rejected; invalid UTF-8 and replacement-after-read controls passed; JSON/SVG parsing passed; maximum changed Python line length 94.
- **Implementation commits:** `9ed2d099c2120be8d3ddf96885812591e999b88a`, `dddab6968870f3f50c467fe93f375b2a6e697338`, `bba1b581e490e852abe13a890cffc59ca6cfa158`.
- **Evidence through:** `4adbd8139f0b40718f9b3df614dc9ecb27e5cab1`.
- **Acceptance:** focused software/schema remediation `VALIDATED / COMPLETE`.
- **Scientific boundary:** no paper figure, central value, uncertainty, calibration, timing, PID, stopping profile, pile-up rate, or detector-performance claim was regenerated or authorized.
- **Unrun checks:** repository-wide pytest/ruff, complete shipped-registry build, paper build, link inventory, and GitHub Actions.
- **Coordination limitation:** byte-safe append was unavailable, so `SESSION_LOG.md` and long aggregate matrices were not partially reconstructed; the immutable archive preserves the append-equivalent record.
- **Status:** `COMPLETE`
