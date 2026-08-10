# Latest Handoff

## Session

- **Task:** `ARU-RAW-UPROOT-SAME-STREAM-001`
- **Stamp:** `2026-08-10T113500Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Main before work:** `439d611efe9908ae91379b7024e98ead36e4d30b`
- **Merged upstream:** PR #1159 -> `4fe1efaf931083de0a3c61bd25a447f5cb21e7a2`, after exact-head MC Validation success.
- **Branch:** `fix/raw-timing-manifest-bound-consumer`
- **Parents:** #1149, #993; dependencies #952, #953; CL-001 remains GATED.

## Selected atom

`manifest-bound raw bytes -> Uproot random-access consumer -> same authorized bytes through the full parser lifetime`.

The required invariant is `H(B_consumed) = H(B_manifest) = row.sha256`. Merely hashing a path and later calling `uproot.open(path)` does not establish this when the pathname can change between operations.

## Work completed

PR #1159's reusable `verified_raw_input_stream()` primitive was independently inspected, its exact-head CI was verified successful, and it was squash-merged with expected-head protection.

On the follow-on branch, `src/ccb_mc_validation/raw_uproot_authorization.py` now adds:

- strict unique `run -> manifest row` indexing;
- fail-closed required-run completeness;
- `open_verified_uproot()`, which passes only the verified seekable stream to Uproot and nests the whole Uproot file lifetime inside the descriptor guard context.

`tests/test_raw_uproot_authorization.py` uses real tiny ROOT fixtures to check branch/array reads, asserts Uproot receives a file-like object rather than a string/Path, rejects replacement before open, detects pathname replacement during the Uproot lifetime, and rejects missing/duplicate/malformed run identities.

These fixtures validate software semantics only; they are not beam-data validation.

## Four sequential review votes

- **DAQ / reconstruction lead — ACCEPT adapter / REVISE canonical integration.** Real Uproot random-access is exercised, but `scripts/studies/data_side_real_beam.py::timing()` still calls `uproot.open(path)`.
- **Adversarial mechanism reviewer — ACCEPT bounded threat model / BLOCK pathname fallback.** A replacement while Uproot is alive must end in a provenance failure; privileged metadata-forging writers remain outside scope.
- **Independent validation/statistics reviewer — ACCEPT deterministic tests pending exact-head CI / BLOCK physics inference.** No timing-resolution or detector estimator is validated by fixture tests.
- **Claims/provenance reviewer — BLOCK #993 and CL-001 promotion.** 8x16<->8x18 lineage, event identity, mapping/polarity and real artifact regeneration remain independent atoms.

## Next atomic children

1. Migrate canonical `data_side_real_beam.py::timing()` so every required run is bound to exactly one provenance row and Uproot consumes `open_verified_uproot()` for the complete iteration lifetime. Missing rows must fail before scientific outputs.
2. Keep waveform-width semantics under existing #952 rather than opening a duplicate issue.
3. Measure the additional full verification read on the real data host, with file size/hash, filesystem/device, cold/warm cache, block size, wall time and effective throughput.
4. Regenerate the complete real manifest on the data host and continue #993/#953 exact event/channel/sample lineage. Same-bytes authorization alone does not identify the 16<->18 transformation.
