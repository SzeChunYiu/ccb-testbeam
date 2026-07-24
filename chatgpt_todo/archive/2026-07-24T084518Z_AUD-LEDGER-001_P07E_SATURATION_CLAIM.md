# AUD-LEDGER-001 — P07e saturation claim reconstruction

- **Session stamp:** `2026-07-24T084518Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main SHA:** `71907c86124f2ac0e5c4ee9fd4acc05967a02268`
- **Primary task:** reconstruct malformed claim-ledger row `CL-016` and audit the P07e saturation-recovery evidence hierarchy.
- **Status:** PARTIAL; the ledger row and audit gate are validated, while historical producer-byte provenance and production-transfer validation remain blocked.

## Repository material inspected

- `docs/claim_ledger.csv`
- `tools/audit/validate_claim_ledger_schema.py`
- `reports/1781018174.2030.05ac1ce2/REPORT.md`
- `reports/1781018174.2030.05ac1ce2/result.json`
- `reports/1781018174.2030.05ac1ce2/manifest.json`
- `configs/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.json`
- `scripts/p07e_1781018174_2030_05ac1ce2_duplicate_saturation_validation.py`
- commits `f20e1b0bceac4eeae4532c9e871a363d6dce08d7` and `d30d91bc4b2988d3b1fffa8d7d44e58e1130603b`
- current `chatgpt_todo/` protocol, backlog, active task, blocker register, handoff, and recent history.

## Confirmed result and scientific interpretation

The committed P07e study contains a synthetic pseudo-saturation recovery test and an external held-out odd-duplicate validation. They are not equivalent evidence.

- pseudo-saturation ML charge res68: `0.03669062665507541`;
- external validation rows: `183132` across `33` held-out runs;
- external ML charge res68: `0.1763577793605039`;
- ML run-block 95% interval: `[0.17304334869529975,0.18060166173702746]`;
- external raw charge res68: `0.12079374117700271`;
- raw run-block 95% interval: `[0.11700387021774719,0.12536373643016782]`;
- traditional-template external charge res68: `0.12077766801970549`;
- independently reconstructed ML-minus-raw degradation: `+0.05556403818350119`.

The ML lower interval bound exceeds the raw upper interval bound for the recorded run-block bootstrap. The external real-data duplicate closure therefore does not support applying the ML ratio-transfer correction, despite strong synthetic pseudo-saturation recovery.

- **Policy:** `P07E_EXTERNAL_DUPLICATE_CLOSURE_OVERRIDES_PSEUDO_SATURATION`
- **Decision:** `WITHHOLD_ML_CORRECTION`

This is a source-artifact interpretation, not a new detector-data calculation. No raw ROOT input or bootstrap ensemble was available for independent rerunning.

## Confirmed provenance defect

The manifest records execution commit `f20e1b0bceac4eeae4532c9e871a363d6dce08d7`, an earlier S05e commit that does not contain the P07e producer path. The producer and result bundle were introduced later by `d30d91bc4b2988d3b1fffa8d7d44e58e1130603b`.

The manifest hash-binds outputs and lists 33 raw ROOT input hashes, but it does not record the producer script SHA-256 or a clean/dirty worktree state. Consequently, the exact producer bytes used for the historical result are not recoverable from the manifest alone.

Stable blocker:

- **BLK-P07E-001 — historical P07e producer bytes and transfer authorization**
- Resolve by recovering an exact content-addressed producer snapshot or rerunning from a clean exact commit with producer/config/input/output hashes, then performing preregistered cross-stave and independent new-run validation before production use.

## Changes delivered

- `tools/audit/audit_p07e_saturation_claim.py` v1.0.0
- `tests/test_audit_p07e_saturation_claim.py`
- `docs/validation/p07e_saturation_claim_audit.md`
- `docs/validation/p07e_saturation_claim_validation.json`
- `docs/validation/p07e_saturation_claim.svg`
- reconstructed exact-width `CL-016` in `docs/claim_ledger.csv`
- refreshed `docs/validation/claim_ledger_schema_validation.json`
- refreshed `docs/validation/claim_ledger_schema.svg`
- updated `chatgpt_todo/ACTIVE_TASK.md`

Core direct-main commits before this archive:

- `3ad52b6cfa72f818d4dab2f79ec7705767e557a9` — `feat(audit): validate P07e saturation claim hierarchy`
- `0dbcca7179bb081eb5b20c42ade449d0b984ae22` — `test(audit): cover P07e evidence hierarchy`
- `50736732ce6c394c4ab5779d1a227525b2a6c11f` — `docs(validation): record P07e saturation claim audit`
- `06edd1acf843a0874e84e1d73ffa40a1799dd95c` — `docs(validation): add P07e saturation validation record`
- `b20d503be2c8c99e468ed6e6ddac3d25ea3d4bb8` — `docs(validation): visualize P07e evidence hierarchy`
- `787938208d37061ab0a5e35678b34b2dbb50e027` — `fix(ledger): reconstruct P07e saturation claim`
- `2b297c715ba72df98b85f0aa493b2ec01a9a98be` — `docs(validation): advance ledger width audit to seven rows`
- `961fdde6020bbabf8165e61d6e9c8a9af5e911eb` — `docs(validation): refresh ledger width visualization`
- `a4105467dd5db61bfb9e8de585170050b453e4fe` — `docs(audit): track P07e claim reconstruction`

## Validation performed

```text
python -m py_compile \
  tools/audit/audit_p07e_saturation_claim.py \
  tests/test_audit_p07e_saturation_claim.py

python -m pytest tests/test_audit_p07e_saturation_claim.py -q

4 passed in 0.62s
```

Additional checks:

- source-faithful malformed fixture returned `FLAWED` with ledger-width and producer-provenance findings;
- corrected hash-bound synthetic chain returned `VALIDATED`;
- manifest output-hash mutation failed closed;
- CLI status and JSON/SVG output were checked;
- JSON parsing and SVG XML parsing passed;
- maximum changed Python line length: 100;
- committed ledger Git blob `853d955f449268ec614ac61f33f243d30cf473e0` matches the locally validated exact bytes;
- ledger exact-width state advanced from 6/26 to 7/26, leaving 19 rows withheld.

## Unrun checks and limitations

- no raw ROOT extraction or waveform/event-selection reproduction;
- no ExtraTrees/Huber model rerun;
- no bootstrap resampling rerun;
- no cross-stave or independent new-run transfer validation;
- no full repository pytest or ruff run;
- no GitHub Actions success claimed for these commits;
- no detector calibration or detector-performance improvement claimed.

## Next actions

1. Register and resolve `BLK-P07E-001` with content-addressed producer provenance.
2. Preregister cross-stave and independent-run validation; do not tune on the final validation sample.
3. Keep `CL-016` `GATED` and withhold the ML correction until those acceptance conditions pass.
4. Continue source-backed reconstruction of the remaining 19 malformed claim-ledger rows.
