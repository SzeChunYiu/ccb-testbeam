# Immutable Session Record — AUD-G4-016

## Session identity

- UTC: `2026-07-23T210542Z`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote `main`: `5c64e283594f1ef23d0685eac7b8249d45f1670b`
- Validated implementation/evidence head: `cff8a9f076f334333e938444a34168e4643f1e5f`
- Coordination head before archive: `6aab30077530c399b4fb188b13182a3b1f9fb057`
- Task ID: `AUD-G4-016`
- Destination: direct to `main`
- Acceptance: COMPLETE for floating-point report identity; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

## Start-of-run and concurrency review

The session inspected current remote-main history, the latest handoff and active task,
`compare_stopping_power.py`, its shared simulation/PSTAR validators, focused tests,
validation records, required `chatgpt_todo/` ledgers, commit status, and PR #868.
`AUD-REPO-001` remains owned by another active session and was not duplicated.

A direct clone was unavailable because the runtime could not resolve `github.com`.
Exact source bytes were reconstructed through authenticated GitHub reads and checked
with Git blob hashes. Repository writes used the authenticated contents API.

A concurrent non-overlapping merge, `536d632a2ce446cc95fcf7c635b3597ee99eae13`
(PR #910, configurable WLS time profile), landed after the first coordination writes.
It changed Geant4 WLS configuration files, not the stopping-power comparison or this
task's records. Subsequent writes were based on the advanced remote `main`; no
force-push, history rewrite, branch, or pull-request transport was used.

PR #868 was re-read and remains closed, unmerged, and non-mergeable. It was not
reopened, modified, or merged.

## Confirmed defect

The comparison had already been corrected to group by exact parsed numeric energy.
However, its CSV writer serialized every float using six significant digits:

```python
f"{result[key]:.6g}"
```

and the terminal table printed energy with two decimal places. Therefore two
separate result rows at `1.0000001 MeV` and `1.0000002 MeV` were written as the same
CSV token `1` and displayed as the same terminal token `1.00`. Downstream readers
could not recover which exact configured energy produced a row, contradicting the
reported `EXACT_CONFIGURED_ENERGY` grouping contract. The same six-digit rule could
also truncate other floating-point outputs.

Exact pre-change provenance:

- Git blob: `c3884d953a38b0dad69f50e3a9dc787bc1f29fd0`
- File bytes: `18742`

Running the new regression against those exact old bytes produced:

```text
2 failed, 1 passed
```

The negative control measured former CSV tokens `["1", "1"]` and duplicate terminal
labels `1.00` for the distinct input floats.

## Validated correction

`scripts/single_stave/compare_stopping_power.py` now:

- defines `REPORT_FLOAT_SERIALIZATION=PYTHON_REPR_ROUND_TRIP`;
- serializes every finite float using Python's shortest round-trip `repr`;
- rejects nonfinite values at the output boundary;
- records the serialization contract in every result and CSV row;
- prints configured energy with the same round-trip representation;
- preserves all existing fail-closed parser, physics-comparability, proxy, range,
  component-identity, exact-grouping, and uncertainty gates.

Python guarantees that parsing the emitted representation as a float reproduces the
same binary floating-point value used by the calculation. This is an identity and
traceability correction, not a claim that binary floats represent exact physical
truth or that the diagnostic is an accepted closure.

## Regression and validation

Added:

- `tests/test_compare_stopping_power_report_precision.py`

The tests cover:

1. historical `.6g` collision for two distinct energies;
2. exact round-trip recovery for every floating-point CSV field;
3. distinct terminal configured-energy labels;
4. explicit serialization-contract metadata;
5. fail-closed nonfinite output.

Executed on exact local reconstructions:

```text
python -m py_compile \
  scripts/single_stave/compare_stopping_power.py \
  tests/test_compare_stopping_power_report_precision.py

python -m pytest tests/test_compare_stopping_power_report_precision.py -q

3 passed in 0.03s
```

Additional passed checks:

- exact pre-change Git-blob reconstruction;
- old-bytes negative control: `2 failed, 1 passed`;
- current script Git blob matched `5081da0b77bcfeba07dca95e5087c4b2057c362f`;
- current test Git blob matched `0003cb29cb5a31a38186b589e030ad29263b5a4b`;
- script SHA-256 `838cdee5921f65f38e9cf8e0a1e7f39f94f62cc31815ce9315dbd46778571caa`;
- test SHA-256 `b226f2b947585efbe3141fb40accc0c1788995bed35d2fff93bf3b1a78b3d180`;
- validation JSON parsed;
- SVG parsed as XML;
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

The visual explicitly labels itself synthetic regression evidence, not detector
data. It uses position, text, line routing, boxes, and a crossed-out former state;
color is not required to interpret the result.

## Direct-to-main commits before archive

Implementation, test, and evidence:

- `212d3db82fb920d1dfc2e39de7867b37971d97c8` — `fix(single-stave): preserve round-trip report precision`
- `12c2b88a2aa7557fe9a7b4d9c33e47adbaf2b351` — `test(single-stave): cover round-trip report precision`
- `ee88f8325d92086bca25af2a158938e38684339e` — audit Markdown
- `310945dbcef99ae28ae0e3de2cf644628a174d3d` — machine-readable validation
- `cff8a9f076f334333e938444a34168e4643f1e5f` — visual evidence

Coordination:

- `5948b9a19eef068ca99fc48bb135cbeec98daf72` — active task
- `cf5b805f2628d5d7443e9aeaff68f66a5fb50d16` — backlog
- `b01ec286a2a9fbf5cb6eca3ec762f7ce4eb79f3c` — master index
- `638a16890e7e9b69e1ee5b42fc0ec82f7e1ab1d5` — code-result map
- concurrent `536d632a2ce446cc95fcf7c635b3597ee99eae13` — non-overlapping PR #910 merge
- `d07f72643f84fb24c2148e38ab8120a177e42301` — study ledger
- `340f9c812b54b1445550a7e64272f13848acc0db` — claim matrix
- `34ba8ce6bbd1f50222b76f3d4cfa807c07554861` — visualization matrix
- `6aab30077530c399b4fb188b13182a3b1f9fb057` — blocker refinement

All session-owned writes returned successful commits directly on remote `main`.

## Scientific boundary and next action

No real Geant4 event table, ROOT output, stopping-power closure, uncertainty budget,
calibration, or detector-performance result was generated. Local deposited energy
remains a diagnostic proxy rather than a demonstrated projectile total-energy-loss
observable. Deuteron equal-velocity mapping remains non-accepting.

The next accepted stopping-power unit remains `AUD-G4-005` / `AUD-G4-011`: validate
immutable real exports and an accepted projectile-energy-loss observable, then
preregister and propagate statistical/systematic uncertainty before evaluating any
closure interval.
