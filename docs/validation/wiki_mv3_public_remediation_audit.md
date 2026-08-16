# MV3 public-WIKI remediation audit

## Scope

- Task: `AUD-WIKI-003`
- Session stamp: `2026-07-25T000907Z`
- Initial remote `main`: `94eb6705c5db6d10793532b6b2607b855806298b`
- Policy: `WIKI_MV3_EXACT_VALUES_MUST_BE_BOUND_TO_CANONICAL_SECTIONS`
- Scientific status retained: `FLAWED`
- Blocking record retained: `BLK-MV3-LEGACY-001`

This unit remediates the public root `WIKI.md` after the preceding audit demonstrated that globally present exact tokens did not guarantee that the canonical scientific use sites contained exact evidence.

## Exact tracked evidence

The machine-readable MV3 summary and exact-width canonical claim rows bind:

- selected-data B8: `7051/306745 = 0.02298651974767315`;
- thresholded-MC B8: `55619/249484 = 0.22293614019335908`;
- Pearson chi-square: `204808.2179684494`;
- degrees of freedom: `3`;
- chi-square per degree of freedom: `68269.40598948313`.

These quantities are reproducible fixed-source arithmetic. They do not establish an accepted stopping-profile closure or calibrated goodness-of-fit result.

## Confirmed former public defect

The former WIKI blob `fee0e1a15243904dbeb46254878ade4650a8e1f6` returned seven location-bound findings:

- `CANONICAL_ROW_MISMATCH`;
- `CANONICAL_ROW_ROUNDED_ONLY`;
- `MATERIAL_IMPACT_MISMATCH`;
- `PID_SECTION_MISMATCH`;
- `VALIDATION_MATRIX_MISMATCH`;
- `BLOCKING_ISSUE_MISMATCH`;
- `GAP01_MISMATCH`.

It retained rounded `2.3%`, `22.3%`, and `68269.4` public values and stale wording that exact counts and statistic components were absent, although the tracked summary contains them.

## Correction delivered

Commit `a38f8cf5b2abb6f363a7bd2c0c6bed6828229720` produced WIKI blob `91e82c59a2b59b285c6a529c0637ed665be2c4fd` and bound the exact evidence plus non-authorizing boundary to six unique public use sites:

1. canonical results table;
2. experimental-setup material-impact row;
3. particle-identification MV3 section;
4. MC-validation matrix;
5. MC blocking-issue statement;
6. GAP-01 row.

The correction does not change the scientific verdict. It states that exact arithmetic exists while geometry, trigger and selection transfer, gain response, covariance, p-value interpretation, and detector/model systematics remain unresolved.

## Regression coverage

Added `tests/test_wiki_mv3_public_remediation.py` in commit `eb030003d96ed1e6a589ec03e4e2fdaa6c57d718`.

The focused integration contract requires both existing validators to return `VALIDATED` with zero issues on the corrected public text and exact ledger/summary inputs. A negative control restores the rounded canonical row and requires fail-closed findings.

Local reconstructed validation command:

```text
python -m py_compile \
  tools/audit/validate_wiki_mv3_section_binding.py \
  tools/audit/validate_wiki_mv3_summary.py \
  tests/test_wiki_mv3_public_remediation.py

PYTHONPATH=. python -m pytest \
  tests/test_wiki_mv3_public_remediation.py -q

2 passed in 0.02s
```

Validation scope: exact validator logic, exact ledger/summary arithmetic, and a fixture matching the six committed public-use sites. The GitHub connector does not expose a repository checkout or command runner, so no claim is made that this command executed against a full local clone after publication.

## Visual and machine-readable evidence

- `docs/validation/wiki_mv3_public_remediation_validation.json`
- `docs/validation/wiki_mv3_public_remediation.svg`
- renderer: `tools/audit/render_wiki_mv3_public_remediation.py`

The SVG is explicitly documentation/provenance evidence, not detector data or physics closure.

## Validation limits

Not run in this session:

- ROOT or Geant4 processing;
- detector-data or simulation regeneration;
- repository-wide pytest or ruff;
- GitHub Actions;
- repository-wide broken-link checking.

No new link target was introduced. No status checks or workflow runs were attached to the focused test commit when inspected.

## Interpretation

The public WIKI now states the exact tracked MV3 evidence at each scientific use site and retains the `FLAWED` boundary. This closes the public-text remediation unit but does not resolve `BLK-MV3-LEGACY-001` or authorize a B8 acceptance correction.
