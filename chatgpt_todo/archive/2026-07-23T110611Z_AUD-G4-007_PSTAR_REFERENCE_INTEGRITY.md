# AUD-G4-007 — PSTAR Reference Integrity

## Session

- UTC: 2026-07-23T11:06:11Z
- Owner: scheduled ChatGPT audit session
- Initial remote main: `9dc4005dd030e78d2523d8094fa16adffcfc0bd1`
- Implementation/evidence head: `00dd74cda709a7f5c6489721f3c96077136b40e5`
- Destination: `main`
- Acceptance: COMPLETE for strict reference-table parsing; PARTIAL for scientific stopping-power closure.

## Review performed

Inspected current main history and status, PR #890, the stopping-power diagnostic, its reference-path and range tests, the committed PSTAR CSV, the current audit handoff/backlog/index/maps/blockers, and the relevant scientific limitations. A direct clone failed because this runtime could not resolve `github.com`; authenticated connector reads and writes were used.

## Confirmed defect

The former `read_reference()` caught missing/nonnumeric values and silently skipped those rows, then sorted the surviving rows. It did not reject duplicate or out-of-order energies, nonfinite values, negative stopping components, or nonpositive total stopping power.

The exact pre-change script blob was `0436fb390476697cfc83f88208322a99d7792a1c`. A synthetic malformed-middle-row reference demonstrated that the CLI could discard the row, return success, and print `NUMERICAL TOLERANCE: PASS`. The new fail-closed regression produced six expected failures against the exact old blob.

## Validated change

Current parsing requires all four required columns, every noncomment row to parse, finite values, positive energy and total stopping power, nonnegative electronic/nuclear components, strictly increasing energy in declared file order, and at least two validated rows. Malformed references raise `StoppingPowerInputError`; the CLI returns status 2 and prints no numerical PASS.

## Validation

```text
python -m py_compile scripts/single_stave/compare_stopping_power.py tests/test_compare_stopping_power_reference_path.py tests/test_compare_stopping_power_energy_range.py tests/test_compare_stopping_power_reference_integrity.py
python -m pytest tests/test_compare_stopping_power_reference_path.py tests/test_compare_stopping_power_energy_range.py tests/test_compare_stopping_power_reference_integrity.py -q
14 passed in 2.94s
```

Additional checks: no changed Python line exceeded 100 characters; JSON evidence parsed; SVG parsed as XML. The validated script blob is `7c3c05f12a1311d5ead8d1d45e0f5fea91dc92ce`; the new test blob is `31afa0144e18f7f9e598b60c8850fa6b9269b03e`.

The committed PSTAR CSV was inspected through GitHub but was not materialized in the local container. Full repository pytest, ruff, Geant4, ROOT, CTest, real simulation processing, and GitHub Actions were not run.

## Direct-to-main commits

- `3174a0532b8cce11ff011b1992ec29d9a277ab13` — strict parser implementation
- `d927142cc28090be4739a29db288fb5336b23f95` — focused regression
- `ef11a038e2d4f20403dbc95295819f12557fc4bc` — Markdown audit
- `821df3c1dc52b696ab25b6c926b4eaf83919587e` — machine-readable record
- `00dd74cda709a7f5c6489721f3c96077136b40e5` — synthetic visual
- `462865b60ae1771229e3d4477916664d0cebeb65` — active task
- `a06be9556c2135725244846804f94ddb1284ca28` — backlog
- `f11206df4a0d034ce65975f528ba4ba988f51c6d` — master index
- `50478adc6a74058f49fea1bcadc8283b1129d8e8` — code-result map
- `f69fa4af0a050a07c6699d962b88b1d7a1d4abaf` — study ledger
- `9a9660c50e77a5f03440d4776097dc1459182b62` — claim matrix
- `5db94f9e919ebc8ebf3d39e9ce746033cb95ad0f` — visualization matrix
- `eab90835adce5a2b05ac5a235417c29c505a40dc` — blocker register

## Scientific boundary and next action

This work validates parser integrity only. It does not independently verify NIST source transcription, material equivalence, Geant4 total stopping power, deuteron velocity scaling, calibration, or detector performance. `AUD-G4-005` / `BLK-G4-SP-001` remains open: run a clean proton closure using `G4EmCalculator::ComputeTotalDEDX` or primary entry/exit-energy accounting, quantify secondary escape and energy evolution, preserve exact material/physics/cut/version provenance, and keep deuteron approximation separate.

`SESSION_LOG.md` is append-only. The connector exposes complete-file replacement but not a safe append primitive; this immutable record preserves the full session without risking prior entries. A checkout-capable follow-up should append this entry verbatim.
