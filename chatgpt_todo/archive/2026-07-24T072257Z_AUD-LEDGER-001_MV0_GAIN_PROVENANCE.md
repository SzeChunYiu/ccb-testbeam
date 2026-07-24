# Immutable Scientific-Review Session Record

## Session identity

- UTC stamp: `2026-07-24T072257Z`
- Task: `AUD-LEDGER-001`
- Unit: MV0 gain provenance and uncertainty chain (`CL-013`, `CL-014`, `FIG-EN-001`)
- Owner: scheduled scientific-review session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `712adba593c9b84e4617c1fe8013873cd0c5f753`
- Destination: direct sequential commits to `main`; no task branch, pull request, force-push, or history rewrite
- Acceptance: audit implementation/evidence validated; gain claim remains withheld and `AUD-LEDGER-001` remains `PARTIAL`

## Start-of-run review

Authenticated GitHub reads confirmed the repository, `main` as the default branch, push/admin permission, recent history, open pull requests, mandatory `chatgpt_todo/` records, the canonical claim ledger, MV0 report and calibration artifact, tracked producer script at the cited source commit, and the figure registry. PR #868 remains closed, unmerged, and non-mergeable and was not modified. The initial reviewed main head had no attached status checks, so no CI success is inferred.

A direct clone was attempted but failed because the runtime could not resolve `github.com`. Repository evidence was therefore inspected through authenticated exact GitHub blob reads. Executable checks used source-faithful reduced fixtures; the machine-readable record distinguishes fixture execution from repository blob inspection.

## Repository evidence

- `docs/claim_ledger.csv` blob: `009f48e218b2439f80b2cebf8ebb06a845488089`
- `reports/mv0_calibration_1782677847/REPORT.md` blob: `bc607eb0ae2639c06ab840ff234160958ada60a5`
- `reports/mv0_calibration_1782677847/calibration.json` blob: `74e490753d3e821b0a1353490764a5ede0e9bf75`
- `scripts/mv0_calibrate_from_data.py` blob: `fd911daf3f0fd80df20f4112f4f0f40bf3383afd`
- producer source commit: `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`
- `docs/figure_registry.csv` blob: `1a7b6cbdc18bcc742f0578647a5c785aea78582a`

## Confirmed defects

1. `CL-013` has 38 fields and `CL-014` has 37 fields under the canonical 43-column header. Their late fields remain uninterpretable under the fail-closed schema policy.
2. The report and committed calibration artifact define the v2 data observable as `abs(amplitude_adc - baseline_adc)`, but the tracked producer assigns raw `amplitude_adc` directly to the global and per-stave fit arrays.
3. The report's reproduce command uses `--data`, whereas the script requires `--data-csv`, and it omits required `--truth-npz`.
4. The producer's emitted JSON schema lacks `gain_method`, `gain_systematic_unc_pct`, and `ks_at_median_gain`, although those fields appear in the committed artifact.
5. `CL-013`, `CL-014`, and `FIG-EN-001` cite stale or nonexistent `scripts/mv0_calibration.py` and `reports/mv0_calibration_1782677847/results.json`; the tracked paths are `scripts/mv0_calibrate_from_data.py` and `calibration.json`.
6. The calibration artifact supports the 92 ADC/MeV central value and a stated 30% systematic, but does not provide a statistical uncertainty, formal confidence interval, confidence level, or interval method. Ledger values `stat_unc=14`, `total_unc=31.3`, and interval `[60,124]` are not supported by this artifact.

## Independent calculation

Using the numbers stated in the committed artifact:

```text
1781 ADC / (26.44 MeV * 0.733) = 91.89639906462777 ADC/MeV
```

This reproduces the rounded central value only. It does not establish the missing statistical uncertainty, confidence interval, shape-model adequacy, detector calibration validity, or downstream performance.

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

Commands and measured results:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_mv0_gain_provenance.py \
  tests/test_audit_mv0_gain_provenance.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_mv0_gain_provenance.py -q

4 passed in 0.64s
```

The current-like fixture returned status 1 with ten findings. A corrected chain fixture returned `VALIDATED`. The JSON parsed, the SVG parsed as XML, and changed Python lines were at most 100 characters.

## Direct-main commits recorded before the final handoff

1. `e2389381254560e017b82b5a89eca54329ba182e` — `feat(audit): detect unreproducible MV0 gain provenance`
2. `2cb38204db5b20012cee884d06de786a07b2e9e6` — `test(audit): cover MV0 gain provenance contract`
3. `4fe2a778588b9b081fc2acd90ad79b133ded00f4` — `docs(validation): record MV0 gain provenance conflict`
4. `76f2ae68f81968faac787c25661ab441ccf11de8` — `docs(validation): add MV0 gain provenance record`
5. `0c27a7d24f225a38ed6471a7fc9c0ea701436dd5` — `docs(validation): visualize MV0 gain provenance break`
6. `6f6160c2dd4829f6ce3cfe071379a7b623668018` — `docs(audit): track MV0 gain provenance conflict`

Every connector write above returned a successful direct-main commit. Final remote-main confirmation and the final handoff SHA are recorded in `chatgpt_todo/HANDOFF.md` after publication.

## Acceptance and next action

The audit gate is validated; the gain result is not accepted as a canonical reproduced calibration. Before restoring `CL-013` or `CL-014` as validated claims:

1. recover or repair producer code that implements the documented net-amplitude observable;
2. align the reproduce command and output schema with that producer;
3. rerun on immutable pulse/ROOT/NPZ inputs and retain input/output hashes, environment, exact command, and code SHA;
4. quantify statistical and systematic uncertainty with a declared interval construction and coverage checks;
5. reconstruct both ledger rows to exactly 43 fields from the regenerated evidence;
6. repair `FIG-EN-001` paths and regenerate its uncertainty/per-stave diagnostics;
7. rerun ledger, claim, WIKI, link, figure, and table validators.

No raw data, ROOT output, NPZ truth file, calibration rerun, KS recomputation, bootstrap, simulation, detector-performance result, or accepted uncertainty was produced.

`SESSION_LOG.md` was not replaced because the connector exposes whole-file replacement rather than a byte-safe append and the long append-only file was not available as one independently verified complete byte snapshot. Replacing it would risk provenance loss. This immutable record and the latest handoff preserve the complete session without fabricating an append.
