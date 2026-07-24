# Latest Scientific Review Handoff

## Session identity

- UTC stamp: `2026-07-24T081929Z`
- Task: `AUD-LEDGER-001`
- Added focused task record: `AUD-P04P-001`
- Unit: P04p B2 duplicate-readout winner robustness and exact-width reconstruction of `CL-015`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `251353ffb0e200bd3c495b92c854f60593f44279`
- Validated delivery head before this handoff update: `93a6dd4f54ab6eac8624403ff65d99c52a7c8c42`
- Destination: direct sequential commits to `main`; no task branch, pull request, force-push, or history rewrite
- Acceptance: audit tooling/evidence `VALIDATED`; source-like P04p result state `FLAWED`; `CL-015` and the production-winner claim remain `GATED`; `AUD-LEDGER-001` and `AUD-P04P-001` remain `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected repository permissions/default branch, recent `main`, open/closed PR state, PR #868, commit status, mandatory `chatgpt_todo/` records, the canonical claim ledger, and the complete P04p report/result/manifest/script/config chain. PR #868 is closed, unmerged, and non-mergeable and was not modified.

A direct clone was attempted but the runtime could not resolve `github.com`. Repository facts were therefore established through authenticated GitHub blob reads. Executable validation used exact locally constructed files and a source-faithful reduced P04p fixture; no fixture result is represented as detector data.

No status checks were attached to the initial reviewed head. No GitHub Actions success is inferred for this unit.

## Exact repository evidence

- pre-change claim-ledger blob: `009f48e218b2439f80b2cebf8ebb06a845488089`
- P04p report blob: `b9029f1c7f8d8d87499b8a7a88d807692b56ae71`
- P04p result blob: `e2c75352b5c66f70923ef525d8251be3af9cfdc8`
- P04p manifest blob: `00b244470bb9dbd4060769e69e720b79c07f756d`
- P04p producer blob: `6f3bbf1638b8729e425088e6b1f8a0663b3a5615`
- P04p config blob: `d11592ba547a7028527dea3ac5fc3329362cb9a4`
- producer/result source commit: `c31b40fdadff23272b13e3824e769f518c53b38e`

## Confirmed model-selection flaw

The committed rule selects methods whose accepted-coverage point estimate is at least `0.50`, then minimizes accepted charge res68, timing abs68, and calibration ECE. The reported GBT has:

- accepted coverage `0.5016432417313474`;
- run-block-bootstrap 95% coverage interval `[0.4781032287979763,0.5382552094265317]`;
- accepted charge res68 `0.03902452880489024`.

The point estimate is only `0.001643` above the gate, while the interval crosses below it. The result does not declare whether eligibility is controlled by point coverage, a confidence bound, or another uncertainty criterion.

A conservative sensitivity calculation that requires the lower 95% coverage bound to satisfy the same gate excludes GBT. MLP is then first eligible:

- accepted coverage `0.5470846194571808`;
- lower 95% bound `0.5225633159229767`;
- accepted charge res68 `0.04055070702536622`.

This sensitivity result does **not** designate MLP as canonical because the lower-bound rule was not preregistered. Registered policy:

```text
COVERAGE_GATE_MUST_USE_PREDECLARED_UNCERTAINTY_RULE
```

## Ledger reconstruction

`CL-015` previously had 36 fields under the 43-column header. It now has exactly 43 fields with:

- claim: B2 duplicate-readout harm-veto accepted charge res68;
- value `0.03902452880489024`;
- 95% run-block-bootstrap interval `[0.03566372530746706,0.042719761350795714]`;
- `100107` events and `8` evaluation runs;
- traditional-rule baseline `0.07854122474166687`;
- delta `-0.03951669593677663`;
- truth type `data_external_duplicate_readout`;
- status `GATED`;
- exact current report/script/result/config/manifest paths and source commit;
- blocker `BLK-P04P-001`.

Ledger schema progress is now 6/26 exact-width rows. Twenty rows remain withheld under `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

## Validation delivered

Added:

- `tools/audit/audit_p04p_winner_robustness.py` v1.0.0;
- `tests/test_audit_p04p_winner_robustness.py`;
- `tests/test_claim_ledger_p04p_row.py`;
- `docs/validation/p04p_winner_robustness_audit.md`;
- `docs/validation/p04p_winner_robustness_fixture.json`;
- `docs/validation/p04p_winner_robustness_validation.json`;
- `docs/validation/p04p_winner_robustness.svg`.

Commands:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/audit_p04p_winner_robustness.py \
  tests/test_audit_p04p_winner_robustness.py \
  tests/test_claim_ledger_p04p_row.py

PYTHONPATH=. python -m pytest \
  tests/test_audit_p04p_winner_robustness.py \
  tests/test_claim_ledger_p04p_row.py -q

6 passed in 1.14s
```

Additional checks:

- source-faithful current-like fixture: status `FLAWED` with `COVERAGE_GATE_UNCERTAINTY_POLICY_MISSING` and `WINNER_CHANGES_UNDER_CI_LOWER_BOUND_GATE`;
- corrected preregistered synthetic contract: `VALIDATED`;
- JSON parsing passed;
- SVG XML parsing passed;
- maximum changed Python line length: 100;
- committed auditor blob `faea3340ef55b9e1fd5f84c1813d65e88d4cce2a` matches locally validated bytes;
- locally validated audit-test blob `c913edafb1f65ca8c8fb58f5e61fedfe6a2565a0`;
- locally validated ledger-test blob `0a762b80f477f897cd6dbdba9fea22d38cf0318b`;
- corrected ledger blob `4dc46181f48211e017ba0d2ff29bdac2c6f21897`.

Full repository pytest, ruff, raw ROOT processing, classifier training, bootstrap regeneration, cross-stave validation, broken-link checking, and GitHub Actions were not run.

## Direct-main commit sequence

1. `faeea505fd618d151c1880cc65906eaee52eb40a` — `feat(audit): assess P04p winner robustness`
2. `20da314c59e7221374fd5a2d4314a92c99e789a1` — `test(audit): cover P04p coverage-gate robustness`
3. `f88ffebd923b713e1cc7a520b9e66510ed9b159d` — `test(ledger): cover source-backed P04p claim row`
4. `c17f6ef3e53ca150fce1afe27cc44718a3c93530` — validation audit
5. `756004131737b13b567af94048fbb890c87787ca` — validation JSON
6. `ba1ebc36073452f87284f6ce21b1a3d369d43f75` — source-faithful fixture
7. `8a0934a91ec69a12ce29430f2521997177938e9c` — visual evidence
8. `70172e12c7eec0a8a9200b45bd1aa8b53415541c` — exact-width `CL-015`
9. `3c6a6347858b212f26b4eefd20c91724a04283a9` — ledger schema JSON
10. `3767e2c55fdaba7a279ecd917481bb7b5b03e8e4` — ledger schema SVG
11. `99e546a58f42167e255fa5f501b3eb3bc913671a` — active-task state
12. `e024b56cb4210e805b870a83741d10db706f5c03` — blocker registration
13. `38d80b9d9b7cb164744101125cb4d5665afe7e38` — immutable archive
14. `c7e07c677bbfa7792113f0916eb2bbd17b45beea` — backlog update
15. `489da1d60f90b12d0abbaa0aa06c89ecbc3d2583` — master index
16. `67e87f17782b43dd54cee0e51586cec79a63c064` — study ledger
17. `83f12563ff09aad7aef2d93e28a0a49d1d808437` — claim-evidence matrix
18. `71907c86124f2ac0e5c4ee9fd4acc05967a02268` — visualization matrix
19. `93a6dd4f54ab6eac8624403ff65d99c52a7c8c42` — code-result map

Every write returned a successful direct-main commit. The immutable full record is:

`chatgpt_todo/archive/2026-07-24T081929Z_AUD-LEDGER-001_P04P_WINNER_ROBUSTNESS.md`

## Session-log limitation

`SESSION_LOG.md` was not replaced. The connector exposes complete-file replacement rather than a byte-safe append, while the long append-only blob could not be retrieved as one independently verified complete text snapshot. Reconstructing it from truncated responses would risk deleting prior provenance. The complete session is preserved in the immutable archive and this handoff; no append is fabricated.

## Scientific boundary and next action

No raw ROOT file, waveform, retrained model, regenerated bootstrap ensemble, independent holdout, new-run sample, cross-stave transfer sample, truth-energy target, calibration, or detector-performance result was produced. Do not claim GBT as a robust production winner or promote MLP from the sensitivity calculation.

Resolution requires:

1. preregister the uncertainty-aware coverage eligibility rule and model-family multiplicity treatment;
2. freeze independent model-selection and validation runs;
3. validate transfer to B4/B6/B8 and new runs;
4. retain exact data/code/config/output hashes and environment provenance;
5. rerun ledger, claim, figure, link, and WIKI gates before changing `CL-015` from `GATED`.
