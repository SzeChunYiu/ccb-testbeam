# Latest Handoff

## Session

- **Task ID:** `ARU-RAW-DIGEST-SAME-STREAM-CLOSURE`
- **Stamp:** `2026-08-10T104900Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial remote main:** `7fb2a06596a87cb2dd294ec9d0b149e3575293e5`
- **Branch:** `fix/raw-input-same-stream-provenance`
- **PR:** #1157
- **Primary issue:** #1155
- **Parent:** #993
- **Related:** #952, #953; CL-001 remains GATED.
- **Acceptance boundary:** implementation/tests are complete on PR #1157; only exact-head/current-base GitHub Actions may authorize merge or #1155 closure.

## Selected atom

`raw ROOT pathname -> one opened regular-file byte stream -> SHA-256 + exact byte count + descriptor identity/stability -> raw-input provenance row -> waveform-lineage evidence`.

## Exact result

The pre-fix producer performed three separate pathname observations:

```text
path.exists()
-> sha256_file(path)
-> path.stat().st_size
```

A pathname replacement between those operations can serialize a row with a digest from state A and a byte count from state B.

The new contract defines one stream `B` from one opened descriptor and requires

```text
sha256 = H(B)
bytes = |B|
```

with stable `(st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns)` before/after the read and exact `bytes_read == st_size_after` closure.

## Implementation

`scripts/studies/data_side_real_beam.py` now includes `digest_raw_input()`:

- one `os.open()` call with `O_NOFOLLOW`;
- regular-file requirement;
- bounded `os.read()` loop feeding both SHA-256 and the byte counter;
- `fstat()` source identity before and after the read;
- fail-closed mutation detection;
- recorded source device, inode, link count, mtime and ctime;
- explicit schema `same-open-stream-v1` in `provenance.json`.

`collect_raw_input_digests()` keeps #1154's complete-list/missing-run semantics but no longer uses separate `exists/hash/stat` observations. Only `FileNotFoundError` becomes an explicit missing run; symlink/nonregular/unstable inputs fail instead of producing an ordinary row.

## Hostile tests

`tests/test_data_side_rmax_quarantine.py` now tests:

1. known exact SHA-256 and byte counts on stable synthetic files;
2. the legacy `H(A)` + `|B|` mixed-version counterexample;
3. pathname replacement after descriptor open, proving the repaired row stays bound to the original stream rather than the replacement;
4. in-place append during hashing, which must fail closed;
5. final-component symlink rejection;
6. nonregular input and invalid block size;
7. missing-run ordering and complete manifest preservation;
8. persisted digest-schema identity.

No test success is claimed yet. This runtime could not obtain a local checkout because ordinary network resolution to `github.com` is unavailable. PR #1157 has been opened; if its head moves after a workflow starts, that earlier workflow is stale and must not authorize merge.

## Four sequential review passes

- **DAQ/provenance lead — ACCEPT local contract / BLOCK #993 closure:** same-stream rows are necessary, not sufficient, for 8x16<->8x18 lineage.
- **Adversarial filesystem reviewer — ACCEPT bounded contract:** path replacement, mutation, symlink and nonregular worlds are separated; privileged hostile-writer guarantees remain outside this atom.
- **Independent validation/statistics reviewer — ACCEPT deterministic design pending CI / BLOCK real artifact:** synthetic state-machine falsifiers are decisive for the software contract, but the real 33-file manifest must be regenerated on the data host.
- **Claims/provenance reviewer — ACCEPT repair / BLOCK promotion:** content-row coherence does not establish waveform transformation, polarity, timing, PID or detector performance.

## Repository actions

- Created branch `fix/raw-input-same-stream-provenance` from `main@7fb2a06596a87cb2dd294ec9d0b149e3575293e5`.
- Added the one-open provenance implementation.
- Added hostile regression tests.
- Added immutable ARU archive `chatgpt_todo/archive/2026-08-10T104900Z_ARU-RAW-DIGEST-SAME-STREAM-CLOSURE.md`.
- Opened PR #1157 and bound `ACTIVE_TASK.md` / this handoff to it.
- Do not infer validation from earlier #1154/#1156 runs; inspect the final #1157 head and its current-base workflow.

## Scientific boundary

No raw ROOT file was opened in this runtime, no real beam provenance artifact was regenerated, no Geant4 simulation was run, and no S00 count, timing, PID, penetration, energy, pile-up, calibration or detector-performance value changed. CL-001 remains GATED. #993 remains open.

## Next

Require exact-head/current-base CI for PR #1157. After merge, regenerate the complete real raw-input manifest on the data host using the original canonical files, then continue #993/#953 with exact event/channel/sample lineage rather than interpreting digest closure as a 16<->18 transform proof.
