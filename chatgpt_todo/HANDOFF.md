# Latest Handoff — AUD-G4-022 analyzer optical bookkeeping

## Delivery identity

- **Session stamp:** `2026-07-25T141517Z`
- **Initial remote `main`:** `48e3192dc69dd8c9408930171ed66f7a0627979e`
- **Validated implementation/evidence/active-task head:**
  `0b4e05b2432284cb0d2d06fffcdae98a27087cd3`
- **Immutable archive commit:**
  `b9c976759c054797273cf1367821e7ee5dafd370`
- **Validated delivery handoff / recorded after-SHA:**
  `a67a84fcfe206de5e091966226e1a67024cc1ada`
- **Destination:** direct contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport
- **Push result:** every contents write returned a successful commit SHA;
  post-write remote history confirmed `a67a84fcfe206de5e091966226e1a67024cc1ada`
  and all focused predecessors on `main`
- **Focused remediation acceptance:** `VALIDATED`
- **Cumulative task status:** `PARTIAL`
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T141517Z_AUD-G4-022_ANALYZER_OPTICAL_BOOKKEEPING.md`

## Confirmed defect and quantitative control

The former analyzer blob `5a3fdd88757bec8b8f39b2ca9f7be889b70e848c`
bounded all readout arrivals by `n_scint_generated` and used that same
scintillation-only denominator for G4S-03. The current producer blob
`2e10565aa41182618083634cd18b6ddae89660da` records generated
scintillation, WLS, and Cerenkov tracks separately.

A synthetic event with 10 scintillation, 5 WLS, 0 Cerenkov, and 11 selected-end
arrivals is valid under the current producer bookkeeping. The former observable
was `11/10 = 1.1`; the correct total-optical observable is
`11/15 = 0.7333333333333333`.

## Correction

`analyze_single_stave.py` is now version 2.0.0 under policy
`ANALYZER_MUST_PRESERVE_COMPONENT_OPTICAL_COUNTS_AND_USE_EXACT_TOTAL`.

For current normalized input it now:

1. preserves `n_scint_generated`, `n_wls_generated`,
   `n_cerenkov_generated`, and `n_optical_generated_total`;
2. rejects partial current optical contracts;
3. rejects nonfinite, negative, or fractional counts;
4. verifies the exact row-wise component sum;
5. applies `n_end_selected <= n_optical_generated_total` and then
   `n_detected_pe <= n_end_selected`;
6. uses the total for the G4S-03 collection-efficiency denominator;
7. records contract, denominator, and component summaries in validation,
   `result.json`, `single_stave_summary.csv`, G4S-03 plot metadata/source data,
   and the manifest;
8. keeps older tables readable only under the explicit
   `LEGACY_SCINTILLATION_ONLY` label.

The event-contract document and Geant4 README were synchronized with the
corrected normalized path without claiming real-ROOT physics closure.

## Files delivered

- `scripts/single_stave/analyze_single_stave.py`
- `tests/test_analyze_single_stave_optical_contract.py`
- `scripts/single_stave/EVENT_CONTRACT.md`
- `geant4/single_stave/README.md`
- `tools/audit/render_single_stave_analyzer_optical_evidence.py`
- `docs/validation/single_stave_analyzer_optical_validation.json`
- `docs/validation/single_stave_analyzer_optical.svg`
- `docs/validation/single_stave_analyzer_optical_audit.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`
- immutable archive listed above
- this handoff

## Validation

```text
python -m py_compile \
  scripts/single_stave/analyze_single_stave.py \
  tests/test_analyze_single_stave_optical_contract.py \
  tools/audit/render_single_stave_analyzer_optical_evidence.py

PYTHONPATH=. pytest -q tests/test_analyze_single_stave_optical_contract.py

9 passed in 0.08s
```

A 120-row synthetic current-contract table also completed the full analyzer
path. `result.json` returned `PASS_SMOKE`, contract `CURRENT_COMPONENT_SUM`, and
denominator `n_optical_generated_total`; G4S-03 plot metadata and source data
recorded the same denominator and contract. The manifest contained 22 hashed
outputs. JSON and SVG parsing passed. Maximum changed Python line length was
100. Ruff was unavailable in the execution environment.

## Direct-main sequence

- `10701b3c723e1380dba59b848eb1904fa6428cac` — analyzer remediation
- `c3e8c8ae3bb49ad08cb60b9b62d0257166cbe9e6` — focused tests
- `af7150d84567a23305fd7a191b05a81b79d82f52` — event-contract documentation
- `ab42dadd2d0e6b681082de059fbddf9824a600d2` — Geant4 README synchronization
- `96d517caccf8590f7b02acc57f1cbe1c3685c6eb` — evidence renderer
- `cadc6afaf5eb12a3697994e187dbca4606bf9a73` — validation JSON
- `f4eeab819e223dd16b42d46cc85b607d90138c0d` — SVG evidence
- `f2477309b4ac7e6ed15946752c70747b67837eed` — audit report
- `b9c976759c054797273cf1367821e7ee5dafd370` — immutable archive
- `0b4e05b2432284cb0d2d06fffcdae98a27087cd3` — active-task update
- `a67a84fcfe206de5e091966226e1a67024cc1ada` — complete handoff

The connector returns commit SHAs rather than conventional textual `git push`
stdout. Remote history confirmed the delivery handoff on `main`.

## Checks not run

Repository-wide pytest/ruff, Geant4 build and CTest, immutable production ROOT
execution, GitHub Actions, and repository-wide link inventory were not run. No
broad CI, calibration, or physics-closure claim is made.

## Coordination boundary

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced because the connector provides
whole-file replacement rather than byte-safe append/patch. Replacing a partial
or stale reconstruction could erase unrelated long-lived or append-only
provenance. The immutable archive and this handoff are the append-equivalent
record; mandatory aggregate synchronization remains an explicit governance gap.

## Scientific boundary and next gate

No real ROOT bytes were processed, no Geant4 event was generated, and no optical
yield, calibration, resolution, PID, or detector-performance quantity was
measured or changed.

`AUD-G4-022` remains `PARTIAL`. Completion now requires executing the adapter and
analyzer on immutable real current-ROOT bytes with the producer sidecar and
commit, ROOT and normalized hashes, row-count closure, result/manifest hashes,
and review of all real generated diagnostics.

PR #868 remains closed, unmerged, and untouched.
