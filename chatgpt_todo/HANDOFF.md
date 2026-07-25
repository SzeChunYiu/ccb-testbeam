# Latest Handoff — AUD-G4-022 single-stave event contract

## Delivery identity

- **Session stamp:** `2026-07-25T133443Z`
- **Initial remote `main`:** `2f653429c2b7ead1d35752a23f3bb908506dd23d`
- **Validated implementation/evidence head:**
  `e1aca1062e09fafd9a2b48ab10af7f204ef64556`
- **Immutable archive commit:**
  `c90dc985b6a70bf95a4fe42e3f1822ea61a2f4da`
- **Validated delivery handoff / recorded after-SHA:**
  `937e8cdaba7181c494e0be839b1b8b59d0dba042`
- **Destination:** direct contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport
- **Push result:** every contents write returned a successful commit SHA;
  post-write remote history confirmed `937e8cdaba7181c494e0be839b1b8b59d0dba042`
  and all focused predecessors on `main`
- **Focused acceptance:** `VALIDATED`
- **Cumulative task status:** `PARTIAL`
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T133443Z_AUD-G4-022_EVENT_CONTRACT.md`

A concurrent Chapter 8 task was active when this run began and completed as
`2848a996a35d45951b97287ea51edca11ec22036`. This session selected a
non-overlapping single-stave contract unit and preserved that work.

## Confirmed defect and correction

The current producer writes `event`, `particle`, `ke_MeV`,
`arrival_readout`, `detected_readout`, and `track_len_scint_mm`; the analyzer
expects different normalized names and centimetres. Its alias table did not map
the two current readout branches or the track-length unit.

The analyzer also bounded all arrivals by the scintillation-only count despite
separate producer counters for scintillation, WLS, and Cerenkov optical tracks.
The explicit auditable total is:

```text
n_optical_generated_total =
    n_scint_generated + n_wls_generated + n_cerenkov_generated
```

Added `scripts/single_stave/adapt_geant4_events.py` under policy
`CURRENT_GEANT4_EVENT_TREE_MUST_MAP_EXPLICITLY_TO_ANALYSIS_CONTRACT`. It maps
fields and particle labels explicitly, converts mm to cm, retains component
counters, adds the total, validates count ordering, rejects malformed or
ambiguous data, checks input identity, protects paths/previous outputs, and
records byte counts and SHA-256 provenance.

The adapter reports `analysis_compatibility=SCHEMA_ADAPTER_ONLY`. The existing
analyzer still uses the scintillation-only bound and denominator; this remains a
truth-preserving blocker rather than being hidden by the conversion layer.

The public `geant4/single_stave/README.md` was corrected to stop advertising
direct analyzer compatibility or an implemented `--mode fast`. Corrected README
Git blob: `a0d2cc0ab61562ba9c6d58dcc9bb53fcdba9f3d0`.

## Files delivered

- `scripts/single_stave/adapt_geant4_events.py`
- `scripts/single_stave/EVENT_CONTRACT.md`
- `tests/test_adapt_geant4_events.py`
- `tools/audit/render_single_stave_event_contract_evidence.py`
- `docs/validation/single_stave_event_contract_audit.md`
- `docs/validation/single_stave_event_contract_validation.json`
- `docs/validation/single_stave_event_contract.svg`
- corrected `geant4/single_stave/README.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`
- immutable archive listed above
- this handoff

## Source and artifact identities

- producer Git blob: `2e10565aa41182618083634cd18b6ddae89660da`
- analyzer Git blob: `5a3fdd88757bec8b8f39b2ca9f7be889b70e848c`
- adapter SHA-256:
  `883a5108c054db4e103838869c199d7e2e6588ec3b72170f41bf89b60f772b3c`
- tests SHA-256:
  `a66ddce0d2cd2198b146e9ee72c5153bb97de894f92cdaa00b7ca6714e303f71`
- renderer SHA-256:
  `e1cac840006b64deca45241f888dccd971a39b1aeaee537c931bedf1fab636ad`
- contract documentation SHA-256:
  `6beab423f2f8a976662ddf08836380db6b28bff381d076ea5844b25f35568b8b`
- audit Markdown SHA-256:
  `fa7b69f8618368422cabb5337e15f91e32b15e081120435cb2ccb4c6950c51a6`

## Validation

```text
python -m py_compile \
  scripts/single_stave/adapt_geant4_events.py \
  tests/test_adapt_geant4_events.py \
  tools/audit/render_single_stave_event_contract_evidence.py

pytest -q tests/test_adapt_geant4_events.py

12 passed in 1.59s
```

The regression binds the exact current `RunAction.cc` branch declarations and
covers mapping, PDG conversion, mm-to-cm conversion, WLS-inclusive optical-count
semantics, invalid ordering, nonfinite/fractional/negative values, ambiguous
columns, duplicate keys, atomic publication, overwrite protection, and path
aliases. JSON and SVG parsing passed; maximum changed Python line length was 95.

## Direct-main sequence

`da481285`, `7a712f39`, `0ebc84a7`, `23c23058`, `0c24e5e3`,
`6661e25f`, `033f9733`, `39d9dc0a`, `4e552b31`, `17e71903`,
`e1aca106`, `c90dc985`, and `937e8cda` are the ordered focused commits;
full SHAs are retained in the immutable archive and Git history.

The connector returns commit SHAs rather than conventional textual `git push`
stdout. Remote history confirmed the delivery handoff on `main`.

## Checks not run

Repository-wide pytest/ruff, Geant4 build and CTest, real ROOT execution,
integrated analyzer validation after its downstream correction, GitHub Actions,
and repository-wide link inventory were not run. No broad CI or physics closure
is claimed.

## Coordination boundary

`ACTIVE_TASK.md` was updated after the concurrent task became complete.
`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced because the connector provides
whole-file replacement rather than byte-safe append/patch. Replacing an
incomplete reconstruction could erase unrelated long-lived provenance. The
archive and handoff are the append-equivalent record; aggregate synchronization
remains an explicit governance gap.

## Scientific boundary and next gate

No real ROOT bytes were processed, no Geant4 event was generated, and no optical
yield, calibration, resolution, PID, or detector-performance quantity was
measured or changed.

`AUD-G4-022` remains `PARTIAL`. Completion requires updating
`analyze_single_stave.py` to consume and report scintillation/WLS/Cerenkov
components plus the total without semantic renaming, adding an integrated
current-ROOT regression, and executing the complete path on immutable real ROOT
bytes with code/input/output hashes and row-count closure.

PR #868 remains closed, unmerged, non-mergeable, and untouched.
