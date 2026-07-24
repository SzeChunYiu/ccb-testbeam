# Latest Scientific Review Handoff

## Session

- UTC stamp: `2026-07-24T072257Z`
- Task: `AUD-LEDGER-001`
- Unit: MV0 gain provenance and uncertainty chain (`CL-013`, `CL-014`, `FIG-EN-001`)
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `712adba593c9b84e4617c1fe8013873cd0c5f753`
- Validated implementation/evidence head: `0c27a7d24f225a38ed6471a7fc9c0ea701436dd5`
- Coordination/archive head before this final handoff: `16e92e0113831045b7ecdeb96b44d1a7c75afe8b`
- Destination: direct sequential commits to `main`; no task branch, pull request, force-push, or history rewrite
- Acceptance: audit tooling/evidence `VALIDATED`; the 92 ADC/MeV calibration claim is `WITHHELD`; `AUD-LEDGER-001` remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads reviewed repository permissions/default branch, recent `main` history, open PRs, PR #868, current commit status, mandatory `chatgpt_todo/` records, `docs/claim_ledger.csv`, the MV0 report, committed calibration artifact, tracked producer script at its cited source commit, and `docs/figure_registry.csv`. The initial head was preserved. PR #868 remains closed, unmerged, and non-mergeable and was not modified.

A direct clone was attempted but failed because the runtime could not resolve `github.com`. Repository facts were therefore established through authenticated exact GitHub blob reads. Executable validation used source-faithful reduced fixtures; no result from those fixtures is represented as detector data.

No status checks were attached to the initial reviewed head. No GitHub Actions success is inferred.

## Exact repository evidence

- claim ledger blob: `009f48e218b2439f80b2cebf8ebb06a845488089`
- MV0 report blob: `bc607eb0ae2639c06ab840ff234160958ada60a5`
- MV0 calibration JSON blob: `74e490753d3e821b0a1353490764a5ede0e9bf75`
- tracked producer blob: `fd911daf3f0fd80df20f4112f4f0f40bf3383afd`
- producer source commit: `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`
- figure registry blob: `1a7b6cbdc18bcc742f0578647a5c785aea78582a`

## Confirmed provenance and scientific-reporting defects

1. `CL-013` has 38 fields and `CL-014` has 37 fields under the canonical 43-column ledger header. Their late fields remain withheld under `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.
2. The report and committed calibration artifact declare the v2 data observable as `abs(amplitude_adc - baseline_adc)`.
3. The tracked producer at the recorded source commit instead assigns raw `amplitude_adc` to both the global and per-stave fit arrays. It does not implement the methodology claimed by the artifact.
4. The report's reproduce command uses `--data`, while the producer requires `--data-csv`, and omits required `--truth-npz`.
5. The producer's output schema lacks artifact fields `gain_method`, `gain_systematic_unc_pct`, and `ks_at_median_gain`; the tracked code and committed JSON cannot be one direct execution chain as written.
6. The ledger and `FIG-EN-001` cite stale/nonexistent `scripts/mv0_calibration.py` and `reports/mv0_calibration_1782677847/results.json`. The tracked items are `scripts/mv0_calibrate_from_data.py` and `calibration.json`.
7. The artifact supports the rounded central value 92 ADC/MeV, a stated 30% systematic, KS=0.1577 at the median-matched gain, `n_data=579424`, and `n_mc=321130` for B2. It does not provide a statistical uncertainty, confidence interval, confidence level, or interval construction.
8. Ledger values `stat_unc=14`, `total_unc=31.3`, and interval `[60,124]` are therefore unsupported by the committed calibration artifact and cannot be promoted canonically from it.

## Independent calculation

The central value can be independently reproduced from the committed artifact's stated numbers:

```text
1781 ADC / (26.44 MeV × 0.733) = 91.89639906462777 ADC/MeV
```

This calculation supports rounding to 92 only. It does not establish the fit's shape adequacy, a statistical uncertainty, an interval, coverage, detector calibration validity, or downstream performance.

## Validation delivered

Added:

- `tools/audit/audit_mv0_gain_provenance.py` v1.0.0;
- `tests/test_audit_mv0_gain_provenance.py`;
- `docs/validation/mv0_gain_provenance_audit.md`;
- `docs/validation/mv0_gain_provenance_validation.json`;
- `docs/validation/mv0_gain_provenance.svg`.

Policy:

```text
MV0_GAIN_NOT_CANONICAL_UNTIL_PRODUCER_AND_ARTIFACT_REPRODUCE
```

The audit checks exact target-row widths, stale source tokens, the artifact's declared observable and central-value contract, producer-script syntax/observable/CLI/output schema, report-command compatibility, and exact-byte fixture provenance. It returns 0 for an aligned chain, 1 for measured inconsistencies, and 2 for controlled input/encoding/schema failures.

Commands and results:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_mv0_gain_provenance.py \
  tests/test_audit_mv0_gain_provenance.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_mv0_gain_provenance.py -q

4 passed in 0.64s
```

The current-like fixture returned status 1 with ten findings. The corrected-chain fixture returned `VALIDATED`. JSON and SVG parsing passed. Maximum changed Python line lengths were 100 and 87 characters.

Ruff, full repository pytest, raw-data processing, ROOT/NPZ processing, calibration execution, KS recomputation, bootstrapping, WIKI/link/figure checks, and GitHub Actions were not run.

## Direct-main commits

1. `e2389381254560e017b82b5a89eca54329ba182e` — `feat(audit): detect unreproducible MV0 gain provenance`
2. `2cb38204db5b20012cee884d06de786a07b2e9e6` — `test(audit): cover MV0 gain provenance contract`
3. `4fe2a778588b9b081fc2acd90ad79b133ded00f4` — `docs(validation): record MV0 gain provenance conflict`
4. `76f2ae68f81968faac787c25661ab441ccf11de8` — `docs(validation): add MV0 gain provenance record`
5. `0c27a7d24f225a38ed6471a7fc9c0ea701436dd5` — `docs(validation): visualize MV0 gain provenance break`
6. `6f6160c2dd4829f6ce3cfe071379a7b623668018` — `docs(audit): track MV0 gain provenance conflict`
7. `16e92e0113831045b7ecdeb96b44d1a7c75afe8b` — `docs(audit): archive MV0 gain provenance audit`

Every connector write returned a successful direct-main commit. The user-facing completion records the final handoff commit after a fresh recent-main confirmation.

## Files changed

- `tools/audit/audit_mv0_gain_provenance.py`
- `tests/test_audit_mv0_gain_provenance.py`
- `docs/validation/mv0_gain_provenance_audit.md`
- `docs/validation/mv0_gain_provenance_validation.json`
- `docs/validation/mv0_gain_provenance.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/HANDOFF.md`
- `chatgpt_todo/archive/2026-07-24T072257Z_AUD-LEDGER-001_MV0_GAIN_PROVENANCE.md`

## Scientific boundary and next task

No raw pulse table, ROOT file, NPZ truth file, calibration rerun, accepted KS comparison, bootstrap, simulation, detector calibration, or detector-performance result was produced. The visual evidence is a provenance-chain schematic, explicitly not detector data.

Before restoring `CL-013` or `CL-014` as canonical validated claims:

1. recover or repair producer code that implements the documented net-amplitude observable;
2. align the reproduce command and JSON schema with that producer;
3. rerun on immutable pulse/ROOT/NPZ inputs and retain exact input/output hashes, software environment, command, code SHA, selections, event/pulse counts, and fit diagnostics;
4. preregister and calculate statistical/systematic uncertainty and interval construction with coverage checks;
5. reconstruct both ledger rows to exactly 43 fields and repair `FIG-EN-001` provenance;
6. rerun ledger, claim, WIKI, link, table, and figure validation before promotion.

`SESSION_LOG.md` was not replaced because the connector provides whole-file replacement rather than a byte-safe append, and the long append-only file was not available as one independently verified complete byte snapshot. Replacing partial reconstructed bytes would risk destroying prior provenance. The complete session is preserved in the immutable archive and this handoff rather than fabricating a log append.
