# AUD-LEDGER-001 — Legacy MV1 PID claim-row reconstruction

- **UTC session stamp:** `2026-07-24T170218Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `86fb70f4408a9bb5c0bb6dc24c016a9428e1dd0b`
- **Task unit:** source-backed reconstruction of `CL-017` and `CL-018`
- **Acceptance:** this two-row governance and validation unit is `VALIDATED`; the legacy PID values remain `GATED`; ledger-wide `AUD-LEDGER-001` remains `PARTIAL`.

## Finding

The two PID claim rows had 38 fields under a 43-field schema and cited nonexistent
source paths. The exact tracked output records HGB AUC `0.9859658513538254` and purity
`0.9644090769970706` at nominal 90% efficiency on 296,972 truth-labelled proton and
deuteron tracks. The producer splits rows by index parity, does not record `event_id`,
does not set the HGB random state, and records no input digest, environment versions,
uncertainty, or selected/true-positive counts. Multi-track events can therefore cross
the train/test boundary, and the outputs cannot be authorized as an accepted PID
ceiling or beam-data performance result.

## Exact evidence

- Producer: `scripts/mv1_mv2_truth_pid_energy.py`
  - Git blob: `4f3632e59ede59bcf27e053265908ddca77b4386`
  - bytes: `10508`
  - SHA-256: `534c70a754dba6a7017b35bc9074111d7d8db8e43795240848ea312a25c6e6ee`
- Summary: `reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json`
  - Git blob: `9e49af48025b9699d957e932d06901dd47a45321`
  - bytes: `4129`
  - SHA-256: `ecf7c6209728899b641484a0409a3f4e2d2e403491d2c113b0e5a29f0f2df4bb`
- Introducing commit: `3539ae3aad222284bd7be100802a2651c0e064de`
- Current engineering correction: `src/ccb_mc_validation/studies/mv1_pid.py`, with
  group-disjoint splitting and deterministic/provenance controls introduced in
  `ee3d9f93ab8b12757e5bfc5006dda7be74bb4c33`.

## Delivered files

- corrected `docs/claim_ledger.csv`;
- `tools/audit/validate_mv1_legacy_claim_rows.py`;
- `tools/audit/render_mv1_split_leakage_evidence.py`;
- `tests/test_validate_mv1_legacy_claim_rows.py`;
- `docs/validation/mv1_legacy_claim_rows_audit.md`;
- `docs/validation/mv1_legacy_claim_rows_validation.json`;
- `docs/validation/mv1_legacy_split_leakage.svg`;
- refreshed `docs/validation/claim_ledger_schema_audit.md`;
- refreshed `docs/validation/claim_ledger_schema_validation.json`;
- refreshed `docs/validation/claim_ledger_schema.svg`;
- updated coordination task and handoff records.

## Validation

```text
python -m py_compile \
  tools/audit/validate_mv1_legacy_claim_rows.py \
  tools/audit/render_mv1_split_leakage_evidence.py \
  tests/test_validate_mv1_legacy_claim_rows.py

PYTHONPATH=. python -m pytest tests/test_validate_mv1_legacy_claim_rows.py -q
6 passed in 0.82s
```

The direct validator returned `VALIDATED`, `n_issues=0`. JSON and SVG parsed, source
Git blobs matched the exact local reconstructions, and changed Python files contain no
line longer than 100 characters. Cumulative schema state is 16/26 exact-width and
10/26 malformed/withheld rows; global status remains intentionally `FLAWED`.

## Scientific boundary and resolution plan

No simulation or beam-data sample was rerun and no uncertainty was calculated. Resolve
`BLK-MV1-001` with immutable input and event-group provenance, a clean group-disjoint
rerun, explicit versions/seeds, grouped AUC and operating-point intervals, repeated
split/seed sensitivity, independent holdout, detector-response sensitivity, and
separate beam-data closure. Chapter 8 must not call the legacy values an established
truth ceiling before that work is complete.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, and `BLOCKERS.md` are long shared coordination files.
The available contents connector only offers whole-file replacement, not a byte-safe
append or patch primitive. They were not reconstructed from partial ranged responses,
because that could erase concurrent provenance. This immutable archive and the latest
`HANDOFF.md` carry the complete run and blocker definition; the exact claim rows also
record `BLK-MV1-001`.
