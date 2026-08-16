# AUD-G4-021 — stopping-power output-safety remediation

## Session

- UTC: `2026-07-24T030404Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `da94ca3f494b08209ed2d8f1d6d2cdc3ad85ac2c`
- Owner: scheduled independent scientific-review session
- Destination: direct to `main`
- Acceptance: COMPLETE for output/input alias rejection and atomic report publication; broader stopping-power physics remains open.

## Start-of-run review

Fetched current `main`, confirmed admin/push permission, inspected recent history, open PRs, PR #868, current source/tests/audit evidence, and all mandatory `chatgpt_todo/` records. PR #868 remained closed, unmerged, and non-mergeable and was not modified. `AUD-REPO-001` remained owned by another active session and was not duplicated. A local clone was unavailable because `github.com` did not resolve; repository reads and direct-main writes used the authenticated GitHub connector.

## Confirmed defect

Pre-change source:

- path: `scripts/single_stave/compare_stopping_power.py`
- Git blob: `360f3e46db664f4eead48021536f210e2f7a85c9`

The reporter opened the requested final path directly after input validation. It did not reject an output path resolving to the simulation or PSTAR input and did not publish through a same-directory temporary file plus atomic replacement. Thus a report could destroy exact scientific input bytes or leave a partial file at the canonical output name after a failure.

## Corrected method

Current validated source:

- Git blob: `043dbd8cae7362dede199b42b28aeb383bccde8d`
- bytes: `23541`
- SHA-256: `aa9b2f854f2eb2cb9120399e045969b5b8b4dadf939fc186afbcd2650cb397f7`

Policy: `NO_INPUT_OUTPUT_ALIAS_AND_ATOMIC_REPORT_WRITE`.

The canonical reporter now:

1. resolves output and input paths without requiring the final output to exist;
2. rejects resolved equality and existing-file identity through `os.path.samefile`;
3. writes a uniquely named temporary file in the destination directory;
4. completes CSV serialization, flushes, and `fsync`s the temporary file;
5. measures temporary-file bytes and SHA-256;
6. publishes only with `os.replace`;
7. removes temporary files on failure while preserving a pre-existing final report;
8. records the publication policy in CSV rows and returns/prints final output path, bytes, SHA-256, alias-check state, and atomic-publication state.

The report digest is returned and printed after publication rather than embedded in the same file, which would be self-referential.

## Regression and validation

Added `tests/test_compare_stopping_power_output_safety.py` (Git blob `776cbec3923ee4883bace045724ed652957afa59`, SHA-256 `29087d41927af1e0f932c329cdbffbc5e975c76fff6a2427caf00ce91e087139`).

Executed on exact local files whose Git blobs match the committed source and test:

```text
PYTHONPATH=. python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/audit_stopping_power_output_safety.py \
  tests/test_compare_stopping_power_output_safety.py \
  tests/test_compare_stopping_power_report_reproducibility.py \
  tests/test_compare_stopping_power_report_precision.py

PYTHONPATH=. python -m pytest \
  tests/test_compare_stopping_power_output_safety.py \
  tests/test_compare_stopping_power_report_reproducibility.py \
  tests/test_compare_stopping_power_report_precision.py -q

12 passed in 0.07s

PYTHONPATH=. python tools/audit/audit_stopping_power_output_safety.py \
  scripts/single_stave/compare_stopping_power.py

OUTPUT-SAFETY AUDIT: status=VALIDATED
```

Covered:

- direct CLI output equal to simulation input;
- direct CLI output equal to PSTAR reference input;
- resolved symlink alias;
- injected serialization failure;
- injected `os.replace` failure;
- preservation of existing final output on both failures;
- temporary-file cleanup;
- exact successful output bytes and SHA-256;
- compatibility with report precision and self-contained-report regressions;
- AST confirmation of alias guard, atomic helper, and absence of direct final-path writing.

Additional checks: validation JSON parsed; SVG parsed as XML; maximum changed Python line lengths were 91 for source and 93 for test.

## Evidence

- `docs/validation/stopping_power_output_safety_remediation_audit.md`
- `docs/validation/stopping_power_output_safety_remediation_validation.json`
- `docs/validation/stopping_power_output_safety_remediation.svg`

The SVG is explicitly synthetic software/provenance evidence, not detector data.

## Direct-main commit sequence before archive

- `b5ca01bba7b3dc0e3ee89e9939ad77f7998ab3e9` — `fix(single-stave): publish stopping-power reports atomically`
- `a99dfba46cf36c196566b08301b98fbe980aa2ba` — `test(single-stave): cover atomic report publication`
- `3b43970ee65db5fdcc9104d233765ae0a1e6b354` — `docs(validation): record atomic report publication`
- `48b7ad23ea7dd6cf5e81c055d84f973a0b47316d` — `docs(validation): add atomic report publication record`
- `625c38af6380a4950de323779242293331df7972` — `docs(validation): visualize atomic report publication`
- `4c0c6570be67660a61c184120036415b7ae902e5` — `docs(audit): complete atomic report publication task`
- `5868ae5022e580952b16f47b48892c741fbbac0b` — `docs(audit): close atomic report publication backlog`
- `871b1e09921614e902928b51abcd6a9a2e02736c` — `docs(audit): map atomic report publication`
- `2a894c89e48af90286fe922852b1a20f5151b6e4` — `docs(audit): ledger atomic report publication`
- `770ba0ab041b624d4fe9707dc95cc542da545b07` — `docs(audit): validate atomic report publication claim`
- `e7435804b73aff6074c88ddfde76d28226030bd1` — `docs(audit): update atomic report publication visual`
- `965f706aab15e3413d455a63ff07e5adc5527065` — `docs(audit): index atomic report publication`
- `822a5dcb5d1adff7a093518fd35135411962c47f` — `docs(audit): resolve atomic report publication blocker`

Every write was a successful direct-main GitHub commit. No force-push, history rewrite, task branch, or PR transport was used.

## Scientific boundary

No real Geant4 event export, ROOT output, accepted projectile total-energy-loss observable, secondary-escape calculation, energy-evolution integration, uncertainty budget, deuteron-reference validation, calibration, or detector-performance result was produced. Full repository pytest, ruff, Geant4/CTest, ROOT processing, real simulation execution, and GitHub Actions were not run. No broader CI or physics-closure success is claimed.

`AUD-G4-021` is COMPLETE and `BLK-G4-SP-004` is RESOLVED. Accepted stopping-power closure remains open under `AUD-G4-005`, `AUD-G4-011`, and `BLK-G4-SP-001`.
