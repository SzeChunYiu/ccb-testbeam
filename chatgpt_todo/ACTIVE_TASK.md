# Active Task

- **Task ID:** AUD-MC-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T021422Z
- **Initial remote main SHA:** `f01b16fba39bcd21bb57a10638d36dcfe521b01f`
- **Scope:** harden `tools/audit/audit_mc_weight_usage.py` so effective-sample-size reports cannot silently discard invalid weights, flatten non-event-aligned arrays, select an ambiguous branch, or overwrite the exact ROOT input.
- **Repository evidence:** exact former blob `9b2375b98fd76784ce3fb961e4dcdbf169f7495e` filters nonfinite values, reshapes arbitrary arrays, selects the first recognized branch when several exist, omits input-byte provenance, and writes JSON directly to the requested path without an input/output alias gate.
- **Files:** `tools/audit/audit_mc_weight_usage.py`; `docs/contracts/MC_WEIGHT_POLICY.md`; focused tests; deterministic validation JSON/SVG/audit; immutable archive; latest handoff.
- **Validation plan:** reconstruct the former blob exactly; demonstrate false `OK` results for nonfinite, ambiguous, and matrix-valued inputs plus destructive input/output aliasing; compile corrected code; run focused pytest; parse JSON/SVG; check line lengths and committed blob identities.
- **Scientific boundary:** a valid weight vector and ESS report do not prove that downstream analyses actually consume the weights or that a weighted model closes against data. Production ROOT bytes and downstream reruns remain external/compute blockers.
- **Status:** ACTIVE
