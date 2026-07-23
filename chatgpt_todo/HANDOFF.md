# Latest Handoff

## Session

- **UTC:** 2026-07-23T16:06:03Z
- **Task:** `AUD-G4-010`
- **Initial remote main:** `b7a3a4d73537ee036c506658f5331a6ac4f5e999`
- **Validated implementation/evidence head:** `1237fbcdfd530ea637cde27acc39c5c94b25600b`
- **Coordination/archive head before this handoff:** `10f858986019b0e27f5d1353cbcdedeeddacf031`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Acceptance:** COMPLETE for canonical simulation-parser integration, focused regression, provenance propagation, visual evidence, coordination records, and direct-to-main delivery; PARTIAL for exact real-table execution and accepted stopping-power closure.

## Start-of-run and concurrent-work review

- Inspected current `main`, recent history, repository permissions, current stopping-power code/tests/data, previous `AUD-G4-009` handoff, and mandatory `chatgpt_todo/` records.
- PR #868 was rechecked and remains closed, unmerged, and non-mergeable. It was not modified or merged.
- No status checks were attached to the initial head.
- No task branch, pull request, force-push, history rewrite, raw-data change, or unrelated deletion was used.

## Confirmed defect

`AUD-G4-009` added a strict standalone simulation-table validator, but the canonical `scripts/single_stave/compare_stopping_power.py` still used a separate permissive reader. That reader silently skipped rows with missing particle, energy, deposit, track length, or nonpositive track length and selected the first populated alias.

A synthetic three-row reproduction with a missing middle-row energy measured:

```json
{"input_rows": 3, "returned_rows": 2, "silently_skipped": 1}
```

Thus a malformed event table could become an undocumented selected subset before PSTAR aggregation.

## Validated implementation

### Shared parser v1.1.0

`tools/audit/validate_stopping_power_sim_table.py` now exposes `read_validated_simulation_table(...)`, which returns normalized event rows plus provenance after validating every noncomment row. It:

- canonicalizes proton/deuteron labels;
- requires exactly one energy, deposit, and track-length alias;
- converts centimetre track lengths to millimetres;
- rejects missing, nonnumeric, nonfinite, and nonphysical values;
- rejects raw/quenched mixing and ambiguous aliases;
- records exact path, byte size, SHA-256, header, validated rows, particle counts, energy range, basis, and tool version.

### Canonical comparison integration

`compare_stopping_power.py` now imports the shared parser and no longer uses the legacy silent-skip logic. It:

- returns input-error status 2 for malformed or ambiguous simulation input;
- emits no numerical PASS after an input error;
- aggregates only normalized validated rows;
- propagates simulation input SHA-256, bytes, validated-row count, basis, and validator version into result rows and output CSV;
- preserves fail-closed reference integrity/domain behavior and non-accepting quenched-proxy behavior;
- remains explicitly `DIAGNOSTIC_ONLY`.

Added `tests/test_compare_stopping_power_sim_input_integration.py` covering malformed middle-row rejection, ambiguous alias rejection, CLI failure behavior, normalization, row accounting, provenance, and output columns.

## Reproducible validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_compare_stopping_power_sim_input_integration.py

python -m pytest \
  tests/test_compare_stopping_power_reference_path.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_compare_stopping_power_sim_input_integration.py -q

35 passed in 4.34s
```

Additional completed checks:

- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line lengths were 91, 91, and 99 characters;
- local SHA-256 values were recorded in the immutable archive and validation JSON.

Not run:

- ruff, because it was unavailable;
- full repository pytest;
- Geant4 build/CTest;
- ROOT or real simulation processing;
- GitHub Actions.

No broader CI, real stopping-power closure, calibration, or detector-performance result is claimed.

## Reproducible evidence

Added:

- `docs/validation/stopping_power_sim_input_integration_audit.md`;
- `docs/validation/stopping_power_sim_input_integration_validation.json`;
- `docs/validation/stopping_power_sim_input_integration.svg`.

The SVG explicitly states that it is synthetic regression evidence and not detector data. It contrasts the former three-to-two-row silent path with integrated status-2 rejection and no numerical PASS.

## Direct-to-main commits

Implementation, tests, and evidence:

- `99f276fe38592f709542e03fb79c783e88dffc27` — `fix(single-stave): integrate fail-closed simulation parser`
- `b4cbc0399d679bfbb8fd2f30d35f10ed211a1550` — `refactor(audit): expose canonical stopping-power rows`
- `8debfbae9c846f078316b2bc9c0b6e58a82dbb03` — `test(single-stave): cover shared simulation parser integration`
- `b72c2b147663efc428fad2927b359146c0bed7eb` — `docs(validation): record stopping-power parser integration`
- `3804be1dfaba40f99e171ca4b1156d1314bea13e` — `docs(validation): add stopping-power parser integration record`
- `1237fbcdfd530ea637cde27acc39c5c94b25600b` — `docs(validation): visualize stopping-power parser integration`

Coordination and provenance:

- `efb909a1e7446ee0ba38bb3c4f8bc4b59ff1b22c` — `docs(audit): track stopping-power parser integration`
- `a4251f561ab012c1a5a1b9dfccea2e3b6b8c48f2` — `docs(audit): index stopping-power parser integration`
- `73c37b4c40bd3d3d12f47bcd8faa47dd8cfc70bb` — `docs(audit): map canonical stopping-power parser integration`
- `f4882e8e6c524502add2c018ed0a4fe47b2ab2e8` — `docs(audit): record canonical stopping-power parser study`
- `ff4b94f5843050c2cd264255a4100a1c7511f5fe` — `docs(audit): classify stopping-power parser integration`
- `907d87deb16e2bd575d0960ff214afe619ab2a3b` — `docs(audit): register stopping-power parser integration visual`
- `095fb4e6b82cfb9be45009cfda51664c19d91858` — `docs(audit): resolve stopping-power parser integration blocker`
- `83eeddf44a4a80aa2c3646e4919039de9f17c4ac` — `docs(audit): claim stopping-power parser integration`
- `10f858986019b0e27f5d1353cbcdedeeddacf031` — `docs(audit): archive stopping-power parser integration`

Every write above returned a successful direct-main commit SHA. This handoff update is the final direct-main write for the session and its returned SHA must be confirmed as remote `main` in the final delivery report.

## Repository-local records

Updated:

- `ACTIVE_TASK.md`;
- `BACKLOG.md`;
- `MASTER_INDEX.md`;
- `CODE_RESULT_MAP.md`;
- `STUDY_REVIEW_LEDGER.md`;
- `CLAIM_EVIDENCE_MATRIX.md`;
- `VISUALIZATION_MATRIX.md`;
- `BLOCKERS.md`;
- `HANDOFF.md`.

Added immutable provenance:

- `archive/2026-07-23T160603Z_AUD-G4-010_SIM_INPUT_INTEGRATION.md`.

`SESSION_LOG.md` was not replaced. It is append-only, the connector offers complete-file replacement but no safe append primitive, and only partial paged reads of the long file were available. Replacing it from reconstructed bytes could destroy prior provenance. The immutable archive is the complete session record, and this limitation is explicitly documented rather than concealed.

## Scientific boundary and next action

This session validates software ingestion and integration only. It does not establish:

- that any exact real Geant4 event table satisfies the schema;
- that the external PSTAR transcription is independently correct;
- that local deposited energy equals projectile total energy loss;
- that escaping-secondary energy and production-cut dependence are negligible;
- that the deuteron `S_d(E) ≈ S_p(E/2)` approximation is accurate;
- any detector calibration or performance conclusion.

Next:

1. run the integrated CLI on exact real exported event CSVs;
2. retain input/output hashes, validated-row count, particle/energy coverage, basis, command, environment, and code commit;
3. inspect any rejected rows rather than filtering them silently;
4. execute the separate accepted proton closure under `AUD-G4-005` / `BLK-G4-SP-001`.
