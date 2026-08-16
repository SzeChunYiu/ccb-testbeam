# Immutable Handoff — AUD-G4-012 PSTAR component-sum integrity

## Session

- **UTC:** 2026-07-23T17:41:35Z
- **Task:** `AUD-G4-012`
- **Owner:** scheduled ChatGPT scientific-review session
- **Initial remote main:** `ccc61c04b16000d338939b3bf04c03fa8ec6f56c`
- **Validated implementation/evidence head:** `1f3d4d4813890254d0990008b425a26c1a5a7bf2`
- **Session-log head before this archive:** `6765cc0c4b614993ba2c4ab9a6808fd6edd7f752`
- **Destination:** direct commits to `main`
- **Acceptance:** PARTIAL — exact committed-table component identity and a standalone fail-closed validator are validated; canonical comparison integration remains open.

## Start-of-run review

- Inspected current `main`, recent history, permissions, the previous `AUD-G4-010` handoff, `compare_stopping_power.py`, the strict PSTAR reference parser, simulation-table parser, tests, committed PSTAR table, validation records, and mandatory `chatgpt_todo/` files.
- Checked PR #868: closed, not merged, and non-mergeable. It was not modified.
- Direct local Git network access remained unavailable because `github.com` could not be resolved; authenticated GitHub connector reads and writes were used.
- No task branch, pull request, force-push, history rewrite, raw-data modification, or unrelated deletion was used.

## Authoritative scientific identity

NIST documentation defines proton total stopping power as the sum of electronic and nuclear stopping powers. The repository table exposes all three columns, but the canonical parser previously validated each field independently and did not test the cross-column identity.

## Confirmed defect

A row with a finite, positive, strictly ordered but incorrectly transcribed `total_MeV_cm2_g` value could pass `read_reference()` and directly alter the denominator of every reported simulation/reference ratio. Existing checks would not compare that total with `electronic_MeV_cm2_g + nuclear_MeV_cm2_g`.

## Validated implementation

Added `tools/audit/validate_pstar_component_sum.py` version 1.0.0. It:

- reads every noncomment row;
- requires energy, electronic, nuclear, and total columns;
- parses exact decimal tokens rather than binary floats;
- rejects missing, nonnumeric, nonfinite, nonphysical, excess-field, duplicate-energy, and out-of-order rows;
- assigns each written value a rounding interval of one half-unit in its last written decimal place;
- adds electronic and nuclear intervals;
- requires overlap with the declared-total interval;
- fails with status 2 and writes no validation JSON on an inconsistent row;
- records path, byte size, SHA-256, row count, identity, rounding model, and overlap-width extrema.

Added `tests/test_validate_pstar_component_sum.py` with coverage for:

- rounded NIST-style rows;
- scientific notation;
- exact byte/SHA-256 provenance;
- inconsistent total rejection;
- nonnumeric, nonfinite, and nonphysical values;
- fail-closed CLI behavior;
- successful machine-readable output.

## Exact committed-table validation

The complete PSTAR file was reconstructed from GitHub content chunks and its local Git blob identity was checked before execution.

- **Path:** `data/reference/stopping_power/pstar_polystyrene.csv`
- **GitHub blob:** `7e953dd346caedcee6da54180fb636b890a64040`
- **Reconstructed Git blob:** `7e953dd346caedcee6da54180fb636b890a64040`
- **Exact blob match:** yes
- **Bytes:** 7413
- **SHA-256:** `bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd`
- **Rows validated:** 141
- **Result:** all rows component-consistent under written decimal rounding
- **Minimum overlap width:** `0.0002615 MeV cm^2/g`
- **Maximum overlap width:** `0.110 MeV cm^2/g`

Command:

```bash
python tools/audit/validate_pstar_component_sum.py \
  data/reference/stopping_power/pstar_polystyrene.csv \
  --output /tmp/pstar_component_sum_validation_payload.json
```

Output:

```text
PSTAR component sum: status=VALIDATED rows=141 sha256=bc4d8b018115fd0892fe4ea22b6ec3da7be8ab65afa7595337c491ae6ed869dd
```

## Regression validation

```bash
python -m py_compile \
  tools/audit/validate_pstar_component_sum.py \
  tests/test_validate_pstar_component_sum.py

python -m pytest tests/test_validate_pstar_component_sum.py -q
```

Result:

```text
8 passed in 1.21s
```

Additional checks:

- exact table Git blob identity passed;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length was 87 characters.

Not run:

- full repository pytest;
- ruff;
- Geant4 build or CTest;
- ROOT or real simulation processing;
- GitHub Actions.

## Reproducible evidence

Added:

- `docs/validation/pstar_component_sum_audit.md`
- `docs/validation/pstar_component_sum_validation.json`
- `docs/validation/pstar_component_sum.svg`

The SVG is explicitly labelled as synthetic regression evidence and not detector data. It contrasts overlapping accepted rounding intervals with separated rejected intervals and states that no arbitrary floating-point tolerance is used.

## Direct-to-main commits

Implementation, tests, and evidence:

- `4af6004ac52b236561d525a390f9218015be373f` — `feat(audit): validate PSTAR component-sum identity`
- `2cf9c7ff37fe5e53c6b4ea2d9e6b34eeeadcc2f5` — `test(audit): cover PSTAR component-sum validation`
- `dc929c5c339914f7679323e79be0326bf6a57a1d` — `docs(validation): record PSTAR component-sum audit`
- `ae95c20b0f7621dd8eb04e4ba0bf7090e11c9dfb` — `docs(validation): add PSTAR component-sum validation record`
- `1f3d4d4813890254d0990008b425a26c1a5a7bf2` — `docs(validation): visualize PSTAR component-sum gate`

Coordination before this archive:

- `a7cf64a642b150a55b56dc13c2e6a7759657685f` — `docs(audit): claim PSTAR component-sum integrity task`
- `818f407dba3c2a67998f156dcf732f1b38b8ed33` — `docs(audit): track PSTAR component-sum integrity`
- `b7ec04b7c3f78518a25c3caa87a1c1d982c20282` — `docs(audit): index PSTAR component-sum integrity`
- `3fccd2afb24453952bb2437f27488c289cbfe336` — `docs(audit): map PSTAR component-sum validation`
- `a9010b49e6fa8b6ffce1230563b0d99125aabaad` — `docs(audit): record PSTAR component-sum study`
- `850e7baee56b8271f5486acde5d7d53014d6df5d` — `docs(audit): classify PSTAR component-sum claim`
- `e29958818344a2796e7bfd152d106eb7b2847ce4` — `docs(audit): register PSTAR component-sum visual`
- `b8a16ff032567afb7e7c0c7b2c32da41bf0a1028` — `docs(audit): register PSTAR component-sum integration blocker`
- `6765cc0c4b614993ba2c4ab9a6808fd6edd7f752` — `docs(audit): append PSTAR component-sum session`

## Repository-local coordination

Updated:

- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/MASTER_INDEX.md`
- `chatgpt_todo/CODE_RESULT_MAP.md`
- `chatgpt_todo/STUDY_REVIEW_LEDGER.md`
- `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`
- `chatgpt_todo/VISUALIZATION_MATRIX.md`
- `chatgpt_todo/BLOCKERS.md`
- `chatgpt_todo/SESSION_LOG.md`

Stable records added:

- `AUD-G4-012`
- `IDX-G4-014`
- `CRM-G4-012`
- `ST-G4-REF-002`
- `CL-G4-013`
- `VIS-G4-011`
- `BLK-G4-SP-002`

## Scientific boundary and unresolved risk

This run validates the internal total-component identity of the exact current PSTAR bytes. It does not:

- independently re-query NIST;
- prove every value was transcribed from the correct material/source;
- validate the deuteron velocity-scaling approximation;
- validate Geant4 local deposited energy as projectile total energy loss;
- run a real simulation comparison;
- establish calibration or detector performance.

The canonical comparison currently bypasses the standalone cross-column validator. A modified reference with a wrong but finite positive total may still reach the ratio calculation. `AUD-G4-012` therefore remains PARTIAL under `BLK-G4-SP-002`.

## Next action

Refactor the canonical reference ingestion so `compare_stopping_power.py` uses the same component-sum validation, add a direct-CLI regression that mutates one total field and requires status 2 with no numerical PASS, then run all existing stopping-power reference and simulation-input suites together.
