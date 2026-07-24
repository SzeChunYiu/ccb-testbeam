# Latest Scientific Review Handoff

## Session

- UTC: `2026-07-24T030404Z`
- Task: `AUD-G4-021`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `da94ca3f494b08209ed2d8f1d6d2cdc3ad85ac2c`
- Validated code/test/evidence head: `625c38af6380a4950de323779242293331df7972`
- Remote main after coordination and append-only session log, immediately before this final handoff: `ee808f4d78531eb69b2b56761a3516006ca6f039`
- Destination: direct to `main`
- Acceptance: COMPLETE for stopping-power output/input alias rejection and atomic report publication. Broader stopping-power physics closure remains open.

## Start-of-run and concurrent-work review

- Confirmed repository admin/push permission, default branch `main`, recent history, open PR inventory, current coordination records, and initial commit status.
- Based the implementation on current remote `main`; no task branch, pull request, force push, history rewrite, unrelated rollback, or destructive source-data change was used.
- PR #868 remains closed, unmerged, and non-mergeable. It was not modified or merged.
- `AUD-REPO-001` remains owned by another active session and was not duplicated.
- A direct clone failed because the runtime could not resolve `github.com`; exact files were reconstructed from authenticated GitHub contents and all repository writes were direct-main connector commits.
- A concurrent non-overlapping WIKI audit advanced `main` during this session. Subsequent coordination and session-log writes were based on the advanced remote head; no concurrent commit was discarded.

## Confirmed artifact-integrity defect

Pre-change source:

- path: `scripts/single_stave/compare_stopping_power.py`
- Git blob SHA-1: `360f3e46db664f4eead48021536f210e2f7a85c9`

After validating and reading simulation and PSTAR inputs, the reporter opened the requested final output directly with `out_path.open("w")`. The path had no explicit equality/identity check against either validated input and no temporary-file plus atomic-replacement publication path.

Consequences:

1. `--out` equal to `--sim` or `--reference`, including a resolving symlink or existing-file alias, could destroy the exact scientific input bytes required to reproduce the calculation.
2. A serialization, process, encoding, or filesystem failure after opening the final path could leave a truncated CSV under the canonical requested filename.

This was a software/provenance defect. It did not by itself establish or invalidate stopping-power physics.

## Corrected method

Current validated source:

- Git blob SHA-1: `043dbd8cae7362dede199b42b28aeb383bccde8d`
- file bytes: `23541`
- SHA-256: `aa9b2f854f2eb2cb9120399e045969b5b8b4dadf939fc186afbcd2650cb397f7`

Registered policy:

`NO_INPUT_OUTPUT_ALIAS_AND_ATOMIC_REPORT_WRITE`

The canonical reporter now:

1. expands and resolves output and input paths without requiring the final output to exist;
2. rejects resolved equality with either input;
3. additionally rejects identity between existing files through `os.path.samefile`, covering hard-link aliases;
4. performs the alias gate before reading either input;
5. serializes the complete CSV to a uniquely named `NamedTemporaryFile` in the destination directory;
6. flushes and `fsync`s the temporary file;
7. measures the completed temporary file's byte size and SHA-256;
8. publishes only with `os.replace(temp_path, out_path)`;
9. removes the temporary file after serialization or replacement failure and leaves any previous final report unchanged;
10. records the publication policy in every CSV row and returns/prints final path, byte size, SHA-256, alias-check state, and atomic-publication state.

The final digest is returned and printed after publication. It is intentionally not embedded as the digest of its own containing CSV, which would be self-referential.

## Regression, validation, and evidence

Added:

- `tests/test_compare_stopping_power_output_safety.py`
- `docs/validation/stopping_power_output_safety_remediation_audit.md`
- `docs/validation/stopping_power_output_safety_remediation_validation.json`
- `docs/validation/stopping_power_output_safety_remediation.svg`

The SVG is explicitly labelled synthetic software/provenance evidence, not detector data, and distinguishes paths using text, position, arrows, and cross-out marks rather than color alone.

Focused regression covers:

- direct CLI output equal to the simulation input;
- direct CLI output equal to the PSTAR reference input;
- resolved symlink output alias;
- injected CSV serialization failure;
- injected `os.replace` failure;
- exact preservation of input bytes and a pre-existing final report;
- cleanup of all temporary files after failure;
- exact final report byte-size and SHA-256 provenance;
- retention of the policy in machine-readable output;
- AST confirmation that the canonical reporter has an alias guard and atomic helper and no direct final-path write.

Executed on exact local files whose Git blobs match committed `main`:

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

Exact committed test:

- Git blob SHA-1: `776cbec3923ee4883bace045724ed652957afa59`
- SHA-256: `29087d41927af1e0f932c329cdbffbc5e975c76fff6a2427caf00ce91e087139`

Additional passed checks:

- validation JSON parse;
- SVG XML parse;
- maximum changed source line length: 91 characters;
- maximum new test line length: 93 characters;
- exact Git-blob identity for source and focused test.

Not run: full repository pytest, ruff, Geant4/CTest, ROOT processing, real simulation execution, or GitHub Actions. No broad CI or physics-closure success is claimed.

## Direct-to-main commit sequence

Implementation and evidence:

- `b5ca01bba7b3dc0e3ee89e9939ad77f7998ab3e9` — `fix(single-stave): publish stopping-power reports atomically`
- `a99dfba46cf36c196566b08301b98fbe980aa2ba` — `test(single-stave): cover atomic report publication`
- `3b43970ee65db5fdcc9104d233765ae0a1e6b354` — `docs(validation): record atomic report publication`
- `48b7ad23ea7dd6cf5e81c055d84f973a0b47316d` — `docs(validation): add atomic report publication record`
- `625c38af6380a4950de323779242293331df7972` — `docs(validation): visualize atomic report publication`

Coordination and provenance:

- `4c0c6570be67660a61c184120036415b7ae902e5` — `docs(audit): complete atomic report publication task`
- `5868ae5022e580952b16f47b48892c741fbbac0b` — `docs(audit): close atomic report publication backlog`
- `871b1e09921614e902928b51abcd6a9a2e02736c` — `docs(audit): map atomic report publication`
- `2a894c89e48af90286fe922852b1a20f5151b6e4` — `docs(audit): ledger atomic report publication`
- `770ba0ab041b624d4fe9707dc95cc542da545b07` — `docs(audit): validate atomic report publication claim`
- `e7435804b73aff6074c88ddfde76d28226030bd1` — `docs(audit): update atomic report publication visual`
- `965f706aab15e3413d455a63ff07e5adc5527065` — `docs(audit): index atomic report publication`
- `822a5dcb5d1adff7a093518fd35135411962c47f` — `docs(audit): resolve atomic report publication blocker`
- `e8b01b4414d2a797c5f97fe3ee98f88e99ad254a` — `docs(audit): archive atomic report publication remediation`
- `ee808f4d78531eb69b2b56761a3516006ca6f039` — `docs(audit): append atomic report publication session`

All operations returned successful direct-main GitHub commits. A local `git push` transcript is unavailable because DNS prevented a checkout; authenticated GitHub commit responses and subsequent remote-main reads are the push evidence. The commit containing this handoff is the final remote-main verification target and is confirmed separately after the write.

## `chatgpt_todo/` updates

Updated:

- `ACTIVE_TASK.md`
- `BACKLOG.md`
- `MASTER_INDEX.md`
- `CODE_RESULT_MAP.md`
- `STUDY_REVIEW_LEDGER.md`
- `CLAIM_EVIDENCE_MATRIX.md`
- `VISUALIZATION_MATRIX.md`
- `BLOCKERS.md`
- `SESSION_LOG.md`
- `HANDOFF.md`

Stable records now show:

- `AUD-G4-021`: COMPLETE
- `IDX-G4-023`: COMPLETE
- `CRM-G4-021`: COMPLETE
- `ST-G4-STOP-013`: COMPLETE
- `CL-G4-022`: COMPLETE
- `VIS-G4-021`: COMPLETE
- `BLK-G4-SP-004`: RESOLVED

Added immutable session record:

- `chatgpt_todo/archive/2026-07-24T030404Z_AUD-G4-021_OUTPUT_SAFETY_REMEDIATION.md`

`SESSION_LOG.md` was reconstructed from complete non-overlapping ranged reads of the same Git blob and appended without altering its prior bytes. Commit `ee808f4d78531eb69b2b56761a3516006ca6f039` records the append.

## Scientific boundary and next action

This run did not:

- process a real Geant4 event export or ROOT output;
- establish local deposited energy as projectile total energy loss;
- quantify energy carried by escaping generated secondaries;
- integrate projectile energy evolution along the path;
- evaluate statistical/systematic uncertainty or covariance;
- validate the deuteron equal-velocity proxy;
- establish Geant4/PSTAR agreement;
- produce calibration or detector-performance results.

`AUD-G4-021` is COMPLETE and `BLK-G4-SP-004` is RESOLVED. Accepted stopping-power closure remains open under `AUD-G4-005`, `AUD-G4-011`, and `BLK-G4-SP-001`.

The next accepted unit is to run the integrated CLI on immutable real proton exports and then perform a clean projectile-total-energy-loss closure using `G4EmCalculator::ComputeTotalDEDX` or primary entry/exit kinetic energy with path/reference integration, secondary-escape accounting, exact material/physics-list/cut/version provenance, a preregistered uncertainty budget, and required overlay/ratio/failure-diagnostic plots.
