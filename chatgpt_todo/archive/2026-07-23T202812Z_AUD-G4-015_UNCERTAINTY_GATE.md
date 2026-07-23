# AUD-G4-015 — stopping-power point-estimate uncertainty gate

## Session

- **UTC:** `2026-07-23T20:28:12Z`
- **Owner:** scheduled ChatGPT scientific-review session
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `905a83ce1723b10dafab46887a76aa48378f2234`
- **Validated implementation/evidence head:** `08f615f6b6edefa363eee086930e1eb0867474bb`
- **Coordination head before archive:** `8e16214d317102c4ad85f580edb80c960ebe91d2`
- **Destination:** direct to `main`; no branch, pull request, force-push, or history rewrite
- **Acceptance:** COMPLETE for the fail-closed uncertainty authorization gate; accepted stopping-power physics closure remains blocked.

## Start-of-run review

Inspected current `main`, recent history, repository permissions, PR #868, canonical stopping-power code, strict simulation and PSTAR validators, focused tests, validation records, and mandatory `chatgpt_todo/` files. PR #868 is closed, unmerged, and non-mergeable and was not modified. A direct clone was attempted and failed because the runtime could not resolve `github.com`; authenticated GitHub connector reads and direct-main writes were used.

`AUD-REPO-001` remains owned by a concurrent LUNARC session and was not duplicated.

## Confirmed defect

The previous canonical comparison treated a direct-proton point estimate inside a percentage tolerance as accepted agreement when:

- the simulation field was labelled unquenched raw deposit;
- the reference was direct proton PSTAR;
- `abs(delta_percent) <= tolerance_percent`.

It did not evaluate statistical or systematic uncertainty. Exact synthetic reproduction using the pre-change script blob `8b9c0c530b6414c774601286a0d67f13500aa532` produced:

- one proton event;
- ratio `1.0`;
- `within_tolerance=true`;
- row status `PASS`;
- `NUMERICAL TOLERANCE: PASS`;
- CLI exit status `0`.

Forty repeated identical rows produced the same acceptance without supplying independent stochastic or systematic information.

## Methodological source

B. N. Taylor and C. E. Kuyatt, *Guidelines for Evaluating and Expressing the Uncertainty of NIST Measurement Results*, NIST Technical Note 1297 (1994), DOI `10.6028/NIST.tn.1297`. Sections 2, 5, and 7 support quantitative uncertainty reporting and the distinction between statistically evaluated and other uncertainty components. This is recorded as a reporting-method source, not as a claim that the simulation proxy is a measurement.

## Validated correction

`compare_stopping_power.py` now:

- retains `numeric_within_tolerance` as a point-estimate diagnostic;
- records `uncertainty_method=NOT_EVALUATED`;
- records `uncertainty_evaluated=false`;
- records explicit `acceptance_status`;
- keeps `within_tolerance=false` while uncertainty is not evaluated;
- prints direct numerical matches as `POINT_ONLY` rather than `PASS`;
- prints `NUMERICAL TOLERANCE: POINT_ESTIMATE_ONLY_NOT_ACCEPTED`;
- returns CLI status `1` for point-estimate-only output;
- preserves the built-in self-test as an explicitly arithmetic/path-wiring test that may return success while displaying the non-accepting scientific state.

No uncertainty value was invented. The code fails closed until a reviewed method exists.

## Validation

Executed on exact local reconstructions of the committed blobs:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/validate_pstar_component_sum.py \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_compare_stopping_power_uncertainty_gate.py \
  tests/test_compare_stopping_power_energy_grouping.py \
  tests/test_compare_stopping_power_quenched_proxy.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_deuteron_proxy.py

python -m pytest \
  tests/test_compare_stopping_power_uncertainty_gate.py \
  tests/test_compare_stopping_power_energy_grouping.py \
  tests/test_compare_stopping_power_quenched_proxy.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_deuteron_proxy.py -q

19 passed in 3.77s
```

The new four-test uncertainty module run against exact pre-change bytes produced `4 failed`, demonstrating all four former unsafe behaviors. JSON and SVG parsing passed. All changed Python files compiled. Maximum changed Python line length was 97 characters.

Validated committed blob identities:

| File | Git blob | SHA-256 |
|---|---|---|
| `scripts/single_stave/compare_stopping_power.py` | `c3884d953a38b0dad69f50e3a9dc787bc1f29fd0` | `ef7fbc16a8d31a361055942df9e9d3d16639bcb5b2ec3ce50e09fde56f7f8de6` |
| `tests/test_compare_stopping_power_uncertainty_gate.py` | `33a0a727a405f7c4b2cf4e40e107dcb0157a5b38` | `51b5ba2d35922631a01675dd85cdfa98e3bed83acbb0af1c6beb6319dac3b38b` |
| `tests/test_compare_stopping_power_energy_grouping.py` | `24f82f77e2ee71b7b8f8be99c4e449634df28391` | `7a571c409e25068f711f436ba0e1fef40fd743ab477bcfd398492503c4248c65` |
| `tests/test_compare_stopping_power_quenched_proxy.py` | `49ee4cf7e4f5b8f7e27e68304cfb4f4f29829ee8` | `53ae4ddb2de343eea67fdf35d18d27b26e61a1901b2e09a7e75ac346d9aaf96e` |
| `tests/test_compare_stopping_power_pstar_component_integration.py` | `e1c8cce837fcd64b5410a2ec4ac9eadaae9aaca3` | `b7ea3b1fae04d888098fa0f1e92f0f7e7cdba42dc1d198339ba47173dd937cf2` |
| `tests/test_compare_stopping_power_deuteron_proxy.py` | `d59302bcf4efc1829897db36d7726670d2ff9b8d` | `4dbdd8dfa7ac5c8134986f291e6829e599f4b2f5624a3d6048fe73ca2e9d2f40` |

Not run: full repository pytest, ruff, Geant4/CTest, ROOT processing, real simulation execution, or GitHub Actions. No broader CI success is claimed.

## Evidence

- `docs/validation/stopping_power_uncertainty_gate_audit.md`
- `docs/validation/stopping_power_uncertainty_gate_validation.json`
- `docs/validation/stopping_power_uncertainty_gate.svg`

The SVG is synthetic regression evidence and is explicitly labelled as not detector data.

## Direct-main commits

Implementation, tests, and evidence:

- `2ace1e6c74b0cd95f76365ed8c9d29d8eb1b9416` — `fix(single-stave): fail closed without uncertainty evaluation`
- `acbeaecf0302c993648a1c84ca30211f31d10eb2` — `test(single-stave): gate point estimates without uncertainty`
- `565bf55b3508ef645902e2e66b02dec843722adc` — energy-grouping acceptance regression
- `4db637b1ac3cec34ecab52e534fc05e134e4aad3` — raw/quenched acceptance regression
- `c85deddbaaadc0568c6058dbe52b2dd308a1a018` — PSTAR-provenance acceptance regression
- `448df29b559eac246681e47d0aaf66100a077d97` — proton/deuteron acceptance regression
- `306461d189eceb135ac6f6a969ec747c7610d6d1` — audit report
- `401cb5bcbf0883e426d07ce1bdb5844a28c270f2` — machine-readable validation
- `08f615f6b6edefa363eee086930e1eb0867474bb` — visual evidence

Coordination before this archive:

- `9edd7b85b24e76b5022d194c50194fba1bf2d749` — active task
- `c9c8fc64fd4564f8bad9380c60de14c4a9eba908` — backlog
- `5ca3ec50f195cdab5388670c159704173c931bee` — master index
- `cd63a759c51f36f0cc5b9d3de9fe90ed8aa78f43` — claim matrix
- `80943b7fbae8b385296358ab62045fc1a3dc71f2` — code-result map
- `dafa4080dffd9567b879dc4dc2877cec3bd8a77b` — study ledger
- `1cd43d79196cf385aff2fb6b1188e65ac2ccb4b2` — visualization matrix
- `8e16214d317102c4ad85f580edb80c960ebe91d2` — blocker refinement

Each GitHub contents operation returned a successful direct-main commit. Remote history was re-read after the writes and showed the sequence consecutively on `main`.

## Scientific boundary and next action

No real Geant4 event table, ROOT output, accepted uncertainty budget, projectile entry/exit-energy closure, `G4EmCalculator` comparison, calibration, or detector-performance result was produced.

The next accepted stopping-power unit must combine immutable real exports with an accepted projectile-energy-loss observable and a preregistered uncertainty budget covering statistical and relevant systematic/model components. Only then may an agreement interval and acceptance criterion be evaluated.
