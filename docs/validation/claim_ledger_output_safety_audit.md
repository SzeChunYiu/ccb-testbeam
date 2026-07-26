# Claim-ledger validator output-safety audit

## Scope

Task `AUD-LEDGER-002` reviews only the publication boundary of
`tools/audit/validate_claim_ledger_schema.py`. It does not validate the meaning,
truth type, uncertainty, source, or scientific acceptance of any claim-ledger row.

Policy:

`CLAIM_LEDGER_VALIDATION_OUTPUTS_MUST_BE_DISTINCT_AND_ATOMIC`

## Repository finding

The pre-change source is Git blob
`1961e63756b734db30a4a9a8037a756c291afe25`, validator version `1.0.0`.
Its JSON and SVG writers created parent directories and wrote directly to the
requested final path. The CLI did not check whether `--output` or `--svg` aliased
the canonical claim ledger or each other.

Consequences:

1. `validate_claim_ledger_schema.py docs/claim_ledger.csv --output docs/claim_ledger.csv`
   could replace the canonical CSV with JSON while returning the validation status.
2. A symlink or hard-link alias could cause the same destructive overwrite.
3. `--output` and `--svg` could name one path, leaving only the last serialization.
4. A failed or interrupted direct write could expose a truncated final artifact or
   destroy a previously valid report.

The independent former-algorithm control reconstructed the exact v1.0.0 JSON
publication operation (`Path.write_text` to the requested final path). It changed
the synthetic ledger SHA-256 from
`8ac3fd4271ac5f74666ff705e06e01463e2884fdb61a02542697faa43884b9c7`
to
`02256a1562f272f5010ea9418392880323338835e41adc729a0ef020c2ed902d`.
This control is explicitly an algorithm reconstruction, not execution of the
historical Git blob.

## Remediation

Validator version `1.1.0` now:

- rejects resolved-path, symlink, and existing hard-link aliases between the claim
  ledger, JSON output, and SVG output;
- creates a unique temporary file in the destination directory;
- writes strict UTF-8, flushes, and calls `fsync`;
- publishes with `os.replace`;
- removes temporary files after failures;
- maps publication failures to controlled CLI status `2`;
- records the output-safety policy in every validation payload;
- returns byte count, SHA-256, and publication method from the atomic writer.

The existing schema semantics remain unchanged: exact 43-column rows are
interpretable, width-mismatched rows are withheld, duplicates are findings, and
invalid UTF-8 or malformed CSV remains a controlled input error.

## Validation

Executed in the isolated validation fixture:

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

Additional checks:

- direct JSON-to-ledger alias: status `2`, input SHA-256 unchanged;
- symlinked SVG-to-ledger alias: status `2`, input bytes unchanged;
- JSON/SVG same-path request: status `2`, no output created;
- injected `os.replace` failure: status `2`, previous final output retained;
- temporary-file cleanup after injected failure: zero remaining files;
- validation JSON parsed successfully;
- SVG parsed successfully as XML;
- maximum changed Python line length: 96 characters.

## Version-controlled evidence

- `tests/test_claim_ledger_schema_output_safety.py`
- `tools/audit/render_claim_ledger_output_safety_evidence.py`
- `docs/validation/claim_ledger_output_safety_validation.json`
- `docs/validation/claim_ledger_output_safety.svg`

Validated local file identities before publication:

| Path | Bytes | SHA-256 | Git blob |
|---|---:|---|---|
| `tools/audit/validate_claim_ledger_schema.py` | 11977 | `ac4e9d2736a73592fb5f1d689c0613cd1435f0f075c6bf75402d7b4946bfadaf` | `55cadb30d52346eb27af2e9dee35e57c05829b52` |
| `tests/test_claim_ledger_schema_output_safety.py` | 3056 | `7ca9b3795cd6e6da553d4035f73ad06ddac5a4daa34e692477d2fbf824f9acf5` | `45c63d3a91d2f8403f8ca8fe00e7c014c3653be2` |
| `tools/audit/render_claim_ledger_output_safety_evidence.py` | 9332 | `44af56afcd4f3e280b94bc24e2f478850299a459ab880ee150c59a6c5e944b05` | `dd480d2726e8223763f5ecdaffb9483888ef0bd7` |
| `docs/validation/claim_ledger_output_safety_validation.json` | 2153 | `bde4ff7ab4d9cdd81ee81999ab77cf00d85069c62010d2737d4df91bb448bb48` | `9a9f6fb4ad207d3a03ee6d45e3926f8cc4f12831` |
| `docs/validation/claim_ledger_output_safety.svg` | 2331 | `962f6d79df0f0cf39caaa7e916d1192fb582b0000dc9889c516fa7a8edf7386b` | `47e9498ebf5a58c6087b2426700c6016ef1f3276` |

## Acceptance boundary

The focused output-publication remediation is `VALIDATED / COMPLETE`.

The current tracked schema-validation record reports 26/26 exact-width rows, but
this task does not independently re-evaluate the scientific support of those rows.
It does not close `AUD-LEDGER-001`, validate any claim value, authorize any status,
or establish any detector-performance result.

Repository-wide pytest, ruff, all downstream WIKI/claim validators, ROOT or
simulation processing, and GitHub Actions were not run in this isolated fixture.
