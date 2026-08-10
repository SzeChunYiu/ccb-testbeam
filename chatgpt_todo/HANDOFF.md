# Latest Handoff

## Session

- **Completed task:** `ARU-RAW-DIGEST-SAME-STREAM-CLOSURE`
- **Next task:** `ARU-RAW-CONSUMER-SAME-BYTES-001`
- **Stamp:** `2026-08-10T111000Z`
- **Owner:** hourly Atomic Research Universe audit session
- **Main before implementation:** `7fb2a06596a87cb2dd294ec9d0b149e3575293e5`
- **Main after merge:** `572cd4218051d763cbdc55d290be570941cba67d`
- **Implementation PR:** #1157
- **Closed leaf:** #1155
- **Open parents / child compatibility:** #993, #952, #953, #1149
- **Claim state:** CL-001 remains GATED.

## Completed atom

`raw ROOT pathname -> one opened regular-file byte stream -> SHA-256 + exact byte count + descriptor identity/stability -> raw-input provenance row`.

The merged contract requires

```text
sha256 = H(B)
bytes = |B|
```

for the same opened stream `B`, with stable `(st_dev, st_ino, st_size, st_mtime_ns, st_ctime_ns)` before/after the read and exact byte-count closure. Final-component symlinks, nonregular files, and tested source mutations fail closed.

## Adversarial result preserved

The first exact-head workflow, run `31381447250` on head `fa188b57a94762f10d6ad786c3bd00cdd5f20dc8`, failed with `1 failed, 1294 passed, 1 skipped, 8 xfailed, 1 xpassed`. The only failure falsified the test author's expectation that replacing a pathname after descriptor open would still return an ordinary coherent row. On the CI filesystem, the replacement changed the descriptor metadata stability tuple and the implementation rejected the source.

The implementation was not weakened. The hostile test was revised to require this stronger fail-closed behavior.

## Final validation and repository state

Final PR #1157 head:

`5040e2ae6a7e49e90fa796625e7e94a34fd5442c`

MC Validation run `31381908999` completed successfully:

```text
ruff: All checks passed!
pytest: 1295 passed, 1 skipped, 8 xfailed, 1 xpassed, 6 warnings in 90.18s
final enforcement: PASS
```

The retained workflow artifact is `validation-logs-31381908999-1`, artifact ID `9060283089`, digest `sha256:edb09ba7e6eb9be0319259676612e40e019c7ae3e335ce3460ade5fec5318700`.

`main` was rechecked immediately before merge and remained the tested base `7fb2a06596a87cb2dd294ec9d0b149e3575293e5`. PR #1157 was squash-merged as:

`572cd4218051d763cbdc55d290be570941cba67d`

Issue #1155 was then closed as completed with the scientific scope explicitly bounded.

## Four sequential review votes

- **DAQ/provenance lead — ACCEPT local closure / BLOCK #993 closure.** Same-stream file rows are necessary, not a proof of the 8x16<->8x18 transformation.
- **Adversarial filesystem reviewer — ACCEPT after falsifier-driven revision.** Legacy split observations, in-place mutation, pathname replacement, symlink and nonregular worlds now have explicit negative controls; privileged hostile-writer guarantees are outside this atom.
- **Independent validation/statistics reviewer — ACCEPT software closure / BLOCK real artifact.** Exact-head CI is green and the first failed hostile test demonstrated non-tautological validation. The actual 33-file manifest was not regenerated here.
- **Claims/provenance reviewer — ACCEPT bounded repair / BLOCK promotion.** No CL-001, timing, PID, penetration, energy or detector-performance claim is promoted.

## Recursive child compatibility

The real-beam study now creates internally coherent manifest rows, but later scientific code independently reopens `RAW_DIR/hrdb_run_*.root` with `uproot.open`. Therefore

```text
H(B_manifest) = H(row)
```

does not establish

```text
B_consumer = B_manifest
```

if the pathname can change between the provenance pass and the scientific read. This is the same verified-read/consumer universe already tracked as #1149; the issue was cross-linked instead of creating a duplicate.

## Scientific boundary

No raw ROOT beam file was opened in this runtime, no real 33-file provenance artifact was regenerated, no Geant4 simulation was run, and no S00 count, timing, PID, penetration, energy, pile-up, calibration, or detector-performance value changed. #993 remains open.

## Next

Use #1149 as the authority for the raw-side same-bytes consumer atom. Design and execute a deterministic path-replacement/mutation test across the manifest-to-`uproot.open` boundary; select verified stream/snapshot consumption or a mechanically enforced immutable-source contract. When the data host is available, regenerate the complete canonical raw-input manifest and resume #993/#953 word-level event/channel/sample lineage rather than inferring 16x18 closure from hashes alone.
