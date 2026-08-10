# Latest Handoff

## Session

- **Task ID:** `ARU-S00-VERIFIED-READ-SNAPSHOT-001`
- **Stamp:** `2026-08-10T081600Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial main:** `ef4f3cbabe010285558a425fc3e92d525b1803a2`
- **Validated merge this session:** PR #1148 exact head `820e157b0b5ec9bd0d05cb60a889a547e2228c13` had MC Validation CI run 933 = `success`; squash-merged to main as `96be3588241753601a4a96e6451527e5b3ebfe6b`.
- **Issue:** #1149
- **Parents:** #1147 -> #1110
- **Branch:** `fix/s00-verified-read-snapshot`
- **Status:** `VERIFIED_READ_IMPLEMENTED_PENDING_EXACT_HEAD_CI_AND_CONSUMER_MIGRATION`

## Selected atom

```text
content-bound CURRENT.json
-> one immutable generation identity
-> mutable filesystem object
-> verification
-> exact bytes consumed downstream
```

The v2 pointer merged through #1148 binds the authoritative SHA-256, but the existing `resolve_artifact()` API still proves only `H(file at t_verify)=H(pointer)` and then returns a mutable pathname. A consumer that later reopens that path can observe different bytes after in-place mutation or mutation through a hard-link alias.

The required authorising-read invariant is stronger:

```text
H(bytes actually consumed) = H(pointer snapshot)
```

## Mechanism universe and collapse

- documentation-only single-writer assumption: rejected for strict authorisation;
- chmod-only read-only generations: useful defense in depth, not byte provenance;
- `st_nlink == 1` rejection: blocks one alias mechanism but not generic in-place/path races;
- same-source-descriptor verify + rewind: collapses pathname replacement but not later writes to the same inode;
- all-bytes memory copy: exact but potentially selected-table-sized memory;
- **streaming private snapshot: selected.** Copy in bounded blocks to a secure temporary file and hash those exact copied blocks before the consumer can see the snapshot;
- filesystem snapshot/object store: stronger infrastructure option, deferred.

## Work completed

1. Merged the already-successful #1148 content-identity primitive only after exact-head CI verification.
2. Added `src/ccb_mc_validation/s00_verified_read.py`.
3. The API reads `CURRENT.json` exactly once, validates the named generation path, opens the source with `O_NOFOLLOW` where supported, records `fstat` identity metadata, copies in bounded blocks to `tempfile.mkstemp`, hashes the exact copied bytes, fsyncs the snapshot, and yields only after digest equality.
4. Compound suffixes such as `.csv.gz` are preserved so file-based downstream readers can retain compression inference.
5. The yielded snapshot is made read-only for the context and removed on exit.
6. Added deterministic tests for tamper-before-copy, tamper-after-copy, hard-link alias mutation before/after snapshot, pointer swap, cleanup, bad logical names, invalid block sizes and scratch directory errors.
7. Added a separate hostile negative control proving the old `resolve_artifact()->later Path read` API can observe mutated bytes after successful verification.
8. Preserved the full ARU record in `chatgpt_todo/archive/2026-08-10T081600Z_ARU-S00-VERIFIED-READ-SNAPSHOT.md`.

## Four sequential expert passes

- **Filesystem/reconstruction lead — ACCEPT design / pending exact-head CI.** Private snapshot semantics bind the bytes consumed rather than merely a mutable path. Remaining empirical question: real selected-table I/O overhead.
- **Adversarial mechanism reviewer — ACCEPT local contract / BLOCK direct-path authorisation.** Hard-link and post-verification mutation are neutralised for snapshot consumers; privileged mutation of the reader's private temp/process is outside the declared threat model.
- **Statistics/validation reviewer — ACCEPT deterministic contract / pending CI.** This is an exact byte/state-machine problem, not a beam-statistical result. The hostile old-resolver control is intentionally retained.
- **Claims/provenance reviewer — REVISE #1110 / no CL-001 promotion.** The new primitive is not authoritative until downstream claim/study consumers are migrated to it; legacy paths and `resolve_artifact()->reopen` remain non-authorising for strict concurrency claims.

## External authority checked

Official Python documentation for `tempfile` documents secure temporary-file creation (`mkstemp`/`NamedTemporaryFile`) and warns against name-only `mktemp`; official `os` documentation provides `os.open`, `O_NOFOLLOW` where supported, and file-descriptor stat metadata. These sources support software semantics only.

## Unresolved children / next work

1. Exact-head CI for this branch; do not merge on stale workflow results.
2. Measure snapshot read+write overhead on the actual selected pulse table before claiming the cost is negligible.
3. Migrate the first authoritative downstream consumer to `verified_artifact_snapshot()` and prove its parser consumes the snapshot rather than reopening the generation/legacy path.
4. Return to #1110 producer integration once active overlapping producer work (#1146) is reconciled; report + pulse table must enter one content-bound generation before a single pointer commit.
5. Keep #1109 pedestal physics and CL-001 scientific status separate from this filesystem/provenance closure.

## Scientific boundary

No raw ROOT population was rescanned, no S00 count was regenerated, no Geant4 simulation was run, and no timing/PID/penetration/energy/pile-up/detector-performance quantity changed.
