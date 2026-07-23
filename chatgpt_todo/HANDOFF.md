# Latest Scientific Review Handoff

## Session

- **UTC:** `2026-07-23T20:19:05Z`
- **Task:** `AUD-G4-014`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `f147160f2c3be0df59f45c77cf209d2982547d04`
- **Validated implementation/evidence head:** `b24260118f25d1d36fbee118fb4ed1891377ef6c`
- **Coordination/archive head before this handoff:** `7d0de67e4e262e86700db4db64938aee8de0d2b8`
- **Destination:** direct to `main`
- **Acceptance:** COMPLETE for deuteron-reference fail-closed authorization, focused regression, visual evidence, coordination, and immutable archive; accepted stopping-power physics closure remains PARTIAL.

## Start-of-run and concurrent-work review

- A direct clone was attempted and failed with `Could not resolve host: github.com`; authenticated GitHub connector reads and direct-main writes were used.
- Inspected remote-main history, repository permissions, PR #868, canonical stopping-power code, strict simulation/PSTAR validators, focused tests, validation records, and all mandatory `chatgpt_todo/` files.
- PR #868 remains closed, unmerged, and non-mergeable. It was not reopened, modified, or merged.
- No overlapping active/completed task was duplicated. No task branch, pull request, force-push, history rewrite, unrelated deletion, or raw-data modification was used.

## Confirmed scientific-method defect

The canonical diagnostic mapped deuterons to proton PSTAR at half the configured energy:

```python
if normalized.startswith("d"):
    return energy_mev / 2.0
```

Acceptance then used only the unquenched-deposit flag and numerical tolerance. A raw deuteron row could therefore set `within_tolerance=true`, print `NUMERICAL TOLERANCE: PASS`, and return status 0 even though its reference was an unvalidated equal-velocity proton proxy rather than a direct deuteron stopping-power datum.

Authoritative scope:

- NIST PSTAR provides stopping-power and range tables for protons, not deuterons.
- Brolley and Ribe, Phys. Rev. 98, 1112 (1955), DOI `10.1103/PhysRev.98.1112`, measured equal-velocity proton/deuteron stopping in selected gases, demonstrating that the relationship is an empirical, material-specific question rather than a provenance-free identity.

Exact pre-change script blob:

`3c492b172669f2cdca160c52e1acc495a319973e`

Synthetic defect case:

- deuteron configured energy: `2 MeV`;
- proton PSTAR lookup energy: `1 MeV`;
- simulated deposited-energy/path proxy: `10 MeV cm2/g`;
- proton reference: `10 MeV cm2/g`;
- numerical ratio: `1.0`;
- pre-change acceptance: true;
- corrected physics comparability: false.

## Validated correction

`compare_stopping_power.py` now:

- distinguishes `DIRECT_PSTAR_PROTON` from `VELOCITY_SCALED_PROTON_PROXY`;
- rejects deuteron input by default before writing an output CSV or printing a numerical PASS;
- permits `--allow-deuteron-proxy` only for labelled, non-accepting diagnostics;
- records `reference_basis`, `reference_direct_pstar_comparable`, and `physics_comparable` in results and CSVs;
- requires numerical tolerance, unquenched input, and a direct proton reference before setting `within_tolerance=true`;
- makes mixed proton/deuteron output non-accepting;
- uses proton cases only in the built-in self-test.

## Regression and validation

Added:

- `tests/test_compare_stopping_power_deuteron_proxy.py`

Updated:

- `tests/test_compare_stopping_power_energy_range.py`

Coverage:

1. default deuteron status-2 rejection, no output CSV, and no numerical PASS;
2. explicit proxy output with exact arithmetic ratio `1.0` but `within_tolerance=false`;
3. propagated reference-basis and physics-comparability fields;
4. direct proton acceptance remains available;
5. mixed proton/deuteron output remains non-accepting;
6. deuteron range checks still use proton-equivalent `E/2` but cannot authorize physics acceptance;
7. existing quenched-proxy behavior remains non-accepting.

Executed on exact local reconstructions:

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

- exact changed-file Git blob identity;
- validation JSON parse;
- SVG XML parse;
- maximum changed Python line length: 91;
- local changed-file SHA-256 capture.

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

No broader CI, deuteron-reference accuracy, or stopping-power agreement is claimed.

## Reproducible evidence

Added:

- `docs/validation/stopping_power_deuteron_proxy_audit.md`
- `docs/validation/stopping_power_deuteron_proxy_validation.json`
- `docs/validation/stopping_power_deuteron_proxy.svg`

The SVG is explicitly labelled synthetic regression evidence, not detector data. It contrasts the former numerical-PASS authorization with the corrected labelled, non-accepting proxy path.

## Direct-to-main commits

Implementation, tests, and evidence:

- `24e83639c0d99e667283a0bc46513cd8a739695e` — `fix(single-stave): fail closed on deuteron PSTAR proxy`
- `9ae8ab04fe671f7c3ae6fc021cf3f082234ea5e8` — `test(single-stave): gate deuteron PSTAR proxy`
- `2ad66f1016652a01a1adc44f3e9761024c9f621e` — `test(single-stave): mark deuteron range checks nonaccepting`
- `4cac6e22dc0e92576df8c334954ecd7aafdaea79` — `docs(validation): record deuteron PSTAR proxy audit`
- `590addf67b3e31b22af944bb64afcc58c33c708a` — `docs(validation): add deuteron proxy validation record`
- `b24260118f25d1d36fbee118fb4ed1891377ef6c` — `docs(validation): visualize deuteron proxy acceptance gate`

Coordination and provenance:

- `f30047711f549de57dec139324191242fc05dbfd` — active-task completion
- `4491635ad537bbfaa9c60407157cfa75039d55c7` — backlog completion
- `44c14791df3ae3ae7f75526fd456852bb65ca7e6` — master-index entry
- `33c12595c930879febcd1c29f6dd6c81ab4d5c13` — code-result mapping
- `846bcfe2d3377fb02c5f7c0fefe3bca337fede6e` — study-ledger entry
- `0663db8f4f4fc9a3388adbfc46857eb652cbfc57` — claim classification
- `6655f4a64954ccd564e51513fefe16b404467a59` — visualization entry
- `d500c4d5900d6146aedefd937a07fe86a2aca9b6` — stopping-power blocker refinement
- `7d0de67e4e262e86700db4db64938aee8de0d2b8` — immutable session archive

Every listed write returned a successful direct-main commit SHA from GitHub's contents API. This handoff update is the final repository write for the session and must be re-read at remote-main head before delivery is reported. No git-push console transcript exists in this connector execution; the exact write result is the returned commit SHA and subsequent remote-main readback.

## Repository-local records

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

Added immutable provenance:

- `chatgpt_todo/archive/2026-07-23T201905Z_AUD-G4-014_DEUTERON_PROXY_GATE.md`

`SESSION_LOG.md` is append-only. It was inspected in complete non-overlapping ranges, but the connector exposes complete-file replacement rather than append. Replacing it from manually reconstructed chunks would create avoidable provenance-loss risk, so it was not rewritten. The immutable archive contains the complete session entry and this limitation is explicit rather than concealed.

## Blockers and next action

### Resolved

`AUD-G4-014` is COMPLETE. Proton PSTAR evaluated at `E_d/2` can no longer masquerade as a direct, accepting deuteron reference.

### Still open

- `AUD-G4-011`: run the integrated CLI on exact immutable real Geant4 exports with complete input/output/environment provenance.
- `AUD-G4-005` / `BLK-G4-SP-001`: establish an accepted proton closure using `G4EmCalculator` or primary entry/exit energy plus path/reference integration and quantify escaping-secondary energy and production-cut dependence.
- For deuterons, obtain an authoritative deuteron stopping-power reference or independently validate a bounded approximation for the exact material and energy domain.
- External PSTAR transcription/material provenance remains independently unverified.

## Scientific boundary

This session validates fail-closed reference-basis authorization and its traceable software enforcement. It does not establish the accuracy of the deuteron equal-velocity approximation for polystyrene, does not establish that local deposited energy equals projectile total energy loss, and does not establish Geant4/PSTAR agreement, calibration, or detector performance. No Geant4 executable, ROOT file, real event table, stopping-power closure, calibration, or detector-performance output was generated.
