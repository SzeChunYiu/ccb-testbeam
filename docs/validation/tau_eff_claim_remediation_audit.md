# CL-011 Effective-Live-Time Claim Remediation

## Scope

This unit corrects the canonical `CL-011` record in `docs/claim_ledger.csv` so that it
binds to the primary S10b data study rather than to the later MV5 reuse. It does not
change the tracked S10b result or authorize a detector-wide dead-time or pile-up-rate
claim.

## Start state

- Initial remote `main`: `563582a0d7b1d3b0fac3e33cc241b4981a21912e`.
- Pre-change ledger Git blob: `8135794d6f0b22da6b760bf6234bb8e1cae795fb`.
- The reconstructed pre-change bytes matched that blob exactly.
- The old row cited secondary MV5 files, including a nonexistent `results.json`, and
  labelled the result `data_mc_self_consistent` / `VALIDATED`.
- It also supplied unsupported `0.5`, `1.0`, and `1.12 ns` uncertainty components and
  the wrong selected-pulse count (`213843`).

## Primary evidence and independent reconstruction

Primary tracked evidence is the S10b bundle at source commit
`da9651c56ef6495ce9656d84b69b600daa6d8f86`:

- `reports/1781000867.546870.5c124aaf/REPORT.md`;
- `reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py`;
- `reports/1781000867.546870.5c124aaf/result.json`;
- `reports/1781000867.546870.5c124aaf/manifest.json`;
- `reports/1781000867.546870.5c124aaf/heldout_run_summary.csv`.

The held-out table contains 14 unique run rows and 252,266 selected pulses. The
unweighted mean of the fourteen run-level 10% template-crossing estimates relative to
CFD20 is `124.79018394263471 ns`. Replaying the recorded seed and producer RNG stream
reproduces the run-bootstrap percentile interval
`[123.33094981246663, 126.35875117626817] ns`.

## Corrected canonical contract

`CL-011` now records:

- claim text: `S10b run-average 10% template live-time relative to CFD20`;
- value: `124.79018394263471 ns`;
- 95% run-bootstrap interval:
  `[123.33094981246663, 126.35875117626817] ns`;
- `n_runs=14` and `n_data=252266`;
- `truth_type=data_measurement`;
- `status=DONE_DATA_ONLY` and `allowed_status_validated=NO`;
- primary S10b report, producer, result, manifest, and source commit;
- `blocked_by=BLK-S10B-001`;
- no statistical/systematic/total uncertainty decomposition.

The notes state that this is a threshold-, selection-, and run-weighting-specific
estimand, not a detector-wide universal dead time, and that MV5 uses the value as an
input rather than independently validating it.

## Reproducible validation

Commands executed on the exact reconstructed candidate files:

```text
python -m py_compile tests/test_tau_eff_claim_current.py
pytest -q tests/test_tau_eff_claim_current.py

2 passed in 0.02s
```

Additional checks:

- all 27 CSV rows, including the header, contain exactly 43 fields;
- `CL-011` occurs exactly once;
- the regression reconstructs the 14-run count, 252,266 pulse count, central value,
  interval, and source commit from tracked S10b artifacts;
- JSON and SVG evidence parse successfully;
- the changed Python file has no line longer than 100 characters.

Candidate ledger provenance before publication:

- bytes: `21431`;
- SHA-256: `e532f3af57c2d50d261bac6a0b40546decc45a4f780fd57f92afc279a4d71ea4`;
- Git blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`.

A first direct contents write exposed an unrelated-path preservation mistake in the
candidate transcription: two existing P04p/P07e producer/config paths had periods
where the canonical rows used underscores. A byte-identity check caught the mismatch,
and corrective commit `ab03023366396caaa97abc4cb7ea9a81aeae0731` restored the
unrelated paths. The final ledger blob is the validated
`254dc5b64945260193d6b1bd4146bd6400ad28cf`.

## Remaining public synchronization

The canonical ledger correction does not silently rewrite every dependent public
surface. `WIKI.md`, Chapter 1, and Chapter 5 still contain stale `VALIDATED`,
`data + MC self-consistent`, rounded-interval, and unsupported uncertainty wording.
Those files require a separate exact-content remediation with focused regressions and
link checks.

## Scientific boundary

No raw ROOT file was reprocessed, no waveform template or fit was rerun, and no new
systematic uncertainty was estimated. The result remains `DONE_DATA_ONLY` and blocked
under `BLK-S10B-001` pending threshold and run-weighting sensitivity, independent
cross-method or external closure, and an accepted systematic uncertainty model. No
accepted Rmax, universal detector dead time, calibration, or detector-performance
claim follows from this ledger correction.
