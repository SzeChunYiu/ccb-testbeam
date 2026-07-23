# Latest Scientific Review Handoff

## Session

- **UTC:** `2026-07-23T20:28:12Z`
- **Task:** `AUD-G4-015`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `905a83ce1723b10dafab46887a76aa48378f2234`
- **Validated implementation/evidence head:** `08f615f6b6edefa363eee086930e1eb0867474bb`
- **Coordination/archive head before this handoff:** `21294243b5d8a3bdd8dca3d207e959d79d68ab15`
- **Destination:** direct to `main`
- **Acceptance:** COMPLETE for fail-closed point-estimate uncertainty authorization, focused regression, visual evidence, coordination, and immutable archive; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

## Start-of-run and concurrent-work review

- Inspected current remote-main history, permissions, PR #868, canonical stopping-power code, shared simulation/PSTAR validators, focused tests, validation records, and mandatory `chatgpt_todo/` files.
- PR #868 is closed, unmerged, and non-mergeable. It was not reopened, modified, or merged.
- `AUD-REPO-001` remains owned by a concurrent LUNARC session and was not duplicated.
- A direct clone was attempted and failed with `Could not resolve host: github.com`; exact source/test bytes were reconstructed through authenticated GitHub reads and verified with Git blob hashes.
- No task branch, pull request, force-push, history rewrite, unrelated deletion, raw-data edit, simulation-output edit, or fabricated result was used.

## Confirmed scientific-method defect

The previous direct-proton acceptance logic required only:

1. unquenched raw deposited-energy input;
2. a direct proton PSTAR reference;
3. a point-estimate ratio inside the selected percentage tolerance.

It evaluated no statistical or systematic uncertainty. A synthetic one-event ratio of exactly `1.0` therefore set `within_tolerance=true`, printed `PASS` and `NUMERICAL TOLERANCE: PASS`, and returned status `0`. Forty repeated identical rows produced the same acceptance without providing independent uncertainty information.

Exact pre-change script provenance:

- Git blob: `8b9c0c530b6414c774601286a0d67f13500aa532`
- SHA-256: `768d4136bf59ee10c5074298bd7fa8195adb3d680e291802b520c88f97911260`

Running the new four-test regression against those exact old bytes produced `4 failed`, confirming all former fail-open cases.

## Methodological source

Recorded primary methodological source:

- B. N. Taylor and C. E. Kuyatt, *Guidelines for Evaluating and Expressing the Uncertainty of NIST Measurement Results*, NIST Technical Note 1297 (1994), DOI `10.6028/NIST.tn.1297`.
- Sections 2, 5, and 7 support quantitative uncertainty reporting, classification of statistically evaluated and other components, combination, and transparent reporting.

This source is used as a reporting-method standard. It does not transform the local-deposition simulation proxy into a physical measurement.

## Validated correction

`compare_stopping_power.py` now:

- preserves `numeric_within_tolerance` as a point-estimate diagnostic;
- records `uncertainty_method=NOT_EVALUATED`;
- records `uncertainty_evaluated=false`;
- records explicit `acceptance_status` values;
- keeps `within_tolerance=false` until a validated uncertainty method exists;
- prints a numerical match as `POINT_ONLY`, never `PASS`;
- prints `NUMERICAL TOLERANCE: POINT_ESTIMATE_ONLY_NOT_ACCEPTED`;
- prints `UNCERTAINTY EVALUATION: NOT_EVALUATED`;
- returns CLI status `1` for point-estimate-only output;
- keeps the built-in self-test explicitly arithmetic/path-wiring only: it can return success for exact synthetic arithmetic but reports the non-accepting scientific state.

No uncertainty number or interval was invented.

## Regression and validation

Added:

- `tests/test_compare_stopping_power_uncertainty_gate.py`

Updated:

- `tests/test_compare_stopping_power_energy_grouping.py`
- `tests/test_compare_stopping_power_quenched_proxy.py`
- `tests/test_compare_stopping_power_pstar_component_integration.py`
- `tests/test_compare_stopping_power_deuteron_proxy.py`

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

Additional passed checks:

- exact old Git blob reconstruction;
- exact committed Git blob identities for all changed Python files;
- old-bytes negative control: `4 failed` as expected;
- JSON parse;
- SVG XML parse;
- maximum changed Python line length: 97 characters.

Not run:

- full repository pytest;
- ruff;
- Geant4 build/CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

No broader CI or stopping-power agreement is claimed.

## Reproducible evidence

Added:

- `docs/validation/stopping_power_uncertainty_gate_audit.md`
- `docs/validation/stopping_power_uncertainty_gate_validation.json`
- `docs/validation/stopping_power_uncertainty_gate.svg`

The SVG is explicitly labelled synthetic regression evidence, not detector data. It contrasts the former PASS/exit-0 state with the corrected `POINT_ONLY`/exit-1 state using text, line style, position, and a crossed-out former state rather than color alone.

## Direct-to-main commit sequence

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

Coordination and immutable provenance:

- `9edd7b85b24e76b5022d194c50194fba1bf2d749` — active task
- `c9c8fc64fd4564f8bad9380c60de14c4a9eba908` — backlog
- `5ca3ec50f195cdab5388670c159704173c931bee` — master index
- `cd63a759c51f36f0cc5b9d3de9fe90ed8aa78f43` — claim matrix
- `80943b7fbae8b385296358ab62045fc1a3dc71f2` — code-result map
- `dafa4080dffd9567b879dc4dc2877cec3bd8a77b` — study ledger
- `1cd43d79196cf385aff2fb6b1188e65ac2ccb4b2` — visualization matrix
- `8e16214d317102c4ad85f580edb80c960ebe91d2` — blocker refinement
- `21294243b5d8a3bdd8dca3d207e959d79d68ab15` — immutable archive

All GitHub contents operations returned successful direct-main commits. Remote history was re-read after the writes and showed the sequence consecutively on `main`. No branch or PR transport was required.

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

- `chatgpt_todo/archive/2026-07-23T202812Z_AUD-G4-015_UNCERTAINTY_GATE.md`

`SESSION_LOG.md` was inspected but not replaced: the connector exposes complete-file replacement rather than a safe append operation, and the append-only file is large. Replacing it from paged/truncated retrieval risked destroying prior provenance. The immutable archive contains the complete session entry and this limitation is explicit here.

## Scientific boundary and next task

This run does not implement an uncertainty budget and does not claim accepted Geant4/PSTAR agreement. No exact real event table, ROOT output, `G4EmCalculator` calculation, projectile entry/exit-energy closure, calibration, or detector-performance result was generated.

The next accepted unit is `AUD-G4-005`/`AUD-G4-011`: validate immutable real exports and an accepted projectile-energy-loss observable, then preregister and propagate event/replicate Type A uncertainty, between-seed/run/configuration variation, deposit/path covariance, material-density/reference uncertainty, production-cut/physics-list/material/geometry sensitivity, secondary escape, and particle-energy evolution before evaluating a closure interval.
