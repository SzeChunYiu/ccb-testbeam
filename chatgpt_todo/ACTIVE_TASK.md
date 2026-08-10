# Active Task

- **Task ID:** `ARU-RAW-CONSUMER-SAME-BYTES-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T112500Z`
- **Initial remote main SHA:** `439d611efe9908ae91379b7024e98ead36e4d30b`
- **Parent issues:** `#993`, `#1149`
- **Upstream completed leaf:** `#1155` via PR `#1157`.
- **Related blockers:** `#952`, `#953`; CL-001 remains `GATED`.
- **Branch:** `fix/raw-consumer-same-bytes`
- **Policy:** `MANIFEST_IDENTITY_DOES_NOT_AUTHORIZE_A_LATER_PATHNAME_REOPEN`.
- **Selected atom:** `verified raw-input manifest row -> one verified opened descriptor -> seekable consumer stream -> post-consumer stability gate`.
- **Exact invariant:** the consumer stream must be opened from the descriptor whose SHA-256, byte count, device/inode/link identity, size, mtime and ctime match the manifest row; a later independent pathname reopen is non-authorizing.
- **Implementation:** `src/ccb_mc_validation/raw_input_authorization.py::verified_raw_input_stream()` opens once with `O_NOFOLLOW`, verifies regular-file identity plus exact digest/byte count, rewinds, yields a duplicate seekable descriptor, retains a guard descriptor and fails closed if source/link metadata change before context exit.
- **Hostile controls:** legacy path-replacement demonstration; same-content new-inode replacement; different-content replacement; path replacement while the stream is held; in-place mutation; hard-link alias creation; digest mismatch; malformed path/digest/integer fields; symlink and invalid block size.
- **Expert votes:** DAQ/provenance `ACCEPT primitive / BLOCK #993`; adversarial filesystem `ACCEPT bounded ordinary-filesystem contract / REJECT snapshot-level overclaim`; validation/statistics `ACCEPT deterministic tests pending exact-head CI / BLOCK real artifact`; claims/provenance `ACCEPT local repair / BLOCK claim promotion`.
- **Scientific boundary:** this branch adds the reusable authorization primitive and falsifiers only. `data_side_real_beam.py::timing()` still reopens raw paths independently until the next integration child. No real raw ROOT file, regenerated manifest, timing result, PID, energy result, MC result or public claim is produced here.
- **Next:** exact-head CI for the primitive PR; then integrate it into the complete Uproot iteration lifetime, make missing/unmatched manifest rows fail closed, add a mocked Uproot no-path-reopen test, benchmark the extra verification read on the data host, and resume #993/#953 word-level lineage.
- **Status:** `ACTIVE / PARTIAL`
