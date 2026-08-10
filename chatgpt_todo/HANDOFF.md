# Latest Handoff

## Session

- **Task:** `ARU-RAW-UPROOT-SAME-STREAM-001`
- **Stamp:** `2026-08-10T114700Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Main before work:** `439d611efe9908ae91379b7024e98ead36e4d30b`
- **Merged upstream:** PR #1159 -> `4fe1efaf931083de0a3c61bd25a447f5cb21e7a2`, after exact-head MC Validation success.
- **Branch / PR:** `fix/raw-timing-manifest-bound-consumer` / #1160
- **Parents:** #1149, #993; dependencies #952, #953; CL-001 remains GATED.

## Selected atom

`manifest-bound raw bytes -> canonical Uproot timing consumer -> exact same authorized bytes through the complete parser/iteration lifetime`.

Required invariant: `H(B_consumed) = H(B_manifest) = row.sha256`, with `(dev,ino,nlink,size,mtime_ns,ctime_ns)` stable through verification and consumer-context exit.

## Work completed

PR #1159's reusable `verified_raw_input_stream()` primitive was independently inspected, its exact-head CI was verified successful, and it was squash-merged with expected-head protection.

PR #1160 adds `src/ccb_mc_validation/raw_uproot_authorization.py` with strict unique run indexing, required-run completeness, and `open_verified_uproot()`. The adapter passes only the verified seekable stream to Uproot and nests the entire Uproot file lifetime inside the descriptor guard context.

The canonical `scripts/studies/data_side_real_beam.py::timing()` is now migrated on the branch: it receives the provenance record, canonicalizes timing run IDs, requires one row per needed run, removes the old missing-path silent skip and direct `uproot.open(path)`, iterates each ROOT tree inside the verified Uproot context, and records `manifest-bound-same-open-stream-v1` plus the authorized run list in its output.

Fixture tests cover real tiny-ROOT adapter reads, file-like-not-path argument, pre-open replacement, replacement while Uproot is alive, duplicate/missing/malformed run rows, canonical timing success, missing manifest row before raw open, and canonical raw-file replacement rejection. These are software/provenance tests, not beam validation.

## Four sequential review votes

- **DAQ / reconstruction lead — ACCEPT canonical same-bytes integration pending exact-head CI.** Physical first-four baseline validity, sampling interpretation, and 8x16/8x18 lineage remain separate atoms.
- **Adversarial mechanism reviewer — ACCEPT bounded descriptor/Uproot contract / BLOCK any future pathname fallback.** Privileged writers able to mutate bytes while forging/restoring metadata remain outside the proven threat model.
- **Independent validation/statistics reviewer — ACCEPT deterministic fixture design pending exact-head CI / BLOCK detector inference.** No timing-resolution or detector estimator is validated by these fixtures.
- **Claims/provenance reviewer — BLOCK #993 and CL-001 promotion.** Event identity, width lineage, mapping/polarity, real manifest regeneration, and downstream cross-atom closure remain unresolved.

## Next atomic children

1. Wait only for exact-head CI on the final #1160 branch state; do not reuse earlier green heads after documentation/code changes.
2. Measure the extra full verification read on the real data host: source bytes/hash, filesystem/device, cold/warm cache, block size, wall time, throughput and storage overhead. Compare with a copied snapshot only if threat/cost evidence requires it.
3. Regenerate the complete real manifest on the data host and rerun the canonical timing producer before treating prior report artifacts as authorizing under the new contract.
4. Continue #993/#953 exact event/channel/sample and word-level lineage. Keep 8x16/8x18 waveform-width semantics under existing #952; same-bytes authorization does not identify the transform.
