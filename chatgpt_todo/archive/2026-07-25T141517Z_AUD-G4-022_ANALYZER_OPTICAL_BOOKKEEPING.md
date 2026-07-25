# AUD-G4-022 — analyzer optical-bookkeeping remediation

## Identity

- Session stamp: `2026-07-25T141517Z`
- Owner: scheduled scientific-review session
- Initial remote main: `48e3192dc69dd8c9408930171ed66f7a0627979e`
- Validated core/evidence head: `f2477309b4ac7e6ed15946752c70747b67837eed`
- Destination: direct commits to remote `main`; no force-push, history rewrite, task branch, or PR transport
- Focused acceptance: `VALIDATED`
- Cumulative task status: `PARTIAL`

## Repository area reviewed

- `geant4/single_stave/src/RunAction.cc`
- `scripts/single_stave/adapt_geant4_events.py`
- `scripts/single_stave/analyze_single_stave.py`
- `scripts/single_stave/EVENT_CONTRACT.md`
- `geant4/single_stave/README.md`
- `tests/test_adapt_geant4_events.py`
- current `chatgpt_todo/ACTIVE_TASK.md` and `HANDOFF.md`
- recent direct-main history and current PR #868 boundary inherited from the prior handoff

## Confirmed defect

The former analyzer blob `5a3fdd88757bec8b8f39b2ca9f7be889b70e848c`
bounded `n_end_selected` by `n_scint_generated` and used that same
scintillation-only denominator for G4S-03. The producer blob
`2e10565aa41182618083634cd18b6ddae89660da` records scintillation, WLS, and
Cerenkov generated optical tracks separately. The prior check rejected valid
WLS-inclusive bookkeeping and could produce a collection ratio above one.

Synthetic control:

- scintillation = 10
- WLS = 5
- Cerenkov = 0
- total = 15
- selected-end arrivals = 11
- former ratio = `11/10 = 1.1`
- corrected ratio = `11/15 = 0.7333333333333333`

## Correction

Analyzer version 2.0.0 implements policy
`ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL`.

It preserves the three component counters, requires the declared total when any
current-contract optical field is present, verifies the exact row-wise sum,
rejects malformed count contracts, bounds arrivals by the total, records the
contract/denominator in machine-readable outputs, and labels old inputs
`LEGACY_SCINTILLATION_ONLY` rather than treating them as current evidence.
G4S-03 now divides by `n_optical_generated_total` for current normalized input.

The Geant4 README and event-contract documentation were synchronized with the
corrected path while retaining the real-ROOT scientific boundary.

## Files delivered

- `scripts/single_stave/analyze_single_stave.py`
- `tests/test_analyze_single_stave_optical_contract.py`
- `scripts/single_stave/EVENT_CONTRACT.md`
- `geant4/single_stave/README.md`
- `tools/audit/render_single_stave_analyzer_optical_evidence.py`
- `docs/validation/single_stave_analyzer_optical_validation.json`
- `docs/validation/single_stave_analyzer_optical.svg`
- `docs/validation/single_stave_analyzer_optical_audit.md`
- this immutable archive
- updated active task and latest handoff

## Validation

```text
python -m py_compile \
  scripts/single_stave/analyze_single_stave.py \
  tests/test_analyze_single_stave_optical_contract.py \
  tools/audit/render_single_stave_analyzer_optical_evidence.py

PYTHONPATH=. pytest -q tests/test_analyze_single_stave_optical_contract.py

9 passed in 0.12s
```

A separate 120-row synthetic current-contract run completed the full analyzer
plot/result path with status `PASS_SMOKE`, contract `CURRENT_COMPONENT_SUM`, and
G4S-03 denominator `n_optical_generated_total`. The source table retained the
same denominator and contract. JSON and SVG parsing passed. Maximum changed
Python line length was 100. Ruff was unavailable.

## Direct-main sequence

- `10701b3c723e1380dba59b848eb1904fa6428cac` — analyzer remediation
- `c3e8c8ae3bb49ad08cb60b9b62d0257166cbe9e6` — focused tests
- `af7150d84567a23305fd7a191b05a81b79d82f52` — event-contract documentation
- `ab42dadd2d0e6b681082de059fbddf9824a600d2` — Geant4 README synchronization
- `96d517caccf8590f7b02acc57f1cbe1c3685c6eb` — evidence renderer
- `cadc6afaf5eb12a3697994e187dbca4606bf9a73` — validation JSON
- `f4eeab819e223dd16b42d46cc85b607d90138c0d` — SVG evidence
- `f2477309b4ac7e6ed15946752c70747b67837eed` — audit report / validated core head

The connector returned successful direct-main commit SHAs rather than textual
`git push` output. Post-write remote reads must confirm the final coordination
commit and focused predecessors on `main`.

## Checks not run

Repository-wide pytest and ruff, Geant4 build/CTest, immutable production ROOT
execution, GitHub Actions, and repository-wide link inventory were not run. No
broad CI success or physics closure is claimed.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced because the connector exposes
whole-file replacement rather than byte-safe append/patch and their complete
current contents are long-lived. Replacing a partial reconstruction could erase
unrelated provenance. This archive and `HANDOFF.md` are the append-equivalent
record; the mandatory aggregate synchronization gap remains explicit.

## Scientific boundary and next gate

No real ROOT bytes were processed, no Geant4 event was generated, and no optical
yield, calibration, resolution, PID, or detector-performance quantity was
measured or changed.

`AUD-G4-022` remains `PARTIAL`. Completion now requires executing the adapter and
analyzer on immutable real current-ROOT bytes with producer sidecar, producer
commit, ROOT and normalized hashes, row-count closure, result/manifest hashes,
and review of all real generated diagnostics.

PR #868 remains closed, unmerged, and untouched.
