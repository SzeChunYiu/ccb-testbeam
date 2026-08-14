# Publication readiness

**State:** `FAIL_CLOSED / NOT_SUBMISSION_READY`

**Current-head audit baseline:** `main@6447aab4` (2026-08-14)

**Detailed completion audit:** `chatgpt_todo/PAPER_COMPLETION_AUDIT_20260814.md`

Central gated items:

- #956/#1321: DeltaE-E producer repaired in #1336, final figure package delivered via corrected producer (CL-030..033 point to paper_956_deltaE_E_20260814T090700Z). Remaining gates: layer-map offset (#1296), saturation source-binding, MC provenance (#1311).
- #1303/#1322: optical grid regeneration in flight (~4h SLURM job running); 8.9% energy result quarantined until regenerated optical campaign completes.
- #1296/#962/#1045/#869/#954: installed hardware, run/trigger, mapping and polarity evidence.
- #1311: MC production provenance (rerun in flight).
- #1349: source uncertainty propagation.
- #1334/#1348: hardware BOM evidence.
- #1350: 8×16 depth-profile figures.
- #1317/#1318/#1319/#1320: final timing figure package pending.
- #1304/#1299: canonical claim ledger LIVE; WIKI reconciliation pending.
- #1301/#1305: umbrella submission and merged-state fail-closed gates.

The current package has no authorising non-README files in `publication/figures/final/`, `publication/figures/source_data/` or `publication/tables/final/`. `validate_publication.py` currently verifies package structure/hold state; it is not a scientific submission-readiness validator.

A green PDF build means only that the controlled working manuscript compiled. It does **not** mean physics claims passed publication review.
