# Immutable session record — AUD-DELTAE-001 strict rerun

## Identity

- UTC stamp: `2026-07-25T042815Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `86c6e086d3716ab3ac10481fae92f1a316adf2d3`
- Focus: content-addressed and transactional production wrapper for the corrected A-002 ΔE-E bridge
- Acceptance: `PARTIAL`

## Start-of-run inspection

Authenticated GitHub reads inspected repository permissions, current and recent `main` history, open pull requests, PR #868, head status checks, `chatgpt_todo/README.md`, `MASTER_INDEX.md`, `BACKLOG.md`, `ACTIVE_TASK.md`, `HANDOFF.md`, `BLOCKERS.md`, `SESSION_LOG.md`, the current bridge, its focused tests, and related amplitude/ΔE-E tasks.

PR #868 remained closed, unmerged, and non-mergeable. It was not modified. No status checks were attached to the observed head.

## Repository facts and defect

The existing bridge blob `7f50ce667a6cde07e94717d0187831da4d8459ac` already:

- creates one row per `(source_file_id, run, evt)`;
- retains `eventno` only as a collision diagnostic;
- requires explicit amplitude semantics;
- uses signed polarity-aware pedestal conversion;
- rejects opposite-polarity/nonfinite absolute rows;
- verifies that stopping counts sum to the physical-event count.

Its `main()` still used hard-coded paths, read the input by pathname without an expected digest, directly wrote separate JSON/CSV/PNG files, silently replaced existing outputs, and omitted code/commit/command/runtime/output identities. Those are provenance and publication defects, not evidence that the transformation itself is numerically wrong.

## Delivered correction

Added:

- `scripts/single_stave/deltaE_E_data_bridge_strict.py`;
- `tests/test_deltae_data_bridge_strict.py`;
- `scripts/single_stave/DELTAE_STRICT_RERUN.md`;
- `tools/audit/render_deltae_strict_rerun_evidence.py`;
- `docs/validation/deltae_strict_rerun_validation.json`;
- `docs/validation/deltae_strict_rerun.svg`;
- `docs/validation/deltae_strict_rerun_audit.md`.

Policy: `DELTAE_BRIDGE_CONTENT_ADDRESSED_TRANSACTIONAL_RERUN`.

The strict runner requires an expected input SHA-256, verifies the same input path before and after processing, requires a clean tracked checkout at the expected commit, records both script hashes plus command/runtime provenance, validates unique physical keys and finite output values, repeats provenance in CSV/SVG, rejects output containment aliases, requires explicit overwrite, stages the complete JSON/CSV/SVG bundle, and restores an old bundle after an injected in-process publication failure.

## Validation

```text
python -m py_compile \
  scripts/single_stave/deltaE_E_data_bridge_strict.py \
  tests/test_deltae_data_bridge_strict.py

PYTHONPATH=. pytest -q tests/test_deltae_data_bridge_strict.py

9 passed in 1.79s
```

Regression coverage:

1. valid content-addressed reconstructable bundle;
2. input SHA mismatch;
3. repository commit mismatch;
4. input/output containment alias;
5. implicit overwrite preservation;
6. injected publication failure and rollback;
7. input replacement during processing;
8. duplicate physical composite keys;
9. nonfinite output values.

JSON parsing and SVG XML parsing passed. Changed Python lines were at most 97 characters.

Synthetic evidence used two physical events, two unique keys, and stopping-bin total two. It is software/provenance validation, not detector data.

## Direct-main sequence before coordination closeout

- `064aafc9354f72991a143afbdfc4a3f76a3a601f` — task claim;
- `58752eda055dabc80606c8bdf2a6a28214742cd5` — strict runner;
- `723bdf21145e6168abb810ab9ea211e76a7b5118` — focused tests;
- `d955b1aff119eedc236dc8b1d2a4b19d5e761c19` — rerun instructions;
- `79e85b08beb8ee806ab0e2e4e044531eb48f91d0` — evidence renderer;
- `1c9957db9b107d9df0779cdfa065fd20a14236c5` — compact SVG text output;
- `0f6a232d430df82bc8e46736d089262a29f8a864` — validation JSON;
- `7968b249adcf8b3245baa205edf8103231895b2b` — visual evidence;
- `b2b1aea516ad8579de9b7f6f0a990b2c0fa5a496` — audit report;
- `165169d38fda6e3d1dc6dd828522cb1029cf473b` — backlog progress.

GitHub contents writes returned successful direct-main commit SHAs. No force-push, history rewrite, branch transport, or PR was used.

## Scientific boundary

Exact A-002 pulse-table and supporting convention/polarity evidence bytes were unavailable. No production rerun, accepted stopping distribution, threshold study, uncertainty budget, calibration, ΔE-E particle-identification result, or detector-performance claim was produced. `BLK-AMP-001`, `AUD-AMP-009`, `AUD-AMP-010`, and `AUD-DELTAE-002` remain open/partial.

## Next action

After evidence authorization, execute the documented command from a clean exact commit against the immutable A-002 table, inspect every warning, retain the bundle hashes, quantify threshold/pedestal/calibration/selection uncertainty, and require independent closure before restoring any stopping or PID claim.
