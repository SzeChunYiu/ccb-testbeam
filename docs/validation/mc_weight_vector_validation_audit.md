# MC weight-vector validation audit

## Scope

This unit reviews `tools/audit/audit_mc_weight_usage.py`, the repository's
executable gate for issue #880 / A-003 weight provenance and weighted effective
sample size. It is software and provenance validation, not a production-MC or
detector-performance result.

## Repository facts

The MC weight contract states that the Krakow source samples `theta_cm`
uniformly and stores the lab-angle cross-section factor in `PrimaryWeight`.
The retained production report records 2,000,000 primaries, weight range
0.126–15.325, ESS 694,524, and ESS fraction 0.347. Downstream unweighted truth
results are therefore not physical production distributions.

The exact former auditor was Git blob
`9b2375b98fd76784ce3fb961e4dcdbf169f7495e`, 2,414 bytes, SHA-256
`16977d2ef277dd3cdeb3dea9047e09db84a3a6881d1d2bf278fff72d698bd7ed`.

## Confirmed defects

The former implementation:

1. flattened arbitrary arrays with `reshape(-1)`, so non-event-aligned matrices
   could become apparently valid scalar weights;
2. removed nonfinite values before calculating `n`, sums, and ESS, silently
   changing the sample and its sufficient statistics;
3. selected the first recognized branch when multiple weight branches existed;
4. did not compare the weight count with `tree.num_entries`;
5. did not record exact input byte size or SHA-256;
6. wrote JSON directly to the requested path and allowed `--out` to equal the
   ROOT input.

Exact-former-source synthetic negative controls returned `OK` after dropping a
NaN (`n=2`, ESS `1.8`), returned `OK` after choosing `PrimaryWeight` over a
simultaneous `EventWeight`, returned `OK` after flattening a 2×2 array, and
overwrote the input bytes with JSON while exiting zero when input and output
paths were identical.

## Corrected method

Version 2.0.0 implements policy:

`MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED`

A report is now accepting only when there is exactly one recognized branch,
one scalar finite nonnegative weight per tree entry, at least one positive
weight, and positive finite sums. The tool records exact input bytes and
SHA-256, uses `math.fsum` for `sum_w` and `sum_w2`, reports entry/weight/zero/
positive counts and tail diagnostics, rejects input/output aliasing, and
publishes JSON atomically through a same-directory temporary file.

Negative weights are rejected for this source-specific cross-section policy.
This does not assert that signed-weight event generators should use the same
contract; they require a separately declared estimator and ESS interpretation.

## Validation

```text
python -m py_compile \
  tools/audit/audit_mc_weight_usage.py \
  tests/test_audit_mc_weight_usage_strict.py \
  tools/audit/render_mc_weight_vector_validation_evidence.py

pytest -q tests/test_audit_mc_weight_usage_strict.py

8 passed in 0.04s
```

The tests cover valid ESS/provenance, nonfinite and negative values, all-zero
weights, ambiguous branches, non-vector shape, entry-count mismatch, atomic JSON
publication, compatibility fields, and destructive-alias prevention. Validation
used Python 3.13.5, NumPy 2.3.5, and pytest 9.0.2. JSON and SVG parsing passed;
changed Python lines are no longer than 100 characters.

## Better-method comparison

Silently filtering invalid values has lower implementation cost but changes the
sample without a declared missing-data model and can inflate or deflate ESS.
Fail-closed validation preserves traceability and forces upstream repair.
Selecting a branch by precedence is convenient but cannot establish semantic
identity when multiple branches coexist; explicit ambiguity rejection is safer.
`math.fsum` improves numerical stability with negligible cost compared with ROOT
I/O. Atomic output publication prevents partial or destructive provenance
artifacts.

## Scientific boundary and blockers

No production ROOT file was available in this runtime, so the retained
2,000,000-primary ESS was not independently regenerated. The corrected audit
validates the weight vector only; it does not demonstrate that any downstream
histogram, fit, metric, or model consumed those weights. Production reruns,
weight-sensitive before/after plots, covariance and uncertainty propagation,
and data/MC closure remain blocked by external bytes and LUNARC compute.
