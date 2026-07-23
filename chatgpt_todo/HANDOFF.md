# Latest Handoff

## Session

- **UTC:** 2026-07-23T11:06:11Z
- **Task:** `AUD-G4-007`
- **Initial remote main:** `9dc4005dd030e78d2523d8094fa16adffcfc0bd1`
- **Implementation/evidence head:** `00dd74cda709a7f5c6489721f3c96077136b40e5`
- **Coordination/archive head before this handoff:** `d825bbc1d465ce2c258a44356afdea08618eff9b`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Acceptance:** COMPLETE for fail-closed PSTAR reference integrity; PARTIAL for accepted stopping-power physics closure.

## Start-of-run review

- A direct clone failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and direct-to-main writes were used.
- Inspected current history/status, PR #890, the stopping-power script, reference-path/range tests, committed PSTAR CSV, and all relevant `chatgpt_todo/` records.
- Initial head had no attached status checks. No GitHub Actions success is claimed.
- No concurrent main commits appeared between the initial review and implementation writes. No force-push, branch rewrite, or unrelated-file deletion occurred.

## Confirmed defect

The former `read_reference()` silently skipped rows whose required values were missing or nonnumeric and then sorted the surviving rows. It also accepted duplicate or out-of-order energies, nonfinite values, negative stopping components, and nonpositive total stopping power.

The exact pre-change blob was `0436fb390476697cfc83f88208322a99d7792a1c`. A synthetic three-row table with a malformed middle row demonstrated that the CLI could discard the row, return success, and print `NUMERICAL TOLERANCE: PASS`. The new regression produced six expected failures against the exact old implementation.

## Validated change

`scripts/single_stave/compare_stopping_power.py` now requires:

- all four required reference columns;
- every noncomment data row to contain parseable required values;
- finite values only;
- positive energy and total stopping power;
- nonnegative electronic and nuclear components;
- strictly increasing energy in declared file order;
- at least two validated rows.

Malformed reference data raises `StoppingPowerInputError`. The CLI returns status 2 and does not print a numerical PASS.

Added:

- `tests/test_compare_stopping_power_reference_integrity.py`
- `docs/validation/stopping_power_reference_integrity_audit.md`
- `docs/validation/stopping_power_reference_integrity_validation.json`
- `docs/validation/stopping_power_reference_integrity.svg`

## Reproducible validation

```text
python -m py_compile scripts/single_stave/compare_stopping_power.py tests/test_compare_stopping_power_reference_path.py tests/test_compare_stopping_power_energy_range.py tests/test_compare_stopping_power_reference_integrity.py
python -m pytest tests/test_compare_stopping_power_reference_path.py tests/test_compare_stopping_power_energy_range.py tests/test_compare_stopping_power_reference_integrity.py -q
14 passed in 2.94s
```

Additional checks:

- exact old-script regression: `6 failed, 1 passed in 1.08s` as expected;
- no changed Python line exceeded 100 characters;
- JSON evidence parsed successfully;
- SVG parsed successfully as XML;
- validated script blob: `7c3c05f12a1311d5ead8d1d45e0f5fea91dc92ce`;
- validated test blob: `31afa0144e18f7f9e598b60c8850fa6b9269b03e`.

The reference-path test used a synthetic local table covering self-test energies. The committed PSTAR CSV was inspected through GitHub but not materialized in the execution container. Full repository pytest, ruff, Geant4, ROOT, CTest, real simulation processing, and GitHub Actions were not run.

## Visual evidence

`docs/validation/stopping_power_reference_integrity.svg` is explicitly labelled as a synthetic regression schematic. It contrasts the former skip/sort path and possible numerical PASS with strict row rejection, status 2, and no numerical PASS. It is not detector data.

## Scientific interpretation

The correction prevents corrupted or reordered local reference data from silently changing the numerical comparison. It does not establish a stopping-power closure or independently validate the external PSTAR transcription.

Still unresolved under `AUD-G4-005` / `BLK-G4-SP-001`:

- local deposited energy may differ from projectile total energy loss when secondaries escape;
- particle energy evolves along the scored path;
- material, density, production cuts, and physics list affect the comparison;
- no direct proton closure was run here;
- `S_d(E) ≈ S_p(E/2)` remains an approximation.

No Geant4 executable, ROOT file, real simulation, stopping-power measurement, calibration, or detector-performance result was generated.

## Direct-to-main commits

Implementation and validation evidence:

- `3174a0532b8cce11ff011b1992ec29d9a277ab13` — `fix(single-stave): validate PSTAR reference rows strictly`
- `d927142cc28090be4739a29db288fb5336b23f95` — `test(single-stave): cover PSTAR reference-integrity gate`
- `ef11a038e2d4f20403dbc95295819f12557fc4bc` — `docs(validation): record PSTAR reference-integrity audit`
- `821df3c1dc52b696ab25b6c926b4eaf83919587e` — `docs(validation): add PSTAR reference-integrity record`
- `00dd74cda709a7f5c6489721f3c96077136b40e5` — `docs(validation): visualize PSTAR reference-integrity gate`

Coordination and provenance:

- `462865b60ae1771229e3d4477916664d0cebeb65` — active task
- `a06be9556c2135725244846804f94ddb1284ca28` — backlog
- `f11206df4a0d034ce65975f528ba4ba988f51c6d` — master index
- `50478adc6a74058f49fea1bcadc8283b1129d8e8` — code-result map
- `f69fa4af0a050a07c6699d962b88b1d7a1d4abaf` — study ledger
- `9a9660c50e77a5f03440d4776097dc1459182b62` — claim matrix
- `5db94f9e919ebc8ebf3d39e9ce746033cb95ad0f` — visualization matrix
- `eab90835adce5a2b05ac5a235417c29c505a40dc` — blocker register
- `d825bbc1d465ce2c258a44356afdea08618eff9b` — immutable archive

Every write returned a successful commit SHA on `main`. The remote head must be queried after this handoff write for final confirmation.

## Repository-local records

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/MASTER_INDEX.md`
- `chatgpt_todo/CODE_RESULT_MAP.md`
- `chatgpt_todo/STUDY_REVIEW_LEDGER.md`
- `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`
- `chatgpt_todo/VISUALIZATION_MATRIX.md`
- `chatgpt_todo/BLOCKERS.md`
- `chatgpt_todo/HANDOFF.md`

Added:

- `chatgpt_todo/archive/2026-07-23T110611Z_AUD-G4-007_PSTAR_REFERENCE_INTEGRITY.md`

`SESSION_LOG.md` is append-only. The connector exposes complete-file replacement but no safe append primitive; replacing it without a checkout would risk changing prior history. The immutable archive contains the complete session entry. A checkout-capable follow-up should append it verbatim.

## Acceptance and next action

- Reference-row integrity gate: COMPLETE.
- Declared-order and duplicate-energy gate: COMPLETE.
- Nonfinite/nonphysical-value gate: COMPLETE.
- CLI fail-closed behavior: COMPLETE.
- Focused synthetic regression: COMPLETE.
- Markdown/JSON/SVG evidence: COMPLETE.
- Remote-main implementation/evidence: COMPLETE.
- Accepted stopping-power closure: PARTIAL / BLOCKED.

Next task: execute `AUD-G4-005` in a clean Geant4 environment. Start with proton-only `G4EmCalculator::ComputeTotalDEDX` at exact reference energies and exact material/physics/cut configuration, then add primary entry/exit energy and secondary-escape diagnostics. Retain exact versions, commands, seeds, event counts, hashes, uncertainties, overlays/ratios, and failure interpretation. Keep the deuteron approximation separate.
