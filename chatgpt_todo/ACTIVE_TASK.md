# Active Task

- **Task ID:** AUD-G4-012
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T17:41:35Z
- **Initial remote main SHA:** `ccc61c04b16000d338939b3bf04c03fa8ec6f56c`
- **Validated implementation/evidence head:** `1f3d4d4813890254d0990008b425a26c1a5a7bf2`
- **Scope:** validate the PSTAR cross-column identity `total = electronic + nuclear` using exact decimal rounding intervals so a transcription error in the total column cannot silently bias simulation/reference ratios.
- **Confirmed defect:** the canonical reference parser validates each required value independently but does not verify that the declared total is consistent with the electronic and nuclear components. A finite, positive, ordered row with a wrong total can pass existing structural checks.
- **Validated change:** standalone validator v1.0.0 parses exact decimal tokens, derives half-unit-in-last-place intervals, requires overlap between the component-sum and declared-total intervals, records exact provenance, and fails closed on inconsistent rows.
- **Exact table result:** Git blob `7e953dd346caedcee6da54180fb636b890a64040` was reconstructed byte-for-byte; 7413 bytes, SHA-256 `bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd`, 141 rows, all component-consistent under written rounding.
- **Commands:** focused `py_compile`; `pytest tests/test_validate_pstar_component_sum.py -q`; exact-table CLI validation; JSON and SVG parsing; Git blob identity; line-length scan.
- **Validation:** `8 passed in 1.21s`; exact table `status=VALIDATED rows=141`; JSON/SVG parse passed; maximum changed Python line length 87.
- **Evidence:** `docs/validation/pstar_component_sum_audit.md`, `pstar_component_sum_validation.json`, and `pstar_component_sum.svg`.
- **Boundary:** the new check is standalone and is not yet invoked by `compare_stopping_power.py`; source transcription, material identity, Geant4 closure, and deuteron scaling remain unvalidated.
- **Status:** PARTIAL; integrate the validated component-sum parser into the canonical comparison before marking COMPLETE.
