# Immutable handoff — AUD-G4-022 single-stave event contract

## Session identity

- **UTC stamp:** `2026-07-25T133443Z`
- **Task:** `AUD-G4-022`
- **Initial remote main:** `2f653429c2b7ead1d35752a23f3bb908506dd23d`
- **Owner:** scheduled scientific-review session
- **Destination:** direct contents-API commits to `main`; no branch, PR,
  force-push, or history rewrite
- **Focused result:** `VALIDATED`
- **Cumulative status:** `PARTIAL`

A concurrent Chapter 8 task was already active at the start of the run. This
session selected a non-overlapping single-stave producer/analysis-contract unit,
preserved the other task, and only changed `ACTIVE_TASK.md` after the concurrent
record had reached `COMPLETE`.

## Repository facts reviewed

Reviewed current main history, open PRs, PR #868, the mandatory coordination
files, the single-stave CMake/README/configuration, `RunAction.cc`,
`analyze_single_stave.py`, its tests and documentation, and the older PR #881
review. The exact source identities bound by the validation record are:

- producer `geant4/single_stave/src/RunAction.cc`, Git blob
  `2e10565aa41182618083634cd18b6ddae89660da`;
- analyzer `scripts/single_stave/analyze_single_stave.py`, Git blob
  `5a3fdd88757bec8b8f39b2ca9f7be889b70e848c`.

PR #868 remained closed, unmerged, and non-mergeable and was not modified.

## Confirmed defect

The producer writes `event`, `particle`, `ke_MeV`, `arrival_readout`,
`detected_readout`, and `track_len_scint_mm`. The analyzer requires normalized
`event_id`, `particle_pdg`, `kinetic_energy_MeV`, `n_end_selected`,
`n_detected_pe`, and `track_length_scint_cm`; its alias table did not map the
current readout branches or the track-length unit.

The analyzer additionally bounded all selected-end arrivals by
`n_scint_generated`. The producer separately records scintillation, WLS, and
Cerenkov generated optical tracks. The explicit bookkeeping total is therefore:

```text
n_optical_generated_total =
    n_scint_generated + n_wls_generated + n_cerenkov_generated
```

The public Geant4 README also implied direct analyzer compatibility and
presented `--mode fast` as available, while the CLI explicitly rejects fast mode.

## Validated implementation

Added `scripts/single_stave/adapt_geant4_events.py` v1.0.0 under policy
`CURRENT_GEANT4_EVENT_TREE_MUST_MAP_EXPLICITLY_TO_ANALYSIS_CONTRACT`.

The adapter:

- maps current branch names explicitly, including physical readout sensor
  semantics;
- maps proton/deuteron labels to exact PDG codes;
- converts `track_len_scint_mm` to `track_length_scint_cm` using mm / 10;
- retains all three generated optical categories and adds their total;
- validates arrivals against the total and detected PE against arrivals;
- rejects missing/ambiguous columns, unknown species, nonfinite values,
  fractional/negative counts, invalid event IDs/energies, duplicate keys,
  destructive aliases, changed input bytes, and accidental overwrite;
- records exact input/output byte size and SHA-256 plus the mapping and
  downstream compatibility boundary;
- publishes the table and metadata atomically per artifact.

The adapter reports `analysis_compatibility=SCHEMA_ADAPTER_ONLY`. This is
intentional: the legacy analyzer still uses the scintillation-only denominator
and is not yet accepted for direct current-ROOT analysis.

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

## Validation

Executed on exact local reconstruction:

```text
python -m py_compile \
  scripts/single_stave/adapt_geant4_events.py \
  tests/test_adapt_geant4_events.py \
  tools/audit/render_single_stave_event_contract_evidence.py

pytest -q tests/test_adapt_geant4_events.py

12 passed in 1.59s
```

The source-bound regression covers all required current `RunAction.cc` branch
names. Additional controls cover field mapping, unit conversion, WLS-inclusive
optical-count semantics, invalid ordering, nonfinite/fractional/negative values,
ambiguous columns, atomic output, existing-output protection, and input aliases.
JSON parsing, SVG XML parsing, and changed-Python line-length checks passed; the
maximum line length was 95 characters.

Machine-readable identities:

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

## Direct-main commits before this archive

- `da481285c050d0761aa4fce8c5c68d3336528864` — adapter;
- `7a712f39d1a344f3966fff5f951baa240ba56cc6` — tests;
- `0ebc84a7352a5073d90ed250ae50db57dbbf61d3` — event contract;
- `23c230589fa1eff3f0c3f8dffa84caf4b4fa04ea` — evidence renderer;
- `0c24e5e3a26b3119f71c223624e01473d163c681` — initial validation JSON;
- `6661e25fc4218c5e142c71992d7d7ac222d07d68` — SVG evidence;
- `033f97334d1aec80b0ad3cd3c37ca0824125f39a` — initial audit report;
- `39d9dc0aacccc93d2e4d0ae86ef5da8d58c1f4c1` — README correction;
- `4e552b31d3729add954823e62df4923db6577a0c` — report/source binding;
- `17e71903ef4295773241aa6c6911d9252289d4bd` — final JSON/source binding;
- `e1aca1062e09fafd9a2b48ab10af7f204ef64556` — active-task record.

The contents API returned successful commit SHAs rather than conventional
textual `git push` output. Recent remote history showed the sequence on `main`.
The concurrent Chapter 8 archive/handoff commit
`2848a996a35d45951b97287ea51edca11ec22036` was preserved in history.

## Checks not run

- complete repository pytest and ruff;
- CMake/CTest or a Geant4 build;
- execution on a real current ROOT `events` ntuple;
- the existing analyzer's full fixture suite after an analyzer change;
- GitHub Actions;
- repository-wide broken-link inventory.

No broader CI or physics closure is claimed.

## Coordination boundary

`ACTIVE_TASK.md` was safely updated after the concurrent task became complete.
`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were not replaced because the connector exposes whole-file replacement
rather than byte-safe append/patch and those shared records are long-lived and
partly stale relative to immutable archives. Replacing an incomplete
reconstruction could erase unrelated provenance. This archive and the latest
handoff are the append-equivalent record; aggregate synchronization remains an
explicit governance gap.

## Scientific boundary and next acceptance gate

No real ROOT bytes were processed, no Geant4 event was generated, and no
optical yield, calibration, resolution, PID, or detector-performance quantity
was measured or changed.

`AUD-G4-022` remains `PARTIAL`. Completion requires updating
`analyze_single_stave.py` to consume and report scintillation/WLS/Cerenkov
component counts and `n_optical_generated_total` without semantic renaming,
adding an integrated current-ROOT regression, and executing the complete path
on immutable real ROOT bytes with code/input/output hashes and row-count
closure.
