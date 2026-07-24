# Latest Scientific Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T084518Z`
- **Task:** `AUD-LEDGER-001`
- **Focused task:** `AUD-P07E-001`
- **Unit:** P07e B2 saturation ratio-transfer evidence hierarchy, historical producer provenance, and exact-width reconstruction of `CL-016`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote `main`:** `71907c86124f2ac0e5c4ee9fd4acc05967a02268`
- **Validated delivery head before this handoff update:** `ace4fe0e77afa1a938084e016e36bf9201cb121c`
- **Destination:** direct sequential commits to `main`; no task branch, pull request, force-push, or history rewrite
- **Acceptance:** audit implementation and evidence `VALIDATED`; `CL-016` and production saturation correction remain `GATED`; `AUD-LEDGER-001` and `AUD-P07E-001` remain `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected current `main`, recent repository history, the active P04p handoff, mandatory `chatgpt_todo/` records, the canonical 43-column claim ledger, the P07e report/result/manifest/script/config chain, and the relevant historical commits. Concurrent P04p commits were preserved and no active unit was duplicated.

A local clone was not available because the runtime could not resolve `github.com`. Repository facts were therefore established through authenticated GitHub file/blob/commit reads. Executable validation used source-faithful reduced fixtures with exact recorded P07e metric values; fixtures are not detector data.

## Study and claim reviewed

P07e ticket `1781018174.2030.05ac1ce2` tests a ratio-transfer model for high-amplitude B2 waveforms. Its result contains two scientifically different evidence layers:

1. synthetic pseudo-saturation closure on clean pulses;
2. external leave-one-run-out validation against the paired odd duplicate channel.

The generic malformed ledger text `Saturation recovery ML` did not identify which layer controlled scientific authorization and did not preserve metric, interval, baseline, sample size, source paths, or provenance limitations.

## Quantitative reconstruction

Exact committed result values:

- pseudo-saturation ML charge res68: `0.03669062665507541`;
- external validation rows: `183132`;
- held-out runs: `33`;
- external ML charge res68: `0.1763577793605039`;
- ML run-block 95% interval: `[0.17304334869529975,0.18060166173702746]`;
- external raw charge res68: `0.12079374117700271`;
- raw run-block 95% interval: `[0.11700387021774719,0.12536373643016782]`;
- traditional-template external charge res68: `0.12077766801970549`;
- independently reconstructed ML-minus-raw degradation: `+0.05556403818350119`.

The ML lower interval bound exceeds the raw upper interval bound. Under the recorded run-block bootstrap and metric definition, external duplicate charge closure is worse after the ML correction.

- **Policy:** `P07E_EXTERNAL_DUPLICATE_CLOSURE_OVERRIDES_PSEUDO_SATURATION`
- **Scientific decision:** `WITHHOLD_ML_CORRECTION`

The pseudo-saturation result remains useful as a synthetic closure test, but it does not authorize production application to real high-amplitude pulses when the external duplicate test contradicts it.

## Provenance finding

The P07e manifest records execution commit:

`f20e1b0bceac4eeae4532c9e871a363d6dce08d7`

That commit is an earlier S05e rate-study commit and does not contain the recorded P07e producer path. The P07e producer and output bundle were introduced later by:

`d30d91bc4b2988d3b1fffa8d7d44e58e1130603b`

The manifest hash-binds output files and lists 33 raw ROOT input hashes, but it records neither the producer script SHA-256 nor clean/dirty worktree state. Exact historical producer bytes are therefore not recoverable from the manifest alone.

Registered blocker:

- **`BLK-P07E-001` — historical P07e producer bytes and saturation-transfer authorization**

Resolution requires either recovery of a content-addressed producer snapshot or a clean exact-commit rerun with producer/config/input/output hashes, followed by preregistered cross-stave and independent new-run transfer validation.

## Code, tests, evidence, and ledger changes

Added:

- `tools/audit/audit_p07e_saturation_claim.py` v1.0.0;
- `tests/test_audit_p07e_saturation_claim.py`;
- `docs/validation/p07e_saturation_claim_audit.md`;
- `docs/validation/p07e_saturation_claim_validation.json`;
- `docs/validation/p07e_saturation_claim.svg`;
- `chatgpt_todo/archive/2026-07-24T084518Z_AUD-LEDGER-001_P07E_SATURATION_CLAIM.md`.

Updated:

- `docs/claim_ledger.csv` — `CL-016` is now exactly 43 fields;
- `docs/validation/claim_ledger_schema_validation.json`;
- `docs/validation/claim_ledger_schema.svg`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- `BACKLOG.md`;
- `BLOCKERS.md`;
- `CLAIM_EVIDENCE_MATRIX.md`;
- `STUDY_REVIEW_LEDGER.md`;
- `VISUALIZATION_MATRIX.md`;
- this handoff.

`CL-016` now records:

- claim: `B2 saturation ratio-transfer duplicate charge res68`;
- value, interval, 183132 rows, 33 runs, raw baseline, and signed delta;
- truth type `data_external_duplicate_readout`;
- status `GATED`;
- current report/script/result/config/manifest paths;
- CI state `CI_AVAILABLE_PRODUCER_BYTES_UNBOUND`;
- blocker `BLK-P07E-001`.

Claim-ledger width progress advanced from `6/26` to `7/26` exact rows. Nineteen malformed rows remain fail-closed and their late fields remain withheld.

## Validation performed

```text
python -m py_compile \
  tools/audit/audit_p07e_saturation_claim.py \
  tests/test_audit_p07e_saturation_claim.py

python -m pytest tests/test_audit_p07e_saturation_claim.py -q

4 passed in 0.62s
```

Additional validation:

- malformed current-like ledger plus unbound producer fixture returned `FLAWED` with controlled findings;
- aligned hash-bound synthetic chain returned `VALIDATED`;
- mutated manifest output hash failed closed;
- CLI nonzero status, JSON output, and SVG output were checked;
- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length: 100 characters;
- reconstructed ledger bytes match committed Git blob `853d955f449268ec614ac61f33f243d30cf473e0`.

## Direct-to-main commit sequence

- `3ad52b6cfa72f818d4dab2f79ec7705767e557a9` — `feat(audit): validate P07e saturation claim hierarchy`
- `0dbcca7179bb081eb5b20c42ade449d0b984ae22` — `test(audit): cover P07e evidence hierarchy`
- `50736732ce6c394c4ab5779d1a227525b2a6c11f` — `docs(validation): record P07e saturation claim audit`
- `06edd1acf843a0874e84e1d73ffa40a1799dd95c` — `docs(validation): add P07e saturation validation record`
- `b20d503be2c8c99e468ed6e6ddac3d25ea3d4bb8` — `docs(validation): visualize P07e evidence hierarchy`
- `787938208d37061ab0a5e35678b34b2dbb50e027` — `fix(ledger): reconstruct P07e saturation claim`
- `2b297c715ba72df98b85f0aa493b2ec01a9a98be` — `docs(validation): advance ledger width audit to seven rows`
- `961fdde6020bbabf8165e61d6e9c8a9af5e911eb` — `docs(validation): refresh ledger width visualization`
- `a4105467dd5db61bfb9e8de585170050b453e4fe` — `docs(audit): track P07e claim reconstruction`
- `6659a1ea653342f589cae43effbddf1dbe45fae2` — `docs(audit): archive P07e saturation claim review`
- `9bf6c17db7221adf82c69a461f2b97c48d1ffd31` — `docs(audit): register P07e provenance blocker`
- `1d9529528e270172f5e442601c5d1533e63092d3` — `docs(audit): advance ledger audit through P07e`
- `0f0e79031777faa203c086860d6a163d10c838ae` — `docs(audit): add P07e claim evidence gate`
- `02f4cfceefe6a36193cfa0d66e6b90728c376c66` — `docs(audit): register P07e evidence visualization`
- `ace4fe0e77afa1a938084e016e36bf9201cb121c` — `docs(audit): record P07e study review`

All writes returned successful direct-main commit results through the authenticated GitHub connector. A recent-main query confirmed the ordered commit chain through `ace4fe0e77afa1a938084e016e36bf9201cb121c` before this handoff update.

## Unrun checks and scientific boundary

Not run or unavailable:

- raw ROOT extraction and event-selection reproduction;
- ExtraTrees/Huber model refit;
- bootstrap ensemble regeneration;
- cross-stave or independent new-run transfer validation;
- full repository pytest and ruff;
- GitHub Actions for this commit sequence;
- calibration or detector-performance validation.

No raw data, source waveform table, model output, or detector result was modified. No claim is made that the P07e correction improves real charge reconstruction or is production-ready.

`SESSION_LOG.md` was not replaced. The connector exposes complete-file replacement but returned only truncated views of the long append-only file; reconstructing it manually would create an avoidable provenance-loss risk. The complete session record is retained in the immutable archive above and in this handoff. This is an explicit unresolved compliance limitation, not a claim that the append occurred.

## Next actions

1. Recover or cleanly reproduce content-addressed P07e producer provenance.
2. Preregister and run cross-stave plus independent new-run saturation validation without tuning on the final validation sample.
3. Keep `CL-016` `GATED` and withhold the correction until external closure and provenance gates pass.
4. Continue source-backed reconstruction of the remaining 19 malformed claim-ledger rows.
