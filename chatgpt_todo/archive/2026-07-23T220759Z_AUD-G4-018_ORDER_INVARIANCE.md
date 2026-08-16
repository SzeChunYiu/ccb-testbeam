# Immutable Session Record — AUD-G4-018

## Session identity

- **UTC stamp:** `2026-07-23T220759Z`
- **Owner:** scheduled ChatGPT audit session
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Destination:** direct to `main`
- **Initial remote main SHA:** `c0a5d46d8a14bb933aa401514ee2f7408276ae0b`
- **Primary area:** `scripts/single_stave/compare_stopping_power.py`
- **Task state:** COMPLETE for numerical row-order invariance; stopping-power physics closure remains PARTIAL/BLOCKED.

## Start-of-run review

Reviewed current remote-main history, repository permissions, the previous `AUD-G4-017` handoff, mandatory `chatgpt_todo/` ledgers, the canonical stopping-power comparison, focused report tests, and concurrent SiPM commits. `AUD-REPO-001` remained owned by another active session and was not duplicated. PR #868 was not modified or merged.

A direct checkout was unavailable because the runtime could not resolve `github.com`. Exact source/test bytes were reconstructed from authenticated GitHub contents and verified with Git blob hashes before local validation.

## Confirmed numerical defect

The former grouped aggregation used repeated binary64 `+=` operations for deposited energy and track length. Floating-point addition is not associative; therefore the same validated event multiset could produce different sufficient statistics when CSV rows were reordered.

Exact pre-change source provenance:

- **Git blob:** `79ea276741807d896cc6d2a99e8071605cc238f0`
- **Synthetic group:** proton at 1 MeV, one `1.0 MeV` deposit, ten `1e-16 MeV` deposits, eleven `1 mm` track lengths, density `1 g/cm3`.
- **Large-first sequential deposit sum:** `1.0 MeV`
- **Small-first sequential deposit sum:** `1.000000000000001 MeV`
- **Large-first proxy:** `0.9090909090909092 MeV cm2/g`
- **Small-first proxy:** `0.9090909090909101 MeV cm2/g`
- **Exact-old-source negative control:** `2 failed, 1 passed`

The defect could perturb ratios or threshold classifications for numerically sensitive groups without any physical change in the event set.

## Validated correction

The canonical comparison now:

1. groups validated rows by canonical particle and exact configured numeric energy;
2. retains deposit and track values per group;
3. calculates both totals with `math.fsum`;
4. records `summation_method=MATH_FSUM_PER_GROUP` in every result and CSV row;
5. prints the summation method in terminal output.

This does not increase the dominant memory class because the validated parser already materializes all canonical event rows in memory.

Exact post-change source provenance:

- **Git blob:** `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc`
- **SHA-256:** `ee61e0f2a76fa2e94513d176ce7b34698acaada02d84defe480df38a2f32dd72`
- **Focused test SHA-256:** `5607b1d0da7fec7f083462ac54b45967a4c4c9bb2d95016a4e040df3edf4ba27`

## Validation commands and results

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

The corrected forward and reversed synthetic groups produced identical complete result dictionaries, including:

- `deposit_sum_MeV = 1.000000000000001`
- `track_length_sum_mm = 11.0`
- `sim_total_MeV_cm2_g = 0.9090909090909101`
- `summation_method = MATH_FSUM_PER_GROUP`

Additional checks passed:

- exact pre-change Git-blob reconstruction;
- exact post-change Git-blob verification;
- existing report precision and report reproducibility regressions;
- validation JSON parsing;
- SVG XML parsing;
- changed Python line length no greater than 100 characters.

Not run:

- full repository pytest;
- ruff;
- Geant4 build or CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

No broader CI or physics result is claimed.

## Reproducible evidence

Added:

- `tests/test_compare_stopping_power_order_invariance.py`
- `docs/validation/stopping_power_order_invariance_audit.md`
- `docs/validation/stopping_power_order_invariance_validation.json`
- `docs/validation/stopping_power_order_invariance.svg`

The SVG is explicitly labelled as synthetic floating-point regression evidence, not detector data. It uses exact values, text, position, cross-out, and line geometry rather than color alone.

## Direct-to-main commits before archive

- `d9aa75dc686fd5e18b0d8f2f4256ea57397bd288` — `fix(single-stave): make stopping-power aggregation order-stable`
- `3ac6f171ff7265b9959320a43ccfb8f3f5c84792` — `test(single-stave): cover stopping-power row-order invariance`
- `3f1572f237fa1920909fed643d40d43d209b93e3` — `docs(validation): record stopping-power order-invariance audit`
- `d7c8525e66258f590ca138000d223112e738d3ab` — `docs(validation): add stopping-power order-invariance record`
- `768e13daa5056dd06f9b962e66b004fa5d9c4d97` — `docs(validation): visualize stopping-power order invariance`
- `78cae0518e2b45cfad22c05680e12bf27adcd5af` — `docs(audit): claim stopping-power order-invariance task`
- `43c54a567be31c251b0aaa84369589e873883ec2` — `docs(audit): record stopping-power order-invariance task`
- `7acbf963841912190361dd46421af83f13939ee2` — `docs(audit): index stopping-power order invariance`
- `71b634b1713d57cb7fd9f7c9ad1aacb9d6185114` — `docs(audit): map stopping-power order invariance`
- `e178644f0957087e74d81d8e8df59b50836f032b` — `docs(audit): ledger stopping-power order invariance`
- `4ce36c238361a10088176bbd7412e667b18e76fb` — `docs(audit): classify stopping-power order invariance`
- `c3167359138cb7fa6a5ed50e29b81bd0a8d56c43` — `docs(audit): register stopping-power order-invariance visual`
- `484b9143c51f20f236685839c50b4d4126d54c39` — `docs(audit): refine stopping-power closure blocker`

Every connector contents write returned a successful direct-main commit. No force push, history rewrite, or task branch was used.

## Scientific boundary and next action

This correction removes a numerical file-order artifact from the deposited-energy proxy. It does not establish that local deposited energy equals projectile total kinetic-energy loss, quantify generated-secondary escape, handle energy evolution, provide a statistical/systematic uncertainty budget, validate a real immutable export, or demonstrate Geant4/PSTAR agreement.

The next accepted stopping-power work remains `AUD-G4-011` and `AUD-G4-005`: validate exact real exported event bytes and an accepted projectile-loss observable, then preregister and propagate uncertainty before evaluating closure.
