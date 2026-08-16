# Immutable session archive — AUD-LEDGER-001 Rmax quarantine

## Session

- UTC stamp: `2026-07-24T061758Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `72fccaa8f4d6c00665c60fd0a94884c87cdd544b`
- Task: `AUD-LEDGER-001`
- Owner: scheduled scientific-review session
- Destination: direct sequential commits to `main`; no branch, PR, force-push, or history rewrite

## Start-of-run review

Fetched current `main`, permissions/default branch, recent commits, open PRs, PR #868, commit status/workflow state, mandatory `chatgpt_todo/` records, claim ledger, figure/table registries, WIKI, MV5 report/summary/script, academic pile-up chapter, source commit, and tracked MV5 figure. A local clone failed because DNS could not resolve `github.com`; authenticated GitHub reads/writes were used. PR #868 remained closed, unmerged, and non-mergeable and was not modified.

## Confirmed scientific/provenance defects

1. `CL-010` had 37 fields and `CL-012` had 36 fields under the 43-column schema, withholding their late-field interpretation.
2. The reported `3.0448717948717947 MHz` equals `(1 / 124.8 ns) × 0.38`; `0.38` is recorded as the beam duty factor, not a validated occupancy-quality threshold.
3. The academic chapter starts from `mu_max=0.1`, obtains `0.801 MHz` per stave and `3.20 MHz` for four staves, then labels `3.05 MHz` as a rounding. This is not a valid rounding step.
4. The MV5 summary records `rmax_from_failure_ceiling_mhz=null`; the maximum recovery failure fraction is `0.03475`, below the recorded ceiling `0.17`. The recovery curve therefore does not establish a `3.044 MHz` crossing or lower bound.
5. `FIG-PU-003` pointed to nonexistent `reports/.../results.json` and `docs/figures/rmax_comparison.png` paths while the tracked source JSON and six-panel PNG are `mv5_pileup_summary.json` and `mv5_pileup.png`.
6. The WIKI and academic chapter still publicly present conflicting `3.044–3.05 MHz` language; this unit did not rewrite those complete files.

## Correction

- Reconstructed `CL-010` to exactly 43 fields, status `BLOCKED`, truth type `derived_model_conflicted`, no accepted current value or uncertainty, blocked by `S-STAT-003`.
- Reconstructed `CL-012` to exactly 43 fields, status `SUPERSEDED`, no accepted current value, retained only as correction history.
- Both rows now cite the tracked MV5 report, script, summary JSON, source commit `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`, and `FIG-PU-003`.
- Repaired `FIG-PU-003` to the tracked summary JSON and six-panel PNG and explicitly labelled it non-accepting pending definition resolution.
- Added `validate_claim_ledger_cl010.py` v1.0.0, focused tests, Markdown/JSON/SVG evidence, and refreshed cumulative schema evidence.

## Validation

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_cl010.py \
  tests/test_validate_claim_ledger_cl010.py

PYTHONPATH=. python -m pytest tests/test_validate_claim_ledger_cl010.py -q

6 passed in 0.04s
```

Additional results:

- source-faithful fixture validator: `VALIDATED`, zero issues;
- validation JSON parsed;
- both SVGs parsed as XML;
- maximum changed Python line length: 92;
- updated ledger: 10097 bytes, SHA-256 `809e03162f04f94235fe36612c0ec8a3ccf4ae054a5d87341bdd5e26ad3c57d6`;
- exact rows: 5/26 (`CL-001`, `CL-007`, `CL-010`, `CL-011`, `CL-012`);
- width-mismatched rows: 21;
- cumulative schema status: `FLAWED` by fail-closed policy.

The full repository suite, ruff, ROOT processing, simulation execution, WIKI validator, broken-link checker, and GitHub Actions were not run. Repository source facts were verified through authenticated blob reads; no real data or simulation output was regenerated.

## Direct-main commits before this archive

1. `d9aeff21544f84fc01485510d5ac2476c251966a` — `fix(ledger): quarantine conflicted Rmax claims`
2. `6b45cfd2b6fcf8ac4c60bd401549bab7d1ea6008` — `fix(ledger): repair Rmax figure provenance`
3. `44e4d7fcf9cb65c2e20e142c4b2eaad3a2bcc84f` — `feat(audit): validate conflicted Rmax claim quarantine`
4. `be637cbca0a3d879eab12b7f7c808bf2aeac6e45` — `test(audit): cover conflicted Rmax ledger gate`
5. `21c4fdd483d8484453c7b72c159f7166d81e2c2c` — `docs(validation): record Rmax claim quarantine`
6. `97168267bd7f4319f1912dd5d882b819230407d1` — `docs(validation): add Rmax quarantine record`
7. `509df1f3d02356e755d4d7c8fc7e6a1a98498891` — `docs(validation): visualize Rmax claim conflict`
8. `6e965555933720717e8ee1223fd21260a2809989` — `docs(validation): advance ledger width audit to five rows`
9. `0bc21206270cd25d7947ffbd41b9636f0ba02904` — `docs(validation): refresh five-row ledger schema record`
10. `f9ce6c9eb3a02e90e1f1826b7ffe9304a93303cb` — `docs(validation): refresh ledger width visualization`
11. `292f5ad6e55438e155dec756b9bf257a723a3524` — `docs(audit): advance ledger reconstruction through Rmax claims`

## Acceptance and next action

`AUD-LEDGER-001` remains `PARTIAL`. No Rmax is scientifically accepted. Resolve `S-STAT-003` by defining the measurand, per-stave/total-rate normalization, occupancy criterion, duty-factor use, uncertainty, falsifiers, and independent validation before restoring a rate. Then synchronize WIKI/chapter text and continue source-backed reconstruction of the remaining 21 malformed ledger rows.

`SESSION_LOG.md` was not replaced because the connector offers whole-file replacement rather than byte-safe append and only paged/truncated reads were available. Replacing reconstructed partial bytes could destroy prior append-only provenance; this archive and `HANDOFF.md` preserve the complete run instead.
