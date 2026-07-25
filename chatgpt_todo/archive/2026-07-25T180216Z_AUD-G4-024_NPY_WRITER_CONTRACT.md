# AUD-G4-024 — NPY writer contract remediation

## Session identity

- Session stamp: `2026-07-25T180216Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `a5b108fc8ead2f644c8b362f3a8732ef1d0528fc`
- Task status: focused `VALIDATED`; cumulative `PARTIAL`
- Policy: `NPY_OUTPUT_MUST_BE_LITTLE_ENDIAN_AND_FAIL_CLOSED`

## Repository state reviewed

- current remote-main history and combined status;
- open PR inventory;
- closed, unmerged PR #868;
- merged Opticks PR #920;
- `chatgpt_todo/ACTIVE_TASK.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and
  `HANDOFF.md`;
- `geant4/single_stave/include/NpyWriter.hh`;
- `geant4/single_stave/src/RunAction.cc`, `SteppingAction.cc`,
  `StackingAction.cc`, `TrackingAction.cc`, and `EventAction.cc`;
- `geant4/single_stave/CMakeLists.txt`.

The repository could not be cloned because the execution container could not
resolve `github.com`; exact source bytes were fetched through the GitHub
connector and the focused standalone files were reconstructed locally.

## Confirmed defects

Former NPY writer blob: `21ab586666daa978e4befa3b7b3387e808d76495`.

1. NumPy v1.0 requires the two-byte header length to be little-endian, but the
   writer copied native `uint16_t` bytes.
2. The header declared `<f4`, but the writer emitted native float bytes.
3. Shape multiplication could overflow silently.
4. A non-empty shape could be paired with a null data pointer.
5. Stream open/write/flush state was never checked.
6. Exact former-code negative control: writing beneath a missing parent
   directory returned status `0` and produced no file.

Authoritative format source:
<https://numpy.org/doc/2.0/reference/generated/numpy.lib.format.html>.

## Remediation

Corrected header blob: `0db837e3614eb725571e3863fce3a15855c52f03`.

- Explicit little-endian v1.0 header length.
- Little-endian float32 emission on both little- and big-endian hosts.
- Non-empty shape requirement.
- Checked shape product.
- Null payload rejection for non-empty arrays.
- Checked output open, write, and flush state.
- Exceptions propagate before `RunAction` can print a successful
  `CCB_GPU_PHOTONS` line.

## Validation

```text
python -m py_compile \
  tests/test_npy_writer_contract.py \
  tools/audit/render_npy_writer_contract_evidence.py

pytest -q tests/test_npy_writer_contract.py
6 passed in 0.36s
```

Validated cases:

- exact values and dtype loaded by NumPy;
- explicit little-endian header bytes;
- valid empty `(0,4,4)` output;
- fail-closed non-empty null pointer;
- fail-closed shape overflow;
- fail-closed unwritable path.

JSON parsing and SVG XML parsing passed. Maximum changed line lengths were 82
characters for C++ and 92 for Python.

## Files changed

Updated:

- `geant4/single_stave/include/NpyWriter.hh`
- `chatgpt_todo/ACTIVE_TASK.md`

Added:

- `tests/test_npy_writer_contract.py`
- `tools/audit/render_npy_writer_contract_evidence.py`
- `docs/validation/npy_writer_contract_validation.json`
- `docs/validation/npy_writer_contract.svg`
- `docs/validation/npy_writer_contract_audit.md`
- this immutable archive.

## Direct-main commits through active-task completion

- `e54f1f5d8c3a3175e3bce56e459d461c523e01cc` — fail-closed writer
- `09d4409e2b9091718b563b98da186376ce22cad6` — compiled regression
- `b3dfbf5ab5a5710b5ada0e634c1ccfd6324269e8` — initial renderer
- `5e064ca5bca2b1472679cf22071ef375dc3a8d8c` — valid SVG renderer
- `c81ebf5e3ef42440429aae01f6712af491ce013e` — validation JSON
- `1aea4a30415a8fb95dd12d91ed8c30fb07c6e64b` — SVG evidence
- `c8f0cbca9033010861c7982c1358d17d3e80c945` — audit report
- `6444cc6693bd3c5183c9f88e4f25adbf24c1cc97` — active task

GitHub contents writes returned commit SHAs rather than conventional textual
`git push` stdout. No force push, branch, or PR transport was used.

## Scientific boundary

This is serialization and artifact-integrity validation, not optical-physics
validation. No Geant4 event, Opticks propagation, GPU hit collection, optical
yield, sensor response, calibration, or detector-performance result was
produced or changed.

The next GPU-focused review should validate the event-vector cardinality
against the `(N,4,4)` shape, creator-process accounting, GPU/CPU mode metadata,
output-directory failures, immutable per-event hashes, successful hit gather,
and preregistered CPU/GPU parity diagnostics.

## Unrun checks

- full Geant4 build and CTest;
- Opticks A40 execution;
- real input-photon regeneration;
- repository-wide pytest and ruff;
- broad broken-link inventory;
- GitHub Actions.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, `MASTER_INDEX.md`, and aggregate
matrices were read but not replaced. The connector exposes whole-file
replacement while the complete shared records are paged or truncated; replacing
a partial reconstruction could erase unrelated append-only provenance. This
archive and the latest handoff preserve the complete append-equivalent record.
