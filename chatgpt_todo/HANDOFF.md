# Latest Handoff

## Session

- **Task:** `AUD-DELTAE-005`
- **Stamp:** `2026-07-26T040516Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `87e81a490dd9889901fbfb18604685bc2e437d27`
- **Validated delivery/handoff commit:** `df3d3dd341fc16f925c3a3f8689aacb65cd74c66`
- **Remote-main confirmation:** post-write history confirmed the delivery commit and every focused
  ancestor consecutively on remote `main`.
- **Destination:** direct commits to `main`; every `update_ref` used `force=false` and returned
  `success=true`; no task branch, force-push, history rewrite, or PR transport.
- **Focused acceptance:** canonical CSV reader and same-snapshot provenance `VALIDATED / COMPLETE`.
- **Scientific acceptance:** A-002 physics result remains `PARTIAL / BLOCKED`.

## Start-of-run review

Fetched current `main`, recent history, repository permissions, commit status, open PR #933, closed
PR #868, all mandatory coordination records, the canonical DeltaE source and tests, the existing
key-identity audit, renderer, and validation evidence. PR #933 remained draft, open, unmergeable,
and unmerged. PR #868 remained closed and unmerged. No concurrent commit advanced `main` during the
focused implementation sequence.

## Confirmed defect

Former source blob `fe5dd5e4673f32fa5a4b94776531f2b392e12414` declared the composite key
`(source_file_id, run_id, event_id)` but used default `pandas.read_csv(path)`. Exact tokens `001` and
`1` both became integer `1`, reducing two exact keys to one and creating one false data/MC inner-join
match. Casting after parsing cannot recover leading zeros or undo a match already created.

Policy:

`DELTAE_CSV_COMPOSITE_KEYS_MUST_BE_READ_AS_LOSSLESS_TEXT`

## Remediation

The canonical front door now reads CSV-like inputs once as bytes, decodes strict UTF-8, parses all
three key columns with pandas string dtypes, and retains byte count and SHA-256 from the same parsed
snapshot. `result.json` and `manifest.json` publish the reader policy, snapshot policy, and dtype map;
the manifest reuses the retained snapshot rather than re-reading a mutable path.

The complete former numerical/plotting implementation is retained byte-for-byte at
`scripts/single_stave/_deltaE_E_core.py`. This isolates the input correction and avoids unrelated
changes to the reviewed 761-line analysis core.

## Files changed

- `scripts/single_stave/deltaE_E.py`
- `scripts/single_stave/_deltaE_E_core.py`
- `tests/test_deltae_csv_key_remediation.py`
- `docs/validation/deltae_csv_key_identity_validation.json`
- `docs/validation/deltae_csv_key_identity.svg`
- `docs/validation/deltae_csv_key_identity_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/SESSION_LOG.md`
- `chatgpt_todo/archive/2026-07-26T040516Z_AUD-DELTAE-005_CSV_KEY_REMEDIATION.md`
- this handoff.

## Exact identities

- front-door blob: `90e0709f5f065062bb4dc9f990975992a53d76b1`;
- front-door bytes: `5854`;
- front-door SHA-256: `edbf8f5513a39c95fdab7a6f895c7b5a4868ee1dad0b41148f195ceeab1c9c21`;
- retained-core blob: `fe5dd5e4673f32fa5a4b94776531f2b392e12414`;
- regression blob: `0c9fdf933e4749a2fbbd585c4a831cdc428ae599`.

## Validation

Executed against the exact committed front-door bytes:

```text
python -m py_compile deltaE_E.py test_deltae_csv_key_remediation.py
PYTHONPATH=. pytest -q test_wrapper.py
4 passed in 0.03s
```

Environment: Python `3.13.5`, pandas `2.2.3`.

Validated behavior:

- `001`, `0007`, and `0009` remain exact strings;
- distinct `001` versus `1` inputs produce zero false matches;
- invalid UTF-8 fails before parsing;
- a post-read path mutation does not change manifest bytes or SHA-256;
- result metadata publishes the reader contract;
- AST-equivalent checks found `read_bytes`, strict `decode`, explicit `dtype`, policy, and all keys;
- JSON and SVG parsing passed;
- changed Python line lengths are at most 96 characters.

The committed repository regression additionally requires the exact-source audit to return zero
findings and performs a direct CSV-backed CLI run. Those two full-repository tests were not locally
executed because the networkless container could not materialize the retained core, although the
implementation commit preserves it by exact Git blob identity. No Actions run or attached status
check was available; repository-wide pytest and ruff are not claimed.

## Direct-main commits

- `746789f640d9d066b9aa4749784073288ca1a248` — `fix(deltae): preserve CSV composite-key identity`;
- `0565f4bc29c5d8230cd84c767339105adc28e5d6` —
  `fix(deltae): bind audit to strict reader body`;
- `43e7181235864a7a7f93d920aee7ac04917f2528` —
  `docs(validation): record DeltaE CSV key remediation`;
- `1ffddad85558e1008e5e7f61b3622b8121f8d78f` —
  `docs(audit): archive DeltaE CSV key remediation`;
- `df3d3dd341fc16f925c3a3f8689aacb65cd74c66` —
  `docs(audit): hand off DeltaE CSV key remediation`.

GitHub returned `success=true` for each non-forced `main` ref update. Post-write remote history
confirmed `df3d3dd341fc16f925c3a3f8689aacb65cd74c66` and all focused ancestors consecutively on `main`.

## Scientific boundary and next action

No exact A-002 pulse table, ROOT file, amplitude convention, pulse polarity, stopping fraction,
DeltaE-E PID result, uncertainty budget, calibration, or detector-performance result was produced.
`AUD-DELTAE-001`, `AUD-DELTAE-002`, and `BLK-AMP-001` remain open. The next scientific step is to
bind immutable convention/polarity evidence and execute a content-addressed production rerun through
this strict input boundary, followed by cardinality, uncertainty, plot, and claim validation.
