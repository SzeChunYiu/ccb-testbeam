# ML / Model-Selection Validation Standard

Parent: #1609 under global revalidation #1594.

A high AUC, low `sigma68`, good cross-validation score, or narrow bootstrap interval is **not** sufficient to authorize a production scientific model. Model discovery and scientific validation are different stages.

## Required gates for a promoted ML/model-selection claim

1. **Target/label independence**
   - State exactly how the target is constructed.
   - Demonstrate that the label is not a deterministic/disguised function of model inputs.
   - Run target-shuffle and synthetic leakage sentinels where applicable.

2. **Split independence**
   - Split at the physical dependence unit: normally run/run-family and event, not random rows.
   - Fit preprocessing, calibration, feature selection and hyperparameters on training data only.
   - Record every run/event family exposed during method development.

3. **Model-selection multiplicity**
   - Inventory candidate model families, feature sets, cuts, architectures and hyperparameter searches.
   - If the reported result is selected as the best among many attempts, its final validation set must not have participated in that selection.
   - A bootstrap CI conditional on the selected winner does not correct winner's curse by itself.

4. **Untouched final validation**
   - A promoted winner requires a never-used run block/campaign/external transfer set, or an equivalent preregistered validation design.
   - If no untouched sample exists, the result is `EXPLORATORY`/`GATED`, regardless of cross-validation quality.

5. **Strong comparator**
   - Compare against a physically/statistically strong traditional baseline under identical selection, data split and uncertainty treatment.
   - A weak comparator does not establish an ML advantage.

6. **Uncertainty/dependence**
   - Resampling unit must match the data-generating dependence structure.
   - Report covariance/common-mode effects and nuisance/systematic sensitivity relevant to the metric.
   - State interval method and coverage target.

7. **Slice/transfer behavior**
   - Report run/stave/operating-condition and physically relevant worst slices, not only aggregate score.
   - Test new-run/new-stave/domain transfer before production use.

8. **Probability interpretation**
   - If scores are interpreted as probabilities, evaluate calibration/coverage on independent data.

## Status rule

Allowed states during development include `EXPLORATORY`, `REVIEW`, `GATED`, `BLOCKED`, and `FLAWED`.

A model may enter `SUPPORTED`/`VALIDATED`/`PRODUCTION` only when the machine-readable `ML_VALIDATION_LEDGER.csv` records:

- label independence = PASS;
- leakage controls = PASS;
- physical split independence = PASS;
- multiplicity policy = PASS;
- untouched validation = PASS;
- strong baseline = PASS;
- uncertainty/dependence = PASS;
- transfer/slice review = PASS;
- provenance = COMPLETE;
- four-role review acceptance where the claim is a headline physics/detector result.

## Existing project consequences

- Truth-label classifiers remain truth/simulation evidence unless transferred independently to beam data.
- Models chosen after repeated exploration on shared held-out runs are not independently validated merely because those runs were called “test”.
- P04p duplicate-readout and P07e saturation-transfer production claims remain gated by existing external-transfer/selection evidence.
- Timing/frontier studies such as S52a/S71a remain exploratory until the global raw/calibration contract and untouched-validation/multiplicity gates close.

The purpose of this standard is not to disallow ML. It is to make a claimed ML advantage answer the same scientific question on evidence that was not used to create the claim.
