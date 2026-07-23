# Immutable Session Record — AUD-G4-017

## Session

- **UTC:** `2026-07-23T21:31:26Z`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `5b6907d646527078c45ec615e0153f977f3214c5`
- **Validated implementation/evidence head:** `1d7e44a23516617b0ec9cf7deac27b052944b925`
- **Coordination head before archive:** `80e7761e4b996af420d37080ed39a857d370aa66`
- **Destination:** direct to `main`
- **Acceptance:** COMPLETE for stopping-power report central-value/configuration reproducibility; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

## Start-of-run review

- Inspected remote-main history, concurrent changes, repository permissions, PR #868, current commit status, the canonical stopping-power comparison, shared simulation/PSTAR validators, focused tests, validation records, and mandatory `chatgpt_todo/` files.
- `AUD-REPO-001` remained owned by a concurrent session and was not duplicated.
- PR #868 is closed, unmerged, and non-mergeable. It was not reopened, modified, or merged.
- A direct clone was attempted and failed with `Could not resolve host: github.com`; exact source/test bytes were reconstructed through authenticated GitHub reads.
- Concurrent non-overlapping SiPM/Geant4 work, including PR #912, advanced `main`; all session writes used current content SHAs and no force-push or history rewrite.

## Confirmed traceability defect

The report exposed derived `sim_total_MeV_cm2_g`, ratio, delta, and point-estimate status but omitted the inputs and numerical settings needed to reproduce them:

- summed deposited energy;
- summed track length;
- material density;
- tolerance percentage;
- estimator identity.

Thus two runs over identical event rows could use different density or tolerance settings and produce materially different numerical values or statuses without those choices appearing in the machine-readable report.

Exact pre-change provenance:

- Git blob: `5081da0b77bcfeba07dca95e5087c4b2057c362f`
- Bytes: `19191`
- SHA-256: `838cdee5921f65f38e9cf8e0a1e7f39f94f62cc31815ce9315dbd46778571caa`
- New-test negative control: `2 failed in 0.11s`

## Validated correction

`scripts/single_stave/compare_stopping_power.py` now records in every result and CSV row:

- `deposit_sum_MeV`;
- `track_length_sum_mm`;
- `material_density_g_cm3`;
- `mass_stopping_estimator=RATIO_OF_SUMS_TRACK_LENGTH_WEIGHTED`;
- `tolerance_percent`.

The central proxy is independently reconstructable as:

```text
(deposit_sum_MeV / track_length_sum_mm) * 10 / material_density_g_cm3
```

The point-estimate gate is independently reconstructable as:

```text
abs(delta_percent) <= tolerance_percent
```

The terminal output names the estimator. Existing shared parsers, exact energy grouping, proxy gates, uncertainty non-acceptance, and round-trip float serialization remain in place.

## Regression and validation

Added:

- `tests/test_compare_stopping_power_report_reproducibility.py`

Executed on exact local reconstructions:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_report_precision.py \
  tests/test_compare_stopping_power_report_reproducibility.py

python -m pytest \
  tests/test_compare_stopping_power_report_precision.py \
  tests/test_compare_stopping_power_report_reproducibility.py -q

5 passed in 0.07s
```

Additional passed checks:

- exact pre-change Git-blob reconstruction;
- old-bytes negative control: `2 failed in 0.11s`;
- current script blob `79ea276741807d896cc6d2a99e8071605cc238f0`;
- current script SHA-256 `5946901c0aa10fdc5f4e8e55d867927f6476ec03db4d58d75bd498d004687213`;
- current test blob `37595f083c2a12b5de7c42253cffb007874c7b7c`;
- current test SHA-256 `90105dd7b4cb2a588c24997d9b7b350ceb74a65ac09b120a75f1217a176ce24e`;
- validation JSON parse;
- SVG XML parse;
- maximum changed Python line length: 93 characters.

Not run:

- full repository pytest;
- ruff;
- Geant4 build/CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

## Reproducible evidence

Added:

- `docs/validation/stopping_power_report_reproducibility_audit.md`
- `docs/validation/stopping_power_report_reproducibility_validation.json`
- `docs/validation/stopping_power_report_reproducibility.svg`

The SVG is explicitly labelled synthetic regression evidence, not detector data, and contrasts the former derived-only report with the corrected self-contained report using text, position, formulae, and a crossed-out former state rather than color alone.

## Direct-to-main commit sequence before archive

- `aaac294ebef672461680c65bcfb85e0834f88864` — `fix(single-stave): make stopping-power reports independently reproducible`
- `a3591bdd69e2d7018a48476339eb8e396ba1621f` — `test(single-stave): cover self-contained stopping-power reports`
- `473786627d8ce9d7c76c44fc258ebd9e975b1713` — validation audit Markdown
- `c36e7a277c9a34d46b3f0911e0f89c161df5e31f` — validation JSON
- `1d7e44a23516617b0ec9cf7deac27b052944b925` — validation SVG
- `fa66a0c574a233e0f4fe6f0df5073cc99a68ce39` — active task
- `d169c588d8ba41f3e7bc1094cd32f90ab7d6e7df` — backlog
- `2a9275b2efcece8bf9d89a7915a5e3f5fb616df1` — master index
- `b0846c23396fb2407808e68388b23e86662cfd2d` — code-result map
- `3e3595549a8538a6760414d5b514846fab9d9db3` — study ledger
- `bf3418c3682cf437c6bbe20f099be15de04b7256` — claim matrix
- `80e7761e4b996af420d37080ed39a857d370aa66` — visualization matrix

## Scientific boundary and next work

No exact real Geant4 event table, ROOT output, accepted projectile total-energy-loss observable, quantitative uncertainty budget, stopping-power closure, calibration, or detector-performance result was generated.

`AUD-G4-017` is COMPLETE. Next accepted stopping-power work remains `AUD-G4-005` and `AUD-G4-011`: validate immutable real exports and an accepted projectile-loss observable, quantify secondary escape and energy evolution, then preregister and propagate statistical/systematic uncertainty before evaluating any closure interval.
