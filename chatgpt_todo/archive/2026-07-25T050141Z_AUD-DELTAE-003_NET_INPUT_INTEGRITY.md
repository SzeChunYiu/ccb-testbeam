# Immutable handoff — AUD-DELTAE-003 net-input integrity

- **UTC stamp:** `2026-07-25T050141Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `67a7cdd6ef0dc64f00a9ebb43077d2acc1a7418e`
- **Task:** `AUD-DELTAE-003`
- **Status:** `PARTIAL`
- **Policy:** `DELTAE_NET_AMPLITUDE_ROWS_MUST_BE_FINITE_NUMERIC_BEFORE_AGGREGATION`

## Repository evidence

Current bridge: `scripts/single_stave/deltaE_E_data_bridge.py`, Git blob
`7f50ce667a6cde07e94717d0187831da4d8459ac`.

Observed operations: direct net assignment at source lines 183-184, aggregation
and pivot at 200-215, then missing-layer zero fill at 218-221. The absolute path
has a finite numeric gate, but the net path does not.

## Demonstrated failure

The executable current-control fixture preserves those exact relevant
operations. With one physical event containing finite B4 and NaN B2, the bridge
accepts the event and reports `amp_B2=0.0`. With positive-infinity B2, the bridge
accepts infinity. The audit returns `FLAWED` with three findings:

- `NONFINITE_NET_ROW_NOT_REJECTED`;
- `NONFINITE_NET_ROW_BECAME_ZERO`;
- `INFINITE_NET_ROW_NOT_REJECTED`.

## Files delivered

- `tools/audit/audit_deltae_net_input_integrity.py`
- `tests/test_audit_deltae_net_input_integrity.py`
- `tools/audit/render_deltae_net_input_integrity_evidence.py`
- `docs/validation/deltae_net_input_integrity_audit.md`
- `docs/validation/deltae_net_input_integrity_validation.json`
- `docs/validation/deltae_net_input_integrity.svg`

## Validation

Focused `py_compile` passed. Focused pytest returned `5 passed in 0.12s`.
Validation JSON and SVG XML parsed. Changed Python lines are at most 95
characters.

## Scientific boundary

This is synthetic software/provenance validation only. No exact A-002 pulse
bytes were available; no production rerun, stopping distribution, ΔE-E plot,
calibration, uncertainty budget, or detector-performance claim was produced.

## Next action

Add fail-closed finite numeric validation to the canonical net-amplitude path
before aggregation, add bridge and strict-runner regressions, rerun all focused
checks, and only then perform the content-addressed A-002 rerun after amplitude
convention and polarity evidence is authorized.

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices require a
safe full-current append/patch. This connector exposes whole-file replacement;
those shared files were not reconstructed from partial responses in this unit.
The present immutable archive and latest handoff retain the complete run.
