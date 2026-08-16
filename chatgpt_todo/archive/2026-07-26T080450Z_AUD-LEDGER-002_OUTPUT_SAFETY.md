# Immutable handoff — AUD-LEDGER-002

## Session

- **Stamp:** `2026-07-26T080450Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `f28b166c836b3055b2ff1e110c15767ba075e72b`
- **Task:** prevent destructive or partial output publication by the canonical claim-ledger schema validator.
- **Policy:** `CLAIM_LEDGER_VALIDATION_OUTPUTS_MUST_BE_DISTINCT_AND_ATOMIC`.

## Repository facts

The pre-change validator was version `1.0.0`, Git blob
`1961e63756b734db30a4a9a8037a756c291afe25`. Its JSON and SVG writers used
`Path.write_text` directly on the requested final path. The CLI performed no
resolved-path, symlink, hard-link, or JSON/SVG pairwise alias check.

Therefore a command naming `docs/claim_ledger.csv` as `--output` or `--svg`
could replace the canonical claim ledger. A failed or interrupted direct write
could also expose a partial final artifact or destroy a previous valid report.

## Independent control

The former v1.0.0 JSON publication algorithm was reconstructed exactly from the
inspected writer operation. On a valid synthetic 43-column ledger it changed the
input SHA-256 from
`8ac3fd4271ac5f74666ff705e06e01463e2884fdb61a02542697faa43884b9c7`
to
`02256a1562f272f5010ea9418392880323338835e41adc729a0ef020c2ed902d`.
This is explicitly an independent algorithm reconstruction, not execution of the
historical Git blob.

## Remediation

Validator version `1.1.0` now:

- rejects aliases among the input ledger, JSON output, and SVG output;
- follows resolved paths and checks existing-file identity to catch symlinks and
  hard links;
- serializes to a unique same-directory temporary file;
- flushes and calls `fsync`;
- publishes using `os.replace`;
- removes temporary files on failure;
- preserves any previous final output when replacement fails;
- converts publication failure to controlled CLI status `2`;
- records `CLAIM_LEDGER_VALIDATION_OUTPUTS_MUST_BE_DISTINCT_AND_ATOMIC` in
  validation payloads;
- returns byte count, SHA-256, and publication method from the atomic writer.

Schema semantics were preserved: exact 43-column rows are interpretable,
width-mismatched rows are withheld, duplicate IDs are findings, and malformed CSV
or invalid UTF-8 remains a controlled error.

## Validation

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_schema.py \
  tests/test_validate_claim_ledger_schema.py \
  tests/test_claim_ledger_schema_output_safety.py \
  tools/audit/render_claim_ledger_output_safety_evidence.py

pytest -q \
  tests/test_validate_claim_ledger_schema.py \
  tests/test_claim_ledger_schema_output_safety.py

19 passed in 0.08s
```

Additional validated controls:

- direct JSON-to-ledger alias: status `2`, input unchanged;
- symlinked SVG-to-ledger alias: status `2`, input unchanged;
- JSON/SVG same destination: status `2`, no output created;
- injected `os.replace` failure: status `2`, previous output preserved;
- temporary files after injected failure: zero;
- JSON parse: passed;
- SVG XML parse: passed;
- maximum changed Python line length: 96;
- ruff was unavailable in the isolated execution environment and was not claimed.

## Versioned evidence

- `tools/audit/validate_claim_ledger_schema.py`
- `tests/test_claim_ledger_schema_output_safety.py`
- `tools/audit/render_claim_ledger_output_safety_evidence.py`
- `docs/validation/claim_ledger_output_safety_validation.json`
- `docs/validation/claim_ledger_output_safety.svg`
- `docs/validation/claim_ledger_output_safety_audit.md`

Validated identities:

- source blob `55cadb30d52346eb27af2e9dee35e57c05829b52`, SHA-256
  `ac4e9d2736a73592fb5f1d689c0613cd1435f0f075c6bf75402d7b4946bfadaf`;
- focused-test blob `45c63d3a91d2f8403f8ca8fe00e7c014c3653be2`, SHA-256
  `7ca9b3795cd6e6da553d4035f73ad06ddac5a4daa34e692477d2fbf824f9acf5`;
- renderer blob `dd480d2726e8223763f5ecdaffb9483888ef0bd7`;
- validation JSON blob `9a9f6fb4ad207d3a03ee6d45e3926f8cc4f12831`;
- SVG blob `47e9498ebf5a58c6087b2426700c6016ef1f3276`.

## Direct-main commits through core evidence

- `bb13b82ce7b3dceadf6624162869294e570e6ca5` — task claim;
- `1bc72041835d4613c11c25dd6ab6f8ab033b9020` — validator remediation;
- `cc4858817ee3a958d85a4b6d0f40a5bb21106436` — focused tests;
- `fd1e2b90e9f54775155cd81e00531dec870f8ee9` — evidence renderer;
- `f5165ba0c631516839fac80602fde42b33245857` — machine-readable evidence;
- `0282bc6dc91df58fde76ce5302e6d8bc2c9d8f3f` — visual evidence;
- `6db5e4e22535d1ce11884de63ba196170badc614` — audit report.

GitHub returned a successful commit SHA for every direct `main` contents write.
No branch, pull request, force update, or history rewrite was used.

## Acceptance boundary

Focused output-publication remediation: `VALIDATED / COMPLETE`.

The tracked schema record reports 26/26 exact-width rows, but this session did not
independently re-evaluate the scientific support, values, uncertainties, sources,
or statuses of those claims. `AUD-LEDGER-001` remains open for claim-level review.
No ROOT file, simulation, calibration, PID, timing, pile-up, stopping, or detector-
performance result was produced or authorized.

Repository-wide pytest, ruff, downstream WIKI/claim validators, ROOT processing,
simulation execution, link inventory, and GitHub Actions were not run.
