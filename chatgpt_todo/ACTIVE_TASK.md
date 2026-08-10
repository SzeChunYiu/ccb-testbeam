# Active Task

- **Task ID:** `ARU-RAW-UPROOT-SAME-STREAM-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T113500Z`
- **Initial remote main SHA:** `439d611efe9908ae91379b7024e98ead36e4d30b`
- **Merged same-stream primitive:** PR `#1159`, squash merge `4fe1efaf931083de0a3c61bd25a447f5cb21e7a2` after exact-head MC Validation success.
- **Parent issues:** `#993`, `#1149`; related blockers `#952`, `#953`; CL-001 remains `GATED`.
- **Branch:** `fix/raw-timing-manifest-bound-consumer`.
- **Policy:** `UPROOT_MUST_CONSUME_THE_VERIFIED_STREAM_NOT_REOPEN_THE_PATHNAME`.
- **Selected atom:** `manifest row -> verified descriptor -> Uproot random-access lifetime -> post-consumer identity gate`.
- **Exact invariant:** `H(B_consumed) = H(B_manifest) = row.sha256`, with `(dev,ino,nlink,size,mtime_ns,ctime_ns)` stable through verification and consumer-context exit.
- **Implementation:** `src/ccb_mc_validation/raw_uproot_authorization.py` adds unique run indexing, required-run completeness and `open_verified_uproot()`, which nests the entire Uproot file lifetime inside `verified_raw_input_stream()` and never passes a pathname to Uproot.
- **Hostile controls:** tiny ROOT real-Uproot read; spy asserting file-like-not-path input; pre-open replacement; pathname replacement during Uproot lifetime; duplicate/missing run rows; bool/float/string/negative run identifiers.
- **Scientific boundary:** fixtures test software semantics only. No beam file, real 33-file manifest, timing result, PID/energy/MC result or detector-performance claim is produced. The canonical `data_side_real_beam.py::timing()` still requires migration and #993/#952/#953 remain unresolved.
- **Next:** exact-head CI for the adapter PR; migrate the canonical timing loop to require provenance rows and use the adapter for the complete iteration lifetime; benchmark the extra verification read on the data host; then resume #993/#953 exact event/channel/sample lineage.
- **Status:** `ACTIVE / PARTIAL`
