# MV0 gain provenance and uncertainty audit

## Scope

This audit reviews the repository chain behind claim-ledger rows `CL-013` and
`CL-014`: the public MV0 v2 report, the committed `calibration.json`, the tracked
producer script, and the canonical claim ledger. It is a software/provenance audit,
not a remeasurement of the detector gain.

## Repository evidence inspected

- base `main`: `712adba593c9b84e4617c1fe8013873cd0c5f753`;
- `docs/claim_ledger.csv` blob `009f48e218b2439f80b2cebf8ebb06a845488089`;
- `reports/mv0_calibration_1782677847/REPORT.md` blob
  `bc607eb0ae2639c06ab840ff234160958ada60a5`;
- `reports/mv0_calibration_1782677847/calibration.json` blob
  `74e490753d3e821b0a1353490764a5ede0e9bf75`;
- `scripts/mv0_calibrate_from_data.py` blob
  `fd911daf3f0fd80df20f4112f4f0f40bf3383afd` at source commit
  `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`;
- `docs/figure_registry.csv` blob `1a7b6cbdc18bcc742f0578647a5c785aea78582a`.

## Confirmed conflict

The report and committed calibration artifact define the v2 data observable as

```text
abs(amplitude_adc - baseline_adc)
```

and describe the central value as median matching. The tracked producer at the
recorded source commit instead assigns raw `amplitude_adc` directly to both the
global and per-stave fit arrays. Therefore the tracked code does not implement the
methodology claimed by the result artifact.

The report's reproduce command also uses `--data`, while the tracked parser requires
`--data-csv`, and the command omits the required `--truth-npz` input. The script's
written JSON schema lacks the artifact's `gain_method`,
`gain_systematic_unc_pct`, and `ks_at_median_gain` fields. The committed artifact
therefore cannot be regenerated from the declared command and tracked producer as
written.

## Claim-ledger defects

`CL-013` has 38 fields and `CL-014` has 37 fields under the canonical 43-column
header. Their late fields are withheld by the existing fail-closed ledger policy.
The raw rows and `FIG-EN-001` also cite `scripts/mv0_calibration.py` and
`reports/mv0_calibration_1782677847/results.json`; the tracked producer and result
artifact are instead `scripts/mv0_calibrate_from_data.py` and `calibration.json`.

The artifact supports:

- central value `92 ADC/MeV`;
- `30%` stated systematic uncertainty, equal to `27.6 ADC/MeV` before rounding;
- KS statistic `0.1577` at the median-matched gain;
- B2 counts `n_data=579424` and `n_mc=321130`.

It does **not** provide a statistical uncertainty, a formal confidence interval,
a confidence level, or an interval construction method. The ledger values
`stat_unc=14`, `total_unc=31.3`, and interval `[60,124]` are not supported by this
artifact. The independently recomputed central value from the stated numbers is

```text
1781 / (26.44 * 0.733) = 91.89639906462777 ADC/MeV.
```

## Validated gate

`tools/audit/audit_mv0_gain_provenance.py` v1.0.0 checks:

1. exact 43-column widths for `CL-013` and `CL-014`;
2. stale producer/result tokens in the ledger;
3. the calibration artifact's declared central value, systematic percentage, and
   net-amplitude method;
4. producer-script syntax, data observable, CLI contract, and output schema;
5. report-command compatibility;
6. immutable byte/SHA-256 provenance for every local audit input.

Policy:

```text
MV0_GAIN_NOT_CANONICAL_UNTIL_PRODUCER_AND_ARTIFACT_REPRODUCE
```

The exact repository was unavailable as a local checkout because DNS resolution for
`github.com` failed. The executable regression therefore used a source-faithful
reduced fixture, while the repository findings and blob identities were verified by
authenticated GitHub reads. The machine-readable record distinguishes those two
evidence classes.

## Validation commands

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_mv0_gain_provenance.py \
  tests/test_audit_mv0_gain_provenance.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_mv0_gain_provenance.py -q

4 passed in 0.64s
```

The current-like fixture returned status 1 with ten findings. The corrected fixture
returned `VALIDATED`. The validation JSON parsed, the SVG parsed as XML, and maximum
changed Python line lengths were 100 and 87 characters.

## Acceptance state

The audit implementation, tests, and evidence are validated. The gain claim itself
is not. Until the producer, command, raw inputs, output schema, uncertainty fields,
ledger rows, and figure provenance form one reproducible chain, the canonical gain
must be withheld from `VALIDATED` use.

No raw pulse table, ROOT file, NPZ truth file, calibration rerun, KS recomputation,
bootstrap, detector calibration, or downstream performance result was produced.
