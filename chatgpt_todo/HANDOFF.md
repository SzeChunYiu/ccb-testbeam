# Latest Scientific Review Handoff

## Session

- UTC: `2026-07-23T23:08:25Z`
- Task: `AUD-G4-019`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `eec220db6807d3d3615d92c6d39d4fb2e18e4335`
- Validated implementation/evidence head: `807febe85c35b537c53a5acdf1795ee9a67d7cb2`
- Remote main before handoff: `b29e86b5aec0cc0493e6b795cb7877c00d174f77`
- Destination: direct to `main`
- Acceptance: COMPLETE for simulation input byte-snapshot provenance; stopping-power physics closure remains PARTIAL/BLOCKED.

## Review and finding

The run inspected current main history, repository permissions, the canonical stopping-power comparison, shared simulation parser, parser tests, mandatory audit records, commit status, and PR #868. PR #868 remains closed, unmerged, and non-mergeable and was not modified. A direct clone failed because the runtime could not resolve `github.com`; authenticated GitHub reads and writes were used.

Validator v1.1.0 parsed CSV rows with `Path.read_text()`, then later measured byte size and SHA-256 through separate path reads. A replaced input path could therefore yield normalized rows from bytes A but provenance from bytes B. Invalid UTF-8 also escaped as an uncontrolled decoder exception.

## Validated correction

`tools/audit/validate_stopping_power_sim_table.py` v1.2.0 now:

1. reads exact bytes once;
2. decodes and parses that byte string;
3. derives byte count and SHA-256 from the same bytes;
4. records `input_snapshot_method=SINGLE_READ_EXACT_BYTES`;
5. converts invalid UTF-8 into controlled `SimulationTableError` status 2.

Existing particle, energy, deposit, track-length, alias, physical-value, completeness, and raw/quenched gates are retained.

## Validation

```text
python -m py_compile \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_snapshot.py

python -m pytest \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_snapshot.py -q

19 passed in 2.01s
```

The former algorithm fails both new tests: provenance follows replacement bytes, and invalid UTF-8 raises an uncaught decoder exception. JSON and SVG parsing passed. Changed Python lines are at most 94 characters. The committed implementation blob `6a57b93d6fb4f63a7b714b858d379f02b5a7eda0` matches the locally validated blob.

Not run: full repository pytest, ruff, Geant4/CTest, ROOT processing, real simulation, or GitHub Actions.

## Evidence

- `docs/validation/stopping_power_sim_snapshot_audit.md`
- `docs/validation/stopping_power_sim_snapshot_validation.json`
- `docs/validation/stopping_power_sim_snapshot.svg`
- `chatgpt_todo/archive/2026-07-23T230825Z_AUD-G4-019_SIM_INPUT_SNAPSHOT.md`

The SVG is synthetic software regression evidence, not detector data.

## Direct-main commits

- `efc9610bd382ea52f6bbc8e53be87af6c74766fa` — implementation
- `76b5e1dcf5e8fb3ad9c66a9646dd8ddab3d3dcea` — regression tests
- `964042dc25b1b0abcd0eac0ec35e4f1b3268abe7` — audit report
- `f28049ce952bf5e8194f7c3936adab2401d713b6` — validation JSON
- `807febe85c35b537c53a5acdf1795ee9a67d7cb2` — visual evidence
- `17322a138cc160eef09beadd2ede6df5a4076625` — active task
- `462738e51fdfc93cb5eaef34e0de1d8260369c83` — backlog
- `b29e86b5aec0cc0493e6b795cb7877c00d174f77` — immutable archive

`SESSION_LOG.md` was not replaced because the connector has no safe append primitive and complete byte-safe current content was unavailable. Replacing the append-only file could destroy prior provenance. The immutable archive contains the complete run record.

## Scientific boundary

This validates parser/provenance identity only. No real Geant4 export, accepted projectile-energy-loss observable, uncertainty budget, stopping-power closure, calibration, or detector-performance result was produced. `BLK-G4-SP-001` remains open. The next work remains immutable real-export validation (`AUD-G4-011`) and accepted projectile-loss closure (`AUD-G4-005`).
