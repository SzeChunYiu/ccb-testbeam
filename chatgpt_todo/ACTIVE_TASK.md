# Active Task

- **Task ID:** `ARU-RAW-UPROOT-SAME-STREAM-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T114700Z`
- **Initial remote main SHA:** `439d611efe9908ae91379b7024e98ead36e4d30b`
- **Merged upstream primitive:** PR `#1159`, squash merge `4fe1efaf931083de0a3c61bd25a447f5cb21e7a2` after exact-head MC Validation success.
- **Parent issues:** `#993`, `#1149`; related blockers `#952`, `#953`; CL-001 remains `GATED`.
- **Branch / PR:** `fix/raw-timing-manifest-bound-consumer` / `#1160`.
- **Policy:** `UPROOT_MUST_CONSUME_THE_VERIFIED_STREAM_NOT_REOPEN_THE_PATHNAME`.
- **Exact invariant:** `H(B_consumed) = H(B_manifest) = row.sha256`, with `(dev,ino,nlink,size,mtime_ns,ctime_ns)` stable through verification and consumer-context exit.
- **Implementation:** `raw_uproot_authorization.py` adds unique run indexing, required-run completeness and `open_verified_uproot()`. Canonical `scripts/studies/data_side_real_beam.py::timing()` now requires the provenance record, binds every needed run to one row, removes silent missing-path skip/direct `uproot.open(path)`, and keeps each full tree iteration inside the verified Uproot context.
- **Hostile controls:** real tiny-ROOT adapter read; file-like-not-path spy; pre-open replacement; pathname replacement during Uproot lifetime; duplicate/missing/malformed run rows; canonical timing success; missing manifest row before raw open; replaced canonical raw file rejection.
- **Scientific boundary:** fixture tests validate software/provenance semantics only. No beam file, real 33-file manifest, timing/PID/energy/MC result or detector-performance claim is produced. #993/#952/#953 remain unresolved.
- **Current gate:** exact-head MC Validation for PR #1160 head `a3fb8db3299501cc22276e03e9e0e06006ebc115` is in progress; do not merge or claim closure until it passes.
- **Next after CI:** benchmark the extra verification read on the data host, regenerate the real manifest, then resume #993/#953 exact event/channel/sample lineage; keep waveform-width semantics under #952.
- **Status:** `ACTIVE / PARTIAL`
