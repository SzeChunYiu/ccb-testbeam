# AUD-G4-014 — Deuteron PSTAR proxy acceptance gate

## Session

- **UTC:** `2026-07-23T20:19:05Z`
- **Owner:** scheduled ChatGPT audit session
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `f147160f2c3be0df59f45c77cf209d2982547d04`
- **Validated implementation/evidence head:** `b24260118f25d1d36fbee118fb4ed1891377ef6c`
- **Coordination head before archive:** `d500c4d5900d6146aedefd937a07fe86a2aca9b6`
- **Destination:** direct GitHub contents-API commits to `main`
- **Acceptance:** COMPLETE for the fail-closed deuteron-reference software gate; accepted stopping-power closure remains PARTIAL.

## Start-of-run review

- A direct clone was attempted and failed with `Could not resolve host: github.com`.
- Authenticated GitHub connector reads and direct-main writes were used.
- Inspected current main history, repository permissions, PR #868, canonical stopping-power code, strict simulation/PSTAR parsers, focused tests, prior validation records, and all mandatory `chatgpt_todo/` files.
- PR #868 remained closed, unmerged, and non-mergeable. It was not modified or merged.
- No task branch, pull request, force-push, history rewrite, raw-data modification, or unrelated deletion was used.

## Confirmed scientific-method defect

The pre-change code mapped deuterons to proton PSTAR at half the configured energy:

```python
if normalized.startswith("d"):
    return energy_mev / 2.0
```

but acceptance used only the unquenched-deposit flag and numerical tolerance. A raw deuteron row could therefore set `within_tolerance=true`, print `NUMERICAL TOLERANCE: PASS`, and return status 0 even though its reference was an unvalidated equal-velocity proton proxy rather than a direct deuteron datum.

NIST PSTAR is explicitly a proton stopping-power/range program. Equal-velocity proton/deuteron stopping comparisons are empirical and material-specific; the reviewed primary measurement is Brolley and Ribe, Phys. Rev. 98, 1112 (1955), DOI `10.1103/PhysRev.98.1112`.

Exact pre-change script blob:

`3c492b172669f2cdca160c52e1acc495a319973e`

Synthetic defect reproduction:

- deuteron configured energy: `2 MeV`;
- proton lookup energy: `1 MeV`;
- simulation proxy: `10 MeV cm2/g`;
- proton PSTAR reference: `10 MeV cm2/g`;
- numerical ratio: `1.0`;
- former acceptance: true;
- corrected physics comparability: false.

## Validated correction

`compare_stopping_power.py` now:

- distinguishes `DIRECT_PSTAR_PROTON` from `VELOCITY_SCALED_PROTON_PROXY`;
- rejects deuteron input by default before writing an output CSV or numerical PASS;
- permits `--allow-deuteron-proxy` only for labelled, non-accepting diagnostics;
- records `reference_basis`, `reference_direct_pstar_comparable`, and `physics_comparable` in result dictionaries and CSVs;
- requires numeric tolerance, unquenched input, and a direct proton reference before setting `within_tolerance=true`;
- makes mixed proton/deuteron output non-accepting;
- uses proton cases only in the built-in self-test.

## Files changed

- `scripts/single_stave/compare_stopping_power.py`
- `tests/test_compare_stopping_power_deuteron_proxy.py`
- `tests/test_compare_stopping_power_energy_range.py`
- `docs/validation/stopping_power_deuteron_proxy_audit.md`
- `docs/validation/stopping_power_deuteron_proxy_validation.json`
- `docs/validation/stopping_power_deuteron_proxy.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/BACKLOG.md`
- `chatgpt_todo/MASTER_INDEX.md`
- `chatgpt_todo/CODE_RESULT_MAP.md`
- `chatgpt_todo/STUDY_REVIEW_LEDGER.md`
- `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`
- `chatgpt_todo/VISUALIZATION_MATRIX.md`
- `chatgpt_todo/BLOCKERS.md`

## Validation

Executed on exact local reconstructions of the committed changed Python files and API-compatible copies of the unchanged canonical validators:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_deuteron_proxy.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_quenched_proxy.py

python -m pytest \
  tests/test_compare_stopping_power_deuteron_proxy.py \
  tests/test_compare_stopping_power_energy_range.py \
  tests/test_compare_stopping_power_quenched_proxy.py -q

9 passed in 5.78s
```

Additional passed checks:

- validation JSON parse;
- SVG XML parse;
- exact changed-file Git blob identity;
- maximum changed Python line length: 91.

Changed-file provenance:

| File | Bytes | SHA-256 | Git blob |
|---|---:|---|---|
| `scripts/single_stave/compare_stopping_power.py` | 17865 | `768d4136bf59ee10c5074298bd7fa8195adb3d680e291802b520c88f97911260` | `8b9c0c530b6414c774601286a0d67f13500aa532` |
| `tests/test_compare_stopping_power_deuteron_proxy.py` | 5103 | `135bf0b620a6bf5721329b29cf1fbd6e26e64e0b3200e0d5c2502b707a684b01` | `6febfc382a10d11194be1a57f99f41cf85bdcd48` |
| `tests/test_compare_stopping_power_energy_range.py` | 3859 | `479976f772e51c376ce6c3b12b42b9a8066ba2ce34156ebf9b8b6298948067e9` | `026b6a12a4ea27e499f2fc2baf3e98020d65a58a` |

Not run:

- full repository pytest;
- ruff, which was unavailable;
- Geant4 build/CTest;
- ROOT processing;
- real simulation execution;
- GitHub Actions.

## Direct-main commits

Implementation, tests, and evidence:

- `24e83639c0d99e667283a0bc46513cd8a739695e` — `fix(single-stave): fail closed on deuteron PSTAR proxy`
- `9ae8ab04fe671f7c3ae6fc021cf3f082234ea5e8` — `test(single-stave): gate deuteron PSTAR proxy`
- `2ad66f1016652a01a1adc44f3e9761024c9f621e` — `test(single-stave): mark deuteron range checks nonaccepting`
- `4cac6e22dc0e92576df8c334954ecd7aafdaea79` — `docs(validation): record deuteron PSTAR proxy audit`
- `590addf67b3e31b22af944bb64afcc58c33c708a` — `docs(validation): add deuteron proxy validation record`
- `b24260118f25d1d36fbee118fb4ed1891377ef6c` — `docs(validation): visualize deuteron proxy acceptance gate`

Coordination before archive:

- `f30047711f549de57dec139324191242fc05dbfd` — active-task completion
- `4491635ad537bbfaa9c60407157cfa75039d55c7` — backlog completion
- `44c14791df3ae3ae7f75526fd456852bb65ca7e6` — master-index entry
- `33c12595c930879febcd1c29f6dd6c81ab4d5c13` — code-result mapping
- `846bcfe2d3377fb02c5f7c0fefe3bca337fede6e` — study-ledger entry
- `0663db8f4f4fc9a3388adbfc46857eb652cbfc57` — claim classification
- `6655f4a64954ccd564e51513fefe16b404467a59` — visualization entry
- `d500c4d5900d6146aedefd937a07fe86a2aca9b6` — blocker refinement

Every write returned a successful direct-main commit SHA from GitHub's contents API. No git-push console transcript exists in this connector execution; the exact API outcome is the returned commit SHA and subsequent remote-main readback.

## Session-log limitation

`SESSION_LOG.md` is append-only. The connector exposes complete-file replacement, not an append primitive. The file was read in non-overlapping ranges, but replacing it from manually reconstructed chunks would create avoidable provenance-loss risk. It was therefore not rewritten. This immutable archive is the complete session record, and `HANDOFF.md` records the limitation explicitly.

## Scientific boundary and next actions

No real Geant4 event table, ROOT output, deuteron-specific polystyrene reference, accepted stopping-power closure, calibration, or detector-performance result was produced.

`BLK-G4-SP-001` remains OPEN. Next actions:

1. run the integrated CLI on exact real proton exports with immutable provenance;
2. validate a projectile-energy-loss observable using `G4EmCalculator` or primary entry/exit energy and path integration;
3. quantify secondary escape and production-cut dependence;
4. obtain an authoritative deuteron reference or independently validate a bounded approximation for the exact material and energy domain;
5. produce overlay, ratio, energy/path, and secondary-escape diagnostics with uncertainty and hashes.
