# Data-Side Rmax Occupancy Remediation Audit

## Scope

Task `AUD-LEDGER-004-R1` remediates the data-side producer, study report, and canonical `CL-010` row under:

`OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE`

Initial remote `main` was `a5d66f563029183e170c24f5412fffc4e336d602`.

## Defect

The selected table measures 640,737 selected B-stave pulses over 584,602 composite events, with mean selected multiplicity `1.0960225931488432`. It does not measure event-arrival exposure, luminosity, run live time, an accepted pile-up-quality ceiling, or a detector-wide effective live window.

The former producer nevertheless calculated `0.38 / 130 ns = 2.923076923076923 MHz`, labelled it data-derived, and the report claimed that occupancy corroborated an accepted rate. `CL-010` consequently published `2.92 MHz`, unsupported `0.10` and `0.20 MHz` uncertainty components, status `DONE_DATA_ONLY`, and no blocker.

## Remediation

The producer now:

- reports occupancy only as `DESCRIPTIVE_SELECTED_PULSE_MULTIPLICITY_ONLY`;
- sets `rmax_authorized=false` and `rmax_status=BLOCKED`;
- publishes no accepted Rmax value;
- binds the exact `CL-011` estimand `124.79018394263471 ns`;
- labels `0.38` as a legacy convention;
- exposes `3.045111305987686 MHz` only as `model_sensitivity_only_mhz`;
- states that rate exposure and an accepted `mu_max` are absent;
- labels the occupancy plot `Rmax withheld pending S-STAT-003`.

The report now separates measured occupancy from model inputs and states that `CL-010` remains blocked. The canonical ledger row now has a blank value and uncertainty fields, status `BLOCKED`, blocker `S-STAT-003`, and the source-conflict quarantine against the MV5 report and summary.

## Independent calculation

```text
640737 / 584602 = 1.0960225931488432 selected pulses per composite event
0.38 / 124.79018394263471 ns = 3.045111305987686 MHz
0.38 / 130 ns = 2.923076923076923 MHz
former minus exact = -0.1220343829107633 MHz
```

Both rates are convention/model sensitivities. Neither is converted into an empirical detector-rate measurement by plotting selected-pulse occupancy.

## Validation

```text
python -m py_compile \
  scripts/studies/data_side_real_beam.py \
  tests/test_data_side_rmax_quarantine.py

pytest -q tests/test_data_side_rmax_quarantine.py

2 passed in 0.32s
```

Additional checks:

- exact producer/report/ledger contract: `VALIDATED`, zero findings;
- all 26 ledger records: exactly 43 columns;
- exact remote Git blob identities matched locally validated bytes;
- validation JSON parsed;
- SVG parsed as XML;
- renderer compiled and reproduced the SVG.

Validated input identities:

| Artifact | Git blob | SHA-256 | Bytes |
|---|---|---:|---:|
| `scripts/studies/data_side_real_beam.py` | `ae5b7474a38c0b1df5cf683ab1c6de82a789b913` | `eb6fa133377c91f6804bfcb237fd5eb8aa708cdb3ae57b4b35dbee8f483ab7dc` | 13,724 |
| `reports/studies/data_side/REPORT.md` | `b3a9c3d96a8df3b6f85be381aa6b004914eb6bf6` | `c7867e0ebfe3299486d95abf6acef4b6588a5fcae11bc1ee0cca0f38d8fe90c4` | 7,113 |
| `docs/claim_ledger.csv` | `d666d9db6e7026c8d4ba0d69cc1fb301adf5c306` | `67673cb00fb2a4704a04438cbfc87133eadda39413e65a62aa324272f2008563` | 22,276 |
| `tests/test_data_side_rmax_quarantine.py` | `a5ec0a18ae3e246f60ad8875249e2a10df3ba0f8` | `b8c4654948554492d2e5465f28428ae4ab0131e79517bd554d26a287918cd3fc` | 1,739 |

## Delivery sequence

- `676549430e33994ca66b709ba102bfdc8998cf57` — task claim;
- `512671d35aa25c9830e80cd9ff525fd43254e608` — producer remediation;
- `6255a1a263adc3f33c12f9af62ca8dafafdaf3b3` — report remediation;
- `25a058b4438ab17a5fcad5de49f8e1716cd917de` — canonical-ledger remediation;
- `d82585d006c984d03126bbe6b583dca4ddbb7f80` — focused regression;
- `f739c0b17b5821022e8cd6b103345a82a11ce4c3` — evidence renderer;
- `4d3c1a798e3f02e5a72204198a2b43ee3094ad57` — machine-readable evidence;
- `e55a3de0043faa86db6cd05826d745180fcc9270` — visual evidence.

## Scientific boundary

No raw ROOT file was reprocessed. No event-arrival exposure, luminosity, accepted `mu_max`, recovery-failure ceiling, universal dead time, calibration, PID result, or detector-performance quantity was produced. The accepted numerical Rmax remains withheld under `S-STAT-003`.

Repository-wide pytest, ruff, ROOT processing, the complete link inventory, and GitHub Actions were not run in this focused unit and are not claimed as passing.
