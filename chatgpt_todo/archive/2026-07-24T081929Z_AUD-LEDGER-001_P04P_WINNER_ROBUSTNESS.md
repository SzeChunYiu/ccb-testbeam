# Immutable session archive — AUD-LEDGER-001 P04p winner robustness

## Identity

- UTC stamp: `2026-07-24T081929Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `251353ffb0e200bd3c495b92c854f60593f44279`
- Owner: scheduled scientific-review session
- Unit: source-backed `CL-015` reconstruction and P04p duplicate-readout model-selection robustness
- Destination: direct sequential commits to `main`; no force-push, branch rewrite, or stale PR merge

## Start-of-run review

Authenticated GitHub reads checked recent `main`, repository permissions/default branch, PR #868, commit status, the mandatory `chatgpt_todo/` records, the canonical 43-column claim ledger, the P04p report/result/manifest/script/config, source history, and relevant validation tooling. PR #868 was closed, unmerged, and non-mergeable and was not modified. The initial reviewed head had no attached status checks.

A local clone was attempted and failed because the runtime could not resolve `github.com`. Repository facts were therefore established through authenticated exact GitHub blob reads. Executable tests used exact locally constructed source files and a source-faithful reduced P04p fixture; the fixture is explicitly not detector data.

## Exact source evidence

- pre-change claim ledger blob: `009f48e218b2439f80b2cebf8ebb06a845488089`
- P04p report blob: `b9029f1c7f8d8d87499b8a7a88d807692b56ae71`
- P04p result blob: `e2c75352b5c66f70923ef525d8251be3af9cfdc8`
- P04p manifest blob: `00b244470bb9dbd4060769e69e720b79c07f756d`
- P04p producer blob: `6f3bbf1638b8729e425088e6b1f8a0663b3a5615`
- P04p config blob: `d11592ba547a7028527dea3ac5fc3329362cb9a4`
- manifest/source commit: `c31b40fdadff23272b13e3824e769f518c53b38e`

## Confirmed model-selection flaw

The committed selection rule requires accepted coverage at least 0.50 and then minimizes accepted charge res68, timing abs68, and calibration ECE. The producer applies the coverage gate to the point estimate only.

The reported GBT winner has:

- accepted coverage `0.5016432417313474`;
- run-block-bootstrap 95% interval `[0.4781032287979763,0.5382552094265317]`;
- accepted charge res68 `0.03902452880489024`.

The point estimate is only `0.001643` above the gate, and the committed result does not declare how interval uncertainty controls eligibility. Under a documented sensitivity check requiring the lower 95% coverage bound to meet 0.50, GBT is ineligible and MLP is first eligible (`coverage=0.5470846194571808`, lower bound `0.5225633159229767`, charge res68 `0.04055070702536622`). This does not make MLP the canonical winner because that rule was not preregistered.

Registered policy:

```text
COVERAGE_GATE_MUST_USE_PREDECLARED_UNCERTAINTY_RULE
```

## Claim-ledger correction

`CL-015` previously had 36 fields. It is reconstructed to exactly 43 fields with source-backed metric, central value, interval, interval method/unit, event/run counts, traditional-rule baseline, delta, truth type, status, exact current paths, source commit, and blocker. It remains `GATED` and explicitly states that B2 external duplicate-readout closure is not truth-energy validation.

Ledger schema progress is now 6/26 exact-width rows; 20 rows remain withheld under `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

## Validation

Commands:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_p04p_winner_robustness.py \
  tests/test_audit_p04p_winner_robustness.py \
  tests/test_claim_ledger_p04p_row.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_p04p_winner_robustness.py \
  tests/test_claim_ledger_p04p_row.py -q
```

Result: `6 passed in 1.14s`.

Additional checks:

- current-like fixture: status `FLAWED`, two expected findings;
- corrected preregistered synthetic contract: `VALIDATED`;
- JSON parsing: passed;
- SVG XML parsing: passed;
- maximum changed Python line length: 100;
- locally validated Git blobs:
  - auditor `faea3340ef55b9e1fd5f84c1813d65e88d4cce2a`;
  - audit tests `c913edafb1f65ca8c8fb58f5e61fedfe6a2565a0`;
  - ledger test `0a762b80f477f897cd6dbdba9fea22d38cf0318b`;
  - corrected ledger `4dc46181f48211e017ba0d2ff29bdac2c6f21897`.

Full repository pytest, ruff, ROOT processing, model training, bootstrap regeneration, cross-stave validation, and GitHub Actions were not run.

## Direct-main commits before archive

1. `faeea505fd618d151c1880cc65906eaee52eb40a` — `feat(audit): assess P04p winner robustness`
2. `20da314c59e7221374fd5a2d4314a92c99e789a1` — `test(audit): cover P04p coverage-gate robustness`
3. `f88ffebd923b713e1cc7a520b9e66510ed9b159d` — `test(ledger): cover source-backed P04p claim row`
4. `c17f6ef3e53ca150fce1afe27cc44718a3c93530` — `docs(validation): record P04p winner instability`
5. `756004131737b13b567af94048fbb890c87787ca` — `docs(validation): add P04p robustness record`
6. `ba1ebc36073452f87284f6ce21b1a3d369d43f75` — `test(data): add P04p robustness fixture`
7. `8a0934a91ec69a12ce29430f2521997177938e9c` — `docs(validation): visualize P04p selection instability`
8. `70172e12c7eec0a8a9200b45bd1aa8b53415541c` — `fix(ledger): reconstruct P04p duplicate-readout claim`
9. `3c6a6347858b212f26b4eefd20c91724a04283a9` — `docs(validation): advance ledger width audit to six rows`
10. `3767e2c55fdaba7a279ecd917481bb7b5b03e8e4` — `docs(validation): refresh ledger width visualization`
11. `99e546a58f42167e255fa5f501b3eb3bc913671a` — `docs(audit): advance ledger audit through P04p`
12. `e024b56cb4210e805b870a83741d10db706f5c03` — `docs(audit): register P04p winner-selection blocker`

Every write returned a successful direct-main commit. The latest handoff records the archive and final remote head.

## Scientific boundary and next action

No raw ROOT table, waveform, retrained classifier, regenerated bootstrap ensemble, new-run holdout, cross-stave transfer sample, truth-energy target, calibration, or detector-performance result was produced. Do not claim GBT as a robust production winner or promote MLP from the sensitivity analysis.

Resolution requires a preregistered uncertainty-aware coverage contract and model-family multiplicity policy, independent selection/validation runs, cross-stave transfer to B4/B6/B8, and immutable rerun provenance before changing `CL-015` from `GATED`.
