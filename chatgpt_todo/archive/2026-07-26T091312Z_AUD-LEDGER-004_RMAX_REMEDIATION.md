# Immutable Handoff — AUD-LEDGER-004-R1

## Session

- Stamp: `2026-07-26T091312Z`
- Initial remote `main`: `a5d66f563029183e170c24f5412fffc4e336d602`
- Owner: scheduled scientific-review session
- Policy: `OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE`
- Acceptance: focused remediation `VALIDATED`; accepted absolute Rmax remains `BLOCKED` under `S-STAT-003`.

## Reviewed

- recent remote-main history and concurrent timing-identity delivery;
- `chatgpt_todo/ACTIVE_TASK.md`, `HANDOFF.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and `SESSION_LOG.md`;
- `scripts/studies/data_side_real_beam.py`;
- `reports/studies/data_side/REPORT.md`;
- `docs/claim_ledger.csv`;
- existing `tools/audit/audit_data_side_rmax_semantics.py` and visual renderer;
- open PR #939 and closed PR #868 status.

## Confirmed defect

The selected table contains 640,737 selected pulses over 584,602 composite events. It measures selected-pulse multiplicity, not event-arrival exposure, luminosity, an accepted pile-up-quality ceiling, or a detector-wide live window. The former producer nevertheless calculated `0.38 / 130 ns = 2.923076923076923 MHz`, called it data-derived, and the report claimed corroboration of an accepted rate. Canonical `CL-010` published `2.92 MHz`, unsupported `0.10` and `0.20 MHz` components, status `DONE_DATA_ONLY`, and no blocker.

## Delivered remediation

- `scripts/studies/data_side_real_beam.py`
  - occupancy labelled `DESCRIPTIVE_SELECTED_PULSE_MULTIPLICITY_ONLY`;
  - `rmax_authorized=false`;
  - `rmax_status=BLOCKED`;
  - `accepted_rmax_mhz=null`;
  - exact `CL-011` value `124.79018394263471 ns`;
  - `mu_max=0.38` labelled legacy convention;
  - `3.045111305987686 MHz` published only as model sensitivity;
  - occupancy figure states `Rmax withheld pending S-STAT-003`.
- `reports/studies/data_side/REPORT.md`
  - removes data-derived/corroboration wording;
  - separates measured occupancy from model conventions;
  - states `CL-010 remains BLOCKED`.
- `docs/claim_ledger.csv`
  - blank accepted value and uncertainty fields;
  - `truth_type=derived_model_conflicted`;
  - `status=BLOCKED`;
  - `blocked_by=S-STAT-003`;
  - source-conflict quarantine bound to tracked MV5 artifacts.
- `tests/test_data_side_rmax_quarantine.py`
  - executes the fail-closed producer contract on a synthetic composite-event table;
  - verifies exact model sensitivity and plot publication;
  - rejects former authorization phrases.
- reproducible JSON, renderer, SVG, and Markdown evidence under `docs/validation/`.

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

- Exact producer/report/ledger contract: `VALIDATED`, zero findings.
- Ledger: 26 records, every record exactly 43 columns.
- Exact local Git blob hashes matched the remote blobs.
- JSON parsed.
- Renderer compiled and reproduced the SVG.
- SVG parsed as XML.

## Validated identities

| Artifact | Git blob | SHA-256 | Bytes |
|---|---|---:|---:|
| producer | `ae5b7474a38c0b1df5cf683ab1c6de82a789b913` | `eb6fa133377c91f6804bfcb237fd5eb8aa708cdb3ae57b4b35dbee8f483ab7dc` | 13,724 |
| report | `b3a9c3d96a8df3b6f85be381aa6b004914eb6bf6` | `c7867e0ebfe3299486d95abf6acef4b6588a5fcae11bc1ee0cca0f38d8fe90c4` | 7,113 |
| ledger | `d666d9db6e7026c8d4ba0d69cc1fb301adf5c306` | `67673cb00fb2a4704a04438cbfc87133eadda39413e65a62aa324272f2008563` | 22,276 |
| regression | `a5ec0a18ae3e246f60ad8875249e2a10df3ba0f8` | `b8c4654948554492d2e5465f28428ae4ab0131e79517bd554d26a287918cd3fc` | 1,739 |

## Direct-main commits through evidence

- `676549430e33994ca66b709ba102bfdc8998cf57` — task claim;
- `512671d35aa25c9830e80cd9ff525fd43254e608` — producer remediation;
- `6255a1a263adc3f33c12f9af62ca8dafafdaf3b3` — report remediation;
- `25a058b4438ab17a5fcad5de49f8e1716cd917de` — ledger remediation;
- `d82585d006c984d03126bbe6b583dca4ddbb7f80` — regression;
- `f739c0b17b5821022e8cd6b103345a82a11ce4c3` — renderer;
- `4d3c1a798e3f02e5a72204198a2b43ee3094ad57` — JSON evidence;
- `e55a3de0043faa86db6cd05826d745180fcc9270` — SVG evidence;
- `78c56e05c93f664688502d2f4fd7c3490dc74f7a` — audit report.

GitHub contents writes returned successful direct-main commit SHAs. Recent history confirmed the sequence on remote `main`; no branch, force-push, or history rewrite was used.

## Unrun checks and boundary

No raw ROOT file was reprocessed. No arrival-rate exposure, luminosity, accepted `mu_max`, recovery-failure ceiling, universal dead time, calibration, PID result, or detector-performance quantity was produced. Repository-wide pytest, ruff, ROOT processing, full link checking, and GitHub Actions were not run and are not claimed as passing.

PR #939 remained open and unmerged. PR #868 remained closed and unmerged.
