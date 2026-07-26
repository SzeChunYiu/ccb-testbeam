# Latest Handoff

## Session

- **Task ID:** `AUD-LEDGER-004-R1`
- **Stamp:** `2026-07-26T091312Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `a5d66f563029183e170c24f5412fffc4e336d602`
- **Validated delivery/handoff commit:** `1c01dc385e75e1a74aa6b306384ee5715cc72177`
- **Remote main after validated delivery:** `1c01dc385e75e1a74aa6b306384ee5715cc72177`
- **Destination:** direct sequential commits to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push result:** GitHub contents API returned successful direct-main commit SHAs for every write; recent history confirmed the consecutive sequence on remote `main`. The connector does not return a conventional terminal `git push` transcript, and none is claimed.
- **Focused acceptance:** producer/report/ledger remediation `VALIDATED / COMPLETE`.
- **Scientific acceptance:** accepted absolute Rmax remains `BLOCKED` under `S-STAT-003`.

## Finding

Policy:

`OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE`

The selected table measures 640,737 selected B-stave pulses over 584,602 composite events, with mean selected multiplicity `1.0960225931488432`. It does not measure event-arrival exposure, luminosity, run live time, an accepted pile-up-quality ceiling, or a detector-wide live window.

The former producer nevertheless calculated `0.38 / 130 ns = 2.923076923076923 MHz`, labelled it data-derived, and the report said occupancy corroborated an accepted rate. Canonical `CL-010` then published `2.92 MHz`, unsupported `0.10` and `0.20 MHz` uncertainty components, status `DONE_DATA_ONLY`, and no blocker.

## Work delivered

Updated:

- `scripts/studies/data_side_real_beam.py`
  - occupancy is descriptive only;
  - `rmax_authorized=false`;
  - `rmax_status=BLOCKED`;
  - `accepted_rmax_mhz=null`;
  - exact `CL-011` value `124.79018394263471 ns`;
  - `mu_max=0.38` labelled legacy convention;
  - `3.045111305987686 MHz` labelled model sensitivity only;
  - occupancy plot title states `Rmax withheld pending S-STAT-003`.
- `reports/studies/data_side/REPORT.md`
  - removes data-derived/corroboration wording;
  - distinguishes measured occupancy from model assumptions;
  - states `CL-010 remains BLOCKED`.
- `docs/claim_ledger.csv`
  - accepted value and uncertainty fields blank;
  - `truth_type=derived_model_conflicted`;
  - `status=BLOCKED`;
  - `blocked_by=S-STAT-003`;
  - source-conflict quarantine restored against tracked MV5 artifacts.
- `chatgpt_todo/ACTIVE_TASK.md` — focused unit complete.

Added:

- `tests/test_data_side_rmax_quarantine.py`
- `tools/audit/render_data_side_rmax_remediation_evidence.py`
- `docs/validation/data_side_rmax_remediation_validation.json`
- `docs/validation/data_side_rmax_remediation.svg`
- `docs/validation/data_side_rmax_remediation_audit.md`
- `chatgpt_todo/archive/2026-07-26T091312Z_AUD-LEDGER-004_RMAX_REMEDIATION.md`

## Independent calculations

```text
640737 / 584602 = 1.0960225931488432 selected pulses per composite event
0.38 / 124.79018394263471 ns = 3.045111305987686 MHz
0.38 / 130 ns = 2.923076923076923 MHz
former minus exact = -0.1220343829107633 MHz
```

Both rates are convention/model sensitivities and are non-authorizing.

## Validation

```text
python -m py_compile \
  scripts/studies/data_side_real_beam.py \
  tests/test_data_side_rmax_quarantine.py

pytest -q tests/test_data_side_rmax_quarantine.py

2 passed in 0.32s
```

Additional results:

- exact producer/report/ledger contract: `VALIDATED`, zero findings;
- claim ledger: 26 records, every record exactly 43 columns;
- exact local Git blob hashes matched remote content blobs;
- validation JSON parsed;
- evidence renderer compiled and reproduced the SVG;
- SVG parsed as XML;
- no combined commit statuses are attached to the validated delivery commit, so broad CI success is not claimed.

Validated blobs:

| Artifact | Git blob | SHA-256 | Bytes |
|---|---|---:|---:|
| producer | `ae5b7474a38c0b1df5cf683ab1c6de82a789b913` | `eb6fa133377c91f6804bfcb237fd5eb8aa708cdb3ae57b4b35dbee8f483ab7dc` | 13,724 |
| report | `b3a9c3d96a8df3b6f85be381aa6b004914eb6bf6` | `c7867e0ebfe3299486d95abf6acef4b6588a5fcae11bc1ee0cca0f38d8fe90c4` | 7,113 |
| ledger | `d666d9db6e7026c8d4ba0d69cc1fb301adf5c306` | `67673cb00fb2a4704a04438cbfc87133eadda39413e65a62aa324272f2008563` | 22,276 |
| regression | `a5ec0a18ae3e246f60ad8875249e2a10df3ba0f8` | `b8c4654948554492d2e5465f28428ae4ab0131e79517bd554d26a287918cd3fc` | 1,739 |

## Direct-main sequence

- `676549430e33994ca66b709ba102bfdc8998cf57` — task claim;
- `512671d35aa25c9830e80cd9ff525fd43254e608` — producer remediation;
- `6255a1a263adc3f33c12f9af62ca8dafafdaf3b3` — report remediation;
- `25a058b4438ab17a5fcad5de49f8e1716cd917de` — ledger remediation;
- `d82585d006c984d03126bbe6b583dca4ddbb7f80` — focused regression;
- `f739c0b17b5821022e8cd6b103345a82a11ce4c3` — evidence renderer;
- `4d3c1a798e3f02e5a72204198a2b43ee3094ad57` — machine-readable evidence;
- `e55a3de0043faa86db6cd05826d745180fcc9270` — visual evidence;
- `78c56e05c93f664688502d2f4fd7c3490dc74f7a` — audit report;
- `9c08aedf4bfeab90d6b4650aec84246a6ec1d285` — immutable archive;
- `ba44bcb0e9ca1ec63c5e0dad0be686d5918b8a60` — active-task completion;
- `1c01dc385e75e1a74aa6b306384ee5715cc72177` — validated delivery handoff.

## Scientific boundary

No raw ROOT file was reprocessed. No event-arrival exposure, luminosity, accepted `mu_max`, recovery-failure ceiling, universal dead time, calibration, PID result, or detector-performance quantity was produced. Repository-wide pytest, ruff, ROOT processing, complete link checking, and GitHub Actions were not run and are not claimed as passing.

PR #939 remained open, non-mergeable, and unmerged. PR #868 remained closed, non-mergeable, and unmerged.

`SESSION_LOG.md` was read completely through paged connector ranges, but the available write operation is whole-file replacement rather than a byte-safe append. Reconstructing the complete historical file inside one write payload risked transcription damage. The mandatory append was therefore not reported as completed; the immutable archive and this handoff retain the full append-equivalent record.

## Next action

Keep `CL-010` value-withheld until a preregistered pile-up-quality estimand, immutable exposure/rate inputs, recovery-ceiling crossing, and uncertainty model are validated. Separately regenerate the descriptive occupancy figure with the corrected producer when the immutable input environment is available; do not reinterpret it as an absolute-rate measurement.
