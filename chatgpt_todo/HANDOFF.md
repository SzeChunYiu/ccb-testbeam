# Latest Scientific Review Handoff

## Session

- UTC: `2026-07-23T23:08:25Z`
- Task: `AUD-G4-019`
- Repository: `SzeChunYiu/ccb-testbeam`
- Initial remote main: `eec220db6807d3d3615d92c6d39d4fb2e18e4335`
- Validated implementation/evidence head: `807febe85c35b537c53a5acdf1795ee9a67d7cb2`
- Remote main immediately before final handoff: `d213721e6b6e8b3a50394d18529ef07237e42b06`
- Destination: direct to `main`
- Acceptance: COMPLETE for simulation-table parse/provenance byte-snapshot identity; accepted stopping-power physics closure remains PARTIAL/BLOCKED.

## Start-of-run and concurrent-work review

- Fetched current remote-main history and confirmed repository admin/push permission.
- Inspected the canonical stopping-power comparison, shared simulation parser, parser tests, previous handoff, active task, backlog, master index, code-result map, study ledger, claim matrix, visualization matrix, blocker register, PR #868, and commit status.
- `AUD-REPO-001` remained owned by a concurrent session and was not duplicated.
- PR #868 remains closed, unmerged, and non-mergeable. It was not reopened, changed, or merged.
- A direct clone/fetch attempt failed with `Could not resolve host: github.com`; exact source/test bytes were reconstructed through authenticated GitHub reads.
- Every session write targeted current `main`; no force push, history rewrite, task branch, or unrelated rollback was used.

## Confirmed provenance defect

`tools/audit/validate_stopping_power_sim_table.py` v1.1.0 used separate path reads for scientific content and provenance:

1. `Path.read_text()` supplied the CSV rows;
2. `Path.stat().st_size` later supplied byte count;
3. `sha256_file()` later streamed the path again for the digest.

If the path was replaced between these operations, normalized event rows could describe bytes A while the recorded byte count and SHA-256 described bytes B. The parser also allowed invalid UTF-8 to escape as an uncaught `UnicodeDecodeError` rather than the documented status-2 input failure.

## Validated correction

Validator v1.2.0 now:

1. reads exact input bytes once;
2. decodes and parses that byte string;
3. calculates byte count from `len(input_bytes)`;
4. calculates SHA-256 from the same byte string;
5. records `input_snapshot_method=SINGLE_READ_EXACT_BYTES`;
6. maps invalid UTF-8 to `SimulationTableError`, so the CLI returns status 2 without a validation success line.

All existing particle, energy, energy-deposit, track-length, alias, finite-value, physical-value, raw/quenched, and complete-row gates are retained.

## Regression and validation

Added `tests/test_validate_stopping_power_sim_snapshot.py`.

```text
python -m py_compile \
  tools/audit/validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_snapshot.py

python -m pytest \
  tests/test_validate_stopping_power_sim_table.py \
  tests/test_validate_stopping_power_sim_snapshot.py -q

19 passed in 2.01s
```

The deterministic mutation regression replaces the path after data-line formation and verifies that returned rows, size, and digest remain bound to the original byte snapshot. The exact former algorithm fails both new assertions: provenance follows replacement bytes, and invalid UTF-8 raises an uncaught decoder exception.

Additional passed checks:

- validation JSON parse;
- SVG XML parse;
- maximum changed Python line length 94;
- committed implementation blob `6a57b93d6fb4f63a7b714b858d379f02b5a7eda0` equals the locally validated blob;
- implementation SHA-256 `35068d8dd59680ab12ac9f4f595cbc00fb406713d09c931a7071ca7caf317bee`.

Not run: full repository pytest, ruff, Geant4/CTest, ROOT processing, real simulation execution, or GitHub Actions. No broader CI, simulation, or physics-closure success is claimed.

## Reproducible evidence

- `docs/validation/stopping_power_sim_snapshot_audit.md`
- `docs/validation/stopping_power_sim_snapshot_validation.json`
- `docs/validation/stopping_power_sim_snapshot.svg`

The SVG is explicitly synthetic software regression evidence, not detector data. It contrasts the former split-read path with the corrected one-snapshot path using text, position, and cross-out rather than color alone.

## Direct-to-main commit sequence

Core implementation, test, and evidence:

- `efc9610bd382ea52f6bbc8e53be87af6c74766fa` — `fix(audit): bind simulation rows to one byte snapshot`
- `76b5e1dcf5e8fb3ad9c66a9646dd8ddab3d3dcea` — `test(audit): cover simulation byte-snapshot provenance`
- `964042dc25b1b0abcd0eac0ec35e4f1b3268abe7` — validation audit Markdown
- `f28049ce952bf5e8194f7c3936adab2401d713b6` — validation JSON
- `807febe85c35b537c53a5acdf1795ee9a67d7cb2` — validation SVG

Coordination and provenance:

- `17322a138cc160eef09beadd2ede6df5a4076625` — active task
- `462738e51fdfc93cb5eaef34e0de1d8260369c83` — backlog
- `b29e86b5aec0cc0493e6b795cb7877c00d174f77` — immutable archive
- `c9e5b50c0026b356972c21e9230af00507e683d2` — preliminary handoff
- `29e4180d42c57930e912dc4bb935f3759bdba979` — initial master-index update
- `5c77fbcc5a9edf98446c5fcf89af8ed4578ae6bf` — initial code-result-map update
- `a5a0cf92441a7aa67b7e3a8cf7bf8184c13167a4` — initial study-ledger update
- `42b63d60890a06af44a243c1471358a4157955eb` — initial claim-matrix update
- `efa495871170032a9476fcf35313f2e770dea70e` — initial visualization-matrix update
- `149e5cb6d8a3fed65505c5243c875b7a9637053b` — blocker register
- `dee38edb723f0ace9faa283824e3393aa018c270` — prior final handoff
- `97b5c487d22c8c68bfdab3e9a37f53557516e734` — preserve all pre-existing master-index detail while retaining new row
- `67a7f7a2ef4df7c1bac40ee54c1d272de44cec14` — preserve all pre-existing code-result-map detail while retaining new row
- `928814ccbfb23c7eda4c7a97f7d576ee8970a827` — preserve all pre-existing study-ledger detail while retaining new row
- `65b18a66f7d9286a189ff29d4f9df3ffa7c622bf` — preserve all pre-existing claim-matrix detail while retaining new row
- `d213721e6b6e8b3a50394d18529ef07237e42b06` — preserve all pre-existing visualization-matrix detail while retaining new row

The preservation commits correct an over-broad first coordination rewrite and ensure unrelated existing audit detail remains intact. Every contents write returned a successful direct-main commit. The commit containing this final handoff is confirmed separately through remote-main history after the write.

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
- `HANDOFF.md`

Added immutable session record:

- `chatgpt_todo/archive/2026-07-23T230825Z_AUD-G4-019_SIM_INPUT_SNAPSHOT.md`

`SESSION_LOG.md` was not replaced because it is append-only, the connector exposes complete-file replacement rather than a safe append primitive, and a complete byte-safe current payload was not available. Replacing it could destroy prior provenance. The immutable archive is the complete reproducible session record; this coordination limitation is not a scientific acceptance claim.

## Scientific boundary and next task

This establishes that normalized simulation rows and their reported input digest derive from one exact byte snapshot. It does not validate a real Geant4 export, establish that local deposited energy equals projectile total energy loss, quantify secondary escape or energy evolution, implement an uncertainty budget, or demonstrate Geant4/PSTAR agreement.

`AUD-G4-019` is COMPLETE. `BLK-G4-SP-001` remains OPEN. The next accepted stopping-power work remains `AUD-G4-011` and `AUD-G4-005`: validate immutable real exports and an accepted projectile-loss observable, quantify secondary escape and energy evolution, then preregister and propagate uncertainty before evaluating closure.
