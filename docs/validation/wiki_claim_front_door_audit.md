# WIKI claim front-door consistency audit

## Scope

This audit checks the public repository `WIKI.md` front door against the canonical
`docs/claim_ledger.csv`. It is a documentation and claim-governance review, not a
new detector-data or simulation result.

Repository source inspected on `main`:

- `WIKI.md` blob `c27a1e555145cb248e253f17a6f6d1cfe64542a8`;
- `docs/claim_ledger.csv` blob `6f4d4023814b42a566826912bcef7df9903c41e7`.

The exact relevant WIKI ranges were the front matter, confidence-status legend,
canonical results table, timing key-results table, and MC validation matrix. The
canonical ledger records used were `CL-007` and `CL-011`.

## Confirmed inconsistencies

1. The WIKI uses `PASS` three times for the MV4 raw timing-pull claim. `PASS` is
   absent from the WIKI's own confidence-status legend, while authoritative
   ledger record `CL-007` classifies the claim as `VALIDATED`.
2. The WIKI canonical table labels the effective live-time truth type as
   `data_only`. Ledger record `CL-011` uses `data_mc_self_consistent` and notes
   that the truth classification was upgraded during review.
3. The front matter says `Every number has uncertainty.` The claim ledger still
   contains explicit `CI_MISSING_BLOCKING` entries, including the raw timing
   pull and effective live-time records. The sentence therefore overstates the
   completeness of the uncertainty inventory.

These are public claim-state inconsistencies. They do not change the underlying
numerical values, but they can cause readers and downstream summaries to assign
unsupported confidence or provenance.

## Better method

The public front door should be generated or checked against the canonical
ledger. The registered policy is:

`WIKI_FRONT_DOOR_MUST_MATCH_CANONICAL_LEDGER`

A safe remediation must:

- replace the three MV4 raw `PASS` labels with the canonical `VALIDATED` label;
- change the effective live-time truth type to `data + MC self-consistent`;
- replace the blanket uncertainty-completeness statement with wording that
  explicitly points to unresolved uncertainty fields in the claim ledger;
- run the validator and require status `VALIDATED` before publication;
- preserve the scientific caveat that `CL-007` still has missing uncertainty
  inputs despite its claim-state label.

## Reproducible validation

Tool and tests:

- `tools/audit/validate_wiki_claim_front_door.py` v1.0.0;
- `tests/test_validate_wiki_claim_front_door.py`.

Commands:

```text
python -m py_compile \
  tools/audit/validate_wiki_claim_front_door.py \
  tests/test_validate_wiki_claim_front_door.py

python -m pytest tests/test_validate_wiki_claim_front_door.py -q
```

Result:

```text
5 passed in 0.03s
```

A reconstruction from the exact cited WIKI lines and ledger rows returned status
`FLAWED`, process status 1, and eight issues:

- three `STATUS_OUTSIDE_LEGEND`;
- three `STATUS_LEDGER_MISMATCH`;
- one `TRUTH_TYPE_LEDGER_MISMATCH`;
- one `OVERSTATED_UNCERTAINTY_COMPLETENESS`.

The test suite also verifies the corrected state, missing required claim IDs,
machine-readable flaw output, and controlled invalid-UTF-8 handling.

## Acceptance boundary

This audit validates the defect and a fail-closed checking method. It does not
rewrite `WIKI.md` in this unit, recalculate timing or pile-up results, fill the
missing uncertainty inputs, or establish peer-reviewed validity. The task remains
partial until the public WIKI is corrected and the validator returns
`VALIDATED` on the complete current files.
