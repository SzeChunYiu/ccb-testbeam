# AUD-DELTAE-007 — DeltaE present-signal value integrity

## Session

- **Stamp:** `2026-07-26T050335Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `6c25424ae2507396d352d0b7e45d737752b2872d`
- **Task:** `AUD-DELTAE-007`
- **Policy:** `DELTAE_PRESENT_SIGNAL_CELLS_MUST_BE_FINITE_NUMERIC`
- **Missing-layer policy:** `ZERO_ONLY_WHEN_SUPPORTED_COLUMN_IS_ABSENT`
- **Destination:** direct commits to `main`; no branch, PR transport, force-push, or history rewrite.

## Start-of-run review

Reviewed repository metadata and permissions, current remote history, open draft PR #933, closed PR
#868, commit checks, all mandatory coordination records, the canonical DeltaE front door, retained
numerical/plotting core, existing DeltaE tests, prior CSV-key and Parquet provenance remediations,
backlog, blockers, and the previous handoff. No duplicate active task for this defect was found.

PR #933 remained draft, open, non-mergeable, and blocked by its red repository-wide integration gate.
PR #868 remained closed and unmerged. Neither was modified or merged.

## Confirmed defect

The retained numerical core blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414` used
`pd.to_numeric(..., errors="coerce").fillna(0.0)` for supported B-layer columns. Consequently a
present malformed or missing-value signal cell could silently become zero, while positive or
negative infinity could remain in the table. Extra MC `edep_B*` columns discovered dynamically for
full-energy and stopping calculations were not all subjected to a finite-value gate.

Exact former front-door blob: `a5c255a971a7cf672f011f84b91a3c7b64d1f209`.

This merged two different input states: a wholly absent supported detector layer and a present but
invalid measured cell. Only the former is eligible for the established zero-fill convention.

## Remediation

Commit `63348699fe3a507fb9008ee582b193c28c7a7b20` updates
`scripts/single_stave/deltaE_E.py` to:

1. coerce every present data `amp_B2/B4/B6/B8` cell to numeric;
2. reject every nonnumeric, missing-value, NaN, positive-infinite, or negative-infinite present cell;
3. discover and validate every present MC `edep_B*` column, including optional deeper layers;
4. zero-fill only a wholly absent supported downstream column;
5. raise `SignalValueError` with column, invalid count, and first row indices;
6. install strict preparation functions into the retained core's production path;
7. publish the signal-value and missing-layer policies in result and manifest contracts.

Corrected source identity:

- Git blob: `be00a58dbbc3c2b9de424c80bea3b5a4be6fe119`;
- bytes: `10349`;
- SHA-256: `ef51bec47aa15eada369a4e46f4036dfe4ba54409030aa18adf1a3d951165548`;
- maximum line length: `85`.

## Synthetic validation

Controls covered:

- malformed present data signal: former zero, current controlled rejection;
- NaN and both infinities in present data signals: current controlled rejection;
- malformed/nonfinite required and optional MC layers, including `edep_B10`: current rejection;
- wholly absent `amp_B8` or `edep_B8`: retained zero-fill behavior;
- finite numeric strings: converted without changing numerical values;
- result/manifest contract publication;
- production-hook replacement;
- error count and row-index reporting;
- strict source audit, malformed-contract mutation, invalid UTF-8, output aliasing, and atomic JSON.

Executed:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E.py \
  tools/audit/audit_deltae_signal_value_contract.py \
  tests/test_deltae_signal_value_contract.py \
  tests/test_audit_deltae_signal_value_contract.py \
  tools/audit/render_deltae_signal_value_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_deltae_signal_value_contract.py \
  tests/test_audit_deltae_signal_value_contract.py

19 passed in 3.06s
```

Environment: Python `3.13.5`, pandas `2.2.3`, NumPy `2.3.5`.

Additional checks: exact-source audit `VALIDATED` with zero findings; JSON parse passed; SVG XML
parse passed; changed Python lines were at most 100 characters.

The networkless validation checkout used the exact proposed front door/tests/auditor/renderer with a
minimal retained-core stub to exercise this focused boundary. A full repository checkout could not be
materialized because `github.com` DNS resolution failed. Repository-wide pytest/ruff, actual ROOT or
Parquet processing, GitHub Actions, and the complete link inventory were not run and are not claimed.

## Evidence

- `tests/test_deltae_signal_value_contract.py`
- `tools/audit/audit_deltae_signal_value_contract.py`
- `tests/test_audit_deltae_signal_value_contract.py`
- `tools/audit/render_deltae_signal_value_evidence.py`
- `docs/validation/deltae_signal_value_contract_validation.json`
- `docs/validation/deltae_signal_value_contract.svg`
- `docs/validation/deltae_signal_value_contract_audit.md`

The SVG is synthetic software/provenance evidence, not detector data.

## Direct-main commits before final coordination

- `6dc2d50c4d8d6a10f99ff2c5ab351c515d86cd18` — task claim;
- `63348699fe3a507fb9008ee582b193c28c7a7b20` — implementation;
- `03439cbb7b66e300a21eeadb4e8f880b8a10620c` — direct contract tests;
- `c08f1e23bc82eb8bcedf78694907e67133e621f3` — fail-closed audit;
- `cff6e38e947855a06bec096be07db37208697a15` — audit tests;
- `f38c2eb713d802ea3bbbde4f4c288989ad0f1c32` — evidence renderer;
- `115e2c7b3905d07d5c5d847b974961bdc85f8f5a` — machine-readable validation;
- `cf21c48f3231d3c6167a57f227d5c22d5a69d47b` — visual evidence;
- `bd4d1fc72c2d51e03cecadd21aa49523511d5a7f` — audit report;
- `ac029b8ffbb5efa2995ce942783bf571cc1642f7` — backlog synchronization.

## Scientific boundary and next action

Focused software integrity is `VALIDATED / COMPLETE`. No exact A-002 pulse table, amplitude
convention, pulse polarity, stopping fraction, DeltaE-E PID result, uncertainty budget, calibration,
or detector-performance result was produced. `AUD-DELTAE-001`, `AUD-DELTAE-002`, `AUD-AMP-009`,
`AUD-AMP-010`, and `BLK-AMP-001` remain open.

Next, obtain hash-bound A-002 convention and polarity evidence, then run the immutable production
table through the strict reader and present-signal gate before event-cardinality, uncertainty, plot,
and claim validation.

## Coordination limitation

The GitHub connector exposes complete-file replacement rather than byte-safe append for
`SESSION_LOG.md`, and the complete current append-only file could not be materialized in the
networkless checkout. A partial reconstruction was not written because it could erase prior
provenance. The final handoff records this unmet mandatory append explicitly.
