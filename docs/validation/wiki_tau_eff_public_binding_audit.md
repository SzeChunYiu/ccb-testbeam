# WIKI S10b live10 public-binding audit

## Scope

This audit reviews whether the two public `WIKI.md` locations that state the
`CL-011` effective-live-time result are bound to the exact canonical S10b
estimand, interval, truth type, status, counts, provenance boundary, and
limitations.

- Audit ID: `AUD-WIKI-004`
- Session stamp: `2026-07-25T102318Z`
- Initial remote `main`: `dcd30497d7e83a35d686b8835aefdb2537fbcf02`
- WIKI Git blob: `91e82c59a2b59b285c6a529c0637ed665be2c4fd`
- Claim-ledger Git blob: `254dc5b64945260193d6b1bd4146bd6400ad28cf`
- Policy: `WIKI_TAU_EFF_MUST_BIND_EXACT_S10B_ESTIMAND_AND_INTERVAL`

The immediately preceding concurrent change corrected the full Chapter 5 text
at commit `dcd30497d7e83a35d686b8835aefdb2537fbcf02`. This unit does not duplicate
that chapter rewrite; it audits the still-stale root WIKI and adds a fail-closed
public-binding gate.

## Canonical source contract

Exact-width ledger row `CL-011` records:

- measurand: S10b run-average 10% template live-time relative to CFD20;
- value: `124.79018394263471 ns`;
- run-bootstrap 95% interval:
  `[123.33094981246663, 126.35875117626817] ns`;
- 14 runs and 252266 selected pulses;
- `truth_type=data_measurement`;
- `status=DONE_DATA_ONLY` and `allowed_status_validated=NO`;
- primary source commit
  `da9651c56ef6495ce9656d84b69b600daa6d8f86`;
- blocker `BLK-S10B-001`;
- no separate statistical, systematic, or total uncertainty components.

The row states that the result is threshold-, selection-, and run-weighting-
specific, not a detector-wide universal dead time. MV5 reuses the rounded value
as a simulation input rather than independently validating the data
measurement.

## Confirmed public defects

The current canonical-results row publishes `124.79 ns`, unsupported `0.5` and
`1.0` components, `data + MC self-consistent`, and `VALIDATED`.

The current pile-up section separately states that tau-eff remains validated,
publishes `124.79 ns` with `VALIDATED`, and omits the exact interval, run and
pulse counts, run-average estimand, `BLK-S10B-001`, and the MV5 input-versus-
validation distinction.

These are not only rounding differences. They change the uncertainty model,
truth type, acceptance state, and scientific interpretation.

## Method improvement

`tools/audit/validate_wiki_tau_eff_public_binding.py` validates exact bytes with
strict UTF-8 and binds evidence to two unique locations:

1. `### Canonical Results Table`;
2. `## 5. Pile-up Analysis`.

The gate requires exact central and interval text, blank stat/syst display,
`data_measurement`, `DONE_DATA_ONLY`, 14 runs, 252266 selected pulses, the
run-average and run-bootstrap semantics, the non-universal-dead-time caveat,
MV5 reuse language, and `BLK-S10B-001`. Exact tokens placed in an unrelated
decoy appendix cannot rescue stale claim sites.

It also rejects duplicate section anchors, malformed or duplicate `CL-011`
rows, invalid UTF-8, and destructive output aliases. JSON publication is
atomic.

## Validation

Executed on reconstructed exact contract fixtures and exact current public
excerpts:

```text
python -m py_compile \
  tools/audit/validate_wiki_tau_eff_public_binding.py \
  tests/test_validate_wiki_tau_eff_public_binding.py \
  tools/audit/render_wiki_tau_eff_public_binding_evidence.py

PYTHONPATH=. pytest -q tests/test_validate_wiki_tau_eff_public_binding.py

7 passed in 1.63s
```

The current exact excerpts return `FLAWED` with 24 findings across eight code
families. A corrected two-location fixture returns `VALIDATED` with zero
findings. The decoy-token regression proves location binding. JSON parsing,
SVG XML parsing, strict UTF-8 handling, alias rejection, and atomic-output
checks passed. Changed Python lines are no longer than 95 characters.

## Files

- `tools/audit/validate_wiki_tau_eff_public_binding.py`
- `tests/test_validate_wiki_tau_eff_public_binding.py`
- `tools/audit/render_wiki_tau_eff_public_binding_evidence.py`
- `docs/validation/wiki_tau_eff_public_binding_validation.json`
- `docs/validation/wiki_tau_eff_public_binding.svg`

## Acceptance and scientific boundary

Status: `PARTIAL`.

The defect and fail-closed gate are validated. The root WIKI itself is not
rewritten in this audit unit. Its remediation must update both public locations
and run this gate plus the existing front-door, canonical-results, and broken-
link checks before declaring the public synchronization complete.

This is documentation and provenance validation only. No ROOT input was
reprocessed, no waveform fit was rerun, no new uncertainty was estimated, and
no detector-wide dead time, accepted Rmax, calibration, or performance result
is established.
