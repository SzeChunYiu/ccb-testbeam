# Latest Scientific Review Handoff

## Session

- **UTC:** `2026-07-23T21:05:42Z`
- **Task:** `AUD-G4-016`
- **Repository:** `SzeChunYiu/ccb-testbeam`
- **Initial remote main:** `5c64e283594f1ef23d0685eac7b8249d45f1670b`
- **Validated implementation/evidence head:** `cff8a9f076f334333e938444a34168e4643f1e5f`
- **Remote main immediately before this handoff:** `ae573a82e038a131be0793e308c9339fb1109518`
- **Destination:** direct to `main`
- **Acceptance:** COMPLETE for exact floating-point identity in stopping-power reports; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

## Start-of-run and concurrent-work review

- Inspected current remote-main history, repository permissions, PR #868, canonical stopping-power code, shared simulation/PSTAR validators, focused tests, validation records, and all mandatory `chatgpt_todo/` files.
- `AUD-REPO-001` remained owned by a concurrent session and was not duplicated.
- A direct clone was unavailable because this runtime could not resolve `github.com`; exact source and test bytes were reconstructed through authenticated GitHub reads and checked with Git blob hashes.
- Concurrent non-overlapping PR #910 merged as `536d632a2ce446cc95fcf7c635b3597ee99eae13` after the first coordination writes. It changed Geant4 WLS configuration, not this task's stopping-power code/evidence. Subsequent writes used the advanced remote `main` without force-push or history rewrite.
- PR #868 remains closed, unmerged, and non-mergeable. It was not reopened, modified, or merged.
- No task branch, pull request, force-push, history rewrite, unrelated deletion, or destructive source-data edit was used.

## Confirmed numerical-traceability defect

The comparison had already been corrected to group events by exact parsed numeric energy, but its machine-readable output serialized every float with six significant digits:

```python
f"{result[key]:.6g}"
```

and its terminal table displayed configured energy with two decimal places.

Two separate results at `1.0000001 MeV` and `1.0000002 MeV` were therefore written as the identical CSV token `1` and shown as the identical terminal token `1.00`. A downstream reader could not reconstruct which exact configured-energy point produced each row, despite `energy_grouping=EXACT_CONFIGURED_ENERGY`. Other floating-point fields were also truncated by the same output rule.

Exact pre-change provenance:

- Git blob: `c3884d953a38b0dad69f50e3a9dc787bc1f29fd0`
- File bytes: `18742`
- New-test negative control: `2 failed, 1 passed`
- Measured former close-energy CSV tokens: `["1", "1"]`

## Validated correction

`scripts/single_stave/compare_stopping_power.py` now:

- defines `REPORT_FLOAT_SERIALIZATION=PYTHON_REPR_ROUND_TRIP`;
- writes every finite float using Python's shortest round-trip `repr`;
- rejects a nonfinite value at the report boundary;
- records `report_float_serialization` in result dictionaries and CSV rows;
- prints configured energy using the same round-trip representation;
- preserves the existing canonical input parsers, reference component identity, range rejection, exact grouping, raw/quenched gate, deuteron proxy gate, and uncertainty non-acceptance.

Parsing a written float token now reproduces the same binary float used by the calculation. This is a serialization-identity correction, not a claim that the diagnostic is an accepted measurement or closure.

## Regression and validation

Added:

- `tests/test_compare_stopping_power_report_precision.py`

Executed on exact local reconstructions:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_report_precision.py

python -m pytest tests/test_compare_stopping_power_report_precision.py -q

3 passed in 0.03s
```

Coverage verifies:

- the historical `.6g` collision;
- distinct post-change CSV tokens `1.0000001` and `1.0000002`;
- exact round-trip recovery for every float field;
- distinct terminal energy labels;
- explicit serialization-contract metadata;
- fail-closed nonfinite output.

Additional passed checks:

- exact old Git blob reconstruction;
- exact current Git blob identities;
- script blob `5081da0b77bcfeba07dca95e5087c4b2057c362f`;
- test blob `0003cb29cb5a31a38186b589e030ad29263b5a4b`;
- script SHA-256 `838cdee5921f65f38e9cf8e0a1e7f39f94f62cc31815ce9315dbd46778571caa`;
- test SHA-256 `b226f2b947585efbe3141fb40accc0c1788995bed35d2fff93bf3b1a78b3d180`;
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

No broader CI, simulation, or physics-closure success is claimed.

## Reproducible evidence

Added:

- `docs/validation/stopping_power_report_precision_audit.md`
- `docs/validation/stopping_power_report_precision_validation.json`
- `docs/validation/stopping_power_report_precision.svg`

The SVG is explicitly labelled synthetic regression evidence, not detector data. It shows the former two-floats-to-one-token collision and the corrected two distinct round-trip tokens using text, position, line routing, boxes, and a crossed-out former state rather than relying on color.

## Direct-to-main commit sequence

Implementation, test, and evidence:

- `212d3db82fb920d1dfc2e39de7867b37971d97c8` — `fix(single-stave): preserve round-trip report precision`
- `12c2b88a2aa7557fe9a7b4d9c33e47adbaf2b351` — `test(single-stave): cover round-trip report precision`
- `ee88f8325d92086bca25af2a158938e38684339e` — audit Markdown
- `310945dbcef99ae28ae0e3de2cf644628a174d3d` — validation JSON
- `cff8a9f076f334333e938444a34168e4643f1e5f` — visual evidence

Coordination and immutable provenance:

- `5948b9a19eef068ca99fc48bb135cbeec98daf72` — active task
- `cf5b805f2628d5d7443e9aeaff68f66a5fb50d16` — backlog
- `b01ec286a2a9fbf5cb6eca3ec762f7ce4eb79f3c` — master index
- `638a16890e7e9b69e1ee5b42fc0ec82f7e1ab1d5` — code-result map
- concurrent `536d632a2ce446cc95fcf7c635b3597ee99eae13` — non-overlapping PR #910 merge
- `d07f72643f84fb24c2148e38ab8120a177e42301` — study ledger
- `340f9c812b54b1445550a7e64272f13848acc0db` — claim matrix
- `34ba8ce6bbd1f50222b76f3d4cfa807c07554861` — visualization matrix
- `6aab30077530c399b4fb188b13182a3b1f9fb057` — blocker refinement
- `d46aa58d73820b7926591d3f6314424355a03fef` — immutable archive
- `ae573a82e038a131be0793e308c9339fb1109518` — append-only session log

All session-owned GitHub contents operations returned successful direct-main commits. The final handoff commit is confirmed separately by remote-main history after this write.

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
- `SESSION_LOG.md`
- `HANDOFF.md`

Added immutable session record:

- `chatgpt_todo/archive/2026-07-23T210542Z_AUD-G4-016_REPORT_PRECISION.md`

## Scientific boundary and next task

No exact real Geant4 event table, ROOT output, accepted projectile total-energy-loss observable, quantitative uncertainty budget, stopping-power closure, calibration, or detector-performance result was generated.

`AUD-G4-016` is COMPLETE. The next accepted stopping-power work remains `AUD-G4-005` and `AUD-G4-011`: validate immutable real exports and an accepted projectile-loss observable, quantify secondary escape and energy evolution, then preregister and propagate statistical/systematic uncertainty before evaluating any closure interval.
