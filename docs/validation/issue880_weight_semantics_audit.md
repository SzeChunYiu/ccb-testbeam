# Issue #880 weight semantics audit

- **Audit ID:** `AUD-MC-002`
- **Status:** `PARTIAL`
- **Policy:** `ISSUE880_WEIGHTS_MUST_FAIL_CLOSED_AND_BIAS_DIRECTION_MUST_BE_EXPLICIT`
- **Scope:** the tracked issue #880 weighted/unweighted study producer and retained JSON summary
- **Repository source:** `scripts/single_stave/issues879_880_887_mc_study.py`
- **Retained result:** `reports/issues879_880_887_mc_analysis/issues879_880_887_result.json`

## Scientific question

Does the issue #880 study fail closed when event weights are invalid, and do its reported
"bias" fields state an unambiguous direction and denominator?

This matters because the retained one-million-event summary reports a large PrimaryWeight
spread and an effective sample size of only 34.7% of nominal. A silent substitution or a
mislabelled relative change can materially alter the interpretation of the reported MC bias.

## Repository facts inspected

The tracked producer is Git blob `bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`.
The tracked result is Git blob `37d69e2c697a7ce7c9e1eff9aeff48539551d922`.
PR #897 merged the issue #880 weighted-chain changes and issue #880 remains open with a
comment describing the retained weighted/unweighted differences.

The producer contains four fail-open paths:

1. `load_mc` replaces every nonfinite event weight with `1.0`;
2. `wmean` falls back to the ordinary mean when the weight sum is not positive;
3. `wmedian` and `wfrac` likewise fall back to unweighted estimators;
4. `wcorr` falls back to ordinary Pearson correlation.

Those behaviors conflict with the repository's source-specific nonnegative event-weight
policy: an invalid weight vector must stop the analysis, not silently become an unweighted
analysis.

## Independent arithmetic reconstruction

The retained summary records:

| Quantity | Legacy unweighted | PrimaryWeighted |
|---|---:|---:|
| First B-layer mean EDep | 6.674567424757 MeV | 2.134364334727324 MeV |
| Entering-B deuteron fraction | 0.5719111928400914 | 0.16606032425392264 |

The existing field
`first_B_layer_mean_rel_bias_pct = -68.02243203341332` is numerically:

```text
100 × (weighted − unweighted) / unweighted
```

It is therefore a **weighted change relative to the unweighted value**, not an unqualified
measure of how much the legacy estimate was biased. The reverse comparison is:

```text
100 × (unweighted − weighted) / weighted
= +212.7192164972955%
```

The existing deuteron field is similarly directional:

```text
100 × (weighted fraction − unweighted fraction)
= −40.585086858616876 percentage points
```

When the statement concerns legacy overstatement, the direction is instead:

```text
100 × (unweighted fraction − weighted fraction)
= +40.585086858616876 percentage points
```

and relative to the weighted fraction the legacy overstatement is
`+244.39966043037631%`.

No arithmetic mismatch was found. The defect is semantic: the field names and prose do not
name the direction and denominator, so readers can reasonably interpret `−68%` as the
relative bias of the legacy value when the corresponding legacy overstatement is `+213%`.

## Provenance gap

The retained result records a filesystem path and generation time but omits:

- exact ROOT input byte size and SHA-256;
- producer commit SHA;
- exact generation command and environment;
- event-weight validation policy and version.

The exact production ROOT bytes were not available in this session, so the one-million-event
study was not rerun. The retained values were independently recalculated only from the
tracked JSON summary.

## Better method

The corrected contract should:

1. validate every selected event weight before any statistic is computed;
2. reject missing, empty, nonfinite, negative, or zero-total weights;
3. never substitute unit weights and never fall back to an unweighted estimator;
4. emit both directional comparisons with explicit field names and denominators;
5. record ROOT hash, producer commit, command, environment, branch semantics, and policy;
6. include weighted uncertainty or resampling diagnostics before the differences authorize a
   physics claim.

Recommended fields are:

- `weighted_change_relative_to_unweighted_pct`;
- `legacy_unweighted_overstatement_relative_to_weighted_pct`;
- `legacy_unweighted_minus_weighted_pp`.

## Validation gate delivered

Added:

- `tools/audit/audit_issue880_weight_semantics.py`;
- `tests/test_audit_issue880_weight_semantics.py`;
- `tools/audit/render_issue880_weight_semantics_evidence.py`;
- `docs/validation/issue880_weight_semantics_validation.json`;
- `docs/validation/issue880_weight_semantics.svg`.

Executed:

```text
python -m py_compile \
  tools/audit/audit_issue880_weight_semantics.py \
  tests/test_audit_issue880_weight_semantics.py \
  tools/audit/render_issue880_weight_semantics_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_issue880_weight_semantics.py

6 passed in 0.04s
```

The focused regression covers the current fail-open and ambiguous-direction patterns, a
strict direction-explicit accepted fixture, arithmetic mutation detection, invalid UTF-8,
atomic JSON publication, and destructive input/output alias rejection. Validation JSON
parsing and SVG XML parsing passed. Changed Python lines are no longer than 99 characters.

## Acceptance boundary

The **audit gate and independent arithmetic reconstruction are validated**. The retained
issue #880 study remains `FLAWED` until its producer is changed and the exact ROOT input is
rerun with content-addressed provenance. This audit does not establish that the first primary
is the scientifically correct event-weight carrier, quantify weighted uncertainty, or provide
data/MC closure.
