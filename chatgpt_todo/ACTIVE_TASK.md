# Active Task

- **Task ID:** AUD-AMP-010
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-23T07:05:54Z
- **Base main SHA:** `7021e5491fc60ae2f59645ffb62f156d578b0947`
- **Scope:** require every optional amplitude-evidence fragment to identify an existing, immutable line or line range in the byte-verified supporting artifact.
- **Assumption under test:** hashing a supporting file is insufficient traceability when `evidence_reference` may include an unchecked decorative or nonexistent fragment.
- **Confirmed finding:** validator v1.2.0 discarded everything after `#`, so `producer_contract.md#claim-that-does-not-exist` was accepted whenever the file hash matched.
- **Files:** `tools/audit/validate_amplitude_evidence_map.py`, `tests/test_amplitude_evidence_integration.py`, `tests/test_amplitude_evidence_reference_fragments.py`, and `chatgpt_todo/` coordination records.
- **Change:** validator v1.3.0 accepts whole-file references or canonical `#L<start>` / `#L<start>-L<end>` fragments, rejects malformed/reversed/out-of-range fragments, records scope and verified line bounds, and exposes the validator version in every normalized evidence record.
- **Validation plan executed:** compile the validator, convention auditor, and focused tests; run validator and auditor-integration pytest modules; scan changed files for lines over 100 characters; compare local Git blob hashes with returned GitHub content SHAs; inspect remote commit order.
- **Validation result:** exact local reconstruction returned `36 passed in 0.06s`; compilation and line-length scan passed; local blob hashes matched the GitHub-updated validator and integration-test blobs. Ruff, the complete repository suite, and GitHub Actions were not run and are not claimed.
- **Boundary:** no real A-002 pulse table or supporting evidence artifact was available. No amplitude convention, stopping profile, CSV, plot, calibration, or detector-performance result was regenerated.
- **Status:** PARTIAL — fragment traceability tooling and focused synthetic regression are validated; real A-002 authorization and regenerated scientific outputs remain BLOCKED.
