# Immutable Session — AUD-LEDGER-003 CL-011 Remediation

## Identity

- UTC stamp: `2026-07-25T080448Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `563582a0d7b1d3b0fac3e33cc241b4981a21912e`
- Task: canonical `CL-011` effective-live-time remediation
- Destination: direct sequential commits to `main`; no force-push or history rewrite

## Start-of-run review

Inspected repository metadata, recent `main` history, open PRs, closed PR #868,
current status checks, repository-local coordination records, the canonical ledger,
root WIKI, Chapters 1 and 5, the prior tau-eff audit gate and tests, and the primary
S10b result, manifest, and held-out-run table. No concurrent `main` change appeared
before the focused write sequence. The initial commit had no attached status checks.
PR #868 remained closed, unmerged, non-mergeable, and untouched.

## Confirmed defect and correction

The former exact-width `CL-011` row cited MV5 as primary evidence, included a
nonexistent `results.json`, rounded the value and interval, supplied unsupported
`0.5/1.0/1.12 ns` uncertainty components, recorded `213843` pulses, and classified a
secondary reuse as independent `VALIDATED` data+MC closure.

The corrected row binds the primary S10b bundle at commit
`da9651c56ef6495ce9656d84b69b600daa6d8f86` and records:

- equal-weight mean of 14 run-level 10% template crossings relative to CFD20:
  `124.79018394263471 ns`;
- run-bootstrap 95% interval:
  `[123.33094981246663, 126.35875117626817] ns`;
- 14 runs and 252266 selected pulses;
- `truth_type=data_measurement`;
- `status=DONE_DATA_ONLY`, `allowed_status_validated=NO`;
- `blocked_by=BLK-S10B-001`;
- no statistical/systematic/total decomposition.

The row states that MV5 uses rounded 124.8 ns as an input rather than independently
validating the measurement and that the estimand is not a detector-wide universal
dead time.

## Exact provenance and validation

The pre-change ledger was reconstructed byte-for-byte and matched Git blob
`8135794d6f0b22da6b760bf6234bb8e1cae795fb`.

Candidate corrected ledger:

- 21431 bytes;
- SHA-256 `e532f3af57c2d50d261bac6a0b40546decc45a4f780fd57f92afc279a4d71ea4`;
- Git blob `254dc5b64945260193d6b1bd4146bd6400ad28cf`;
- 27/27 rows contain exactly 43 fields.

Commands:

```text
python -m py_compile tests/test_tau_eff_claim_current.py
pytest -q tests/test_tau_eff_claim_current.py

2 passed in 0.02s
```

The regression verifies unique exact-width `CL-011`, every required field and caveat,
14 unique runs, 252266 pulses, the central mean, exact interval, and source commit.
JSON and SVG parsing and the 100-character Python line gate passed.

The first direct ledger write (`aaa40edfc4e9f351e2c8f21460ef6e4d7419d287`)
transiently mistranscribed two unrelated P04p/P07e producer/config paths with periods
instead of underscores. The unexpected Git blob identity exposed the error.
Corrective commit `ab03023366396caaa97abc4cb7ea9a81aeae0731` restored the
unrelated rows and produced the exact validated blob before tests or evidence were
published. The transient mistake is retained in history and is not concealed.

## Acceptance and remaining risks

Acceptance is PARTIAL. The canonical ledger correction and focused regression are
validated. `WIKI.md`, Chapter 1, and Chapter 5 still contain stale `VALIDATED`,
`data + MC self-consistent`, rounded-interval, or unsupported uncertainty wording and
must be synchronized in a separate exact-content unit.

No raw ROOT file was reprocessed, no waveform fit was rerun, and no new systematic
uncertainty was produced. Threshold and run-weighting sensitivity, independent
cross-method/external closure, and an accepted systematic model remain required under
`BLK-S10B-001`. No universal dead time, accepted Rmax, calibration, or detector
performance is claimed.

The append-only `SESSION_LOG.md` was reviewed through complete ranged snapshots. A
safe append remains pending the final focused commit SHAs; no partial reconstruction
will replace the log.
