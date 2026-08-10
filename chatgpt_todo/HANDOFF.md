# Latest Handoff

## Session

- **Task:** `ARU-RAW-CONSUMER-SAME-BYTES-001`
- **Stamp:** `2026-08-10T112500Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Main at branch point:** `439d611efe9908ae91379b7024e98ead36e4d30b`
- **Branch:** `fix/raw-consumer-same-bytes`
- **Parents:** #1149, #993
- **Dependencies:** #952, #953; upstream #1155 is merged/closed.
- **Claim state:** CL-001 remains GATED.

## Selected atom

`same-stream raw manifest row -> later scientific consumer -> exact manifest-bound opened object or controlled failure`.

Merged #1155 proves that each raw-input row is internally coherent:

```text
sha256(row) = H(B_manifest)
bytes(row) = |B_manifest|
```

but current `scripts/studies/data_side_real_beam.py::timing()` later performs an independent `uproot.open(RAW_DIR / ...)`. Therefore the row does not prove `B_consumer = B_manifest` if the pathname changes between the two operations.

## Implemented primitive

New module `src/ccb_mc_validation/raw_input_authorization.py` adds `verified_raw_input_stream()`.

It:

1. strictly parses the manifest file/digest/descriptor fields;
2. opens the raw path once with `O_NOFOLLOW`;
3. requires a regular file and exact `(dev, ino, nlink, size, mtime_ns, ctime_ns)` match to the manifest row;
4. hashes/counts that descriptor and requires exact SHA-256 + byte-count closure;
5. rewinds it and yields a duplicate descriptor as a seekable binary file-like object;
6. retains a guard descriptor and fails closed if descriptor/link metadata change before consumer-context exit.

The consumer therefore never needs to resolve the pathname a second time after verification.

## Mechanisms and equivalence collapse

- Independent pathname reopen is rejected as authorizing.
- Rearranging pathname `stat/hash/open` operations does not solve the same TOCTOU mechanism.
- A descriptor-bound verified stream is the selected low-copy survivor.
- A private content-addressed snapshot is stronger against concurrent in-place mutation but incurs a full copy; this remains a separate cost/immutability child rather than being conflated with the descriptor design.
- A source-bound immutable data-host/object-store contract is another survivor if the real host can prove it mechanically.

## Hostile tests added

`tests/test_raw_input_authorization.py` covers stable read/seek, legacy independent-path replacement, same-content new-inode replacement, different-content replacement, replacement while the stream is held, in-place mutation, hard-link alias creation, digest mismatch, strict path/digest/integer schema, symlink rejection, and invalid block size.

The same-content replacement test is intentionally important: equal SHA-256 content does not establish that a later analysis consumed the same source object from the same manifest transaction.

## Four sequential review votes

- **DAQ/raw provenance lead — ACCEPT primitive / BLOCK #993.** The primitive closes a consumer identity gap only; it does not derive 8x16<->8x18 lineage.
- **Adversarial filesystem reviewer — ACCEPT bounded contract / REJECT snapshot-level overclaim.** An open descriptor prevents pathname replacement from redirecting reads, and post-consumer metadata catches ordinary mutation/link-state changes. Privileged metadata-forging writers and distributed-filesystem specifics are outside the proven threat model.
- **Independent validation/statistics reviewer — ACCEPT deterministic design pending exact-head CI / BLOCK real artifact.** These are binary filesystem invariants, not beam-statistical tests. A mocked Uproot integration test is still required.
- **Claims/provenance reviewer — ACCEPT local repair / BLOCK promotion.** No timing, PID, energy, detector-resolution, 8x16/8x18, or CL-001 claim is promoted.

## Scientific and validation boundary

No raw beam ROOT file was available in this runtime. The real 33-file provenance artifact was not regenerated, no production I/O benchmark was measured, no Geant4 simulation was run, and no detector result changed. This branch currently adds the reusable authorization primitive and its falsifiers; `timing()` still needs integration.

## Next atomic children

1. Integrate `verified_raw_input_stream()` into the full Uproot iteration lifetime in `timing()`; Uproot officially accepts seekable Python file-like objects, so the integration need not reopen a path.
2. Make missing/unmatched manifest rows fail closed instead of silently skipping required timing runs.
3. Add a mocked Uproot test proving the parser receives a file-like stream and no independent pathname open occurs.
4. Measure the extra verification-read cost on the real data host; compare descriptor streaming with a verified snapshot only if cost/threat requirements justify it.
5. Regenerate the real manifest and continue #993/#953 event/channel/sample and word-level closure. Hash identity alone must never be used to infer the 16<->18 transform.
