# Latest Handoff

## Session

- **Task ID:** `ARU-S00-VERIFIED-READ-SNAPSHOT-001`
- **Stamp:** `2026-08-10T081600Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Initial main:** `ef4f3cbabe010285558a425fc3e92d525b1803a2`
- **Prerequisite merge:** PR #1148 exact head `820e157b0b5ec9bd0d05cb60a889a547e2228c13` had MC Validation CI run 933 = `success`; squash-merged as `96be3588241753601a4a96e6451527e5b3ebfe6b`.
- **Atom merge:** PR #1150 exact head `4675627807efff576cd9aa51b977b4480b64976b` had MC Validation CI run 943 = `success`; squash-merged as `83256325f5cf9021912578963fdc19f6b9257df2`.
- **Exact CI result:** ruff gate passed; pytest reported `1257 passed, 1 skipped, 8 xfailed, 1 xpassed, 6 warnings in 90.64 s`.
- **Issue:** #1149 remains open.
- **Parents:** #1147 -> #1110.
- **Status:** `SAME_BYTES_PRIMITIVE_VALIDATED_ON_MAIN / REAL_SCALE_BENCHMARK_AND_CONSUMER_MIGRATION_OPEN`

## Selected atom

```text
content-bound CURRENT.json
-> one immutable generation identity
-> mutable filesystem object
-> verification
-> exact bytes consumed downstream
```

The v2 pointer merged through #1148 binds the authoritative SHA-256, but `resolve_artifact()` by itself proves only `H(file at t_verify)=H(pointer)` and then returns a mutable pathname. The retained negative control demonstrates that a later path read can observe different bytes after a hard-link mutation.

The stronger authorising-read invariant is:

```text
H(bytes actually consumed) = H(pointer snapshot)
```

## Mechanism universe and collapse

- documentation-only single-writer assumption: rejected for strict authorisation;
- chmod-only read-only generations: useful defense in depth, not byte provenance;
- `st_nlink == 1` rejection: blocks one alias mechanism but not generic in-place/path races;
- same-source-descriptor verify + rewind: collapses pathname replacement but not later writes to the same inode;
- all-bytes memory copy: exact but potentially selected-table-sized memory;
- **streaming private snapshot: selected and now validated on main.** Copy in bounded blocks to a secure temporary file and hash those exact copied blocks before the consumer can see the snapshot;
- filesystem snapshot/object store: stronger infrastructure option, deferred.

## Validated implementation

`src/ccb_mc_validation/s00_verified_read.py` now provides `verified_artifact_snapshot()`:

1. read `CURRENT.json` once to freeze one old-or-new authority snapshot;
2. validate the named generation artifact;
3. open the source with `O_NOFOLLOW` where supported and capture descriptor identity metadata;
4. copy in bounded blocks into a secure `mkstemp` snapshot while hashing those exact copied bytes;
5. fsync and require copied SHA-256 equality with the pointer;
6. yield the private read-only snapshot to downstream code;
7. remove the snapshot on context exit.

Compound suffixes such as `.csv.gz` are preserved for file-based parsers. The implementation records the source device, inode, link count and size for provenance/diagnostics.

## Deterministic falsifiers that passed exact-head CI

- source tamper before snapshot -> fail closed on digest mismatch;
- source tamper after snapshot -> private consumed bytes unchanged;
- hard-link alias mutation before snapshot -> fail closed;
- hard-link alias mutation after snapshot -> private consumed bytes unchanged;
- pointer advances from generation g1 to g2 while a snapshot is held -> reader remains bound to one complete g1 snapshot;
- unknown logical artifact, invalid block sizes and invalid scratch directory -> controlled failures;
- separate negative control proves `resolve_artifact()->later Path read` can observe a post-verification hard-link mutation.

## Four sequential expert passes after CI

- **Filesystem/reconstruction lead — ACCEPT local same-bytes primitive.** The read contract now binds consumed bytes rather than only a pathname. Remaining empirical uncertainty is real selected-table I/O overhead.
- **Adversarial mechanism reviewer — ACCEPT snapshot / BLOCK direct-path authorisation.** Source-path and hard-link mutations are neutralised for snapshot consumers; intentionally targeting the reader's private temp/process is outside the declared threat model.
- **Statistics/validation reviewer — ACCEPT deterministic closure.** This is exact byte/state-machine validation, not a beam-statistical result. No physical inference was made from the CI suite.
- **Claims/provenance reviewer — REVISE parent #1110 / no CL-001 promotion.** Authoritative consumers must migrate to the snapshot boundary before strict provenance claims can rely on it.

## Coordination / unresolved work

- #1149 remains open for the real selected-pulse-table I/O benchmark and authoritative consumer migration.
- #1110 remains open: canonical report + selected pulse table still need one content-bound immutable generation and a single pointer commit after all P0 gates.
- Active PR #1146 currently changes `scripts/01_build_pulse_table_from_root.py`; reconcile/merge/rebase that producer work before publication integration rather than creating a competing producer edit.
- Direct legacy reads and `resolve_artifact()->reopen Path` remain non-authorising for strict concurrent-reader provenance.
- #1109 pedestal physics and CL-001 scientific state remain separate; nothing in this filesystem work validates samples 0--3 as a physical pedestal or changes the historical pulse count.

## CI observation not promoted into this atom

The successful GitHub Actions job emitted a checkout post-job warning about a `.claude/worktrees/...` path missing from `.gitmodules`. The test/lint gate still concluded success. This was not used as evidence for or against the S00 read contract and should be audited separately only if it recurs or affects checkout/reproducibility.

## Scientific boundary

No raw ROOT population was rescanned, no S00 count was regenerated, no Geant4 simulation was run, and no timing/PID/penetration/energy/pile-up/detector-performance quantity changed.
