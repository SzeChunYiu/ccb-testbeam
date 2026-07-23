# Active Task

- **Task ID:** AUD-AMP-009
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T06:09:08Z
- **Base main SHA:** `1b00e612cd9358486f2d9db0164def1ec09fec20`
- **Scope:** require amplitude-convention authorization to measure the bytes of every supporting schema, producer-code, or pedestal-evidence artifact rather than trusting a declared digest string.
- **Assumption under test:** an `evidence_reference_sha256` field is not immutable provenance unless the referenced file is resolved under a controlled root and its measured SHA-256 equals the declaration.
- **Confirmed finding:** v1.1.0 of `validate_amplitude_evidence_map.py` validated digest syntax only, while v3.0.0 of `amplitude_convention_audit.py` could use that unchecked declaration to authorize `ABSOLUTE` or `NET` physics processing.
- **Files:** `tools/audit/validate_amplitude_evidence_map.py`, `tools/audit/amplitude_convention_audit.py`, six focused test modules, `chatgpt_todo/` coordination records.
- **Change:** added controlled reference-path resolution, measured supporting-artifact SHA-256 comparison, path-containment and missing-file gates, verified-evidence state, and fail-closed treatment of raw programmatic maps whose reference bytes were not resolved.
- **Validation plan executed:** compile both tools and affected tests; run the six focused pytest modules; scan changed files for lines over 100 characters; inspect staged-equivalent content and remote commit sequence.
- **Validation result:** focused local reconstruction returned `35 passed in 0.12s`; all changed files compiled; no over-100-character lines remained. Ruff, the complete repository suite, and GitHub Actions were unavailable and are not claimed.
- **Boundary:** no real A-002 pulse table or supporting evidence artifact was available. No amplitude convention, stopping profile, CSV, plot, calibration, or detector-performance result was regenerated.
- **Status:** PARTIAL — reference-byte verification tooling and synthetic regression are validated; real A-002 authorization and regenerated scientific outputs remain BLOCKED.
