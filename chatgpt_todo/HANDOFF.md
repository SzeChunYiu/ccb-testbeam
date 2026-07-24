# Latest Scientific Review Handoff

## Session

- UTC: `2026-07-24T020230Z`
- Task: `AUD-G4-021`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `cdaf032c13f9967ad2a02c420987058b8a57a61b`
- Validated audit/test/evidence head: `ef388f3fc90e8d81804d277dbbe7840ae4ae4a27`
- Remote main immediately before final handoff: `2602611bccd62117ebe10664e6e3223549ae5f1e`
- Destination: direct to `main`
- Acceptance: `PARTIAL`; the output-safety defect and remediation contract are validated, but the canonical reporter remains unchanged.

## Start-of-run and concurrent-work review

- Confirmed repository admin/push permission, default branch `main`, recent history, open PR inventory, current coordination records, and initial commit status.
- Initial `main` had no attached status checks.
- Based every write on current remote `main`; no task branch, PR, force push, history rewrite, or unrelated rollback was used.
- PR #868 remains closed, unmerged, and non-mergeable. It was not modified or merged.
- `AUD-REPO-001` remains owned by a concurrent session and was not duplicated.
- A direct clone failed because the runtime could not resolve `github.com`; complete source ranges and direct-main writes used the authenticated GitHub connector.

## Confirmed artifact-integrity defect

Current source inspected:

- path: `scripts/single_stave/compare_stopping_power.py`
- Git blob SHA-1: `360f3e46db664f4eead48021536f210e2f7a85c9`

After validating and reading the simulation and PSTAR inputs, `run_compare()` writes the report directly through:

```python
with out_path.open("w", newline="") as handle:
```

The canonical path has no explicit output-versus-input alias rejection and no temporary-file plus atomic-replacement publication step.

Consequences:

1. `--out` equal to `--sim` or `--reference` can replace the exact validated input bytes with a derived CSV. The current invocation may finish from in-memory rows, but its reproduction provenance has been destroyed.
2. A serialization, process, encoding, or filesystem failure after opening the final path can leave an incomplete CSV under the canonical requested filename.

This is a software/provenance defect. It does not by itself establish or invalidate stopping-power physics.

## Better method and policy

Registered policy:

`NO_INPUT_OUTPUT_ALIAS_AND_ATOMIC_REPORT_WRITE`

A complete remediation must:

1. resolve input and output paths without requiring the output to exist;
2. reject output paths that alias either validated input, including resolved symlink equality where supported;
3. serialize the full CSV to a same-directory temporary file;
4. close that file successfully;
5. publish only through `os.replace(temp_path, out_path)`;
6. remove temporary files on failure and preserve any previous final report;
7. add direct CLI regressions for both aliases and injected write failure;
8. report final output byte size and SHA-256.

## Audit tool, tests, and evidence

Added:

- `tools/audit/audit_stopping_power_output_safety.py` v1.0.0
- `tests/test_audit_stopping_power_output_safety.py`
- `docs/validation/stopping_power_output_safety_audit.md`
- `docs/validation/stopping_power_output_safety_validation.json`
- `docs/validation/stopping_power_output_safety.svg`

The AST audit checks `run_compare()` for a direct final-path write, an explicit `_validate_output_path(...)` gate, and an atomic `_write_report_atomically(...)` or `os.replace(...)` path. It returns status 0 for a validated implementation, 1 for a confirmed flaw, and 2 for controlled source-read/UTF-8/parse/entry-point errors.

The SVG is explicitly synthetic software/provenance evidence—not detector data—and uses text, position, arrows, and cross-out marks rather than color alone.

## Validation commands and results

Executed in a reconstructed local audit workspace:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_stopping_power_output_safety.py \
  tests/test_audit_stopping_power_output_safety.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_stopping_power_output_safety.py -q

5 passed in 1.63s
```

Additional passed checks:

- validation JSON parse;
- SVG XML parse;
- maximum audit-tool line length: 91 characters;
- maximum test line length: 92 characters.

The exact complete canonical source was inspected through authenticated GitHub ranges but was not executed locally. Executable regression used synthetic vulnerable and fixed source controls. No full repository pytest, ruff, Geant4/CTest, ROOT processing, real simulation, or GitHub Actions success is claimed.

## Direct-to-main commit sequence

- `3e5907c51eb01ce4db3dd07d7fee81f96320c9dd` — `docs(audit): activate stopping-power output safety audit`
- `089f8e49f7e1b283569dc5a1fac13f90b5c141d0` — `feat(audit): detect unsafe stopping-power report writes`
- `bed21d9ae9db1e39d6dcb2114a38c992666b9896` — `test(audit): cover stopping-power output safety audit`
- `e1c0f11f1fb9bafc927b015d1be60d68ac024cdc` — `docs(validation): record stopping-power output safety flaw`
- `ccac9327d7b7949ee1aee91f775280a08e70bb30` — `docs(validation): add stopping-power output safety record`
- `ef388f3fc90e8d81804d277dbbe7840ae4ae4a27` — `docs(validation): visualize stopping-power output safety`
- `200248fd62dfe1460834f933c7793b6e3c8e40f1` — `docs(audit): register stopping-power output safety task`
- `efb914de128759babe72c06262796f0ecb6a7791` — `docs(audit): index stopping-power output safety flaw`
- `9adfbb7c5930ee3bbaa5d9c5602b608fc45e4eed` — `docs(audit): map stopping-power output safety flaw`
- `9e9959259e1c499dbdca070921e7785ea58b38ff` — `docs(audit): ledger stopping-power output safety flaw`
- `67ffc8bf2f9689defab2a280680230a3e921602e` — `docs(audit): classify stopping-power output safety claim`
- `524648614c5c8a421e9401c9f6cfff478846db3c` — `docs(audit): register stopping-power output safety visual`
- `6e10c2e0f3364fada18a3bf4ea939ad9a7b6fa29` — `docs(audit): block unsafe stopping-power report publication`
- `fbb7f8af3235e3493b0e86529886d0ae8c3ae7ef` — `docs(audit): complete stopping-power output safety audit`
- `2602611bccd62117ebe10664e6e3223549ae5f1e` — `docs(audit): archive stopping-power output safety audit`

All operations returned successful direct-main GitHub commits. A local `git push` transcript is unavailable because DNS prevented a checkout; the final handoff commit must be separately verified as remote-main head.

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
- `HANDOFF.md`

Added stable records:

- `AUD-G4-021`
- `IDX-G4-023`
- `CRM-G4-021`
- `ST-G4-STOP-013`
- `CL-G4-022`
- `VIS-G4-021`
- `BLK-G4-SP-004`

Added immutable session record:

- `chatgpt_todo/archive/2026-07-24T020230Z_AUD-G4-021_OUTPUT_SAFETY.md`

`SESSION_LOG.md` was not overwritten. The connector exposes whole-file replacement rather than a byte-safe append operation; manually reconstructing the append-only history from ranged responses would create avoidable provenance-loss risk. The immutable archive and this handoff retain the complete run record, and the missing append is an explicit coordination limitation.

## Scientific boundary and status

This run did not:

- modify the canonical stopping-power reporter;
- process a real Geant4 export;
- validate local deposited energy as projectile total energy loss;
- evaluate statistical/systematic uncertainty;
- establish proton or deuteron Geant4/PSTAR agreement;
- produce calibration or detector-performance results.

`AUD-G4-021` is `PARTIAL`; `BLK-G4-SP-004` is `OPEN`; accepted stopping-power closure remains open under `BLK-G4-SP-001`, `AUD-G4-005`, and `AUD-G4-011`.

## Required next action

Modify `compare_stopping_power.py` to reject output/input aliases and publish atomically, add direct CLI regressions that prove input bytes and pre-existing outputs survive failure, record the final report digest, run the supported stopping-power regression set, and only then mark `AUD-G4-021` complete.
