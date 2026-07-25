# Issue #880 strict producer remediation audit

## Status

**Validated implementation; production rerun blocked.** The repository now has a fail-closed
replacement entry point and reusable numerical contract for event-weighted analyses. The exact
one-million-event ROOT input was not available in this runtime, so the retained issue #880 result
has not been superseded and remains a flagged diagnostic.

Policy:

`ISSUE880_STRICT_CONTENT_ADDRESSED_WEIGHTED_RERUN`

Weight-vector contract:

`MC_WEIGHT_VECTOR_MUST_BE_UNAMBIGUOUS_FINITE_NONNEGATIVE_AND_EVENT_ALIGNED`

## Repository evidence reviewed

- Historical producer: `scripts/single_stave/issues879_880_887_mc_study.py`, Git blob
  `bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`.
- Retained result: `reports/issues879_880_887_mc_analysis/issues879_880_887_result.json`, Git blob
  `37d69e2c697a7ce7c9e1eff9aeff48539551d922`.
- Issue #880 asks that MC event weights be used correctly.
- The preceding `AUD-MC-002` audit established that the historical producer coerces nonfinite
  weights to `1.0`, allows four weighted estimators to fall back to unweighted values, reports
  ambiguous signed comparison fields, and omits content-addressed input/producer provenance.

## Correction delivered

### Reusable strict numerical layer

`scripts/single_stave/strict_event_weights.py` provides:

- one-dimensional, event-count-aligned weight validation;
- rejection of nonfinite, negative, empty, and all-zero weight vectors;
- `math.fsum`-based weighted means, sums, ESS, and covariance components;
- fail-closed weighted median, fraction, and correlation estimators;
- explicit handling of zero relative denominators as JSON `null`, never an epsilon substitution;
- both weighted-minus-unweighted and legacy-minus-weighted comparison directions;
- deterministic, atomic JSON publication with protected-input alias rejection;
- exact file byte counts and SHA-256 digests.

### Strict study entry point

`scripts/single_stave/issues879_880_887_mc_study_strict.py` is the canonical rerun entry point for
this study. It retains the historical producer only as imported study/plot logic and replaces its
weight-sensitive primitives before execution. The strict entry point additionally:

1. requires exactly one `PrimaryWeight` and one `PrimaryPDG` value per loaded event;
2. verifies the loaded count against ROOT tree metadata and `--entry-stop`;
3. rejects nonfinite or negative scintillator energy deposits;
4. hashes the ROOT input before and after the ROOT read and requires byte identity;
5. refuses a tracked-dirty producer checkout;
6. records git commit, exact command, Python/platform/NumPy versions, and SHA-256 of the strict
   wrapper, numerical module, and historical producer;
7. publishes direction-explicit issue #880 comparisons;
8. rejects zero-weight selected subsamples instead of silently returning unweighted or undefined
   statistics;
9. requires `--overwrite` before replacing a prior artifact set;
10. writes the machine-readable result atomically and protects the ROOT/code inputs from aliasing.

The historical entry point is retained for provenance but is not accepted for a new scientific
rerun.

## Independent retained-result arithmetic

The retained values are arithmetically reproducible; the problem was interpretation and
provenance rather than an arithmetic discrepancy.

| Quantity | Unweighted legacy | PrimaryWeighted | Direction-explicit comparison |
|---|---:|---:|---:|
| First B-layer mean EDep | 6.674567424757 MeV | 2.134364334727324 MeV | weighted minus unweighted = -68.022432% of \|unweighted\| |
| First B-layer mean EDep | 6.674567424757 MeV | 2.134364334727324 MeV | legacy minus weighted = +212.719216% of \|weighted\| |
| Entering-B deuteron fraction | 0.5719111928400914 | 0.16606032425392264 | legacy minus weighted = +40.585087 percentage points |
| Entering-B deuteron fraction | 0.5719111928400914 | 0.16606032425392264 | legacy overstatement = +244.399660% of \|weighted\| |

These are simulation-summary comparisons, not detector calibration or empirical species
measurements.

## Validation

Commands executed on the exact strict module, wrapper, focused tests, and renderer prepared for
publication:

```text
python -m py_compile \
  scripts/single_stave/strict_event_weights.py \
  scripts/single_stave/issues879_880_887_mc_study_strict.py \
  tests/test_strict_event_weights.py \
  tests/test_issues879_880_887_strict_producer.py \
  tools/audit/render_issue880_strict_producer_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_strict_event_weights.py \
  tests/test_issues879_880_887_strict_producer.py

17 passed in 0.04s
```

The exact historical producer source was inspected through GitHub blob
`bc1220fdfe1010989fd8ab273f8c1b1fcf708b2c`. Because connector-returned repository bytes were not
materialized into the local runtime, local wrapper tests used a minimal API-compatible historical
module fixture. The committed tests import the actual sibling producer in a complete checkout; no
claim is made that the complete repository test suite or production ROOT run was executed here.

The tests cover:

- correct weighted mean, median, fraction, correlation, ESS, and provenance fields;
- nonfinite, negative, multidimensional, all-zero, empty, and misaligned weights;
- nonfinite values, length mismatches, and zero-variance correlations;
- both comparison directions and their explicit denominators;
- zero-denominator `null` behavior;
- atomic JSON publication and destructive alias prevention;
- strict issue #880 summary semantics on synthetic event-aligned arrays;
- empty entering-species selections and zero-weight PID subsamples;
- explicit overwrite gating;
- absence of the historical unit-weight coercion, unweighted fallbacks, and epsilon denominator.

JSON parsing and SVG XML parsing passed. Changed Python files are no longer than 100 characters per
line. The SVG is synthetic software/provenance evidence and is not detector data.

## Required production command

Run from a clean checkout at the commit intended to authorize the output:

```text
python scripts/single_stave/issues879_880_887_mc_study_strict.py \
  --root geant4/data/output_krakow_1M.root \
  --tree hibeam \
  --entry-stop 0 \
  --out reports/issues879_880_887_mc_analysis_strict
```

Use `--overwrite` only after archiving or intentionally superseding a complete prior strict output
bundle. The resulting JSON must be retained with every generated plot and reviewed before any issue
#879, #880, or #887 claim is restored.

## Scientific acceptance boundary

This unit validates code and synthetic edge cases. It does **not**:

- reproduce the exact one-million-event study;
- establish that the first primary is the scientifically correct event-weight carrier;
- quantify weighted uncertainty or confidence intervals;
- test weight-tail sensitivity under every selection;
- validate event-selection transfer to data;
- establish detector calibration, species identification, or data/MC closure.

The retained result remains `FLAWED`. Closing issue #880 requires a clean content-addressed rerun,
weighted uncertainty and tail-stability diagnostics, regenerated plots, and scientific review of the
weight definition and data/MC transfer.
