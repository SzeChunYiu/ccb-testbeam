# Latest Handoff

## Completed atom

- **Task:** `ARU-RAW-UPROOT-SAME-STREAM-001`
- **Validated head:** `16a2273e5b1a3c043ddc604264a5a68c1406c1ec`
- **CI:** MC Validation run `31385123680` completed successfully; checkout, install, lint, unit tests and enforcement all passed.
- **Merged:** PR #1160 -> `f023b8f01272f996e296475b0068095f48b27acf` on protected `main`.
- **Invariant now implemented in canonical raw timing:** `H(B_consumed) = H(B_manifest) = row.sha256`, with descriptor identity stable through verification and the full Uproot iteration lifetime.

`src/ccb_mc_validation/raw_uproot_authorization.py` supplies strict unique run indexing, required-run completeness, and `open_verified_uproot()`. `scripts/studies/data_side_real_beam.py::timing()` now consumes the provenance record, requires one manifest row for every timing-required run, removes silent missing-path skip/direct `uproot.open(path)`, and keeps every ROOT iteration inside the verified stream context. Tiny ROOT controls validate real Uproot random access, file-like-not-path input, pre-open replacement rejection, in-lifetime replacement detection, missing/duplicate/malformed run rows, and canonical timing integration.

## Four final review votes

- **DAQ / reconstruction lead — ACCEPT local same-bytes integration.** Physical pedestal validity, timing estimator interpretation, and 8x16/8x18 lineage remain unresolved.
- **Adversarial mechanism reviewer — ACCEPT bounded ordinary-filesystem contract.** Future pathname fallback is non-authorizing; privileged metadata-forging writers and distributed-filesystem semantics are outside the measured threat model.
- **Independent validation/statistics reviewer — ACCEPT deterministic software closure.** Fixture tests are not detector-performance validation, and the production-size verification cost remains unmeasured.
- **Claims/provenance reviewer — BLOCK #993/CL-001 promotion.** #952/#953, event identity, mapping/polarity, real manifest regeneration and cross-atom closure remain open.

## Unresolved children

The raw-side implementation is present on remote main, but the real data host is still required to regenerate the complete manifest, benchmark the extra verification pass, and rerun canonical real-beam outputs. #1149 stays open for its original S00 selected-table read contract/scale benchmark. #993/#952/#953 remain open; same-bytes authorization does not identify the historical 16<->18 transformation.

## Next highest-value executable atom

Because immutable beam bytes/data-host benchmarking are unavailable in this runtime, move to the independent code-ready P0 statistical atom **#1051 / `ARU-DATAMC-ECDF-001`** rather than stalling. `scripts/compare_data_mc.py` currently represents a weighted empirical CDF with linear interpolation. The next session should implement the right-continuous weighted step CDF

`F_w(x) = sum_i w_i I(X_i <= x) / sum_i w_i`,

collapse tied support exactly, prove invariance under weighted-row splitting/merging, cross-check equal-weight KS-D against an independent oracle, and keep p-value/null calibration explicitly blocked under #1049 until that separate atom is repaired.
