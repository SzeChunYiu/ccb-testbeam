# MV3 public-WIKI section-binding audit

## Scope

This audit tests whether exact MV3 evidence is attached to the public WIKI sections
that make the claim. It does not recalculate detector performance.

## Confirmed governance defect

`tools/audit/validate_wiki_mv3_summary.py` validates source arithmetic and checks that
seven exact tokens occur somewhere in `WIKI.md`. Its focused valid fixture is a single
paragraph containing those tokens. Therefore, a document can satisfy global token
presence by placing an exact reference appendix at the end while leaving the
canonical results table rounded or stale.

That is a scientific-governance defect: evidence location determines which public
claim is authorized.

## New fail-closed gate

`tools/audit/validate_wiki_mv3_section_binding.py` requires unique, location-bound
content in six public use sites:

1. canonical results table;
2. experimental-setup material-impact row;
3. PID MV3 section;
4. MC-validation matrix;
5. MC blocking-issue line;
6. GAP-01 row.

The validator records exact WIKI bytes and SHA-256, rejects missing or duplicate
section anchors, requires exact source values in the canonical and PID locations,
requires the `FLAWED` boundary and `BLK-MV3-LEGACY-001`, and returns controlled
status 0, 1, or 2.

Policy:

`WIKI_MV3_EXACT_VALUES_MUST_BE_BOUND_TO_CANONICAL_SECTIONS`

## Current exact WIKI result

The exact current root WIKI was reconstructed from authenticated line reads and
matched Git blob `fee0e1a15243904dbeb46254878ade4650a8e1f6`:

- bytes: `23355`;
- SHA-256: `c0e8c8f7aa0c6b8f024ea9821dcb046b77376aecc95c81301afaf40248417680`;
- status: `FLAWED`;
- findings: `7`.

Finding codes:

- `CANONICAL_ROW_MISMATCH`;
- `CANONICAL_ROW_ROUNDED_ONLY`;
- `MATERIAL_IMPACT_MISMATCH`;
- `PID_SECTION_MISMATCH`;
- `VALIDATION_MATRIX_MISMATCH`;
- `BLOCKING_ISSUE_MISMATCH`;
- `GAP01_MISMATCH`.

## Regression evidence

A synthetic document was constructed with:

- all seven exact MV3 tokens present globally;
- no missing exact-value token;
- a deliberately rounded canonical row.

The global-token predicate is satisfied, but the new validator returns `FLAWED` with
`CANONICAL_ROW_MISMATCH` and `CANONICAL_ROW_ROUNDED_ONLY`.

This demonstrates the failure mode without treating synthetic text as detector data.

## Validation

```text
python -m py_compile \
  tools/audit/validate_wiki_mv3_section_binding.py \
  tools/audit/render_wiki_mv3_section_binding_evidence.py \
  tests/test_validate_wiki_mv3_section_binding.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_wiki_mv3_section_binding.py -q

5 passed in 0.03s
```

Additional checks:

- exact current-WIKI direct audit: status 1, seven findings;
- corrected six-section fixture: `VALIDATED`, zero findings;
- token-dump regression: `FLAWED`, two findings;
- missing and duplicate anchors: rejected;
- invalid UTF-8: controlled `ValidationError`;
- JSON parse: PASS;
- SVG XML parse: PASS;
- maximum changed Python line lengths: 96, 99, and 90 characters.

## Visual evidence

`docs/validation/wiki_mv3_section_binding.svg` contrasts the current rounded,
location-unbound state with the synthetic token-dump failure. It is explicitly
software/documentation evidence, not detector data.

Generation command:

```text
python tools/audit/render_wiki_mv3_section_binding_evidence.py \
  --json docs/validation/wiki_mv3_section_binding_validation.json \
  --out docs/validation/wiki_mv3_section_binding.svg
```

## Scientific boundary

Exact tracked MV3 counts and Pearson arithmetic remain a fixed-source diagnostic.
They do not establish geometry closure, trigger/selection transfer, gain response,
covariance, calibrated p-value interpretation, detector/model systematics, or a B8
acceptance correction. `BLK-MV3-LEGACY-001` remains open.
