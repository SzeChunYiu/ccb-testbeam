# Publication readiness

**State:** `FAIL_CLOSED / NOT_SUBMISSION_READY`

**Current-head audit baseline:** `main@c9796f28d9280591a475b1b1545686e26e0956a6` (2026-08-14)

**Detailed completion audit:** `chatgpt_todo/PAPER_COMPLETION_AUDIT_20260814.md`

Central gated items:

- #956/#1321: corrected DeltaE-E must be rerun from the authorising 8×16 pre-threshold event-level amplitude product; MC physical-layer/readout namespaces, mapping, trigger and event-measure semantics also need repair.
- #1297/#1302/#1303/#1322: the historical optical grid and 8.9% energy result are non-authorising; regenerate the current optical model and choose `E_raw` vs `E_vis` explicitly before a new held-out reconstruction.
- #1296/#962/#1045/#869/#954: installed hardware, run/trigger, mapping and polarity evidence.
- #1053/#1179/#1311: legacy MC event-measure conversion, source uncertainty and exact production provenance. The deterministic direct-CDF sampler defect tracked by #1178 is repaired/closed, but that does **not** authorise the historical paper MC.
- #1317/#1318/#1319/#1320: the final setup, beam-data depth, MC depth and timing figure packages are still pending.
- #1304/#1299: one canonical scientific claim/status mechanism and current-facing WIKI/documentation reconciliation. The WIKI still contains stale claim promotions that disagree with `docs/claim_ledger.csv`.
- #1301/#1305: umbrella submission and merged-state fail-closed gates.

The current package has no authorising non-README files in `publication/figures/final/`, `publication/figures/source_data/` or `publication/tables/final/`. `validate_publication.py` currently verifies package structure/hold state; it is not a scientific submission-readiness validator.

A green PDF build means only that the controlled working manuscript compiled. It does **not** mean physics claims passed publication review.
