# Latest Scientific Review Handoff

## Session

- **UTC:** `2026-07-23T18:15:39Z`
- **Task:** `AUD-G4-012`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `bf295c1e7d295698673ffa7bb4c668c19015df49`
- **Validated implementation/evidence head:** `084b753685e5dc22a978482eef71f7649e352d3b`
- **Coordination/archive/session-log head before this handoff:** `3719b3ad713cd0e2023366279bea7cf866a60086`
- **Destination:** direct to `main`
- **Acceptance:** COMPLETE for canonical PSTAR component-identity integration, focused regression, visual evidence, coordination, archive, and append-only log; scientific stopping-power closure remains PARTIAL.

## Start-of-run and concurrent-work review

- Inspected current `main`, recent commits, repository permissions, open PR inventory, PR #868, the canonical stopping-power code, standalone reference and simulation validators, focused tests, exact PSTAR reference metadata, prior validation records, and every mandatory `chatgpt_todo/` file.
- PR #868 is closed, unmerged, and non-mergeable. It was not reopened, modified, or merged.
- Direct local clone remained unavailable because the runtime could not resolve `github.com`; authenticated connector reads and direct-main writes were used.
- No task branch, pull request, force-push, history rewrite, unrelated deletion, or raw-data modification was used.

## Confirmed defect

The prior run added a fail-closed exact-decimal validator for the PSTAR identity

```text
total_MeV_cm2_g = electronic_MeV_cm2_g + nuclear_MeV_cm2_g
```

but `scripts/single_stave/compare_stopping_power.py` retained an independent float parser. It rejected malformed, nonfinite, nonphysical, duplicate-energy, and out-of-order rows, but did not enforce the cross-column identity. A finite positive ordered row such as `1,9,1,8` could therefore enter a numerical simulation/reference ratio.

## Validated correction

### Canonical reference parser

`tools/audit/validate_pstar_component_sum.py` is now version `1.1.0` and exposes:

```python
read_validated_pstar_table(path)
```

The function validates every noncomment row and returns both canonical float rows and exact provenance. It requires:

- valid unique headers and all four required fields;
- exact Decimal parsing of written values;
- finite and physical values;
- strictly increasing energy in declared file order;
- overlap between the declared-total rounding interval and the electronic-plus-nuclear interval, using one half-unit in the last written decimal place.

### Canonical comparison integration

`compare_stopping_power.py` now imports that parser directly. No second PSTAR reference parser remains in the comparison path. Valid result rows and output CSVs record:

- `reference_input_sha256`;
- `reference_input_bytes`;
- `reference_rows_validated`;
- `reference_validator_version`;
- `reference_component_identity`;
- `reference_component_consistent`.

The CLI prints one `PSTAR REFERENCE VALIDATION` line before any numerical tolerance statement. The self-test uses the same validated reference path.

### Fail-closed direct CLI behavior

A synthetic reference containing `1,9,1,8` now:

- exits with status 2;
- reports the component inconsistency;
- writes no result CSV;
- prints no `NUMERICAL TOLERANCE: PASS`.

## Reproducible validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/validate_pstar_component_sum.py \
  tests/test_validate_pstar_component_sum.py \
  tests/test_compare_stopping_power_pstar_component_integration.py

python -m pytest \
  tests/test_validate_pstar_component_sum.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_quenched_proxy.py \
  tests/test_compare_stopping_power_sim_input_integration.py \
  tests/test_validate_stopping_power_sim_table.py -q

42 passed in 4.22s
```

Additional passed checks:

- validation JSON parsing;
- SVG XML parsing;
- maximum changed Python line length: 97;
- local SHA-256 values recorded in the validation JSON.

Not run:

- full repository pytest;
- ruff;
- Geant4 build and CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

No broader CI result or scientific stopping-power agreement is claimed.

## Reproducible evidence

Added:

- `docs/validation/pstar_component_sum_integration_audit.md`;
- `docs/validation/pstar_component_sum_integration_validation.json`;
- `docs/validation/pstar_component_sum_integration.svg`.

The SVG is explicitly labelled synthetic regression evidence, not detector data. It contrasts the former independent-parser path with shared exact-decimal status-2 rejection and no numerical PASS.

## Direct-to-main commits

Implementation, tests, and evidence:

- `b1b0d4b180c5a125a222c11795e4ada46adce2dc` — `fix(single-stave): integrate PSTAR component identity gate`
- `f13d9d9f1e845c7e15b6ae79d08b269dc67fed54` — `refactor(audit): expose canonical validated PSTAR rows`
- `a9c4c161715a02dbbe0efedb71734de70154e7e5` — `test(audit): cover canonical PSTAR row return`
- `fbedabdfed0d8588aa7dfdf0eea597d0372fdb56` — `test(single-stave): integrate PSTAR component identity gate`
- `1ec2487c70b70191c81cd7f2340ed425aacae7a3` — `docs(validation): record PSTAR component integration audit`
- `9c1271134c7ae08173d3acc079a0f1d57fc4aa6b` — `docs(validation): add PSTAR component integration record`
- `084b753685e5dc22a978482eef71f7649e352d3b` — `docs(validation): visualize PSTAR component integration gate`

Coordination and provenance:

- `36616f358291800d2f5fd97e9a353d6ee87f7cda` — active task completion
- `ea54802219b80123db0746befa9dac3640f4f992` — backlog completion
- `28a564545c9d0ef96f1197d8429e49d32e908237` — master index update
- `6744f91cc5b3560f4b96f2c9a8fc241c7f456d4a` — code-result mapping
- `8038e8458c4c89936dddec1e0beeaad24439004b` — study ledger update
- `672407761297f707f061fca8ca6ff6e1cecc7ca7` — claim matrix update
- `df85cbd960157ec420caf73dc96757d495a1541f` — visualization matrix update
- `d867cf8d769be2ef9bbb07a9b53c8c1d6e295e48` — blocker resolution
- `dd157ec98f176f785a9a3cacde3272671778836e` — immutable archive
- `3719b3ad713cd0e2023366279bea7cf866a60086` — append-only session log

Every write above returned a successful direct-main commit SHA. This handoff update is the final write for the session; its returned SHA must be re-read as remote `main` before delivery is reported.

## Repository-local records

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

Added immutable provenance:

- `chatgpt_todo/archive/2026-07-23T181539Z_AUD-G4-012_PSTAR_COMPONENT_INTEGRATION.md`

## Blockers and next action

### Resolved

`BLK-G4-SP-002` is RESOLVED. The canonical comparison can no longer bypass the PSTAR component identity.

### Still open

`BLK-G4-SP-001` remains OPEN. Local unquenched deposited energy is a diagnostic proxy and may differ from projectile total energy loss when secondaries escape or energy evolves along the path. The deuteron `S_d(E) ≈ S_p(E/2)` mapping remains approximate.

`AUD-G4-011` remains PARTIAL because no exact real exported Geant4 event table was available. A future real-table run must retain path, bytes, SHA-256, validated rows, particle/energy coverage, deposit basis, code commit, command, environment, output hash, and any rejection.

External NIST transcription/material provenance was not independently re-queried in this session.

## Scientific boundary

This session validates internal PSTAR component identity and its canonical software enforcement. It does not establish Geant4/PSTAR agreement, a detector calibration, or detector performance. No Geant4 executable, ROOT file, real event table, stopping-power closure, calibration, or detector-performance output was generated.
