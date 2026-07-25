# Latest Handoff — AUD-G4-022 single-stave event contract

## Delivery identity

- **Session stamp:** `2026-07-25T133443Z`
- **Initial remote `main`:** `2f653429c2b7ead1d35752a23f3bb908506dd23d`
- **Validated implementation/evidence head before archive:**
  `e1aca1062e09fafd9a2b48ab10af7f204ef64556`
- **Validated delivery / recorded after-SHA:**
  `c90dc985b6a70bf95a4fe42e3f1822ea61a2f4da`
- **Destination:** direct contents-API commits to remote `main`; no force-push,
  history rewrite, task branch, or PR transport
- **Push result:** every contents write returned a successful commit SHA; recent
  remote history confirmed the implementation, documentation, evidence, active
  task, and immutable archive on `main`
- **Focused acceptance:** `VALIDATED`
- **Cumulative task status:** `PARTIAL`
- **Immutable archive:**
  `chatgpt_todo/archive/2026-07-25T133443Z_AUD-G4-022_EVENT_CONTRACT.md`

A concurrent Chapter 8 task was active at the start of this run and completed as
`2848a996a35d45951b97287ea51edca11ec22036`. This session selected a
non-overlapping single-stave contract task and preserved that concurrent work.

## Confirmed repository defect

The current producer and analyzer were not directly contract-compatible:

| Current producer field | Required normalized field | Correction |
|---|---|---|
| `event` | `event_id` | explicit rename |
| `particle` | `particle_pdg` | proton → 2212; deuteron → 1000010020 |
| `ke_MeV` | `kinetic_energy_MeV` | explicit rename |
| `arrival_readout` | `n_end_selected` | physical readout mapping |
| `detected_readout` | `n_detected_pe` | physical readout mapping |
| `track_len_scint_mm` | `track_length_scint_cm` | mm / 10 |

The analyzer also bounded all readout arrivals by the scintillation-only counter,
although the producer separately records scintillation, WLS, and Cerenkov
optical tracks. The auditable total is:

```text
n_optical_generated_total =
    n_scint_generated + n_wls_generated + n_cerenkov_generated
```

The Geant4 README additionally implied direct analyzer compatibility and an
implemented `--mode fast`; the current CLI rejects fast mode.

## Validated engineering work

Added `scripts/single_stave/adapt_geant4_events.py` under policy
`CURRENT_GEANT4_EVENT_TREE_MUST_MAP_EXPLICITLY_TO_ANALYSIS_CONTRACT`.

It performs explicit mapping and unit conversion, preserves the three generated
optical categories, adds the total, validates count ordering, rejects malformed
or ambiguous data, checks input identity before/after reading, prevents
path-alias destruction and accidental overwrite, atomically publishes each
artifact, and records input/output byte counts and SHA-256 values.

The adapter reports `analysis_compatibility=SCHEMA_ADAPTER_ONLY`: the legacy
analyzer still applies the scintillation-only bound and denominator. This is a
truth-preserving blocker, not a claim of end-to-end acceptance.

Added:

- `tests/test_adapt_geant4_events.py`;
- `scripts/single_stave/EVENT_CONTRACT.md`;
- `tools/audit/render_single_stave_event_contract_evidence.py`;
- `docs/validation/single_stave_event_contract_audit.md`;
- `docs/validation/single_stave_event_contract_validation.json`;
- `docs/validation/single_stave_event_contract.svg`.

Corrected `geant4/single_stave/README.md` to remove the false direct-analysis
and implemented-fast-mode implications. Corrected README blob:
`a0d2cc0ab61562ba9c6d58dcc9bb53fcdba9f3d0`.

## Source and artifact identities

- producer Git blob: `2e10565aa41182618083634cd18b6ddae89660da`;
- analyzer Git blob: `5a3fdd88757bec8b8f39b2ca9f7be889b70e848c`;
- adapter SHA-256:
  `883a5108c054db4e103838869c199d7e2e6588ec3b72170f41bf89b60f772b3c`;
- tests SHA-256:
  `a66ddce0d2cd2198b146e9ee72c5153bb97de894f92cdaa00b7ca6714e303f71`;
- renderer SHA-256:
  `e1cac840006b64deca45241f888dccd971a39b1aeaee537c931bedf1fab636ad`;
- event-contract documentation SHA-256:
  `6beab423f2f8a976662ddf08836380db6b28bff381d076ea5844b25f35568b8b`;
- final audit Markdown SHA-256:
  `fa7b69f8618368422cabb5337e15f91e32b15e081120435cb2ccb4c6950c51a6`.

## Validation

```text
python -m py_compile \
  scripts/single_stave/adapt_geant4_events.py \
  tests/test_adapt_geant4_events.py \
  tools/audit/render_single_stave_event_contract_evidence.py

pytest -q tests/test_adapt_geant4_events.py

12 passed in 1.59s
```

Controls cover the exact current `RunAction.cc` branch declarations, field and
particle mapping, mm-to-cm conversion, WLS-inclusive generated-track accounting,
invalid count ordering, nonfinite/fractional/negative counts, ambiguity,
duplicate keys, atomic publication, overwrite protection, and destructive
aliases. JSON parsing, SVG XML parsing, and the 95-character maximum Python line
length passed.

## Direct-main commit sequence

- `da481285c050d0761aa4fce8c5c68d3336528864` — event-tree adapter;
- `7a712f39d1a344f3966fff5f951baa240ba56cc6` — focused tests;
- `0ebc84a7352a5073d90ed250ae50db57dbbf61d3` — event-contract documentation;
- `23c230589fa1eff3f0c3f8dffa84caf4b4fa04ea` — evidence renderer;
- `0c24e5e3a26b3119f71c223624e01473d163c681` — initial validation JSON;
- `6661e25fc4218c5e142c71992d7d7ac222d07d68` — visual evidence;
- `033f97334d1aec80b0ad3cd3c37ca0824125f39a` — initial audit report;
- `39d9dc0aacccc93d2e4d0ae86ef5da8d58c1f4c1` — public README correction;
- `4e552b31d3729add954823e62df4923db6577a0c` — audit/source update;
- `17e71903ef4295773241aa6c6911d9252289d4bd` — final JSON/source binding;
- `e1aca1062e09fafd9a2b48ab10af7f204ef64556` — active-task update;
- `c90dc985b6a70bf95a4fe42e3f1822ea61a2f4da` — immutable archive and
  validated delivery head.

The connector returns commit SHAs rather than conventional textual `git push`
stdout. Post-write remote history confirmed the sequence on `main`.

## Checks not run

- repository-wide pytest and ruff;
- Geant4 build, CMake, or CTest;
- execution on a real current ROOT `events` ntuple;
- integrated analyzer regression after changing the downstream bound;
- GitHub Actions;
- repository-wide broken-link inventory.

No broad CI, calibration, or physics-closure claim is made.

## Coordination boundary

`ACTIVE_TASK.md` was updated after the concurrent task reached `COMPLETE`.
`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were reviewed but not replaced. The connector exposes whole-file
replacement rather than byte-safe append/patch and these shared records are
long-lived and partly stale relative to later immutable archives. Replacing an
incomplete reconstruction could erase unrelated provenance. The immutable
archive and this handoff are the append-equivalent record; aggregate
synchronization remains an explicit governance gap.

## Scientific boundary and next gate

No real ROOT bytes were processed, no Geant4 event was generated, and no
optical yield, calibration, resolution, PID, or detector-performance quantity
was measured or changed.

`AUD-G4-022` remains `PARTIAL`. Completion requires updating
`analyze_single_stave.py` to consume and report the scintillation/WLS/Cerenkov
components and total without semantic renaming, adding an integrated current-
ROOT regression, and executing the complete path on immutable real ROOT bytes
with code/input/output hashes and row-count closure.

PR #868 remains closed, unmerged, non-mergeable, and untouched.
