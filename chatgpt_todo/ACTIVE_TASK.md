# Active Task

- **Task ID:** AUD-AMP-011
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T192915Z
- **Initial remote main SHA:** `e215a4cd44ca6ed2eff3ec45921fcc72faa1e115`
- **Scope:** prevent whitespace-only amplitude-evidence line fragments from authorizing physics conventions and retain a digest of the exact selected fragment bytes.
- **Confirmed defect:** validator v1.3.0 accepted any in-range `#L<start>[-L<end>]` selection, including a line containing only spaces or tabs, and recorded no fragment byte size or SHA-256.
- **Correction:** validator v1.4.0 rejects selections with zero nonblank lines and records selected-fragment byte count, nonblank-line count, and SHA-256 while preserving whole-file references.
- **Validation:** old-source negative control returned `2 failed, 6 passed`; current focused suites returned `23 passed in 0.05s`; changed Python lines are no longer than 100 characters.
- **Evidence:** `docs/validation/amplitude_evidence_fragment_content_audit.md`, `.json`, and `.svg`.
- **Scientific boundary:** synthetic software/provenance validation only; no A-002 amplitude convention, pedestal evidence, regenerated stopping profile, or detector result was validated.
- **Status:** COMPLETE.
