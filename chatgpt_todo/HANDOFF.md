# Latest Handoff

## Session

- **UTC:** 2026-07-23T17:41:35Z
- **Task:** `AUD-G4-012`
- **Initial remote main:** `ccc61c04b16000d338939b3bf04c03fa8ec6f56c`
- **Validated implementation/evidence head:** `1f3d4d4813890254d0990008b425a26c1a5a7bf2`
- **Coordination/archive head before this handoff:** `a1c60b73754a649becd8b7e5e51148c3298b2194`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** `main`
- **Acceptance:** COMPLETE for the exact current PSTAR table's internal component identity, standalone fail-closed validation, focused tests, visual evidence, coordination, append-only log, and direct-main delivery; PARTIAL for canonical comparison integration, independent external-source verification, and accepted Geant4 stopping-power closure.

## Start-of-run and concurrent-work review

- Inspected current `main`, recent history, repository permissions, previous `AUD-G4-010` handoff, stopping-power code/tests/reference data, prior validation records, and every mandatory `chatgpt_todo/` record.
- PR #868 was rechecked: closed, not merged, and non-mergeable. It was not modified or merged.
- No task branch, pull request, force-push, history rewrite, raw-data modification, or unrelated deletion was used.
- Direct local Git network access remained unavailable because this runtime could not resolve `github.com`; authenticated connector reads and direct-to-main writes were used.

## Confirmed scientific/numerical defect

NIST defines proton total stopping power as the sum of electronic and nuclear stopping powers. The committed reference contains all three columns, but `compare_stopping_power.py::read_reference()` previously validated each field independently without testing the cross-column identity.

A finite, positive, ordered row with an incorrectly transcribed `total_MeV_cm2_g` could therefore pass existing structural checks and bias every simulation/reference ratio.

## Validated implementation

Added `tools/audit/validate_pstar_component_sum.py` version 1.0.0. It:

- requires energy, electronic, nuclear, and total columns;
- parses exact decimal tokens;
- rejects missing, nonnumeric, nonfinite, nonphysical, excess-field, duplicate-energy, and out-of-order rows;
- assigns each written value a rounding interval of one half-unit in its last written decimal place;
- forms the `electronic + nuclear` interval;
- requires overlap with the declared-total interval;
- returns status 2 and writes no output JSON for an inconsistent row;
- records exact path, bytes, SHA-256, row count, identity, rounding model, and overlap extrema.

Added `tests/test_validate_pstar_component_sum.py` covering rounded NIST-style rows, scientific notation, exact provenance, inconsistent totals, invalid values, fail-closed CLI behavior, and normalized JSON output.

## Exact committed-table validation

The complete committed CSV was reconstructed from GitHub content and checked for exact Git blob identity before execution.

- **Path:** `data/reference/stopping_power/pstar_polystyrene.csv`
- **GitHub blob:** `7e953dd346caedcee6da54180fb636b890a64040`
- **Reconstructed Git blob:** `7e953dd346caedcee6da54180fb636b890a64040`
- **Exact blob match:** yes
- **Bytes:** 7413
- **SHA-256:** `bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd`
- **Rows validated:** 141
- **Result:** 141/141 rows component-consistent under written decimal rounding
- **Minimum overlap width:** `0.0002615 MeV cm^2/g`
- **Maximum overlap width:** `0.110 MeV cm^2/g`

Command and output:

```text
python tools/audit/validate_pstar_component_sum.py \
  data/reference/stopping_power/pstar_polystyrene.csv \
  --output /tmp/pstar_component_sum_validation_payload.json

PSTAR component sum: status=VALIDATED rows=141 sha256=bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd
```

## Reproducible regression validation

```text
python -m py_compile \
  tools/audit/validate_pstar_component_sum.py \
  tests/test_validate_pstar_component_sum.py

python -m pytest tests/test_validate_pstar_component_sum.py -q

8 passed in 1.21s
```

Additional passed checks:

- exact PSTAR Git blob identity;
- validation JSON parsing;
- SVG XML parsing;
- changed-Python maximum line length: 87 characters.

Not run:

- full repository pytest;
- ruff;
- Geant4 build/CTest;
- ROOT or real simulation processing;
- GitHub Actions.

No broader CI, accepted stopping-power closure, calibration, or detector-performance result is claimed.

## Reproducible evidence

Added:

- `docs/validation/pstar_component_sum_audit.md`;
- `docs/validation/pstar_component_sum_validation.json`;
- `docs/validation/pstar_component_sum.svg`.

The SVG is explicitly labelled synthetic regression evidence—not detector data—and distinguishes accepted overlap from rejected interval separation using position and text as well as color.

## Direct-to-main commits

Implementation, tests, and evidence:

- `4af6004ac52b236561d525a390f9218015be373f` — `feat(audit): validate PSTAR component-sum identity`
- `2cf9c7ff37fe5e53c6b4ea2d9e6b34eeeadcc2f5` — `test(audit): cover PSTAR component-sum validation`
- `dc929c5c339914f7679323e79be0326bf6a57a1d` — `docs(validation): record PSTAR component-sum audit`
- `ae95c20b0f7621dd8eb04e4ba0bf7090e11c9dfb` — `docs(validation): add PSTAR component-sum validation record`
- `1f3d4d4813890254d0990008b425a26c1a5a7bf2` — `docs(validation): visualize PSTAR component-sum gate`

Coordination and provenance:

- `a7cf64a642b150a55b56dc13c2e6a7759657685f` — `docs(audit): claim PSTAR component-sum integrity task`
- `818f407dba3c2a67998f156dcf732f1b38b8ed33` — `docs(audit): track PSTAR component-sum integrity`
- `b7ec04b7c3f78518a25c3caa87a1c1d982c20282` — `docs(audit): index PSTAR component-sum integrity`
- `3fccd2afb24453952bb2437f27488c289cbfe336` — `docs(audit): map PSTAR component-sum validation`
- `a9010b49e6fa8b6ffce1230563b0d99125aabaad` — `docs(audit): record PSTAR component-sum study`
- `850e7baee56b8271f5486acde5d7d53014d6df5d` — `docs(audit): classify PSTAR component-sum claim`
- `e29958818344a2796e7bfd152d106eb7b2847ce4` — `docs(audit): register PSTAR component-sum visual`
- `b8a16ff032567afb7e7c0c7b2c32da41bf0a1028` — `docs(audit): register PSTAR component-sum integration blocker`
- `6765cc0c4b614993ba2c4ab9a6808fd6edd7f752` — `docs(audit): append PSTAR component-sum session`
- `a1c60b73754a649becd8b7e5e51148c3298b2194` — `docs(audit): archive PSTAR component-sum integrity`

This handoff update is the final direct-main write and its returned commit must be confirmed as remote `main` before delivery is reported.

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
- `SESSION_LOG.md`;
- `HANDOFF.md`.

Added immutable provenance:

- `archive/2026-07-23T174135Z_AUD-G4-012_PSTAR_COMPONENT_SUM.md`.

Stable IDs:

- `AUD-G4-012`;
- `IDX-G4-014`;
- `CRM-G4-012`;
- `ST-G4-REF-002`;
- `CL-G4-013`;
- `VIS-G4-011`;
- `BLK-G4-SP-002`.

## Scientific boundary and next action

The exact current PSTAR bytes pass the component identity. This does not independently prove the source transcription, material identity, Geant4 observable, deuteron approximation, calibration, or detector performance.

The new validator is standalone. `compare_stopping_power.py` can still be called directly with a modified reference table whose total is finite and positive but component-inconsistent. `AUD-G4-012` therefore remains PARTIAL under `BLK-G4-SP-002`.

Next:

1. expose one canonical validated PSTAR parser or invoke the component-sum gate in `compare_stopping_power.py`;
2. add a direct-CLI regression that mutates one total value and requires status 2 with no numerical PASS;
3. rerun all stopping-power reference and simulation-input suites together;
4. preserve exact reference and output hashes;
5. keep accepted physics closure separate under `AUD-G4-005` / `BLK-G4-SP-001`.
