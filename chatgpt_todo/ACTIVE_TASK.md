# Active Task

- **Task ID:** AUD-MC-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T021422Z
- **Initial remote main SHA:** `f01b16fba39bcd21bb57a10638d36dcfe521b01f`
- **Scope:** harden `tools/audit/audit_mc_weight_usage.py` so effective-sample-size reports cannot silently discard invalid weights, flatten non-event-aligned arrays, select an ambiguous branch, or overwrite the exact ROOT input.
- **Repository evidence:** exact former blob `9b2375b98fd76784ce3fb961e4dcdbf169f7495e` filtered nonfinite values, reshaped arbitrary arrays, selected the first recognized branch when several existed, omitted input-byte provenance, and wrote JSON directly to the requested path without an input/output alias gate.
- **Files:** strict validator v2.0.0; MC weight policy v2; focused tests; deterministic renderer; validation JSON/SVG/audit; immutable archive; latest handoff.
- **Validation:** exact former-source negative controls reproduced false `OK` results for a NaN-containing vector, simultaneous `PrimaryWeight`/`EventWeight`, and a 2×2 array, plus destructive input/output aliasing with exit zero; corrected compilation passed; focused pytest returned `8 passed in 0.04s`; JSON and SVG parsed; changed Python lines are at most 100 characters; committed script/test/renderer/contract blobs match validated bytes.
- **Scientific boundary:** a valid weight vector and ESS report do not prove downstream analyses consume the weights or close against data. The exact production ROOT file, weighted downstream reruns, uncertainty propagation, and data/MC closure remain external/compute blockers.
- **Status:** COMPLETE — strict event-aligned weight validation, reproducible evidence, and policy correction delivered directly to remote `main`.
