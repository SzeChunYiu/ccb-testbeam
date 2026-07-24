# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T170218Z`
- **Task:** `AUD-LEDGER-001`
- **Unit:** source-backed reconstruction of legacy MV1 PID claims `CL-017` and `CL-018`
- **Initial remote `main`:** `86fb70f4408a9bb5c0bb6dc24c016a9428e1dd0b`
- **Validated delivery head before this handoff:** `eb69a1c4132439edc33bf54aa8546c7ae2b14d6e`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** this two-row reconstruction and validation unit is `VALIDATED`; both PID values remain `GATED`; ledger-wide `AUD-LEDGER-001` remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected current `main`, recent repository history, PR #868,
commit status, mandatory `chatgpt_todo/` records, the canonical claim ledger and schema
evidence, the legacy MV1 producer/output and introducing commit, the current MV1
implementation, the current Chapter 8 narrative, and the engineering commit that
introduced group-disjoint fail-closed ML evaluation.

The write sequence was based on current remote head
`86fb70f4408a9bb5c0bb6dc24c016a9428e1dd0b`. No concurrent non-session commit appeared
during the focused sequence. No force push, history rewrite, task branch, deletion, or
replacement of unrelated contributor work was used. The connector returned successful
direct-main commit SHAs rather than conventional textual `git push` output.

PR #868 remains closed, unmerged, and non-mergeable and was not modified. No workflow
or status checks were attached to the starting head, so no GitHub Actions success is
claimed for this unit.

## Confirmed defects

The claim ledger has 43 named fields, but both legacy PID rows had only 38 columns.
Their late truth type, status, source, link, CI, blocker, supersession, and notes fields
were therefore correctly withheld by the repository's fail-closed schema policy.

The former rows also cited nonexistent paths:

- `reports/mv1_pid/REPORT.md`;
- `scripts/mv1_pid.py`;
- `reports/mv1_pid/results.json`.

The real tracked source uses row-index parity for train/test splitting after building a
track-level table that may contain multiple tracks from one event. It does not retain
`event_id`, so event groups can cross the split. The HGB estimator has no explicit
`random_state`; no environment/input manifest or exact ROOT digest is recorded; AUC and
purity carry no uncertainty. The purity summary does not retain the selected and
true-positive counts needed to reconstruct a binomial interval.

## Exact source evidence and fixed outputs

Legacy producer:

- path: `scripts/mv1_mv2_truth_pid_energy.py`;
- Git blob: `4f3632e59ede59bcf27e053265908ddca77b4386`;
- bytes: `10508`;
- SHA-256: `534c70a754dba6a7017b35bc9074111d7d8db8e43795240848ea312a25c6e6ee`.

Legacy output:

- path: `reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json`;
- Git blob: `9e49af48025b9699d957e932d06901dd47a45321`;
- bytes: `4129`;
- SHA-256: `ecf7c6209728899b641484a0409a3f4e2d2e403491d2c113b0e5a29f0f2df4bb`.

Introducing source commit:

`3539ae3aad222284bd7be100802a2651c0e064de`

Fixed output values:

| Quantity | Value |
|---|---:|
| all charged B-arm tracks | 400369 |
| proton tracks | 150130 |
| deuteron tracks | 146842 |
| binary proton/deuteron tracks | 296972 |
| HGB ROC AUC | 0.9859658513538254 |
| HGB purity at nominal 90% efficiency | 0.9644090769970706 |

These are truth-labelled simulation outputs. They are not beam-data PID performance.

## Delivered correction

`CL-017` and `CL-018` now have exactly 43 columns and record:

- the full-precision fixed output;
- `truth_type=mc_truth_only`;
- `status=GATED` and `allowed_status_validated=NO`;
- the real producer/output paths and source commit;
- `n_mc=296972`;
- `ci_status=NOT_EVALUATED_LEGACY_ROW_INDEX_SPLIT`;
- blocker `BLK-MV1-001`;
- explicit event-group leakage, determinism, provenance, uncertainty, and empirical-use
  boundaries.

The repository's current `src/ccb_mc_validation/studies/mv1_pid.py` uses group-disjoint
splitting, explicit estimator seeds, recorded versions, and fail-closed statuses. Commit
`ee3d9f93ab8b12757e5bfc5006dda7be74bb4c33` documents those engineering corrections.
The old 400369-track sample has not been rerun through that corrected path, so the
legacy outputs do not inherit its validation status.

Cumulative ledger state after this unit:

- exact-width rows: `16/26`;
- malformed and withheld rows: `10/26`;
- ledger bytes: `16393`;
- ledger SHA-256: `e607d042b7f6c6d1a62bf8fddb3c42e20e1e6429dc38a366696062330fb8eeb7`;
- width histogram: `36:1, 37:2, 38:5, 39:2, 43:16`;
- global schema status: intentionally `FLAWED` until all rows are repaired.

## New and updated files

Added:

- `tools/audit/validate_mv1_legacy_claim_rows.py`;
- `tools/audit/render_mv1_split_leakage_evidence.py`;
- `tests/test_validate_mv1_legacy_claim_rows.py`;
- `docs/validation/mv1_legacy_claim_rows_audit.md`;
- `docs/validation/mv1_legacy_claim_rows_validation.json`;
- `docs/validation/mv1_legacy_split_leakage.svg`;
- `chatgpt_todo/archive/2026-07-24T170218Z_AUD-LEDGER-001_MV1_PID_CLAIMS.md`.

Updated:

- `docs/claim_ledger.csv`;
- `docs/validation/claim_ledger_schema_audit.md`;
- `docs/validation/claim_ledger_schema_validation.json`;
- `docs/validation/claim_ledger_schema.svg`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- `chatgpt_todo/HANDOFF.md`.

Policies:

- `LEGACY_MV1_PID_OUTPUTS_REQUIRE_GROUP_DISJOINT_RERUN_AND_UNCERTAINTY`;
- `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

## Validation

Executed locally against exact repository-byte reconstructions. The committed validator
blob was reconstructed exactly after publication and rerun with the committed test
blob:

```text
python -m py_compile \
  tools/audit/validate_mv1_legacy_claim_rows.py \
  tools/audit/render_mv1_split_leakage_evidence.py \
  tests/test_validate_mv1_legacy_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv1_legacy_claim_rows.py -q

6 passed in 0.57s

PYTHONPATH=. python tools/audit/validate_mv1_legacy_claim_rows.py \
  docs/claim_ledger.csv \
  reports/mv1_mv2_truth_pid_energy_1782220258/mv1_mv2_truth_summary.json \
  scripts/mv1_mv2_truth_pid_energy.py \
  --output /tmp/mv1_check.json

direct validator: VALIDATED; issues: 0
```

Additional checks:

- corrected ledger Git blob equals local validated blob
  `9a8d4ab0c4985db31ceb48488c325570f18f0425`;
- committed validator Git blob equals the exact rerun blob
  `9565b458e15d17572a1b82e11e4d413c627ee8a2`;
- committed test Git blob equals the exact rerun blob
  `529d9f1534ecffbae4d7992300a12dfbb9f02f9a`;
- validation JSON parsed;
- both SVG files parsed as XML;
- maximum Python line lengths were 86, 95, and 97 characters.

Full repository pytest, ruff, ROOT processing, simulation reruns, beam-data processing,
repository-wide link checking, and GitHub Actions were not run. No broader CI success is
claimed.

## Direct-main commit sequence

1. `f3d70a8f33a9ecdaeb05178b3f0269c1a1cd02d4` — `fix(ledger): reconstruct legacy MV1 PID claims`
2. `888049a626be4eac259907e2d8081ffad5d3a4d3` — `feat(audit): validate legacy MV1 PID claim rows`
3. `54b4ff27b26d949d6cfb407d2bc65fbe788dfc1d` — `test(audit): cover legacy MV1 PID claim governance`
4. `f27341ee153e2af336d877086d3a68d5969ea01a` — `feat(audit): render MV1 split-leakage evidence`
5. `5e316080c248bed8c4032264747e38eef6eaab4f` — `docs(validation): record legacy MV1 PID claim audit`
6. `1e3d3e05e5a3e5de69f1ec75ab368d344ff714c2` — `docs(validation): add legacy MV1 PID machine record`
7. `47cef61739e98bcb4ddc70aef6211d4dff94eb84` — `docs(validation): visualize legacy MV1 split gate`
8. `41b82458704baace02b60b87aa872c73a38bf971` — `docs(validation): record sixteen exact ledger rows`
9. `d864ce091f30389ab5ca87a5d34c593e9dbea55d` — `docs(validation): update cumulative ledger schema record`
10. `b7c61195828b6ec543917da884a0b764cb5faa07` — `docs(validation): visualize sixteen exact ledger rows`
11. `7d3ada0f8a140c31f90e7efe3f52c48f2c33b846` — `docs(audit): complete legacy MV1 claim-row unit`
12. `eb69a1c4132439edc33bf54aa8546c7ae2b14d6e` — `docs(audit): archive legacy MV1 claim-row reconstruction`
13. this handoff commit — `docs(audit): hand off legacy MV1 claim reconstruction`

A post-write history read confirmed commits 1--12 as consecutive on remote `main`. The
connector exposes the resulting commit SHAs rather than textual push stdout.

## Scientific boundary and blockers

This unit does not establish an accepted truth-MC ceiling, empirical proton/deuteron
PID performance, a production model, or a confidence interval. It does not measure the
size of the row-index leakage effect.

`BLK-MV1-001` remains open. Resolution requires immutable ROOT/event-group provenance,
a clean group-disjoint rerun, content-addressed code/config/input/output, explicit
versions and seeds, grouped AUC and operating-point uncertainty, repeated split/seed
sensitivity, an independent final holdout, detector/physics sensitivity, and separate
beam-data closure.

Chapter 8 still contains unconditional wording that calls the legacy outputs an
established MC truth ceiling. It must be synchronized in a dedicated complete-document
unit rather than overwritten from a truncated response.

Ten claim rows remain malformed: `CL-002` through `CL-006`, `CL-008`, `CL-009`, and
`CL-019` through `CL-021`.

## Coordination limitation and next action

`SESSION_LOG.md`, `BACKLOG.md`, and `BLOCKERS.md` are long shared coordination files.
The available connector supports whole-file replacement but not a byte-safe append or
patch operation. This run did not replace them from partial ranged responses because
that could destroy concurrent provenance. The complete session and blocker definition
are retained in this handoff and immutable archive, while the canonical claim rows
record `BLK-MV1-001` directly.

Next recommended focused unit: reconstruct the source-coherent malformed MV3 group
`CL-019`--`CL-021`, while separately registering Chapter 8 public-wording synchronization
against the exact full document.
