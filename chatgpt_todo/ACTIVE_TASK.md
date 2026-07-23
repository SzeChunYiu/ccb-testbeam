# Active Task

- **Task ID:** AUD-G4-010
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T16:06:03Z
- **Initial remote main SHA:** `b7a3a4d73537ee036c506658f5331a6ac4f5e999`
- **Validated implementation head:** `1237fbcdfd530ea637cde27acc39c5c94b25600b`
- **Latest coordination head before this record:** `095fb4e6b82cfb9be45009cfda51664c19d91858`
- **Scope:** integrate the strict stopping-power simulation-table parser into `scripts/single_stave/compare_stopping_power.py` so the canonical CLI cannot silently omit malformed rows or select ambiguous aliases.
- **Confirmed defect:** the canonical comparison still used a duplicated permissive reader even after `AUD-G4-009` added a strict standalone validator. A synthetic three-row table with a missing middle-row energy returned two rows without failure.
- **Validated change:** shared validator v1.1.0 now returns normalized rows plus provenance; the canonical CLI delegates to it, propagates input SHA-256/bytes/validated-row count/version to output, and returns status 2 before numerical PASS on malformed or ambiguous input.
- **Commands:** `python -m py_compile` over the comparison, validator, three existing stopping-power suites, standalone-validator tests, and integration tests; `python -m pytest` over the same five focused test modules; JSON/XML parsing and changed-file line-length scan.
- **Validation:** `35 passed in 4.34s`; compile passed; validation JSON and SVG parsed; maximum changed Python line lengths are 91, 91, and 99 characters; ruff was unavailable.
- **Evidence:** `docs/validation/stopping_power_sim_input_integration_audit.md`, `stopping_power_sim_input_integration_validation.json`, and `stopping_power_sim_input_integration.svg`.
- **Boundary:** no exact real Geant4 event table, ROOT output, simulation run, accepted PSTAR closure, calibration, or detector-performance result was produced. Local deposited energy remains a diagnostic proxy and deuteron velocity scaling remains approximate.
- **Status:** COMPLETE for the focused parser-integration unit; PARTIAL scientific stopping-power program remains under `AUD-G4-005`, `AUD-G4-011`, and `BLK-G4-SP-001`.
