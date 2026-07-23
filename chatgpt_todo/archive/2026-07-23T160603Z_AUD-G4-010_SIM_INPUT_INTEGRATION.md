# AUD-G4-010 — Canonical stopping-power simulation-input integration

## Session

- **UTC:** 2026-07-23T16:06:03Z
- **Owner:** scheduled ChatGPT audit session
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Initial remote main:** `b7a3a4d73537ee036c506658f5331a6ac4f5e999`
- **Focused acceptance:** COMPLETE for canonical parser integration, synthetic regression, provenance propagation, visual evidence, and direct-to-main delivery; PARTIAL for real-table validation and accepted stopping-power closure.

## Start-of-run review

- Inspected current `main`, recent commits, repository permissions, PR #868 state, commit status, stopping-power comparison code, strict standalone simulation-table validator, focused tests, PSTAR reference data, and mandatory `chatgpt_todo/` records.
- PR #868 was confirmed closed, unmerged, and non-mergeable. It was not modified or merged.
- No status checks were attached to the initial head.
- Direct repository work used authenticated GitHub connector writes because the runtime did not provide a reliable checked-out repository path; no force-push, history rewrite, branch-only delivery, raw-data modification, or unrelated deletion was used.

## Confirmed defect

`AUD-G4-009` had added a strict standalone preflight, but `scripts/single_stave/compare_stopping_power.py` still contained a separate permissive `read_sim` implementation. That implementation:

- silently continued past missing particle values;
- silently continued past missing energy-deposit values;
- silently continued past missing energy or track length;
- silently continued past nonpositive track length;
- chose the first populated alias rather than rejecting multiple populated aliases.

A synthetic three-row reproduction with a missing energy in the middle row measured:

```json
{"input_rows": 3, "returned_rows": 2, "silently_skipped": 1}
```

This is parser-regression evidence, not detector data and not a Geant4/PSTAR agreement result.

## Validated implementation

### Shared parser

`tools/audit/validate_stopping_power_sim_table.py` is now version `1.1.0` and exposes:

```python
read_validated_simulation_table(path, allow_quenched_proxy=False)
```

It returns normalized rows together with exact provenance after validating every noncomment row. It canonicalizes proton/deuteron labels, converts centimetre track lengths to millimetres, rejects ambiguous aliases, rejects missing/nonnumeric/nonfinite/nonphysical values, rejects raw/quenched mixing, and records SHA-256, byte size, validated-row count, basis, and validator version.

### Canonical comparison

`scripts/single_stave/compare_stopping_power.py` now imports and delegates to the shared parser. The legacy silent-skip path is no longer used. The comparison:

- returns input-error status 2 for malformed or ambiguous simulation input;
- prints no numerical PASS after an input error;
- aggregates only normalized validated rows;
- records simulation input SHA-256, byte size, validated-row count, deposit basis, and validator version in result rows and output CSV;
- preserves fail-closed PSTAR reference integrity/domain handling and non-accepting quenched-proxy behavior;
- retains explicit `DIAGNOSTIC_ONLY` scientific status.

### Regression coverage

Added `tests/test_compare_stopping_power_sim_input_integration.py` covering:

1. rejection of a malformed middle row;
2. rejection of multiple populated energy aliases;
3. CLI status 2 and suppression of numerical PASS;
4. canonical particle normalization, exact input provenance, validated-row count, validator version, and output CSV fields.

## Reproducible validation

Executed on exact local reconstructions of the committed files:

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

Additional checks:

- validation JSON parsed successfully;
- SVG parsed successfully as XML;
- maximum changed Python line lengths: comparison 91, validator 91, integration test 99;
- ruff was unavailable;
- full repository pytest, Geant4/CTest, ROOT processing, real simulation execution, and GitHub Actions were not run.

Local SHA-256 values used in the validation record:

- comparison: `f2a7ae1c6434bf705c19f47f89670a0e4ef1e81bc7195f12a70f2d20e8ab6ae9`;
- shared validator: `24fae560a345eb6b211e4d09cc79c2cce69ccbe75c2f4dc85c49fb5bb2c8c218`;
- integration test: `f3eb911c5aa94e711cc0860ba6aff4da411cd1a826463e4953bbcea421231ce5`.

## Visual and machine-readable evidence

Added:

- `docs/validation/stopping_power_sim_input_integration_audit.md`;
- `docs/validation/stopping_power_sim_input_integration_validation.json`;
- `docs/validation/stopping_power_sim_input_integration.svg`.

The SVG explicitly states that it is synthetic regression evidence and not detector data. It contrasts the former three-to-two-row silent path with integrated status-2 rejection and no numerical PASS.

## Direct-to-main commits

- `99f276fe38592f709542e03fb79c783e88dffc27` — `fix(single-stave): integrate fail-closed simulation parser`
- `b4cbc0399d679bfbb8fd2f30d35f10ed211a1550` — `refactor(audit): expose canonical stopping-power rows`
- `8debfbae9c846f078316b2bc9c0b6e58a82dbb03` — `test(single-stave): cover shared simulation parser integration`
- `b72c2b147663efc428fad2927b359146c0bed7eb` — `docs(validation): record stopping-power parser integration`
- `3804be1dfaba40f99e171ca4b1156d1314bea13e` — `docs(validation): add stopping-power parser integration record`
- `1237fbcdfd530ea637cde27acc39c5c94b25600b` — `docs(validation): visualize stopping-power parser integration`
- `efb909a1e7446ee0ba38bb3c4f8bc4b59ff1b22c` — `docs(audit): track stopping-power parser integration`
- `a4251f561ab012c1a5a1b9dfccea2e3b6b8c48f2` — `docs(audit): index stopping-power parser integration`
- `73c37b4c40bd3d3d12f47bcd8faa47dd8cfc70bb` — `docs(audit): map canonical stopping-power parser integration`
- `f4882e8e6c524502add2c018ed0a4fe47b2ab2e8` — `docs(audit): record canonical stopping-power parser study`
- `ff4b94f5843050c2cd264255a4100a1c7511f5fe` — `docs(audit): classify stopping-power parser integration`
- `907d87deb16e2bd575d0960ff214afe619ab2a3b` — `docs(audit): register stopping-power parser integration visual`
- `095fb4e6b82cfb9be45009cfda51664c19d91858` — `docs(audit): resolve stopping-power parser integration blocker`
- `83eeddf44a4a80aa2c3646e4919039de9f17c4ac` — `docs(audit): claim stopping-power parser integration`

## Scientific boundary and unresolved risk

This change prevents malformed or ambiguous simulation rows from silently entering the diagnostic. It does not establish Geant4 agreement with PSTAR or validate a detector response.

Still unresolved:

- no exact real exported Geant4 event table was available;
- local deposited energy may exclude energy carried by generated secondaries;
- projectile energy evolves along the scored path;
- production cuts, material definition, density, and physics list affect the result;
- deuteron `S_d(E) ≈ S_p(E/2)` remains an approximation;
- full repository tests, ruff, Geant4/CTest, ROOT processing, and GitHub Actions were not run.

## Next action

Run the integrated CLI against exact real exported event tables and retain path, byte size, SHA-256, validated-row count, particle/energy coverage, deposit basis, command, environment, code commit, output hash, and any rejection. Then execute the separate accepted proton stopping-power closure under `AUD-G4-005` / `BLK-G4-SP-001`.

## Session-log handling

`chatgpt_todo/SESSION_LOG.md` is append-only. The connector exposes complete-file replacement but no safe append primitive, and the long file was available only through partial paged reads. It was not replaced from reconstructed or incomplete bytes because that could destroy prior provenance. This immutable archive is the complete run record; the omission is explicitly carried into the handoff.
