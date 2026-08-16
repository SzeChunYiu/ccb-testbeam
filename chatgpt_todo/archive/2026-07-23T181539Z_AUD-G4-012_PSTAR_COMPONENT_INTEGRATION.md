# AUD-G4-012 — Canonical PSTAR component identity integration

## Session

- UTC: `2026-07-23T18:15:39Z`
- Owner: scheduled ChatGPT audit session
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `bf295c1e7d295698673ffa7bb4c668c19015df49`
- Validated implementation/evidence head: `084b753685e5dc22a978482eef71f7649e352d3b`
- Destination: direct commits to `main`
- Task: `AUD-G4-012`

## Start-of-run review

Inspected current `main`, recent history, open PRs, PR #868, repository permissions, the comparison script, strict simulation parser, standalone PSTAR component validator, focused tests, exact committed PSTAR reference metadata, and all mandatory `chatgpt_todo/` records. PR #868 remained closed, unmerged, and non-mergeable and was not modified.

Direct local clone remained unavailable because the runtime could not resolve `github.com`; authenticated connector reads and writes were used. No force-push, history rewrite, unrelated deletion, or raw-data modification occurred.

## Confirmed defect

The standalone v1.0.0 component validator checked the exact-decimal identity

`total_MeV_cm2_g = electronic_MeV_cm2_g + nuclear_MeV_cm2_g`

but `scripts/single_stave/compare_stopping_power.py` maintained an independent float parser. A finite positive ordered row such as `1,9,1,8` could therefore enter a numerical ratio even though its total disagreed with the components.

## Validated correction

`tools/audit/validate_pstar_component_sum.py` is now v1.1.0 and exposes `read_validated_pstar_table()`, returning canonical float rows plus exact input provenance after:

- complete/unique required-header validation;
- exact Decimal parsing of every required field;
- finite and physical-value checks;
- strict declared energy order;
- half-unit-in-last-written-place intervals;
- overlap enforcement between the declared-total interval and the summed component interval.

`compare_stopping_power.py` now imports this parser directly. It records reference SHA-256, bytes, validated-row count, validator version, component identity, and consistency in each result and output CSV. The self-test uses the same path.

A direct CLI fixture with `1,9,1,8` returns status 2, writes no result CSV, and prints no `NUMERICAL TOLERANCE: PASS`.

## Files changed

- `scripts/single_stave/compare_stopping_power.py`
- `tools/audit/validate_pstar_component_sum.py`
- `tests/test_validate_pstar_component_sum.py`
- `tests/test_compare_stopping_power_pstar_component_integration.py`
- `docs/validation/pstar_component_sum_integration_audit.md`
- `docs/validation/pstar_component_sum_integration_validation.json`
- `docs/validation/pstar_component_sum_integration.svg`
- relevant `chatgpt_todo/` ledgers and blocker state

## Validation

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tools/audit/validate_pstar_component_sum.py \
  tests/test_validate_pstar_component_sum.py \
  tests/test_compare_stopping_power_pstar_component_integration.py

python -m pytest \
  tests/test_validate_pstar_component_sum.py \
  tests/test_compare_stopping_power_pstar_component_integration.py \
  tests/test_compare_stopping_power_reference_integrity.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_quenched_proxy.py \
  tests/test_compare_stopping_power_sim_input_integration.py \
  tests/test_validate_stopping_power_sim_table.py -q

42 passed in 4.22s
```

Additional passed checks:

- validation JSON parsed;
- SVG parsed as XML;
- maximum changed Python line length: 97;
- local file SHA-256 values recorded in the validation JSON.

Not run:

- full repository pytest;
- ruff;
- Geant4 build/CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

## Direct-main commits through validated evidence head

- `b1b0d4b180c5a125a222c11795e4ada46adce2dc` — `fix(single-stave): integrate PSTAR component identity gate`
- `f13d9d9f1e845c7e15b6ae79d08b269dc67fed54` — `refactor(audit): expose canonical validated PSTAR rows`
- `a9c4c161715a02dbbe0efedb71734de70154e7e5` — `test(audit): cover canonical PSTAR row return`
- `fbedabdfed0d8588aa7dfdf0eea597d0372fdb56` — `test(single-stave): integrate PSTAR component identity gate`
- `1ec2487c70b70191c81cd7f2340ed425aacae7a3` — `docs(validation): record PSTAR component integration audit`
- `9c1271134c7ae08173d3acc079a0f1d57fc4aa6b` — `docs(validation): add PSTAR component integration record`
- `084b753685e5dc22a978482eef71f7649e352d3b` — `docs(validation): visualize PSTAR component integration gate`

Coordination commits before this archive:

- `36616f358291800d2f5fd97e9a353d6ee87f7cda`
- `ea54802219b80123db0746befa9dac3640f4f992`
- `28a564545c9d0ef96f1197d8429e49d32e908237`
- `6744f91cc5b3560f4b96f2c9a8fc241c7f456d4a`
- `8038e8458c4c89936dddec1e0beeaad24439004b`
- `672407761297f707f061fca8ca6ff6e1cecc7ca7`
- `df85cbd960157ec420caf73dc96757d495a1541f`
- `d867cf8d769be2ef9bbb07a9b53c8c1d6e295e48`

## Acceptance and scientific boundary

`AUD-G4-012` is COMPLETE. The canonical comparison can no longer bypass the internal PSTAR component identity.

This does not independently verify the external NIST transcription or material selection. It does not show that local Geant4 deposited energy equals projectile total energy loss. Deuteron velocity scaling remains approximate. Accepted physics closure remains open under `AUD-G4-005` / `BLK-G4-SP-001`, and exact real-export execution remains open under `AUD-G4-011`.
