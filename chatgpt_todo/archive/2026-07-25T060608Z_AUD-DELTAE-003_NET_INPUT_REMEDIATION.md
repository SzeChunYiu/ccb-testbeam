# Immutable scientific-review record — AUD-DELTAE-003

## Session identity

- **UTC stamp:** `2026-07-25T060608Z`
- **Owner:** scheduled scientific-review session
- **Task:** `AUD-DELTAE-003`
- **Initial remote main:** `421aafd6894b6ba3b92b98f616141084742b6812`
- **Scope:** remediate fail-open nonfinite net-amplitude handling in the canonical A-002 ΔE-E bridge
- **Destination:** sequential direct commits to remote `main`; no branch, force-push, history rewrite, or stale PR transport

## Repository state and coordination reviewed

Inspected current `main`, recent commits, current status checks, PR #868, repository
README, the canonical bridge, strict runner, existing bridge tests, prior audit tool,
validation evidence, and the required `chatgpt_todo/` records.

PR #868 was closed, unmerged, and non-mergeable and was not modified. The initial
main commit had no attached combined status checks.

The previous handoff and active task identified exactly one open remediation:
coerce the selected net-amplitude field and reject nonfinite values before
aggregation, pivoting, and missing-layer zero filling.

## Confirmed former defect

Prior source Git blob:

`7f50ce667a6cde07e94717d0187831da4d8459ac`

The net branch directly assigned `df[signal_column] = df[ampcol]`. A synthetic
physical event with NaN B2 and finite B4 was accepted after B2 disappeared during
pivoting and became `amp_B2 = 0.0`. Positive infinity was retained. These
transformations could change the ΔE coordinate and stopping-layer classification
without an explicit input rejection.

## Correction

The canonical bridge now:

1. converts net amplitudes with `pd.to_numeric(errors="coerce")`;
2. requires every converted value to satisfy `np.isfinite`;
3. raises before `groupby`, `pivot_table`, or missing-layer zero filling when any
   present row is nonfinite or nonnumeric;
4. preserves zero filling only for genuinely absent stave measurements after
   finite row validation and event/stave aggregation;
5. records convention-specific `amplitude_validation` and an explicit
   `missing_layer_policy` in the result dictionary.

Implementation commit:

`910efe6b37b3d16a31275e9c0502ee2bd5512ab9`

Current source Git blob:

`2820c461508990d743cc53754c33ec2934a3c9ad`

Exact source byte provenance:

- bytes: `13225`;
- SHA-256: `8295d117b068795ea48015c14cbd7531094dae5931283e5e9205121d5eaa8011`.

## Regression and validation

Added `tests/test_deltae_net_input_remediation.py` in commit
`64f486988252145d3d6744ddc4a1a0c828e59cf1`.

The tests cover:

- NaN;
- positive infinity;
- negative infinity;
- nonnumeric net input;
- finite-value preservation;
- genuine missing-layer zero semantics;
- successful execution of the existing net-integrity audit against the corrected
  canonical bridge;
- strict-runner rejection before output publication.

Executed on exact reconstructed current repository files:

```text
python -m py_compile \
  scripts/single_stave/deltaE_E_data_bridge.py \
  tools/audit/audit_deltae_net_input_integrity.py \
  tests/test_deltae_net_input_remediation.py

pytest -q \
  tests/test_deltae_data_bridge_composite_key.py \
  tests/test_deltae_net_input_remediation.py

17 passed in 0.31s
```

The existing executable audit returned `VALIDATED` with zero issues. The finite
control remained accepted, while NaN and positive infinity were rejected. JSON
and SVG parsing passed. Changed Python lines were at most 95 characters.

The exact current strict-runner delegation and pre-publication path were inspected.
The new repository test calls the actual `run_strict_bridge` API. The connector
did not expose a complete network checkout, so local execution used exact current
files plus a faithful reconstruction of the unchanged runner path. No
repository-wide pytest or CI success is claimed.

## Evidence files

- `docs/validation/deltae_net_input_integrity_audit.md`;
- `docs/validation/deltae_net_input_integrity_validation.json`;
- `docs/validation/deltae_net_input_integrity.svg`;
- `tools/audit/render_deltae_net_input_integrity_evidence.py`.

Evidence commits completed before this archive:

- `20bc4b7b36c6942578264fee5d9126aefaf6ff06` — renderer;
- `ce05cb0d29adda547c4260f39f0d72383903269f` — JSON record;
- `ef9d29d79945fd1898ae462c0a4312819097559c` — SVG evidence;
- `2ce21a737fc01f05b1dab8669a13a2bcaecf58c8` — remediation report.

## Acceptance and scientific boundary

The software-remediation unit of `AUD-DELTAE-003` is `COMPLETE`. Invalid present
net-amplitude rows can no longer be converted into absent-layer zeros or
propagate infinity into the event table.

This does not authorize A-002 scientific output. Exact A-002 input bytes,
measured amplitude convention and polarity evidence, a production rerun,
stopping fractions, an uncertainty budget, ΔE-E PID, calibration, and detector
performance remain blocked under `BLK-AMP-001`, `AUD-DELTAE-001`, and
`AUD-DELTAE-002`.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices are shared long-lived files. The available connector replaces complete
files and does not expose a byte-safe append or line patch operation. Their
current state was returned in paged or truncated responses; replacing a partial
reconstruction could erase unrelated concurrent provenance. This immutable
record and the latest `HANDOFF.md` therefore provide the complete append-equivalent
record. The aggregate synchronization requirement remains explicitly unmet for
this run rather than being fabricated or applied destructively.
