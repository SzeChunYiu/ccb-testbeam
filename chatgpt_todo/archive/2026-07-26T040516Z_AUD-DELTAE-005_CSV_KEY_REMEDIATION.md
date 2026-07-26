# AUD-DELTAE-005 — CSV composite-key remediation

- **Session stamp:** `2026-07-26T040516Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `87e81a490dd9889901fbfb18604685bc2e437d27`
- **Task:** `AUD-DELTAE-005`
- **Policy:** `DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`
- **Focused status:** `VALIDATED / COMPLETE`
- **Cumulative A-002 physics status:** `PARTIAL / BLOCKED`

## Start-of-run review

Fetched current `main`, recent history, repository permissions, commit status, open PR inventory,
closed PR #868 state, `chatgpt_todo/README.md`, `BACKLOG.md`, `ACTIVE_TASK.md`, `HANDOFF.md`,
`SESSION_LOG.md`, the canonical DeltaE source, its existing tests, the fail-closed key-identity audit,
and its validation evidence. No concurrent commit advanced `main` during the implementation writes.
PR #933 remained draft, open, unmergeable, and unmerged. PR #868 remained closed and unmerged.

## Confirmed defect

The former canonical source blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414` declared the
event key `(source_file_id, run_id, event_id)` but called default `pandas.read_csv(path)`. In a
deterministic control, exact `source_file_id` tokens `001` and `1` both became integer `1`, reducing
two exact keys to one and creating one false data/MC inner-join match. Post-read string conversion
cannot recover a lost leading zero or undo a match already created by type inference.

## Better-method decision

- Protecting only `source_file_id` was rejected because all three columns define identity.
- Post-read string conversion was rejected because it is irreversible after lossy inference.
- Re-reading the path for provenance was rejected because the path can be replaced after parsing.
- Removing CSV support was rejected because it is an established documented workflow.
- Rewriting the full reviewed analysis was rejected as unnecessary risk.

The selected design preserves the original 761-line numerical and plotting implementation
byte-for-byte as `scripts/single_stave/_deltaE_E_core.py`, while a small canonical front door owns
the reader and provenance contract.

## Remediation

The canonical `scripts/single_stave/deltaE_E.py` now:

1. reads each CSV-like input once using `Path.read_bytes()`;
2. decodes strict UTF-8;
3. parses `source_file_id`, `run_id`, and `event_id` with pandas string dtypes;
4. retains byte count and SHA-256 from the same parsed snapshot;
5. reuses that same-snapshot provenance in `manifest.json`;
6. publishes the reader policy, snapshot policy, and dtype map in result and manifest metadata;
7. rejects invalid UTF-8 before key validation or joining.

Implementation identities:

- front-door commit `0565f4bc29c5d8230cd84c767339105adc28e5d6`;
- front-door Git blob `90e0709f5f065062bb4dc9f990975992a53d76b1`;
- front-door bytes `5854`;
- front-door SHA-256 `edbf8f5513a39c95fdab7a6f895c7b5a4868ee1dad0b41148f195ceeab1c9c21`;
- retained-core Git blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414`;
- regression Git blob `0c9fdf933e4749a2fbbd585c4a831cdc428ae599`.

## Validation

Executed against the exact committed front-door bytes in the available local environment:

```text
python -m py_compile deltaE_E.py test_deltae_csv_key_remediation.py
PYTHONPATH=. pytest -q test_wrapper.py
4 passed in 0.03s
```

Environment: Python `3.13.5`, pandas `2.2.3`.

Validated controls:

- `001`, `0007`, and `0009` remain exact strings;
- distinct `001` versus `1` inputs yield zero false matches;
- invalid UTF-8 fails before parsing;
- replacing the path after parsing does not alter the manifest byte count or SHA-256;
- the result publishes the reader contract;
- an AST-equivalent source check found `read_bytes`, strict `decode`, `read_csv(..., dtype=...)`,
  the policy token, and all three key tokens in `read_table()`;
- JSON parsing and SVG XML parsing passed;
- maximum changed Python line lengths were 87 and 96 characters.

The committed full-repository regressions also require the exact-source audit to return zero findings
and execute the CSV-backed CLI. They were not run locally because the networkless execution container
could not materialize the retained core from GitHub, although the implementation commit preserves it
by exact Git blob identity. No GitHub Actions run or attached status check was available for the
implementation commit; repository-wide pytest and ruff are not claimed.

## Evidence

- `tests/test_deltae_csv_key_remediation.py`
- `docs/validation/deltae_csv_key_identity_validation.json`
- `docs/validation/deltae_csv_key_identity.svg`
- `docs/validation/deltae_csv_key_identity_audit.md`

## Direct-main commits before coordination

- `746789f640d9d066b9aa4749784073288ca1a248` — preserve CSV composite-key identity;
- `0565f4bc29c5d8230cd84c767339105adc28e5d6` — bind the audit to the strict reader body;
- `43e7181235864a7a7f93d920aee7ac04917f2528` — update machine-readable, visual, and narrative evidence.

Every branch ref update used `force=false`; GitHub returned `success=true`. No task branch, pull
request, force-push, or history rewrite was used.

## Scientific boundary

No exact A-002 pulse table, ROOT file, stopping fraction, DeltaE-E PID result, uncertainty budget,
calibration, or detector-performance result was produced. Amplitude convention and polarity remain
blocked under `AUD-DELTAE-001`, `AUD-DELTAE-002`, and `BLK-AMP-001`. The next scientific step is an
immutable production rerun only after those evidence gates pass.
