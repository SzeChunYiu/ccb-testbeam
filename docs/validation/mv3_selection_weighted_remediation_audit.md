# MV3 weighted-selection producer remediation

## Finding

The former producer read `PrimaryWeight` but never used it, silently defaulted invalid weights to
1.0, and selected only positive charges. It also compared unselected MC to all data while comparing
selected MC to Sample-I data, so its advertised improvement changed the data target.

## Correction

`mv3_selection_matched.py` now fails closed on malformed weights, uses canonical signed-charge
selection, emits weighted physical and unweighted sensitivity profiles, records weight sums and ESS,
uses same-target selection ablation, hashes all declared inputs, and publishes JSON atomically.
The source report now quarantines the tracked JSON and PNG files as superseded unweighted
diagnostics rather than accepted closure evidence.

## Validation

```text
python -m py_compile \
  scripts/studies/mv3_selection_matched.py \
  tests/test_mv3_selection_weighted_contract.py \
  tools/audit/render_mv3_selection_weighted_remediation_evidence.py

pytest -q tests/test_mv3_selection_weighted_contract.py
6 passed in 0.04s
```

Synthetic controls verify a two-event profile with weights 1 and 9 produces a weighted B2/B8 split
of 0.1/0.9 while the unweighted sensitivity is 0.5/0.5. Invalid weight cardinality, NaN, negative
weights, zero-total selections, and non-atomic JSON publication fail closed. The validation JSON and
SVG parse successfully, and prepared Python lines are at most 99 characters.

The authenticated connector returned exact post-write Git blobs and the committed source was
re-read after publication. The local execution environment could not establish a network checkout
or download the remote raw bytes, so exact committed-blob pytest is not claimed; the validation
record distinguishes prepared-byte execution from remote delivery.

## Scientific boundary

No production ROOT or beam-data file was rerun. Existing summary/PNG artifacts are quarantined as
superseded unweighted diagnostics. No weighted stopping profile, covariance, material correction,
scattering correction, calibration, PID result, or detector-performance claim is produced here.
Canonical `CL-021` remains `FLAWED` under `BLK-MV3-LEGACY-001`.
