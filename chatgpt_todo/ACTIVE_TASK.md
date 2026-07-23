# Active Task

- **Task ID:** AUD-G4-012
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T18:15:39Z
- **Initial remote main SHA:** `bf295c1e7d295698673ffa7bb4c668c19015df49`
- **Validated implementation/evidence head:** `084b753685e5dc22a978482eef71f7649e352d3b`
- **Scope:** integrate the exact-decimal PSTAR component identity `total = electronic + nuclear` into the canonical stopping-power comparison so arbitrary reference input cannot bypass the validated cross-column gate.
- **Confirmed defect:** `compare_stopping_power.py` independently parsed finite, positive, ordered values but did not test the component identity; a row such as `1,9,1,8` could enter a numerical ratio.
- **Validated change:** validator v1.1.0 exposes canonical rows plus provenance; the comparison imports that parser, rejects component-inconsistent input with status 2 before numerical output, and records reference SHA-256, bytes, row count, validator version, identity, and consistency.
- **Commands:** focused `py_compile`; combined pytest over component, reference integrity/domain, quenched proxy, simulation integration, and simulation validator modules; JSON/SVG parsing; line-length and file-hash checks.
- **Validation:** `42 passed in 4.22s`; invalid direct CLI returned status 2, wrote no CSV, and printed no numerical PASS; JSON/SVG parsing passed; maximum changed Python line length 97.
- **Evidence:** `docs/validation/pstar_component_sum_integration_audit.md`, `pstar_component_sum_integration_validation.json`, and `pstar_component_sum_integration.svg`.
- **Boundary:** canonical component validation is complete; external source transcription/material identity and accepted Geant4 stopping-power closure remain separate and unresolved.
- **Status:** COMPLETE for `AUD-G4-012`; next dependency-resolved scientific work remains `AUD-G4-011` real-export execution or `AUD-G4-005` accepted physics closure when exact artifacts/compute are available.
