# Latest Scientific Review Handoff

## Session

- **UTC:** `2026-07-23T22:07:59Z`
- **Task:** `AUD-G4-018`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `c0a5d46d8a14bb933aa401514ee2f7408276ae0b`
- **Validated implementation/evidence head:** `768e13daa5056dd06f9b962e66b004fa5d9c4d97`
- **Remote main immediately before this handoff:** `1f8b15a7aff0c925960754f005b69c9b8986cad0`
- **Destination:** direct to `main`
- **Acceptance:** COMPLETE for stopping-power aggregation row-order invariance; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

## Start-of-run and concurrent-work review

- Inspected current remote-main history, repository permissions, the previous stopping-power handoff, canonical comparison code, focused tests, mandatory `chatgpt_todo/` files, and concurrent SiPM commits.
- `AUD-REPO-001` remained owned by a concurrent session and was not duplicated.
- Direct checkout remained unavailable because the runtime could not resolve `github.com`; exact source and test bytes were reconstructed through authenticated GitHub reads and checked with Git blob hashes.
- Current-main work began from the latest non-overlapping SiPM commit `c0a5d46d8a14bb933aa401514ee2f7408276ae0b`. Every write used current file SHAs; no force push, history rewrite, task branch, or unrelated rollback was used.
- PR #868 was rechecked: it is closed, unmerged, and non-mergeable. It was not reopened, modified, or merged.

## Confirmed numerical-method defect

The former `aggregate()` implementation repeatedly applied binary64 `+=` to deposited-energy and track-length values. Floating-point addition is not associative, so identical validated event multisets could yield different sufficient statistics solely from CSV row order.

Exact pre-change provenance:

- **Git blob:** `79ea276741807d896cc6d2a99e8071605cc238f0`
- **Synthetic group:** proton at `1.0 MeV`; one `1.0 MeV` deposit; ten `1e-16 MeV` deposits; eleven `1.0 mm` track lengths; density `1.0 g/cm3`.
- **Large-first sequential deposit sum:** `1.0 MeV`
- **Small-first sequential deposit sum:** `1.000000000000001 MeV`
- **Large-first proxy:** `0.9090909090909092 MeV cm2/g`
- **Small-first proxy:** `0.9090909090909101 MeV cm2/g`
- **Exact-old-source negative control:** `2 failed, 1 passed`

This could perturb the reported proxy, ratio, delta, or a numerical threshold classification without a physical change in the event set.

## Validated correction

`scripts/single_stave/compare_stopping_power.py` now:

1. groups validated rows by canonical particle and exact configured numeric energy;
2. stores deposited-energy and track-length values per group;
3. evaluates both grouped totals with `math.fsum`;
4. records `summation_method=MATH_FSUM_PER_GROUP` in every result and CSV row;
5. prints the summation method in terminal output.

The validated parser already materializes the complete canonical event table, so this does not alter the dominant input-memory model.

Exact post-change provenance:

- **Git blob:** `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc`
- **Script SHA-256:** `ee61e0f2a76fa2e94513d176ce7b34698acaada02d84defe480df38a2f32dd72`
- **Focused test SHA-256:** `5607b1d0da7fec7f083462ac54b45967a4c4c9bb2d95016a4e040df3edf4ba27`

## Regression and validation

Added:

- `tests/test_compare_stopping_power_order_invariance.py`

Executed on exact local reconstructions:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_order_invariance.py \
  tests/test_compare_stopping_power_report_precision.py \
  tests/test_compare_stopping_power_report_reproducibility.py

python -m pytest \
  tests/test_compare_stopping_power_order_invariance.py \
  tests/test_compare_stopping_power_report_precision.py \
  tests/test_compare_stopping_power_report_reproducibility.py -q

8 passed in 0.06s
```

Coverage verifies:

- the old sequential algorithm changes under row reversal;
- the corrected forward and reversed event multisets produce identical complete result dictionaries;
- the corrected deposit sum is `1.000000000000001 MeV` in both orders;
- the corrected track sum is `11.0 mm` in both orders;
- the corrected proxy is `0.9090909090909101 MeV cm2/g` in both orders;
- `MATH_FSUM_PER_GROUP` is retained in memory, CSV, and terminal output;
- existing exact float serialization and self-contained report behavior remain valid.

Additional passed checks:

- exact old Git-blob reconstruction;
- old-source negative control: `2 failed, 1 passed`;
- exact current Git-blob verification;
- validation JSON parse;
- SVG XML parse;
- changed Python lines no longer than 100 characters.

Not run:

- full repository pytest;
- ruff;
- Geant4 build or CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

No broader CI, simulation, or physics-closure success is claimed.

## Reproducible evidence

Added:

- `docs/validation/stopping_power_order_invariance_audit.md`
- `docs/validation/stopping_power_order_invariance_validation.json`
- `docs/validation/stopping_power_order_invariance.svg`

The SVG is explicitly labelled synthetic floating-point regression evidence, not detector data. It contrasts the former order-dependent path with the corrected compensated sums using exact values, text, position, and cross-out rather than color alone.

## Direct-to-main commit sequence

Implementation, test, and evidence:

- `d9aa75dc686fd5e18b0d8f2f4256ea57397bd288` — `fix(single-stave): make stopping-power aggregation order-stable`
- `3ac6f171ff7265b9959320a43ccfb8f3f5c84792` — `test(single-stave): cover stopping-power row-order invariance`
- `3f1572f237fa1920909fed643d40d43d209b93e3` — validation audit Markdown
- `d7c8525e66258f590ca138000d223112e738d3ab` — validation JSON
- `768e13daa5056dd06f9b962e66b004fa5d9c4d97` — validation SVG

Coordination and immutable provenance:

- `78cae0518e2b45cfad22c05680e12bf27adcd5af` — active task
- `43c54a567be31c251b0aaa84369589e873883ec2` — backlog
- `7acbf963841912190361dd46421af83f13939ee2` — master index
- `71b634b1713d57cb7fd9f7c9ad1aacb9d6185114` — code-result map
- `e178644f0957087e74d81d8e8df59b50836f032b` — study ledger
- `4ce36c238361a10088176bbd7412e667b18e76fb` — claim matrix
- `c3167359138cb7fa6a5ed50e29b81bd0a8d56c43` — visualization matrix
- `484b9143c51f20f236685839c50b4d4126d54c39` — blocker register
- `1f8b15a7aff0c925960754f005b69c9b8986cad0` — immutable archive

Every session-owned GitHub contents write returned a successful direct-main commit. The final handoff commit is confirmed separately by remote-main history after this write.

## `chatgpt_todo/` updates

Updated:

- `ACTIVE_TASK.md`
- `BACKLOG.md`
- `MASTER_INDEX.md`
- `CODE_RESULT_MAP.md`
- `STUDY_REVIEW_LEDGER.md`
- `CLAIM_EVIDENCE_MATRIX.md`
- `VISUALIZATION_MATRIX.md`
- `BLOCKERS.md`
- `HANDOFF.md`

Added immutable session record:

- `chatgpt_todo/archive/2026-07-23T220759Z_AUD-G4-018_ORDER_INVARIANCE.md`

`SESSION_LOG.md` was not replaced because the connector returned only a partial read of the long append-only file and exposes complete-file replacement rather than a safe append primitive. Replacing it from incomplete bytes could destroy earlier provenance. The immutable archive contains the complete session entry. This is a coordination limitation, not a scientific acceptance claim.

## Scientific boundary and next task

No exact real Geant4 event table, ROOT output, accepted projectile total-energy-loss observable, quantitative uncertainty budget, stopping-power closure, calibration, or detector-performance result was generated.

`AUD-G4-018` is COMPLETE. The next accepted stopping-power work remains `AUD-G4-011` and `AUD-G4-005`: validate immutable real exports and an accepted projectile-loss observable, quantify secondary escape and energy evolution, then preregister and propagate statistical/systematic uncertainty before evaluating any closure interval.
