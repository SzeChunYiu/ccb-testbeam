# Active Task

- **Task ID:** AUD-WIKI-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T102230Z
- **Initial remote main SHA:** `74966884f40e6dbc8ac6243d4983eaa7dfb395ae`
- **Scope completed in this unit:** extended the root-WIKI claim gate from MV4/tau-only coverage to exact-width canonical bindings for Rmax, P04p duplicate readout, and P07e saturation recovery.
- **Confirmed defect:** validator v1.1.0 bound only `CL-007` and `CL-011`, so a source-faithful WIKI with a blocked-but-published Rmax and unsupported ML-win wording could return `VALIDATED`.
- **Implemented files:** upgraded `tools/audit/validate_wiki_claim_front_door.py` to v1.2.0; expanded focused tests; added Markdown, JSON, and SVG validation evidence.
- **Canonical bindings:** `CL-007`, `CL-010`, `CL-011`, `CL-012`, `CL-015`, and `CL-016`, each required to have exactly 43 columns before interpretation.
- **Measured current state:** an exact claim-bearing WIKI excerpt plus the exact current ledger returned `FLAWED` with 21 findings; all six required claim rows were exactly 43 columns.
- **Validation:** `py_compile` passed; focused pytest returned `10 passed in 0.04s`; JSON and SVG parsed; maximum changed Python line lengths are 91 and 98 characters; exact current ledger bytes matched Git blob `853d955f449268ec614ac61f33f243d30cf473e0`.
- **Evidence policy:** `WIKI_FRONT_DOOR_MUST_MATCH_EXACT_WIDTH_CANONICAL_CLAIMS`.
- **Required remediation:** withhold numerical Rmax pending S-STAT-003; retain 3.0448717948717947 MHz only as superseded history; replace combined/domain ML-win wording with separate GATED P04p/P07e statements; authorize no production duplicate-readout model or saturation correction.
- **Scientific boundary:** no detector data, simulation, fit, Rmax calculation, uncertainty interval, model training, calibration, or detector-performance result was generated.
- **Remaining work:** rewrite the complete current `WIKI.md`, run validator v1.2.0 on the exact full WIKI and ledger, run broken-link checks, and require `VALIDATED` before closing `AUD-WIKI-001`.
- **Status:** PARTIAL; audit gate and evidence are VALIDATED, public root WIKI remediation remains open.
