# Active Task

- **Task ID:** `ARU-RAW-CONSUMER-SAME-BYTES-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T111000Z`
- **Current remote main SHA:** `572cd4218051d763cbdc55d290be570941cba67d`
- **Parent issues:** `#993`, `#1149`
- **Upstream completed leaf:** `#1155` via PR `#1157`.
- **Related blockers:** `#952`, `#953`; CL-001 remains `GATED`.
- **Policy:** `MANIFEST_IDENTITY_DOES_NOT_AUTHORIZE_A_LATER_PATHNAME_REOPEN`.
- **Selected next atom:** `verified raw-input manifest row -> later scientific consumer open -> exact same consumed bytes or controlled failure`.
- **Exact compatibility invariant:** `H(B_manifest)=H(row)` is necessary but does not imply `B_consumer=B_manifest` when a later consumer independently reopens a mutable pathname.
- **Current evidence:** `data_provenance()` now creates same-stream coherent rows on main, while the data-side timing path later performs independent `uproot.open()` calls on `RAW_DIR/hrdb_run_*.root`. This is the raw-side instance of the verified-read/consumer problem already tracked under #1149; no duplicate issue should be opened.
- **Required falsifier:** hash a fixed raw fixture, mutate/replace the path before a mocked consumer-open boundary, and require either verified-stream/snapshot consumption of the original authorized bytes or a controlled provenance failure before scientific outputs are authorized.
- **Candidate survivors:** verified descriptor/stream consumption; content-addressed immutable source snapshot; or a mechanically enforced and recorded immutable data-host contract. Plain pathname reopen is non-authorizing.
- **Completed #1155 evidence:** final PR head `5040e2ae6a7e49e90fa796625e7e94a34fd5442c`; MC Validation run `31381908999`; ruff clean; pytest `1295 passed, 1 skipped, 8 xfailed, 1 xpassed`; squash merge `572cd4218051d763cbdc55d290be570941cba67d`; issue closed completed.
- **Scientific boundary:** the merged row-integrity repair does not establish 8x16<->8x18 lineage, raw->sorted closure, waveform polarity, timing correctness, PID, or detector performance. The real 33-file provenance artifact still requires regeneration on the data host.
- **Next execution order:** solve the raw-side same-bytes consumer boundary under #1149, regenerate the complete real manifest on the data host when available, then continue #993/#953 exact event/channel/sample lineage.
- **Status:** `ACTIVE / TRIAGED`
