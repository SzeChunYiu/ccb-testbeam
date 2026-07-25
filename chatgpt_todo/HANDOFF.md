# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-25T042815Z`
- **Task:** `AUD-DELTAE-001`
- **Unit:** fail-closed, content-addressed and transactional A-002 ΔE-E rerun path
- **Initial remote `main`:** `86c6e086d3716ab3ac10481fae92f1a316adf2d3`
- **Validated implementation/evidence head:** `93a5589c8957d13a1774093586a5ed968049a2c0`
- **Complete delivery handoff / recorded after-SHA:** `d6c1a65a13765e045555791f7168c119a79abd15`
- **Immutable archive:** `chatgpt_todo/archive/2026-07-25T042815Z_AUD-DELTAE-001_STRICT_RERUN.md`
- **Destination:** direct sequential commits to remote `main`; no force-push, branch transport, PR, or history rewrite
- **Push result:** GitHub contents writes returned successful direct-main commit SHAs; post-write history confirmed `d6c1a65a13765e045555791f7168c119a79abd15` on remote `main`
- **Acceptance:** **PARTIAL** — software/provenance gate validated; exact evidence-authorized A-002 production rerun remains blocked

This confirmation-only update records that the complete delivery handoff is present on remote `main`. It does not change the scientific implementation or acceptance state.

## Repository evidence and confirmed defect

The existing bridge is `scripts/single_stave/deltaE_E_data_bridge.py`, Git blob `7f50ce667a6cde07e94717d0187831da4d8459ac`. Its focused bridge tests are blob `3b59a793f5d67e6a0d3c7117c42ec41ad7b84a90`.

The bridge already implements the scientifically important transformation corrections:

- one output row per `(source_file_id, run, evt)`;
- `eventno` retained only as a collision diagnostic;
- explicit amplitude-column and convention selection;
- signed polarity-aware absolute-code conversion;
- fail-closed rejection of opposite-polarity/nonfinite rows;
- stopping-distribution total equal to physical-event count.

Its former command-line path still used hard-coded input/output locations, parsed by pathname without an expected exact input digest, wrote JSON/CSV/PNG directly, implicitly replaced outputs, and omitted repository/code/command/runtime/output identities. These defects prevented a later reviewer from proving that the output bundle was generated together from the declared immutable bytes and code.

## Correction delivered

Added `scripts/single_stave/deltaE_E_data_bridge_strict.py`, blob `76f7ffda2c2af92b400ca61f2f12c2b34fff7dba`, under policy:

`DELTAE_BRIDGE_CONTENT_ADDRESSED_TRANSACTIONAL_RERUN`

The runner:

- requires an expected exact input SHA-256;
- parses one captured byte snapshot and requires the same path identity after processing;
- requires a clean tracked checkout at an explicit expected commit;
- records runner and bridge script identities, command, platform and package versions;
- requires explicit source identity, amplitude column, convention, and conditional polarity;
- delegates scientific event construction to the existing bridge rather than creating a second method;
- validates required columns, unique composite keys, source identity, finite ADC values, physical-event count, and stopping-bin total;
- repeats provenance in every event-CSV row and in visible and embedded SVG metadata;
- rejects an output directory that contains a protected input/code path;
- requires explicit `--overwrite` for an existing bundle;
- stages all three output files in a sibling directory, renames the complete directory into place, and restores the previous bundle after an injected in-process publication failure;
- labels successful software output `BLOCKED_PENDING_A002_EVIDENCE_AND_CLOSURE`.

`result.json` is the bundle commit marker and records the expected CSV/SVG identities. The runner re-reads all published files and verifies their byte counts and SHA-256 values.

Also added:

- `tests/test_deltae_data_bridge_strict.py`, blob `796ccc908d54246881b3774fba5a7853e8201b03`;
- `scripts/single_stave/DELTAE_STRICT_RERUN.md`, blob `f765f72df25eb3259edc9f6ae1cafbf292f22858`;
- `tools/audit/render_deltae_strict_rerun_evidence.py`, current blob `b88ecc889b47c1f86d538896c2599ea9b4c96c95`;
- Markdown, JSON, and SVG validation evidence under `docs/validation/`;
- backlog state, active-task completion, and immutable archive.

## Validation

```text
python -m py_compile \
  scripts/single_stave/deltaE_E_data_bridge_strict.py \
  tests/test_deltae_data_bridge_strict.py

PYTHONPATH=. pytest -q tests/test_deltae_data_bridge_strict.py

9 passed in 1.79s
```

The tests cover a valid content-addressed bundle, input-hash mismatch, repository-commit mismatch, input/output containment alias, implicit overwrite preservation, injected publication failure with rollback, input replacement during processing, duplicate physical keys, and nonfinite output ADC values.

The synthetic fixture produced two event rows, two unique composite keys, and stopping-bin total two. JSON and SVG XML parsing passed. Changed Python lines were at most 97 characters. This is synthetic software/provenance validation, not detector data.

Evidence:

- `docs/validation/deltae_strict_rerun_audit.md`;
- `docs/validation/deltae_strict_rerun_validation.json`;
- `docs/validation/deltae_strict_rerun.svg`.

No repository-wide pytest, ruff, real bridge run, ROOT processing, or GitHub Actions success is claimed.

## Direct-main commit sequence

- `064aafc9354f72991a143afbdfc4a3f76a3a601f` — task claim;
- `58752eda055dabc80606c8bdf2a6a28214742cd5` — strict runner;
- `723bdf21145e6168abb810ab9ea211e76a7b5118` — focused tests;
- `d955b1aff119eedc236dc8b1d2a4b19d5e761c19` — rerun instructions;
- `79e85b08beb8ee806ab0e2e4e044531eb48f91d0` — evidence renderer;
- `1c9957db9b107d9df0779cdfa065fd20a14236c5` — compact SVG text output;
- `0f6a232d430df82bc8e46736d089262a29f8a864` — validation JSON;
- `7968b249adcf8b3245baa205edf8103231895b2b` — visual evidence;
- `b2b1aea516ad8579de9b7f6f0a990b2c0fa5a496` — audit report;
- `165169d38fda6e3d1dc6dd828522cb1029cf473b` — backlog progress;
- `2606d00c377746b991c12824911f89012357d739` — immutable archive;
- `93a5589c8957d13a1774093586a5ed968049a2c0` — active-task completion and validated implementation/evidence head;
- `d6c1a65a13765e045555791f7168c119a79abd15` — complete delivery handoff, confirmed on remote `main`.

## Scientific boundary and next action

Exact A-002 pulse-table bytes and independently reviewable amplitude-convention/polarity evidence were unavailable. No production rerun, accepted stopping distribution, threshold/pedestal/calibration uncertainty, ΔE-E particle-identification result, or detector-performance claim was produced.

`BLK-AMP-001`, `AUD-AMP-009`, `AUD-AMP-010`, and `AUD-DELTAE-002` remain operative. Run the documented strict command only after evidence authorization, then retain the complete bundle hashes, inspect all warnings, quantify threshold/pedestal/calibration/selection effects, and require independent closure.

`SESSION_LOG.md` was not replaced in this connector run because the available action replaces the entire file and a complete byte-safe append was not exposed. Replacing a truncated or paged snapshot would violate the append-only provenance rule. The immutable archive and this handoff preserve the complete append-equivalent session record; this specific mandatory aggregate synchronization step remains unmet.
